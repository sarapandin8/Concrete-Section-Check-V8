"""Independent force/geometry and code-boundary regressions for SHEARCOMP1."""
import copy
import math
from unittest.mock import patch

import pandas as pd
import pytest

from test_igird_uls5_shear_general_procedure import _state, _demand, _route
from concrete_pmm_pro.code_checks.aashto_lrfd import (
    aashto_shear_smax_mm, aashto_shear_transverse_design_fy_mpa,
)
from concrete_pmm_pro.core.aashto_units import ksi_to_mpa
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui import igird_shear_section as section


def composite_state(*, thickness=220.0, debonded=False):
    state = _state(debonded=debonded)
    state["section_parameters"] = {"composite_enabled": True, "B1_mm": 800.0,
        "Be_mm": 2400.0, "Tslab_mm": thickness, "deck_fc_MPa": 35.0,
        "Be_mode": "Manual", "Be_strength_verified": True}
    return state


def test_composite_depth_matches_independent_rectangular_compression_resultants():
    state = composite_state()
    row = _demand(10).iloc[0].to_dict()
    depth = section.depth_values(state, row=row, strength_route=_route())
    # No ordinary bars. All strands lie at y=120. The whole compression
    # block is within the 2400x220 deck; alpha1=.85, fc=35 MPa.
    assert depth["Depth source status"] == "PASS"
    assert depth["y T mm"] == pytest.approx(120.0)
    force = depth["T kN"] * 1000
    a = force / (0.85 * 35 * 2400)
    assert a < 220
    yc = 1820.0 - a / 2
    lever = yc - 120
    assert depth["y C mm"] == pytest.approx(yc, abs=1e-5)
    assert depth["de mm"] == pytest.approx(1700)
    assert depth["C-T lever arm mm"] == pytest.approx(lever, abs=1e-5)
    assert depth["dv_mm"] == pytest.approx(max(lever, .9*1700, .72*1820), abs=1e-5)
    assert abs(depth["Depth force residual N"]) < 1e-5
    assert abs(depth["Depth moment residual N-mm"]) < .01


def test_web_fc_and_width_stay_precast_while_deck_changes_phi_vn():
    row = _demand(10).iloc[0].to_dict()
    state = composite_state()
    before_geometry = state["section_geometry"].model_dump()
    final = ap._beam_uls_shear_result_for_row(state, row, strength_route=_route())
    thicker = ap._beam_uls_shear_result_for_row(composite_state(thickness=320), row, strength_route=_route())
    precast = ap._beam_uls_shear_result_for_row(_state(), row, strength_route=_route())
    assert final["Section basis"] == "FINAL COMPOSITE"
    assert final["h mm"] == 1820 and precast["h mm"] == 1600
    assert final["f'c MPa"] == thicker["f'c MPa"] == precast["f'c MPa"] == 45
    assert final["bw mm"] == thicker["bw mm"] == precast["bw mm"] == 800
    assert final["Compression f'c MPa"] == 35
    assert thicker["dv mm"] > final["dv mm"] > precast["dv mm"]
    assert thicker["φVn kN"] > final["φVn kN"] > precast["φVn kN"]
    assert state["section_geometry"].model_dump() == before_geometry
    assert section.RUNTIME_KEY not in state


@pytest.mark.parametrize("nu", [-200, 0, 200])
def test_actual_force_centroids_reproduce_axial_and_moment_equilibrium(nu):
    state = composite_state()
    row = _demand(10).iloc[0].to_dict()
    row["Nu"] = nu
    result = section.depth_values(state, row=row, strength_route=_route())
    force = result["force_trace"]
    assert force["C_N"] - force["T_N"] == pytest.approx(force["Pn_N"], abs=1e-5)
    assert abs(force["force_balance_N"]) < 1e-5
    assert abs(force["moment_balance_Nmm"]) < .01
    assert result["dv_mm"] >= max(.9*force["de_mm"], .72*force["h_mm"])


def test_debonded_shear_depth_requires_kappa_two_even_without_service_tension():
    state = composite_state(debonded=True)
    state["igird_flexure_development_settings"] = {"debonded_service_condition": "no_tension_confirmed"}
    value = section.depth_values(state, row=_demand(1.2).iloc[0].to_dict(), strength_route=_route())
    families = value["force_trace"]["strand_development_trace"]
    debonded = next(r for r in families if "debonded" in r["Family"])
    assert debonded["kappa"] == 2
    assert debonded["bonded_distance_mm"] == pytest.approx(200)
    assert debonded["transfer_factor"] == pytest.approx(200/(60*15.2))
    assert debonded["fpx_limit_MPa"] < 120000/140


def test_spacing_branch_includes_phi_and_resisting_vp():
    fc, bv, dv, vu = 45., 200., 1080., 1120000.
    assert vu/(bv*dv*fc) < .125
    smax, ratio, _ = aashto_shear_smax_mm(fc,bv,dv,vu,phi=.85)
    assert ratio == pytest.approx(vu/(.85*bv*dv*fc))
    assert ratio > .125
    assert smax == pytest.approx(304.8)
    with_vp = aashto_shear_smax_mm(fc,bv,dv,vu,phi=.85,vp_N=200000)
    assert with_vp[1] == pytest.approx((vu-.85*200000)/(.85*bv*dv*fc))
    assert with_vp[0] == pytest.approx(609.6)
    with pytest.raises(ValueError):
        aashto_shear_smax_mm(fc,bv,dv,vu,phi=0)


def test_high_grade_transverse_fy_requires_the_special_application_source():
    default, note = aashto_shear_transverse_design_fy_mpa(750)
    verified, _ = aashto_shear_transverse_design_fy_mpa(750,qualifying_5_4_3_3=True)
    assert default == pytest.approx(ksi_to_mpa(75))
    assert verified == pytest.approx(ksi_to_mpa(100))
    assert "exception not declared" in note
    assert aashto_shear_transverse_design_fy_mpa(390)[0] == 390


def test_manual_dv_cannot_override_the_code_lower_bound_or_overcredit_depth():
    state = composite_state()
    row = _demand(10).iloc[0].to_dict()
    auto = section.depth_values(state,row=row,strength_route=_route())
    state[ap.SHEAR_DEPTH_SETTINGS_KEY] = {"mode":ap.SHEAR_DEPTH_MODE_MANUAL,"dv_mm":auto["dv lower bound mm"]}
    valid = section.depth_values(state,row=row,strength_route=_route())
    assert valid["dv_mm"] == pytest.approx(auto["dv lower bound mm"])
    for invalid in (100, 1820):
        state[ap.SHEAR_DEPTH_SETTINGS_KEY]["dv_mm"] = invalid
        value = section.depth_values(state,row=row,strength_route=_route())
        assert math.isnan(value["dv_mm"])
        assert value["Depth source status"] == "REVIEW"


def test_composite_acceptance_waits_for_width_and_current_interface_result():
    state = composite_state()
    demand = _demand(10)
    row = ap._beam_uls_shear_check_dataframe(state,demand,strength_route=_route()).iloc[0]
    assert row["Strength status"] == "PASS"
    assert row["Status"] == "REVIEW"
    assert row["Composite action status"] == "REVIEW"
    assert "Interface Shear" in row["Depth note"]
    before = ap._beam_uls_check_input_hash(state,demand,strength_route=_route(),check_name="Shear")
    prep, cs, _ = ap._beam_uls_final_composite_preparation(state)
    state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY] = {"stirrups_cross_and_anchored":True}
    settings = ap._igird_interface_shear_settings_from_state(state)
    source = ap._igird_interface_source_dataframe(demand)
    interface, _ = ap._igird_interface_shear_dataframe(state,source,prep=prep,composite_state=cs,
        settings=settings,strength_route=_route())
    assert ap._igird_interface_overall_status(interface) == "PASS"
    signature = ap._igird_interface_shear_hash(state,source,settings=settings,strength_route=_route())
    ap._beam_uls_store_manual_result(state,ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME,input_hash=signature,
        result={"result_version":ap._IGIRDER_INTERFACE_SHEAR_RESULT_VERSION,"interface_shear_df":interface})
    after = ap._beam_uls_check_input_hash(state,demand,strength_route=_route(),check_name="Shear")
    assert before != after
    row = ap._beam_uls_shear_check_dataframe(state,demand,strength_route=_route()).iloc[0]
    assert row["Composite action status"] == row["Status"] == "PASS"
    state["section_parameters"]["Be_strength_verified"] = False
    row = ap._beam_uls_shear_check_dataframe(state,demand,strength_route=_route()).iloc[0]
    assert row["Status"] == "REVIEW"


def test_no_implicit_support_exception_at_physical_cut_end_rows():
    source = pd.concat([_demand(0),_demand(10),_demand(20)],ignore_index=True)
    state = composite_state()
    result = ap._beam_uls_calculate_selected_check(state,source,selected_check="Shear",strength_route=_route())
    eligible = ap._beam_uls_shear_design_rows_for_governing(result["shear_check_df"])
    assert {"0.000", "20.000"}.issubset(set(eligible["Governing x"].str.replace(" m","",regex=False)))
    pd.testing.assert_frame_equal(source,pd.concat([_demand(0),_demand(10),_demand(20)],ignore_index=True))


def test_hashes_include_geometry_and_updated_equations_without_resolving():
    state = composite_state()
    source = _demand(10)
    before = ap._beam_uls_check_input_hash(state,source,strength_route=_route(),check_name="Shear")
    changed = copy.deepcopy(state)
    changed["section_geometry"].outer_polygon[2].y = 1610
    with patch.object(section,"depth_values",side_effect=AssertionError("Review/hash must not solve")):
        after = ap._beam_uls_check_input_hash(changed,source,strength_route=_route(),check_name="Shear")
    assert before != after
    result = ap._beam_uls_shear_check_dataframe(state,source,strength_route=_route()).iloc[0]
    with patch.object(section,"depth_values",side_effect=AssertionError("Trace must not solve")):
        trace = ap._beam_uls_shear_calculation_trace_dataframe(result)
    assert trace["Code basis"].str.contains("5.7.2.8").any()
    assert trace["Equation / substitution"].str.contains("φ bv dv",regex=False).any()


def bearing_state(**changes):
    from concrete_pmm_pro.analysis.igird_shear_support import SETTINGS_KEY
    state = composite_state()
    state[SETTINGS_KEY] = {"locations_confirmed":True, "offset_reference":"centerline",
        "left_offset_m":.4, "right_offset_m":.4,
        "left_bearing_length_mm":0., "right_bearing_length_mm":0., **changes}
    return state


def test_known_centerlines_without_lengths_do_not_invent_internal_faces_or_critical_sections():
    from concrete_pmm_pro.analysis.igird_shear_support import support_basis
    state = bearing_state()
    basis = support_basis(state,span_m=20)
    assert basis["status"] == "BEARING LENGTH REQUIRED"
    assert [s["centerline_x_m"] for s in basis["supports"]] == [.4,19.6]
    assert all(s["inside_face_x_m"] is None for s in basis["supports"])
    assert not basis["near_support_exception"]
    assert ap._beam_uls_shear_default_critical_section_rows(state,_demand(10),strength_route=_route()) == []


def test_face_plus_local_dv_markers_use_bearing_footprint_and_keep_overhang_rows():
    from concrete_pmm_pro.analysis.igird_shear_support import support_basis
    state = bearing_state(left_bearing_length_mm=400,right_bearing_length_mm=400)
    source = pd.concat([_demand(x) for x in (0,1,10,19,20)],ignore_index=True)
    basis = support_basis(state,span_m=20)
    assert [s["inside_face_x_m"] for s in basis["supports"]] == pytest.approx([.6,19.4])
    assert [s["outer_face_x_m"] for s in basis["supports"]] == pytest.approx([.2,19.8])
    markers = ap._beam_uls_shear_default_critical_section_rows(state,source,strength_route=_route())
    assert len(markers) == 2
    for marker in markers:
        depth = section.depth_values(state,row=_demand(marker["x_m"]).iloc[0].to_dict(),strength_route=_route())
        assert abs(marker["x_m"]-marker["Support face x m"]) == pytest.approx(depth["dv_mm"]/1000,abs=1e-6)
    result = ap._beam_uls_calculate_selected_check(state,source,selected_check="Shear",strength_route=_route())
    assert not ap._beam_uls_shear_near_support_load_indices(result["shear_check_df"])
    eligible = ap._beam_uls_shear_design_rows_for_governing(result["shear_check_df"])
    assert {"0.000 m","20.000 m"}.issubset(set(eligible["Governing x"]))
    pd.testing.assert_frame_equal(source,pd.concat([_demand(x) for x in (0,1,10,19,20)],ignore_index=True))


def test_direct_internal_face_reference_and_invalid_bearing_footprints():
    from concrete_pmm_pro.analysis.igird_shear_support import support_basis
    basis = support_basis(bearing_state(offset_reference="inside_face"),span_m=20)
    assert basis["status"] == "FACES KNOWN"
    assert [s["inside_face_x_m"] for s in basis["supports"]] == [.4,19.6]
    assert all(s["centerline_x_m"] is None for s in basis["supports"])
    for state in (bearing_state(left_bearing_length_mm=1000),bearing_state(left_offset_m=12,right_offset_m=12),bearing_state(left_offset_m=float("nan"))):
        assert support_basis(state,span_m=20)["status"] == "INVALID"
        assert not support_basis(state,span_m=20)["near_support_exception"]
    state = composite_state(); state.pop("igird_shear_support_settings")
    assert support_basis(state,span_m=20)["status"] == "UNCONFIRMED"
    assert ap._beam_uls_shear_default_critical_section_rows(state,_demand(10),strength_route=_route()) == []


def test_bearing_changes_stale_vt_only_and_leave_cut_end_depth_unchanged():
    state = bearing_state(); source = _demand(1)
    before = {name:ap._beam_uls_check_input_hash(state,source,strength_route=_route(),check_name=name) for name in ("Shear","Torsion","Shear + Torsion","Flexure — Final Composite")}
    depth = section.depth_values(state,row=source.iloc[0].to_dict(),strength_route=_route())
    state["igird_shear_support_settings"]["left_offset_m"] = .7
    for name in before:
        after = ap._beam_uls_check_input_hash(state,source,strength_route=_route(),check_name=name)
        assert (after == before[name]) == (name == "Flexure — Final Composite")
    after = section.depth_values(state,row=source.iloc[0].to_dict(),strength_route=_route())
    assert after["dv_mm"] == depth["dv_mm"]
    assert after["force_trace"]["strand_development_trace"] == depth["force_trace"]["strand_development_trace"]


def test_support_project_save_reload_does_not_leak_previous_project_geometry():
    from concrete_pmm_pro.io.project_io import project_from_session_state, project_to_json, project_from_json, apply_project_to_session_state
    state = bearing_state()
    saved = project_from_session_state(state)
    restored = {"igird_support_widget_left_offset":15.}
    apply_project_to_session_state(project_from_json(project_to_json(saved)),restored)
    assert restored["igird_shear_support_settings"]["left_offset_m"] == .4
    assert "igird_support_widget_left_offset" not in restored
    saved.metadata.pop("igird_shear_support_settings")
    apply_project_to_session_state(saved,restored)
    assert not restored["igird_shear_support_settings"]["locations_confirmed"]


def test_canonical_depth_geometry_signature_ignores_vertex_order_and_name():
    state = composite_state()
    original = section.geometry_signature(state)
    state["section_geometry"].name = "Different display label"
    points = state["section_geometry"].outer_polygon
    state["section_geometry"].outer_polygon = list(reversed(points[1:]+points[:1]))
    assert section.geometry_signature(state) == original


def test_invalid_section_and_disabled_prestress_remain_review_without_crashing():
    for field in ("section_geometry","concrete_material"):
        state = _state();state.pop(field)
        result = section.depth_values(state,row=_demand(10).iloc[0].to_dict(),strength_route=_route())
        assert result["Depth source status"] == "REVIEW"
        assert math.isnan(result["dv_mm"])
