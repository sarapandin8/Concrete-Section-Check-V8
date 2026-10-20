"""Independent hand checks, axis isolation, and exclusion regressions."""
from copy import deepcopy
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis import slab_aashto62 as code
from concrete_pmm_pro.analysis import slab_shell56 as legacy
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED, END_REASON
from concrete_pmm_pro.io.slab_shell_import import BANK_KEY
from concrete_pmm_pro.visualization.slab_shell56 import element_envelope, plan_figure
from test_slab_shell56 import steel, model_state
from test_slab_endzone60 import end_state


def shear(n=0.,m=10.,v=50.,*,h=350.,reinforcement=None,top=0,bottom=1):
    return code.directional_shear(np.array([h]),np.array([n]),np.array([m]),np.array([v]),reinforcement or steel(),top,bottom)


def test_simplified_si_strength_matches_direct_us_customary_hand_calculation():
    r=shear()
    dv=.9*(350-64)
    # US source equation: fc=35/6.894757293 ksi, b=1000/25.4 in.
    vc_kip=.0316*2*np.sqrt(35/6.894757293)*(1000/25.4)*(dv/25.4)
    capacity=.9*vc_kip*4.4482216152605
    assert r['phiVn (kN/m)'][0]==pytest.approx(capacity,rel=1e-9)
    assert r['shear D/C'][0]==pytest.approx(50/capacity,rel=1e-9)
    assert r['beta'][0]==2 and r['theta (deg)'][0]==45


def test_general_uses_matching_tension_mat_strain_and_qualified_layer_spacing():
    s=steel(area=1340.4128655)
    r=shear(n=50,m=-20,v=30,reinforcement=s,top=2,bottom=3)
    dv=.9*(350-48)
    eps=(max(20000/dv,30)+25+30)/(200000*1340.4128655/1000)
    sx=min(dv,350-48-48)
    sxe=np.clip(sx*1.38/.63,304.8,2032.)
    beta=4.8/(1+750*eps)*51/(39+sxe/25.4)
    assert r['tension mat'][0]=='Top'
    assert r['strain used'][0]==pytest.approx(eps)
    assert r['sx (mm)'][0]==pytest.approx(sx)
    assert r['beta'][0]==pytest.approx(beta)
    assert r['theta (deg)'][0]==pytest.approx(29+3500*eps)


def test_rank1057_longitudinal_is_not_reclassified_by_transverse_axial_tension():
    s=steel();s.area[0]=1005.3096491487337;s.area[1:]=1340.412865531645
    rows=pd.DataFrame([{'Thickness (mm)':312.5,'Nx':-853.25,'Ny':47.31,'Nxy':99.88,
        'Mx':5.2954,'My':-11.8968,'Mxy':-8.0155,'Vx':-104.51,'Vy':11.28}])
    r=code.section_checks(rows,s).iloc[0]
    assert r['Longitudinal beta']==2
    assert r['Longitudinal shear D/C']==pytest.approx(104.51/198.808807095,rel=1e-8)
    assert r['Transverse procedure'].endswith('general')
    assert r['Transverse shear D/C']<.1
    assert r['Shell coupling status']=='REVIEW' and r['Design acceptance']=='REVIEW REQUIRED'


def test_directional_checks_do_not_borrow_orthogonal_actions_or_reinforcement():
    s=steel()
    rows=pd.DataFrame([dict(zip(['Thickness (mm)','Nx','Ny','Nxy','Mx','My','Mxy','Vx','Vy'],
                               [350,-200,50,20,25,-10,8,80,20]))])
    first=code.section_checks(rows,s)
    changed=rows.copy();changed.loc[0,['Ny','My','Vy']]=[5000,-1000,-9000]
    second=code.section_checks(changed,s)
    l=[c for c in first if c.startswith('Longitudinal ')]
    pd.testing.assert_frame_equal(first[l],second[l])
    changed_steel=deepcopy(s);changed_steel.area[2:]*=2
    third=code.section_checks(rows,changed_steel)
    pd.testing.assert_frame_equal(first[l],third[l])


def test_zero_moment_uses_smaller_mat_and_negative_moment_uses_top_mat():
    s=steel();s.area[0]=700;s.area[1]=1600
    assert shear(m=0,reinforcement=s)['As tension (mm²/m)'][0]==700
    assert shear(m=-10,reinforcement=s)['As tension (mm²/m)'][0]==700
    assert shear(m=10,reinforcement=s)['As tension (mm²/m)'][0]==1600


def test_excess_general_strain_remains_unknown_not_capped_to_a_pass():
    r=shear(n=3000,m=100,v=50)
    assert r['strain used'][0]>.006
    assert np.isnan(r['shear D/C'][0]) and r['shear status'][0]=='REVIEW'
    assert np.isnan(r['Vn (kN/m)'][0]) and np.isnan(r['tie D/C'][0])


def test_cracked_all_tension_section_doubles_strain_and_aggregate_is_not_guessed():
    r=shear(n=600,m=0,v=10)
    assert r['both faces tension'][0]
    assert r['strain raw'][0]==pytest.approx(2*(10+300+10)/200000.)
    assert r['sxe (mm)'][0]>=304.8


def test_longitudinal_shear_tie_uses_code_tension_side_and_us_phi_factors():
    r=shear(n=-20,m=-30,v=40)
    demand=max(0,30000/(.9*257.4)-20/(2*.75)+40/.9)
    assert r['tie required (kN/m)'][0]==pytest.approx(demand)
    assert r['tie D/C'][0]==pytest.approx(demand/(1000*390/1000))


@pytest.mark.parametrize('moment',[30.,-30.])
def test_pure_bending_nm_matches_independent_strain_compatible_equilibrium(moment):
    s=steel();h=350.;alpha=.85;fc=35.;beta=.85-.05*(35/6.894757293-4)
    # The neutral axis is shallower than the top bars: BOTH mats are in
    # tension at ultimate. Independently verify they both yield, then C=2Asfy.
    a=2*1000*390/(alpha*fc*1000)
    assert .003*(64/(a/beta)-1)>390/200000
    mr=.9*2*1000*390*(h/2-a/2)/1e6
    r=code.nm_ratios(np.array([h]),np.array([0.]),np.array([moment]),s,0,1)
    assert r[0,0]==pytest.approx(abs(moment)/mr,rel=.001)
    assert r[0,4]==pytest.approx(.9)
    assert r[0,3]==pytest.approx(a/beta,rel=.01)


def test_pure_tension_is_two_mats_and_nm_scales_on_the_same_load_ray():
    s=steel()
    r=code.nm_ratios(np.array([350.,350.,350.]),np.array([100.,0.,200.]),np.array([0.,0.,0.]),s,0,1)
    assert r[0,0]==pytest.approx(100/(.9*2*1000*390/1000),rel=1e-5)
    assert r[1,0]==0 and r[2,0]==pytest.approx(2*r[0,0])


def test_nm_signed_load_scaling_and_symmetry_and_discrete_curve_convergence():
    s=steel();h=350.
    r=code.nm_ratios(np.full(4,h),np.array([-300,-600,-300,-300]),np.array([40,80,-40,0]),s,0,1)
    assert r[1,0]==pytest.approx(2*r[0,0])
    assert r[2,0]==pytest.approx(r[0,0])
    fine=code.nm_curve(h,s,0,1,points=640)
    with patch.object(code,'nm_curve',return_value=fine):
        rf=code.nm_ratios(np.full(4,h),np.array([-300,-600,-300,-300]),np.array([40,80,-40,0]),s,0,1)
    np.testing.assert_allclose(r[:,0],rf[:,0],rtol=.002)


def test_current_source_exclusions_keep_raw_actions_and_never_solve_omitted_records():
    state=end_state();source=state[BANK_KEY].tables['forces'].copy(deep=True)
    with patch.object(code,'section_checks',wraps=code.section_checks) as solver:
        r=code.calculate(state)
    assert r['source_rows']==64 and r['geometry_excluded_rows']==48 and r['design_rows']==16
    assert len(solver.call_args.args[0])==16
    omitted=r['rows'].loc[~r['rows'][INCLUDED]]
    assert omitted[[c for c,_ in code.VIEWS.values()]].isna().all().all()
    assert omitted['Section status'].eq('EXCLUDED').all()
    pd.testing.assert_frame_equal(source,state[BANK_KEY].tables['forces'])
    # Changing omitted forces cannot change any retained directional check.
    other=deepcopy(state);ids=set(omitted.Joint)
    other[BANK_KEY].tables['forces'].loc[lambda f:f.Joint.isin(ids),['F11','F22','F12','M11','M22','M12','V13','V23']]=1e12
    pd.testing.assert_frame_equal(r['summary'],code.calculate(other)['summary'])


def test_result_fingerprint_is_input_only_and_no_other_solver_runs():
    state=model_state()
    with patch.object(legacy,'calculate',side_effect=AssertionError('research solver must not run')):
        result=code.calculate(state)
    state[code.RESULT_KEY]=result
    assert code.current(state) is result
    state['slab_shell55_aashto62_view']='Shear · longitudinal'
    assert code.current(state) is result
    state['section_parameters']['deck_long_rebar_top_spacing_mm']=200.
    assert code.current(state) is None


def test_plan_full_geometry_exclusions_and_all_case_coverage_are_retained():
    r=code.calculate(end_state())
    adapter=code.map_adapter(r,'Shear · transverse')
    selected=element_envelope(adapter)
    assert not selected['Map incomplete'].any()
    assert len(selected)==len(r['geometry'].elements)
    fig=plan_figure(adapter)
    assert any(t.name=='Excluded end zones' for t in fig.data)
    gov=next(t for t in fig.data if t.name.startswith('Gov.'))
    assert gov.x[0]==1.


def test_incomplete_source_is_review_and_unknown_shear_cannot_appear_passed():
    state=model_state();state[BANK_KEY].tables['forces']=state[BANK_KEY].tables['forces'].iloc[1:].copy()
    r=code.calculate(state)
    assert r['incomplete'] and not r['summary'].Status.eq('PASS').any()
    env=element_envelope(code.map_adapter(r,'Shear · transverse'))
    assert env['Map incomplete'].any()


def test_missing_girder_connectivity_cannot_silently_disable_agreed_exclusions():
    state=end_state()
    state[BANK_KEY].tables.pop('frames')
    with pytest.raises(ValueError,match='Agreed connection exclusions'):
        code.calculate(state)
