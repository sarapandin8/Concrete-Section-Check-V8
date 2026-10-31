"""Full-content Word streaming, original formats, Cloud guard and native chart fidelity."""
from io import BytesIO
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile
from unittest.mock import patch

from docx import Document
from lxml import etree
import numpy as np
import pandas as pd
from PIL import Image
import plotly.graph_objects as go
import pytest
from packaging.requirements import Requirement

from concrete_pmm_pro.reporting import bg40_word as word, bg40_template as reference
from concrete_pmm_pro.reporting import export_runtime as runtime
from concrete_pmm_pro.reporting.figure_export import plotly_figure_to_png_bytes
from concrete_pmm_pro.reporting.word_stream import StreamingWordBody, active_body
from concrete_pmm_pro.ui.bg40_report import build_complete_artifact, default_metadata
from test_igird_reportcharts8 import calculated_state
from test_word_report_export import _one_pixel_png


def canonical(data):
    return etree.tostring(etree.fromstring(data),method='c14n',exclusive=True)


@pytest.mark.parametrize('columns', [3,10])
def test_streamed_tables_preserve_all_original_word_values_and_formats(columns):
    data=pd.DataFrame({f'Column {i}':['Thai สะพาน',' space ','tab\tline\nnext','',
        1.23456789012345,None,-1e-12,float('nan')] for i in range(columns)})
    original=reference.document()
    word._table(original,data,'Complete source rows','Source case A')
    before=BytesIO();original.save(before)
    document=reference.document()
    with StreamingWordBody(document) as stream:
        word._table(document,data,'Complete source rows','Source case A')
        after=stream.save()
    with ZipFile(before) as a,ZipFile(BytesIO(after)) as b:
        assert canonical(a.read('word/document.xml'))==canonical(b.read('word/document.xml'))
        for name in ('word/styles.xml','word/theme/theme1.xml'):
            assert a.read(name)==b.read(name)


def test_large_word_table_retains_every_row_without_accumulating_rows_in_dom():
    total=5000
    data=pd.DataFrame({'Case':[f'Source-{i}' for i in range(total)],
        'Result':[i+0.123456789 for i in range(total)],'Status':['FAIL']*total})
    document=reference.document();pending=[];events=[]
    def progress(message):
        events.append(message)
        pending.append(len(document.element.xpath('.//w:tr')))
    with StreamingWordBody(document,progress=progress) as stream:
        word._table(document,data,'Full source table','No row reduction')
        output=stream.save()
    doc=Document(BytesIO(output))
    assert len(doc.tables[0].rows)==total+1
    assert doc.tables[0].cell(total,0).text==f'Source-{total-1}'
    assert max(pending)<=1
    assert events[-1].endswith('(5,000/5,000 rows)')


def test_cancelled_word_stream_cleans_spool_and_next_document_can_start():
    document=reference.document()
    with pytest.raises(RuntimeError,match='abort'):
        with StreamingWordBody(document) as stream:
            directory=Path(stream.directory.name)
            word._para(document,'Complete source')
            raise RuntimeError('abort')
    assert not directory.exists() and active_body(document) is None
    with StreamingWordBody(reference.document()) as stream:
        assert stream.save().startswith(b'PK')


def test_complete_streamed_word_has_unique_drawing_ids_and_original_native_equations(calculated_state,monkeypatch):
    monkeypatch.setattr(word,'plotly_figure_to_png_bytes',lambda *a,**k:(_one_pixel_png(),[]))
    artifact=build_complete_artifact(calculated_state,default_metadata(calculated_state))
    doc=Document(BytesIO(artifact['docx']))
    ids=[shape._inline.docPr.id for shape in doc.inline_shapes]
    assert len(ids)==len(set(ids))==len(artifact['figures'])>1
    assert [shape._inline.docPr.name for shape in doc.inline_shapes]==[f'Picture {i}' for i in ids]
    assert doc._element.xpath('.//m:oMath')


def test_low_container_headroom_fails_before_more_export_allocations():
    memory={'container_headroom_mib':40.,'container_used_mib':960.,'container_limit_mib':1000.}
    with patch.object(runtime,'memory_snapshot',return_value=memory),patch.object(runtime.gc,'collect') as collect:
        with pytest.raises(runtime.ReportResourceError,match='40.0 MiB'):
            runtime.check_export_headroom()
        assert collect.call_count==1


def test_memory_guard_accepts_recovered_or_unknown_accounting():
    low={'container_headroom_mib':40.,'container_used_mib':960.,'container_limit_mib':1000.}
    enough={'container_headroom_mib':200.}
    with patch.object(runtime,'memory_snapshot',side_effect=[low,enough]):
        assert runtime.check_export_headroom()==enough
    with patch.object(runtime,'memory_snapshot',return_value={}):
        assert runtime.check_export_headroom()=={}


def test_deployment_pins_tested_python312_without_forcing_old_pandas_on_python314():
    requirements=[Requirement(line) for line in Path('requirements.txt').read_text().splitlines()
                  if line.strip() and not line.lstrip().startswith('#')]
    def selected(python):
        return {item.name:str(item.specifier) for item in requirements
                if item.marker is None or item.marker.evaluate({'python_version':python})}
    assert selected('3.12')['pandas']=='==2.2.3'
    assert selected('3.14')['pandas']=='>=2.2'
    for python in ('3.12','3.14'):
        assert selected(python)['plotly']=='==5.24.1'
        assert selected(python)['python-docx']=='==1.2.0'


def test_single_process_chart_matches_native_geometry_with_only_minor_edge_antialiasing():
    figure=go.Figure(go.Bar(x=['A','B'],y=[1.234567,-2.345678]))
    figure.update_layout(width=480,height=320)
    script=("import plotly.io as pio,sys; pio.kaleido.scope.mathjax=None; "
            "sys.stdout.buffer.write(pio.from_json(sys.stdin.read()).to_image(format='png'))")
    original=subprocess.run([sys.executable,'-c',script],input=figure.to_json().encode(),
        capture_output=True,check=True,timeout=30).stdout
    rendered,warnings=plotly_figure_to_png_bytes(figure)
    assert not warnings
    a=np.asarray(Image.open(BytesIO(original)).convert('RGBA')).astype(int)
    b=np.asarray(Image.open(BytesIO(rendered)).convert('RGBA')).astype(int)
    assert a.shape==b.shape
    delta=np.abs(a-b)
    assert float(delta.mean())<.05
    assert float(np.any(delta>32,axis=2).mean())<.001
