from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.crossbeam_uls import (
    build_crossbeam_uls_flexure_preparation,
    run_crossbeam_uls_flexure,
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



def _center_column_rows(length_m: float) -> list[dict[str, object]]:
    row = dict(default_column_stage_rows(length_m)[0])
    row["Column ID"] = "C1"
    row["Station s (m)"] = 0.5 * length_m
    row["Blong (mm)"] = 2000.0
    return [row]


def _support_source_rows(case_name: str, *, p_kn: float = 5000.0) -> list[dict[str, object]]:
    return [
        {
            "Active": True,
            "Station s (m)": station,
            "Check Point": "",
            "Case Name": case_name,
            "P": p_kn,
            "V2": 0.0,
            "T": 0.0,
            "M3": moment,
            "Note": "exact Column Face source row",
        }
        for station, moment in ((9.0, 2400.0), (11.0, 2400.0))
    ]

def _ready_state() -> dict[str, object]:
    length_m = 20.0
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(default_crossbeam_segment_rows(length_m), definitions)
    # Make every segment use one solid Section ID so the test isolates the
    # physical-joint continuity rule from a geometry transition.
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
    profile_rows = [
        {
            "Tendon": tendon_id,
            "Station s (m)": station,
            "Point": point,
            "Aps (mm²)": float(tendon["Strands"]) * float(tendon["Aps/strand mm²"]),
            "fpj (MPa)": float(tendon["fpu MPa"]) * float(tendon["fpj/fpu"]),
            "fpe (MPa)": 1116.0,
        }
        for tendon in tendons
        for tendon_id in [str(tendon["Tendon ID"])]
        for station, point in ((0.0, "P1"), (0.5 * length_m, "P2"), (length_m, "P3"))
    ]
    link = {
        "schema": "crossbeam-effective-prestress-loads-link-v2",
        "ready": True,
        "source_id": "analysis1a-ready-source",
        "contract_id": "analysis1a-ready-contract",
        "average_total_loss_percent": 20.0,
        "effective_prestress_ratio_percent": 80.0,
        "average_effective_stress_mpa": 1116.0,
        "member_length_m": length_m,
        "profile_ready": True,
        "tendon_station_profiles": profile_rows,
        "allow_uniform_average_uls_override": False,
    }
    return {
        "crossbeam_ui1_length_m": length_m,
        "crossbeam_ui1_segment_layout_rows": segments,
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        CB_RB_TEMPLATE_ROWS_KEY: longitudinal,
        CB_RB_ZONE_ROWS_KEY: zones,
        CB_TR_TEMPLATE_ROWS_KEY: transverse,
        CB_TENDON_SYSTEM_ROWS_KEY: tendons,
        CB_PROFILE_ROWS_KEY: profile,
        CROSSBEAM_COLUMN_ROWS_KEY: _center_column_rows(length_m),
        CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY: link,
        CB_STATION_FORCE_CONTRACT_KEY: default_station_force_contract(
            effective_prestress_link=link
        ),
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        "concrete_materials": default_concrete_materials(),
        # Deliberately empty: Crossbeam ANALYSIS1A must not depend on the
        # generic Column/Pier load-case table.
        "load_cases": [],
        "crossbeam_uls_loads_table": [
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
            },
            *_support_source_rows("ULS-INT"),
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
            *_support_source_rows("ULS-JOINT"),
        ],
    }


def test_crossbeam_adapter_runs_without_generic_load_cases_and_preserves_row_coupling() -> None:
    state = _ready_state()
    preparation = build_crossbeam_uls_flexure_preparation(state)

    assert preparation.ready, preparation.errors
    assert len(preparation.derived_support_rows) == 4
    interior = next(
        row for row in preparation.rows
        if row.case_name == "ULS-INT" and row.check_point == "Interior"
    )
    joint_rows = [
        row for row in preparation.rows
        if row.case_name == "ULS-JOINT" and row.location_type == "PHYSICAL SEGMENT JOINT"
    ]
    assert len(joint_rows) == 2
    joint = joint_rows[0]

    assert interior.analysis_input.load_cases[0].Pu_N == pytest.approx(5_000_000.0)
    assert interior.analysis_input.load_cases[0].Mux_Nmm == pytest.approx(2_200_000_000.0)
    assert interior.source_v2_kn == pytest.approx(320.0)
    assert interior.source_t_knm == pytest.approx(45.0)
    assert interior.ordinary_rebar_count == 0
    assert interior.rebar_credit_status == "TENDON-ONLY"
    assert interior.bonded_tendon_count == 3

    assert joint.location_type == "PHYSICAL SEGMENT JOINT"
    assert joint.ordinary_rebar_count == 0
    assert joint.bonded_tendon_count == 3
    assert joint.analysis_input.load_cases[0].Mux_Nmm == pytest.approx(2_600_000_000.0)

    # Runtime-generated Rebar/Tendon UUIDs must not invalidate the result cache.
    rebuilt = build_crossbeam_uls_flexure_preparation(state)
    assert rebuilt.fingerprint == preparation.fingerprint
    assert [row.capacity_signature for row in rebuilt.rows] == [
        row.capacity_signature for row in preparation.rows
    ]


def test_crossbeam_adapter_blocks_only_missing_engineering_source_not_model_revision() -> None:
    state = _ready_state()
    contract = dict(state[CB_STATION_FORCE_CONTRACT_KEY])
    contract["model_revision"] = ""
    state[CB_STATION_FORCE_CONTRACT_KEY] = contract
    assert build_crossbeam_uls_flexure_preparation(state).ready is True

    link = dict(state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY])
    link["ready"] = False
    state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY] = link
    blocked = build_crossbeam_uls_flexure_preparation(state)
    assert blocked.ready is False
    assert any("CURRENT/CLOSED" in message for message in blocked.errors)


@dataclass
class _DirectState:
    c_mm: float = 500.0
    a_mm: float = 400.0
    eps_t: float = 0.005
    strain_condition: str = "Tension-controlled"
    prestress_compression_reversal_count: int = 0


@dataclass
class _DirectResult:
    state: _DirectState | None = field(default_factory=_DirectState)
    capacity_phiMn_Nmm: float | None = 4_000_000_000.0
    nominal_Mn_Nmm: float | None = 4_500_000_000.0
    phi: float | None = 0.9
    axial_dcr: float | None = 0.057
    status: str = "PASS"
    message: str = "Direct exact-axis equilibrium solved."
    force_residual_N: float | None = 0.0
    force_residual_ratio: float | None = 0.0
    iterations: int = 12
    bracket_count: int = 1
    warnings: tuple[str, ...] = ()


def test_crossbeam_run_uses_direct_uniaxial_route_and_keeps_joint_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    preparation = build_crossbeam_uls_flexure_preparation(_ready_state())
    calls = {"direct": 0}

    def _direct(_analysis_input: object, *, Pu_N: float, moment_sign: float) -> _DirectResult:
        calls["direct"] += 1
        assert Pu_N == pytest.approx(5_000_000.0)
        assert moment_sign == pytest.approx(1.0)
        return _DirectResult()

    monkeypatch.setattr(
        "concrete_pmm_pro.analysis.crossbeam_uls.solve_crossbeam_uniaxial_flexure",
        _direct,
    )
    result = run_crossbeam_uls_flexure(preparation)

    assert result["status"] == "REVIEW"
    assert result["station_checks"] == len(preparation.rows)
    assert result["solver_route"] == "DIRECT UNIAXIAL P-M3"
    assert result["accuracy_preset_dependency"].startswith("NONE")
    assert calls["direct"] == result["structural_solves"]
    assert result["structural_solves"] >= 1
    joints = [
        row for row in result["rows"]
        if row["Case"] == "ULS-JOINT" and row["Location type"] == "PHYSICAL SEGMENT JOINT"
    ]
    assert len(joints) == 2
    assert {str(row["Check Point"])[-1] for row in joints} == {"L", "R"}
    assert all(row["Ordinary bars credited"] == 0 for row in joints)
    assert all(row["Bonded tendons credited"] == 3 for row in joints)

def test_analysis_page_routes_crossbeam_before_generic_preflight() -> None:
    source = open("concrete_pmm_pro/ui/analysis_page.py", encoding="utf-8").read()
    block = source[source.index("def render_analysis_uls_pmm"):source.index("def render_analysis_sls_stress")]
    assert "is_portal_frame_crossbeam_workflow" in block
    assert "_render_crossbeam_uls_flexure_workspace()" in block
    assert block.index("_render_crossbeam_uls_flexure_workspace()") < block.index("_render_beam_girder_uls_workspace")
    assert "No active ULS load cases" not in block


def _zero_moment_state() -> dict[str, object]:
    state = _ready_state()
    state["crossbeam_uls_loads_table"] = [
        {
            "Active": True,
            "Station s (m)": 4.0,
            "Check Point": "Left zero",
            "Case Name": "ULS-ENV",
            "P": 5000.0,
            "V2": 0.0,
            "T": 0.0,
            "M3": 0.0,
            "Note": "eligible zero-moment left station",
        },
        {
            "Active": True,
            "Station s (m)": 5.0,
            "Check Point": "Left reference",
            "Case Name": "ULS-ENV",
            "P": 5000.0,
            "V2": 320.0,
            "T": 45.0,
            "M3": 2200.0,
            "Note": "nearest left reference",
        },
        {
            "Active": True,
            "Station s (m)": 9.0,
            "Check Point": "",
            "Case Name": "ULS-ENV",
            "P": 5000.0,
            "V2": 0.0,
            "T": 0.0,
            "M3": 1200.0,
            "Note": "left Column Face source",
        },
        {
            "Active": True,
            "Station s (m)": 11.0,
            "Check Point": "",
            "Case Name": "ULS-ENV",
            "P": 5000.0,
            "V2": 0.0,
            "T": 0.0,
            "M3": -1200.0,
            "Note": "right Column Face source",
        },
        {
            "Active": True,
            "Station s (m)": 15.0,
            "Check Point": "Right reference",
            "Case Name": "ULS-ENV",
            "P": 5000.0,
            "V2": -320.0,
            "T": -45.0,
            "M3": -1800.0,
            "Note": "nearest right reference",
        },
        {
            "Active": True,
            "Station s (m)": 16.0,
            "Check Point": "Right zero",
            "Case Name": "ULS-ENV",
            "P": 5000.0,
            "V2": 0.0,
            "T": 0.0,
            "M3": 0.0,
            "Note": "eligible zero-moment right station",
        },
    ]
    return state


def test_zero_m3_endpoints_use_nearest_same_case_direction_and_keep_axial_dc_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation = build_crossbeam_uls_flexure_preparation(_zero_moment_state())
    assert preparation.ready, preparation.errors

    monkeypatch.setattr(
        "concrete_pmm_pro.analysis.crossbeam_uls.solve_crossbeam_uniaxial_flexure",
        lambda _analysis_input, *, Pu_N, moment_sign: _DirectResult(),
    )
    result = run_crossbeam_uls_flexure(preparation)
    endpoints = {
        float(row["Station s (m)"]): row
        for row in result["rows"]
        if float(row["Station s (m)"]) in {4.0, 16.0}
    }

    assert endpoints[4.0]["Capacity kN-m"] == pytest.approx(4000.0)
    assert endpoints[16.0]["Capacity kN-m"] == pytest.approx(4000.0)
    assert endpoints[4.0]["φMn at Pu"] == "4,000.000 kN-m"
    assert endpoints[16.0]["φMn at Pu"] == "4,000.000 kN-m"
    assert endpoints[4.0]["Flexural D/C"] == "0.000"
    assert endpoints[16.0]["Flexural D/C"] == "0.000"
    assert endpoints[4.0]["Axial D/C"] == "0.057"
    assert endpoints[16.0]["Axial D/C"] == "0.057"
    assert endpoints[4.0]["Capacity plot sign"] == pytest.approx(1.0)
    assert endpoints[16.0]["Capacity plot sign"] == pytest.approx(-1.0)
    assert "s = 5.000 m" in endpoints[4.0]["Direction reference"]
    assert "s = 15.000 m" in endpoints[16.0]["Direction reference"]


def test_zero_m3_without_nonzero_same_case_is_review_and_not_guessed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _ready_state()
    state["crossbeam_uls_loads_table"] = [
        {
            "Active": True,
            "Station s (m)": station,
            "Check Point": "Zero-only case" if station == 5.0 else "",
            "Case Name": "ULS-ZERO-ONLY",
            "P": 5000.0,
            "V2": 0.0,
            "T": 0.0,
            "M3": 0.0,
            "Note": "direction intentionally unavailable",
        }
        for station in (5.0, 9.0, 11.0, 15.0)
    ]
    preparation = build_crossbeam_uls_flexure_preparation(state)
    assert preparation.ready, preparation.errors

    monkeypatch.setattr(
        "concrete_pmm_pro.analysis.crossbeam_uls.solve_crossbeam_uniaxial_flexure",
        lambda _analysis_input, *, Pu_N, moment_sign: _DirectResult(),
    )
    row = next(
        item for item in run_crossbeam_uls_flexure(preparation)["rows"]
        if item["Check Point"] == "Zero-only case"
    )
    assert row["Status"] == "REVIEW"
    assert row["Capacity"] == "-"
    assert row["Flexural D/C"] == "-"
    assert float(row["Axial D/C"]) == pytest.approx(0.062, abs=0.001)
    assert "no nonzero M3 row" in row["Direction reference"]


def test_crossbeam_chart_uses_lowest_capacity_when_duplicate_faces_have_equal_dc() -> None:
    from concrete_pmm_pro.ui.analysis_page import _crossbeam_flexure_chart_rows

    source = pd.DataFrame(
        [
            {"Case": "ULS-ENV", "Station s (m)": 10.0, "Utilization value": 0.0, "Capacity kN-m": 4200.0},
            {"Case": "ULS-ENV", "Station s (m)": 10.0, "Utilization value": 0.0, "Capacity kN-m": 3900.0},
        ]
    )
    chosen = _crossbeam_flexure_chart_rows(source)
    assert len(chosen.index) == 1
    assert float(chosen.iloc[0]["Capacity kN-m"]) == pytest.approx(3900.0)
