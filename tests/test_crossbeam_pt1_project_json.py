from __future__ import annotations

import json

from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_ACTIVE_ID_KEY,
    CB_SECLIB_DEFINITIONS_KEY,
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.tendon import (
    canonical_tendon_profile_points,
    canonical_tendon_system_rows,
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import (
    CB_3D_TRANSPARENT_KEY,
    CB_ACTIVE_TENDONS_KEY,
    CB_PROFILE_REV_KEY,
    CB_PROFILE_ROWS_KEY,
    CB_TENDON_COUNT_KEY,
    CB_TENDON_PROJECT_LOAD_VALIDATION_KEY,
    CB_TENDON_SYSTEM_REV_KEY,
    CB_TENDON_SYSTEM_ROWS_KEY,
    CROSSBEAM_TENDON_LEGACY_METADATA_KEYS,
    CROSSBEAM_TENDON_METADATA_KEY,
    CROSSBEAM_TENDON_SCHEMA_VERSION,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)


def _crossbeam_geometry_state() -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(default_crossbeam_segment_rows(20.0), definitions)
    state: dict[str, object] = {
        "project_name": "Crossbeam PT1 persistence",
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        CB_SECLIB_ACTIVE_ID_KEY: definitions[1]["Section ID"],
        "crossbeam_ui1_length_m": 20.0,
        "crossbeam_ui1_segment_layout_rows": segments,
    }
    return state, segments, definitions


def _custom_tendon_input(definitions: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    system = default_tendon_system_rows()
    system[0].update(
        {
            "Tendon ID": "PT-A",
            "Type": "External",
            "Strands": 31,
            "Aps/strand mm²": 150.0,
            "fpu MPa": 1900.0,
            "fpj/fpu": 0.72,
            "Jacking end": "Left",
        }
    )
    ids = [str(row["Tendon ID"]) for row in system]
    params = definitions[0]["Parameters"]
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=ids,
        width_mm=float(params["width_mm"]),
        height_mm=float(params["height_mm"]),
    )
    profile[1]["x lateral (mm)"] = 1325.0  # External tendon may lie outside the section preview envelope.
    profile[1]["dtop (mm)"] = 1710.0
    return canonical_tendon_system_rows(system), canonical_tendon_profile_points(profile, 20.0)


def test_project_json_round_trip_preserves_complete_pt1_input_model() -> None:
    source, _segments, definitions = _crossbeam_geometry_state()
    system, profile = _custom_tendon_input(definitions)
    source.update(
        {
            CB_TENDON_COUNT_KEY: len(system),
            CB_TENDON_SYSTEM_ROWS_KEY: system,
            CB_PROFILE_ROWS_KEY: profile,
            CB_ACTIVE_TENDONS_KEY: ["PT-A", "T3"],
            CB_3D_TRANSPARENT_KEY: False,
        }
    )

    project = project_from_session_state(source)
    block = project.metadata[CROSSBEAM_TENDON_METADATA_KEY]
    assert block["schema_version"] == CROSSBEAM_TENDON_SCHEMA_VERSION
    assert set(block) == {"schema_version", "tendon_system", "profile_points", "preview"}

    restored: dict[str, object] = {}
    apply_project_to_session_state(project_from_json(project_to_json(project)), restored)

    assert restored[CB_TENDON_SYSTEM_ROWS_KEY] == system
    assert restored[CB_PROFILE_ROWS_KEY] == profile
    assert restored[CB_TENDON_COUNT_KEY] == 8
    assert restored[CB_ACTIVE_TENDONS_KEY] == ["PT-A", "T3"]
    assert restored[CB_3D_TRANSPARENT_KEY] is False
    assert restored[CB_TENDON_SYSTEM_REV_KEY] == 1
    assert restored[CB_PROFILE_REV_KEY] == 1
    pt_a = next(row for row in restored[CB_TENDON_SYSTEM_ROWS_KEY] if row["Tendon ID"] == "PT-A")
    assert pt_a["Type"] == "External"
    assert pt_a["Strands"] == 31
    assert pt_a["Aps/strand mm²"] == 150.0
    assert pt_a["fpu MPa"] == 1900.0
    assert pt_a["fpj/fpu"] == 0.72
    assert pt_a["Jacking end"] == "Left"
    validation = restored[CB_TENDON_PROJECT_LOAD_VALIDATION_KEY]
    assert validation["status"] == "SOURCE READY"
    assert validation["references_resolved"] is True
    assert validation["pt_continuity"] == "REQUIRED — NOT VERIFIED"
    assert validation["migrated"] is False


def test_older_crossbeam_project_without_pt1_block_seeds_eight_web_tendons_and_profiles() -> None:
    source, _segments, _definitions = _crossbeam_geometry_state()
    older_project = project_from_session_state(source)
    assert CROSSBEAM_TENDON_METADATA_KEY not in older_project.metadata

    restored: dict[str, object] = {
        CB_TENDON_SYSTEM_ROWS_KEY: [{"Tendon ID": "STALE"}],
        CB_PROFILE_ROWS_KEY: [{"Tendon ID": "STALE"}],
    }
    apply_project_to_session_state(project_from_json(project_to_json(older_project)), restored)

    assert restored[CB_TENDON_SYSTEM_ROWS_KEY] == default_tendon_system_rows()
    assert len(restored[CB_PROFILE_ROWS_KEY]) == 24
    p1_by_id = {
        row["Tendon ID"]: row
        for row in restored[CB_PROFILE_ROWS_KEY]
        if row["Point"] == "P1"
    }
    assert {p1_by_id[f"T{index}"]["x lateral (mm)"] for index in range(1, 5)} == {-1100.0}
    assert {p1_by_id[f"T{index}"]["x lateral (mm)"] for index in range(5, 9)} == {1100.0}
    validation = restored[CB_TENDON_PROJECT_LOAD_VALIDATION_KEY]
    assert validation["status"] == "SOURCE READY"
    assert validation["migrated"] is True
    assert any("no Crossbeam tendon block" in note for note in validation["migration_notes"])

    resaved = project_from_session_state(restored)
    assert CROSSBEAM_TENDON_METADATA_KEY in resaved.metadata


def test_unresolved_profile_tendon_id_is_preserved_and_reported_after_load() -> None:
    source, _segments, definitions = _crossbeam_geometry_state()
    system = default_tendon_system_rows()
    params = definitions[0]["Parameters"]
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=[str(row["Tendon ID"]) for row in system],
        width_mm=float(params["width_mm"]),
        height_mm=float(params["height_mm"]),
    )
    profile[0]["Tendon ID"] = "PT-MISSING"
    project_data = json.loads(project_to_json(project_from_session_state(source)))
    project_data["metadata"][CROSSBEAM_TENDON_METADATA_KEY] = {
        "schema_version": CROSSBEAM_TENDON_SCHEMA_VERSION,
        "tendon_system": system,
        "profile_points": profile,
    }

    restored: dict[str, object] = {}
    apply_project_to_session_state(project_from_json(json.dumps(project_data)), restored)

    assert restored[CB_PROFILE_ROWS_KEY][0]["Tendon ID"] == "PT-MISSING"
    validation = restored[CB_TENDON_PROJECT_LOAD_VALIDATION_KEY]
    assert validation["status"] == "REVIEW REQUIRED"
    assert validation["references_resolved"] is False
    assert any("PT-MISSING" in message for message in validation["errors"])

    resaved = project_from_session_state(restored)
    assert all(key not in resaved.metadata for key in CROSSBEAM_TENDON_LEGACY_METADATA_KEYS)
