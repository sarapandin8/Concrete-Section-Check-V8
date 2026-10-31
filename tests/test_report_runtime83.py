"""Report entry must stay idle; explicit review/export retains source guards."""
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.ui import bg40_report as ui
from concrete_pmm_pro.reporting.bg40_data import _json_signature

APP=Path(__file__).resolve().parents[1]/'app.py'


def report_app(extra=None):
    app=AppTest.from_file(str(APP),default_timeout=120)
    for key,value in {'analysis_mode_settings':{'member_type':'beam_girder'},
        'section_preset_key':'parametric_i_girder','_nav_active_workspace':'Report / QA',**(extra or {})}.items():
        app.session_state[key]=value
    return app


def test_entering_and_reopening_report_does_not_build_documents_scan_export_sources_or_render_charts():
    app=report_app()
    with patch.object(ui,'build_workflow_report',side_effect=AssertionError('Hidden report build')), \
         patch.object(ui,'source_signature',side_effect=AssertionError('Hidden export scan')), \
         patch('concrete_pmm_pro.ui.igird_uls_report.make_package_figure',side_effect=AssertionError('Hidden chart build')):
        for _ in range(3):
            app.run(timeout=120)
            assert not app.exception,[e.message for e in app.exception]
            assert not app.dataframe and not app.get('plotly_chart')
    assert not app.checkbox
    assert any('FAIL, REVIEW, STALE' in w.value for w in app.warning)
    assert next(b for b in app.button if b.key=='bg40_80_build')


def test_saved_report_is_validated_once_per_rerun_without_rebuilding_it():
    app=report_app({ui.ARTIFACT_KEY:{'signature':'current','docx':b'ui-test','evidence':b'ui-test',
        'figures':[],'status':'FAIL','chapters':10}})
    with patch.object(ui,'source_signature',return_value='current') as signature, \
         patch.object(ui,'build_workflow_report',side_effect=AssertionError('Unrequested rebuild')):
        app.run(timeout=120)
    assert not app.exception
    assert signature.call_count==1
    assert any(d.key=='bg40_80_download' for d in app.get('download_button'))
    assert any('Engineering status: FAIL' in t.value for t in app.caption)


def test_stale_download_stays_hidden_without_building_a_replacement():
    app=report_app({ui.ARTIFACT_KEY:{'signature':'old'}})
    with patch.object(ui,'source_signature',return_value='changed'), \
         patch.object(ui,'build_workflow_report',side_effect=AssertionError('Unrequested rebuild')):
        app.run(timeout=120)
    assert not app.exception
    assert not any(d.key=='bg40_80_download' for d in app.get('download_button'))
    assert any('STALE' in w.value for w in app.warning)


def test_explicit_preview_loads_once_and_closing_it_stops_preview_work():
    app=report_app()
    app.run(timeout=120)
    actual=ui.build_workflow_report
    with patch.object(ui,'build_workflow_report',wraps=actual) as build:
        app.session_state['bg40_83_preview_open']=True
        app.run(timeout=120)
        assert not app.exception,[e.message for e in app.exception]
        assert build.call_count==1
        assert app.dataframe
        app.session_state['bg40_83_preview_open']=False
        app.run(timeout=120)
        assert not app.exception
        assert build.call_count==1
        assert not app.dataframe


def test_unexpected_report_preparation_error_keeps_page_alive_and_no_download_is_offered():
    app=report_app();app.run(timeout=120)
    with patch.object(ui,'build_workflow_report',side_effect=RuntimeError('Malformed imported result')):
        next(b for b in app.button if b.key=='bg40_80_build').click().run(timeout=120)
    assert not app.exception
    assert any('complete report could not be created' in e.value for e in app.error)
    assert 'Malformed imported result' in app.session_state[ui.ERROR_KEY]
    assert not any(d.key=='bg40_80_download' for d in app.get('download_button'))


def test_currency_validation_failure_keeps_rebuild_button_available():
    app=report_app({ui.ARTIFACT_KEY:{'signature':'old'}})
    with patch.object(ui,'source_signature',side_effect=RuntimeError('Corrupt source payload')):
        app.run(timeout=120)
    assert not app.exception
    assert any(b.key=='bg40_80_build' for b in app.button)
    assert not any(d.key=='bg40_80_download' for d in app.get('download_button'))
    assert any('complete report could not be created' in e.value for e in app.error)


def test_explicit_export_builds_once_and_does_not_force_an_extra_rerun():
    app=report_app();app.run(timeout=120)
    report=object()
    artifact={'signature':'prepared','docx':b'ui-test','evidence':b'ui-test','figures':[],
        'status':'REVIEW','chapters':10}
    with patch.object(ui,'build_workflow_report',return_value=report) as build, \
         patch.object(ui,'build_complete_artifact',return_value=artifact) as export, \
         patch.object(ui,'source_signature',side_effect=AssertionError('Redundant artifact scan')):
        next(b for b in app.button if b.key=='bg40_80_build').click().run(timeout=120)
    assert not app.exception,[e.message for e in app.exception]
    assert build.call_count==export.call_count==1
    assert export.call_args.args[2] is report
    assert any(d.key=='bg40_80_download' for d in app.get('download_button'))


def test_closed_chart_panel_does_not_render_charts_when_equation_traces_are_open():
    app=report_app({'bg40_83_traces_open':True})
    with patch('concrete_pmm_pro.ui.igird_uls_report.current_check_packages',side_effect=AssertionError('Closed chart panel read source')):
        app.run(timeout=120)
    assert not app.exception,[e.message for e in app.exception]
    assert not app.get('plotly_chart')


@pytest.mark.parametrize('payload,default',[
    ({'Thai':'รายการคำนวณ','nested':[0,1.23456789,True,None,{'z':'last','a':'first'}]},None),
    ({'source':[{'cell':'αβγ'} for _ in range(3000)],'tuple':(1,2)},None),
    ({'legacy':Path('source.xlsx'),'unicode':'橋'},str)])
def test_incremental_signature_matches_original_json_digest_exactly(payload,default):
    expected=sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':'),default=default).encode()).hexdigest()
    assert _json_signature(payload,default=default)==expected
