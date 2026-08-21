import math

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.uls_strength_routing import beam_girder_uls_strength_route
from concrete_pmm_pro.code_checks.aashto_lrfd import (
    aashto_development_area_factor,
    aashto_general_shear_parameters,
    aashto_prestressed_shear_phi,
    aashto_pretensioned_strand_development_length_mm,
    aashto_pretensioned_transfer_fpo_factor,
    aashto_pretensioned_transfer_length_mm,
)
from concrete_pmm_pro.core.aashto_units import inch_to_mm, mpa_to_ksi
from concrete_pmm_pro.core.models import ConcreteMaterial, Point2D, SectionGeometry
from concrete_pmm_pro.ui.analysis_page import (
    _IGIRDER_COMBINED_VT_RESULT_VERSION,
    _IGIRDER_SHEAR_RESULT_VERSION,
    _beam_uls_combined_vt_check_dataframe,
    _beam_uls_current_cached_result,
    _beam_uls_shear_check_dataframe,
    _beam_uls_shear_critical_section_dataframe,
    _beam_uls_shear_diagram_boundary_dataframe,
    _beam_uls_combine_shear_check_frames,
    _beam_uls_shear_design_rows_for_governing,
    _beam_uls_store_manual_result,
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


def _strand_table(*, debonded: bool = False):
    return pd.DataFrame(
        [
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
        ]
    )


def _state(*, debonded: bool = False):
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
        "beam_girder_shear_reinforcement_table": pd.DataFrame(
            [
                {
                    "Active": True,
                    "Zone": "Full span",
                    "x_start_m": 0.0,
                    "x_end_m": 20.0,
                    "Bar Size": "DB12",
                    "Diameter_mm": 12.0,
                    "Legs": 2.0,
                    "Spacing_mm": 150.0,
                    "fy_MPa": 390.0,
                    "Note": "provided",
                }
            ]
        ),
    }


def _demand(x_m: float = 1.20, *, tu_kNm: float = 0.0):
    return pd.DataFrame(
        [
            {
                "Active": True,
                "Station x (m)": x_m,
                "Case Name": "Strength I",
                "Mux": 500.0,
                "Vuy": 400.0,
                "Tu": tu_kNm,
                "Muy": 0.0,
                "Vux": 0.0,
                "Nu": 0.0,
                "Note": "",
            }
        ]
    )


def test_general_procedure_beta_theta_equations_and_limits():
    at_zero = aashto_general_shear_parameters(epsilon_s=0.0, has_minimum_transverse_reinforcement=True)
    assert at_zero.beta == pytest.approx(4.8)
    assert at_zero.theta_deg == pytest.approx(29.0)

    strained = aashto_general_shear_parameters(epsilon_s=0.001, has_minimum_transverse_reinforcement=True)
    assert strained.beta == pytest.approx(4.8 / (1.0 + 750.0 * 0.001))
    assert strained.theta_deg == pytest.approx(29.0 + 3500.0 * 0.001)

    negative = aashto_general_shear_parameters(epsilon_s=-0.002, has_minimum_transverse_reinforcement=True)
    assert negative.epsilon_s_used == 0.0
    assert negative.beta == pytest.approx(4.8)

    upper = aashto_general_shear_parameters(epsilon_s=0.010, has_minimum_transverse_reinforcement=True)
    assert upper.epsilon_s_used == pytest.approx(0.006)
    assert upper.theta_deg == pytest.approx(50.0)


def test_general_procedure_less_than_minimum_transverse_uses_sxe_inch_branch():
    params = aashto_general_shear_parameters(
        epsilon_s=0.001,
        has_minimum_transverse_reinforcement=False,
        sxe_mm=80.0 * 25.4,
    )
    expected = (4.8 / (1.0 + 750.0 * 0.001)) * (51.0 / (39.0 + 80.0))
    assert params.beta == pytest.approx(expected)
    assert params.sxe_in == pytest.approx(80.0)


def test_prestressed_shear_phi_switches_for_debonded_strands():
    bonded, bonded_basis = aashto_prestressed_shear_phi(has_unbonded_or_debonded_strands=False)
    debonded, debonded_basis = aashto_prestressed_shear_phi(has_unbonded_or_debonded_strands=True)
    assert bonded == pytest.approx(0.90)
    assert debonded == pytest.approx(0.85)
    assert "bonded" in bonded_basis.lower()
    assert "debonded" in debonded_basis.lower()


def test_pretensioned_transfer_and_development_are_explicitly_unit_safe():
    db_mm = 15.2
    fpe_mpa = 120_000.0 / 140.0
    fps_mpa = 1670.0
    depth_mm = 1600.0

    transfer = aashto_pretensioned_transfer_length_mm(db_mm)
    assert transfer == pytest.approx(60.0 * db_mm)
    assert aashto_pretensioned_transfer_fpo_factor(bonded_distance_mm=0.0, db_mm=db_mm) == 0.0
    assert aashto_pretensioned_transfer_fpo_factor(bonded_distance_mm=30.0 * db_mm, db_mm=db_mm) == pytest.approx(0.5)
    assert aashto_pretensioned_transfer_fpo_factor(bonded_distance_mm=60.0 * db_mm, db_mm=db_mm) == pytest.approx(1.0)

    ld_mm, kappa, _basis = aashto_pretensioned_strand_development_length_mm(
        fps_MPa=fps_mpa,
        fpe_MPa=fpe_mpa,
        db_mm=db_mm,
        member_depth_mm=depth_mm,
    )
    expected_in = 1.6 * (mpa_to_ksi(fps_mpa) - (2.0 / 3.0) * mpa_to_ksi(fpe_mpa)) * (db_mm / 25.4)
    assert kappa == pytest.approx(1.6)
    assert ld_mm == pytest.approx(inch_to_mm(expected_in))
    assert aashto_development_area_factor(bonded_distance_mm=0.5 * ld_mm, development_length_mm=ld_mm) == pytest.approx(0.5)

    debonded_ld_mm, debonded_kappa, _ = aashto_pretensioned_strand_development_length_mm(
        fps_MPa=fps_mpa,
        fpe_MPa=fpe_mpa,
        db_mm=db_mm,
        member_depth_mm=depth_mm,
        debonded_conservative=True,
    )
    assert debonded_kappa == pytest.approx(2.0)
    assert debonded_ld_mm > ld_mm


def test_igird_shear_uses_general_procedure_and_exposes_station_trace():
    shear = _beam_uls_shear_check_dataframe(_state(), _demand(), strength_route=_route())
    assert len(shear) == 1
    row = shear.iloc[0]
    assert "5.7.3.4.2" in row["Method"]
    assert math.isfinite(float(row["εs raw"]))
    assert math.isfinite(float(row["εs used"]))
    assert float(row["β"]) != pytest.approx(2.0)
    assert float(row["θ deg"]) != pytest.approx(45.0)
    assert float(row["Aps developed tension mm2"]) > 0.0
    assert 0.0 < float(row["Aps development factor min"]) <= 1.0
    assert 0.0 < float(row["fpo transfer factor min"]) <= 1.0
    assert row["φ"] == pytest.approx(0.90)
    assert "5.7.3.4.2" in row["General Procedure branch"]


def test_igird_debonding_changes_phi_and_reduces_end_zone_prestress_participation():
    bonded = _beam_uls_shear_check_dataframe(_state(debonded=False), _demand(x_m=1.20), strength_route=_route()).iloc[0]
    debonded = _beam_uls_shear_check_dataframe(_state(debonded=True), _demand(x_m=1.20), strength_route=_route()).iloc[0]
    assert bonded["φ"] == pytest.approx(0.90)
    assert debonded["φ"] == pytest.approx(0.85)
    assert float(debonded["Aps developed tension mm2"]) < float(bonded["Aps developed tension mm2"])
    assert float(debonded["Aps development factor min"]) < float(bonded["Aps development factor min"])


def test_igird_combined_vt_is_review_until_torsion_theta_route_is_consistent():
    state = _state()
    combined = _beam_uls_combined_vt_check_dataframe(state, _demand(tu_kNm=20.0), strength_route=_route())
    assert not combined.empty
    decision = combined[combined["Status"] != "DIAGRAM BOUNDARY"]
    assert not decision.empty
    assert set(decision["Status"]) == {"REVIEW"}
    assert "PASS" not in set(combined["Status"])
    assert any("theta" in str(note).lower() or "θ" in str(note) for note in decision["Notes"].tolist())


def test_igird_shear_cache_version_is_selective_and_flexure_cache_is_not_invalidated():
    input_hash = "qa-hash"
    cache_key = "_beam_girder_uls_manual_calculation_cache"
    state = {
        "section_preset_key": "parametric_i_girder",
        cache_key: {
            "Shear": {"input_hash": input_hash, "status": "PASS", "check": "Shear"},
            "Flexure — Final Composite": {"input_hash": input_hash, "status": "PASS", "check": "Flexure — Final Composite"},
        },
    }
    assert _beam_uls_current_cached_result(state, "Shear", input_hash) is None
    assert _beam_uls_current_cached_result(state, "Flexure — Final Composite", input_hash) is not None

    _beam_uls_store_manual_result(state, "Shear", input_hash=input_hash, result={"status": "PASS", "result_df": pd.DataFrame([{"Status": "PASS"}])})
    current_shear = _beam_uls_current_cached_result(state, "Shear", input_hash)
    assert current_shear is not None
    assert current_shear["result_version"] == _IGIRDER_SHEAR_RESULT_VERSION

    _beam_uls_store_manual_result(state, "Shear + Torsion", input_hash=input_hash, result={"status": "REVIEW", "result_df": pd.DataFrame([{"Status": "REVIEW"}])})
    current_combined = _beam_uls_current_cached_result(state, "Shear + Torsion", input_hash)
    assert current_combined is not None
    assert current_combined["result_version"] == _IGIRDER_COMBINED_VT_RESULT_VERSION



def test_igird_less_than_minimum_transverse_does_not_invent_sxe_capacity():
    state = _state()
    table = state["beam_girder_shear_reinforcement_table"].copy()
    table.loc[:, "Spacing_mm"] = 600.0
    state["beam_girder_shear_reinforcement_table"] = table
    row = _beam_uls_shear_check_dataframe(state, _demand(), strength_route=_route()).iloc[0]
    assert row["Status"] == "FAIL"
    assert row["Strength status"] == "REVIEW"
    assert row["Detailing status"] == "FAIL"
    assert math.isnan(float(row["β"]))
    assert math.isnan(float(row["sxe mm"]))
    assert "source blocked" in str(row["Capacity"]).lower()
    assert "sx/ag" in str(row["Notes"])


def test_igird_critical_sections_are_inserted_near_dv_and_boundary_rows_do_not_govern():
    state = _state()
    active = pd.DataFrame([
        {"Active": True, "Station x (m)": 0.0, "Case Name": "Strength I", "Mux": 10.0, "Vuy": 500.0, "Tu": 0.0, "Muy": 0.0, "Vux": 0.0, "Nu": 0.0, "Note": ""},
        {"Active": True, "Station x (m)": 10.0, "Case Name": "Strength I", "Mux": 500.0, "Vuy": 100.0, "Tu": 0.0, "Muy": 0.0, "Vux": 0.0, "Nu": 0.0, "Note": ""},
        {"Active": True, "Station x (m)": 20.0, "Case Name": "Strength I", "Mux": 10.0, "Vuy": -500.0, "Tu": 0.0, "Muy": 0.0, "Vux": 0.0, "Nu": 0.0, "Note": ""},
    ])
    station = _beam_uls_shear_check_dataframe(state, active, strength_route=_route())
    critical = _beam_uls_shear_critical_section_dataframe(state, active, strength_route=_route())
    boundary = _beam_uls_shear_diagram_boundary_dataframe(state, active, strength_route=_route())
    assert len(critical) == 2
    assert set(critical["Station type"]) == {"CRITICAL SHEAR SECTION"}
    offsets = pd.to_numeric(critical["Critical offset m"], errors="coerce")
    dvs = pd.to_numeric(critical["dv mm"], errors="coerce") / 1000.0
    assert all(abs(a - b) < 1.0e-6 for a, b in zip(offsets, dvs))
    if not boundary.empty:
        assert set(boundary["Status"]) == {"DIAGRAM BOUNDARY"}
    combined = _beam_uls_combine_shear_check_frames(station, critical, boundary)
    eligible = _beam_uls_shear_design_rows_for_governing(combined)
    assert not eligible.empty
    assert "DIAGRAM BOUNDARY" not in set(eligible["Station type"].astype(str))
    # Exact x=0/L load rows remain diagram demand context once dv critical rows exist.
    eligible_x = pd.to_numeric(eligible["Governing x"].astype(str).str.replace(" m", "", regex=False), errors="coerce")
    assert not any(abs(x) < 1.0e-9 or abs(x - 20.0) < 1.0e-9 for x in eligible_x.dropna())


def test_igird_development_screen_uses_fpu_upper_bound_not_fpy():
    row = _beam_uls_shear_check_dataframe(_state(), _demand(x_m=1.20), strength_route=_route()).iloc[0]
    fpe_mpa = 120_000.0 / 140.0
    expected_ld, _, _ = aashto_pretensioned_strand_development_length_mm(
        fps_MPa=1860.0,
        fpe_MPa=fpe_mpa,
        db_mm=15.2,
        member_depth_mm=1600.0,
    )
    assert float(row["Development length max mm"]) == pytest.approx(expected_ld)
    assert "fps=fpu" in str(row["Notes"])


def test_uls5a_near_support_load_stations_inside_dv_are_diagram_only() -> None:
    """Ordinary stations inside adopted dv must not outrank the critical section."""

    from concrete_pmm_pro.ui.analysis_page import (
        _beam_uls_governing_shear_row,
        _beam_uls_shear_audit_dataframe,
        _beam_uls_shear_near_support_load_indices,
    )

    shear = pd.DataFrame(
        [
            {"Station type": "LOAD STATION", "Governing x": "0.000 m", "Case": "Strength I", "Strength D/C value": 0.90, "Detailing D/C value": 0.20, "Demand kN": 500.0, "Status": "PASS"},
            {"Station type": "LOAD STATION", "Governing x": "1.000 m", "Case": "Strength I", "Strength D/C value": 0.95, "Detailing D/C value": 0.20, "Demand kN": 450.0, "Status": "PASS"},
            {"Station type": "CRITICAL SHEAR SECTION", "Support side": "LEFT", "Critical offset m": 1.051, "Governing x": "1.051 m", "Case": "Strength I", "Strength D/C value": 0.31, "Detailing D/C value": 0.20, "Demand kN": 447.0, "Status": "PASS"},
            {"Station type": "LOAD STATION", "Governing x": "2.000 m", "Case": "Strength I", "Strength D/C value": 0.25, "Detailing D/C value": 0.20, "Demand kN": 400.0, "Status": "PASS"},
            {"Station type": "LOAD STATION", "Governing x": "17.000 m", "Case": "Strength I", "Strength D/C value": 0.32, "Detailing D/C value": 0.20, "Demand kN": -350.0, "Status": "PASS"},
            {"Station type": "CRITICAL SHEAR SECTION", "Support side": "RIGHT", "Critical offset m": 1.051, "Governing x": "18.949 m", "Case": "Strength I", "Strength D/C value": 0.30, "Detailing D/C value": 0.20, "Demand kN": -447.0, "Status": "PASS"},
            {"Station type": "LOAD STATION", "Governing x": "19.000 m", "Case": "Strength I", "Strength D/C value": 0.96, "Detailing D/C value": 0.20, "Demand kN": -450.0, "Status": "PASS"},
            {"Station type": "LOAD STATION", "Governing x": "20.000 m", "Case": "Strength I", "Strength D/C value": 0.99, "Detailing D/C value": 0.20, "Demand kN": -500.0, "Status": "PASS"},
        ]
    )

    excluded = _beam_uls_shear_near_support_load_indices(shear)
    assert excluded == {0, 1, 6, 7}

    eligible = _beam_uls_shear_design_rows_for_governing(shear)
    assert set(eligible["Governing x"]) == {"1.051 m", "2.000 m", "17.000 m", "18.949 m"}

    governing = _beam_uls_governing_shear_row(shear)
    assert governing is not None
    assert governing["Governing x"] == "17.000 m"
    assert governing["Strength D/C value"] == pytest.approx(0.32)

    audit = _beam_uls_shear_audit_dataframe(shear)
    role_by_x = dict(zip(audit["Station x"], audit["Design role"]))
    assert role_by_x["1.000 m"] == "Near-support diagram only"
    assert role_by_x["1.051 m"] == "Critical design section"
    assert role_by_x["17.000 m"] == "Design station"

    status_by_x = dict(zip(audit["Station x"], audit["Status"]))
    assert status_by_x["1.000 m"] == "NON-GOVERNING"
    assert status_by_x["1.051 m"] == "PASS"
    assert status_by_x["17.000 m"] == "PASS"


def test_uls5a_governing_shear_equation_trace_is_read_only_and_complete() -> None:
    from concrete_pmm_pro.ui.analysis_page import (
        _beam_uls_shear_calculation_trace_dataframe,
        _beam_uls_shear_variable_definitions_dataframe,
    )

    row = {
        "εs raw": -0.001067,
        "εs used": 0.0,
        "εs numerator N": -106700.0,
        "εs denominator N": 100000000.0,
        "β": 4.8,
        "θ deg": 29.0,
        "cotθ": 1.804,
        "f'c MPa": 45.0,
        "bw mm": 200.0,
        "dv mm": 1051.35,
        "fy MPa": 390.0,
        "Av/s mm2/mm": 1.0053,
        "Vc kN": 505.61,
        "Vs kN": 1003.91,
        "Vn uncapped kN": 1509.52,
        "Vn limit kN": 2128.98,
        "Vn kN": 1509.52,
        "φ": 0.90,
        "φVn kN": 1358.57,
        "Demand kN": -350.0,
        "Strength D/C value": 0.258,
    }

    trace = _beam_uls_shear_calculation_trace_dataframe(row)
    assert list(trace["Step"]) == [
        "1 · Longitudinal strain εs",
        "2 · Concrete factor β",
        "3 · Compression-field angle θ",
        "4 · Concrete shear resistance Vc",
        "5 · Stirrup shear resistance Vs",
        "6 · Nominal resistance Vn",
        "7 · Factored shear resistance φVn",
        "8 · Strength utilization",
    ]
    assert "raw -1.067‰ → adopted 0.000‰" in trace.iloc[0]["Result"]
    assert "0.083" in trace.iloc[3]["Equation / substitution"]
    assert "min(Vc + Vs + Vp" in trace.iloc[5]["Equation / substitution"]

    definitions = _beam_uls_shear_variable_definitions_dataframe()
    symbols = set(definitions["Symbol"])
    assert {"Vu", "bv", "d", "dv", "εs", "β", "θ", "Vc", "Vs", "Vn", "φVn", "Av/s", "Av/s,min", "smax", "Aps", "fpo", "Vp", "φ"}.issubset(symbols)
