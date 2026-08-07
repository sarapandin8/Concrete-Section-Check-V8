from __future__ import annotations

from copy import deepcopy

from concrete_pmm_pro.analysis.crossbeam_uls import build_crossbeam_uls_flexure_preparation
from concrete_pmm_pro.crossbeam.project_geometry import (
    CROSSBEAM_PROJECT_GEOMETRY_AUDIT_KEY,
    crossbeam_project_geometry_audit,
)
from concrete_pmm_pro.crossbeam.rebar import (
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_PROJECT_LOAD_VALIDATION_KEY,
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
    reset_crossbeam_rebar_zones_from_segment_layout,
)
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_ACTIVE_ID_KEY,
    CB_SECLIB_DEFINITIONS_KEY,
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.transverse import default_crossbeam_transverse_templates
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.io.project_io import (
    CROSSBEAM_UI1A_MIGRATION_STATE_KEY,
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)
from concrete_pmm_pro.ui import crossbeam_pages


def _saved_30m_project_with_stale_45m_rebar() -> tuple[object, list[dict[str, object]]]:
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(30.0), definitions
    )
    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)
    stale_zones = []
    for source in zones:
        row = dict(source)
        row["s_start_m"] = float(row["s_start_m"]) * 1.5
        row["s_end_m"] = float(row["s_end_m"]) * 1.5
        stale_zones.append(row)
    source_state: dict[str, object] = {
        "project_name": "30 m Project JSON authority regression",
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        CB_SECLIB_ACTIVE_ID_KEY: definitions[0]["Section ID"],
        crossbeam_pages.CB_LENGTH_KEY: 30.0,
        crossbeam_pages.CB_SEGMENT_ROWS_KEY: segments,
        CB_RB_TEMPLATE_ROWS_KEY: longitudinal,
        CB_TR_TEMPLATE_ROWS_KEY: transverse,
        CB_RB_ZONE_ROWS_KEY: stale_zones,
    }
    project = project_from_json(project_to_json(project_from_session_state(source_state)))
    return project, segments


def test_canonical_30m_project_restore_wins_over_old_seed_and_stale_widgets(monkeypatch) -> None:
    project, expected_segments = _saved_30m_project_with_stale_45m_rebar()
    restored: dict[str, object] = {
        "crossbeam_pt1b_length_widget_m": 20.0,
        "crossbeam_pt1b_length_widget_synced_m": 20.0,
        "crossbeam_ui1a_segment_editor_7": {"edited_rows": {0: {"End": 20.0}}},
        "crossbeam_tr1_zone_geometry_4": {"edited_rows": {0: {"End": 20.0}}},
    }

    apply_project_to_session_state(project, restored)

    assert restored[crossbeam_pages.CB_LENGTH_KEY] == 30.0
    assert restored[crossbeam_pages.CB_SEGMENT_ROWS_KEY] == expected_segments
    assert restored[CROSSBEAM_UI1A_MIGRATION_STATE_KEY] is True
    assert "crossbeam_pt1b_length_widget_m" not in restored
    assert "crossbeam_pt1b_length_widget_synced_m" not in restored
    assert "crossbeam_ui1a_segment_editor_7" not in restored
    assert "crossbeam_tr1_zone_geometry_4" not in restored

    # Several page-entry reruns must only canonicalize; they must never infer
    # that the saved 30 m coordinates are an untouched default seed.
    class _StreamlitStub:
        session_state = restored

    monkeypatch.setattr(crossbeam_pages, "st", _StreamlitStub())
    for _ in range(3):
        crossbeam_pages._ensure_state()
        assert restored[crossbeam_pages.CB_LENGTH_KEY] == 30.0
        assert restored[crossbeam_pages.CB_SEGMENT_ROWS_KEY] == expected_segments


def test_45m_rebar_is_reported_not_silently_scaled_and_explicit_reset_repairs_it() -> None:
    project, expected_segments = _saved_30m_project_with_stale_45m_rebar()
    restored: dict[str, object] = {}
    apply_project_to_session_state(project, restored)

    original_templates = deepcopy(restored[CB_RB_TEMPLATE_ROWS_KEY])
    original_zone_rows = deepcopy(restored[CB_RB_ZONE_ROWS_KEY])
    audit = restored[CROSSBEAM_PROJECT_GEOMETRY_AUDIT_KEY]
    assert audit["status"] == "INCONSISTENT"
    assert audit["rebar"]["extent_end_m"] == 45.0
    assert audit["rebar"]["reset_supported"] is True
    assert restored[CB_RB_ZONE_ROWS_KEY] == original_zone_rows
    validation = restored[CB_RB_PROJECT_LOAD_VALIDATION_KEY]
    assert validation["status"] == "REVIEW REQUIRED"
    assert any(
        "Rebar Zone extent = 0.000–45.000 m, but Crossbeam length = 30.000 m."
        in message
        for message in validation["errors"]
    )
    preparation = build_crossbeam_uls_flexure_preparation(restored)
    # Segmental Flexure now adopts concrete compression + bonded Tendons only,
    # so stale ordinary-rebar geometry remains a project/rebar REVIEW but does
    # not block the flexural Mn calculation itself.
    assert not any(
        "Rebar Zone extent = 0.000–45.000 m, but Crossbeam length = 30.000 m."
        in message
        for message in preparation.errors
    )
    # This legacy fixture may still be blocked by its old Prestress source, but
    # the stale 45 m ordinary-rebar geometry is no longer a Segmental Flexure
    # blocker because Mn uses the adopted tendon-only basis.

    reset_crossbeam_rebar_zones_from_segment_layout(restored, expected_segments)

    assert restored[CB_RB_TEMPLATE_ROWS_KEY] == original_templates
    assert [row["s_start_m"] for row in restored[CB_RB_ZONE_ROWS_KEY]] == [
        row["x_start_m"] for row in expected_segments
    ]
    assert [row["s_end_m"] for row in restored[CB_RB_ZONE_ROWS_KEY]] == [
        row["x_end_m"] for row in expected_segments
    ]
    assert restored[CB_RB_PROJECT_LOAD_VALIDATION_KEY]["status"] == "READY"
    assert crossbeam_project_geometry_audit(restored)["status"] == "READY"


def test_valid_custom_rebar_subdivision_is_preserved_without_one_click_reset() -> None:
    project, segments = _saved_30m_project_with_stale_45m_rebar()
    restored: dict[str, object] = {}
    apply_project_to_session_state(project, restored)
    reset_crossbeam_rebar_zones_from_segment_layout(restored, segments)
    rows = list(restored[CB_RB_ZONE_ROWS_KEY])
    original = dict(rows[0])
    rows[0] = dict(original, s_end_m=2.0)
    split = dict(original)
    split["Zone ID"] = "Z-S1-B"
    split["s_start_m"] = 2.0
    rows.insert(1, split)
    restored[CB_RB_ZONE_ROWS_KEY] = rows

    audit = crossbeam_project_geometry_audit(restored)

    assert audit["status"] == "READY"
    assert audit["rebar"]["geometry_consistent"] is True
    assert audit["rebar"]["one_zone_per_segment"] is False
    assert audit["rebar"]["reset_supported"] is False


def test_cip_geometry_audit_uses_active_cip_rebar_assignments_not_dormant_precast_rows() -> None:
    active_layout = [
        {
            "Segment": "Z1",
            "x_start_m": 0.0,
            "x_end_m": 30.0,
            "Section ID": "CB-S01",
        }
    ]
    active_cip_zones = [
        {
            "Zone ID": "Z1",
            "Segment": "Z1",
            "s_start_m": 0.0,
            "s_end_m": 30.0,
            "Longitudinal template": "RB-SOLID-COLUMN",
            "Transverse template": "TR-SOLID-COLUMN",
        }
    ]
    dormant_precast_zones = [
        {
            "Zone ID": "Z-S1",
            "Segment": "S1",
            "s_start_m": 0.0,
            "s_end_m": 4.5,
        },
        {
            "Zone ID": "Z-S2",
            "Segment": "S2",
            "s_start_m": 4.5,
            "s_end_m": 30.0,
        },
    ]
    state = {
        "crossbeam_ui1_length_m": 30.0,
        "crossbeam_ui1_segment_layout_rows": active_layout,
        "crossbeam_ptloss3b1_construction_method": "Cast-in-Place",
        "crossbeam_rb_cip2a_zone_assignment_rows": active_cip_zones,
        "crossbeam_rb1_zone_assignment_rows": dormant_precast_zones,
    }

    audit = crossbeam_project_geometry_audit(state)

    assert audit["status"] == "READY"
    assert audit["construction_method"] == "Cast-in-Place"
    assert audit["active_rebar_zone_key"] == "crossbeam_rb_cip2a_zone_assignment_rows"
    assert audit["rebar_zone_count"] == 1
    assert audit["rebar"]["geometry_consistent"] is True
    assert not any(issue.get("Component") == "Rebar Zones" for issue in audit["issues"])
