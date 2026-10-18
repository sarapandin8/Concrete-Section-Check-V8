"""Independent equilibrium limits and safe integration, not structural validation."""
from dataclasses import replace
from copy import deepcopy
from unittest.mock import patch, MagicMock
import math

import pytest

from concrete_pmm_pro.analysis import igird_composite_steel45 as e
from concrete_pmm_pro.ui import igird_composite_steel45 as ui


def supplies(**changes):
    s=e.Supplies(core_ao_mm2=200000.,core_ph_mm=3000.,core_dv_mm=1000.,core_leg_N_per_mm=100.,
        u_ao_mm2=100000.,u_ph_mm=2400.,u_dv_mm=1000.,u_leg_N_per_mm=100.,slab_closing_N_per_mm=1000.,
        bottom_longitudinal_N=1e8,top_longitudinal_N=2e8,top_girder_longitudinal_N=1e8,top_slab_longitudinal_N=1e8,
        diagonal_q_N_per_mm=1e5,contact_width_mm=600.,u_leg_spacing_mm=100.,contact_MPa=1000.,
        interface_MPa=1000.,mu=1.,cot_theta=1.)
    s=replace(s,**changes)
    return replace(s,top_longitudinal_N=s.top_girder_longitudinal_N+s.top_slab_longitudinal_N)


def test_two_physical_paths_use_distinct_areas_and_one_leg_in_each_torsion_term():
    s=supplies()
    r=e.calculate(s,vu_N=100000.,tu_Nmm=10e6,mu_Nmm=0.,nu_tension_N=0.)
    assert r['model_Vn_kN']==pytest.approx(2*1000*(100+100)/1000)
    assert r['model_Tn_kNm']==pytest.approx((2*200000*100+2*100000*100)/1e6)
    assert r['T']['core_T_Nmm']==pytest.approx(40e6)
    assert r['T']['U_T_Nmm']==pytest.approx(20e6)
    # A 2*At U-leg-area shortcut would incorrectly double the U contribution.
    assert r['model_Tn_kNm'] < 80.


def test_removing_u_preserves_core_and_cannot_use_disconnected_slab_steel():
    s=supplies(u_leg_N_per_mm=0.,top_girder_longitudinal_N=100000.,top_slab_longitudinal_N=1e8)
    r=e.solve(s,vu_N=0.,tu_Nmm=1e6)
    expected_q=min(100.,100000/(.45*3000))
    assert r['capacity_factor']==pytest.approx(2*200000*expected_q/1e6)
    assert r['U_T_Nmm']==pytest.approx(0.)
    assert e.solve(s,vu_N=1000.,tu_Nmm=0.)['capacity_factor']>0


def test_slab_longitudinal_pool_limits_only_connected_u_path():
    r=e.solve(supplies(top_slab_longitudinal_N=10000.),vu_N=0.,tu_Nmm=1e6)
    q_u=10000/(.45*2400)
    assert r['U_T_Nmm']==pytest.approx(2*100000*q_u)
    assert 'U-path slab longitudinal steel' in r['active_limits']
    none=e.solve(supplies(top_slab_longitudinal_N=0.),vu_N=0.,tu_Nmm=1e6)
    assert none['capacity_factor']==pytest.approx(40.)
    assert none['U_T_Nmm']==pytest.approx(0.)


def test_combined_v_t_cannot_spend_independent_full_intercepts():
    s=supplies(u_ao_mm2=200000.)
    r=e.solve(s,vu_N=400000.,tu_Nmm=80e6)
    assert r['capacity_factor']==pytest.approx(.5)
    assert r['utilization']==pytest.approx(2.)
    assert sum(r['U_force_each_N_per_mm'])<=200.+1e-6


def test_shared_concrete_is_counted_once_across_overlapping_paths():
    s=supplies(diagonal_q_N_per_mm=150.)
    r=e.solve(s,vu_N=0.,tu_Nmm=1e6)
    assert r['capacity_factor']==pytest.approx(50.)
    q=r['core_T_Nmm']/(2*s.core_ao_mm2)+r['U_T_Nmm']/(2*s.u_ao_mm2)
    assert q==pytest.approx(150.)
    assert 'shared concrete flow budget' in r['active_limits']


def test_signed_torque_retains_interface_couple_and_equilibrium_witness():
    s=supplies(core_leg_N_per_mm=0.)
    r=e.solve(s,vu_N=0.,tu_Nmm=-1e6)
    q=r['U_T_Nmm']/(2*s.u_ao_mm2)
    assert sum(r['contact_qx_N_per_mm'])==pytest.approx(0.,abs=1e-7)
    assert -sum(y*f for y,f in zip(r['contact_y_mm'],r['contact_qx_N_per_mm']))==pytest.approx(s.u_leg_spacing_mm*q)
    assert all(abs(f)<=s.mu*c+1e-7 for f,c in zip(r['contact_qx_N_per_mm'],r['contact_compression_N_per_mm']))
    assert max(r['checks'].values())<2e-7
    positive=e.solve(s,vu_N=0.,tu_Nmm=1e6)
    assert positive['capacity_factor']==pytest.approx(r['capacity_factor'])


def test_less_contact_friction_reduces_both_v_and_t_using_same_u_ties():
    s=supplies(core_leg_N_per_mm=0.,mu=.01)
    weak=e.calculate(s,vu_N=100000.,tu_Nmm=10e6,mu_Nmm=0.,nu_tension_N=0.)
    strong=e.calculate(replace(s,mu=1.),vu_N=100000.,tu_Nmm=10e6,mu_Nmm=0.,nu_tension_N=0.)
    assert weak['model_Vn_kN']<strong['model_Vn_kN']
    assert weak['model_Tn_kNm']<strong['model_Tn_kNm']
    assert weak['model_VT_factor']<strong['model_VT_factor']


@pytest.mark.parametrize('field',['u_leg_N_per_mm','slab_closing_N_per_mm','top_slab_longitudinal_N'])
def test_more_of_a_physical_supply_cannot_reduce_the_same_model_capacity(field):
    s=supplies(**{field:50.})
    weak=e.solve(s,vu_N=100000.,tu_Nmm=20e6)
    changed=replace(s,**{field:1000.})
    changed=replace(changed,top_longitudinal_N=changed.top_girder_longitudinal_N+changed.top_slab_longitudinal_N)
    strong=e.solve(changed,vu_N=100000.,tu_Nmm=20e6)
    assert strong['capacity_factor']>=weak['capacity_factor']-1e-8


@pytest.mark.parametrize('bad',[None,float('nan'),float('inf'),True])
def test_unknown_actions_cannot_become_zero_or_pass(bad):
    with pytest.raises((ValueError,TypeError)):
        e.solve(supplies(),vu_N=bad,tu_Nmm=1e6)


def test_zero_supply_is_not_missing_and_no_result_can_issue_production_pass():
    s=supplies(core_leg_N_per_mm=0.,u_leg_N_per_mm=0.)
    r=e.calculate(s,vu_N=100000.,tu_Nmm=1e6,mu_Nmm=0.,nu_tension_N=0.)
    assert r['model_Vn_kN']==pytest.approx(0.)
    assert r['model_Tn_kNm']==pytest.approx(0.)
    for key in ('accepted_Vn_kN','accepted_Tn_kNm','accepted_VT_factor'):assert r[key] is None
    assert r['production_status']=='UNVALIDATED — REVIEW'


def test_render_never_recalculates_and_uses_current_stored_values():
    snapshot={'enabled':True,'rows':[],'reason':'No matching source'}
    before=deepcopy(snapshot)
    with patch('streamlit.markdown'),patch('streamlit.warning'),patch('streamlit.caption'),patch('streamlit.info'),\
         patch('streamlit.expander',return_value=MagicMock()),patch('streamlit.latex'),\
         patch.object(e,'calculate',side_effect=AssertionError('Render must not solve')):
        ui.render(snapshot)
    assert snapshot==before


def test_review_is_detached_before_production_cache_and_only_current_hash_can_read_it():
    state={}; result={'core_result':123,ui.KEY:{'enabled':True,'rows':[]}}
    before=deepcopy(result)
    clean=ui.detach_review(state,result,fingerprint='current')
    assert ui.KEY not in clean and clean['core_result']==123
    assert result==before
    assert ui.current(state,'current')==result[ui.KEY]
    assert ui.current(state,'stale') is None
    assert 'project_metadata' not in state
