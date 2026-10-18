"""Reported CSI torque survives analysis, cache invalidation and audit display."""
from copy import deepcopy
from unittest.mock import patch

import pandas as pd
import pytest

from concrete_pmm_pro.io import csi_force_reference as ref
from concrete_pmm_pro.ui import analysis_page as ap, csi_reference_analysis as adapter
from test_igird_csiref26 import CFG, I, RAW, bound_row, seed, source_row


def state():
    result = seed()
    result['section_geometry'] = I
    result['section_parameters'] = {**result['section_parameters'], 'Be_mm': 1200.,
        'Tslab_mm': 350., 'deck_fc_MPa': 35., 'composite_enabled': True}
    return result


@pytest.mark.parametrize('torque', [-40., 0., 40.])
@pytest.mark.parametrize('check', ['Torsion', 'Shear + Torsion'])
def test_lateral_shear_and_both_offsets_cannot_change_reported_torque(torque, check):
    actions = {**RAW, 'T': torque, 'V3': 1000.}
    row = ref.bind_reference(pd.DataFrame([source_row(actions)]),
        {**CFG, 'local3_offset_from_web_m': .2}).iloc[0].to_dict()
    original = deepcopy(row)
    converted = adapter.convert_for_check(state(), row, check_name=check)
    assert converted['Tu'] == torque
    assert converted['Vuy'] == actions['V2'] and converted['Vux'] == actions['V3']
    assert converted['Nu'] == actions['P']
    # Bending still requires the actual axial-force eccentricity. This policy
    # must not become an accidental bypass for flexure/SLS moment transport.
    assert converted['Muy'] == pytest.approx(10.)
    assert converted['Mux'] != actions['M3']
    trace = ref.trace_columns(converted)
    assert trace['T reference y mm'] == pytest.approx(484.4)
    assert trace['T reference local3 mm'] == pytest.approx(200.)
    assert trace['T C-O local2 m'] == trace['T C-O local3 m'] == 0.
    assert trace['T shift applied'] is False
    assert row == original


def test_repeated_conversion_and_later_bending_retarget_keep_the_original_vector():
    row = bound_row()
    model = state()
    first = adapter.convert_for_check(model, row, check_name='Torsion')
    again = adapter.convert_for_check(model, first, check_name='Shear + Torsion')
    assert first['Tu'] == again['Tu'] == RAW['T']
    assert ref.actions(again) == RAW
    bending = ref.translate_row(again, origin={'deck_top_y_mm':1100., 'target_y_mm':393., 'target_local3_mm':0.})
    assert bending['Tu'] == pytest.approx(49.14)
    assert bending['Mux'] == pytest.approx(581.72)


def test_independent_envelope_does_not_become_concurrent_when_t_is_retained():
    row = bound_row(step='Max', mode='unverified', kind='ENVELOPE')
    converted = adapter.convert_for_check(state(), row, check_name='Shear + Torsion')
    assert converted['Tu'] == RAW['T']
    assert converted[ref.RUNTIME_KEY]['mode'] == 'BLOCKED'
    result = ref.qualify_result({'Status':'PASS'}, converted, check_name='Shear + Torsion')
    assert result['Status'] == 'REVIEW'
    assert 'Paired Max/Min' in result['Reference review']


def test_source_torque_policy_cannot_certify_resistance_at_the_reporting_point():
    converted = adapter.convert_for_check(state(), bound_row(), check_name='Torsion')
    result = ref.qualify_result({'Status':'PASS','Overall status':'PASS'}, converted, check_name='Torsion')
    assert result['Status'] == result['Overall status'] == 'REVIEW'
    assert 'screening results' in result['Reference review']
    assert result['T used kN-m'] == RAW['T']


@pytest.mark.parametrize('check', ['Torsion', 'Shear + Torsion'])
def test_legacy_torque_policy_results_are_stale(check):
    model = state()
    rows = pd.DataFrame([bound_row()])
    route = ap.beam_girder_uls_strength_route(is_bridge=True,is_building=False,
        project_design_code='AASHTO LRFD',code_edition='2020')
    current = ap._beam_uls_check_input_hash(model,rows,strength_route=route,check_name=check)
    with patch.object(ref,'SOURCE_TORSION_POLICY','legacy-centroid-torque'):
        legacy = ap._beam_uls_check_input_hash(model,rows,strength_route=route,check_name=check)
    assert legacy != current


def test_read_only_audit_shows_original_torque_instead_of_a_shift_equation():
    row = adapter.convert_for_check(state(),bound_row(),check_name='Shear + Torsion')
    columns = ref.trace_columns(row)
    with patch('streamlit.markdown'), patch('streamlit.caption') as caption, \
         patch('streamlit.warning'), patch('streamlit.dataframe') as table, \
         patch.object(ref,'geometry_origin',side_effect=AssertionError('audit must not recalculate')):
        adapter.render_trace(columns)
    shown = table.call_args.args[0]
    torque = shown.loc[shown['Action'].eq('T')].iloc[0]
    assert torque['Result (kN-m)'] == RAW['T']
    assert 'unchanged' in torque['Equation']
    assert any('ไม่ย้ายไป centroid' in str(call) for call in caption.call_args_list)
