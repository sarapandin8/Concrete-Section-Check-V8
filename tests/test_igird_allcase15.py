"""All selection must preserve every source curve and same-case resistance."""
from contextlib import ExitStack
from copy import deepcopy
from unittest.mock import patch
import math

import pandas as pd
import pytest
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui.igird_vt_workspace import make_strength_all_cases_figure
from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS
from concrete_pmm_pro.visualization.igird_uls_chart_display import native_csi_diagram_rows
from qa.igird_allcase15_model import source_model
from test_igird_uls6_torsion_general_procedure import _route


@pytest.fixture(scope='module')
def packages():
    state = source_model()
    result = {}
    for member, rows in mr.member_inputs(state).items():
        for check in ('Shear', 'Torsion'):
            checked = mr.calculate_member(state, rows, check_name=check, route=_route())
            assert not checked.get('error'), checked
            result[member, check] = (rows, checked)
    return state, result


def build(state, rows, result, check):
    kind = check.lower()
    return make_strength_all_cases_figure(rows, result[FRAME_KEYS[check]],
        check_name=check, code_label='AASHTO LRFD 9th Edition', span_m=20.,
        diagram=result.get(kind+'_diagram_capacity_df'),
        boundary=result.get(kind+'_boundary_capacity_df'),
        critical=result.get('shear_critical_section_df'), source_context_df=rows)


@pytest.mark.parametrize('check,component,label', [('Shear','Vuy','Vu'), ('Torsion','Tu','Tu')])
@pytest.mark.parametrize('member', ['BOBJ1 / Left Exterior Girder', 'BOBJ1 / Interior Girder 2'])
def test_every_actual_native_case_and_station_is_plotted_without_solving(packages, check, component, label, member):
    state, all_results = packages
    rows, result = all_results[member, check]
    before = deepcopy(result)
    original = rows.copy(deep=True)
    with ExitStack() as stack:
        for name in ('_beam_uls_calculate_selected_check', '_beam_uls_flexure_preview_dataframe',
                     '_beam_uls_igird_shear_diagram_capacity_dataframe',
                     '_beam_uls_igird_torsion_diagram_capacity_dataframe'):
            stack.enter_context(patch.object(ap, name, side_effect=AssertionError('Review must not solve')))
        stack.enter_context(patch.object(mr, 'calculate_member', side_effect=AssertionError('Review must not solve')))
        fig = build(state, rows, result, check)
    demands = [t for t in fig.data if str(t.name).startswith(label+' C')]
    assert len(demands) == 16 == rows['Case Name'].nunique()
    assert len(fig.layout.meta['member_case_legend']) == 16
    assert set(fig.layout.meta['member_case_legend'].values()) == set(rows['Case Name'])
    expected = native_csi_diagram_rows(rows, member_length_m=20., source_context_df=rows)
    for trace in demands:
        case = fig.layout.meta['member_case_legend'][trace.name]
        source = expected.loc[expected['Case Name'].eq(case)].sort_values('Station x (m)', kind='stable')
        assert list(trace.x) == source['Station x (m)'].tolist()
        assert list(trace.y) == source[component].tolist()
        assert all(custom[0] == case for custom in trace.customdata)
        assert trace.connectgaps is False
        assert trace.showlegend is not False
    assert tuple(fig.layout.xaxis.range) == (0., 20.)
    assert 'all load cases' in fig.layout.title.text
    pd.testing.assert_frame_equal(rows, original, check_exact=True)
    for key, old in before.items():
        if isinstance(old, pd.DataFrame):
            pd.testing.assert_frame_equal(result[key], old, check_exact=True)
    quantity = '±φVn' if check == 'Shear' else '±φTn'
    metric = 'φVn kN' if check == 'Shear' else 'φTn kN-m'
    diagram = result[check.lower()+'_diagram_capacity_df']
    for trace in (t for t in fig.data if t.name == quantity):
        for x, y, custom in zip(trace.x, trace.y, trace.customdata):
            if math.isfinite(y):
                source = diagram.loc[diagram.Case.eq(custom[0]) & diagram['Governing x'].eq(f'{x:.3f} m')]
                # Shear can additionally retain independently checked critical sections.
                if source.empty and check == 'Shear':
                    critical = result['shear_critical_section_df']
                    source = critical.loc[critical.Case.eq(custom[0]) & critical['Governing x'].eq(f'{x:.3f} m')]
                assert not source.empty
                assert abs(y) == pytest.approx(float(source.iloc[0][metric]))


@pytest.mark.parametrize('check', ['Shear','Torsion'])
def test_coincident_demands_keep_both_cases_and_distinct_resistance_remains_separate(check):
    rows = pd.DataFrame([{'Case Name':case,'Station x (m)':x,'Vuy':v,'Tu':v}
        for case in ('A','B') for x,v in ((0.,-10.),(10.,0.),(20.,10.))])
    metric = 'φVn kN' if check == 'Shear' else 'φTn kN-m'
    frame = pd.DataFrame([{'Case':case,'Governing x':f'{x:.3f} m',metric:capacity,
        'φVc kN':10.,'φTcr kN-m':15.,'Threshold kN-m':3.75,'Status':'REVIEW',
        'D/C value':.5,'Strength D/C value':.5}
        for case,capacity in (('A',100.),('B',200.)) for x in (0.,10.,20.)])
    fig = make_strength_all_cases_figure(rows, frame, check_name=check, code_label='QA',span_m=20.)
    demands = [t for t in fig.data if t.name in {'Vu C1','Vu C2','Tu C1','Tu C2'}]
    assert len(demands) == 2
    assert list(demands[0].y) == list(demands[1].y) == [-10.,0.,10.]
    quantity = '±φVn' if check == 'Shear' else '±φTn'
    capacity = [t for t in fig.data if t.name == quantity]
    assert {tuple(t.y) for t in capacity} == {(100.,)*3,(-100.,)*3,(200.,)*3,(-200.,)*3}


@pytest.mark.parametrize('check', ['Shear','Torsion'])
def test_missing_capacity_in_one_case_keeps_its_gap_and_review(packages, check):
    state, all_results = packages
    rows, old = all_results['BOBJ1 / Left Exterior Girder',check]
    result = deepcopy(old)
    diagram = result[check.lower()+'_diagram_capacity_df']
    case = rows['Case Name'].iloc[0]
    metric = 'φVn kN' if check == 'Shear' else 'φTn kN-m'
    at = diagram.Case.eq(case) & diagram['Governing x'].eq('10.000 m')
    assert at.any()
    diagram.loc[at,metric] = float('nan')
    fig = build(state,rows,result,check)
    quantity = '±φVn' if check == 'Shear' else '±φTn'
    paths = [t for t in fig.data if t.name == quantity and t.customdata[0][0] == case]
    assert paths and all(math.isnan(t.y[list(t.x).index(10.)]) and t.connectgaps is False for t in paths)
    assert any(r['x_m'] == 10. and case in r['cases'] for r in fig.layout.meta['unavailable_capacity'])
    assert 'REVIEW' in fig.layout.meta['igird_report_note'][1]


def test_torsion_investigation_reference_is_retained_when_one_case_has_no_strength(packages):
    state, all_results = packages
    rows, old = all_results['BOBJ1 / Left Exterior Girder','Torsion']
    result = deepcopy(old)
    case = rows['Case Name'].iloc[0]
    diagram = result['torsion_diagram_capacity_df']
    diagram.loc[diagram.Case.eq(case),'φTn kN-m'] = float('nan')
    fig = build(state,rows,result,'Torsion')
    assert any(t.name == '±0.25φTcr' and t.customdata[0][0] == case for t in fig.data)
    assert len(fig.layout.meta['member_case_legend']) == 16
