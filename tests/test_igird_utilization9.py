"""The strength curve must not fill or replace omitted original design checks."""
from copy import deepcopy
import math
from unittest.mock import patch

import pandas as pd
import pytest

from concrete_pmm_pro.ui import analysis_page as ap, igird_uls_report as report, igird_member_results as mr
from concrete_pmm_pro.ui.igird_case_review import controlling_result
from concrete_pmm_pro.ui.igird_torsion_utilization import (
    make_torsion_utilization_figure, utilization_audit,
)
from test_igird_reportcharts8 import calculated_state, no_report_solvers
from test_igird_uls7_concurrent_vt import ready_state
from test_igird_uls6_torsion_general_procedure import _demand, _route
from test_igird_chart3_full_span import native


def pairs():
    source = pd.DataFrame({'Case Name': ['A']*3, 'Station x (m)': [4., 5., 6.],
                          'Tu': [100., 1.581234567890123, -140.], 'Vuy': 100.})
    checks = pd.DataFrame({'Case': ['A']*3, 'Governing x': ['4.000 m', '5.000 m', '6.000 m'],
        'Demand kN-m': source.Tu, 'D/C value': [.5, float('nan'), .7],
        'Detailing D/C value': [.4, float('nan'), 1.854],
        'Threshold status': ['DESIGN REQUIRED', 'BELOW THRESHOLD', 'DESIGN REQUIRED'],
        'Status': ['REVIEW', 'REVIEW', 'FAIL']})
    diagram = checks.copy(deep=True)
    diagram['φTn kN-m'] = 200.
    diagram['Diagram source case'] = 'A'
    return source, checks, diagram


def figure(source, checks, diagram):
    return make_torsion_utilization_figure(source, checks, diagram=diagram,
        code_label='AASHTO LRFD 9th Edition', span_m=20., member_name='Interior Girder 2', case='A')


def strength(fig):
    return next(t for t in fig.data if t.name == 'Strength |Tu|/φTn')


def test_below_threshold_uses_actual_resistance_without_filling_original_design_dc():
    source, checks, diagram = pairs()
    before = deepcopy(checks)
    fig = figure(source, checks, diagram)
    blue = strength(fig)
    assert blue.y == pytest.approx([.5, source.Tu.iloc[1]/200., .7])
    assert blue.connectgaps is False
    design = next(t for t in fig.data if t.name == 'Original max check D/C')
    assert design.mode == 'markers' and math.isnan(design.y[1])
    assert design.y[2] == 1.854
    gov = next(t for t in fig.data if t.name == 'Governing original check')
    assert gov.x == (6.,) and gov.y == (1.854,)
    assert gov.customdata[0][1] == 'Torsion detailing'
    audit = fig.layout.meta['torsion_utilization_audit'][1]
    assert audit['Threshold status'] == 'BELOW THRESHOLD'
    assert audit['Original row status'] == 'REVIEW'
    assert audit['Original maximum check D/C'] is None and not audit['Curve gap']
    assert audit['Tu kN-m'] == source.Tu.iloc[1]
    pd.testing.assert_frame_equal(checks, before, check_exact=True)


@pytest.mark.parametrize('tu,capacity,cached_tu,reason', [
    (float('nan'), 200., 0., 'Original Tu'), (1.58, float('nan'), 1.58, 'finite and positive'),
    (1.58, 0., 1.58, 'finite and positive'), (1.58, -200., 1.58, 'finite and positive'),
    (1.58, float('inf'), 1.58, 'finite and positive'), (1.58, 200., 1., 'does not match'),
    (1.58, 200., float('nan'), 'does not match'),
])
def test_unavailable_pairs_retain_real_gaps_and_audited_reasons(tu, capacity, cached_tu, reason):
    source, checks, diagram = pairs()
    source.loc[1, 'Tu'] = tu
    diagram.loc[1, 'Demand kN-m'] = cached_tu
    diagram.loc[1, 'φTn kN-m'] = capacity
    fig = figure(source, checks, diagram)
    assert math.isnan(strength(fig).y[1])
    audit = fig.layout.meta['torsion_utilization_audit'][1]
    assert reason in audit['Explanation'] and audit['Curve gap']
    assert fig.layout.meta['unavailable_capacity'][0]['x_m'] == 5.
    assert any(a.text == '×' and a.x == 5. and a.yref == 'paper' for a in fig.layout.annotations)


def test_actual_zero_tu_has_a_zero_strength_ratio_with_positive_stored_capacity():
    source, checks, diagram = pairs()
    source.loc[1, 'Tu'] = diagram.loc[1, 'Demand kN-m'] = 0.
    checks.loc[1, 'Threshold status'] = 'BELOW THRESHOLD'
    fig = figure(source, checks, diagram)
    assert strength(fig).y[1] == 0.
    assert fig.layout.meta['torsion_utilization_audit'][1]['Original maximum check D/C'] is None


@pytest.mark.parametrize('field,value', [('Diagram source case', 'Other case'),
    ('Diagram source sheet', 'Other sheet'), ('Diagram source row', '9')])
def test_mismatched_cached_source_is_not_borrowed(field, value):
    source, checks, diagram = pairs()
    diagram[field] = ''
    diagram.loc[1, field] = value
    audit = utilization_audit(source, checks, diagram, span_m=20.)
    assert audit.iloc[1]['Availability'] == 'UNAVAILABLE'
    assert field in audit.iloc[1]['Explanation']


@pytest.mark.parametrize('duplicate', ['source', 'capacity'])
def test_ambiguous_same_case_station_is_not_silently_selected(duplicate):
    source, checks, diagram = pairs()
    if duplicate == 'source':
        source = pd.concat([source, source.iloc[[1]]], ignore_index=True)
    else:
        diagram = pd.concat([diagram, diagram.iloc[[1]]], ignore_index=True)
    audit = utilization_audit(source, checks, diagram, span_m=20.)
    assert audit.iloc[1]['Availability'] == 'UNAVAILABLE'
    assert 'Ambiguous' in audit.iloc[1]['Explanation']


def test_missing_station_resistance_is_not_interpolated_from_neighbors():
    source, checks, diagram = pairs()
    fig = figure(source, checks, diagram.drop(index=1))
    assert math.isnan(strength(fig).y[1])
    assert 'missing' in fig.layout.meta['torsion_utilization_audit'][1]['Explanation']


def test_all_case_envelope_maximizes_paired_ratios_not_independent_force_capacity_bounds():
    source = pd.DataFrame({'Case Name': ['A', 'B'], 'Station x (m)': [5., 5.], 'Tu': [100., 60.]})
    checks = pd.DataFrame({'Case': ['A', 'B'], 'Governing x': ['5.000 m']*2,
                          'D/C value': [1., 2.], 'Status': ['PASS', 'FAIL']})
    diagram = checks.assign(**{'Demand kN-m': [100., 60.], 'φTn kN-m': [100., 30.]})
    fig = figure(source, checks, diagram)
    assert strength(fig).y == (2.,) and strength(fig).customdata[0][0] == 'B'
    assert strength(fig).y[0] != 100./30.
    diagram.loc[1, 'φTn kN-m'] = float('nan')
    fig = figure(source, checks, diagram)
    assert strength(fig).y == (1.,) and strength(fig).customdata[0][4] == 1
    audit = fig.layout.meta['torsion_utilization_audit']
    assert len(audit) == 2 and not any(r['Curve gap'] for r in audit)
    assert audit[1]['Availability'] == 'UNAVAILABLE'
    assert controlling_result(checks, 'Torsion')['row']['Case'] == 'B'


def test_original_infinite_check_is_labelled_infinite_and_does_not_change_strength_curve():
    source, checks, diagram = pairs()
    checks.loc[2, 'Detailing D/C value'] = float('inf')
    fig = figure(source, checks, diagram)
    design = next(t for t in fig.data if t.name == 'Original max check D/C')
    assert design.customdata[2][2] == '∞' and math.isfinite(design.y[2])
    assert strength(fig).y[2] == .7
    assert any(a.text == '∞' for a in fig.layout.annotations)


def test_actual_solver_below_threshold_and_zero_station_have_qualified_cached_ratios():
    state = ready_state()
    source = pd.concat([_demand(x=5., tu=1.58), _demand(x=6., tu=300.),
                        _demand(x=7., tu=0.)], ignore_index=True)
    result = mr.calculate_member(state, source, check_name='Torsion', route=_route())
    before = deepcopy(result)
    with patch.object(ap, '_beam_uls_igird_torsion_result_for_row', side_effect=AssertionError('Review cannot solve')):
        fig = figure(source, result['torsion_check_df'], result['torsion_diagram_capacity_df'])
    audit = pd.DataFrame(fig.layout.meta['torsion_utilization_audit'])
    assert audit['Availability'].eq('AVAILABLE').all()
    assert audit.iloc[0]['Strength utilization |Tu|/phiTn'] == pytest.approx(1.58/audit.iloc[0]['phiTn kN-m'])
    assert audit.iloc[2]['Strength utilization |Tu|/phiTn'] == 0.
    checks = result['torsion_check_df']
    assert checks.loc[checks['Governing x'].isin(['5.000 m', '7.000 m']), 'D/C value'].isna().all()
    for key, value in result.items():
        if isinstance(value, pd.DataFrame):
            pd.testing.assert_frame_equal(value, before[key], check_exact=True)


def test_native_csi_shared_endpoints_use_only_their_qualified_original_pair(native):
    from concrete_pmm_pro.visualization.igird_uls_chart_display import native_csi_diagram_rows
    selected_case = next(case for case in native['Case Name'].unique() if case.endswith('Max / set 2'))
    source = native.loc[native['Case Name'].eq(selected_case)]
    physical = native_csi_diagram_rows(source, member_length_m=20., source_context_df=native)
    diagram = pd.DataFrame({'Case': physical['Case Name'],
        'Governing x': physical['Station x (m)'].map(lambda x: f'{x:.3f} m'),
        'Demand kN-m': physical['Tu'], 'φTn kN-m': 200.,
        'Diagram source case': physical['__Source case'],
        'Diagram source sheet': physical['__Source sheet'], 'Diagram source row': physical['__Source row']})
    checks = diagram[['Case', 'Governing x']].assign(Status='REVIEW')
    fig = make_torsion_utilization_figure(source, checks, diagram=diagram,
        code_label='QA', span_m=20., source_context_df=native)
    assert strength(fig).x[0] == 0. and strength(fig).x[-1] == 20.
    audit = fig.layout.meta['torsion_utilization_audit']
    assert all(row['Availability'] == 'AVAILABLE' for row in audit)
    endpoints = [r for r in audit if r['Station x (m)'] in (0., 20.)]
    assert all(r['Diagram source case'].endswith('Max / set 1') for r in endpoints)
    assert all(r['Case'] == selected_case for r in endpoints)


def test_station_formatter_collision_preserves_both_unavailable_source_rows():
    source, checks, diagram = pairs()
    collision = source.iloc[[1]].copy()
    collision.loc[:, 'Station x (m)'] = 5.0001
    source = pd.concat([source, collision], ignore_index=True)
    audit = utilization_audit(source, checks, diagram, span_m=20.)
    collided = audit.loc[audit['Original source row count'].eq(2)]
    assert len(collided) == 2 and collided['Availability'].eq('UNAVAILABLE').all()
    assert set(collided['Station x (m)']) == {5., 5.0001}


def test_report_utilization_is_case_scoped_and_preserves_actual_design_control(calculated_state):
    state = deepcopy(calculated_state)
    before = deepcopy(state)
    with no_report_solvers():
        for member, package in report.current_check_packages(state, 'Torsion').items():
            for suffix in ('ULS1', 'ULS2'):
                case = member+' / '+suffix
                fig = report.make_package_figure(state, package, member=member, case=case,
                    check_name='Torsion', code_label='QA', chart_view='Overview — utilization')
                assert fig.layout.meta['review_case'] == case
                assert all(row['Case'] == case for row in fig.layout.meta['torsion_utilization_audit'])
                assert fig.layout.meta['igird_report_view'] == 'Overview — utilization'
                assert 'Open markers' in fig.layout.meta['igird_report_note'][0]
                assert fig.layout.meta['igird_report_selected_control']['Component'] == controlling_result(
                    package['result']['torsion_check_df'].loc[lambda f: f.Case.eq(case)], 'Torsion')['component']
    pd.testing.assert_frame_equal(state['igird_uls_member_bank'], before['igird_uls_member_bank'], check_exact=True)
    pd.testing.assert_frame_equal(state['beam_uls_loads_table'], before['beam_uls_loads_table'], check_exact=True)
