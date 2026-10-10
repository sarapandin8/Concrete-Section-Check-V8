"""Independent force benchmarks and ULS7 source/development gates."""
import math
from copy import deepcopy

import pandas as pd
import pytest

import app
from concrete_pmm_pro.analysis.igird_combined_vt import (
    DEVELOPMENT_KEY, RESULT_VERSION, concurrent_vt_si, development_settings,
    nominal_tension_fps, ordinary_development_factor,
)
from concrete_pmm_pro.core.analysis import AnalysisInput, AnalysisSettings, AnalysisModeSettings
from concrete_pmm_pro.core.models import ConcreteMaterial, PrestressElement, Rebar, RebarMaterial
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state, project_from_json, project_from_session_state, project_to_json,
)
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_combined_vt import calculation_trace
from test_igird_uls6_torsion_general_procedure import _state, _demand, _route


def ready_state():
    state = _state()
    state.update({
        "analysis_mode_settings": AnalysisModeSettings(member_type="beam_girder"),
        "project_design_code": "AASHTO LRFD", "code_edition": "AASHTO LRFD 9th Edition",
        "section_has_ordinary_rebar": True, "section_has_prestressing_steel": True,
        "rebars_valid_for_analysis": True,
        "section_parameters": {"composite_enabled": True, "B1_mm": 800.0, "Be_mm": 2400.0,
            "Tslab_mm": 220.0, "deck_fc_MPa": 35.0, "Be_mode": "Manual", "Be_strength_verified": True},
        "rebar_materials": [RebarMaterial(name="SD40", fy_MPa=390.0)],
        "rebars": [Rebar(x_mm=x, y_mm=y, diameter_mm=20.0, material_name="SD40")
            for y in [100.0,1500.0] for x in [-150.0,150.0]],
        DEVELOPMENT_KEY: {"continuous_full_span_confirmed": True, "left_end_anchored_confirmed": True,
            "right_end_anchored_confirmed": True, "development_length_mm": 1000.0, "note": "QA verified full-span bars"},
    })
    state["beam_girder_shear_reinforcement_table"]["Diameter_mm"] = 16.0
    state["beam_girder_shear_reinforcement_table"]["Bar Size"] = "DB16"
    state["beam_girder_shear_reinforcement_table"]["Spacing_mm"] = 100.0
    return state


def check(state=None, **actions):
    state = state or ready_state()
    demand = _demand(x=actions.pop("x",10.0), mux=actions.pop("mux",1000.0),
                vu=actions.pop("vu",200.0),tu=actions.pop("tu",200.0), **actions)
    # Explicitly verified hypothetical interface detailing for this ready QA
    # model. Compute its actual independent check; never fabricate a PASS.
    state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY] = {"stirrups_cross_and_anchored":True}
    prep, composite, _ = ap._beam_uls_final_composite_preparation(state)
    settings = ap._igird_interface_shear_settings_from_state(state)
    source = ap._igird_interface_source_dataframe(demand)
    interface, _ = ap._igird_interface_shear_dataframe(state,source,prep=prep,
        composite_state=composite,settings=settings,strength_route=_route())
    signature = ap._igird_interface_shear_hash(state,source,settings=settings,strength_route=_route())
    ap._beam_uls_store_manual_result(state,ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME,input_hash=signature,
        result={"result_version":ap._IGIRDER_INTERFACE_SHEAR_RESULT_VERSION,"interface_shear_df":interface})
    return ap._beam_uls_combined_vt_check_dataframe(state,demand,strength_route=_route())


def physical(df):
    return df.loc[df["Station type"].eq("LOAD STATION")].iloc[0]


def force_inputs(**changes):
    terms = dict(mu_Nmm=1000e6, nu_compression_positive_N=-200e3, vu_N=500e3, tu_Nmm=150e6,
        phi=.9, fc_MPa=45.0, bv_mm=200.0, dv_mm=1200.0, Ao_mm2=300000.0, ph_mm=4000.0,
        fy_MPa=390.0, cot_theta=1.25, vc_N=300e3, avs_provided=3.0, ats_required=.5,
        avs_minimum=.3, aps_fps_N=2000e3, as_fy_N=300e3)
    terms.update(changes)
    return terms


def test_equation_5_7_3_6_3_1_against_independent_force_benchmark():
    r = concurrent_vt_si(**force_inputs())
    vs_allocated = (3.0-2*.5)*390*1200*1.25
    vs_used = min(vs_allocated,500e3/.9)
    shear_term = abs(500e3/.9)-.5*vs_used
    torsion_term = .45*4000*150e6/(2*300000*.9)
    expected = 1000e6/(.9*1200)+.5*200e3/.9+1.25*math.sqrt(shear_term**2+torsion_term**2)
    assert r["vs_used_N"] == pytest.approx(vs_used)
    assert r["torsion_term_N"] == pytest.approx(500000.0)
    assert r["longitudinal_required_N"] == pytest.approx(expected)
    assert r["longitudinal_dc"] == pytest.approx(expected/2300e3)


def test_compression_positive_app_sign_reduces_longitudinal_demand():
    compression = concurrent_vt_si(**force_inputs(nu_compression_positive_N=200e3))
    tension = concurrent_vt_si(**force_inputs(nu_compression_positive_N=-200e3))
    assert compression["nu_term_N"] == pytest.approx(-100e3/.9)
    assert tension["longitudinal_required_N"]-compression["longitudinal_required_N"] == pytest.approx(200e3/.9)


def test_single_physical_hoop_is_not_counted_twice():
    r = concurrent_vt_si(**force_inputs(avs_provided=1.0, ats_required=.6))
    shear = (500e3/.9-300e3)/(390*1200*1.25)
    assert r["combined_required"] == pytest.approx(max(shear,.3)+2*.6)
    assert r["transverse_dc"] > 1.0
    assert r["available_shear"] == 0.0
    assert r["vs_used_N"] == 0.0


def test_no_torsion_needs_no_ao_ph_and_equals_shear_longitudinal_limit():
    r = concurrent_vt_si(**force_inputs(tu_Nmm=0.0, Ao_mm2=float("nan"), ph_mm=float("nan"), ats_required=0.0))
    assert r["torsion_term_N"] == 0.0
    assert r["longitudinal_required_N"] == pytest.approx(1000e6/(.9*1200)+100e3/.9+1.25*.5*500e3/.9)


@pytest.mark.parametrize("field,value",[("phi",0.0),("Ao_mm2",float("nan")),("vu_N",float("nan")),("aps_fps_N",-1.0)])
def test_force_equation_rejects_invalid_sources(field,value):
    with pytest.raises(ValueError):
        concurrent_vt_si(**force_inputs(**{field:value}))


def test_nominal_fps_matches_closed_form_elastic_rectangular_equilibrium():
    # Analytic independent root: K*c^2 - Aps*(fpe-Ep*ecu)*c - Aps*Ep*ecu*d = 0.
    state = ready_state()
    inp = AnalysisInput(section_geometry=state["section_geometry"],
        concrete_material=ConcreteMaterial(name="40",fc_MPa=40.0),
        prestress_elements=[PrestressElement(x_mm=0,y_mm=120,area_mm2=140,count=70,
            fpu_mpa=1860,fpy_mpa=1670,ep_mpa=195000,initial_stress_mpa=700)],
        settings=AnalysisSettings(code="AASHTO LRFD",prestress_stress_model="linear_cap"))
    from concrete_pmm_pro.code_checks.aashto_lrfd import aashto_alpha1, aashto_beta1
    ecu=inp.concrete_material.ecu; aps=9800.0; d=1480.0
    k=aashto_alpha1(40)*40*800*aashto_beta1(40)
    b=-aps*(700-195000*ecu); cc=-aps*195000*ecu*d
    expected_c=(-b+math.sqrt(b*b-4*k*cc))/(2*k)
    expected_fps=700+195000*ecu*(d/expected_c-1)
    r=nominal_tension_fps(inp,moment_sign=1,axial_nominal_N=0,tension_y_mid_mm=800)
    assert r["ready"]
    assert r["c_mm"] == pytest.approx(expected_c,rel=1e-6)
    assert r["fps_min_MPa"] == pytest.approx(expected_fps,rel=1e-6)
    assert abs(r["residual_N"]) <= .1
    assert 0 < r["fps_min_MPa"] < 1860


@pytest.mark.parametrize("x,expected",[(0.0,0.0),(.25,0),(.5,.5),(1.0,1.0),(10.0,1.0),(19.5,.5),(20.0,0.0)])
def test_ordinary_bar_development_and_end_symmetry(x,expected):
    settings={"continuous_full_span_confirmed":True,"development_length_mm":1000.0}
    assert ordinary_development_factor(settings,x_m=x,span_m=20.0) == expected


def test_continuity_and_anchorage_are_never_assumed():
    assert ordinary_development_factor({},x_m=10,span_m=20) is None
    assert ordinary_development_factor({"continuous_full_span_confirmed":True},x_m=10,span_m=20) is None
    settings={"continuous_full_span_confirmed":True,"left_end_anchored_confirmed":True,
        "right_end_anchored_confirmed":True}
    assert ordinary_development_factor(settings,x_m=0,span_m=20) == 1.0


def test_verified_low_concurrent_actions_can_pass_and_trace_uses_stored_values():
    r=physical(check())
    assert r["Status"] == "PASS", r["Notes"]
    assert r["Threshold status"] == "DESIGN REQUIRED"
    assert r["Result version"] == RESULT_VERSION
    assert 0 < r["fps nominal min MPa"] < 1860
    assert r["Aps fps kN"] == pytest.approx(r["Aps developed tension mm2"]*r["fps nominal min MPa"]/1000)
    expected=(r["Mu term kN"]+r["Nu term kN"]+r["θ cot"]*math.hypot(r["Shear term kN"],r["Torsion term kN"]))
    assert r["Longitudinal required kN"] == pytest.approx(expected)
    assert "5.7.3.6.3-1" in " ".join(calculation_trace(r.to_dict())["Code basis"])


def test_missing_development_never_reports_pass_and_receives_zero_as_credit():
    state=ready_state(); state.pop(DEVELOPMENT_KEY)
    r=physical(check(state))
    assert r["Status"] in {"REVIEW","FAIL"}
    assert r["Development status"] == "REVIEW"
    assert r["As fy kN"] == 0.0


@pytest.mark.parametrize("confirmation",["corner_longitudinal_reinforcement_confirmed","longitudinal_perimeter_distribution_confirmed"])
def test_missing_physical_longitudinal_confirmation_withholds_pass(confirmation):
    state=ready_state();state["beam_girder_torsion_settings"][confirmation]=False
    assert physical(check(state))["Status"] == "REVIEW"


def test_unverified_composite_width_withholds_pass():
    state=ready_state();state["section_parameters"]["Be_strength_verified"]=False
    r=physical(check(state))
    assert r["Status"] == "REVIEW"
    assert "effective width" in r["Notes"]


def test_insufficient_transverse_or_longitudinal_strength_fails():
    # Direct-code moment minimum now leaves the old 1000 kN-m fixture below
    # transverse resistance. Use a independently confirmed actual failure.
    transverse=physical(check(tu=1500.0))
    assert transverse["Transverse status"] == "FAIL"
    assert transverse["Status"] == "FAIL"
    longitudinal=physical(check(mux=10000.0))
    assert longitudinal["Longitudinal D/C value"] > 1.0
    assert longitudinal["Status"] == "FAIL"


def test_physical_supports_and_zero_moment_both_halves_remain_eligible():
    df=check(x=0,mux=0.0)
    supports=df.loc[df["Station type"].eq("LOAD STATION")]
    assert set(supports["Tension face"]) == {"BOTTOM","TOP"}
    assert set(supports["Support side"]) == {"LEFT"}
    assert not supports["Status"].eq("BOUNDARY SKIPPED").any()
    assert supports["Mu kN-m"].eq(0.0).all()


def test_reference_m2_and_invalid_primary_actions():
    base = physical(check())
    reference = physical(check(muy=100.0))
    assert reference["Status"] == base["Status"]
    assert reference["Overall D/C value"] == pytest.approx(base["Overall D/C value"])
    assert reference["M2 reference kN-m"] == 100.0
    r=physical(check(nu=float("nan")))
    assert r["Status"] == "REVIEW"
    assert math.isnan(r["Overall D/C value"])


def test_zone_gap_is_data_required_and_strength_curve_stays_gap():
    state=ready_state();state["beam_girder_shear_reinforcement_table"]["x_end_m"]=8.0
    r=physical(check(state))
    assert r["Status"] == "DATA REQUIRED"
    assert r["Coverage status"] == "REQUIRED"
    assert math.isnan(r["Overall D/C value"])


def test_different_vectors_at_one_case_station_are_not_enveloped():
    actions=pd.concat([_demand(x=10,mux=1000,vu=100,tu=100),_demand(x=10,mux=300,vu=400,tu=60)],ignore_index=True)
    df=ap._beam_uls_combined_vt_check_dataframe(ready_state(),actions,strength_route=_route())
    physical_rows=df.loc[df["Station type"].eq("LOAD STATION")]
    assert set(zip(physical_rows["Mu kN-m"],physical_rows["Vu kN"],physical_rows["Tu kN-m"])) == {(1000.0,100.0,100.0),(300.0,400.0,60.0)}
    assert set(physical_rows["Status"]) == {"REVIEW"}


def test_development_hash_changes_all_three_vt_checks():
    state=ready_state(); actions=_demand()
    before={c:ap._beam_uls_check_input_hash(state,actions,strength_route=_route(),check_name=c) for c in ["Flexure","Shear","Torsion","Shear + Torsion"]}
    state[DEVELOPMENT_KEY]["left_end_anchored_confirmed"]=False
    after={c:ap._beam_uls_check_input_hash(state,actions,strength_route=_route(),check_name=c) for c in before}
    assert all(before[c] != after[c] for c in ["Shear","Torsion","Shear + Torsion"])
    assert before["Flexure"] == after["Flexure"]
    assert ap._IGIRDER_TORSION_RESULT_VERSION.startswith("IGIRDER.DECKULS1.")


def test_summary_rejects_stale_combined_development_without_solving(monkeypatch):
    state=ready_state();state["beam_uls_loads_table"]=_demand(x=10,mux=1000,vu=200,tu=100)
    active=ap._active_beam_uls_demand_dataframe_from_session(state)
    route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    df=ap._beam_uls_combined_vt_check_dataframe(state,active,strength_route=route)
    ap._beam_uls_store_manual_result(state,"Shear + Torsion",input_hash=ap._beam_uls_check_input_hash(state,active,strength_route=route,check_name="Shear + Torsion"),result={"combined_vt_df":df})
    monkeypatch.setattr(ap,"_beam_uls_calculate_selected_check",lambda *a,**k:pytest.fail("Summary must not solve"))
    assert "Shear + Torsion" in app._results_beam_uls_cache(state)
    state[DEVELOPMENT_KEY]["continuous_full_span_confirmed"]=False
    assert "Shear + Torsion" not in app._results_beam_uls_cache(state)


def test_summary_unresolved_row_controls_over_numerical_pass():
    df=pd.DataFrame([{"Status":"PASS","Overall D/C value":.9,"Governing x":"5.000 m"},
                     {"Status":"REVIEW","Overall D/C value":float("nan"),"Governing x":"10.000 m"}])
    assert app._results_beam_uls_best_row({"result_version":RESULT_VERSION,"combined_vt_df":df},"Shear + Torsion")["Status"] == "REVIEW"


def test_project_roundtrip_and_loading_legacy_clears_previous_development():
    state=ready_state()
    project=project_from_session_state(state)
    restored={DEVELOPMENT_KEY:{"continuous_full_span_confirmed":False},"igird_vt_bars_left_anchor":False,
        "beam_girder_torsion_settings":{"longitudinal_perimeter_distribution_confirmed":False,"clear_cover_mm":1000.0},
        "beam_girder_torsion_perimeter_longitudinal_confirmed":False}
    apply_project_to_session_state(project_from_json(project_to_json(project)),restored)
    assert development_settings(restored) == development_settings(state)
    assert "igird_vt_bars_left_anchor" not in restored
    assert restored["beam_girder_torsion_settings"] == state["beam_girder_torsion_settings"]
    assert "beam_girder_torsion_perimeter_longitudinal_confirmed" not in restored
    project.metadata.pop(DEVELOPMENT_KEY,None)
    project.metadata.pop("beam_girder_torsion_settings",None)
    apply_project_to_session_state(project,restored)
    assert development_settings(restored)["continuous_full_span_confirmed"] is False
    assert restored["beam_girder_torsion_settings"] == {}


def test_report_trace_does_not_call_solver(monkeypatch):
    state=ready_state();df=check(state)
    state["_beam_girder_uls_manual_calculation_cache"]={"Shear + Torsion":{"result_version":RESULT_VERSION,"combined_vt_df":df}}
    monkeypatch.setattr(ap,"_beam_uls_calculate_selected_check",lambda *a,**k:pytest.fail("Report must not solve"))
    monkeypatch.setattr("concrete_pmm_pro.ui.igird_combined_vt.nominal_tension_fps",lambda *a,**k:pytest.fail("Report must not solve nominal fps"))
    app._render_report_qa_igird_combined_vt_equation_trace(state)


def test_nominal_fps_uses_developed_ordinary_area_and_excludes_optional_deck_bars(monkeypatch):
    import concrete_pmm_pro.ui.igird_combined_vt as vt
    real=vt.nominal_tension_fps; captured=[]
    def capture(inp,**kwargs):
        captured.append(inp)
        return real(inp,**kwargs)
    monkeypatch.setattr(vt,"nominal_tension_fps",capture)
    state=ready_state()
    state[DEVELOPMENT_KEY]["left_end_anchored_confirmed"]=False
    state[DEVELOPMENT_KEY]["development_length_mm"]=20000.0
    state["section_parameters"].update({"deck_long_rebar_credit_positive_mn":True,
        "deck_long_rebar_fy_MPa":400.0,"deck_long_rebar_Es_MPa":200000.0,
        "deck_long_rebar_top_diameter_mm":16.0,"deck_long_rebar_top_spacing_mm":200.0,
        "deck_long_rebar_top_cover_mm":50.0})
    check(state,x=10.0)
    assert captured
    nominal=next(i for i in captured if len(i.rebars)==4 and abs(i.rebars[0].area_mm2-state["rebars"][0].area_mm2*.5)<1e-5)
    assert {(b.x_mm,b.y_mm,b.material_name) for b in nominal.rebars} == {(b.x_mm,b.y_mm,b.material_name) for b in state["rebars"]}


def test_debonded_source_reduces_developed_aps_and_uses_existing_phi_policy():
    state=ready_state();bonded=physical(check(state,x=2.0))
    state["girder_strand_layout_table"].loc[0,"Debonded strand numbers"]="1,2"
    state["girder_strand_layout_table"].loc[0,"Left debond m"]=1.0
    state["girder_strand_layout_table"].loc[0,"Right debond m"]=1.0
    debonded=physical(check(state,x=2.0))
    assert bonded["φ"] == .9
    assert debonded["φ"] == .85
    assert debonded["Aps developed tension mm2"] < bonded["Aps developed tension mm2"]


def test_summary_component_pass_requires_current_combined_and_all_coverage():
    state=ready_state();actions=_demand(x=10,tu=200,mux=1000,vu=200)
    tdf=ap._beam_uls_torsion_check_dataframe(state,actions,strength_route=_route())
    cache={"Torsion":{"torsion_check_df":tdf,"torsion_coverage_summary":ap._beam_uls_torsion_coverage_summary(tdf)},
        "Shear + Torsion":{"result_version":RESULT_VERSION,"combined_vt_df":check(state)}}
    row=app._results_beam_uls_best_row(cache["Torsion"],"Torsion")
    assert app._results_beam_uls_row_status("Torsion",row,cache) == "PASS — COMPONENT"
    cache["Torsion"]["torsion_coverage_summary"]["status"]="REQUIRED"
    assert app._results_beam_uls_row_status("Torsion",row,cache) == "REVIEW"


def test_overall_summary_accepts_resolved_component_without_mutating_torsion():
    from test_igird_uls5_result_summary import _base_state
    state=_base_state(); cache=state["_beam_girder_uls_manual_calculation_cache"]
    model=ready_state(); actions=_demand(x=10,tu=200,mux=1000,vu=200)
    tdf=ap._beam_uls_torsion_check_dataframe(model,actions,strength_route=_route())
    cache["Torsion"].update(torsion_check_df=tdf,torsion_coverage_summary=ap._beam_uls_torsion_coverage_summary(tdf))
    cache["Shear + Torsion"]["combined_vt_df"]=check(model)
    rows=app._results_beam_uls_summary_rows(state)
    by_check={row["Check"]:row for row in rows}
    assert by_check["Torsion"]["Status"] == "PASS — COMPONENT"
    assert by_check["Overall ULS"]["Status"] == "PASS"
    assert set(tdf["Status"]) == {"REVIEW"}


def test_lightweight_and_missing_nominal_strand_sources_are_review():
    state=ready_state();state["concrete_material"].density_kg_m3=1800
    assert physical(check(state))["Status"] == "REVIEW"
    inp=AnalysisInput(section_geometry=state["section_geometry"],concrete_material=state["concrete_material"],
        rebar_materials=state["rebar_materials"],rebars=state["rebars"])
    assert nominal_tension_fps(inp,moment_sign=1,axial_nominal_N=0,tension_y_mid_mm=800)["ready"] is False


def test_uls7_chart_coalesces_two_halves_conservatively_and_preserves_real_gap():
    rows=[]
    for x in [0,1,2]:
        for face,dc in [("BOTTOM",.8),("TOP",.9)]:
            rows.append({"Governing x":f"{x:.3f} m","Case":"C","Status":"PASS","Tension face":face,
                "Result version":RESULT_VERSION,"Station type":"LOAD STATION",
                "Stress D/C value":.4,"Transverse D/C value":.5,"Longitudinal D/C value":dc})
    rows[3]["Status"]="REVIEW";rows[3]["Longitudinal D/C value"]=float("nan")
    plot=ap._beam_uls_combined_vt_plot_dataframe(pd.DataFrame(rows))
    assert len(plot)==3
    values=plot.set_index("__x_m")["Longitudinal D/C value"]
    assert values.loc[0]==.9
    assert math.isnan(values.loc[1])
    assert values.loc[2]==.9


def test_real_transverse_ui_can_confirm_perimeter_and_unlock_concurrent_pass():
    # Existing test modules install a lightweight Streamlit stub. Use a fresh
    # interpreter to verify the actual production widget/event lifecycle.
    import subprocess, sys
    source="""
import sys
sys.path.insert(0,'tests')
import streamlit as st
from test_igird_uls7_concurrent_vt import ready_state
from concrete_pmm_pro.ui.rebar_page import _render_igird_torsion_layout_settings
if 'qa_seeded' not in st.session_state:
 state=ready_state()
 state['beam_girder_torsion_settings']['longitudinal_perimeter_distribution_confirmed']=False
 state['beam_girder_torsion_zone_settings']=[{'Zone':'Full span','Use for Torsion':True,'Closed Loop':True,'135° Hook':True}]
 st.session_state.update(state);st.session_state['qa_seeded']=True
_render_igird_torsion_layout_settings(st.session_state['beam_girder_shear_reinforcement_table'])
"""
    script=f"""
import sys
sys.path.insert(0,'tests')
from streamlit.testing.v1 import AppTest
from test_igird_uls7_concurrent_vt import physical,check
source={source!r}
at=AppTest.from_string(source,default_timeout=40).run()
assert not at.exception
checkbox=next(c for c in at.checkbox if c.key=='beam_girder_torsion_perimeter_longitudinal_confirmed')
assert not checkbox.disabled
assert physical(check(dict(at.session_state.filtered_state)))['Status']=='REVIEW'
checkbox.check().run()
assert not at.exception
assert at.session_state['beam_girder_torsion_settings']['longitudinal_perimeter_distribution_confirmed'] is True
assert at.session_state['project_metadata']['beam_girder_torsion_settings']['longitudinal_perimeter_distribution_confirmed'] is True
assert physical(check(dict(at.session_state.filtered_state)))['Status']=='PASS'
"""
    result=subprocess.run([sys.executable,"-c",script],capture_output=True,text=True,timeout=60)
    assert result.returncode==0, result.stderr[-4000:]
