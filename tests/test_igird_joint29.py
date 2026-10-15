"""Independent closed-form limits, shared steel, scope and UI isolation."""
from copy import deepcopy
import json
import math
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import igird_dowel_joint as joint
from concrete_pmm_pro.analysis.igird_interface_connectors import at_station
from concrete_pmm_pro.io.project_io import project_from_json, project_from_session_state, project_to_json, apply_project_to_session_state
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_dowel_joint import CACHE_KEY
from test_igird_dowel28 import settings, zone
from test_igird_uls4_interface_integration import _state, _demand, _route


AVF=2*math.pi*12**2/4*1000/150
STEEL=.9*AVF*390/1000


def cfg(**changes):
    return {"mode":joint.MODE,"coating":"uncoated","anchorage_region":"interior",
        "row_spacing_mm":200.,"slab_ldh_available_mm":250.,"hook_tail_mm":180.,
        "hook_inside_bend_mm":72.,"cover_required_mm":50.,"girder_ld_available_mm":900.,
        "action_rows":[],**changes}


def context(**changes):
    return {"normal_weight":True,"fc_slab_MPa":35.,"fc_girder_MPa":45.,
        "slab_thickness_mm":350.,"girder_depth_mm":1500.,"width_mm":600.,
        "girder_polygon":[[-300,0],[300,0],[300,1500],[-300,1500]],
        "contact_center_x_mm":0.,"contact_top_y_mm":1500.,
        "surface_key":"roughened_girder_slab","start_m":0.,"end_m":20.,**changes}


def action(**changes):
    return {"Case":"Known joint state","Station x (m)":10.,"qx_kN_per_m":100.,
        "qy_kN_per_m":0.,"n_kN_per_m":100.,"mx_kNm_per_m":0.,
        "Source":"Independent interface free-body F1",**changes}


def selected_zone(record=None):
    return at_station(settings([zone() if record is None else record]),x_m=10.)["zone"]


def solve(**changes):
    inputs={"width_mm":600.,"leg_spacing_mm":200.,"avf_mm2_per_m":AVF,
        "fy_MPa":390.,"fc_weaker_MPa":35.,"surface_key":"roughened_girder_slab",
        "qx_kN_per_m":100.,"qy_kN_per_m":0.,"n_kN_per_m":0.,"mx_kNm_per_m":0.,**changes}
    return joint.solve_mechanism(**inputs)


def test_development_lengths_match_independent_us_customary_calculation():
    r=joint.development_requirements(db_mm=12,fy_MPa=390,fc_slab_MPa=35,fc_girder_MPa=45,coating='uncoated')
    assert r['hook_required_mm']==pytest.approx(190.80277454783032)
    assert r['straight_required_mm']==pytest.approx(637.6631885238107)
    assert r['tail_required_mm']==144 and r['bend_required_mm']==72
    epoxy=joint.development_requirements(db_mm=12,fy_MPa=390,fc_slab_MPa=35,fc_girder_MPa=45,coating='epoxy')
    assert epoxy['hook_required_mm']==pytest.approx(1.2*r['hook_required_mm'])
    assert epoxy['straight_required_mm']==pytest.approx(1.5*r['straight_required_mm'])


def test_minimum_lengths_and_large_general_bend():
    small=joint.development_requirements(db_mm=6,fy_MPa=200,fc_slab_MPa=60,fc_girder_MPa=60,coating='uncoated')
    assert small['hook_required_mm']==pytest.approx(152.4) and small['straight_required_mm']==pytest.approx(304.8)
    large=joint.development_requirements(db_mm=32,fy_MPa=490,fc_slab_MPa=35,fc_girder_MPa=45,coating='uncoated')
    assert large['bend_required_mm']==256


@pytest.mark.parametrize('change',[{'db_mm':36},{'fy_MPa':530},{'fc_slab_MPa':70},{'coating':'unknown'},{'fy_MPa':True}])
def test_unimplemented_or_invalid_anchorage_route_does_not_produce_lengths(change):
    with pytest.raises(ValueError):
        joint.development_requirements(**{'db_mm':12,'fy_MPa':390,'fc_slab_MPa':35,'fc_girder_MPa':45,'coating':'uncoated',**change})


@pytest.mark.parametrize('change',[
    {'slab_ldh_available_mm':None},{'slab_ldh_available_mm':150},
    {'hook_tail_mm':130},{'hook_inside_bend_mm':48},{'girder_ld_available_mm':600},
    {'girder_ld_available_mm':1490},{'anchorage_region':'discontinuous_end'},
])
def test_partial_or_inadequate_anchorage_never_credits_the_mechanism(change):
    r=joint.evaluate(cfg(**change),selected_zone(),context(),action(),declared_anchored=True)
    assert r['status']=='REVIEW' and not r['mechanism'] and r['reasons']


def test_cover_fit_uses_slab_thickness_and_not_projection_plus_tail():
    r=joint.anchorage(cfg(hook_tail_mm=500),selected_zone(),context(slab_thickness_mm=250))
    assert r['status']=='FAIL' and not r['checks']['slab_hook_cover']['adequate']
    assert r['checks']['slab_ldh_available_mm']['adequate']
    assert joint.anchorage(cfg(),selected_zone(),context())['ready']


def test_bonded_leg_path_checks_the_narrow_web_not_just_the_top_flange():
    polygon=[[-300,0],[300,0],[300,150],[100,300],[100,1200],[300,1350],
             [300,1500],[-300,1500],[-300,1350],[-100,1200],[-100,300],[-300,150]]
    bad=joint.anchorage(cfg(row_spacing_mm=200),selected_zone(),context(girder_polygon=polygon))
    good=joint.anchorage(cfg(row_spacing_mm=80),selected_zone(),context(girder_polygon=polygon))
    assert not bad['ready'] and bad['status']=='FAIL'
    assert bad['checks']['bonded_leg_concrete_cover']['available_mm']==pytest.approx(0.)
    assert good['ready'] and good['checks']['bonded_leg_concrete_cover']['available_mm']==pytest.approx(60.)


def test_internal_void_and_unknown_polygon_cannot_be_ignored_for_anchorage():
    holes=[[[90,800],[110,800],[110,1000],[90,1000]]]
    for ctx in (context(girder_holes=holes),context(girder_polygon=[])):
        assert not joint.anchorage(cfg(),selected_zone(),ctx)['ready']


def test_legacy_declaration_does_not_replace_measured_anchorage_or_density():
    for conf,ctx in [(cfg(hook_tail_mm=None),context()),(cfg(),context(normal_weight=False))]:
        r=joint.evaluate(conf,selected_zone(),ctx,action(),declared_anchored=True)
        assert r['status']=='REVIEW' and not r['mechanism']
    assert not joint.evaluate(cfg(),selected_zone(),context(),action(),declared_anchored=False)['mechanism']


def test_pure_shear_is_exact_zero_cohesion_shear_friction_limit():
    r=solve()
    assert r['ready'] and r['capacity_factor']==pytest.approx(STEEL/100)
    assert r['cohesion_MPa']==0 and r['contact_kN_per_m']==pytest.approx(STEEL)


def test_pure_opening_and_joint_shear_share_one_steel_supply():
    opening=solve(qx_kN_per_m=0,n_kN_per_m=100)
    combined=solve(n_kN_per_m=100)
    assert opening['capacity_factor']==pytest.approx(STEEL/100)
    # From N+V/mu <= phi As fy, not independent N and V capacities.
    assert combined['capacity_factor']==pytest.approx(STEEL/(100+100))
    assert combined['capacity_factor']==pytest.approx(.5*opening['capacity_factor'])
    assert sum(combined['tie_forces_kN_per_m'])==pytest.approx(STEEL)


def test_normal_compression_is_not_silently_credited_as_permanent_clamping():
    r=solve(n_kN_per_m=-100)
    assert r['capacity_factor']==pytest.approx(STEEL/100)
    assert r['contact_kN_per_m']>sum(r['tie_forces_kN_per_m'])
    assert r['friction_kN_per_m']<=sum(r['tie_forces_kN_per_m'])+1e-7


def test_roll_limit_is_below_independent_continuous_pressure_block_solution():
    # Both ties fully yielded; compression block lies outside both ties.
    # M = T*b/2 - T^2/(2*p), p=phi_bearing*0.85fc kN/mm per metre.
    exact=(STEEL*600/2-STEEL**2/(2*(.70*.85*35)))/1000
    values=[solve(qx_kN_per_m=0,mx_kNm_per_m=100,cells=k)['capacity_factor']*100 for k in (32,64,128)]
    assert values[0]<=values[1]+1e-8<=values[2]+1e-8<=exact+1e-8
    assert (exact-values[-1])/exact<.001


def test_signed_roll_mirror_and_transverse_shear_vector():
    plus=solve(qx_kN_per_m=30,qy_kN_per_m=40,n_kN_per_m=20,mx_kNm_per_m=40)
    minus=solve(qx_kN_per_m=-30,qy_kN_per_m=-40,n_kN_per_m=20,mx_kNm_per_m=-40)
    assert plus['capacity_factor']==pytest.approx(minus['capacity_factor'])
    assert plus['tie_forces_kN_per_m']==pytest.approx(minus['tie_forces_kN_per_m'][::-1])
    assert plus['friction_kN_per_m']==pytest.approx(50*plus['capacity_factor'])
    assert plus['normal_reconstructed_kN_per_m']==pytest.approx(20*plus['capacity_factor'])
    assert plus['roll_reconstructed_kNm_per_m']==pytest.approx(40*plus['capacity_factor'])
    assert plus['equilibrium_residual']<1e-6 and plus['yield_constraint_violation']<1e-6


def test_known_failure_is_visible_without_promoting_model_to_full_design_pass():
    r=joint.evaluate(cfg(),selected_zone(),context(),action(qx_kN_per_m=1000),declared_anchored=True)
    assert r['status']=='REVIEW'
    assert r['mechanism']['mechanism']=='EXCEEDS IDEALIZED MECHANISM'
    assert r['mechanism']['utilization']>1


def test_zero_actions_remain_scoped_and_unknown_actions_are_not_zero():
    zero=joint.evaluate(cfg(),selected_zone(),context(),action(qx_kN_per_m=0,n_kN_per_m=0),declared_anchored=True)
    assert zero['status']=='REVIEW' and zero['mechanism']['utilization']==0
    for key in ('qy_kN_per_m','n_kN_per_m','mx_kNm_per_m','Source'):
        r=joint.evaluate(cfg(),selected_zone(),context(),action(**{key:None}),declared_anchored=True)
        assert not r['mechanism'] and r['reasons']


def test_source_declaration_and_physical_domain_are_required():
    for changes in ({'Source':''},{'Case':None},{'Station x (m)':21}):
        r=joint.evaluate(cfg(),selected_zone(),context(),action(**changes),declared_anchored=True)
        assert not r['mechanism'] and r['status']=='REVIEW'
    four=selected_zone();four['Legs']=4
    r=joint.evaluate(cfg(),four,context(),action(),declared_anchored=True)
    assert not r['mechanism'] and any('exactly two' in s for s in r['reasons'])


def test_solver_failure_is_a_review_without_an_unverified_numeric_capacity():
    from types import SimpleNamespace
    with patch('scipy.optimize.linprog',return_value=SimpleNamespace(success=False,status=4,x=None,message='QA numerical failure')):
        r=solve()
    assert not r['ready'] and 'capacity_factor' not in r


@pytest.mark.parametrize('label',['ACI 318-19','AASHTO LRFD 2024','AASHTO unspecified'])
def test_other_code_editions_are_not_silently_treated_as_the_2020_route(label):
    r=ap._igird_dowel_joint_review({},settings(),code_label=label)
    assert r['rows'][0]['Status']=='REVIEW' and not r['traces']


@pytest.mark.parametrize('changes',[{'leg_spacing_mm':600},{'qx_kN_per_m':None},{'surface_key':'unknown'},{'cells':4}])
def test_invalid_mechanism_inputs_are_rejected(changes):
    with pytest.raises(ValueError):solve(**changes)


def test_a_boundary_evaluates_both_diameters_without_summing_or_avf_only_selection():
    conf=settings([zone(0,10,70),zone(10,20,200,Diameter_mm=20)])
    conf[joint.KEY]=cfg(action_rows=[action()])
    ctx=context(girder_zone=zone())
    original=deepcopy((conf,ctx))
    r=joint.build_review(conf,context_for_station=lambda x:ctx,base_context=ctx,girder_zones=[])
    assert len(r['rows'])==2
    assert r['rows'][0]['Anchorage']=='DIMENSION CHECKS MET'
    assert r['rows'][1]['Anchorage']=='FAIL'
    assert all(row['Status']=='REVIEW' for row in r['rows'])
    assert (conf,ctx)==original and 'girder_zone' in ctx


def test_no_interface_actions_or_unknown_ranges_never_infer_from_girder_torque():
    conf=settings([zone(x_start_m=None,x_end_m=None)])
    conf[joint.KEY]=cfg()
    ctx=context()
    r=joint.build_review(conf,context_for_station=lambda x:ctx,base_context=ctx,girder_zones=[])
    assert r['missing_actions'] and not r['rows']
    conf[joint.KEY]['action_rows']=[action()]
    r=joint.build_review(conf,context_for_station=lambda x:ctx,base_context=ctx,girder_zones=[])
    assert r['rows'][0]['Status']=='REVIEW' and not r['traces'][0]['result']['mechanism']
    assert 'no I-stirrup fallback' in r['rows'][0]['Reason']


def test_joint_inputs_roundtrip_without_persisting_solver_witness():
    state=_state();conf=settings();conf[joint.KEY]=cfg(action_rows=[action(mx_kNm_per_m=None)])
    state['project_metadata']={ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY:conf}
    state[CACHE_KEY]={'result':{'sentinel':'NEVER PERSIST WITNESS'}}
    payload=project_to_json(project_from_session_state(state))
    assert 'NEVER PERSIST WITNESS' not in payload
    restored={};apply_project_to_session_state(project_from_json(payload),restored)
    assert ap._igird_interface_shear_settings_from_state(restored)==conf
    assert restored['project_metadata'][ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY][joint.KEY]['action_rows'][0]['mx_kNm_per_m'] is None


def test_preview_input_changes_do_not_clear_or_rehash_production_uls_results():
    state=_state();conf=settings();conf[joint.KEY]=cfg()
    state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY]=conf
    state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]={'sentinel':'production'}
    state[CACHE_KEY]={'sentinel':'old joint preview'}
    before=ap._igird_interface_shear_hash(state,_demand(),settings=conf,strength_route=_route())
    changed=deepcopy(conf);changed[joint.KEY]['hook_tail_mm']=250
    with patch.object(ap.st,'session_state',state):ap._igird_store_interface_shear_settings(changed)
    after=ap._igird_interface_shear_hash(state,_demand(),settings=changed,strength_route=_route())
    assert before==after
    assert state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]=={'sentinel':'production'}
    assert CACHE_KEY not in state


def test_ui_new_inputs_persist_once_with_no_new_confirmation_checkbox():
    conf=settings();conf[joint.KEY]=cfg(slab_ldh_available_mm=None,action_rows=[action(mx_kNm_per_m=None)])
    script="""
import streamlit as st
from concrete_pmm_pro.ui import analysis_page as ap
from test_igird_uls4_interface_integration import _state
if 'initialized' not in st.session_state:
    st.session_state.update(_state())
    st.session_state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY]=CONF
    st.session_state['initialized']=True
ap._igird_render_interface_shear_settings(st.session_state)
""".replace('CONF',repr(conf))
    app=AppTest.from_string(script,default_timeout=60).run()
    assert not app.exception and len(app.checkbox)==1
    saved=deepcopy(app.session_state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY])
    assert saved[joint.KEY]['slab_ldh_available_mm'] is None
    assert saved[joint.KEY]['action_rows'][0]['mx_kNm_per_m'] is None
    app.run();assert not app.exception
    assert app.session_state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY]==saved


def test_review_button_is_the_only_solver_trigger_and_stale_results_are_hidden():
    conf=settings();conf[joint.KEY]=cfg()
    script="""
import streamlit as st
from concrete_pmm_pro.ui.igird_dowel_joint import render_analysis
def calculate():
    st.session_state['runs']=st.session_state.get('runs',0)+1
    return {'requirements':[],'missing_actions':True,'rows':[],'traces':[]}
render_analysis(CONF,fingerprint=str(st.session_state.get('revision',0)),calculate=calculate)
""".replace('CONF',repr(conf))
    app=AppTest.from_string(script,default_timeout=60).run()
    assert not app.exception and 'runs' not in app.session_state
    app.button[0].click().run();assert not app.exception and app.session_state['runs']==1
    app.run();assert app.session_state['runs']==1
    app.session_state['revision']=1;app.run()
    assert app.session_state['runs']==1
    assert any('not calculated' in e.value for e in app.info)
