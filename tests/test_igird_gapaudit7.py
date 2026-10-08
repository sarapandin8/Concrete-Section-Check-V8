"""Missing ratios must explain their source without changing strength decisions."""
from copy import deepcopy
import math
from unittest.mock import patch

import pandas as pd
import pytest

from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_case_review import controlling_result
from concrete_pmm_pro.ui.igird_vt_workspace import make_overview_figure
from test_igird_uls7_concurrent_vt import ready_state
from test_igird_uls6_torsion_general_procedure import _demand, _route


def below_row(**changes):
    # Visible in the user's PDF: threshold screen exists despite overall REVIEW.
    return {'Case': 'Interior / ULS2', 'Governing x': '5.000 m',
        'Status': 'REVIEW', 'Threshold status': 'BELOW THRESHOLD',
        'Transverse status': 'NOT REQUIRED', 'Longitudinal status': 'NOT REQUIRED',
        'Demand kN-m': 1.58, 'Abs demand kN-m': 1.58, 'Threshold kN-m': 27.72,
        'D/C value': float('nan'), 'Source coupling': 'ENVELOPE — REVIEW',
        'Source Excel row': '17', **changes}


def figure(rows, *, source=None, investigation=False, check='Torsion'):
    frame = pd.DataFrame(rows)
    if source is None:
        source = pd.DataFrame({'Case Name': frame['Case'],
            'Station x (m)': frame['Governing x'].str.replace(' m', '', regex=False).astype(float),
            'Tu': frame.get('Demand kN-m', pd.Series(100., index=frame.index)),
            'Vuy': 100.})
    before = deepcopy(frame)
    fig = make_overview_figure(source, frame, check_name=check,
        code_label='AASHTO LRFD 9th Edition', span_m=20., investigation=investigation)
    pd.testing.assert_frame_equal(frame, before, check_exact=True)
    return fig


def strength_neighbor(x, ratio=.7, **changes):
    return {'Case': 'Interior / ULS2', 'Governing x': f'{x:.3f} m', 'Status': 'REVIEW',
        'Threshold status': 'DESIGN REQUIRED', 'D/C value': ratio,
        'Demand kN-m': 200., **changes}


def test_pdf_below_threshold_gap_keeps_overall_review_and_original_curve_values():
    fig = figure([strength_neighbor(4, .5), below_row(), strength_neighbor(6, .7)])
    trace = next(t for t in fig.data if t.name == 'Max D/C')
    assert list(trace.x) == [4., 5., 6.]
    assert trace.y[0] == .5 and math.isnan(trace.y[1]) and trace.y[2] == .7
    assert trace.connectgaps is False
    gap = fig.layout.meta['overview_gap_stations'][0]
    assert gap['classification'] == 'BELOW THRESHOLD' and gap['x_m'] == 5.
    assert gap['stored_statuses'] == ['REVIEW']
    audit = fig.layout.meta['overview_missing_ratio_audit'][0]
    assert audit['Tu kN-m'] == 1.58 and audit['Threshold kN-m'] == 27.72
    assert audit['Source Excel row'] == '17'
    marker = next(a for a in fig.layout.annotations if a.x == 5.)
    assert marker.text == '○' and marker.yref == 'paper'


def test_unavailable_hoop_source_has_a_cross_and_no_filled_strength_ratio():
    row = below_row(**{'Status': 'LAYOUT REQUIRED', 'Threshold status': 'DESIGN REQUIRED',
        'Transverse status': 'NOT READY', 'Demand kN-m': 200., 'Abs demand kN-m': 200.,
        'Notes': 'Closed hoop zone is not qualified.'})
    fig = figure([strength_neighbor(4), row, strength_neighbor(6)])
    assert fig.layout.meta['overview_gap_stations'][0]['classification'] == 'UNAVAILABLE'
    assert next(a for a in fig.layout.annotations if a.x == 5.).text == '×'
    assert 'Closed hoop' in fig.layout.meta['overview_missing_ratio_audit'][0]['Explanation']
    assert math.isnan(next(t for t in fig.data if t.name == 'Max D/C').y[1])


def test_another_case_supplies_the_station_ratio_without_erasing_missing_case_rows():
    fig = figure([strength_neighbor(5, .6, Case='Known'), below_row(Case='Below'),
        below_row(Case='Missing', **{'Threshold status': 'DESIGN REQUIRED', 'Status': 'LAYOUT REQUIRED'})])
    trace = next(t for t in fig.data if t.name == 'Max D/C')
    assert list(trace.y) == [.6] and trace.customdata[0][0] == 'Known'
    assert fig.layout.meta['overview_gap_stations'] == []
    audit = fig.layout.meta['overview_missing_ratio_audit']
    assert {r['Case'] for r in audit} == {'Below', 'Missing'}
    assert not any(r['Curve gap'] for r in audit)


@pytest.mark.parametrize('tu,classification', [(0., 'NO DEMAND'),
    (float('nan'), 'UNAVAILABLE'), (1., 'UNAVAILABLE')])
def test_no_demand_label_requires_a_finite_zero_original_action(tu, classification):
    row = below_row(**{'Transverse status': 'NO DEMAND', 'Threshold status': '',
        'Demand kN-m': 0., 'Abs demand kN-m': 0.})
    source = pd.DataFrame({'Case Name': [row['Case']], 'Station x (m)': [5.],
        'Tu': [tu], 'Vuy': [100.]})
    fig = figure([row], source=source)
    assert fig.layout.meta['overview_gap_stations'][0]['classification'] == classification


@pytest.mark.parametrize('threshold', [float('nan'), 0., -1., 1.])
def test_invalid_or_contradictory_threshold_fields_are_not_labelled_not_required(threshold):
    fig = figure([below_row(**{'Threshold kN-m': threshold})])
    assert fig.layout.meta['overview_gap_stations'][0]['classification'] == 'UNAVAILABLE'


def test_investigation_ratio_remains_a_separate_plot_basis():
    fig = figure([below_row()], investigation=True)
    trace = next(t for t in fig.data if t.name == 'Investigation')
    assert trace.y[0] == pytest.approx(1.58/27.72)
    assert fig.layout.meta['overview_gap_stations'] == []
    assert fig.layout.meta['overview_missing_ratio_audit'] == []
    assert 'not torsion strength' in fig.layout.title.text


@pytest.mark.parametrize('check', ['Shear', 'Shear + Torsion'])
def test_other_overview_unknown_ratios_keep_review_and_the_gap(check):
    row = {'Case': 'A', 'Status': 'REVIEW', 'Governing x': '5.000 m', 'D/C value': float('nan')}
    fig = figure([row], check=check)
    assert fig.layout.meta['overview_gap_stations'][0]['classification'] == 'UNAVAILABLE'
    assert fig.layout.meta['overview_gap_stations'][0]['stored_statuses'] == ['REVIEW']


def test_gap_annotations_escape_source_text_without_changing_original_identity():
    fig = figure([below_row(Case='<untrusted> & source')])
    assert fig.layout.meta['overview_missing_ratio_audit'][0]['Case'] == '<untrusted> & source'
    assert '&lt;untrusted&gt; &amp; source' in fig.layout.annotations[0].hovertext


def test_audit_retains_full_stored_float_precision():
    demand = 1.581234567890123
    fig = figure([below_row(**{'Demand kN-m': demand, 'Abs demand kN-m': demand})])
    assert fig.layout.meta['overview_missing_ratio_audit'][0]['Tu kN-m'] == demand


def test_real_solver_decisions_and_separately_calculated_diagram_resistance_are_unchanged():
    state = ready_state()
    source = pd.concat([_demand(x=5., tu=1.58), _demand(x=6., tu=300.)], ignore_index=True)
    decisions = ap._beam_uls_torsion_check_dataframe(state, source, strength_route=_route())
    before = deepcopy(decisions)
    control = controlling_result(decisions, 'Torsion')
    diagram = ap._beam_uls_igird_torsion_diagram_capacity_dataframe(state, source, decisions, strength_route=_route())
    at_five = diagram.loc[diagram['Governing x'].eq('5.000 m')].iloc[0]
    assert at_five['φTn kN-m'] > 0 and math.isnan(at_five['D/C value'])
    with patch.object(ap, '_beam_uls_igird_torsion_result_for_row', side_effect=AssertionError('No review solver')):
        fig = make_overview_figure(source, decisions, check_name='Torsion',
            code_label='AASHTO LRFD 9th Edition', span_m=20.)
    assert fig.layout.meta['overview_gap_stations'][0]['classification'] == 'BELOW THRESHOLD'
    assert math.isnan(next(t for t in fig.data if t.name == 'Max D/C').y[0])
    pd.testing.assert_frame_equal(decisions, before, check_exact=True)
    assert controlling_result(decisions, 'Torsion')['ratio'] == control['ratio']
    assert controlling_result(decisions, 'Torsion')['row']['Case'] == control['row']['Case']

def test_report_case_has_calculated_capacity_through_threshold_and_zero_without_filling_dc():
    from concrete_pmm_pro.ui.igird_vt_workspace import make_torsion_case_figure
    state = ready_state()
    source = pd.concat([_demand(x=4.,tu=100.),_demand(x=5.,tu=1.58),
                        _demand(x=6.,tu=0.)],ignore_index=True)
    decisions = ap._beam_uls_torsion_check_dataframe(state,source,strength_route=_route())
    diagram = ap._beam_uls_igird_torsion_diagram_capacity_dataframe(state,source,decisions,strength_route=_route())
    before = decisions.copy(deep=True)
    with patch.object(ap,'_beam_uls_igird_torsion_diagram_capacity_dataframe',side_effect=AssertionError('No report solver')):
        fig = make_torsion_case_figure(source,decisions,case='Strength I',code_label='QA',
            span_m=20.,diagram=diagram,member_name='Interior Girder 2')
    cap = next(t for t in fig.data if t.name=='±φTn')
    assert list(cap.x)==[4.,5.,6.] and all(math.isfinite(v) and v>0 for v in cap.y)
    assert list(cap.y)==diagram['φTn kN-m'].tolist()
    assert decisions.loc[decisions['Governing x'].isin(['5.000 m','6.000 m']),'D/C value'].isna().all()
    assert fig.layout.meta['review_case']=='Strength I'
    assert 'below-threshold / zero-Tu' in fig.layout.meta['igird_report_note'][0]
    assert any(a.name=='igird_report_note' for a in fig.layout.annotations)
    assert fig.layout.margin.b>=152 and fig.layout.margin.t>=122
    pd.testing.assert_frame_equal(before,decisions,check_exact=True)


def test_report_case_keeps_unknown_resistance_and_its_image_explanation():
    from concrete_pmm_pro.ui.igird_vt_workspace import make_torsion_case_figure
    source=pd.DataFrame({'Case Name':['A']*3,'Station x (m)':[4.,5.,6.],'Tu':[100.,1.58,100.]})
    rows=pd.DataFrame([strength_neighbor(4,Case='A'),below_row(Case='A'),strength_neighbor(6,Case='A')])
    diagram=rows.copy()
    diagram['φTn kN-m']=[200.,float('nan'),200.]
    diagram['φTcr kN-m']=100.
    diagram['Threshold kN-m']=25.
    fig=make_torsion_case_figure(source,rows,case='A',code_label='QA',span_m=20.,diagram=diagram)
    cap=next(t for t in fig.data if t.name=='±φTn')
    assert math.isnan(cap.y[1]) and cap.connectgaps is False
    assert fig.layout.meta['unavailable_capacity'][0]['x_m']==5.
    assert '1 unavailable resistance' in fig.layout.meta['igird_report_note'][1]


@pytest.fixture
def report_state():
    from test_igird_casecontrol5 import review_model
    from concrete_pmm_pro.io.girder_load_bank import activate_member
    from concrete_pmm_pro.ui import igird_member_results as mr
    state=review_model()
    activate_member(state,'Exterior Girder')
    route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    state[mr.CACHE_KEY]={}
    for member,rows in mr.member_inputs(state).items():
        state[mr.CACHE_KEY][member]={'Torsion':{
            'input_hash':mr.result_hash(state,rows,check_name='Torsion',route=route),
            'result':mr.calculate_member(state,rows,check_name='Torsion',route=route)}}
    return state


def test_report_uses_current_girder_case_package_without_solver_or_state_change(report_state):
    from concrete_pmm_pro.ui.igird_torsion_report import current_torsion_packages,make_package_figure
    from concrete_pmm_pro.ui import igird_member_results as mr
    before=deepcopy(report_state)
    with patch.object(ap,'_beam_uls_calculate_selected_check',side_effect=AssertionError('No report solver')):
        packages=current_torsion_packages(report_state)
        assert set(packages)=={'Exterior Girder','Interior Girder 2'}
        for member,package in packages.items():
            case=member+' / ULS2'
            fig=make_package_figure(report_state,package,member=member,case=case,code_label='QA')
            assert fig.layout.meta['review_case']==case
            assert fig.layout.title.text.startswith('Girder: '+member+'<br>')
            caps=[t for t in fig.data if t.name=='±φTn']
            assert caps and all(row[0]==case for t in caps for row in t.customdata)
    for member in packages:
        old=before[mr.CACHE_KEY][member]['Torsion']['result']
        for key,value in old.items():
            if isinstance(value,pd.DataFrame):
                pd.testing.assert_frame_equal(value,report_state[mr.CACHE_KEY][member]['Torsion']['result'][key],check_exact=True)
    pd.testing.assert_frame_equal(before['igird_uls_member_bank'],report_state['igird_uls_member_bank'],check_exact=True)
    pd.testing.assert_frame_equal(before['beam_uls_loads_table'],report_state['beam_uls_loads_table'],check_exact=True)
    manual=deepcopy(before)
    entry=manual[mr.CACHE_KEY]['Exterior Girder']['Torsion']
    ap._beam_uls_store_manual_result(manual,'Torsion',input_hash=entry['input_hash'],result=entry['result'])
    manual[mr.CACHE_KEY]={}
    manual['igird_uls_member_bank']=[]
    packages=current_torsion_packages(manual)
    assert set(packages)=={'Exterior Girder'}, 'The original single-table manual cache remains reportable'


def test_report_hides_active_table_change_even_before_bank_save(report_state):
    from concrete_pmm_pro.ui.igird_torsion_report import current_torsion_packages, make_current_torsion_report_figure
    report_state['beam_uls_loads_table'].loc[:,'Tu']=999.
    assert set(current_torsion_packages(report_state))=={'Interior Girder 2'}
    assert make_current_torsion_report_figure(report_state,member='Exterior Girder',code_label='QA') is None


def test_report_hides_old_version_and_stale_member_result(report_state):
    from concrete_pmm_pro.ui.igird_torsion_report import current_torsion_packages
    from concrete_pmm_pro.ui import igird_member_results as mr
    report_state[mr.CACHE_KEY]['Exterior Girder']['Torsion']['result']['result_version']='old'
    report_state['igird_uls_member_bank'].loc[report_state['igird_uls_member_bank']['Girder'].eq('Interior Girder 2'),'Tu']=999.
    assert not current_torsion_packages(report_state)


def test_overview_image_explains_omitted_ratios_without_the_ui_caption():
    fig=figure([strength_neighbor(4),below_row(),strength_neighbor(6)])
    note=next(a for a in fig.layout.annotations if a.name=='igird_report_note')
    assert 'not D/C=0' in note.text and 'below threshold' in note.text
    assert fig.layout.margin.b>=152
