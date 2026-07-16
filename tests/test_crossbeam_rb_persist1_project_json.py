from __future__ import annotations

import json

from concrete_pmm_pro.crossbeam.rebar import (
    RB_HOLLOW_MIN,
    RB_SOLID_ANCHORAGE,
    canonical_rebar_templates,
    canonical_rebar_zones,
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
    segment_signature,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_ACTIVE_TEMPLATE_KEY,
    CB_RB_PREVIEW_MARKER_MODE_KEY,
    CB_RB_PREVIEW_SEGMENT_KEY,
    CB_RB_PREVIEW_ZONE_KEY,
    CB_RB_PROJECT_LOAD_VALIDATION_KEY,
    CB_RB_SEGMENT_SIGNATURE_KEY,
    CB_RB_SUBVIEW_KEY,
    CB_RB_TEMPLATE_REV_KEY,
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_REV_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_PREVIEW_MODE_KEY,
    CB_TR_TEMPLATE_REV_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
    CROSSBEAM_REBAR_LEGACY_METADATA_KEYS,
    CROSSBEAM_REBAR_METADATA_KEY,
    CROSSBEAM_REBAR_SCHEMA_VERSION,
)
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_ACTIVE_ID_KEY,
    CB_SECLIB_DEFINITIONS_KEY,
    CROSSBEAM_HOLLOW_PRESET_KEY,
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.transverse import (
    TR_HOLLOW_MIN,
    TR_SOLID_ANCHORAGE,
    canonical_transverse_templates,
    default_crossbeam_transverse_templates,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.io.project_io import (
    ANALYSIS_RESULTS_METADATA_KEY,
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)


def _crossbeam_geometry_state() -> tuple[dict[str, object], list[dict[str, object]]]:
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(default_crossbeam_segment_rows(20.0), definitions)
    state: dict[str, object] = {
        "project_name": "Crossbeam reinforcement persistence",
        "section_preset_key": CROSSBEAM_HOLLOW_PRESET_KEY,
        "section_preset_name": "PC Crossbeam Hollow",
        "section_parameters": definitions[1]["Parameters"],
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        CB_SECLIB_ACTIVE_ID_KEY: definitions[1]["Section ID"],
        "crossbeam_ui1_length_m": 20.0,
        "crossbeam_ui1_segment_layout_rows": segments,
    }
    return state, segments


def _renamed_input_model(
    segments: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    longitudinal = default_crossbeam_rebar_templates()
    for row in longitudinal:
        if row["Template ID"] == RB_HOLLOW_MIN:
            row.update(
                {
                    "Template ID": "RB-HOLLOW-PROJECT",
                    "Template name": "Project hollow longitudinal cage",
                    "Rebar material": "SD50",
                    "fy MPa": 490.0,
                    "Outer bar size": "DB25",
                    "Outer center offset mm": 71.0,
                    "Outer layout method": "By exact bar count",
                    "Outer exact bar count": 40,
                    "Inner bar size": "DB20",
                    "Inner center offset mm": 69.0,
                    "Inner layout method": "By target spacing",
                    "Inner target spacing mm": 175.0,
                    "Credit inside segment": False,
                }
            )
        elif row["Template ID"] == RB_SOLID_ANCHORAGE:
            row["Active"] = False
    longitudinal = canonical_rebar_templates(longitudinal)

    transverse = default_crossbeam_transverse_templates()
    for row in transverse:
        if row["Template ID"] == TR_HOLLOW_MIN:
            row.update(
                {
                    "Template ID": "TR-HOLLOW-PROJECT",
                    "Template name": "Project hollow transverse set",
                    "Rebar material": "SD50",
                    "fy MPa": 490.0,
                    "Bar size": "DB16",
                    "Spacing mm": 125.0,
                    "Center offset mm": 50.0,
                    "First bar offset mm": 90.0,
                    "Last bar offset mm": 110.0,
                    "Left web legs": 3,
                    "Right web legs": 3,
                    "Closed cage": True,
                    "Credit inside segment": False,
                }
            )
        elif row["Template ID"] == TR_SOLID_ANCHORAGE:
            row["Active"] = False
    transverse = canonical_transverse_templates(transverse)
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)
    return longitudinal, transverse, zones


def test_project_json_round_trip_preserves_complete_crossbeam_rebar_input_model() -> None:
    source, segments = _crossbeam_geometry_state()
    longitudinal, transverse, zones = _renamed_input_model(segments)
    selected_segment = str(segments[1]["Segment"])
    selected_zone = next(str(row["Zone ID"]) for row in zones if row["Segment"] == selected_segment)
    source.update(
        {
            CB_RB_TEMPLATE_ROWS_KEY: longitudinal,
            CB_TR_TEMPLATE_ROWS_KEY: transverse,
            CB_RB_ZONE_ROWS_KEY: zones,
            CB_RB_SUBVIEW_KEY: "Section Rebar Preview",
            CB_RB_PREVIEW_SEGMENT_KEY: selected_segment,
            CB_RB_PREVIEW_ZONE_KEY: selected_zone,
            CB_RB_ACTIVE_TEMPLATE_KEY: "RB-HOLLOW-PROJECT",
            CB_TR_PREVIEW_MODE_KEY: "Combined review",
            CB_RB_PREVIEW_MARKER_MODE_KEY: "True bar diameter",
        }
    )

    project = project_from_session_state(source)
    assert ANALYSIS_RESULTS_METADATA_KEY not in project.metadata
    assert CROSSBEAM_REBAR_METADATA_KEY in project.metadata
    block = project.metadata[CROSSBEAM_REBAR_METADATA_KEY]
    assert block["schema_version"] == CROSSBEAM_REBAR_SCHEMA_VERSION
    assert set(block) == {
        "schema_version",
        "longitudinal_templates",
        "transverse_templates",
        "zone_assignments",
        "preview",
    }

    restored: dict[str, object] = {}
    apply_project_to_session_state(project_from_json(project_to_json(project)), restored)

    assert restored[CB_RB_TEMPLATE_ROWS_KEY] == longitudinal
    assert restored[CB_TR_TEMPLATE_ROWS_KEY] == transverse
    assert restored[CB_RB_ZONE_ROWS_KEY] == canonical_rebar_zones(zones)
    restored_hollow = next(
        row for row in restored[CB_RB_TEMPLATE_ROWS_KEY] if row["Template ID"] == "RB-HOLLOW-PROJECT"
    )
    assert restored_hollow["Rebar material"] == "SD50"
    assert restored_hollow["fy MPa"] == 490.0
    assert restored_hollow["Outer bar size"] == "DB25"
    assert restored_hollow["Outer center offset mm"] == 71.0
    assert restored_hollow["Outer exact bar count"] == 40
    assert restored_hollow["Inner target spacing mm"] == 175.0
    assert restored_hollow["Credit inside segment"] is False
    assert next(
        row for row in restored[CB_RB_TEMPLATE_ROWS_KEY] if row["Template ID"] == RB_SOLID_ANCHORAGE
    )["Active"] is False
    restored_transverse = next(
        row for row in restored[CB_TR_TEMPLATE_ROWS_KEY] if row["Template ID"] == "TR-HOLLOW-PROJECT"
    )
    assert restored_transverse["Bar size"] == "DB16"
    assert restored_transverse["Spacing mm"] == 125.0
    assert restored_transverse["First bar offset mm"] == 90.0
    assert restored_transverse["Last bar offset mm"] == 110.0
    assert restored_transverse["Credit inside segment"] is False
    assert next(
        row for row in restored[CB_TR_TEMPLATE_ROWS_KEY] if row["Template ID"] == TR_SOLID_ANCHORAGE
    )["Active"] is False
    hollow_zones = [row for row in restored[CB_RB_ZONE_ROWS_KEY] if row["Segment"] in {"S2", "S4"}]
    assert hollow_zones
    assert {row["Longitudinal template"] for row in hollow_zones} == {"RB-HOLLOW-PROJECT"}
    assert {row["Transverse template"] for row in hollow_zones} == {"TR-HOLLOW-PROJECT"}
    assert restored[CB_RB_SUBVIEW_KEY] == "Section Rebar Preview"
    assert restored[CB_RB_PREVIEW_SEGMENT_KEY] == selected_segment
    assert restored[CB_RB_PREVIEW_ZONE_KEY] == selected_zone
    assert restored[CB_RB_ACTIVE_TEMPLATE_KEY] == "RB-HOLLOW-PROJECT"
    assert restored[CB_TR_PREVIEW_MODE_KEY] == "Combined review"
    assert restored[CB_RB_PREVIEW_MARKER_MODE_KEY] == "True bar diameter"
    assert restored[CB_RB_SEGMENT_SIGNATURE_KEY] == segment_signature(segments)
    assert restored[CB_RB_TEMPLATE_REV_KEY] == 1
    assert restored[CB_TR_TEMPLATE_REV_KEY] == 1
    assert restored[CB_RB_ZONE_REV_KEY] == 1
    validation = restored[CB_RB_PROJECT_LOAD_VALIDATION_KEY]
    assert validation["status"] == "READY"
    assert validation["references_resolved"] is True
    assert validation["migrated"] is False


def test_older_project_without_rebar_block_seeds_scoped_defaults_from_segment_layout() -> None:
    source, segments = _crossbeam_geometry_state()
    older_project = project_from_session_state(source)
    assert CROSSBEAM_REBAR_METADATA_KEY not in older_project.metadata
    restored: dict[str, object] = {
        CB_RB_TEMPLATE_ROWS_KEY: [{"Template ID": "STALE-FROM-OTHER-PROJECT"}],
        CB_TR_TEMPLATE_ROWS_KEY: [{"Template ID": "STALE-TRANSVERSE"}],
        CB_RB_ZONE_ROWS_KEY: [{"Zone ID": "STALE-ZONE"}],
    }

    apply_project_to_session_state(project_from_json(project_to_json(older_project)), restored)

    assert restored[CB_RB_TEMPLATE_ROWS_KEY] == default_crossbeam_rebar_templates()
    assert restored[CB_TR_TEMPLATE_ROWS_KEY] == default_crossbeam_transverse_templates()
    assert restored[CB_RB_ZONE_ROWS_KEY] == default_crossbeam_rebar_zones(
        segments,
        default_crossbeam_rebar_templates(),
        default_crossbeam_transverse_templates(),
    )
    validation = restored[CB_RB_PROJECT_LOAD_VALIDATION_KEY]
    assert validation["status"] == "READY"
    assert validation["references_resolved"] is True
    assert validation["migrated"] is True
    assert any("no Crossbeam reinforcement block" in note for note in validation["migration_notes"])

    resaved = project_from_session_state(restored)
    assert CROSSBEAM_REBAR_METADATA_KEY in resaved.metadata


def test_legacy_flat_metadata_migrates_and_adds_transverse_references() -> None:
    source, segments = _crossbeam_geometry_state()
    project_data = json.loads(project_to_json(project_from_session_state(source)))
    longitudinal = default_crossbeam_rebar_templates()
    legacy_zones = default_crossbeam_rebar_zones(segments, longitudinal)
    for row in legacy_zones:
        row.pop("Transverse template", None)
        row.pop("Longitudinal template", None)
    project_data["metadata"][CB_RB_TEMPLATE_ROWS_KEY] = longitudinal
    project_data["metadata"][CB_RB_ZONE_ROWS_KEY] = legacy_zones

    restored: dict[str, object] = {}
    apply_project_to_session_state(project_from_json(json.dumps(project_data)), restored)

    zones = restored[CB_RB_ZONE_ROWS_KEY]
    assert all(row["Longitudinal template"] == row["Rebar template"] for row in zones)
    assert all(str(row["Transverse template"]) for row in zones)
    validation = restored[CB_RB_PROJECT_LOAD_VALIDATION_KEY]
    assert validation["status"] == "READY"
    assert validation["references_resolved"] is True
    assert validation["migrated"] is True
    assert any("flat Crossbeam" in note for note in validation["migration_notes"])
    assert any("missing Transverse Template" in note for note in validation["migration_notes"])

    resaved = project_from_session_state(restored)
    assert CROSSBEAM_REBAR_METADATA_KEY in resaved.metadata
    assert all(key not in resaved.metadata for key in CROSSBEAM_REBAR_LEGACY_METADATA_KEYS)


def test_post_load_validation_preserves_and_reports_unresolved_template_ids() -> None:
    source, segments = _crossbeam_geometry_state()
    project_data = json.loads(project_to_json(project_from_session_state(source)))
    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)
    zones[1]["Rebar template"] = "RB-MISSING"
    zones[1]["Longitudinal template"] = "RB-MISSING"
    zones[1]["Transverse template"] = "TR-MISSING"
    project_data["metadata"][CROSSBEAM_REBAR_METADATA_KEY] = {
        "schema_version": CROSSBEAM_REBAR_SCHEMA_VERSION,
        "longitudinal_templates": longitudinal,
        "transverse_templates": transverse,
        "zone_assignments": zones,
    }

    restored: dict[str, object] = {}
    apply_project_to_session_state(project_from_json(json.dumps(project_data)), restored)

    assert restored[CB_RB_ZONE_ROWS_KEY][1]["Longitudinal template"] == "RB-MISSING"
    assert restored[CB_RB_ZONE_ROWS_KEY][1]["Transverse template"] == "TR-MISSING"
    validation = restored[CB_RB_PROJECT_LOAD_VALIDATION_KEY]
    assert validation["status"] == "REVIEW REQUIRED"
    assert validation["references_resolved"] is False
    assert validation["migrated"] is False
    assert any("RB-MISSING" in message and "does not resolve" in message for message in validation["errors"])
    assert any("TR-MISSING" in message and "does not resolve" in message for message in validation["errors"])
