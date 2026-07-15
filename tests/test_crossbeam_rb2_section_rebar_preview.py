from pathlib import Path

from concrete_pmm_pro.crossbeam.rebar import (
    RB_HOLLOW_MIN,
    RB_SOLID_COLUMN,
    canonical_rebar_templates,
    default_crossbeam_rebar_templates,
    rebar_diameter_mm,
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
from concrete_pmm_pro.ui.crossbeam_rebar_page import _section_rebar_preview_figure, _result_rebars


def test_rb2_default_templates_include_low_effort_auto_layout_controls():
    rows = canonical_rebar_templates(default_crossbeam_rebar_templates())
    by_id = {row["Template ID"]: row for row in rows}
    hollow = by_id[RB_HOLLOW_MIN]
    solid = by_id[RB_SOLID_COLUMN]
    assert hollow["Outer face bars"] is True
    assert hollow["Inner face bars"] is True
    assert hollow["Outer bar size"] == "DB16"
    assert hollow["Inner bar size"] == "DB16"
    assert solid["Outer face bars"] is True
    assert solid["Inner face bars"] is False
    assert solid["Outer bar size"] == "DB20"
    assert rebar_diameter_mm("DB20") == 20.0


def test_rb2_generates_outer_and_inner_face_bars_for_default_hollow_section():
    definitions = default_section_definitions()
    hollow = definition_map(definitions)["CB-H01"]
    geometry = build_geometry_for_definition(hollow)
    outer = generate_perimeter_rebar_layout(
        geometry,
        bar_size="DB16",
        diameter_mm=16.0,
        material="SD40",
        edge_offset_mm=50.0,
        target_spacing_mm=150.0,
        min_bars=4,
        label_prefix="O",
    )
    inner = generate_inner_face_rebar_layout(
        geometry,
        hole_index=0,
        bar_size="DB16",
        diameter_mm=16.0,
        material="SD40",
        edge_offset_mm=50.0,
        target_spacing_mm=150.0,
        min_bars=4,
        label_prefix="I",
    )
    assert outer.ok, outer.errors
    assert inner.ok, inner.errors
    assert len(outer.table) > 4
    assert len(inner.table) > 4
    assert all(str(label).startswith("O") for label in outer.table["Label"])
    assert all(str(label).startswith("I") for label in inner.table["Label"])


def test_rb2_inner_face_layout_rejects_solid_section_without_void():
    definitions = default_section_definitions()
    solid = definition_map(definitions)["CB-S01"]
    geometry = build_geometry_for_definition(solid)
    result = generate_inner_face_rebar_layout(
        geometry,
        hole_index=0,
        bar_size="DB16",
        diameter_mm=16.0,
        material="SD40",
    )
    assert not result.ok
    assert "no void/hole" in result.errors[0]


def test_rb2_preview_figure_keeps_outer_and_inner_layers_distinct():
    definitions = default_section_definitions()
    geometry = build_geometry_for_definition(definition_map(definitions)["CB-H01"])
    outer_result = generate_perimeter_rebar_layout(
        geometry,
        bar_size="DB16",
        diameter_mm=16.0,
        material="SD40",
        edge_offset_mm=50.0,
        target_spacing_mm=200.0,
        min_bars=4,
        label_prefix="O",
    )
    inner_result = generate_inner_face_rebar_layout(
        geometry,
        hole_index=0,
        bar_size="DB16",
        diameter_mm=16.0,
        material="SD40",
        edge_offset_mm=50.0,
        target_spacing_mm=200.0,
        min_bars=4,
        label_prefix="I",
    )
    fig = _section_rebar_preview_figure(
        geometry,
        outer_rebars=_result_rebars(outer_result, layer="Outer"),
        inner_rebars=_result_rebars(inner_result, layer="Inner"),
        title="RB2 preview",
    )
    names = {str(trace.name) for trace in fig.data}
    assert "Outer-face bars" in names
    assert "Inner-face bars" in names
    assert fig.layout.title.text == "RB2 preview"


def test_rb2_page_uses_separated_button_subnavigation_and_remains_solver_free():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text()
    assert "Section Rebar Preview" in source
    assert "_render_rb2_subnavigation" in source
    assert "st.tabs(" not in source
    assert "generate_inner_face_rebar_layout" in source
    assert "calculate_pmm" not in source
    assert "calculate_flexure" not in source
    assert "calculate_shear" not in source
