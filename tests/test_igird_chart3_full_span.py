"""Source-boundary and capacity-diagram regressions; no fictitious resistance."""
import json
import math
from pathlib import Path
from copy import deepcopy

import pandas as pd
import pytest

from concrete_pmm_pro.io.girder_csi_import import read_tables, prepare_csi_table, SOURCE_TAG
from concrete_pmm_pro.visualization.igird_uls_chart_display import native_csi_diagram_rows
from concrete_pmm_pro.ui import analysis_page as ap
from test_igird_uls6_torsion_general_procedure import _state, _route, _demand
from test_igird_uls7_concurrent_vt import ready_state


@pytest.fixture
def native():
    path = Path('qa/fixtures/CSiBridge_Left_Exterior_Max_Min_latest.xlsx')
    return prepare_csi_table(read_tables(path.read_bytes(), path.name)['Left Exterior Girder'],
        sheet_name='Left Exterior Girder').frame


@pytest.mark.parametrize('component', ['Vuy', 'Tu', 'Mux'])
def test_all_four_force_paths_retain_exact_rows_and_share_only_unique_family_endpoints(native, component):
    before = native.copy(deep=True)
    for case, group in native.groupby('Case Name', sort=False):
        fig = ap._make_beam_uls_demand_figure(group, column=component, title='QA', y_label='QA',
            member_length_m=20, source_context_df=native)
        trace = fig.data[0]
        assert list(trace.x) == list(range(21))
        points = dict(zip(trace.x, trace.y))
        assert all(points[row['Station x (m)']] == row[component] for _, row in group.iterrows())
        if case.endswith('set 2'):
            step = 'Max' if '/ Max /' in case else 'Min'
            original_ends = native.loc[native['Case Name'].str.contains('/ '+step+' /') & native['Station x (m)'].isin([0, 20])]
            assert {x:points[x] for x in (0, 20)} == dict(zip(original_ends['Station x (m)'], original_ends[component]))
            assert len(fig.layout.meta['shared_csi_endpoints']) == 2
            assert trace.customdata[0][1].endswith('set 1') and 'Shared physical endpoint' in trace.customdata[0][4]
            assert trace.customdata[-1][3] == (81 if step == 'Max' else 82)
        else:
            assert not fig.layout.meta['shared_csi_endpoints']
    pd.testing.assert_frame_equal(native, before)
    assert len(native) == 80 and len(native)*6 == 480


@pytest.mark.parametrize('metadata_key,value', [('sheet','Other girder'), ('case','Other case'), ('step','Min'), ('schema','Unknown schema')])
def test_shared_endpoints_require_matching_verified_source_family(native, metadata_key, value):
    target = native.loc[native['Case Name'].str.endswith('/ Max / set 2')]
    context = native.copy(deep=True)
    index = context.loc[context['Station x (m)'].eq(0) & context['Case Name'].str.contains('/ Max /')].index[0]
    info = json.loads(context.loc[index, 'Note'].split(SOURCE_TAG)[1]); info[metadata_key] = value
    context.loc[index, 'Note'] = SOURCE_TAG+json.dumps(info)
    view = native_csi_diagram_rows(target, member_length_m=20, source_context_df=context)
    assert not view['Station x (m)'].eq(0).any()
    assert view['Station x (m)'].eq(20).any()


@pytest.mark.parametrize('conflict', [False, True])
def test_multiple_source_endpoints_are_not_guessed_or_enveloped(native, conflict):
    target = native.loc[native['Case Name'].str.endswith('/ Max / set 2')]
    duplicate = native.loc[native['Station x (m)'].eq(0) & native['Case Name'].str.contains('/ Max /')].copy()
    if conflict:
        duplicate['Vuy'] += 123
    context = pd.concat([native, duplicate], ignore_index=True)
    view = native_csi_diagram_rows(target, member_length_m=20, source_context_df=context)
    assert not view['Station x (m)'].eq(0).any()


def test_no_interior_fill_no_nan_overwrite_and_no_inferred_physical_span(native):
    target = native.loc[native['Case Name'].str.endswith('/ Max / set 2') & native['Station x (m)'].ne(10)].copy()
    view = native_csi_diagram_rows(target, member_length_m=20, source_context_df=native)
    assert not view['Station x (m)'].eq(10).any()
    end = native.loc[native['Case Name'].str.endswith('/ Max / set 1') & native['Station x (m)'].eq(0)].copy()
    end['Case Name'] = target['Case Name'].iloc[0]; end['Vuy'] = float('nan')
    target = pd.concat([target, end], ignore_index=True)
    view = native_csi_diagram_rows(target, member_length_m=20, source_context_df=native)
    assert view.loc[view['Station x (m)'].eq(0), 'Vuy'].isna().all()
    assert not native_csi_diagram_rows(target, member_length_m=21, source_context_df=native)['Station x (m)'].eq(21).any()


def test_case_text_without_native_provenance_does_not_share_endpoints(native):
    native['Note'] = ''
    view = native_csi_diagram_rows(native, member_length_m=20)
    assert len(view) == len(native) and not view['__Shared CSI endpoint'].any()


def test_inactive_source_endpoint_is_not_shared_and_nullable_legacy_notes_are_safe(native):
    target = native.loc[native['Case Name'].str.endswith('/ Max / set 2')]
    context = native.copy(deep=True)
    context.loc[context['Station x (m)'].eq(0) & context['Case Name'].str.contains('/ Max /'),'Active'] = False
    view = native_csi_diagram_rows(target,member_length_m=20,source_context_df=context)
    assert not view['Station x (m)'].eq(0).any()
    context['Note'] = pd.NA
    assert not native_csi_diagram_rows(context,member_length_m=20)['__Shared CSI endpoint'].any()


@pytest.mark.parametrize('tu', [0.0, 10.0])
def test_below_threshold_and_zero_demand_have_calculated_diagram_capacity_without_new_decision(tu):
    state = _state(); source = _demand(x=10, tu=tu)
    decisions = ap._beam_uls_torsion_check_dataframe(state, source, strength_route=_route())
    before = decisions.copy(deep=True)
    assert decisions.iloc[0]['Status'] == ('NO DEMAND' if tu == 0 else 'BELOW THRESHOLD')
    assert decisions['φTn kN-m'].isna().all()
    diagram = ap._beam_uls_igird_torsion_diagram_capacity_dataframe(state, source, decisions, strength_route=_route())
    row = diagram.iloc[0]
    assert row['φTn kN-m'] > 0 and row['Status'] == 'DIAGRAM ONLY' and math.isnan(row['D/C value'])
    expected_theta = 29+3500*max(0, min(.006, row['εs raw']))
    expected = row['φ']*2*row['Ao mm2']*row['At/s mm2/mm']*row['fy MPa']/math.tan(math.radians(expected_theta))/1e6
    assert row['φTn kN-m'] == pytest.approx(expected, rel=2e-10)
    pd.testing.assert_frame_equal(decisions, before)


def test_below_threshold_keeps_source_gates_and_no_interior_capacity_is_copied_to_ends():
    state = _state(closed=False); source = _demand(x=10, tu=10)
    decision = ap._beam_uls_torsion_check_dataframe(state, source, strength_route=_route())
    diagram = ap._beam_uls_igird_torsion_diagram_capacity_dataframe(state, source, decision, strength_route=_route())
    assert decision.iloc[0]['Status'] == 'BELOW THRESHOLD' and diagram['φTn kN-m'].isna().all()
    state = _state(); source = pd.concat([_demand(x=x,tu=100) for x in (0,10,20)],ignore_index=True)
    decision = ap._beam_uls_torsion_check_dataframe(state,source,strength_route=_route())
    diagram = ap._beam_uls_igird_torsion_diagram_capacity_dataframe(state,source,decision,strength_route=_route())
    assert diagram['φTn kN-m'].notna().tolist() == [False,True,False]
    fig = ap._make_beam_uls_torsion_capacity_figure(source,decision,code_label='QA',diagram_capacity_df=diagram,member_length_m=20)
    assert [row['x_m'] for row in fig.layout.meta['unavailable_capacity']] == [0,20]
    assert all(annotation.yref == 'paper' for annotation in fig.layout.annotations)
    trace = next(t for t in fig.data if t.name == '±φTn')
    assert math.isnan(trace.y[0]) and math.isnan(trace.y[-1]) and trace.connectgaps is False
    assert trace.mode == 'lines+markers', 'An isolated known resistance must remain visible'


def test_verified_developed_ordinary_bars_provide_actual_end_capacity():
    state = ready_state(); source = pd.concat([_demand(x=x,tu=10) for x in (0,10,20)],ignore_index=True)
    decision = ap._beam_uls_torsion_check_dataframe(state,source,strength_route=_route())
    diagram = ap._beam_uls_igird_torsion_diagram_capacity_dataframe(state,source,decision,strength_route=_route())
    assert diagram['φTn kN-m'].notna().all()
    assert diagram['Source decision status'].eq('BELOW THRESHOLD').all()


def test_igird_shear_capacity_keeps_an_internal_missing_row_instead_of_bridging_it():
    source = pd.concat([_demand(x=x) for x in (0,10,20)],ignore_index=True)
    rows = pd.DataFrame([{'Case':'Strength I','Governing x':f'{x} m', 'φVn kN':v,
        'φVc kN':50, 'D/C value':float('nan'), 'Notes':'Missing source' if math.isnan(v) else '', 'Status':'REVIEW'}
        for x,v in [(0,100),(10,float('nan')),(20,100)]])
    fig = ap._make_beam_uls_shear_capacity_figure(source,rows,code_label='QA',compact_csi_legend=True,member_length_m=20)
    trace = next(t for t in fig.data if t.name=='±φVn')
    assert list(trace.x) == [0,10,20] and math.isnan(trace.y[1]) and trace.connectgaps is False
    assert fig.layout.meta['unavailable_capacity'][0]['x_m'] == 10


def test_old_torsion_cache_cannot_supply_missing_diagram_payload():
    state = _state(); source = _demand()
    check = 'Torsion'
    signature = ap._beam_uls_check_input_hash(state,source,strength_route=_route(),check_name=check)
    entry = ap._beam_uls_store_manual_result(state,check,input_hash=signature,result={})
    entry['result_version'] = 'IGIRDER.VTQA1.torsion-developed-source'
    assert ap._beam_uls_current_cached_result(state,check,signature) is None


def test_combined_calculation_carries_diagram_without_changing_summary_kernel_version():
    state = _state(); source = _demand()
    result = ap._beam_uls_calculate_selected_check(state,source,selected_check='Shear + Torsion',strength_route=_route())
    assert ap._IGIRDER_COMBINED_VT_RESULT_VERSION == ap.IGIRD_CONCURRENT_VT_VERSION
    assert 'torsion_diagram_capacity_df' in result
    assert result['torsion_diagram_capacity_df']['Status'].eq('DIAGRAM ONLY').all()
    assert result['torsion_diagram_capacity_df']['D/C value'].isna().all()


def test_shared_physical_endpoints_have_identical_actual_shear_resistance_for_both_row_sets(native):
    state = ready_state(); source = native.copy(deep=True); source['Nu'] = 0
    checked = ap._beam_uls_shear_check_dataframe(state,source,strength_route=_route())
    diagram = ap._beam_uls_igird_shear_diagram_capacity_dataframe(state,source,checked,strength_route=_route())
    assert len(diagram)==84 and diagram['φVn kN'].notna().all()
    for step in ['Max','Min']:
        for x in ['0.000 m','20.000 m']:
            rows = diagram.loc[diagram['Case'].str.contains('/ '+step+' /') & diagram['Governing x'].eq(x)]
            assert len(rows)==2 and rows['φVn kN'].nunique()==1 and rows['θ deg'].nunique()==1
    assert diagram['D/C value'].isna().all()


def test_zero_shear_still_has_a_source_qualified_diagram_capacity():
    state = ready_state(); source = _demand(x=10,vu=0,mux=500)
    checked = ap._beam_uls_shear_check_dataframe(state,source,strength_route=_route())
    assert checked.iloc[0]['Status']=='NO DEMAND'
    diagram = ap._beam_uls_igird_shear_diagram_capacity_dataframe(state,source,checked,strength_route=_route())
    assert diagram.iloc[0]['φVn kN']>0 and checked['φVn kN'].isna().all()
