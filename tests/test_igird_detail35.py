"""Hook datum, per-zone bend, geometric limits and independent mesh ownership."""
from copy import deepcopy
import json
import math
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import igird_dowel_detail35 as detail
from concrete_pmm_pro.analysis import igird_dowel_joint as joint
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_session_state, project_from_json, project_to_json
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.visualization.igird_dowel_detail import u_dowel_detail_svg
from test_igird_joint29 import cfg, context, selected_zone, action
from test_igird_uls4_interface_integration import _state


def current(**changes):
    out = detail.migrate(cfg(), {"Tslab_mm":350.}, girder_cover=40., slab_cover=50.)
    out.update({"hook_top_depth_mm":170., **changes})
    return out


@pytest.mark.parametrize("db,expected",[(12,72),(16,96),(20,120),(25,150),(32,192)])
def test_design_bend_is_six_times_the_actual_zone_diameter(db, expected):
    before = current(hook_inside_bend_mm=999)
    result = detail.resolve(before, slab_thickness_mm=350, db_mm=db)
    assert result["hook_inside_bend_mm"] == expected
    assert before["hook_inside_bend_mm"] == 999


def test_top_datum_and_required_covers_are_independent_and_follow_current_thickness():
    conf = current(slab_ldh_available_mm=999)
    result = detail.resolve(conf, slab_thickness_mm=350, db_mm=12)
    assert result["slab_ldh_available_mm"] == 180
    assert detail.covers(result) == (40, 50)
    assert result["cover_required_mm"] == 40
    assert detail.resolve(conf, slab_thickness_mm=400, db_mm=12)["slab_ldh_available_mm"] == 230


def test_six_db_does_not_override_a_larger_code_minimum():
    zone = selected_zone();zone.update(Diameter_mm=32.)
    result = joint.anchorage(current(), zone, context())
    bend = result["checks"]["hook_inside_bend_mm"]
    assert bend["available_mm"] == 192 and bend["required_mm"] == 256
    assert not bend["adequate"] and not result["ready"]


def test_actual_user_geometry_still_fails_180_development_and_34_clear_web_cover():
    polygon=[[-300,-750],[300,-750],[300,-500],[100,-350],[100,450],[300,600],
        [300,750],[-300,750],[-300,600],[-100,450],[-100,-350],[-300,-500]]
    conf = current(row_spacing_mm=120., hook_tail_mm=200., girder_ld_available_mm=1400.)
    result = joint.anchorage(conf, selected_zone(), context(girder_polygon=polygon,contact_top_y_mm=750))
    checks = result["checks"]
    assert checks["hook_inside_bend_mm"]["adequate"]
    assert checks["slab_hook_cover"] == {"available_mm":170., "required_mm":50., "dc":50/170, "adequate":True}
    assert checks["girder_leg_fit"]["adequate"]
    assert not checks["slab_ldh_available_mm"]["adequate"]
    side = checks["bonded_leg_concrete_cover"]
    assert side["available_mm"]-6 == pytest.approx(34)
    assert side["required_mm"]-6 == 40 and not side["adequate"]
    assert not result["ready"]


@pytest.mark.parametrize("e",[None,350.,400.,-1.,float("nan"),True])
def test_unknown_or_impossible_hook_depth_cannot_pass_anchorage(e):
    result = joint.anchorage(current(hook_top_depth_mm=e), selected_zone(), context())
    assert not result["ready"]


def test_migration_does_not_reinterpret_old_required_cover_as_actual_hook_depth():
    old = cfg(cover_required_mm=170, slab_ldh_available_mm=250, hook_inside_bend_mm=48)
    before = deepcopy(old)
    converted = detail.migrate(old, {"Tslab_mm":350})
    assert converted["hook_top_depth_mm"] == 100
    assert converted["girder_clear_cover_required_mm"] == 170
    assert converted["legacy_detail35"]["hook_inside_bend_mm"] == 48
    assert old == before
    assert detail.resolve(old, slab_thickness_mm=999, db_mm=20) == old
    assert detail.migrate(converted, {"Tslab_mm":999}) == converted


def test_unknown_b_d_and_mesh_geometry_are_not_filled_from_required_minima():
    old = cfg(slab_ldh_available_mm=None)
    out = detail.resolve(detail.migrate(old,{"Tslab_mm":350}), slab_thickness_mm=350)
    assert out["hook_top_depth_mm"] is out["slab_ldh_available_mm"] is out["hook_inside_bend_mm"] is None
    for row in detail.mesh_rows(out,{"deck_long_rebar_fy_MPa":390}):
        assert row["Diameter_mm"] is row["Spacing_mm"] is row["Clear_cover_mm"] is None
        assert row["fy_MPa"] == 390


def test_provided_bend_is_kept_and_large_automatic_bend_does_not_unlock_production():
    result = detail.resolve(current(bend_mode="provided",hook_inside_bend_mm=100),slab_thickness_mm=350,db_mm=16)
    assert result["hook_inside_bend_mm"] == 100
    out = joint.evaluate(result, selected_zone(), context(), action(), declared_anchored=True)
    assert out["status"] == "REVIEW"


def test_selected_dowel_source_controls_automatic_bend_list():
    girder=[{"Diameter_mm":12},{"Diameter_mm":16},{"Diameter_mm":32,"Active":False}]
    conf={"connector_source":"dowels_same_zoning", "dowel_zones":[{"Diameter_mm":25}]}
    assert detail.diameter_values(conf,girder) == [12,16]
    conf["connector_source"]="independent_dowels"
    assert detail.diameter_values(conf,girder) == [25]
    conf["connector_source"]="girder_stirrups"
    assert detail.diameter_values(conf,girder) == []


def test_mesh_two_directions_remain_distinct_and_covers_are_not_inferred():
    params={"deck_long_rebar_top_diameter_mm":16.,"deck_long_rebar_top_spacing_mm":200.,
        "deck_long_rebar_top_cover_mm":50.,"deck_long_rebar_fy_MPa":390.}
    conf=current(slab_transverse_mesh={"top":{"Diameter_mm":12.,"Spacing_mm":150.,"fy_MPa":490.}})
    original = deepcopy((conf,params))
    rows = detail.mesh_inventory(conf,params)
    assert len(rows)==4 and rows[0]["Direction"] == "Along girder" and rows[2]["Direction"] == "Across girder"
    assert rows[0]["As_mm2_per_m"] == pytest.approx(math.pi*16**2/4*1000/200)
    assert rows[2]["As_mm2_per_m"] == pytest.approx(math.pi*12**2/4*1000/150)
    assert rows[2]["fy_MPa"] == 490 and rows[2]["Position"] == "Unknown"
    assert rows[3]["As_mm2_per_m"] is None and "no additional" in rows[2]["Scope"]
    assert (conf,params) == original


def test_new_input_json_roundtrip_and_widget_reset_do_not_persist_results():
    state=_state();state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY]={**ap._igird_interface_shear_settings_from_state(state),joint.KEY:current()}
    state["project_metadata"]={**state.get("project_metadata",{}),ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY:state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY]}
    project=project_from_session_state(state)
    output=project_to_json(project)
    restored={"igird_detail35_bend_mode":"provided", "igird_edit33_editor_igird_detail35_mesh_":{"bad":True}}
    apply_project_to_session_state(project_from_json(output),restored)
    conf=ap._igird_interface_shear_settings_from_state(restored)[joint.KEY]
    assert conf["hook_top_depth_mm"] == 170 and conf["bend_mode"] == "auto_6db"
    assert "igird_detail35_bend_mode" not in restored and "igird_edit33_editor_igird_detail35_mesh_" not in restored
    assert "accepted_phiTn" not in output and "mechanism_review" not in output


def test_new_figure_labels_show_measured_e_and_auto_b_d():
    resolved = detail.resolve(current(),slab_thickness_mm=350,db_mm=12)
    svg=u_dowel_detail_svg(resolved,section_params={"Tslab_mm":350})
    assert "170 mm" in svg and "180 mm" in svg and "72 mm" in svg
    assert "Top surface → outside hook" in svg and "6.0db" in svg
    assert "E is required cover" not in svg


def test_hook_and_mesh_edits_stale_research_without_changing_production_hashes():
    from concrete_pmm_pro.ui import igird_coupled_model as coupled, igird_flexure_workspace as fw
    from test_igird_coupled34 import adapter_fixture
    state,rows,route,_ = adapter_fixture()
    settings = ap._igird_interface_shear_settings_from_state(state)
    settings[joint.KEY] = cfg()
    state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY] = settings
    production = fw.fingerprints(state,rows,route=route)
    old = coupled.fingerprint(state,rows,route=route)
    settings[joint.KEY]["slab_ldh_available_mm"] += 10
    state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY] = settings
    assert coupled.fingerprint(state,rows,route=route) != old
    assert fw.fingerprints(state,rows,route=route) == production
    closure = deepcopy(coupled.settings(state))
    settings[joint.KEY]["slab_transverse_mesh"]={"top":{"Diameter_mm":25.,"Spacing_mm":70.,"Clear_cover_mm":50.,"fy_MPa":490.}}
    assert coupled.settings(state) == closure


SCRIPT = '''
import streamlit as st
from concrete_pmm_pro.ui.igird_dowel_joint import render_settings
from concrete_pmm_pro.analysis.igird_dowel_joint import KEY
if 'settings' not in st.session_state:
 st.session_state['settings']={'connector_source':'dowels_same_zoning',KEY:{'mode':'cracked_equilibrium','detail_schema':'IGIRDER.DETAIL35','bend_mode':'auto_6db','hook_top_depth_mm':170.,'girder_clear_cover_required_mm':40.,'slab_clear_cover_required_mm':50.}}
st.session_state['beam_girder_shear_reinforcement_table']=[{'Diameter_mm':12.}]
params={'Tslab_mm':350.,'deck_long_rebar_top_diameter_mm':16.,'deck_long_rebar_top_spacing_mm':200.,'deck_long_rebar_top_cover_mm':50.,'deck_long_rebar_fy_MPa':390.}
st.session_state['settings'].update(render_settings(st.session_state['settings'],section_params=params,state=st.session_state))
'''


def test_actual_input_edits_retain_previous_cells_and_do_not_run_solvers():
    with patch.object(joint,"solve_mechanism",side_effect=AssertionError("Input editing cannot solve")):
        app=AppTest.from_string(SCRIPT,default_timeout=60).run()
        assert not app.exception and not app.button
        mesh=next(node for node in app.dataframe if str(node.key).startswith("igird_detail35_mesh_"))
        app.session_state[mesh.key]={"edited_rows":{0:{"Diameter_mm":12.,"Spacing_mm":150.},1:{"Diameter_mm":16.,"Spacing_mm":200.}},"added_rows":[],"deleted_rows":[]}
        app.run();assert not app.exception
        saved=deepcopy(app.session_state["settings"])
        assert saved[joint.KEY]["slab_transverse_mesh"]["top"]["Diameter_mm"] == 12
        assert saved[joint.KEY]["slab_ldh_available_mm"] == 180 and saved[joint.KEY]["hook_inside_bend_mm"] == 72
        app.run();assert not app.exception and app.session_state["settings"]==saved
