from math import pi
from pathlib import Path

from concrete_pmm_pro.crossbeam.cip_rebar_templates import (
    cip_assigned_longitudinal_quantity_rows,
    cip_longitudinal_quantity_definition,
    default_cip_longitudinal_templates,
    default_cip_transverse_templates,
    default_cip_zone_assignments,
    validate_cip_template_model,
)
from concrete_pmm_pro.crossbeam.rebar import RB_SOLID_COLUMN, canonical_rebar_templates


def _layout():
    return [
        {"Segment": "Z1", "x_start_m": 0.0, "x_end_m": 5.0, "Section role": "Solid", "Section ID": "CB-S01"},
        {"Segment": "Z2", "x_start_m": 5.0, "x_end_m": 15.0, "Section role": "Solid", "Section ID": "CB-S01"},
        {"Segment": "Z3", "x_start_m": 15.0, "x_end_m": 20.0, "Section role": "Solid", "Section ID": "CB-S01"},
    ]


def test_exact_count_is_complete_and_derives_total_perimeter_as():
    template = next(row for row in default_cip_longitudinal_templates() if row["Template ID"] == RB_SOLID_COLUMN)
    template["Outer bar size"] = "DB32"
    template["Outer layout method"] = "By exact bar count"
    template["Outer exact bar count"] = 12

    status = cip_longitudinal_quantity_definition(template)

    assert status["Complete"] is True
    assert status["Source"] == "EXACT BAR COUNT"
    assert status["Derived bar count"] == 12
    assert abs(status["Derived As mm²"] - 12 * pi * 32.0**2 / 4.0) < 1e-6
    assert "12-DB32" in status["Definition"]


def test_target_spacing_is_complete_but_geometry_derived():
    template = next(row for row in default_cip_longitudinal_templates() if row["Template ID"] == RB_SOLID_COLUMN)
    template["Outer bar size"] = "DB25"
    template["Outer layout method"] = "By target spacing"
    template["Outer target spacing mm"] = 150.0

    status = cip_longitudinal_quantity_definition(template)

    assert status["Complete"] is True
    assert status["Source"] == "TARGET SPACING"
    assert status["Geometry derived"] is True
    assert status["Derived bar count"] is None
    assert "assigned Section geometry" in status["Definition"]


def test_adopted_as_is_optional_override_not_required_confirmation():
    template = next(row for row in default_cip_longitudinal_templates() if row["Template ID"] == RB_SOLID_COLUMN)
    template["Top As mm²"] = 2400.0
    template["Bottom As mm²"] = 1800.0
    template["Side As mm²"] = 600.0

    status = cip_longitudinal_quantity_definition(template)

    assert status["Complete"] is True
    assert status["Source"] == "ADOPTED AS OVERRIDE"
    assert status["Derived As mm²"] == 4800.0


def test_disabled_outer_layout_without_override_is_incomplete():
    template = next(row for row in default_cip_longitudinal_templates() if row["Template ID"] == RB_SOLID_COLUMN)
    template["Outer face bars"] = False

    status = cip_longitudinal_quantity_definition(template)

    assert status["Complete"] is False
    assert status["Source"] == "NO OUTER LAYOUT"
    assert "disabled" in status["Issue"]


def test_assigned_exact_count_templates_do_not_trigger_adopted_as_warning():
    layout = _layout()
    long_rows = default_cip_longitudinal_templates()
    support = next(row for row in long_rows if row["Template ID"] == RB_SOLID_COLUMN)
    support["Template ID"] = "RB-SOLID-SUPPORT"
    support["Outer bar size"] = "DB32"
    support["Outer layout method"] = "By exact bar count"
    support["Outer exact bar count"] = 12
    typical = dict(support)
    typical["Template ID"] = "RB-SOLID-TYPICAL"
    typical["Outer exact bar count"] = 8
    long_rows = canonical_rebar_templates([support, typical])
    trans_rows = default_cip_transverse_templates()
    zones = default_cip_zone_assignments(layout, long_rows, trans_rows)
    zones[0]["Longitudinal template"] = zones[0]["Rebar template"] = "RB-SOLID-SUPPORT"
    zones[1]["Longitudinal template"] = zones[1]["Rebar template"] = "RB-SOLID-TYPICAL"
    zones[2]["Longitudinal template"] = zones[2]["Rebar template"] = "RB-SOLID-SUPPORT"

    quantity_rows = cip_assigned_longitudinal_quantity_rows(
        layout_rows=layout,
        longitudinal_templates=long_rows,
        zone_assignments=zones,
    )
    errors, warnings = validate_cip_template_model(
        layout_rows=layout,
        longitudinal_templates=long_rows,
        transverse_templates=trans_rows,
        zone_assignments=zones,
    )

    assert errors == []
    assert warnings == []
    assert {row["Template ID"] for row in quantity_rows} == {"RB-SOLID-SUPPORT", "RB-SOLID-TYPICAL"}
    assert all(row["Complete"] for row in quantity_rows)
    assert {row["Derived bar count"] for row in quantity_rows} == {8, 12}


def test_ui_explains_optional_override_and_exposes_full_transition_details():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text(encoding="utf-8")
    assert "Adopted provided As — optional override / QA" in source
    assert "not a second confirmation step" in source
    assert "Assigned longitudinal quantity sources" in source
    assert "Transition review details" in source
    assert '"Required review": st.column_config.TextColumn(width="large")' in source
    assert "no CIP rebar solver credit from RB-CIP3B" in source
