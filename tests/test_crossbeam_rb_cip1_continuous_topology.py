from __future__ import annotations

import json

from concrete_pmm_pro.crossbeam.cip_rebar import (
    canonical_cip_longitudinal_bar_runs,
    cip_rebar_topology_status,
    default_cip_longitudinal_bar_runs,
    validate_cip_longitudinal_bar_runs,
)
from concrete_pmm_pro.crossbeam.cip_rebar_persistence import (
    CB_RB_CIP_RUN_ROWS_KEY,
    CB_RB_CIP_VALIDATION_KEY,
    CROSSBEAM_CIP_REBAR_METADATA_KEY,
    CROSSBEAM_CIP_REBAR_SCHEMA_VERSION,
)
from concrete_pmm_pro.crossbeam.construction_stage import CONSTRUCTION_METHOD_CIP
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.rebar import (
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
    CROSSBEAM_REBAR_METADATA_KEY,
)
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_DEFINITIONS_KEY,
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.transverse import default_crossbeam_transverse_templates
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)
from concrete_pmm_pro.ui import crossbeam_pages


def _valid_run(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Active": True,
        "Run ID": "CIP-R1",
        "s_start_m": 1.0,
        "s_end_m": 19.0,
        "Bar group": "Top continuous bars",
        "Layer / face": "Top",
        "Bar size": "DB25",
        "Material": "SD40",
        "Definition basis": "By exact bar count",
        "Bar count": 8,
        "Target spacing mm": 0.0,
        "Start intent": "Intentional developed termination",
        "End intent": "Intentional developed termination",
        "Notes": "QA seed only",
    }
    row.update(overrides)
    return row


def test_default_cip_topology_does_not_invent_reinforcement() -> None:
    assert default_cip_longitudinal_bar_runs() == []
    status = cip_rebar_topology_status([], length_m=20.0)
    assert status["status"] == "LAYOUT REQUIRED"
    assert status["active_run_count"] == 0
    assert status["solver_handoff"] == "LOCKED"
    assert any("does not invent reinforcement" in message for message in status["warnings"])


def test_station_based_run_is_valid_without_zone_boundary_termination() -> None:
    # The run spans 1–19 m and therefore may cross any number of CIP Z1/Z2/Z3
    # geometry/property boundaries. RB-CIP1 validation intentionally does not
    # require a run start/end station at a Section/Zone boundary.
    rows, errors, warnings = validate_cip_longitudinal_bar_runs([_valid_run()], length_m=20.0)

    assert errors == []
    assert rows[0]["s_start_m"] == 1.0
    assert rows[0]["s_end_m"] == 19.0
    assert warnings == []
    assert cip_rebar_topology_status(rows, length_m=20.0)["status"] == "FOUNDATION READY"


def test_validation_preserves_unknown_engineering_labels_for_explicit_review() -> None:
    source = _valid_run(
        **{
            "Bar size": "DB40-CUSTOM",
            "Bar diameter mm": 40.0,
            "Material": "CUSTOM-GRADE",
            "fy MPa": 500.0,
            "Layer / face": "Unknown face",
        }
    )
    rows, errors, _warnings = validate_cip_longitudinal_bar_runs([source], length_m=20.0)

    assert rows[0]["Bar size"] == "DB40-CUSTOM"
    assert rows[0]["Material"] == "CUSTOM-GRADE"
    assert rows[0]["Layer / face"] == "Unknown face"
    assert any("DB40-CUSTOM" in message and "not supported" in message for message in errors)
    assert any("CUSTOM-GRADE" in message and "not supported" in message for message in errors)
    assert any("Unknown face" in message and "not supported" in message for message in errors)


def test_validation_rejects_out_of_member_range_duplicates_and_invalid_quantity_basis() -> None:
    rows = [
        _valid_run(**{"Run ID": "R-DUP", "s_start_m": -0.5, "s_end_m": 5.0}),
        _valid_run(
            **{
                "Run ID": "R-DUP",
                "s_start_m": 5.0,
                "s_end_m": 21.0,
                "Definition basis": "By target spacing",
                "Target spacing mm": 0.0,
            }
        ),
    ]

    _canonical, errors, _warnings = validate_cip_longitudinal_bar_runs(rows, length_m=20.0)

    assert any("Duplicate active CIP longitudinal Run ID: R-DUP" in message for message in errors)
    assert sum("physical Crossbeam extent" in message for message in errors) == 2
    assert any("Target spacing must be positive" in message for message in errors)


def test_canonical_model_derives_known_bar_metadata_but_does_not_clamp_stations() -> None:
    rows = canonical_cip_longitudinal_bar_runs(
        [
            _valid_run(
                **{
                    "s_start_m": -2.0,
                    "s_end_m": 25.0,
                    "Bar diameter mm": None,
                    "fy MPa": None,
                }
            )
        ]
    )

    assert rows[0]["s_start_m"] == -2.0
    assert rows[0]["s_end_m"] == 25.0
    assert rows[0]["Bar diameter mm"] == 25.0
    assert rows[0]["fy MPa"] == 390.0


def test_project_json_round_trip_preserves_cip_runs_separately_from_segmental_rebar() -> None:
    definitions = default_section_definitions()
    cip_zones = crossbeam_pages._default_cip_zone_rows(20.0, definitions)
    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    # Keep a valid independent Segmental namespace in the same project to prove
    # RB-CIP1 does not reinterpret or replace the accepted legacy model.
    precast_segments = [
        {
            "Segment": "S1",
            "x_start_m": 0.0,
            "x_end_m": 20.0,
            "Section role": "Solid",
        }
    ]
    segmental_zones = default_crossbeam_rebar_zones(precast_segments, longitudinal, transverse)
    cip_runs = canonical_cip_longitudinal_bar_runs([_valid_run()])

    state: dict[str, object] = {
        "project_name": "RB-CIP1 persistence QA",
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        crossbeam_pages.CB_LENGTH_KEY: 20.0,
        crossbeam_pages.CB_SEGMENT_ROWS_KEY: cip_zones,
        crossbeam_pages.CB_CIP_ZONE_ROWS_KEY: cip_zones,
        crossbeam_pages.CB_PRECAST_SEGMENT_ROWS_KEY: precast_segments,
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: CONSTRUCTION_METHOD_CIP,
        crossbeam_pages.CB_CONSTRUCTION_METHOD_LAST_KEY: CONSTRUCTION_METHOD_CIP,
        CB_RB_TEMPLATE_ROWS_KEY: longitudinal,
        CB_TR_TEMPLATE_ROWS_KEY: transverse,
        CB_RB_ZONE_ROWS_KEY: segmental_zones,
        CB_RB_CIP_RUN_ROWS_KEY: cip_runs,
    }

    project = project_from_session_state(state)
    assert CROSSBEAM_REBAR_METADATA_KEY in project.metadata
    assert CROSSBEAM_CIP_REBAR_METADATA_KEY in project.metadata
    cip_block = project.metadata[CROSSBEAM_CIP_REBAR_METADATA_KEY]
    assert cip_block["schema_version"] == CROSSBEAM_CIP_REBAR_SCHEMA_VERSION
    assert cip_block["solver_handoff"] == "LOCKED"
    assert cip_block["longitudinal_bar_runs"] == cip_runs

    restored: dict[str, object] = {}
    apply_project_to_session_state(project_from_json(project_to_json(project)), restored)

    assert restored[CB_RB_CIP_RUN_ROWS_KEY] == cip_runs
    assert restored[CB_RB_ZONE_ROWS_KEY] == segmental_zones
    assert restored[crossbeam_pages.CB_CIP_ZONE_ROWS_KEY] == cip_zones
    assert restored[crossbeam_pages.CB_PRECAST_SEGMENT_ROWS_KEY] == migrate_segment_rows_to_library(
        precast_segments, definitions, preserve_explicit_unknown_ids=True
    )
    validation = restored[CB_RB_CIP_VALIDATION_KEY]
    assert validation["status"] == "FOUNDATION READY"
    assert validation["migrated_from_segmental"] is False
    assert validation["solver_handoff"] == "LOCKED"


def test_older_project_without_cip_rebar_block_does_not_migrate_segmental_templates_into_runs() -> None:
    definitions = default_section_definitions()
    cip_zones = crossbeam_pages._default_cip_zone_rows(20.0, definitions)
    state: dict[str, object] = {
        "project_name": "Older CIP project",
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        crossbeam_pages.CB_LENGTH_KEY: 20.0,
        crossbeam_pages.CB_SEGMENT_ROWS_KEY: cip_zones,
        crossbeam_pages.CB_CIP_ZONE_ROWS_KEY: cip_zones,
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: CONSTRUCTION_METHOD_CIP,
        crossbeam_pages.CB_CONSTRUCTION_METHOD_LAST_KEY: CONSTRUCTION_METHOD_CIP,
        CB_RB_TEMPLATE_ROWS_KEY: default_crossbeam_rebar_templates(),
        CB_TR_TEMPLATE_ROWS_KEY: default_crossbeam_transverse_templates(),
    }

    raw = json.loads(project_to_json(project_from_session_state(state)))
    assert CROSSBEAM_CIP_REBAR_METADATA_KEY not in raw["metadata"]

    restored: dict[str, object] = {CB_RB_CIP_RUN_ROWS_KEY: [_valid_run(**{"Run ID": "STALE"})]}
    apply_project_to_session_state(project_from_json(json.dumps(raw)), restored)

    assert CB_RB_CIP_RUN_ROWS_KEY not in restored
    assert CB_RB_CIP_VALIDATION_KEY not in restored
