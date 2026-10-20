"""Source invariance, four-mat envelopes, spacing, provenance and truthful plots."""
from copy import deepcopy
from io import BytesIO
import json
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis import slab_top65 as top, slab_shear64 as code, slab_aashto63 as sections
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.io.slab_shell_import import BANK_KEY, PENDING_KEY, parse_files
from concrete_pmm_pro.io.project_io import project_from_session_state, project_to_json, project_from_json, apply_project_to_session_state
from concrete_pmm_pro.visualization import slab_top65 as plots
from concrete_pmm_pro.reporting.slab_top65 import summary_rows
from test_slab_shell56 import model_state, steel
from test_slab_shell55 import upload, fixtures


def test_load_metadata_never_rescales_actions_resistances_or_masks_and_reuses_mechanics():
    state = model_state()
    first = top.calculate(state)
    top.save_load_basis(state, {'method': 'equivalent_udl', 'ballast_mm': 600.,
        'track_width_m': 2.15, 'nominal_pressure_kpa': 150.})
    with patch.object(code, 'calculate', side_effect=AssertionError('mechanics reran')):
        second = top.calculate(state, reuse=first)
    assert second['accepted_result_reused']
    assert second['fingerprint'] != first['fingerprint']
    assert second['actions_multiplier'] == 1. and not second['ballast_in_resistance']
    pd.testing.assert_frame_equal(first['rows'], second['rows'])
    pd.testing.assert_frame_equal(first['summary'], second['summary'])
    assert second['load_basis_status'] == 'SOURCE MATCHED'


def test_new_import_breaks_provenance_binding_and_current_result():
    state = model_state()
    top.save_load_basis(state, {'method': 'equivalent_udl'})
    state[top.RESULT_KEY] = top.calculate(state)
    assert top.current(state) is state[top.RESULT_KEY]
    package = state[BANK_KEY]
    package.signature = ('new-export',)
    state[PENDING_KEY] = package.signature
    assert top.current(state) is None
    assert top.basis_status(state) == 'SOURCE CHANGED'


@pytest.mark.parametrize('key,value', [('ballast_mm', -1), ('ballast_mm', np.nan),
    ('track_width_m', 0), ('nominal_pressure_kpa', np.inf), ('method', 'invented')])
def test_invalid_load_inputs_do_not_partially_write_metadata(key, value):
    state = model_state()
    before = deepcopy(state.get('project_metadata'))
    with pytest.raises(ValueError):
        top.save_load_basis(state, {key: value})
    assert state.get('project_metadata') == before


def test_spacing_matches_cast_in_place_hand_calculation_and_unknown_is_not_pass():
    s = steel()
    s.spacing[:] = 60.  # clear = 60 - 16 = 44 mm
    checks = top.clear_spacing(s, {'shear_max_aggregate_mm': 30., 'shear_aggregate_confirmed': True})
    np.testing.assert_allclose(checks['Clear spacing D/C'], 45/44)
    assert checks['Clear spacing status'].eq('FAIL').all()
    checks = top.clear_spacing(s, {'shear_max_aggregate_mm': 20., 'shear_aggregate_confirmed': True})
    np.testing.assert_allclose(checks['Clear spacing D/C'], 38.1/44)
    assert checks['Clear spacing status'].eq('PASS').all()
    unknown = top.clear_spacing(s, {})
    assert unknown['Clear spacing status'].eq('REVIEW').all()
    assert unknown['Clear spacing D/C'].isna().all()
    s.spacing[:] = 50.  # the absolute code minimum already fails
    assert top.clear_spacing(s, {})['Clear spacing status'].eq('FAIL').all()


def test_aggregate_change_invalidates_details_but_not_the_accepted_mechanical_base():
    state = model_state()
    saved = top.calculate(state)
    state[top.RESULT_KEY] = saved
    state['section_parameters']['shear_max_aggregate_mm'] = 20.
    state['section_parameters']['shear_aggregate_confirmed'] = True
    assert top.current(state) is None
    with patch.object(code, 'calculate', side_effect=AssertionError('mechanics reran')):
        changed = top.calculate(state, reuse=saved)
    assert changed['clear_spacing']['Clear spacing status'].eq('PASS').all()


def test_four_mats_keep_signed_actual_governors_and_axial_tension_in_both():
    h = [350.]*3
    actions = pd.DataFrame({'Thickness (mm)': h, 'Nx': [0., 0., 400.], 'Ny': [0., 0., 0.],
        'Nxy': [0.]*3, 'Mx': [-20., 40., 0.], 'My': [10., -30., 0.],
        'Mxy': [0.]*3, 'Vx': [0.]*3, 'Vy': [0.]*3})
    checked = sections.section_checks(actions, steel())
    rows = pd.concat((actions, checked), axis=1)
    rows['X (m)'] = [1., 2., 3.]
    rows['Y (m)'] = 1.
    rows['OutputCase'] = ['negative', 'positive', 'axial']
    rows['StepType'] = ''
    rows['Joint'] = ['1', '2', '3']
    rows['AreaElem'] = 'E'
    rows[INCLUDED] = True
    result = {'rows': rows, 'steel': steel(), 'support_faces': pd.DataFrame(), 'incomplete': False}
    mats = top.bending_envelopes(result, top.clear_spacing(steel(), {}))
    assert list(mats.Mat) == list(top.inputs.GROUPS)
    for i, direction in ((0, 'Longitudinal'), (1, 'Longitudinal'), (2, 'Transverse'), (3, 'Transverse')):
        mat = mats.iloc[i]
        row = rows.loc[rows.OutputCase.eq(mat['N–M case'])].iloc[0]
        assert mat['Section N–M D/C'] == row[direction+' N–M D/C']
        if i in (0, 1):
            assert mat['N–M case'] == 'axial'
    assert not mats['Known checks'].eq('PASS').any()  # aggregate branch unresolved


def test_static_blank_step_and_new_case_names_work_with_same_native_tables():
    state = model_state()
    package = deepcopy(state[BANK_KEY])
    forces = package.tables['forces']
    forces = forces.loc[forces.StepType.eq('Max')].copy()
    forces['StepType'] = ''
    forces['OutputCase'] = 'UDL_ULS'
    # Retain one original case per native corner; no duplicate records.
    forces = forces.drop_duplicates(['Area', 'AreaElem', 'Joint'])
    package.tables['forces'] = forces
    package.signature = ('static-udl-fixture',)
    state[BANK_KEY] = package
    state[PENDING_KEY] = package.signature
    result = top.calculate(state)
    assert set(result['rows'].OutputCase) == {'UDL_ULS'}
    assert set(result['rows'].StepType) == {''}
    assert not result['incomplete']
    np.testing.assert_array_equal(result['rows'][list(top.inputs.current_package(state).tables['forces'].columns.intersection(['F11','F22','F12','M11','M22','M12','V13','V23']))],
        forces[list(forces.columns.intersection(['F11','F22','F12','M11','M22','M12','V13','V23']))])


def test_same_four_export_sets_are_detected_by_schema_for_static_udl():
    data = fixtures()
    data['forces'] = [{**data['forces'][0], 'OutputCase': 'UDL_ULS', 'CaseType': 'Combination', 'StepType': None}]
    book = parse_files([upload(data, name='static_equivalent_train.xlsx')])
    assert book.ready and book.summary['cases'] == ['UDL_ULS']
    assert book.tables['forces'].StepType.eq('').all()


def test_profile_keeps_native_gaps_full_extent_and_known_numeric_maximum():
    result = top.calculate(model_state())
    adapted = top.map_adapter(result, 'Direct N–M · transverse')
    frame = adapted['rows'].copy()
    frame.loc[frame['X (m)'].eq(1), INCLUDED] = False
    adapted = {**adapted, 'rows': frame}
    before = frame.copy(deep=True)
    profile, length = plots.station_envelope(adapted)
    assert length == pytest.approx(2.)
    assert profile.loc[profile['Station (m)'].eq(1), 'D/C'].isna().all()
    assert profile['D/C'].max() == frame.loc[frame[INCLUDED], 'Field D/C'].max()
    fig = plots.profile(adapted, 'Direct N–M · transverse')
    assert list(fig.layout.xaxis.range) == [0., 2.]
    assert fig.data[0].connectgaps is False
    assert any(np.isnan(v) for v in fig.data[0].y)
    pd.testing.assert_frame_equal(frame, before)


def test_compact_report_is_read_only_and_project_json_contains_only_input_provenance():
    state = model_state()
    top.save_load_basis(state, {'method': 'equivalent_udl'})
    result = top.calculate(state)
    state[top.RESULT_KEY] = result
    with patch.object(top, 'calculate', side_effect=AssertionError('solver ran')), \
         patch.object(code, 'calculate', side_effect=AssertionError('solver ran')):
        payload = top.report_zip(result)
    with ZipFile(BytesIO(payload)) as z:
        assert z.testzip() is None
        provenance = json.loads(z.read('Provenance.json'))
        assert provenance['source_actions_multiplier'] == 1.
        assert not provenance['full_deck_acceptance'] and not provenance['ballast_in_resistance']
    encoded = project_to_json(project_from_session_state(state))
    assert top.RESULT_KEY not in encoded and 'shear_result' not in encoded
    restored = {top.RESULT_KEY: {'old': True}}
    apply_project_to_session_state(project_from_json(encoded), restored)
    assert top.load_basis(restored) == top.load_basis(state)
    assert top.RESULT_KEY not in restored and BANK_KEY not in restored


def test_summary_and_report_rows_are_read_only_include_scope_and_never_reuse_stale_pass():
    state = model_state()
    assert summary_rows({}) == []
    assert summary_rows(state)[0]['Status'] == 'NOT CALCULATED'
    state[top.RESULT_KEY] = top.calculate(state)
    before = deepcopy(state[top.RESULT_KEY]['summary'])
    with patch.object(top, 'calculate', side_effect=AssertionError('solver ran')):
        rows = summary_rows(state)
        assert len(rows) >= len(top.VIEWS)
        assert any(r['Check'] == 'Deck scope / remaining checks' and r['Status'] == 'REVIEW' for r in rows)
        state['section_parameters']['deck_long_rebar_top_spacing_mm'] = 200.
        assert summary_rows(state)[0]['Status'] == 'STALE'
    pd.testing.assert_frame_equal(before, state[top.RESULT_KEY]['summary'])
