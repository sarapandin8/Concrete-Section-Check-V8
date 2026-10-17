"""Physical mat order, real section positions, input persistence and usability."""
from copy import deepcopy
import json
import math
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import igird_slab_layers as layers
from concrete_pmm_pro.ui import analysis_page as ap,igird_flexure_workspace as fw,igird_station36 as station,igird_joint37 as joint_ui
from concrete_pmm_pro.io.project_io import project_from_session_state,project_to_json,project_from_json,apply_project_to_session_state
from test_igird_coupled34 import adapter_fixture


def inputs():
    params={'Tslab_mm':350.,'deck_long_rebar_top_diameter_mm':16.,'deck_long_rebar_bottom_diameter_mm':16.,
        'deck_long_rebar_top_cover_mm':50.,'deck_long_rebar_bottom_cover_mm':50.,
        'Be_mm':1200.,'deck_long_rebar_credit_positive_mn':True,'deck_long_rebar_fy_MPa':390.,'deck_long_rebar_Es_MPa':200000.,
        'deck_long_rebar_top_spacing_mm':200.,'deck_long_rebar_bottom_spacing_mm':150.}
    cfg={layers.ORDER_KEY:layers.RULE,'slab_transverse_mesh':{face:{'Diameter_mm':16.,'Spacing_mm':150.,'Clear_cover_mm':40.,'fy_MPa':390.} for face in ('top','bottom')}}
    return params,cfg


def fixture():
    state,rows,route,_=adapter_fixture();p,cfg=inputs()
    state['section_parameters'].update(p);state['section_preset_key']='parametric_i_girder'
    interface=ap._igird_interface_shear_settings_from_state(state)
    interface.setdefault('dowel_connection',{}).update(cfg)
    state[layers.INTERFACE_KEY]=interface
    state['project_metadata']={**state.get('project_metadata',{}),layers.INTERFACE_KEY:deepcopy(interface)}
    layers.adopt(state)
    return state,rows,route


def test_user_DB16_cover40_places_longitudinal_inside_and_preserves_the_input_values():
    p,cfg=inputs();before=deepcopy((p,cfg));r=layers.resolve(p,cfg)
    assert r['ready'] and (p,cfg)==before
    assert [row['Auto longitudinal cover (mm)'] for row in r['rows']]==[56.,56.]
    assert [row['Transverse centre below top (mm)'] for row in r['rows']]==[48.,302.]
    assert [row['Longitudinal centre below top (mm)'] for row in r['rows']]==[64.,286.]
    assert r['inner_clear_gap_mm']==206.


@pytest.mark.parametrize('dt,ct,dl,t',[(10,30,16,250),(12,35,20,350),(16,40,16,350),(20,45,25,400),(25,50,32,450)])
def test_sizes_and_thickness_change_both_faces_without_suggesting_a_new_bar_size(dt,ct,dl,t):
    p,cfg=inputs();p['Tslab_mm']=t
    for face in ('top','bottom'):
        cfg['slab_transverse_mesh'][face].update(Diameter_mm=dt,Clear_cover_mm=ct)
        p[f'deck_long_rebar_{face}_diameter_mm']=dl
    r=layers.resolve(p,cfg);assert r['ready']
    top,bottom=r['rows'];zt=top['Longitudinal centre below top (mm)'];zb=bottom['Longitudinal centre below top (mm)']
    assert zt==ct+dt+dl/2 and zb==t-zt
    assert zt-top['Transverse centre below top (mm)']==(dt+dl)/2


def test_top_and_bottom_are_independent_and_legacy_layouts_are_not_reinterpreted_by_a_pure_read():
    p,cfg=inputs();cfg['slab_transverse_mesh']['top'].update(Diameter_mm=12.,Clear_cover_mm=35.)
    assert layers.resolve(p,cfg)['parameters']['deck_long_rebar_top_cover_mm']==47.
    assert layers.resolve(p,cfg)['parameters']['deck_long_rebar_bottom_cover_mm']==56.
    assert layers.resolve(p,{})['parameters']==p


@pytest.mark.parametrize('value',[None,True,float('nan'),float('inf'),-1.])
def test_unknown_or_invalid_transverse_cover_is_not_converted_into_zero_or_the_old_manual_cover(value):
    p,cfg=inputs();cfg['slab_transverse_mesh']['top']['Clear_cover_mm']=value
    r=layers.resolve(p,cfg);assert not r['ready']
    assert r['parameters']['deck_long_rebar_top_cover_mm'] is None
    assert r['rows'][0]['Longitudinal centre below top (mm)'] is None


def test_nonpositive_transverse_size_and_overlapping_opposite_mats_are_unavailable():
    p,cfg=inputs();cfg['slab_transverse_mesh']['top']['Diameter_mm']=0
    assert not layers.resolve(p,cfg)['ready']
    p,cfg=inputs();p['Tslab_mm']=130.
    r=layers.resolve(p,cfg);assert not r['ready'] and r['inner_clear_gap_mm']==-14.


def test_current_source_inputs_override_stale_derived_covers_in_every_analysis_reader():
    state,_,_=fixture();state['section_parameters']['deck_long_rebar_top_cover_mm']=999.
    before=deepcopy(state);p=ap._beam_uls_get_state_value(state,'section_parameters')
    assert p['deck_long_rebar_top_cover_mm']==56 and json.dumps(state,sort_keys=True,default=str)==json.dumps(before,sort_keys=True,default=str)
    state[layers.INTERFACE_KEY]['dowel_connection']['slab_transverse_mesh']['top']['Diameter_mm']=20.
    assert ap._beam_uls_get_state_value(state,'section_parameters')['deck_long_rebar_top_cover_mm']==60.


def test_real_composite_section_uses_the_calculated_positions_and_keeps_equivalent_steel_area():
    state,_,_=fixture();prep,comp,notes=ap._beam_uls_final_composite_preparation(state)
    assert comp is not None,notes
    assert [b.y_mm for b in prep.deck_rebars]==pytest.approx([1036.,814.])
    assert [b.area_mm2 for b in prep.deck_rebars]==pytest.approx([math.pi*16**2/4*1200/200,math.pi*16**2/4*1200/150])
    assert comp['section_parameters']['deck_long_rebar_top_cover_mm']==56.
    # Moving the outer transverse mat inward moves the longitudinal centroid
    # by the same distance; this is a section input change, not only a sketch.
    state[layers.INTERFACE_KEY]['dowel_connection']['slab_transverse_mesh']['top']['Clear_cover_mm']=45.
    p2,_,_=ap._beam_uls_final_composite_preparation(state)
    assert p2.deck_rebars[0].y_mm==pytest.approx(1031.)


def test_impossible_or_unknown_layering_blocks_composite_preparation_instead_of_using_zero_cover():
    state,_,_=fixture();state[layers.INTERFACE_KEY]['dowel_connection']['slab_transverse_mesh']['top']['Clear_cover_mm']=None
    prep,comp,notes=ap._beam_uls_final_composite_preparation(state)
    assert not prep.ready and comp is None and any('position is unavailable' in n for n in notes)


def test_geometry_changes_stale_section_and_joint_results_without_changing_any_load():
    state,rows,route=fixture();before=rows.copy(deep=True)
    a=fw.fingerprints(state,rows,route=route);b=joint_ui.fingerprint(state,rows,route=route)
    state[layers.INTERFACE_KEY]['dowel_connection']['slab_transverse_mesh']['top']['Clear_cover_mm']=45.
    assert fw.fingerprints(state,rows,route=route)['section']!=a['section']
    assert joint_ui.fingerprint(state,rows,route=route)!=b
    pd.testing.assert_frame_equal(rows,before)


def test_old_complete_project_adopts_the_requested_order_once_and_saves_inputs_without_results():
    state,_,_=fixture();cfg=state[layers.INTERFACE_KEY]['dowel_connection'];cfg.pop(layers.ORDER_KEY)
    state['section_parameters'].pop(layers.PARAM_ORDER,None)
    state['section_parameters'].update(deck_long_rebar_top_cover_mm=50.,deck_long_rebar_bottom_cover_mm=50.)
    state['project_metadata'][layers.INTERFACE_KEY]=deepcopy(state[layers.INTERFACE_KEY])
    raw=project_to_json(project_from_session_state(state));restored={}
    apply_project_to_session_state(project_from_json(raw),restored)
    assert restored['section_parameters']['deck_long_rebar_top_cover_mm']==56.
    cfg=layers.detail_from_state(restored)
    assert cfg[layers.ORDER_KEY]==layers.RULE and cfg['layer_order_previous_longitudinal_covers_mm']=={'top':50.,'bottom':50.}
    restored[fw.CACHE_KEY]={'joint37_research':{'must_not_persist_numerical_results':123.}}
    output=project_to_json(project_from_session_state(restored));assert 'must_not_persist_numerical_results' not in output
    again={};apply_project_to_session_state(project_from_json(output),again)
    assert again['section_parameters']==restored['section_parameters']


def test_mesh_input_is_available_when_legacy_joint_assessment_is_off_and_never_solves():
    script='''import streamlit as st
from concrete_pmm_pro.ui.igird_dowel_joint import render_settings
st.session_state.setdefault('section_preset_key','parametric_i_girder')
st.session_state.setdefault('section_parameters',{'Tslab_mm':350.,'deck_long_rebar_top_diameter_mm':16.,'deck_long_rebar_bottom_diameter_mm':16.})
current={'dowel_connection':{'mode':'off','slab_transverse_mesh':{face:{'Diameter_mm':16.,'Spacing_mm':150.,'Clear_cover_mm':40.,'fy_MPa':390.} for face in ('top','bottom')}}}
st.session_state['saved']=render_settings(current,section_params=st.session_state['section_parameters'],state=st.session_state)
'''
    from concrete_pmm_pro.analysis import igird_joint37_solver as solver,igird_dowel_joint as joint
    with patch.object(solver,'limit',side_effect=AssertionError('Input view must not solve')),patch.object(joint,'solve_mechanism',side_effect=AssertionError('Input view must not solve')):
        app=AppTest.from_string(script,default_timeout=60).run()
    assert not app.exception and not app.button
    assert not any(x.label=='U-dowel joint assessment' for x in app.selectbox)
    assert not any(x.label=='Anchorage region' for x in app.selectbox)
    assert app.session_state['section_parameters']['deck_long_rebar_top_cover_mm']==56.
    assert app.session_state['saved']['dowel_connection']['mode']=='off'
    assert any('data-slab-layer-guide' in x.value for x in app.markdown)


def test_unknown_model_classification_is_reported_as_model_work_not_a_required_user_guess():
    from concrete_pmm_pro.ui.igird_composite_inputs import input_plan
    _,cfg=inputs();cfg.update(coating='unknown',anchorage_region='unknown')
    result=input_plan({'dowel_connection':cfg},params={'Tslab_mm':350.})
    assert not any(r['Input'] in {'Dowel coating','Anchorage region','Joint force state'} for r in result['missing'])
    assert any(r['Step']=='Anchorage-region evaluation' for r in result['pending'])
    assert cfg['anchorage_region']=='unknown' and result['design_status']=='REVIEW'


def test_final_stage_survives_actual_widget_cleanup_and_is_reset_when_another_project_loads():
    script='''import streamlit as st
from concrete_pmm_pro.ui.igird_view_state import radio
show=st.checkbox('Show analysis',value=True,key='show')
if show:radio('Flexure stage',['Construction — Noncomposite','Final — Composite'],key='stage')
'''
    app=AppTest.from_string(script).run()
    app.radio[0].set_value('Final — Composite').run()
    app.checkbox[0].set_value(False).run()
    assert 'stage' not in app.session_state.filtered_state
    app.checkbox[0].set_value(True).run()
    assert app.radio[0].value=='Final — Composite' and not app.exception
    from concrete_pmm_pro.ui.igird_view_state import KEY
    state,_,_=fixture();state[KEY]={'stage':'Final — Composite'}
    project=project_from_session_state(state)
    assert KEY not in project.metadata
    apply_project_to_session_state(project,state)
    assert KEY not in state


def test_main_calculate_does_not_run_an_archived_model_merely_because_an_old_project_enabled_it():
    from concrete_pmm_pro.ui import igird_coupled_model as legacy,igird_member_results as members
    state,rows,route=fixture()
    state['project_metadata'][legacy.KEY]={'enabled':True}
    with patch.object(legacy,'calculate',side_effect=AssertionError('Legacy calculations require explicit advanced opt-in')), \
         patch.object(members,'calculate_member',return_value={}), \
         patch.object(ap,'_igird_interface_shear_dataframe',return_value=(pd.DataFrame(),[])), \
         patch.object(station,'calculate',return_value={'status':'MODEL BLOCKED'}):
        bundle=fw.calculate_bundle(state,rows,route=route)
    assert bundle['coupled_research']['enabled'] is False
    assert bundle['coupled_research']['accepted_phiTn_Nmm'] is None
