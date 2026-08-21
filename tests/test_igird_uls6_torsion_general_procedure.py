import math

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.uls_strength_routing import beam_girder_uls_strength_route
from concrete_pmm_pro.code_checks import (
    AASHTO_TORSION_TRANSVERSE_FY_MAX_MPA,
    aashto_prestressed_torsion_general_result,
    aashto_torsional_cracking_moment_nmm,
)
from concrete_pmm_pro.core.models import ConcreteMaterial, Point2D, SectionGeometry
from concrete_pmm_pro.ui.analysis_page import (
    _IGIRDER_COMBINED_VT_RESULT_VERSION,
    _IGIRDER_SHEAR_RESULT_VERSION,
    _IGIRDER_TORSION_RESULT_VERSION,
    _beam_uls_check_input_hash,
    _beam_uls_combined_vt_check_dataframe,
    _beam_uls_current_cached_result,
    _beam_uls_store_manual_result,
    _beam_uls_torsion_check_dataframe,
    _beam_uls_torsion_calculation_trace_dataframe,
    _beam_uls_torsion_variable_definitions_dataframe,
)


def _route():
    return beam_girder_uls_strength_route(
        is_bridge=True,
        is_building=False,
        project_design_code="AASHTO LRFD",
        code_edition="AASHTO LRFD 9th Edition",
    )


def _geometry():
    return SectionGeometry(
        name="QA I-Girder",
        outer_polygon=[
            Point2D(x=-400.0, y=0.0),
            Point2D(x=400.0, y=0.0),
            Point2D(x=400.0, y=1600.0),
            Point2D(x=-400.0, y=1600.0),
        ],
    )


def _strand_table(*, debonded=False):
    return pd.DataFrame([
        {
            "Active": True,
            "Group ID": "Bottom",
            "Strand Size": "15.2 mm low-relaxation strand",
            "No. Strands": 20,
            "Area/Strand_mm2": 140.0,
            "Total Aps_mm2": 2800.0,
            "y_mm_from_bottom": 120.0,
            "Pe_transfer/strand_kN": 150.0,
            "Pe_construction/strand_kN": 140.0,
            "Pe_eff_final/strand_kN": 120.0,
            "Left debond m": 1.0 if debonded else 0.0,
            "Right debond m": 1.0 if debonded else 0.0,
            "Debonded strand numbers": "1,2" if debonded else "",
        }
    ])


def _state(*, closed=True, ph_mm=4300.0, debonded=False, fy_mpa=390.0):
    torsion_settings = {
        "closed_loop_confirmed": closed,
        "ph_mm": ph_mm,
        "hoop_centerline_offset_mm": 50.0,
        "longitudinal_perimeter_distribution_confirmed": True,
        "corner_longitudinal_reinforcement_confirmed": True,
        "note": "QA torsion cage",
    }
    return {
        "section_preset_key": "parametric_i_girder",
        "section_preset_name": "Precast I-Girder",
        "section_geometry": _geometry(),
        "concrete_material": ConcreteMaterial(name="Girder", fc_MPa=45.0, density_kg_m3=2400.0),
        "girder_strand_layout_table": _strand_table(debonded=debonded),
        "rebars": [],
        "rebar_materials": [],
        "prestress_elements": [],
        "prestress_materials": [],
        "beam_girder_system_settings": {"span_length_m": 20.0},
        "beam_girder_torsion_settings": torsion_settings,
        "project_metadata": {"beam_girder_torsion_settings": torsion_settings},
        "beam_girder_shear_reinforcement_table": pd.DataFrame([
            {
                "Active": True,
                "Zone": "Full span",
                "x_start_m": 0.0,
                "x_end_m": 20.0,
                "Bar Size": "DB12",
                "Diameter_mm": 12.0,
                "Legs": 2.0,
                "Spacing_mm": 150.0,
                "fy_MPa": fy_mpa,
                "Note": "provided closed hoop",
            }
        ]),
    }


def _demand(*, x=5.0, tu=500.0, vu=400.0, mux=500.0, nu=0.0, muy=0.0):
    return pd.DataFrame([
        {
            "Active": True,
            "Station x (m)": x,
            "Case Name": "Strength I",
            "Mux": mux,
            "Vuy": vu,
            "Tu": tu,
            "Muy": muy,
            "Vux": 0.0,
            "Nu": nu,
            "Note": "",
        }
    ])


def test_code_helper_uses_quarter_phi_tcr_and_solid_veff():
    result = aashto_prestressed_torsion_general_result(
        fc_MPa=45.0,
        Acp_mm2=1_280_000.0,
        Pcp_mm=4_800.0,
        Ao_mm2=1_000_000.0,
        ph_mm=4_300.0,
        tu_Nmm=500.0e6,
        vu_N=400.0e3,
        at_mm2_per_mm=math.pi * 12.0**2 / 4.0 / 150.0,
        fy_MPa=390.0,
        theta_deg=29.0,
        phi=0.90,
        fpc_MPa=1.875,
    )
    assert result.threshold_Nmm == pytest.approx(0.25 * result.phi_tcr_Nmm)
    expected_veff = math.hypot(400.0e3, 0.9 * 4300.0 * 500.0e6 / (2.0 * 1_000_000.0))
    assert result.veff_N == pytest.approx(expected_veff)
    assert result.tn_Nmm > 0.0


def test_igird_torsion_uses_veff_general_procedure_theta_not_fixed_45():
    df = _beam_uls_torsion_check_dataframe(_state(), _demand(), strength_route=_route())
    assert len(df) == 1
    row = df.iloc[0]
    assert row["Threshold status"] == "DESIGN REQUIRED"
    assert math.isfinite(float(row["Veff kN"]))
    assert float(row["Veff kN"]) > 400.0
    assert math.isfinite(float(row["εs raw"]))
    assert float(row["θ deg"]) != pytest.approx(45.0)
    assert "5.7.3.4.2" in str(row["Method"])
    assert float(row["φ"]) == pytest.approx(0.90)
    # Standalone Torsion cannot certify the concurrent longitudinal equation.
    assert row["Status"] in {"REVIEW", "FAIL"}
    if row["Transverse status"] == "PASS" and row["Detailing status"] == "PASS":
        assert row["Status"] == "REVIEW"
        assert row["Longitudinal status"] == "COMBINED CHECK REQUIRED"


def test_igird_torsion_debonding_uses_phi_085():
    row = _beam_uls_torsion_check_dataframe(_state(debonded=True), _demand(), strength_route=_route()).iloc[0]
    assert float(row["φ"]) == pytest.approx(0.85)
    assert "debonded" in str(row["φ policy"]).lower()


def test_igird_torsion_requires_explicit_closed_loop_and_ph_above_threshold():
    row = _beam_uls_torsion_check_dataframe(_state(closed=False, ph_mm=0.0), _demand(), strength_route=_route()).iloc[0]
    assert row["Threshold status"] == "DESIGN REQUIRED"
    assert row["Status"] == "LAYOUT REQUIRED"
    assert "closed" in str(row["Notes"]).lower()


def test_igird_torsion_below_threshold_does_not_require_closed_loop():
    row = _beam_uls_torsion_check_dataframe(_state(closed=False, ph_mm=0.0), _demand(tu=10.0), strength_route=_route()).iloc[0]
    assert row["Status"] == "BELOW THRESHOLD"
    assert row["Transverse status"] == "NOT REQUIRED"
    assert float(row["Threshold kN-m"]) > 10.0


def test_igird_combined_guard_now_points_to_longitudinal_equation_not_fixed_theta():
    combined = _beam_uls_combined_vt_check_dataframe(_state(), _demand(), strength_route=_route())
    decision = combined[combined["Status"] != "DIAGRAM BOUNDARY"]
    assert not decision.empty
    assert set(decision["Status"]) == {"REVIEW"}
    notes = " ".join(decision["Notes"].astype(str).tolist()).lower()
    assert "5.7.3.6.3-1" in notes
    assert "fixed-theta" not in notes


def test_torsion_settings_hash_is_selective_and_result_versions_are_separate():
    state = _state()
    active = _demand()
    shear_hash_1 = _beam_uls_check_input_hash(state, active, strength_route=_route(), check_name="Shear")
    torsion_hash_1 = _beam_uls_check_input_hash(state, active, strength_route=_route(), check_name="Torsion")
    state["beam_girder_torsion_settings"] = {**state["beam_girder_torsion_settings"], "ph_mm": 4400.0}
    shear_hash_2 = _beam_uls_check_input_hash(state, active, strength_route=_route(), check_name="Shear")
    torsion_hash_2 = _beam_uls_check_input_hash(state, active, strength_route=_route(), check_name="Torsion")
    assert shear_hash_1 == shear_hash_2
    assert torsion_hash_1 != torsion_hash_2

    cache_state = {"section_preset_key": "parametric_i_girder"}
    _beam_uls_store_manual_result(cache_state, "Torsion", input_hash="t", result={"status": "REVIEW"})
    _beam_uls_store_manual_result(cache_state, "Shear", input_hash="s", result={"status": "PASS"})
    _beam_uls_store_manual_result(cache_state, "Shear + Torsion", input_hash="c", result={"status": "REVIEW"})
    assert _beam_uls_current_cached_result(cache_state, "Torsion", "t")["result_version"] == _IGIRDER_TORSION_RESULT_VERSION
    assert _beam_uls_current_cached_result(cache_state, "Shear", "s")["result_version"] == _IGIRDER_SHEAR_RESULT_VERSION
    assert _beam_uls_current_cached_result(cache_state, "Shear + Torsion", "c")["result_version"] == _IGIRDER_COMBINED_VT_RESULT_VERSION


def test_torsional_cracking_k_can_be_capped_at_one():
    tcr_k2 = aashto_torsional_cracking_moment_nmm(
        fc_MPa=45.0,
        Acp_mm2=1_280_000.0,
        Pcp_mm=4_800.0,
        shape="solid",
        fpc_MPa=2.0,
        k_max=2.0,
    )
    tcr_k1 = aashto_torsional_cracking_moment_nmm(
        fc_MPa=45.0,
        Acp_mm2=1_280_000.0,
        Pcp_mm=4_800.0,
        shape="solid",
        fpc_MPa=2.0,
        k_max=1.0,
    )
    assert tcr_k1 < tcr_k2


def test_igird_torsion_k_trace_applies_extreme_tension_guard():
    row = _beam_uls_torsion_check_dataframe(
        _state(), _demand(mux=3000.0), strength_route=_route()
    ).iloc[0]
    assert float(row["K max"]) == pytest.approx(1.0)
    assert float(row["K"]) <= 1.0 + 1.0e-12
    assert float(row["Extreme tension MPa"]) > float(row["K tension limit MPa"])
    assert "K <= 1.0" in str(row["K gate status"])


def test_igird_torsion_axial_compression_adjusts_fpc_for_k_with_aashto_sign():
    base = _beam_uls_torsion_check_dataframe(
        _state(), _demand(nu=0.0), strength_route=_route()
    ).iloc[0]
    compression = _beam_uls_torsion_check_dataframe(
        _state(), _demand(nu=1000.0), strength_route=_route()
    ).iloc[0]
    assert float(compression["Nu AASHTO kN"]) == pytest.approx(-1000.0)
    assert float(compression["fpc MPa"]) > float(base["fpc MPa"])


def test_igird_torsion_transverse_fy_is_capped_at_75ksi():
    row = _beam_uls_torsion_check_dataframe(
        _state(fy_mpa=690.0), _demand(), strength_route=_route()
    ).iloc[0]
    assert float(row["fy input MPa"]) == pytest.approx(690.0)
    assert float(row["fy MPa"]) == pytest.approx(AASHTO_TORSION_TRANSVERSE_FY_MAX_MPA)
    assert "5.7.2.7" in str(row["fy policy"])
    assert "75 ksi" in str(row["fy policy"])


def test_torsion_k_allows_axial_tension_to_reduce_k_below_one():
    tcr_zero = aashto_torsional_cracking_moment_nmm(
        fc_MPa=45.0, Acp_mm2=1_280_000.0, Pcp_mm=4_800.0, shape="solid", fpc_MPa=0.0
    )
    tcr_tension_adjusted = aashto_torsional_cracking_moment_nmm(
        fc_MPa=45.0, Acp_mm2=1_280_000.0, Pcp_mm=4_800.0, shape="solid", fpc_MPa=-0.25
    )
    assert tcr_tension_adjusted < tcr_zero


def test_igird_torsion_analysis_trace_exposes_k_and_fy_source_rules():
    row = _beam_uls_torsion_check_dataframe(
        _state(fy_mpa=690.0), _demand(mux=3000.0, nu=250.0), strength_route=_route()
    ).iloc[0].to_dict()
    trace = _beam_uls_torsion_calculation_trace_dataframe(row)
    text = " ".join(trace.astype(str).fillna("").to_numpy().ravel()).lower()
    assert "fpc − nu/ag" in text
    assert "0.19" in text
    assert "5.7.2.7" in text
    defs = _beam_uls_torsion_variable_definitions_dataframe()
    defs_text = " ".join(defs.astype(str).to_numpy().ravel()).lower()
    assert "compression-positive" in defs_text
    assert "75 ksi" in defs_text


def test_igird_torsion_report_qa_trace_is_read_only_source_contract():
    source = open("app.py", encoding="utf-8").read()
    block = source[
        source.index("def _render_report_qa_igird_torsion_equation_trace"):
        source.index("def render_report_qa_workspace")
    ]
    assert "_beam_uls_calculate_selected_check" not in block
    assert "run_pmm_solver" not in block
    assert "run_rc_pmm_solver" not in block
    assert "does not rerun the solver" in block
