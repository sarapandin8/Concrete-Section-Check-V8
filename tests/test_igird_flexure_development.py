"""Engineering boundary, equilibrium, and integration checks for FLEXDEP1."""
import math
from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.igird_flexure_development import (
    SETTINGS_KEY, SectionEquilibrium, development_settings, ordinary_bar_limits,
    solve_developed_station, strand_families, strand_stress_limit,
)
from concrete_pmm_pro.core.analysis import AnalysisInput
from concrete_pmm_pro.core.models import ConcreteMaterial, Rebar, RebarMaterial
from concrete_pmm_pro.geometry.generators import rectangle


def layout(debonded=False):
    return [{"Active": True, "Group ID": "Bottom", "No. Strands": 19,
        "Area/Strand_mm2": 98.7, "y_mm_from_bottom": 100,
        "Strand Size": "12.7 mm low-relaxation strand",
        "Pe_construction/strand_kN": 128.507, "Pe_eff_final/strand_kN": 110.149,
        "Left debond m": 2 if debonded else 0, "Right debond m": 2 if debonded else 0,
        "Debonded strand nos": "2,4,16,18" if debonded else ""}]


def context(debonded=False, bars=False, settings=None, sign=1):
    cfg = development_settings({SETTINGS_KEY: settings or {}})
    families = strand_families(layout(debonded), y_min_mm=-750, span_m=20, stage="final", settings=cfg)
    ai = AnalysisInput(section_geometry=rectangle(width_mm=500, height_mm=1500),
        concrete_material=ConcreteMaterial(name="C45", fc_MPa=45),
        rebar_materials=[RebarMaterial(name="SD40", fy_MPa=390, Es_MPa=200000)],
        rebars=[Rebar(x_mm=x, y_mm=-650, diameter_mm=12, material_name="SD40") for x in (-100,100)] if bars else [],
        prestress_elements=[f.element for f in families])
    ctx = SectionEquilibrium(ai, sign)
    return ctx, families, cfg


def station(ctx, families, cfg, x, nu=0):
    return solve_developed_station(ctx, families, reference=ctx.solve(nu), x_m=x,
        span_m=20, nu_n=nu, precast_depth_mm=1500, girder_fc_mpa=45,
        settings=cfg, params={})


def test_fhwa_development_length_units_and_two_stress_branches():
    # Official FHWA PSC example: fpe=162.83 ksi, fps=264.4 ksi,
    # db=0.5 in; bonded ld=124.7 in (rounded published value).
    stress = 6.894757293168
    args = dict(db_mm=12.7, fpe_mpa=162.83*stress, fps_mpa=264.4*stress,
        depth_mm=1828.8, debonded=False)
    start = strand_stress_limit(distance_mm=0, **args)
    assert start["fpx_limit_MPa"] == 0
    assert start["lt_mm"] == pytest.approx(762)
    assert start["ld_mm"]/25.4 == pytest.approx(124.6773333333)
    half_transfer = strand_stress_limit(distance_mm=381, **args)
    assert half_transfer["fpx_limit_MPa"] == pytest.approx(0.5*args["fpe_mpa"])
    at_transfer = strand_stress_limit(distance_mm=762, **args)
    assert at_transfer["fpx_limit_MPa"] == pytest.approx(args["fpe_mpa"])
    midway = strand_stress_limit(distance_mm=(762+start["ld_mm"])/2, **args)
    assert midway["fpx_limit_MPa"] == pytest.approx((args["fpe_mpa"]+args["fps_mpa"])/2)
    full = strand_stress_limit(distance_mm=start["ld_mm"], **args)
    assert full["fpx_limit_MPa"] == pytest.approx(args["fps_mpa"])


@pytest.mark.parametrize("depth,kappa", [(609.6,1), (609.60001,1.6), (1500,1.6)])
def test_kappa_depth_threshold_and_debonded_service_condition(depth,kappa):
    args = dict(distance_mm=2000, db_mm=12.7, fpe_mpa=1116, fps_mpa=1725, depth_mm=depth)
    assert strand_stress_limit(**args, debonded=False)["kappa"] == kappa
    assert strand_stress_limit(**args, debonded=True)["kappa"] == 2
    assert strand_stress_limit(**args, debonded=True,service_condition="tension")["kappa"] == 2
    assert strand_stress_limit(**args, debonded=True,service_condition="no_tension_confirmed")["kappa"] == kappa


def test_partial_transfer_capacity_matches_independent_rectangular_hand_equilibrium():
    ctx, families, cfg = context()
    r = station(ctx, families, cfg, 0.5)
    # All 19 strands have known transfer-limited force. Equilibrium is C=T;
    # the rectangular concrete resultant is at a/2 from the compression face.
    tension = 19*110149*500/762
    a = tension/(.85*45*500)
    expected_mn = tension*(1400-a/2)
    assert r["Mn_Nmm"] == pytest.approx(expected_mn, rel=1e-8)
    assert r["Aps_force_N"] == pytest.approx(-tension)
    assert abs(r["residual_N"]) < .021


def test_cut_end_zero_and_bearing_offset_have_distinct_available_strength():
    ctx, families, cfg = context()
    r = station(ctx, families, cfg, 0)
    assert r["phiMn_Nmm"] == 0
    assert all(t["fpx_limit_MPa"] == 0 for t in r["strand_trace"])
    ctx2, families2, cfg2 = context(settings={"left_extension_m":.25})
    brg = station(ctx2, families2, cfg2, 0)
    assert brg["phiMn_Nmm"] > 0
    assert brg["strand_trace"][0]["bonded_distance_mm"] == 250
    assert brg["strand_trace"][0]["fpx_limit_MPa"] == pytest.approx(110149/98.7*250/762)


def test_debonded_family_has_zero_force_at_sleeve_exit_and_continuous_strand_taper():
    ctx, families, cfg = context(debonded=True)
    rs = [station(ctx,families,cfg,x) for x in (1.999999,2,2.000001)]
    assert rs[1]["strand_trace"][1]["fpx_limit_MPa"] == 0
    assert rs[2]["strand_trace"][1]["fpx_limit_MPa"] > 0
    assert max(r["phiMn_Nmm"] for r in rs)-min(r["phiMn_Nmm"] for r in rs) < rs[1]["phiMn_Nmm"]*1e-6
    assert families[1].bonded_distance_mm(18) == 0
    assert families[1].bonded_distance_mm(17.5) == 500


def test_full_development_reproduces_reference_and_keeps_individual_nu():
    ctx, families, cfg = context(debonded=True,bars=True,settings={"bars_continuous_confirmed": True})
    for nu in (-100000,0,575159):
        ref = ctx.solve(nu)
        r = station(ctx,families,cfg,10,nu)
        assert r["phiMn_Nmm"] == pytest.approx(ref["phiMn_Nmm"],rel=1e-8)
        assert r["phiPn_N"] == pytest.approx(nu,abs=.021)
        assert r["source_status"] == "PASS"
    assert station(ctx,families,cfg,10,575159)["phiMn_Nmm"] != pytest.approx(station(ctx,families,cfg,10,0)["phiMn_Nmm"])


def test_end_compression_uses_phi_for_both_n_and_m_and_tension_end_has_no_equilibrium():
    ctx, families, cfg = context()
    r = station(ctx,families,cfg,0,575159)
    assert r["phi"] == .75
    assert r["phiPn_N"] == pytest.approx(575159, abs=.021)
    assert r["phiMn_Nmm"] > 0  # External axial compression, not strand credit.
    assert r["Aps_force_N"] == 0
    with pytest.raises(ValueError, match="No directional axial-flexural equilibrium"):
        station(ctx,families,cfg,20,-1492)


def test_ordinary_bar_development_minimum_and_verified_anchorage():
    ctx, _, cfg = context(bars=True)
    factors, traces = ordinary_bar_limits(ctx,x_m=.2,span_m=20,settings=cfg,params={},girder_fc_mpa=45)
    assert factors == [0,0]
    length = traces[0]["ld_full_yield_mm"]
    assert length == pytest.approx(2.4*12*(390/6.894757293168)/math.sqrt(45/6.894757293168)*1.7)
    fs, _ = ordinary_bar_limits(ctx,x_m=0,span_m=20,settings={**cfg,"left_bar_anchored":True},params={},girder_fc_mpa=45)
    assert fs == [1,1]


def test_metadata_roundtrip_and_project_load_clears_previous_widget_and_confirmations():
    from concrete_pmm_pro.io.project_io import project_from_session_state,project_to_json,project_from_json,apply_project_to_session_state
    ctx,_,_=context()
    s={"section_geometry":ctx.ai.section_geometry,"concrete_material":ctx.ai.concrete_material}
    s[SETTINGS_KEY] = {"left_extension_m":.25,"bars_continuous_confirmed":True}
    p = project_from_session_state(s)
    assert p.metadata[SETTINGS_KEY]["left_extension_m"] == .25
    target={SETTINGS_KEY:{"right_extension_m":99},"igird_flexdep_left_extension_m":99}
    apply_project_to_session_state(project_from_json(project_to_json(p)),target)
    assert target[SETTINGS_KEY]["left_extension_m"] == .25
    assert target[SETTINGS_KEY]["right_extension_m"] == 0
    assert "igird_flexdep_left_extension_m" not in target


def test_transition_phi_uses_net_strain_and_same_factor_on_axial_equilibrium():
    ctx,_,_=context()
    trial=ctx.evaluate(600)
    # Net strain at the bottom row: .003*(1400/600-1)=.004,
    # excluding initial prestress. This is a transition section, not phi=1.
    assert trial["eps_t"] == pytest.approx(.004)
    assert trial["phi"] == pytest.approx(11/12)
    solved=ctx.solve(trial["phiPn_N"])
    assert solved["c_mm"] == pytest.approx(600,rel=1e-7)
    assert abs(solved["residual_N"]) < .021


def test_stage_hash_changes_and_production_ui_both_enable_development():
    from concrete_pmm_pro.ui import analysis_page as a
    from concrete_pmm_pro.analysis.uls_strength_routing import beam_girder_uls_strength_route
    route=beam_girder_uls_strength_route(is_bridge=True,is_building=False,project_design_code="AASHTO LRFD",code_edition="9th Edition")
    ctx,_,cfg=context()
    s={"section_geometry":ctx.ai.section_geometry,"concrete_material":ctx.ai.concrete_material,"section_preset_key":"parametric_i_girder"}
    df=pd.DataFrame([{"Case Name":"ULS","Station x (m)":0,"Mux":0,"Nu":0}])
    for fn in (a._beam_uls_construction_flexure_hash,a._beam_uls_final_composite_flexure_hash):
        first=fn(s,df,strength_route=route)
        changed=fn({**s,SETTINGS_KEY:{"left_extension_m":.2}},df,strength_route=route)
        assert first != changed
    source=(Path(a.__file__)).read_text()
    assert source.count("apply_girder_development=True") == 2


@pytest.fixture
def supplied_state():
    from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
    state = {}
    file = Path(__file__).resolve().parents[1] / "qa/fixtures/I_Girder_20m.json"
    apply_project_to_session_state(project_from_json(file.read_text()), state)
    return state


def test_supplied_model_preserves_coupled_rows_nu_and_geometry_and_caps_every_family(supplied_state):
    from concrete_pmm_pro.ui import analysis_page as a
    state = supplied_state
    geometry_before = state["section_geometry"].model_dump()
    route = a._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
    demand, construction, _ = a._beam_uls_construction_demand_from_state(state)
    _, composite, _ = a._beam_uls_final_composite_preparation(state)
    final = a._active_beam_uls_demand_dataframe_from_session(state)
    for stage, source_state, source in [("construction", state, construction), ("final", composite, final)]:
        result, _ = a._beam_uls_flexure_preview_dataframe(source_state, source,
            strength_route=route, prestress_force_stage=stage, full_span_capacity=True,
            use_aashto_solver=True, apply_girder_development=True)
        expected = source.assign(__x=pd.to_numeric(source["Station x (m)"])).sort_values(["Case Name", "__x"], kind="stable")
        assert len(result) == len(source)
        assert list(result["Station x (m)"]) == list(expected["__x"])
        assert list(result["Nu kN"]) == list(pd.to_numeric(expected["Nu"]))
        for _, row in result.iterrows():
            if row["Numerical status"] == "NO EQUILIBRIUM":
                assert stage == "final" and row["Station x (m)"] == 20
                assert math.isnan(row["φMn kN-m"])
                assert row["Status"] == "FAIL"
                continue
            assert abs(row["Force residual N"]) < .021
            assert row["φPn kN"] == pytest.approx(row["Nu kN"], abs=.000021)
            assert row["φMn kN-m"] <= row["Full-development reference φMn kN-m"] * 1.000001
            for trace in row["Strand development trace"]:
                assert 0 <= trace["fps_used_MPa"] <= trace["fpx_limit_MPa"] + 1e-8
                assert trace["fps_used_MPa"] <= trace["fps_reference_MPa"] + 1e-8
        if stage == "construction":
            assert result.iloc[0]["φMn kN-m"] == result.iloc[-1]["φMn kN-m"] == 0
            assert result["φMn kN-m"].tolist() == pytest.approx(result["φMn kN-m"].tolist()[::-1], rel=1e-9)
        else:
            assert result.iloc[0]["Strand force kN"] == 0
            assert result.iloc[0]["φ value"] == .75
            assert result.iloc[0]["φMn kN-m"] > 0
    assert state["section_geometry"].model_dump() == geometry_before


def test_no_equilibrium_plot_has_gap_and_failure_marker_not_zero_capacity():
    from concrete_pmm_pro.ui import analysis_page as a
    source = pd.DataFrame([{"Case Name":"ULS","Station x (m)":x,"Mux":mu,"Nu":nu}
        for x, mu, nu in [(19,100,-10),(20,4,-1.492)]])
    result = pd.DataFrame([{"Case":"ULS","Governing x":"19 m","Demand kN-m":100,
        "Capacity kN-m":200,"Capacity plot sign":1,"Utilization value":.5,
        "Status":"PASS","Numerical status":"PASS"},
        {"Case":"ULS","Governing x":"20 m","Demand kN-m":4,
        "Capacity kN-m":float("nan"),"Capacity plot sign":1,"Utilization value":float("inf"),
        "Status":"FAIL","Numerical status":"NO EQUILIBRIUM"}])
    fig = a._make_beam_uls_flexure_preview_figure(source,result,code_label="AASHTO")
    capacity = next(t for t in fig.data if t.name == "φMn")
    assert list(capacity.x) == [19,20]
    assert capacity.y[0] == 200 and math.isnan(capacity.y[1])
    assert capacity.connectgaps is False
    marker = next(t for t in fig.data if t.name == "Governing flexure check")
    assert list(marker.x) == [20]
    assert list(marker.y) == [4]
    assert list(marker.text) == ["NO EQUILIBRIUM"]


def test_deck_bar_development_uses_actual_diameter_not_smeared_equivalent():
    ctx, _, cfg = context()
    bar = Rebar(x_mm=0, y_mm=1450, diameter_mm=60, material_name="Composite deck longitudinal rebar", label="Top deck")
    ctx.bars = [bar]
    ctx.materials[bar.material_name] = RebarMaterial(name=bar.material_name,fy_MPa=400,Es_MPa=200000)
    factors, trace = ordinary_bar_limits(ctx,x_m=1,span_m=20,settings=cfg,
        params={"deck_long_rebar_top_diameter_mm":16,"deck_fc_MPa":35},girder_fc_mpa=45)
    assert trace[0]["db_mm"] == 16
    assert trace[0]["ld_full_yield_mm"] == pytest.approx(2.4*16*(400/6.894757293168)/math.sqrt(35/6.894757293168)*1.7)
    assert 0 < factors[0] < 1


def test_confirmed_bar_layout_does_not_authorize_pass_with_missing_material():
    ctx, families, cfg = context(bars=True, settings={"bars_continuous_confirmed":True})
    ai = ctx.ai.model_copy(update={"rebar_materials":[]})
    unresolved = SectionEquilibrium(ai,1)
    result = station(unresolved,families,cfg,10)
    assert result["source_status"] == "REVIEW"
    assert "SD40" in result["source_note"]
    assert "fallback" in result["bar_trace"][0]["material_source"]
    assert result["bar_trace"][0]["fy_MPa"] == 390


def test_stale_stage_result_version_is_rejected_even_when_input_hash_matches():
    from concrete_pmm_pro.ui import analysis_page as a
    state = {"section_preset_key":"parametric_i_girder"}
    for name in ("Flexure — Construction", "Flexure — Final Composite"):
        entry = a._beam_uls_store_manual_result(state,name,input_hash="same-input",result={"Status":"REVIEW"})
        assert entry["result_version"].startswith("IGIRDER.FLEXDEP1.")
        assert a._beam_uls_current_cached_result(state,name,"same-input") is not None
        entry["result_version"] = "PREVIOUS_FULL_STRAND_STRENGTH"
        assert a._beam_uls_current_cached_result(state,name,"same-input") is None
