from pathlib import Path

from concrete_pmm_pro.crossbeam.rebar import (
    TEMPLATE_LAYOUT_METHOD_OPTIONS,
    canonical_rebar_templates,
    default_crossbeam_rebar_templates,
    duplicate_rebar_template,
    new_rebar_template,
)
from concrete_pmm_pro.crossbeam.section_library import (
    build_geometry_for_definition,
    default_section_definitions,
    definition_map,
)
from concrete_pmm_pro.geometry.rebar_layout import (
    generate_inner_face_rebar_layout,
    generate_perimeter_rebar_layout,
)


def test_rb2b_creates_and_duplicates_templates_with_stable_unique_ids():
    defaults = canonical_rebar_templates(default_crossbeam_rebar_templates())
    existing = [row["Template ID"] for row in defaults]
    hollow = new_rebar_template("Hollow", existing)
    solid = new_rebar_template("Solid", existing + [hollow["Template ID"]])
    copy = duplicate_rebar_template(hollow, existing + [hollow["Template ID"], solid["Template ID"]])
    assert hollow["Template ID"].startswith("RB-H")
    assert solid["Template ID"].startswith("RB-S")
    assert copy["Template ID"] not in {hollow["Template ID"], solid["Template ID"], *existing}
    assert copy["Template name"].endswith("— Copy")
    assert hollow["Applicable role"] == "Hollow"
    assert solid["Applicable role"] == "Solid"


def test_rb2b_defaults_and_canonical_rows_support_spacing_or_exact_count():
    template = canonical_rebar_templates(default_crossbeam_rebar_templates())[0]
    assert tuple(TEMPLATE_LAYOUT_METHOD_OPTIONS) == ("By target spacing", "By exact bar count")
    assert template["Outer layout method"] == "By target spacing"
    assert template["Inner layout method"] == "By target spacing"
    template["Outer layout method"] = "By exact bar count"
    template["Outer exact bar count"] = 28
    normalized = canonical_rebar_templates([template])[0]
    assert normalized["Outer layout method"] == "By exact bar count"
    assert normalized["Outer exact bar count"] == 28


def test_rb2b_exact_count_generators_return_requested_bar_counts():
    definitions = definition_map(default_section_definitions())
    hollow_geometry = build_geometry_for_definition(definitions["CB-H01"])
    outer = generate_perimeter_rebar_layout(
        hollow_geometry,
        bar_size="DB16",
        diameter_mm=16.0,
        material="SD40",
        edge_offset_mm=50.0,
        target_spacing_mm=150.0,
        exact_bar_count=24,
    )
    inner = generate_inner_face_rebar_layout(
        hollow_geometry,
        hole_index=0,
        bar_size="DB16",
        diameter_mm=16.0,
        material="SD40",
        edge_offset_mm=50.0,
        target_spacing_mm=150.0,
        exact_bar_count=16,
    )
    assert outer.ok, outer.errors
    assert inner.ok, inner.errors
    assert len(outer.table) == 24
    assert len(inner.table) == 16
    assert any("exact perimeter count" in item for item in outer.info)
    assert any("exact inner-face count" in item for item in inner.info)


def test_rb2b_page_exposes_create_duplicate_delete_and_compact_editing():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text()
    for label in ("Duplicate checked", "New Hollow", "New Solid", "Delete checked"):
        assert label in source
    assert "By exact bar count" in source
    assert "Template identity and row actions" in source
    assert "Outer-face auto layout" in source
    assert "Inner-face auto layout" in source
    assert "st.data_editor(" in source
    assert "Template to edit" not in source
    assert "Edit Selected Template" not in source
