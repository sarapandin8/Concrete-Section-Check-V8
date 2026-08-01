from __future__ import annotations

from dataclasses import dataclass

import pytest

from concrete_pmm_pro.analysis.crossbeam_uls import (
    build_crossbeam_uls_flexure_preparation,
    run_crossbeam_uls_flexure,
)
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
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
    link = {
        "ready": True,
        "source_id": "analysis1a-ready-source",
        "contract_id": "analysis1a-ready-contract",
        "average_total_loss_percent": 20.0,
        "effective_prestress_ratio_percent": 80.0,
        "average_effective_stress_mpa": 1116.0,
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
        ],
    }


def test_crossbeam_adapter_runs_without_generic_load_cases_and_preserves_row_coupling() -> None:
    state = _ready_state()
    preparation = build_crossbeam_uls_flexure_preparation(state)

    assert preparation.ready, preparation.errors
    assert len(preparation.rows) == 2
    interior = next(row for row in preparation.rows if row.case_name == "ULS-INT")
    joint = next(row for row in preparation.rows if row.case_name == "ULS-JOINT")

    assert interior.analysis_input.load_cases[0].Pu_N == pytest.approx(5_000_000.0)
    assert interior.analysis_input.load_cases[0].Mux_Nmm == pytest.approx(2_200_000_000.0)
    assert interior.source_v2_kn == pytest.approx(320.0)
    assert interior.source_t_knm == pytest.approx(45.0)
    assert interior.ordinary_rebar_count > 0
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
class _CapacityResult:
    capacity_phiMn_Nmm: float = 4_000_000_000.0
    dcr: float = 0.65
    status: str = "PASS"
    message: str = "Demand is within the directional PMM capacity."


@dataclass
class _CapacitySummary:
    results: tuple[_CapacityResult, ...] = (_CapacityResult(),)
    warnings: tuple[str, ...] = ()


@dataclass
class _PmmResult:
    warnings: tuple[str, ...] = ()


def test_crossbeam_run_uses_existing_pmm_route_and_keeps_joint_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    preparation = build_crossbeam_uls_flexure_preparation(_ready_state())
    calls = {"solver": 0, "capacity": 0}

    def _solver(_analysis_input: object) -> _PmmResult:
        calls["solver"] += 1
        return _PmmResult()

    def _capacity(_pmm: object, _loads: object) -> _CapacitySummary:
        calls["capacity"] += 1
        return _CapacitySummary()

    monkeypatch.setattr("concrete_pmm_pro.analysis.crossbeam_uls.run_pmm_solver", _solver)
    monkeypatch.setattr(
        "concrete_pmm_pro.analysis.crossbeam_uls.check_uls_demands_against_rc_pmm",
        _capacity,
    )
    result = run_crossbeam_uls_flexure(preparation)

    assert result["status"] == "PASS"
    assert result["station_checks"] == 2
    assert calls["capacity"] == 2
    assert calls["solver"] == result["structural_solves"] == 2
    joint = next(row for row in result["rows"] if row["Location type"] == "PHYSICAL SEGMENT JOINT")
    assert joint["Ordinary bars credited"] == 0
    assert joint["Bonded tendons credited"] == 3


def test_analysis_page_routes_crossbeam_before_generic_preflight() -> None:
    source = open("concrete_pmm_pro/ui/analysis_page.py", encoding="utf-8").read()
    block = source[source.index("def render_analysis_uls_pmm"):source.index("def render_analysis_sls_stress")]
    assert "is_portal_frame_crossbeam_workflow" in block
    assert "_render_crossbeam_uls_flexure_workspace()" in block
    assert block.index("_render_crossbeam_uls_flexure_workspace()") < block.index("_render_beam_girder_uls_workspace")
    assert "No active ULS load cases" not in block
