from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from concrete_pmm_pro.crossbeam.editor_commit import data_editor_payload_to_records
from concrete_pmm_pro.crossbeam.rebar import (
    RB_SOLID_ANCHORAGE,
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_REV_KEY,
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_REV_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_REV_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.transverse import (
    TR_SOLID_ANCHORAGE,
    default_crossbeam_transverse_templates,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui import crossbeam_rebar_page as longitudinal_page
from concrete_pmm_pro.ui import crossbeam_transverse_page as transverse_page


def _fake_streamlit(monkeypatch, module, state: dict[str, object]) -> None:
    monkeypatch.setattr(module, "st", SimpleNamespace(session_state=state))


def test_editor_patch_reconstruction_keeps_first_edit_addition_and_deletion() -> None:
    fallback = [
        {"Template ID": "TR-1", "Spacing (mm)": 200.0},
        {"Template ID": "TR-2", "Spacing (mm)": 150.0},
    ]
    payload = {
        "edited_rows": {0: {"Spacing (mm)": 175.0}},
        "deleted_rows": [1],
        "added_rows": [{"Template ID": "TR-3", "Spacing (mm)": 125.0}],
    }

    records = data_editor_payload_to_records(payload, fallback)

    assert records == [
        {"Template ID": "TR-1", "Spacing (mm)": 175.0},
        {"Template ID": "TR-3", "Spacing (mm)": 125.0},
    ]


def test_transverse_split_placement_first_edits_commit_without_repeat(monkeypatch) -> None:
    rows = default_crossbeam_transverse_templates()
    cross_section_fallback = [
        {
            "Template ID": row["Template ID"],
            "Cage centerline offset (mm)": row["Center offset mm"],
            "Reference": "FROM CONCRETE FACE",
        }
        for row in rows
    ]
    cross_section_key = "cross-section-placement-editor"
    state: dict[str, object] = {
        CB_TR_TEMPLATE_ROWS_KEY: rows,
        cross_section_key: {
            "edited_rows": {0: {"Cage centerline offset (mm)": 75.0}}
        },
    }
    _fake_streamlit(monkeypatch, transverse_page, state)

    transverse_page._commit_transverse_fields_editor(
        cross_section_key,
        rows,
        cross_section_fallback,
        {"Cage centerline offset (mm)": "Center offset mm"},
    )

    stored = state[CB_TR_TEMPLATE_ROWS_KEY]
    assert stored[0]["Center offset mm"] == 75.0
    assert stored[1]["Center offset mm"] == 50.0

    longitudinal_fallback = [
        {
            "Template ID": row["Template ID"],
            "First set from Zone start (mm)": row["First bar offset mm"],
            "Minimum clearance to Zone end (mm)": row["Last bar offset mm"],
            "Status": "LOCAL ONLY",
        }
        for row in stored
    ]
    longitudinal_key = "longitudinal-placement-editor"
    state[longitudinal_key] = {
        "edited_rows": {
            0: {
                "First set from Zone start (mm)": 100.0,
                "Minimum clearance to Zone end (mm)": 125.0,
            }
        }
    }
    transverse_page._commit_transverse_fields_editor(
        longitudinal_key,
        stored,
        longitudinal_fallback,
        {
            "First set from Zone start (mm)": "First bar offset mm",
            "Minimum clearance to Zone end (mm)": "Last bar offset mm",
        },
    )

    stored = state[CB_TR_TEMPLATE_ROWS_KEY]
    assert stored[0]["First bar offset mm"] == 100.0
    assert stored[0]["Last bar offset mm"] == 125.0


def test_transverse_topology_and_linked_material_first_edits_commit(monkeypatch) -> None:
    rows = default_crossbeam_transverse_templates()
    topology_key = "hollow-editor"
    material_key = "material-editor"
    topology_fallback = [
        {
            "Template ID": row["Template ID"],
            "Bar": row["Bar size"],
            "Spacing (mm)": row["Spacing mm"],
            "Left legs": row["Left web legs"],
            "Right legs": row["Right web legs"],
            "Closed cage": row["Closed cage"],
        }
        for row in rows
        if row["Applicable role"] == "Hollow"
    ]
    state: dict[str, object] = {
        CB_TR_TEMPLATE_ROWS_KEY: rows,
        CB_TR_TEMPLATE_REV_KEY: 0,
        topology_key: {"edited_rows": {0: {"Spacing (mm)": 175.0, "Left legs": 3}}},
    }
    _fake_streamlit(monkeypatch, transverse_page, state)
    transverse_page._commit_transverse_fields_editor(
        topology_key,
        rows,
        topology_fallback,
        {"Spacing (mm)": "Spacing mm", "Left legs": "Left web legs"},
    )
    stored = state[CB_TR_TEMPLATE_ROWS_KEY]
    assert stored[0]["Spacing mm"] == 175.0
    assert stored[0]["Left web legs"] == 3

    material_fallback = [
        {
            "Template ID": row["Template ID"],
            "fy (MPa)": int(row["fy MPa"]),
            "Material": row["Rebar material"],
            "Active": row["Active"],
            "Credit": row["Credit inside segment"],
        }
        for row in stored
    ]
    state[material_key] = {"edited_rows": {0: {"Material": "SD50"}}}
    transverse_page._commit_transverse_material_editor(
        material_key,
        stored,
        material_fallback,
    )
    stored = state[CB_TR_TEMPLATE_ROWS_KEY]
    assert stored[0]["Rebar material"] == "SD50"
    assert stored[0]["fy MPa"] == 490.0
    assert state[CB_TR_TEMPLATE_REV_KEY] == 1


def test_longitudinal_layout_adopted_and_participation_first_edits_commit(monkeypatch) -> None:
    rows = default_crossbeam_rebar_templates()
    outer_key = "outer-editor"
    adopted_key = "adopted-editor"
    participation_key = "participation-editor"
    state: dict[str, object] = {
        CB_RB_TEMPLATE_ROWS_KEY: rows,
        CB_RB_TEMPLATE_REV_KEY: 0,
    }
    _fake_streamlit(monkeypatch, longitudinal_page, state)

    outer_fallback = [
        {
            "Template ID": row["Template ID"],
            "Use": row["Outer face bars"],
            "Bar": row["Outer bar size"],
            "Method": row["Outer layout method"],
            "Fallback offset (mm)": row["Outer center offset mm"],
            "Target": row["Outer target spacing mm"],
        }
        for row in rows
    ]
    state[outer_key] = {"edited_rows": {0: {"Bar": "DB25", "Target": 175.0}}}
    longitudinal_page._commit_template_face_editor(outer_key, rows, outer_fallback, "Outer")
    stored = state[CB_RB_TEMPLATE_ROWS_KEY]
    assert stored[0]["Outer bar size"] == "DB25"
    assert stored[0]["Outer target spacing mm"] == 175.0

    adopted_fallback = [
        {"Template ID": row["Template ID"], "Top As (mm²)": row["Top As mm²"], "Notes": row["Notes"]}
        for row in stored
    ]
    state[adopted_key] = {"edited_rows": {0: {"Top As (mm²)": 2400.0, "Notes": "first edit"}}}
    longitudinal_page._commit_template_fields_editor(
        adopted_key,
        stored,
        adopted_fallback,
        {"Top As (mm²)": "Top As mm²", "Notes": "Notes"},
    )
    stored = state[CB_RB_TEMPLATE_ROWS_KEY]
    assert stored[0]["Top As mm²"] == 2400.0
    assert stored[0]["Notes"] == "first edit"

    participation_fallback = [
        {
            "Template ID": row["Template ID"],
            "Basis": row["Longitudinal basis"],
            "fy (MPa)": int(row["fy MPa"]),
            "Material": row["Rebar material"],
            "Active": row["Active"],
            "Credit": row["Credit inside segment"],
        }
        for row in stored
    ]
    state[participation_key] = {"edited_rows": {0: {"fy (MPa)": 490, "Credit": False}}}
    longitudinal_page._commit_template_participation_editor(
        participation_key,
        stored,
        participation_fallback,
    )
    stored = state[CB_RB_TEMPLATE_ROWS_KEY]
    assert stored[0]["Rebar material"] == "SD50"
    assert stored[0]["fy MPa"] == 490.0
    assert stored[0]["Credit inside segment"] is False
    assert state[CB_RB_TEMPLATE_REV_KEY] == 1


def test_template_rename_first_edit_updates_longitudinal_zone_reference(monkeypatch) -> None:
    segments = default_crossbeam_segment_rows(20.0)
    rows = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, rows, transverse)
    fallback = [
        {
            "_Original ID": row["Template ID"],
            "Copy": False,
            "Delete": False,
            "Template ID": row["Template ID"],
            "Template name": row["Template name"],
            "Role": row["Applicable role"],
            "Construction": row["Construction"],
        }
        for row in rows
    ]
    editor_key = "identity-editor"
    state: dict[str, object] = {
        CB_RB_TEMPLATE_ROWS_KEY: rows,
        CB_RB_ZONE_ROWS_KEY: zones,
        CB_RB_TEMPLATE_REV_KEY: 0,
        CB_RB_ZONE_REV_KEY: 0,
        editor_key: {"edited_rows": {0: {"Template ID": "RB-HOLLOW-USER"}}},
    }
    _fake_streamlit(monkeypatch, longitudinal_page, state)

    longitudinal_page._commit_template_identity_editor(editor_key, rows, fallback)

    assert state[CB_RB_TEMPLATE_ROWS_KEY][0]["Template ID"] == "RB-HOLLOW-USER"
    hollow_zones = [row for row in state[CB_RB_ZONE_ROWS_KEY] if row["Rebar template"] == "RB-HOLLOW-USER"]
    assert hollow_zones
    assert all(row["Longitudinal template"] == "RB-HOLLOW-USER" for row in hollow_zones)
    assert state[CB_RB_TEMPLATE_REV_KEY] == 1
    assert state[CB_RB_ZONE_REV_KEY] == 1


def test_zone_geometry_and_assignment_first_edits_commit(monkeypatch) -> None:
    segments = default_crossbeam_segment_rows(20.0)
    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)
    geometry_fallback = [
        {
            "_Original Zone": row["Zone ID"],
            "Zone": row["Zone ID"],
            "Segment": row["Segment"],
            "Start": row["s_start_m"],
            "End": row["s_end_m"],
            "Section": row["Segment"],
        }
        for row in zones
    ]
    geometry_key = "zone-geometry"
    state: dict[str, object] = {
        CB_RB_TEMPLATE_ROWS_KEY: longitudinal,
        CB_TR_TEMPLATE_ROWS_KEY: transverse,
        CB_RB_ZONE_ROWS_KEY: zones,
        CB_RB_ZONE_REV_KEY: 0,
        geometry_key: {"edited_rows": {0: {"Zone": "Z-S1-EDIT", "End": 1.75}}},
    }
    _fake_streamlit(monkeypatch, longitudinal_page, state)

    longitudinal_page._commit_zone_geometry_editor(
        geometry_key,
        zones,
        geometry_fallback,
        segments,
        longitudinal,
        transverse,
    )

    stored_zones = state[CB_RB_ZONE_ROWS_KEY]
    assert stored_zones[0]["Zone ID"] == "Z-S1-EDIT"
    assert stored_zones[0]["s_end_m"] == 1.75
    assert state[CB_RB_ZONE_REV_KEY] == 1

    assignment_key = "zone-assignment"
    assignment_fallback = [
        {
            "Zone": row["Zone ID"],
            "Longitudinal template": row["Longitudinal template"],
            "Transverse template": row["Transverse template"],
        }
        for row in stored_zones
    ]
    solid_index = next(index for index, row in enumerate(stored_zones) if row["Segment"] == "S1")
    state[assignment_key] = {
        "edited_rows": {
            solid_index: {
                "Longitudinal template": RB_SOLID_ANCHORAGE,
                "Transverse template": TR_SOLID_ANCHORAGE,
            }
        }
    }
    longitudinal_page._commit_zone_assignment_editor(
        assignment_key,
        stored_zones,
        assignment_fallback,
    )
    assigned = state[CB_RB_ZONE_ROWS_KEY][solid_index]
    assert assigned["Rebar template"] == RB_SOLID_ANCHORAGE
    assert assigned["Longitudinal template"] == RB_SOLID_ANCHORAGE
    assert assigned["Transverse template"] == TR_SOLID_ANCHORAGE


def _data_editor_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "data_editor"
    ]


def test_every_crossbeam_rebar_data_editor_has_first_edit_callback() -> None:
    root = Path(__file__).resolve().parents[1]
    paths_and_counts = {
        # RB-CIP2A replaces the single user-facing bar-run editor with the
        # aligned Solid-template/Section-Zone CIP workflow.  All added editors
        # must obey the same first-edit callback contract as Segmental Rebar.
        root / "concrete_pmm_pro" / "ui" / "crossbeam_rebar_page.py": 17,
        root / "concrete_pmm_pro" / "ui" / "crossbeam_transverse_page.py": 7,
    }
    for path, expected_count in paths_and_counts.items():
        calls = _data_editor_calls(path)
        assert len(calls) == expected_count
        for call in calls:
            keyword_names = {keyword.arg for keyword in call.keywords}
            assert "on_change" in keyword_names, f"Missing first-edit callback at {path}:{call.lineno}"
            assert "args" in keyword_names, f"Missing callback args at {path}:{call.lineno}"
