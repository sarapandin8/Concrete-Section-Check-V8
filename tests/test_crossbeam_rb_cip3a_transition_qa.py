from pathlib import Path

from concrete_pmm_pro.crossbeam.cip_rebar_templates import (
    cip_continuity_audit_rows,
    default_cip_longitudinal_templates,
    default_cip_transverse_templates,
    default_cip_zone_assignments,
)
from concrete_pmm_pro.crossbeam.rebar import RB_SOLID_COLUMN, canonical_rebar_templates


def _layout():
    return [
        {"Segment": "Z1", "x_start_m": 0.0, "x_end_m": 10.0, "Section role": "Solid", "Section ID": "CB-S01"},
        {"Segment": "Z2", "x_start_m": 10.0, "x_end_m": 20.0, "Section role": "Solid", "Section ID": "CB-S01"},
    ]


def _model_with_right_template(right_template_id: str):
    layout = _layout()
    long_rows = default_cip_longitudinal_templates()
    trans_rows = default_cip_transverse_templates()
    zones = default_cip_zone_assignments(layout, long_rows, trans_rows)
    zones[0]["Longitudinal template"] = RB_SOLID_COLUMN
    zones[0]["Rebar template"] = RB_SOLID_COLUMN
    zones[1]["Longitudinal template"] = right_template_id
    zones[1]["Rebar template"] = right_template_id
    return layout, long_rows, zones


def test_matched_adjacent_templates_are_reference_qa_not_certification():
    layout, long_rows, zones = _model_with_right_template(RB_SOLID_COLUMN)
    audit = cip_continuity_audit_rows(layout, zones, long_rows)
    assert audit[0]["Transition"] == "MATCHED LAYOUT"
    assert audit[0]["Quantity change"] == "No template-level change"
    assert "Exact bar identity" in audit[0]["Required review"]


def test_exact_count_increase_is_classified_as_bar_addition():
    layout, long_rows, zones = _model_with_right_template("RB-SOLID-MORE")
    base = next(row for row in long_rows if row["Template ID"] == RB_SOLID_COLUMN)
    base["Outer layout method"] = "By exact bar count"
    base["Outer exact bar count"] = 24
    more = dict(base)
    more["Template ID"] = "RB-SOLID-MORE"
    more["Outer exact bar count"] = 30
    long_rows = canonical_rebar_templates(long_rows + [more])

    audit = cip_continuity_audit_rows(layout, zones, long_rows)
    assert audit[0]["Transition"] == "BAR ADDITION"
    assert audit[0]["Quantity change"] == "+6 perimeter bar(s)"
    assert "development/anchorage remain unverified" in audit[0]["Required review"]


def test_exact_count_decrease_is_classified_as_bar_reduction():
    layout, long_rows, zones = _model_with_right_template("RB-SOLID-LESS")
    base = next(row for row in long_rows if row["Template ID"] == RB_SOLID_COLUMN)
    base["Outer layout method"] = "By exact bar count"
    base["Outer exact bar count"] = 30
    less = dict(base)
    less["Template ID"] = "RB-SOLID-LESS"
    less["Outer exact bar count"] = 24
    long_rows = canonical_rebar_templates(long_rows + [less])

    audit = cip_continuity_audit_rows(layout, zones, long_rows)
    assert audit[0]["Transition"] == "BAR REDUCTION"
    assert audit[0]["Quantity change"] == "6 fewer perimeter bar(s)"
    assert "cut-off and development remain unverified" in audit[0]["Required review"]


def test_target_spacing_change_remains_review_because_actual_count_depends_on_geometry():
    layout, long_rows, zones = _model_with_right_template("RB-SOLID-DENSER")
    base = next(row for row in long_rows if row["Template ID"] == RB_SOLID_COLUMN)
    base["Outer layout method"] = "By target spacing"
    base["Outer target spacing mm"] = 150.0
    denser = dict(base)
    denser["Template ID"] = "RB-SOLID-DENSER"
    denser["Outer target spacing mm"] = 125.0
    long_rows = canonical_rebar_templates(long_rows + [denser])

    audit = cip_continuity_audit_rows(layout, zones, long_rows)
    assert audit[0]["Transition"] == "REVIEW REQUIRED"
    assert audit[0]["Quantity change"] == "Target spacing changes 150.0 → 125.0 mm"
    assert "depends on section geometry" in audit[0]["Required review"]


def test_monotonic_adopted_as_change_is_classified_without_claiming_bar_identity():
    layout, long_rows, zones = _model_with_right_template("RB-SOLID-AS-MORE")
    base = next(row for row in long_rows if row["Template ID"] == RB_SOLID_COLUMN)
    base["Top As mm²"] = 2000.0
    base["Bottom As mm²"] = 1500.0
    base["Side As mm²"] = 500.0
    more = dict(base)
    more["Template ID"] = "RB-SOLID-AS-MORE"
    more["Top As mm²"] = 2500.0
    more["Bottom As mm²"] = 1500.0
    more["Side As mm²"] = 700.0
    long_rows = canonical_rebar_templates(long_rows + [more])

    audit = cip_continuity_audit_rows(layout, zones, long_rows)
    assert audit[0]["Transition"] == "BAR ADDITION"
    assert audit[0]["Quantity change"] == "Adopted As increases by 700.0 mm²"
    assert "Identify continuous bars" in audit[0]["Required review"]


def test_one_zone_has_no_transition_rows():
    layout = _layout()[:1]
    long_rows = default_cip_longitudinal_templates()
    trans_rows = default_cip_transverse_templates()
    zones = default_cip_zone_assignments(layout, long_rows, trans_rows)
    assert cip_continuity_audit_rows(layout, zones, long_rows) == []


def test_cip_transition_ui_states_scope_and_solver_lock():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text(encoding="utf-8")
    assert "Continuity Transition QA" in source
    assert "BAR ADDITION or BAR REDUCTION identifies a quantity transition only" in source
    assert "does not certify development, splice, termination, anchorage, or exact bar identity" in source
    assert "no CIP rebar solver credit from RB-CIP3A" in source


def test_same_template_across_different_section_ids_requires_geometry_transition_review():
    layout = _layout()
    layout[1]["Section ID"] = "CB-S02"
    long_rows = default_cip_longitudinal_templates()
    trans_rows = default_cip_transverse_templates()
    zones = default_cip_zone_assignments(layout, long_rows, trans_rows)

    audit = cip_continuity_audit_rows(layout, zones, long_rows)
    assert audit[0]["Status"] == "MATCHED LAYOUT"  # legacy template-signature field
    assert audit[0]["Transition"] == "REVIEW REQUIRED"
    assert audit[0]["Quantity change"] == "Section geometry changes"
    assert "Generated bar count/coordinates" in audit[0]["Required review"]


def test_one_sided_adopted_as_is_incomplete_not_bar_addition():
    layout, long_rows, zones = _model_with_right_template("RB-SOLID-AS-ONLY-RIGHT")
    base = next(row for row in long_rows if row["Template ID"] == RB_SOLID_COLUMN)
    right = dict(base)
    right["Template ID"] = "RB-SOLID-AS-ONLY-RIGHT"
    right["Top As mm²"] = 2000.0
    long_rows = canonical_rebar_templates(long_rows + [right])

    audit = cip_continuity_audit_rows(layout, zones, long_rows)
    assert audit[0]["Transition"] == "REVIEW REQUIRED"
    assert audit[0]["Quantity change"] == "Adopted As is incomplete on one side"
