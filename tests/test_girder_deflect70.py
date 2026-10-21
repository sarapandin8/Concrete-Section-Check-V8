"""Native CSI scalar envelopes, scoped limits, JSON and read-only handoff."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.io import girder_deflect70 as importer
from concrete_pmm_pro.io.project_io import project_from_session_state, project_to_json, project_from_json, apply_project_to_session_state
from concrete_pmm_pro.serviceability import girder_deflect70 as engine
from concrete_pmm_pro.visualization.girder_deflect70 import figure
from test_girder_deflect69 import source_curves

FIXTURE = Path(__file__).parent / 'fixtures/sls_deflect70/SLS_deflection_source.xlsx'
SOURCE_SHA = '4beac1fa04c5ad73f43a24c654826ac34362dfdac28be7e62fc1830969a7d536'


def bank():
    payload = FIXTURE.read_bytes()
    assert sha256(payload).hexdigest() == SOURCE_SHA
    return importer.parse_workbook(payload, 'SLS deflection.xlsx')


def state(**config):
    return {importer.BANK_KEY: bank(), engine.SETTINGS_KEY: {'profile': 'rail_project', **config}}


def test_actual_workbook_retains_all_native_scalar_records_and_source_identity():
    source = bank()
    assert source['file_sha256'] == SOURCE_SHA
    assert [s['girder'] for s in source['girders']] == ['Left Exterior Girder', 'Interior Girder 2']
    assert all(len(s['rows']) == 48 for s in source['girders'])
    assert all(s['distance_unit'] == s['vertical_unit'] == 'm' for s in source['girders'])
    assert not source['load_definition_in_export'] and source['case_name'] is None
    assert all(set(row) == {'source_row', 'Girder Distance', 'ItemType', 'WebTop Vert'}
        for s in source['girders'] for row in s['rows'])
    assert source['girders'][0]['rows'][0]['source_row'] == 3


def test_service_uses_exact_webtop_values_without_generated_camber_or_load_additions():
    s = state()
    native = deepcopy(s[importer.BANK_KEY])
    generated = source_curves(up=10000, existing_live=10000.)
    unchanged = generated.copy(deep=True)
    result = engine.calculate(s, generated, 20.)
    rows = result['summary'].loc[lambda f: f.Check.eq('Imported SLS envelope |WebTop Vert|')]
    assert rows['Demand (mm)'].tolist() == pytest.approx([9.227, 9.160])
    assert rows['x (m)'].tolist() == [10.45714, 10.45714]
    assert rows.Branch.tolist() == ['Min', 'Min']
    assert rows.Utilization.tolist() == pytest.approx([.692025, .687])
    assert rows.Status.tolist() == ['Preview PASS'] * 2
    assert result['status'] == 'REVIEW REQUIRED' and not result['full_deflection_acceptance']
    for sheet in native['girders']:
        actual = result['service_audit'].loc[lambda f: f.Girder.eq(sheet['girder'])]
        np.testing.assert_array_equal(actual['Station x (m)'], [r['Girder Distance'] for r in sheet['rows']])
        np.testing.assert_array_equal(actual['Deflection (mm)'], [r['WebTop Vert'] * 1000 for r in sheet['rows']])
    pd.testing.assert_frame_equal(unchanged, generated)
    assert s[importer.BANK_KEY] == native
    assert result['curves'].loc[lambda f: f.Stage.eq('Service stage')]['Deflection (mm)'].max() == 0.


def test_calculated_precast_stages_are_preserved_and_generated_service_is_ignored_even_if_invalid():
    generated = source_curves()
    generated.loc[generated.Stage.eq('Service stage'), 'Deflection (mm)'] = np.nan
    result = engine.calculate(state(), generated, 20.)
    for stage in engine.STAGES[:2]:
        np.testing.assert_array_equal(result['curves'].loc[lambda f: f.Stage.eq(stage), 'Deflection (mm)'],
            generated.loc[generated.Stage.eq(stage), 'Deflection (mm)'])


@pytest.mark.parametrize('unit,factor',[('mm',1000.), ('cm',100.), ('ft',1/.3048), ('in',1/.0254)])
def test_length_units_convert_once_and_preserve_source_values(unit, factor):
    s = state()
    for sheet in s[importer.BANK_KEY]['girders']:
        sheet['distance_unit'] = sheet['vertical_unit'] = unit
        for row in sheet['rows']:
            row['Girder Distance'] *= factor
            row['WebTop Vert'] *= factor
    result = engine.calculate(s, source_curves(), 20.)
    values = result['summary'].loc[lambda f: f.Check.eq('Imported SLS envelope |WebTop Vert|'), 'Demand (mm)']
    np.testing.assert_allclose(values, [9.227, 9.160])


@pytest.mark.parametrize('defect,match',[
    ('single', 'only Envelope'), ('missing_min', 'both Envelope'), ('duplicate', 'duplicate station'),
    ('wrong_order', 'Max is below Min'), ('unit', 'length unit'), ('missing_value', 'finite numeric'),
    ('nan', 'finite numeric'), ('negative_x', 'cannot be negative'), ('bridge', 'individual girder')])
def test_invalid_envelope_input_is_rejected_atomically(defect, match):
    source = bank()
    sheet = source['girders'][0]
    if defect == 'single': sheet['rows'][0]['ItemType'] = 'Value'
    elif defect == 'missing_min': sheet['rows'].pop(1)
    elif defect == 'duplicate': sheet['rows'].append(deepcopy(sheet['rows'][0]))
    elif defect == 'wrong_order': sheet['rows'][4]['WebTop Vert'] = -1.
    elif defect == 'unit': sheet['vertical_unit'] = ''
    elif defect == 'missing_value': sheet['rows'][0]['WebTop Vert'] = None
    elif defect == 'nan': sheet['rows'][0]['WebTop Vert'] = float('nan')
    elif defect == 'negative_x': sheet['rows'][0]['Girder Distance'] = -1
    elif defect == 'bridge': sheet['girder'] = 'Entire Bridge Section'
    before = deepcopy(source)
    with pytest.raises(ValueError, match=match): importer.validate_bank(source)
    assert repr(source) == repr(before)


def test_invalid_file_or_single_case_table_cannot_replace_existing_bank():
    before = bank()
    with pytest.raises(ValueError, match='Cannot read'): importer.parse_workbook(b'not an xlsx', 'wrong.xlsx')
    with pytest.raises(ValueError, match='.xlsx'): importer.parse_workbook(FIXTURE.read_bytes(), 'wrong.csv')
    assert before == bank()
    class Sheet:
        title = 'Left Exterior Girder'
        def iter_rows(self, values_only=True):
            return iter([('Girder Distance','ItemType','WebTop Vert'),('m',None,'m'),(0,'Value',0),(20,'Value',0)])
    class Workbook:
        def __iter__(self): return iter([Sheet()])
        def close(self): pass
    with patch.object(importer, 'load_workbook', return_value=Workbook()):
        with pytest.raises(ValueError, match='only Envelope'): importer.parse_workbook(b'qa', 'case.xlsx')


def test_missing_invalid_or_wrong_span_service_never_falls_back_to_generated_response():
    missing = engine.calculate({}, source_curves(), 20.)
    assert not missing['service_available'] and missing['curves'].Stage.nunique() == 2
    s = state(); s[importer.ERROR_KEY] = 'bad replacement'
    blocked = engine.calculate(s, source_curves(), 20.)
    assert not blocked['service_available'] and not blocked['girders']
    assert blocked['summary'].Status.eq('Preview PASS').sum() == 0
    with pytest.raises(ValueError, match='imported Girder Distance'):
        engine.calculate(state(), source_curves().assign(**{'Station x (m)':source_curves()['Station x (m)']/2}), 10.)


def test_project_failure_and_highway_reference_limit_have_distinct_meaning():
    failed = engine.calculate(state(profile='custom', custom_limit_mm=8.), source_curves(), 20.)
    assert failed['summary'].Status.eq('Preview FAIL').sum() == 2 and failed['status'] == 'Preview FAIL'
    highway = engine.calculate(state(profile='aashto_vehicle'), source_curves(), 20.)
    service = highway['summary'].loc[lambda f: f.Check.eq('Imported SLS envelope |WebTop Vert|')]
    assert service['Limit (mm)'].tolist() == [25.,25.]
    assert service.Status.eq('REVIEW').all() and not highway['limit_eligible']


def test_named_figures_keep_all_exported_stations_and_both_sign_limits():
    result = engine.calculate(state(), source_curves(), 20.)
    for girder in result['girders']:
        fig = figure(result, 'Service stage', girder)
        assert girder in fig.layout.title.text and 'WebTop Vert' in fig.layout.title.text
        assert 'Imported SLS envelope' in fig.layout.title.text and list(fig.layout.xaxis.range) == [0,20]
        traces = [t for t in fig.data if str(t.name).startswith('Envelope ' ) and t.mode == 'lines+markers']
        assert [len(t.x) for t in traces] == [24,24]
        assert all(t.connectgaps is False for t in traces)
        limits = [float(t.y[0]) for t in fig.data if 'limit' in str(t.name).casefold()]
        np.testing.assert_allclose(limits, [-20000/1500,20000/1500])
    for stage in engine.STAGES[:2]:
        fig = figure(result, stage)
        assert 'single I-girder' in fig.layout.title.text and 'calculated' in fig.layout.title.text


def test_source_and_settings_round_trip_as_inputs_while_results_and_widgets_clear():
    s = state(construction_limit_mm=25.)
    s[engine.RESULT_KEY] = engine.calculate(s, source_curves(),20.)
    encoded = project_to_json(project_from_session_state(s))
    assert engine.RESULT_KEY not in encoded and 'service_audit' not in encoded
    restored = {engine.RESULT_KEY:{'old':True},'girder_deflect70_ui_girder':'wrong','girder_deflect70_upload_was_present':True}
    apply_project_to_session_state(project_from_json(encoded),restored)
    assert restored[importer.BANK_KEY] == s[importer.BANK_KEY]
    assert engine.settings(restored) == engine.settings(s)
    assert engine.RESULT_KEY not in restored and 'girder_deflect70_ui_girder' not in restored
    assert not restored.get('girder_deflect70_upload_was_present')


def test_summary_report_read_stored_results_and_upload_or_model_changes_mark_them_stale():
    import app
    from concrete_pmm_pro.core.analysis import AnalysisModeSettings
    s = state()
    s['analysis_mode_settings'] = AnalysisModeSettings(member_type='beam_girder',analysis_workflow='bridge_beam_girder')
    app._results_governing_rows(s)
    s[engine.RESULT_KEY] = engine.calculate(s,source_curves(),20.)
    with patch.object(engine,'calculate',side_effect=AssertionError('hidden rerun')):
        rows = app._results_governing_rows(s)
        assert len([r for r in rows if r['Module']=='SLS Deflection']) == 5
        assert app._results_sls_available(s) and not app._results_sls_complete_for_report(s)
        assert any('Left Exterior Girder' in r['Check'] for r in rows)
        payload = engine.report_zip(s[engine.RESULT_KEY])
    with ZipFile(BytesIO(payload)) as z:
        assert z.testzip() is None
        assert json.loads(z.read('Imported_Input.json'))['file_sha256'] == SOURCE_SHA
        assert not json.loads(z.read('Scope.json'))['full_deflection_acceptance']
    s[importer.BANK_KEY]['girders'][0]['rows'][2]['WebTop Vert'] *= 1.01
    assert engine.current(s) is None and engine.summary_rows(s)[0]['Status'] == 'STALE'


def test_removed_legacy_live_udl_does_not_affect_imported_service_or_its_fingerprint():
    s = state()
    s[engine.RESULT_KEY] = engine.calculate(s, source_curves(),20.)
    s['girder_deflect69_settings'] = {'live_udl_kN_m':999999}
    assert engine.current(s) is not None
