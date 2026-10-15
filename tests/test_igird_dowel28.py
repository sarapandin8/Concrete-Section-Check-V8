"""Crossing steel is selected by physical connector source, never summed."""
from copy import deepcopy
import json
import math
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.analysis.igird_interface_connectors import (
    STIRRUPS, LINKED_DOWELS, INDEPENDENT_DOWELS, at_station, copy_girder_zoning,
)
from concrete_pmm_pro.io.project_io import (
    project_from_json, project_from_session_state, project_to_json, apply_project_to_session_state,
)
from concrete_pmm_pro.ui import analysis_page as ap
from test_igird_uls4_interface_integration import _state, _demand, _route


def zone(start=0.,end=20.,spacing=150.,**changes):
    return {"Zone":"Dowel", "x_start_m":start,"x_end_m":end,"Diameter_mm":12.,
        "Legs":2,"Spacing_mm":spacing,"fy_MPa":390.,**changes}


def settings(rows=None,**changes):
    return {"surface_key":"roughened_girder_slab","width_mode":"Auto — I-Girder top flange B1",
        "bvi_override_mm":None,"stirrups_cross_and_anchored":False,"connectors_cross_and_anchored":True,
        "connector_source":INDEPENDENT_DOWELS,"dowel_crossing_legs":2,
        "dowel_zones":[zone()] if rows is None else rows,**changes}


@pytest.mark.parametrize("spacing,expected",[(70,3231.352443692359),(150,1507.9644737231006),(200,1130.9733552923256)])
def test_two_crossing_db12_legs_from_drawing(spacing,expected):
    out=at_station(settings([zone(spacing=spacing)]),x_m=10.)
    assert out['ready'] and out['zone']['Avf_mm2_per_m']==pytest.approx(expected)


def test_independent_dowels_ignore_girder_stirrup_area_count_and_spacing():
    cfg=settings();before=deepcopy(cfg)
    girder=zone(Diameter_mm=25.,Legs=6,Spacing_mm=50.)
    a=at_station(cfg,x_m=10.,girder_zone=girder)
    girder.update(Diameter_mm=32.,Legs=8,Spacing_mm=35.)
    b=at_station(cfg,x_m=10.,girder_zone=girder)
    assert a==b and cfg==before
    assert a['zone']['Legs']==2 and a['zone']['Diameter_mm']==12.


def test_linked_dowel_mode_uses_its_own_crossing_leg_count():
    girder=zone(Legs=4)
    cfg=settings(connector_source=LINKED_DOWELS,dowel_crossing_legs=2)
    out=at_station(cfg,x_m=10.,girder_zone=girder)
    assert out['zone']['Avf_mm2_per_m']==pytest.approx(1507.9644737231)
    assert girder['Legs']==4
    legacy=at_station({},x_m=10.,girder_zone=girder)
    assert legacy['zone']['Avf_mm2_per_m']==pytest.approx(2*out['zone']['Avf_mm2_per_m'])


def test_missing_or_unknown_dowel_source_never_falls_back_to_stirrups():
    for cfg in (settings([]),settings([zone(0,5)]),settings(connector_source='unknown')):
        result=at_station(cfg,x_m=10.,girder_zone=zone())
        assert not result['ready'] and result['zone'] is None


@pytest.mark.parametrize('changes',[{'x_start_m':None},{'x_end_m':None},{'Legs':1.5},{'Spacing_mm':0},{'fy_MPa':None}])
def test_incomplete_or_nonphysical_dowel_records_receive_no_supply(changes):
    assert not at_station(settings([zone(**changes)]),x_m=10.)['ready']


def test_boundaries_take_weaker_adjoining_zone_and_overlaps_are_rejected():
    cfg=settings([zone(0,5,70),zone(5,20,150)])
    out=at_station(cfg,x_m=5.)
    assert out['zone']['Spacing_mm']==150
    assert at_station(cfg,x_m=5.-1e-7)['zone']['Spacing_mm']==70
    assert not at_station(settings([zone(0,6),zone(5,20)]),x_m=10.)['ready']


def test_explicit_copy_creates_independent_records():
    girder=[zone(Spacing_mm=100.)]
    copied=copy_girder_zoning(girder)
    copied[0]['Spacing_mm']=150.
    girder[0]['Diameter_mm']=20.
    assert copied[0]['Diameter_mm']==12. and girder[0]['Spacing_mm']==100.


def run_interface(state,cfg):
    prep,composite,_=ap._beam_uls_final_composite_preparation(state)
    return ap._igird_interface_shear_dataframe(state,_demand(),prep=prep,composite_state=composite,
        settings=cfg,strength_route=_route())[0]


def test_actual_interface_resistance_uses_only_dowels_not_i_hoop_plus_dowels():
    state=_state();cfg=settings()
    state['beam_girder_shear_reinforcement_table'].loc[0,['Diameter_mm','Legs','Spacing_mm']]=[25.,4,50.]
    first=run_interface(state,cfg)
    state['beam_girder_shear_reinforcement_table'].loc[0,['Diameter_mm','Legs','Spacing_mm']]=[32.,8,35.]
    second=run_interface(state,cfg)
    for col in ('Avf provided (mm2/m)','Avf credited (mm2/m)','phi Vni (kN/m)'):
        pd.testing.assert_series_equal(first[col],second[col])
    assert first['Avf provided (mm2/m)'].sub(1507.9644737231).abs().lt(1e-8).all()
    assert first['Connector source'].str.contains('separate layout').all()
    assert first['Connector crossing legs'].eq(2).all()
    assert 'Stirrup' not in first


def test_missing_dowel_coverage_and_unanchored_dowels_cannot_pass_interface():
    missing=run_interface(_state(),settings([]))
    assert missing['Status'].eq('REVIEW').all()
    assert missing['Avf credited (mm2/m)'].eq(0).all()
    unanchored=run_interface(_state(),settings(connectors_cross_and_anchored=False))
    assert unanchored['Status'].eq('REVIEW').all()
    assert unanchored['Avf provided (mm2/m)'].gt(0).all()
    assert unanchored['Avf credited (mm2/m)'].eq(0).all()


def test_separate_dowels_do_not_claim_the_extended_stirrup_minimum_waiver():
    result=run_interface(_state(),settings())
    assert result['Potential 5.7.4.2 waiver'].eq('No').all()


def test_legacy_anchorage_declaration_is_read_without_reinterpreting_old_projects():
    state={'project_metadata':{'beam_girder_interface_shear_settings':{'stirrups_cross_and_anchored':True}}}
    cfg=ap._igird_interface_shear_settings_from_state(state)
    assert cfg['connector_source']==STIRRUPS
    assert cfg['connectors_cross_and_anchored'] is True
    assert cfg['stirrups_cross_and_anchored'] is True


def test_project_json_retains_independent_dowels_and_unknown_extents():
    path=Path(__file__).resolve().parents[1]/'qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json'
    state={};apply_project_to_session_state(project_from_json(path.read_text()),state)
    cfg=settings([zone(x_start_m=None,x_end_m=None)])
    state.setdefault('project_metadata',{})['beam_girder_interface_shear_settings']=cfg
    raw=project_to_json(project_from_session_state(state))
    restored={};apply_project_to_session_state(project_from_json(raw),restored)
    assert ap._igird_interface_shear_settings_from_state(restored)==cfg
    assert not at_station(cfg,x_m=10.)['ready']


def test_ui_retains_missing_extents_without_adding_confirmation_checkboxes():
    cfg=settings([zone(x_start_m=None,x_end_m=None)])
    script="""
import streamlit as st
from concrete_pmm_pro.ui import analysis_page as ap
ap._igird_render_interface_shear_settings(st.session_state)
"""
    at=AppTest.from_string(script)
    at.session_state['project_metadata']={'beam_girder_interface_shear_settings':cfg}
    at.run(timeout=30)
    assert not at.exception
    assert len(at.checkbox)==1  # Reuses the pre-existing anchorage declaration.
    saved=ap._igird_interface_shear_settings_from_state(at.session_state.filtered_state)
    assert saved==cfg
    at.run(timeout=30)
    assert not at.exception
    assert ap._igird_interface_shear_settings_from_state(at.session_state.filtered_state)==cfg


def test_source_change_clears_composite_results_but_unchanged_settings_do_not():
    script="""
import streamlit as st
from concrete_pmm_pro.ui import analysis_page as ap
ap._igird_store_interface_shear_settings(st.session_state['new_settings'])
"""
    cfg=settings()
    at=AppTest.from_string(script)
    at.session_state['project_metadata']={'beam_girder_interface_shear_settings':cfg}
    at.session_state['new_settings']=deepcopy(cfg)
    at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]={'sentinel':'old'}
    at.session_state['igird_member_uls_runtime_results']={'sentinel':'old'}
    at.run(timeout=30)
    assert not at.exception and ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY in at.session_state
    changed=deepcopy(cfg);changed['dowel_zones'][0]['Spacing_mm']=200.
    at.session_state['new_settings']=changed
    at.run(timeout=30)
    assert not at.exception
    assert ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY not in at.session_state
    assert 'igird_member_uls_runtime_results' not in at.session_state
