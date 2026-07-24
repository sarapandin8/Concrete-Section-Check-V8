from pathlib import Path

from concrete_pmm_pro.crossbeam.cip_rebar_templates import (
    cip_adopted_zone_reinforcement_rows,
    cip_continuity_audit_rows,
    default_cip_longitudinal_templates,
    default_cip_transverse_templates,
    default_cip_zone_assignments,
    validate_cip_template_model,
)
from concrete_pmm_pro.crossbeam.rebar import RB_SOLID_ANCHORAGE, RB_SOLID_COLUMN, canonical_rebar_templates


def _layout_two_zones():
    return [
        {"Segment": "Z1", "x_start_m": 0.0, "x_end_m": 10.0, "Section role": "Solid", "Section ID": "CB-S01"},
        {"Segment": "Z2", "x_start_m": 10.0, "x_end_m": 20.0, "Section role": "Solid", "Section ID": "CB-S01"},
    ]


def test_cip_zone_assignment_is_adopted_source_even_when_legacy_credit_flag_is_false():
    layout = [_layout_two_zones()[0]]
    long_rows = default_cip_longitudinal_templates()
    trans_rows = default_cip_transverse_templates()
    anchorage = next(row for row in long_rows if row["Template ID"] == RB_SOLID_ANCHORAGE)
    # This legacy field came from the Precast-oriented template schema.  It must
    # not veto a deliberate CIP Section/Zone assignment.
    anchorage["Credit inside segment"] = False
    zones = default_cip_zone_assignments(layout, long_rows, trans_rows)
    zones[0]["Longitudinal template"] = RB_SOLID_ANCHORAGE
    zones[0]["Rebar template"] = RB_SOLID_ANCHORAGE

    resolved = cip_adopted_zone_reinforcement_rows(
        layout_rows=layout,
        longitudinal_templates=long_rows,
        transverse_templates=trans_rows,
        zone_assignments=zones,
    )

    assert resolved[0]["Status"] == "ADOPTED SOURCE"
    assert resolved[0]["Adoption basis"] == "Section / Zone assignment"
    assert resolved[0]["Longitudinal template"] == RB_SOLID_ANCHORAGE
    assert resolved[0]["Longitudinal source"] is not None
    assert resolved[0]["Longitudinal source"]["Credit inside segment"] is False


def test_cip_continuity_comparison_ignores_legacy_credit_metadata():
    layout = _layout_two_zones()
    long_rows = default_cip_longitudinal_templates()
    trans_rows = default_cip_transverse_templates()
    base = next(row for row in long_rows if row["Template ID"] == RB_SOLID_COLUMN)
    copy = dict(base)
    copy["Template ID"] = "RB-SOLID-SAME-LAYOUT"
    copy["Template name"] = "Same layout with different legacy credit metadata"
    copy["Credit inside segment"] = not bool(base.get("Credit inside segment"))
    long_rows = canonical_rebar_templates(long_rows + [copy])

    zones = default_cip_zone_assignments(layout, long_rows, trans_rows)
    zones[0]["Longitudinal template"] = RB_SOLID_COLUMN
    zones[0]["Rebar template"] = RB_SOLID_COLUMN
    zones[1]["Longitudinal template"] = "RB-SOLID-SAME-LAYOUT"
    zones[1]["Rebar template"] = "RB-SOLID-SAME-LAYOUT"

    audit = cip_continuity_audit_rows(layout, zones, long_rows)
    assert audit[0]["Status"] == "MATCHED LAYOUT"


def test_cip_completeness_warnings_follow_assigned_templates_only():
    layout = [_layout_two_zones()[0]]
    long_rows = default_cip_longitudinal_templates()
    trans_rows = default_cip_transverse_templates()
    for row in long_rows:
        if row["Template ID"] == RB_SOLID_COLUMN:
            row["Top As mm²"] = 1000.0
            row["Bottom As mm²"] = 1000.0
    zones = default_cip_zone_assignments(layout, long_rows, trans_rows)
    zones[0]["Longitudinal template"] = RB_SOLID_COLUMN
    zones[0]["Rebar template"] = RB_SOLID_COLUMN

    errors, warnings = validate_cip_template_model(
        layout_rows=layout,
        longitudinal_templates=long_rows,
        transverse_templates=trans_rows,
        zone_assignments=zones,
    )

    assert errors == []
    assert not any(RB_SOLID_ANCHORAGE in warning for warning in warnings)


def test_cip_longitudinal_ui_has_no_credit_checkbox():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text(encoding="utf-8")
    start = source.index("def _render_cip_longitudinal_template_library")
    end = source.index("def _merge_cip_transverse_rows", start)
    cip_function = source[start:end]
    assert 'CheckboxColumn("Credit in zone"' not in cip_function
    assert "Section / Zone" in cip_function
    assert "single adopted-reinforcement assignment" in cip_function
