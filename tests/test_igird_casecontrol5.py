"""Case filtering and governing ratios must retain one actual row's identity."""
import copy
import math

import pandas as pd
import pytest

from concrete_pmm_pro.ui.igird_case_review import (
    controlling_result, case_ranking, component_controls, filter_case, review_counts,
)
from concrete_pmm_pro.ui.igird_member_results import member_inputs, calculate_member
from test_igird_arrowdisplay4 import mixed_member_model
from test_igird_uls6_torsion_general_procedure import _route


def review_model():
    state = mixed_member_model()
    bank = state['igird_uls_member_bank']
    second = bank['Case Name'].str.endswith('ULS2')
    bank.loc[second, 'Mux'] *= .6
    bank.loc[second, 'Vuy'] *= 1.8
    bank.loc[second, 'Tu'] *= .7
    return state


def test_smaller_signed_moment_can_control_flexure_when_resistance_is_smaller():
    frame = pd.DataFrame([
        {'Case': 'Large positive Mu', 'Governing x': '10.000 m', 'Demand kN-m': 900., 'Utilization value': .5, 'Status': 'PASS'},
        {'Case': 'Small negative Mu', 'Governing x': '5.000 m', 'Demand kN-m': -200., 'Utilization value': .95, 'Status': 'REVIEW'},
    ])
    control = controlling_result(frame, 'Flexure')
    assert control['row']['Case'] == 'Small negative Mu'
    assert control['row']['Demand kN-m'] == -200.
    assert control['ratio'] == .95
    assert control['review_rows'] == 1


def test_shear_detailing_and_minimum_reinforcement_can_control_another_case():
    frame = pd.DataFrame([
        {'Case': 'High Vu', 'Governing x': '10 m', 'Station type': 'LOAD STATION', 'Status': 'PASS',
         'Strength D/C value': .8, 'Detailing D/C value': .3, 'Av/s min D/C': .3},
        {'Case': 'Low Vu', 'Governing x': '5 m', 'Station type': 'LOAD STATION', 'Status': 'FAIL',
         'Strength D/C value': .2, 'Detailing D/C value': 1.4, 'Av/s min D/C': 1.4},
        {'Case': 'Synthetic', 'Governing x': '0 m', 'Station type': 'DIAGRAM BOUNDARY', 'Status': 'DIAGRAM BOUNDARY',
         'Strength D/C value': 99., 'Detailing D/C value': 99.},
    ])
    control = controlling_result(frame, 'Shear')
    assert control['row']['Case'] == 'Low Vu'
    assert control['ratio'] == 1.4
    assert 'Synthetic' not in set(case_ranking(frame, 'Shear')['Controlling load case'])
    components = component_controls(frame, 'Shear')
    assert components.loc[components.Component.eq('Shear strength'), 'Controlling load case'].iloc[0] == 'High Vu'


def test_combined_partial_row_with_missing_overall_value_can_numerically_control():
    frame = pd.DataFrame([
        {'Case': 'Complete', 'Status': 'PASS', 'Governing x': '6 m', 'Overall D/C value': .8,
         'Stress D/C value': .5, 'Transverse D/C value': .8, 'Longitudinal D/C value': .7},
        {'Case': 'Partial', 'Status': 'FAIL', 'Governing x': '2 m', 'Overall D/C value': float('nan'),
         'Transverse D/C value': 1.5, 'Calculation status': 'PARTIAL', 'Longitudinal status': 'DATA REQUIRED'},
    ])
    control = controlling_result(frame, 'Shear + Torsion')
    assert control['row']['Case'] == 'Partial'
    assert control['component'] == 'Combined transverse'
    assert control['ratio'] == 1.5
    assert control['failed_rows'] == 1 and control['review_rows'] == 1


@pytest.mark.parametrize('ratio', [.9, float('inf')])
def test_equal_controlling_cases_are_all_reported_with_stable_selection(ratio):
    frame = pd.DataFrame([{'Case': case, 'Status': 'REVIEW', 'Governing x': '5 m', 'Utilization value': ratio}
                          for case in ['First', 'Second']])
    control = controlling_result(frame, 'Flexure')
    assert control['row']['Case'] == 'First'
    assert control['tied_cases'] == ['First', 'Second']
    assert control['ratio'] == ratio


def test_missing_capacity_and_envelope_review_elsewhere_survives_passing_case():
    frame = pd.DataFrame([
        {'Case': 'Numerical control', 'Status': 'PASS', 'Utilization value': .9},
        {'Case': 'Missing', 'Status': 'REVIEW', 'Utilization value': float('nan'), 'Source coupling': 'ENVELOPE — REVIEW'},
        {'Case': 'Failed source', 'Status': 'FAIL', 'Utilization value': .4},
    ])
    control = controlling_result(frame, 'Flexure')
    assert control['row']['Case'] == 'Numerical control'
    assert control['review_rows'] == 1 and control['failed_rows'] == 1
    assert filter_case(frame, 'Numerical control')['Status'].eq('PASS').all()


def test_no_numeric_strength_has_an_explicit_source_review_fallback():
    frame = pd.DataFrame([{'Case': 'A', 'Status': 'NO DEMAND'}, {'Case': 'B', 'Status': 'LAYOUT REQUIRED'}])
    control = controlling_result(frame, 'Torsion')
    assert control['basis'] == 'NO NUMERIC D/C' and math.isnan(control['ratio'])
    assert control['row']['Case'] == 'B'


def test_torsion_threshold_is_labelled_and_never_mixed_with_strength_dc():
    frame = pd.DataFrame([
        {'Case': 'A', 'Status': 'BELOW THRESHOLD', 'Abs demand kN-m': 10., 'Threshold kN-m': 20.},
        {'Case': 'B', 'Status': 'LAYOUT REQUIRED', 'Abs demand kN-m': 60., 'Threshold kN-m': 30.},
    ])
    control = controlling_result(frame, 'Torsion')
    assert control['row']['Case'] == 'B' and control['ratio'] == 2.
    assert control['basis'] == 'INVESTIGATION ONLY'
    frame.loc[0, 'D/C value'] = .6
    control = controlling_result(frame, 'Torsion')
    assert control['row']['Case'] == 'A' and control['basis'] == 'D/C'
    assert control['review_rows'] == 1
    ranking = case_ranking(frame, 'Torsion')
    assert ranking['Controlling load case'].tolist() == ['A', 'B']
    assert ranking['Basis'].tolist() == ['D/C', 'INVESTIGATION ONLY']


def test_torsion_longitudinal_steel_can_control_if_its_ratio_is_available():
    frame = pd.DataFrame([
        {'Case': 'Transverse', 'Status': 'PASS', 'D/C value': .9, 'Al utilization': .5},
        {'Case': 'Longitudinal', 'Status': 'FAIL', 'D/C value': .4, 'Al utilization': 1.2},
    ])
    control = controlling_result(frame, 'Torsion')
    assert control['row']['Case'] == 'Longitudinal'
    assert control['component'] == 'Torsion longitudinal steel' and control['ratio'] == 1.2


def test_not_required_threshold_labels_do_not_create_false_review_counts():
    rows = pd.DataFrame({'Status': ['BELOW THRESHOLD', 'PASS'],
                         'Threshold status': ['BELOW THRESHOLD', 'DESIGN REQUIRED'],
                         'Coverage status': ['NOT REQUIRED', 'PASS']})
    assert review_counts(rows) == (0, 0)


def test_case_filter_preserves_repeated_station_vectors_and_original_index():
    frame = pd.DataFrame({'Case': ['A', 'B', 'A'], 'x': [5., 5., 5.],
                          'Mux': [1., 2., 3.], 'Tu': [10., 20., 30.]}, index=[7, 7, 8])
    original = frame.copy()
    selected = filter_case(frame, 'A')
    assert selected.index.tolist() == [7, 8]
    assert selected.Mux.tolist() == [1., 3.] and selected.Tu.tolist() == [10., 30.]
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize('check,column', [('Shear', 'Av/s min D/C'),
                                        ('Torsion', 'Al utilization'),
                                        ('Shear + Torsion', 'Overall D/C value')])
def test_overview_uses_same_controlling_components_and_retains_infinite_ratio(check, column):
    from concrete_pmm_pro.ui.igird_vt_workspace import make_overview_figure
    frame = pd.DataFrame([{'Case': 'A', 'Status': 'FAIL', 'Governing x': '5.000 m',
                           'D/C value': .4, 'Strength D/C value': .4, column: float('inf')}])
    source = pd.DataFrame({'Case Name': ['A'], 'Station x (m)': [5.], 'Tu': [10.], 'Vuy': [20.]})
    before = copy.deepcopy(frame)
    control = controlling_result(frame, check)
    fig = make_overview_figure(source, frame, check_name=check, code_label='QA', span_m=20.)
    trace = next(t for t in fig.data if t.name == 'Max D/C')
    assert trace.customdata[0][0] == control['row']['Case']
    assert trace.customdata[0][1] == control['component']
    assert trace.customdata[0][2] == '∞' and math.isfinite(trace.y[0])
    assert 'Imported actions' not in fig.layout.title.text
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize('check,key', [('Flexure','flexure_preview_df'),('Shear','shear_check_df'),
                                     ('Torsion','torsion_check_df'),('Shear + Torsion','combined_vt_df')])
def test_real_case_ranking_and_filtering_preserve_all_stored_data(check, key):
    state = review_model(); original = copy.deepcopy(state)
    for member, source in member_inputs(state).items():
        result = calculate_member(state, source, check_name=check, route=_route())
        frame = result[key]; before = copy.deepcopy(frame)
        rank = case_ranking(frame, check)
        assert set(rank['Controlling load case']) == set(source['Case Name'])
        for case in source['Case Name'].unique():
            pd.testing.assert_frame_equal(filter_case(frame, case), frame.loc[frame['Case'].eq(case)])
        controlling_result(frame, check); component_controls(frame, check)
        pd.testing.assert_frame_equal(frame, before)
    pd.testing.assert_frame_equal(state['igird_uls_member_bank'], original['igird_uls_member_bank'])
