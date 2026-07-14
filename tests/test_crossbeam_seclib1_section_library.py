from __future__ import annotations

import pytest

from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_ACTIVE_ID_KEY,
    CB_SECLIB_DEFINITIONS_KEY,
    CROSSBEAM_HOLLOW_PRESET_KEY,
    DEFAULT_HOLLOW_SECTION_ID,
    DEFAULT_SOLID_SECTION_ID,
    SECLIB_METADATA_KEY,
    add_default_definition,
    canonical_section_definitions,
    default_section_definitions,
    duplicate_definition,
    migrate_segment_rows_to_library,
    rename_definition,
    replace_section_id_in_segments,
    section_ids_used_by_segments,
    section_property_record,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_session_state


def test_default_library_separates_geometry_family_from_project_section_id() -> None:
    definitions = default_section_definitions(
        active_preset_key=CROSSBEAM_HOLLOW_PRESET_KEY,
        active_parameters={
            "width_mm": 2600.0,
            "height_mm": 1600.0,
            "t_top_mm": 350.0,
            "t_bottom_mm": 450.0,
            "t_left_mm": 300.0,
            "t_right_mm": 400.0,
            "bottom_fillet_radius_mm": 200.0,
            "inner_chamfer_mm": 150.0,
        },
    )

    assert [row["Section ID"] for row in definitions] == [DEFAULT_SOLID_SECTION_ID, DEFAULT_HOLLOW_SECTION_ID]
    hollow = definitions[1]
    assert hollow["Preset key"] == CROSSBEAM_HOLLOW_PRESET_KEY
    assert hollow["Parameters"]["t_left_mm"] == pytest.approx(300.0)
    assert hollow["Parameters"]["t_right_mm"] == pytest.approx(400.0)


def test_duplicate_hollow_definition_can_have_different_wall_thickness_and_properties() -> None:
    definitions = default_section_definitions()
    duplicated, new_id = duplicate_definition(definitions, DEFAULT_HOLLOW_SECTION_ID)
    rows = canonical_section_definitions(duplicated)
    clone = next(row for row in rows if row["Section ID"] == new_id)
    clone["Section name"] = "Hollow heavy web"
    clone["Parameters"]["t_left_mm"] = 500.0
    clone["Parameters"]["t_right_mm"] = 500.0

    typical = section_property_record(next(row for row in rows if row["Section ID"] == DEFAULT_HOLLOW_SECTION_ID))
    heavy = section_property_record(clone)

    assert typical["Status"] in {"READY", "REVIEW"}
    assert heavy["Status"] in {"READY", "REVIEW"}
    assert heavy["Area mm²"] > typical["Area mm²"]
    assert heavy["Iy mm4"] > typical["Iy mm4"]


def test_legacy_preset_assignments_migrate_to_section_ids_without_changing_stations() -> None:
    definitions = default_section_definitions()
    legacy = default_crossbeam_segment_rows(20.0)
    migrated = migrate_segment_rows_to_library(legacy, definitions)

    assert migrated[0]["x_start_m"] == pytest.approx(0.0)
    assert migrated[-1]["x_end_m"] == pytest.approx(20.0)
    assert {row["Section ID"] for row in migrated} == {DEFAULT_SOLID_SECTION_ID, DEFAULT_HOLLOW_SECTION_ID}
    assert all(row["Section name"] for row in migrated)


def test_rename_section_id_updates_segment_references_and_usage() -> None:
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(default_crossbeam_segment_rows(20.0), definitions)
    renamed = rename_definition(
        definitions,
        DEFAULT_HOLLOW_SECTION_ID,
        new_section_id="CB-H-TYP",
        new_section_name="Hollow typical revised",
    )
    updated_segments = replace_section_id_in_segments(segments, DEFAULT_HOLLOW_SECTION_ID, "CB-H-TYP")
    usage = section_ids_used_by_segments(updated_segments)

    assert "CB-H-TYP" in {row["Section ID"] for row in renamed}
    assert DEFAULT_HOLLOW_SECTION_ID not in usage
    assert usage["CB-H-TYP"]


def test_add_default_hollow_definition_generates_unique_project_id() -> None:
    definitions = default_section_definitions()
    updated, new_id = add_default_definition(definitions, CROSSBEAM_HOLLOW_PRESET_KEY)

    assert new_id == "CB-H02"
    assert len(updated) == 3
    assert next(row for row in updated if row["Section ID"] == new_id)["Section role"] == "Hollow"


def test_project_json_metadata_round_trip_preserves_section_library_and_segment_assignments() -> None:
    definitions = default_section_definitions()
    definitions, new_id = duplicate_definition(definitions, DEFAULT_HOLLOW_SECTION_ID)
    for row in definitions:
        if row["Section ID"] == new_id:
            row["Section name"] = "Hollow near column"
            row["Parameters"]["t_top_mm"] = 500.0
    segments = migrate_segment_rows_to_library(default_crossbeam_segment_rows(20.0), definitions)
    segments[1]["Section ID"] = new_id

    source_state = {
        "project_name": "Crossbeam library project",
        "section_preset_key": CROSSBEAM_HOLLOW_PRESET_KEY,
        "section_preset_name": "PC Crossbeam Hollow",
        "section_parameters": definitions[1]["Parameters"],
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        CB_SECLIB_ACTIVE_ID_KEY: new_id,
        "crossbeam_ui1_length_m": 20.0,
        "crossbeam_ui1_segment_layout_rows": segments,
    }
    project = project_from_session_state(source_state)

    assert SECLIB_METADATA_KEY in project.metadata
    restored: dict[str, object] = {}
    apply_project_to_session_state(project, restored)

    assert restored[CB_SECLIB_ACTIVE_ID_KEY] == new_id
    restored_definitions = restored[CB_SECLIB_DEFINITIONS_KEY]
    assert isinstance(restored_definitions, list)
    assert any(row["Section ID"] == new_id for row in restored_definitions)
    restored_segments = restored["crossbeam_ui1_segment_layout_rows"]
    assert restored_segments[1]["Section ID"] == new_id


def test_seclib1_remains_crossbeam_scoped_in_source() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    section_builder_source = (root / "concrete_pmm_pro" / "ui" / "section_builder.py").read_text(encoding="utf-8")
    segment_source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_pages.py").read_text(encoding="utf-8")

    assert "prepare_crossbeam_section_library_for_builder(settings)" in section_builder_source
    assert "render_crossbeam_section_library_panel(settings)" in section_builder_source
    assert "Section ID" in segment_source
    assert "Different Hollow IDs may use different wall thicknesses" in segment_source
