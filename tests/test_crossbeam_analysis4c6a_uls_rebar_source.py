from __future__ import annotations

from copy import deepcopy

from concrete_pmm_pro.crossbeam.cip_rebar_templates import (
    CIP_RB_TEMPLATE_ROWS_KEY,
    CIP_RB_ZONE_ROWS_KEY,
    CIP_TR_TEMPLATE_ROWS_KEY,
    default_cip_longitudinal_templates,
    default_cip_transverse_templates,
    default_cip_zone_assignments,
)
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
from concrete_pmm_pro.crossbeam.transverse import default_crossbeam_transverse_templates
from concrete_pmm_pro.crossbeam.uls_rebar_source import build_crossbeam_uls_rebar_source_contract
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows


def _cip_layout() -> list[dict[str, object]]:
    return [
        {
            "Segment": "Z1",
            "x_start_m": 0.0,
            "x_end_m": 30.0,
            "Section ID": "CB-S01",
            "Section role": "Solid",
        }
    ]


def _cip_state() -> dict[str, object]:
    layout = _cip_layout()
    longitudinal = default_cip_longitudinal_templates()
    transverse = default_cip_transverse_templates()
    zones = default_cip_zone_assignments(layout, longitudinal, transverse)
    return {
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Cast-in-Place",
        "crossbeam_ui1_segment_layout_rows": layout,
        CIP_RB_TEMPLATE_ROWS_KEY: longitudinal,
        CIP_RB_ZONE_ROWS_KEY: zones,
        CIP_TR_TEMPLATE_ROWS_KEY: transverse,
        # Deliberately invalid dormant Precast data must not contaminate CIP.
        CB_RB_TEMPLATE_ROWS_KEY: [],
        CB_RB_ZONE_ROWS_KEY: [],
        CB_TR_TEMPLATE_ROWS_KEY: [],
    }


def _precast_state() -> dict[str, object]:
    layout = default_crossbeam_segment_rows(20.0)
    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(layout, longitudinal, transverse)
    return {
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        "crossbeam_ui1_segment_layout_rows": layout,
        CB_RB_TEMPLATE_ROWS_KEY: longitudinal,
        CB_RB_ZONE_ROWS_KEY: zones,
        CB_TR_TEMPLATE_ROWS_KEY: transverse,
        # Deliberately invalid dormant CIP data must not contaminate Precast.
        CIP_RB_TEMPLATE_ROWS_KEY: [],
        CIP_RB_ZONE_ROWS_KEY: [],
        CIP_TR_TEMPLATE_ROWS_KEY: [],
    }


def test_cip_active_source_is_ready_and_dormant_precast_is_ignored() -> None:
    contract = build_crossbeam_uls_rebar_source_contract(_cip_state())

    assert contract.ready is True, contract.errors
    assert contract.status == "READY"
    assert contract.construction_method == "Cast-in-Place"
    assert len(contract.adopted_rows) == 1
    assert contract.adopted_rows[0]["Status"] == "ADOPTED SOURCE"
    assert any("monolithic property boundaries" in message for message in contract.info)


def test_precast_active_source_is_ready_and_preserves_joint_exclusion_scope() -> None:
    contract = build_crossbeam_uls_rebar_source_contract(_precast_state())

    assert contract.ready is True, contract.errors
    assert contract.construction_method == "Precast Segmental"
    assert contract.adopted_rows
    assert all(row["Status"] == "ADOPTED SOURCE" for row in contract.adopted_rows)
    assert any("tendon-only exclusion" in message for message in contract.info)


def test_cip_incomplete_assigned_quantity_blocks_uls_credit() -> None:
    state = _cip_state()
    rows = deepcopy(state[CIP_RB_TEMPLATE_ROWS_KEY])
    assigned_id = state[CIP_RB_ZONE_ROWS_KEY][0]["Longitudinal template"]
    assigned = next(row for row in rows if row["Template ID"] == assigned_id)
    assigned["Outer face bars"] = False
    assigned["Top As mm²"] = 0.0
    assigned["Bottom As mm²"] = 0.0
    assigned["Side As mm²"] = 0.0
    state[CIP_RB_TEMPLATE_ROWS_KEY] = rows

    contract = build_crossbeam_uls_rebar_source_contract(state)

    assert contract.ready is False
    assert contract.status == "SOURCE BLOCKED"
    assert any("ULS longitudinal quantity source is incomplete" in message for message in contract.errors)


def test_fingerprint_tracks_assigned_active_source_not_unassigned_library_rows() -> None:
    state = _cip_state()
    baseline = build_crossbeam_uls_rebar_source_contract(state)
    assert baseline.ready

    unassigned_state = deepcopy(state)
    unassigned = deepcopy(unassigned_state[CIP_RB_TEMPLATE_ROWS_KEY][0])
    unassigned["Template ID"] = "RB-UNASSIGNED-QA"
    unassigned["Applicable role"] = "Hollow"  # invalid for CIP, but unassigned/dormant
    unassigned["Outer target spacing mm"] = 333.0
    unassigned_state[CIP_RB_TEMPLATE_ROWS_KEY].append(unassigned)
    unassigned_contract = build_crossbeam_uls_rebar_source_contract(unassigned_state)
    assert unassigned_contract.ready
    assert unassigned_contract.fingerprint == baseline.fingerprint

    assigned_state = deepcopy(state)
    assigned_id = assigned_state[CIP_RB_ZONE_ROWS_KEY][0]["Longitudinal template"]
    assigned = next(row for row in assigned_state[CIP_RB_TEMPLATE_ROWS_KEY] if row["Template ID"] == assigned_id)
    assigned["Outer target spacing mm"] = float(assigned["Outer target spacing mm"]) + 10.0
    assigned_contract = build_crossbeam_uls_rebar_source_contract(assigned_state)
    assert assigned_contract.ready
    assert assigned_contract.fingerprint != baseline.fingerprint


def test_rebar_ui_exposes_active_mode_uls_handoff_without_unlocking_other_workflows() -> None:
    from pathlib import Path

    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text(encoding="utf-8")
    assert '"title":"ULS solver handoff"' in source
    assert '"title": "ULS solver handoff"' in source
    assert "ULS REINFORCEMENT HANDOFF READY" in source
    assert "SLS/PMM, prestress-loss, Result Summary, and Report/QA handoffs remain unchanged" in source
