from concrete_pmm_pro.crossbeam.cip_rebar_persistence import (
    CROSSBEAM_CIP_REBAR_METADATA_KEY,
    CIP_RB_TEMPLATE_ROWS_KEY,
    CIP_RB_ZONE_ROWS_KEY,
    CIP_TR_TEMPLATE_ROWS_KEY,
    crossbeam_cip_rebar_metadata_from_session_state,
    restore_crossbeam_cip_rebar_project_state,
)
from concrete_pmm_pro.crossbeam.cip_rebar_templates import (
    cip_continuity_audit_rows,
    default_cip_longitudinal_templates,
    default_cip_transverse_templates,
    default_cip_zone_assignments,
    reconcile_cip_zone_assignments,
    validate_cip_template_model,
)


def _layout():
    return [
        {"Segment": "Z1", "x_start_m": 0.0, "x_end_m": 5.0, "Section role": "Solid", "Section ID": "CB-S01"},
        {"Segment": "Z2", "x_start_m": 5.0, "x_end_m": 15.0, "Section role": "Solid", "Section ID": "CB-S02"},
        {"Segment": "Z3", "x_start_m": 15.0, "x_end_m": 20.0, "Section role": "Solid", "Section ID": "CB-S01"},
    ]


def test_cip_template_libraries_are_solid_only():
    long_rows = default_cip_longitudinal_templates()
    trans_rows = default_cip_transverse_templates()
    assert long_rows
    assert trans_rows
    assert {row["Applicable role"] for row in long_rows} == {"Solid"}
    assert {row["Applicable role"] for row in trans_rows} == {"Solid"}
    assert {row["Construction"] for row in long_rows} == {"Cast in place"}
    assert {row["Construction"] for row in trans_rows} == {"Cast in place"}


def test_cip_zone_assignments_follow_section_zone_ids_not_segment_joint_semantics():
    long_rows = default_cip_longitudinal_templates()
    trans_rows = default_cip_transverse_templates()
    zones = default_cip_zone_assignments(_layout(), long_rows, trans_rows)
    assert [row["Zone ID"] for row in zones] == ["Z1", "Z2", "Z3"]
    assert [row["Segment"] for row in zones] == ["Z1", "Z2", "Z3"]
    errors, _warnings = validate_cip_template_model(
        layout_rows=_layout(),
        longitudinal_templates=long_rows,
        transverse_templates=trans_rows,
        zone_assignments=zones,
    )
    assert errors == []


def test_cip_continuity_audit_matches_equal_adjacent_layouts_and_reviews_changes():
    long_rows = default_cip_longitudinal_templates()
    trans_rows = default_cip_transverse_templates()
    zones = default_cip_zone_assignments(_layout(), long_rows, trans_rows)
    rows = cip_continuity_audit_rows(_layout(), zones, long_rows)
    assert len(rows) == 2
    assert {row["Status"] for row in rows} == {"MATCHED LAYOUT"}

    # Assign a different Solid template to Z2. The boundary is still not a
    # physical joint, but the change must require continuity review.
    zones[1]["Longitudinal template"] = "RB-SOLID-ANCHORAGE"
    zones[1]["Rebar template"] = "RB-SOLID-ANCHORAGE"
    changed = cip_continuity_audit_rows(_layout(), zones, long_rows)
    assert changed[0]["Status"] == "REVIEW REQUIRED"
    assert changed[1]["Status"] == "REVIEW REQUIRED"


def test_reconcile_preserves_dormant_cip_zone_assignments_non_destructively():
    long_rows = default_cip_longitudinal_templates()
    trans_rows = default_cip_transverse_templates()
    zones = default_cip_zone_assignments(_layout(), long_rows, trans_rows)
    reduced_layout = _layout()[:2]
    reconciled = reconcile_cip_zone_assignments(zones, reduced_layout, long_rows, trans_rows)
    assert [row["Zone ID"] for row in reconciled[:2]] == ["Z1", "Z2"]
    assert any(row["Zone ID"] == "Z3" for row in reconciled)


def test_project_json_round_trip_preserves_cip_template_model_separate_from_precast_state():
    long_rows = default_cip_longitudinal_templates()
    trans_rows = default_cip_transverse_templates()
    zones = default_cip_zone_assignments(_layout(), long_rows, trans_rows)
    state = {
        CIP_RB_TEMPLATE_ROWS_KEY: long_rows,
        CIP_TR_TEMPLATE_ROWS_KEY: trans_rows,
        CIP_RB_ZONE_ROWS_KEY: zones,
        "crossbeam_rb1_template_rows": [{"Template ID": "PRECAST-ONLY"}],
    }
    payload = crossbeam_cip_rebar_metadata_from_session_state(state)
    assert payload["schema_version"] == 2
    assert payload["longitudinal_templates"]
    assert payload["transverse_templates"]
    assert payload["zone_assignments"]
    assert "PRECAST-ONLY" not in str(payload)

    restored = {"crossbeam_rb1_template_rows": [{"Template ID": "PRECAST-ONLY"}]}
    result = restore_crossbeam_cip_rebar_project_state(
        {CROSSBEAM_CIP_REBAR_METADATA_KEY: payload}, restored, length_m=20.0
    )
    assert result is not None
    assert restored["crossbeam_rb1_template_rows"] == [{"Template ID": "PRECAST-ONLY"}]
    assert restored[CIP_RB_TEMPLATE_ROWS_KEY][0]["Applicable role"] == "Solid"
    assert restored[CIP_RB_ZONE_ROWS_KEY][0]["Zone ID"] == "Z1"


def test_cip_ui_no_longer_exposes_add_draft_bar_run():
    from pathlib import Path

    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text(encoding="utf-8")
    model_source = Path("concrete_pmm_pro/crossbeam/cip_rebar_templates.py").read_text(encoding="utf-8")
    assert "Add draft bar run" not in source
    assert "Rebar Template Library" in source
    assert "Section / Zone Reinforcement Assignment" in source
    assert "Continuity & Station Audit" in model_source
