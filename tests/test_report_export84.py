"""Export lifecycle, fidelity, failure recovery and complete evidence."""
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from docx import Document
import pandas as pd
import plotly.graph_objects as go
import pytest

from concrete_pmm_pro.reporting import figure_export as images, bg40_word as word
from concrete_pmm_pro.ui import bg40_report as ui
from test_word_report_export import _one_pixel_png
from test_igird_reportcharts8 import calculated_state


def test_real_renderer_reuses_one_worker_and_matches_configured_native_png_pixels():
    figure = go.Figure(go.Bar(x=['A', 'B'], y=[1.234567, -2.345678]))
    figure.update_layout(width=480, height=320)
    # Compare reuse to a fresh native render with the same Cloud profile.
    script = ("import plotly.io as pio,sys; pio.kaleido.scope.mathjax=None; "
              "pio.kaleido.scope.chromium_args += ('--single-process',); "
              "sys.stdout.buffer.write(pio.from_json(sys.stdin.read()).to_image(format='png'))")
    expected = subprocess.run([sys.executable, '-c', script], input=figure.to_json().encode(),
                              capture_output=True, check=True, timeout=30).stdout
    native_start = images._StaticImageRenderer._start
    starts = []
    def start(renderer):
        native_start(renderer)
        starts.append(renderer.process)
    with patch.object(images._StaticImageRenderer, '_start', start):
        with images.static_image_export_session():
            for _ in range(3):
                data, warnings = images.plotly_figure_to_png_bytes(figure)
                assert not warnings and data == expected
    assert len(starts) == 1
    assert starts[0].poll() is not None
    assert images._RENDERER.get() is None


def test_renderer_recycles_at_batch_limit_without_overlapping_workers(monkeypatch):
    monkeypatch.setattr(images,'MAX_FIGURES_PER_WORKER',2)
    processes=[]
    native=images._StaticImageRenderer._start
    def start(renderer):
        assert all(p.poll() is not None for p in processes)
        native(renderer)
        processes.append(renderer.process)
    with patch.object(images._StaticImageRenderer,'_start',start), images.static_image_export_session():
        for _ in range(5):
            data,warnings=images.plotly_figure_to_png_bytes(go.Figure(go.Bar(x=['A'],y=[1.])))
            assert data and not warnings
    assert len(processes)==3 and all(p.poll() is not None for p in processes)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX process group lifecycle')
@pytest.mark.parametrize('leader_exits', [False, True])
def test_timeout_kills_owned_descendants_and_next_export_can_recover(tmp_path, monkeypatch, leader_exits):
    marker = tmp_path/'child_host_pid.txt'
    worker = tmp_path/'stalled_worker.py'
    # Record the real /proc identity too: the test runner may use PID namespaces.
    child = ("import pathlib,time; "
        f"pathlib.Path({str(marker)!r}).write_text(pathlib.Path('/proc/self/status').read_text()); "
        "time.sleep(60)")
    worker.write_text('import subprocess,sys,time\n'
                      f'subprocess.Popen([sys.executable,"-c",{child!r}])\n'
                      + ('sys.exit(0)\n' if leader_exits else 'time.sleep(60)\n'))
    native_start = images._StaticImageRenderer._start
    def start(renderer):
        native_start(renderer)
        # Replace the lazy real worker before it receives any request.
        images._terminate_process_tree(renderer.process)
        for pipe in (renderer.process.stdin, renderer.process.stdout):
            pipe.close()
        renderer.process = subprocess.Popen([sys.executable,str(worker)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=renderer.stderr,
            text=True,encoding='utf-8',start_new_session=True)
    with monkeypatch.context() as m:
        m.setattr(images._StaticImageRenderer,'_start',start)
        before = monotonic()
        data, warnings = images.plotly_figure_to_png_bytes(go.Figure(), timeout_seconds=1.)
        assert data is None and 'timed out' in ' '.join(warnings)
        assert monotonic()-before < 6.
    assert marker.exists(), 'The stalled renderer descendant must actually have started'
    host_pid = next(line.split()[1] for line in marker.read_text().splitlines() if line.startswith('Pid:'))
    status = Path('/proc')/host_pid/'status'
    deadline = monotonic()+3
    while status.exists() and 'State:\tZ' not in status.read_text() and monotonic()<deadline:
        sleep(.05)
    assert not status.exists() or 'State:\tZ' in status.read_text()
    data, warnings = images.plotly_figure_to_png_bytes(go.Figure(go.Scatter(x=[0,1],y=[0,1])))
    assert data.startswith(images._PNG_SIGNATURE) and not warnings


def test_cancelled_export_closes_worker_and_releases_export_slot():
    process = None
    with pytest.raises(KeyboardInterrupt):
        with images.static_image_export_session() as renderer:
            data,warnings=images.plotly_figure_to_png_bytes(go.Figure(go.Bar(x=['A'],y=[1.])))
            assert data and not warnings
            process=renderer.process
            raise KeyboardInterrupt('Cancelled report')
    assert process.poll() is not None
    with images.static_image_export_session():
        data,warnings=images.plotly_figure_to_png_bytes(go.Figure(go.Bar(x=['A'],y=[1.])))
        assert data and not warnings


def test_evidence_stream_preserves_exact_csv_json_and_repeated_inline_images(monkeypatch):
    doc = Document()
    for _ in range(3):
        doc.add_picture(BytesIO(_one_pixel_png()))
    output = BytesIO(); doc.save(output)
    table = pd.DataFrame({'Thai':['รายการ','ค่า,อ้างอิง',None], 'full_precision':[1.23456789012345,float('nan'),-1e-12]})
    report = SimpleNamespace(sources=table, controls=table.copy(),
        input_snapshot={'Unicode':'สะพาน','values':[1.23456789012345,None]},
        stored_results={'case':'ULS-01','rows':[{'x':1.23456789012345}]},
        figure_audit=[{'number':f'1.{n}','title':'Repeated exact source image','status':'EMBEDDED'} for n in range(1,4)],
        raw_tables={'Full source table':table}, chapters=[],code='AASHTO',workflow_key='i_girder',
        status='FAIL',signature='test-source',warnings=['Engineering review retained'])
    with patch.object(word,'Document',side_effect=AssertionError('Do not reload Word to package evidence')):
        data = word.build_evidence_zip(report,output.getvalue())
    with ZipFile(BytesIO(data)) as archive:
        assert archive.read('Calculation_Report_BG40.docx') == output.getvalue()
        for name in ('Source_Register.csv','Governing_Checks.csv','tables/001_Full_source_table.csv'):
            assert archive.read(name) == table.to_csv(index=False).encode('utf-8-sig')
        for name,value in (('ProjectInputSnapshot.json',report.input_snapshot),
                           ('StoredResultSnapshot.json',report.stored_results),
                           ('Figure_Register.json',report.figure_audit)):
            assert archive.read(name) == json.dumps(value,ensure_ascii=False,indent=2,default=str).encode()
        for n in range(1,4):
            assert archive.read(f'figures/Figure_1_{n}.png') == _one_pixel_png()
        assert json.loads(archive.read('Provenance.json'))['status'] == 'FAIL'


def test_required_renderer_failure_stops_at_first_figure_and_identifies_it(calculated_state, monkeypatch):
    report = ui.build_workflow_report(calculated_state,ui.default_metadata(calculated_state))
    with patch.object(word,'plotly_figure_to_png_bytes',return_value=(None,['Timed out'])) as render:
        with pytest.raises(word.ReportFigureError,match='Figure .*Timed out'):
            ui.build_complete_artifact(calculated_state,report.metadata,report)
    assert render.call_count == 1
    assert ui.ARTIFACT_KEY not in calculated_state


def test_complete_export_reports_progress_without_omitting_any_content(calculated_state, monkeypatch):
    monkeypatch.setattr(word,'plotly_figure_to_png_bytes',lambda *a,**kw:(_one_pixel_png(),[]))
    events=[]
    report = ui.build_workflow_report(calculated_state,ui.default_metadata(calculated_state))
    artifact = ui.build_complete_artifact(calculated_state,report.metadata,report,
        progress=lambda message,fraction:events.append((message,fraction)))
    assert len(artifact['figures']) == sum(len(c.figures) for c in report.chapters)
    assert all(f['status']=='EMBEDDED' for f in artifact['figures'])
    assert events[-1] == ('Complete report ready to download',1.)
    assert all(0<=fraction<=1 for _,fraction in events)
    assert [f for _,f in events] == sorted(f for _,f in events)
    assert len([m for m,_ in events if m.startswith('Creating figure ')]) == len(artifact['figures'])
