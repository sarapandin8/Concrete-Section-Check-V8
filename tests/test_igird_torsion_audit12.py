"""Direct-code strain and separately disclosed conservative review regressions."""
from copy import deepcopy
import math

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.igird_combined_vt import concurrent_vt_si
from concrete_pmm_pro.ui import analysis_page as ap, igird_shear_section
from concrete_pmm_pro.ui.igird_combined_vt import calculation_trace
from qa.igird_torsion_audit12 import hypothetical_state, reference
from test_igird_uls6_torsion_general_procedure import _demand, _route
from test_igird_uls7_concurrent_vt import check, physical, force_inputs


@pytest.mark.parametrize("mu,vu,veff", [(0, 300, 3000), (500, -300, 3000),
    (-500, 300, 3000), (5000, 300, 3000)])
def test_moment_minimum_retains_actual_shear_when_only_equation_shear_is_replaced(mu, vu, veff):
    state = hypothetical_state()
    row = _demand(x=10, mux=mu, vu=vu, tu=410).iloc[0]
    inp, _ = igird_shear_section.analysis_input_for_station(state, row=row,
        strength_route=_route(), capacity_direction=-1 if mu < 0 else 1)
    result = ap._beam_uls_igird_general_shear_epsilon(state, analysis_input=inp,
        x_m=10, span_length_m=20, tension_face="bottom", mux_kNm=mu,
        vu_kN=vu, nu_compression_positive_kN=0, dv_mm=1600, effective_shear_kN=veff)
    assert result["Mu_min_Nmm"] == pytest.approx(abs(vu)*1000*1600)
    assert result["Mu_used_Nmm"] == pytest.approx(max(abs(mu)*1e6, abs(vu)*1000*1600))
    assert result["Veff used kN"] == veff
    expected_num = result["Mu_used_Nmm"]/1600 + veff*1000-result["Aps_fpo_N"]
    assert result["epsilon_s_raw"] == pytest.approx(expected_num/result["denominator_N"])


@pytest.mark.parametrize("mu,tu,expected", [(500,410,723.0334802314),
    (500,500,663.4272357908), (2500,450,557.6060755973), (5000,410,440.5638628948)])
def test_direct_us_equations_on_a_real_haunched_I_shape(mu, tu, expected):
    state = hypothetical_state()
    combined = physical(check(state, x=10, mux=mu, vu=300, tu=tu))
    t = ap._beam_uls_torsion_check_dataframe(state, _demand(x=10,mux=mu,vu=300,tu=tu), strength_route=_route()).iloc[0]
    independent = reference(t, mu=mu, vu=300, tu=tu)
    assert t["φTn kN-m"] == pytest.approx(expected, rel=2e-10)
    assert t["φTn kN-m"] == pytest.approx(independent["phiTn_kNm"], rel=2e-10)
    assert t["θ deg"] == pytest.approx(independent["theta_deg"])
    assert combined["θ deg"] == pytest.approx(t["θ deg"])
    assert t["Ao mm2"] == pytest.approx(283951.01106327056)
    assert t["ph mm"] == pytest.approx(4709.010659580074)


def test_additional_veff_screen_requires_review_without_fabricating_code_failure():
    row = physical(check(hypothetical_state(), x=10, mux=2500, vu=300, tu=450))
    assert row["Stress D/C value"] == pytest.approx(.09250908580874163)
    assert row["Conservative Veff guard D/C"] == pytest.approx(1.0396817991479042)
    assert row["Conservative Veff guard status"] == "REVIEW"
    assert row["Stress status"] == "PASS"
    assert row["Transverse status"] == "PASS"
    assert row["Longitudinal status"] == "PASS"
    assert row["Overall D/C value"] == pytest.approx(.878004994029488)
    assert row["Status"] == "REVIEW"  # No automatic sectional certificate.


def test_actual_transverse_failure_survives_removal_of_additional_screen_from_code_ratio():
    row = physical(check(hypothetical_state(), x=10, mux=2500, vu=300, tu=500))
    assert row["Status"] == "FAIL"
    assert row["Transverse D/C value"] == pytest.approx(1.0332732025679454)
    assert "Transverse" in row["Failure reason"]


def test_partial_material_source_keeps_known_shear_and_guard_but_no_overall_resistance():
    state = hypothetical_state()
    state["rebar_materials"] = []
    row = physical(check(state, x=10, mux=2500, vu=300, tu=450))
    assert row["Calculation status"] == "PARTIAL"
    assert math.isnan(row["Overall D/C value"])
    assert row["Longitudinal status"] == "DATA REQUIRED"
    assert row["Stress status"] == "PASS"
    assert row["Conservative Veff guard status"] == "REVIEW"


def test_pure_concurrent_function_discloses_both_ratios():
    args = force_inputs()
    row = concurrent_vt_si(**args)
    capacity = args["phi"] * .25 * args["fc_MPa"] * args["bv_mm"] * args["dv_mm"]
    assert row["strut_dc"] == pytest.approx(abs(args["vu_N"])/capacity)
    assert row["veff_guard_dc"] == pytest.approx(math.hypot(args["vu_N"],
        .9*args["ph_mm"]*args["tu_Nmm"]/(2*args["Ao_mm2"]))/capacity)


def test_larger_deck_does_not_invent_torsion_shear_flow_or_hoop_area():
    def torsion(state):
        return ap._beam_uls_torsion_check_dataframe(state,
            _demand(x=10, mux=2500, vu=300, tu=410),strength_route=_route()).iloc[0]
    first = hypothetical_state()
    larger = deepcopy(first)
    larger["section_parameters"].update(Be_mm=4000.0,Tslab_mm=300.0)
    a,b = torsion(first),torsion(larger)
    for key in ("Acp mm2", "Pcp mm", "Ao mm2", "ph mm"):
        assert a[key] == b[key]
    assert a["dv mm"] != b["dv mm"]  # Composite flexural strain still participates.


def test_equation_traces_show_actual_shear_moment_floor_and_separate_review():
    state = hypothetical_state()
    r = physical(check(state,x=10,mux=2500,vu=300,tu=450))
    trace = calculation_trace(r.to_dict())
    assert "Strain moment minimum" in trace["Step"].tolist()
    screen = trace.loc[trace["Step"].eq("Additional Veff screen")].iloc[0]
    assert "excluded" in screen["Code basis"]
    t = ap._beam_uls_torsion_check_dataframe(state,
        _demand(x=10,mux=2500,vu=300,tu=450),strength_route=_route()).iloc[0]
    t_trace = ap._beam_uls_torsion_calculation_trace_dataframe(t.to_dict())
    assert t_trace["Equation / substitution"].str.contains("using actual Vu",regex=False).any()


def test_old_torsion_result_cache_cannot_be_accepted_under_corrected_strain_version():
    state = hypothetical_state()
    old = ap._beam_uls_store_manual_result(state,"Torsion",input_hash="QA",result={})
    # Simulate a cache created by MAXMIN10, not a newly stored current result.
    old["result_version"] = igird_shear_section.RESULT_VERSION+".torsion.chart3"
    assert ap._beam_uls_current_cached_result(state,"Torsion","QA") is None


def test_input_tables_are_unchanged_by_audit_calculation():
    state = hypothetical_state()
    demand = _demand(x=10,mux=2500,vu=300,tu=450)
    before_demand = demand.copy(deep=True)
    before_steel = state["beam_girder_shear_reinforcement_table"].copy(deep=True)
    ap._beam_uls_torsion_check_dataframe(state,demand,strength_route=_route())
    pd.testing.assert_frame_equal(demand,before_demand)
    pd.testing.assert_frame_equal(state["beam_girder_shear_reinforcement_table"],before_steel)
