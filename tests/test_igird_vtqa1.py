"""Development/source regressions and independent V/T equation benchmarks."""
import math
from copy import deepcopy

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.igird_combined_vt import DEVELOPMENT_KEY, development_settings
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_combined_vt import source_readiness_dataframe
from concrete_pmm_pro.ui.igird_vt_workspace import utilization_envelope, make_overview_figure, missing_bar_materials
from test_igird_uls7_concurrent_vt import ready_state, check, physical
from test_igird_uls6_torsion_general_procedure import _demand, _route


def test_missing_material_retains_known_failed_components_without_overall_certificate():
    state = ready_state()
    state['rebar_materials'] = []
    df = check(state, vu=1800, tu=1000)
    row = physical(df)
    assert row['Status'] == 'FAIL'
    assert row['Calculation status'] == 'PARTIAL'
    assert row['Transverse D/C value'] > 1
    assert math.isfinite(row['Stress D/C value'])
    assert math.isnan(row['Overall D/C value'])
    assert row['Longitudinal status'] == 'DATA REQUIRED'
    assert source_readiness_dataframe(df)['Required source / review'].str.contains('SD40').any()
    assert missing_bar_materials(state) == ['SD40']


def test_unresolved_material_has_no_inferred_elastic_stiffness():
    state = ready_state(); state['rebar_materials'] = []
    inp, _ = ap._beam_uls_flexure_analysis_input_for_station(state, row=_demand().iloc[0], strength_route=_route())
    terms = ap._beam_uls_igird_rebar_strain_terms(inp, tension_face='bottom')
    assert terms['EsAs_N'] == 0
    assert not terms['source_ready']
    assert terms['missing_materials'] == ['SD40']


def epsilon(state, *, x=1, already=False, factor=1):
    row = _demand(x=x, mux=1000, vu=200).iloc[0]
    inp, _ = ap._beam_uls_flexure_analysis_input_for_station(state, row=row, strength_route=_route())
    if already:
        inp = inp.model_copy(update={'rebars':[b.model_copy(update={'diameter_mm':b.diameter_mm*math.sqrt(factor)}) for b in inp.rebars]})
    return ap._beam_uls_igird_general_shear_epsilon(state, analysis_input=inp, x_m=x, span_length_m=20,
        tension_face='bottom', mux_kNm=1000, vu_kN=200, nu_compression_positive_kN=0,
        dv_mm=1200, ordinary_development_applied=already)


def test_unconfirmed_bars_get_zero_stiffness_and_no_final_shear_pass():
    state = ready_state(); state.pop(DEVELOPMENT_KEY)
    eps = epsilon(state, x=10)
    assert eps['ready'] and eps['As_mm2'] == 0
    assert not eps['ordinary_source_ready']
    df = ap._beam_uls_shear_check_dataframe(state, _demand(x=10, vu=100), strength_route=_route())
    assert not df['Status'].eq('PASS').any()


def test_partial_development_area_reduced_once_in_strain_equation():
    state = ready_state()
    state[DEVELOPMENT_KEY].update(left_end_anchored_confirmed=False, development_length_mm=2000)
    eps = epsilon(state)
    pre_reduced = epsilon(state, already=True, factor=.5)
    expected_as = 2*math.pi*20**2/4*.5
    expected_denom = expected_as*200000 + eps['EpAps_N']
    assert eps['As_mm2'] == pytest.approx(expected_as)
    assert eps['denominator_N'] == pytest.approx(expected_denom)
    assert pre_reduced['denominator_N'] == pytest.approx(expected_denom)
    expected_num = max(1000e6/1200,200e3)+200e3-eps['Aps_fpo_N']
    assert eps['epsilon_s_raw'] == pytest.approx(expected_num/expected_denom)


def test_accepted_flexure_development_is_reused_until_explicit_vt_source_exists():
    state = {'igird_flexure_development_settings':{'bars_continuous_confirmed':True,
        'left_bar_anchored':False,'right_bar_anchored':True,'bar_ld_mm':1700}}
    assert development_settings(state)['development_length_mm'] == 1700
    assert development_settings(state)['continuous_full_span_confirmed']
    state[DEVELOPMENT_KEY] = {'continuous_full_span_confirmed':False,'development_length_mm':2100}
    assert not development_settings(state)['continuous_full_span_confirmed']
    assert development_settings(state)['development_length_mm'] == 2100


def test_source_fc_design_limits_in_shear_torsion_and_combined():
    state = ready_state()
    state['concrete_material'] = state['concrete_material'].model_copy(update={'fc_MPa':120})
    demand = _demand(x=10, mux=1000, vu=200, tu=500)
    shear = ap._beam_uls_shear_check_dataframe(state, demand, strength_route=_route()).iloc[0]
    torsion = ap._beam_uls_torsion_check_dataframe(state, demand, strength_route=_route()).iloc[0]
    combined = physical(check(state,tu=500))
    assert shear["f'c MPa"] == pytest.approx(15*6.894757293168)
    assert torsion["f'c MPa"] == pytest.approx(10*6.894757293168)
    assert combined["f'c MPa"] == pytest.approx(10*6.894757293168)


@pytest.mark.parametrize('name,function', [('Shear',ap._beam_uls_shear_check_dataframe),
    ('Torsion',ap._beam_uls_torsion_check_dataframe),('Shear + Torsion',ap._beam_uls_combined_vt_check_dataframe)])
def test_reference_m2_v3_do_not_change_primary_numeric_results(name,function):
    state = ready_state(); demand = _demand(x=10,mux=1000,vu=200,tu=300)
    before = function(state,demand,strength_route=_route())
    demand['Muy'] = 100000.; demand['Vux'] = -90000.
    after = function(state,demand,strength_route=_route())
    columns = [c for c in before if c not in {'M2 reference kN-m','V3 reference kN'}]
    pd.testing.assert_frame_equal(before[columns],after[columns])


def test_nominal_vn_and_tn_match_us_unit_equations():
    state = ready_state(); demand = _demand(x=10,mux=1000,vu=500,tu=500)
    s = ap._beam_uls_shear_check_dataframe(state,demand,strength_route=_route()).iloc[0]
    t = ap._beam_uls_torsion_check_dataframe(state,demand,strength_route=_route()).iloc[0]
    ksi = 6.894757293168; inch = 25.4; kip = 4448.2216152605
    eps = max(0,min(.006,s['εs raw']))
    beta = 4.8/(1+750*eps)
    theta = 29+3500*eps
    bw = s['bw mm']/inch; dv = s['dv mm']/inch; fc = s["f'c MPa"]/ksi
    vc_kips = .0316*beta*math.sqrt(fc)*bw*dv
    avs_in = s['Av/s mm2/m']/1000/inch
    vs_kips = avs_in*(s['fy MPa']/ksi)*dv/math.tan(math.radians(theta))
    vn_kips = min(vc_kips+vs_kips,.25*fc*bw*dv)
    assert s['φVn kN'] == pytest.approx(s['φ']*vn_kips*kip/1000, rel=2e-10)
    tn_kipin = 2*(t['Ao mm2']/inch**2)*(t['At/s mm2/mm']/inch)*(t['fy MPa']/ksi)/math.tan(math.radians(29+3500*max(0,min(.006,t['εs raw']))))
    assert t['φTn kN-m'] == pytest.approx(t['φ']*tn_kipin*kip*inch/1e6,rel=2e-10)


def test_auto_depth_does_not_substitute_area_centroid_for_code_force_centroid():
    state = ready_state(); row = _demand().iloc[0]
    inp, _ = ap._beam_uls_flexure_analysis_input_for_station(state,row=row,strength_route=_route())
    depth = ap._beam_uls_effective_shear_depth_values_mm(state,inp,mux_kNm=1000,strength_route=_route())
    assert depth['dv_mm'] == pytest.approx(max(depth['C-T lever arm mm'],.9*depth['de mm'],.72*1820))
    assert depth['dv_mm'] > .72*1600
    assert '0.72h' in depth['dv_note']
    moved = inp.model_copy(update={'rebars':[b.model_copy(update={'y_mm':b.y_mm-50}) for b in inp.rebars]})
    assert ap._beam_uls_effective_shear_depth_values_mm(state,moved,mux_kNm=1000,strength_route=_route())['dv_mm'] == depth['dv_mm']
    manual_value = depth['dv lower bound mm']
    state['beam_girder_shear_depth_settings'] = {'mode':'Manual effective shear depth','dv_mm':manual_value,'note':'Verified conservative depth'}
    manual = ap._beam_uls_effective_shear_depth_values_mm(state,inp,mux_kNm=1000,strength_route=_route())
    assert manual['dv_mm'] == manual_value
    state['beam_girder_shear_depth_settings']['dv_mm'] = 2000
    assert math.isnan(ap._beam_uls_effective_shear_depth_values_mm(state,inp,mux_kNm=1000,strength_route=_route())['dv_mm'])
    demand = _demand(x=10,mux=1000,vu=200,tu=500)
    for function, column in [(ap._beam_uls_shear_check_dataframe,'φVn kN'),
            (ap._beam_uls_torsion_check_dataframe,'φTn kN-m'),
            (ap._beam_uls_combined_vt_check_dataframe,'Overall D/C value')]:
        frame = function(state,demand,strength_route=_route())
        assert frame[column].isna().all(), 'An invalid dv must not fall back to the area-centroid estimate'


def test_overview_maximizes_original_case_ratios_and_preserves_missing_gap():
    frame = pd.DataFrame([
        {'Governing x':'1 m','Case':'A','Status':'PASS','DC':100/200},
        {'Governing x':'1 m','Case':'B','Status':'PASS','DC':20/30},
        {'Governing x':'2 m','Case':'A','Status':'REVIEW','DC':float('nan')},
        {'Governing x':'3 m','Case':'B','Status':'FAIL','DC':float('inf')}])
    before = frame.copy(deep=True)
    e = utilization_envelope(frame,{'Strength':'DC'})
    assert e.iloc[0]['D/C'] == pytest.approx(20/30)
    assert e.iloc[0]['Case'] == 'B'
    assert math.isnan(e.iloc[1]['D/C'])
    assert math.isinf(e.iloc[2]['D/C'])
    pd.testing.assert_frame_equal(frame,before)


def test_combined_partial_overview_has_one_ratio_legend_and_honest_missingness():
    active = _demand(x=10,tu=200)
    frame = pd.DataFrame([{'Governing x':'10 m','Case':'A','Status':'REVIEW',
        'Transverse D/C value':.7,'Stress D/C value':.2,'Longitudinal D/C value':float('nan')}])
    fig = make_overview_figure(active,frame,check_name='Shear + Torsion',code_label='AASHTO LRFD',span_m=20)
    assert [t.name for t in fig.data if t.showlegend is not False] == ['Max D/C','Limit = 1.0']
    assert fig.data[0].y[0] == .7
    assert not fig.data[0].connectgaps
    assert tuple(fig.layout.xaxis.range) == (0,20)
