from __future__ import annotations

import math

import pytest

from concrete_pmm_pro.analysis.crossbeam_uls_shear import (
    CROSSBEAM_ULS_SHEAR_RESULT_HASH_KEY,
    CROSSBEAM_ULS_SHEAR_RESULT_KEY,
    _aci_prestressed_vc_n,
    _minimum_av_per_s,
    _spacing_limits_mm,
    build_crossbeam_uls_shear_preparation,
    run_crossbeam_uls_shear,
)
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials
from concrete_pmm_pro.crossbeam.construction_stage import default_column_stage_rows
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.project_geometry import CROSSBEAM_COLUMN_ROWS_KEY
from concrete_pmm_pro.crossbeam.rebar import (
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_DEFINITIONS_KEY,
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY,
    CB_STATION_FORCE_CONTRACT_KEY,
    default_station_force_contract,
)
from concrete_pmm_pro.crossbeam.tendon import (
    TENDON_BOND_STATE_BONDED,
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import (
    CB_PROFILE_ROWS_KEY,
    CB_TENDON_SYSTEM_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.transverse import default_crossbeam_transverse_templates
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows


def _ready_state(*, include_guard_rows: bool = True) -> dict[str, object]:
    length_m = 20.0
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(default_crossbeam_segment_rows(length_m), definitions)
    solid_id = str(definitions[0]["Section ID"])
    for segment in segments:
        segment["Section ID"] = solid_id
        segment["Section role"] = "Solid"

    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)

    tendons = default_tendon_system_rows(3)
    for tendon in tendons:
        tendon["Bond state"] = TENDON_BOND_STATE_BONDED
    tendon_ids = [str(tendon["Tendon ID"]) for tendon in tendons]
    profile = default_tendon_profile_points(
        length_m,
        tendon_ids=tendon_ids,
        width_mm=2500.0,
        height_mm=1500.0,
    )
    link = {
        "ready": True,
        "source_id": "analysis2-ready-source",
        "contract_id": "analysis2-ready-contract",
        "average_total_loss_percent": 20.0,
        "effective_prestress_ratio_percent": 80.0,
        "average_effective_stress_mpa": 1300.0,
    }
    loads = [
        {
            "Active": True,
            "Station s (m)": 5.0,
            "Check Point": "Interior",
            "Case Name": "ULS-INT",
            "P": 5000.0,
            "V2": 320.0,
            "T": 45.0,
            "M3": 2200.0,
            "Note": "interior row",
        }
    ]
    if include_guard_rows:
        loads.extend(
            [
                {
                    "Active": True,
                    "Station s (m)": 10.0,
                    "Check Point": "Joint",
                    "Case Name": "ULS-JOINT",
                    "P": 5000.0,
                    "V2": 410.0,
                    "T": 50.0,
                    "M3": 2600.0,
                    "Note": "physical joint row",
                },
                {
                    "Active": True,
                    "Station s (m)": 1.5,
                    "Check Point": "C1 centerline",
                    "Case Name": "ULS-C1",
                    "P": 6400.0,
                    "V2": 525.0,
                    "T": 35.0,
                    "M3": -3100.0,
                    "Note": "support footprint row",
                },
            ]
        )
    return {
        "crossbeam_ui1_length_m": length_m,
        "crossbeam_ui1_segment_layout_rows": segments,
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        CB_RB_TEMPLATE_ROWS_KEY: longitudinal,
        CB_RB_ZONE_ROWS_KEY: zones,
        CB_TR_TEMPLATE_ROWS_KEY: transverse,
        CB_TENDON_SYSTEM_ROWS_KEY: tendons,
        CB_PROFILE_ROWS_KEY: profile,
        CROSSBEAM_COLUMN_ROWS_KEY: default_column_stage_rows(length_m),
        CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY: link,
        CB_STATION_FORCE_CONTRACT_KEY: default_station_force_contract(
            effective_prestress_link=link
        ),
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        "concrete_materials": default_concrete_materials(),
        "load_cases": [],
        "crossbeam_uls_loads_table": loads,
    }


def test_preparation_maps_row_coupled_demands_and_guards_joint_and_support() -> None:
    state = _ready_state()
    preparation = build_crossbeam_uls_shear_preparation(state)

    assert preparation.ready, preparation.errors
    assert len(preparation.rows) == 3

    interior = next(row for row in preparation.rows if row.case_name == "ULS-INT")
    assert interior.source_p_kn == pytest.approx(5000.0)
    assert interior.source_v2_kn == pytest.approx(320.0)
    assert interior.source_t_knm == pytest.approx(45.0)
    assert interior.source_m3_knm == pytest.approx(2200.0)
    assert interior.location_type == "SEGMENT / ZONE INTERIOR"
    assert interior.transverse_template is not None
    assert len(interior.prestress_groups) == 3

    joint = next(row for row in preparation.rows if row.case_name == "ULS-JOINT")
    assert joint.location_type == "PHYSICAL SEGMENT JOINT"
    assert joint.transverse_template is None

    support = next(row for row in preparation.rows if row.case_name == "ULS-C1")
    assert support.location_type == "COLUMN / SUPPORT D-REGION"
    assert support.transverse_template is None

    rebuilt = build_crossbeam_uls_shear_preparation(state)
    assert rebuilt.fingerprint == preparation.fingerprint
    assert [row.source_signature for row in rebuilt.rows] == [
        row.source_signature for row in preparation.rows
    ]


def test_run_uses_aci_prestressed_route_and_never_certifies_scope_guards() -> None:
    preparation = build_crossbeam_uls_shear_preparation(_ready_state())
    result = run_crossbeam_uls_shear(preparation)

    assert result["status"] == "REVIEW"
    assert result["station_checks"] == 3
    rows = {row["Case"]: row for row in result["rows"]}

    interior = rows["ULS-INT"]
    assert interior["Strength status"] == "PASS"
    assert interior["Status"] in {"PASS", "FAIL", "REVIEW"}
    assert interior["φ"] == pytest.approx(0.75)
    assert interior["φVn kN"] > 0.0
    assert interior["D/C value"] == pytest.approx(abs(interior["V2 kN"]) / interior["φVn kN"])
    assert interior["Code basis"].startswith("ACI 318-19 22.5.6.2")

    assert rows["ULS-JOINT"]["Status"] == "REVIEW"
    assert rows["ULS-JOINT"]["Capacity"] == "Joint shear transfer not checked"
    assert rows["ULS-C1"]["Status"] == "REVIEW"
    assert rows["ULS-C1"]["Capacity"] == "Support D-region not checked"
    assert result["governing_row"]["Status"] == "REVIEW"


def test_interior_only_can_close_with_pass_without_double_counting_prestress() -> None:
    state = _ready_state(include_guard_rows=False)
    preparation = build_crossbeam_uls_shear_preparation(state)
    assert preparation.ready, preparation.errors

    result = run_crossbeam_uls_shear(preparation)
    assert result["status"] == "PASS"
    row = result["rows"][0]
    assert row["Status"] == "PASS"
    assert row["P kN"] == pytest.approx(5000.0)
    assert row["V2 kN"] == pytest.approx(320.0)
    assert "imported FEA demand remains unchanged" in row["Notes"]


def test_missing_applied_column_layout_blocks_support_d_region_identification() -> None:
    state = _ready_state(include_guard_rows=False)
    state.pop(CROSSBEAM_COLUMN_ROWS_KEY)
    preparation = build_crossbeam_uls_shear_preparation(state)

    assert preparation.ready is False
    assert any("Column / Support Layout is missing" in message for message in preparation.errors)


def test_effective_prestress_applicability_gate_returns_review_not_false_pass() -> None:
    state = _ready_state(include_guard_rows=False)
    link = dict(state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY])
    link["average_effective_stress_mpa"] = 50.0
    state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY] = link
    state[CB_STATION_FORCE_CONTRACT_KEY] = default_station_force_contract(
        effective_prestress_link=link
    )

    preparation = build_crossbeam_uls_shear_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_shear(preparation)
    row = result["rows"][0]

    assert result["status"] == "REVIEW"
    assert row["Status"] == "REVIEW"
    assert math.isnan(float(row["φVn kN"]))
    assert "< 0.400" in row["Notes"]
    assert "refined Vci/Vcw" in row["Notes"]


def test_required_shear_reinforcement_without_sectional_credit_fails() -> None:
    state = _ready_state(include_guard_rows=False)
    state["crossbeam_uls_loads_table"][0]["V2"] = 100_000.0
    for template in state[CB_TR_TEMPLATE_ROWS_KEY]:
        template["Credit inside segment"] = False

    preparation = build_crossbeam_uls_shear_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_shear(preparation)
    row = result["rows"][0]

    assert result["status"] == "FAIL"
    assert row["Detailing status"] == "FAIL"
    assert "no sectional Av/s credit" in row["Notes"]


def test_zero_m3_evaluates_both_tension_faces_and_reports_governing_trial() -> None:
    state = _ready_state(include_guard_rows=False)
    state["crossbeam_uls_loads_table"][0]["M3"] = 0.0

    preparation = build_crossbeam_uls_shear_preparation(state)
    assert preparation.ready, preparation.errors
    row = run_crossbeam_uls_shear(preparation)["rows"][0]

    assert "Zero M3" in row["Bending direction"]
    assert "both sagging and hogging" in row["Notes"]
    assert row["d mm"] >= 0.8 * row["h mm"]


def test_aci_vc_helper_matches_table_22_5_6_2_least_and_lower_bound() -> None:
    result = _aci_prestressed_vc_n(
        sqrt_fc_mpa_sqrt=math.sqrt(45.0),
        bw_mm=1000.0,
        d_mm=1200.0,
        dp_mm=1100.0,
        vu_n=800_000.0,
        mu_nmm=2_400_000_000.0,
    )
    sqrt_fc = math.sqrt(45.0)
    expected_a = (0.05 * sqrt_fc + 4.8 * 800_000.0 * 1100.0 / 2_400_000_000.0) * 1000.0 * 1200.0
    expected_b = (0.05 * sqrt_fc + 4.8) * 1000.0 * 1200.0
    expected_c = 0.42 * sqrt_fc * 1000.0 * 1200.0
    expected_lower = 0.17 * sqrt_fc * 1000.0 * 1200.0
    expected = max(min(expected_a, expected_b, expected_c), expected_lower)

    assert result["Vc_a_N"] == pytest.approx(expected_a)
    assert result["Vc_b_N"] == pytest.approx(expected_b)
    assert result["Vc_c_N"] == pytest.approx(expected_c)
    assert result["Vc_lower_N"] == pytest.approx(expected_lower)
    assert result["Vc_N"] == pytest.approx(expected)



def test_aci_minimum_web_reinforcement_uses_prestress_lesser_of_gate() -> None:
    fc = 45.0
    bw = 1000.0
    fyt = 390.0
    d = 1200.0
    aps_fpu = 12_000_000.0
    required, basis, base, prestress_specific = _minimum_av_per_s(
        fc_mpa=fc,
        bw_mm=bw,
        fyt_mpa=fyt,
        d_mm=d,
        aps_fpu_n=aps_fpu,
        prestress_dominant=True,
    )
    expected_base = max(0.062 * math.sqrt(fc) * bw / fyt, 0.35 * bw / fyt)
    expected_specific = aps_fpu / (80.0 * fyt * d) * math.sqrt(d / bw)

    assert base == pytest.approx(expected_base)
    assert prestress_specific == pytest.approx(expected_specific)
    assert required == pytest.approx(min(expected_base, expected_specific))
    assert "lesser-of" in basis


def test_aci_prestressed_spacing_limits_cover_both_required_vs_branches() -> None:
    low = _spacing_limits_mm(
        h_mm=1500.0,
        vs_required_n=100_000.0,
        fc_mpa=45.0,
        bw_mm=1000.0,
        d_mm=1200.0,
    )
    high = _spacing_limits_mm(
        h_mm=1500.0,
        vs_required_n=10_000_000.0,
        fc_mpa=45.0,
        bw_mm=1000.0,
        d_mm=1200.0,
    )

    assert low[0] == pytest.approx(600.0)
    assert low[1] == pytest.approx(600.0)
    assert "≤" in low[2]
    assert high[0] == pytest.approx(300.0)
    assert high[1] == pytest.approx(300.0)
    assert ">" in high[2]


def test_high_strength_vc_sqrt_limit_depends_on_minimum_web_reinforcement() -> None:
    state = _ready_state(include_guard_rows=False)
    state["concrete_materials"] = [
        material.model_copy(update={"fc_MPa": 80.0})
        if material.name == "C45_PRECAST"
        else material
        for material in state["concrete_materials"]
    ]

    credited = run_crossbeam_uls_shear(
        build_crossbeam_uls_shear_preparation(state)
    )["rows"][0]
    assert credited["√f'c actual"] == pytest.approx(math.sqrt(80.0))
    assert credited["√f'c used for Vc"] == pytest.approx(math.sqrt(80.0))

    for template in state[CB_TR_TEMPLATE_ROWS_KEY]:
        template["Credit inside segment"] = False
    uncredited = run_crossbeam_uls_shear(
        build_crossbeam_uls_shear_preparation(state)
    )["rows"][0]
    assert uncredited["√f'c actual"] == pytest.approx(math.sqrt(80.0))
    assert uncredited["√f'c used for Vc"] == pytest.approx(8.3)


def test_transverse_yield_strength_is_capped_at_420_mpa_for_shear() -> None:
    state = _ready_state(include_guard_rows=False)
    for template in state[CB_TR_TEMPLATE_ROWS_KEY]:
        template["Rebar material"] = "SD50"
        template["fy MPa"] = 490.0

    row = run_crossbeam_uls_shear(
        build_crossbeam_uls_shear_preparation(state)
    )["rows"][0]
    assert row["fyt input MPa"] == pytest.approx(490.0)
    assert row["fyt design MPa"] == pytest.approx(420.0)
    assert "capped at 420 MPa" in row["Notes"]

def test_analysis_page_exposes_crossbeam_flexure_and_shear_lazy_tabs() -> None:
    source = open("concrete_pmm_pro/ui/analysis_page.py", encoding="utf-8").read()
    block = source[source.index("def render_analysis_uls_pmm"):source.index("def render_analysis_sls_stress")]
    assert '"Flexure", "Shear"' in block
    assert "_render_crossbeam_uls_flexure_workspace()" in block
    assert "_render_crossbeam_uls_shear_workspace()" in block
    assert "crossbeam_uls_lazy_check" in block


def test_shear_cache_keys_are_crossbeam_namespaced() -> None:
    assert CROSSBEAM_ULS_SHEAR_RESULT_KEY.startswith("crossbeam_")
    assert CROSSBEAM_ULS_SHEAR_RESULT_HASH_KEY.startswith("crossbeam_")
