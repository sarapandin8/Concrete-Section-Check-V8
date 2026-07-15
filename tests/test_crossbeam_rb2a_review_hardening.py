from pathlib import Path

from concrete_pmm_pro.crossbeam.rebar import (
    RB_HOLLOW_MIN,
    canonical_rebar_templates,
    default_crossbeam_rebar_templates,
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
from concrete_pmm_pro.ui.crossbeam_rebar_page import (
    _adopted_reinforcement_summary,
    _auto_layout_summary,
    _result_rebars,
    _section_rebar_preview_figure,
)


def test_rb2a_template_summary_separates_auto_layout_from_adopted_reinforcement():
    template = canonical_rebar_templates(default_crossbeam_rebar_templates())[0]
    assert template["Template ID"] == RB_HOLLOW_MIN
    assert "Outer" in _auto_layout_summary(template)
    assert "Inner" in _auto_layout_summary(template)
    assert _adopted_reinforcement_summary(template) == "Not adopted"
    template["Top As mm²"] = 1200.0
    template["Bottom As mm²"] = 1400.0
    assert "1200" in _adopted_reinforcement_summary(template)


def test_rb2a_hollow_preview_supports_enhanced_markers_and_true_diameter_modes():
    hollow = definition_map(default_section_definitions())["CB-H01"]
    geometry = build_geometry_for_definition(hollow)
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
    outer = _result_rebars(outer_result, layer="Outer")
    inner = _result_rebars(inner_result, layer="Inner")
    enhanced = _section_rebar_preview_figure(
        geometry,
        outer_rebars=outer,
        inner_rebars=inner,
        title="Enhanced",
        marker_mode="Enhanced markers",
    )
    true_scale = _section_rebar_preview_figure(
        geometry,
        outer_rebars=outer,
        inner_rebars=inner,
        title="True",
        marker_mode="True bar diameter",
    )
    names = {str(trace.name) for trace in enhanced.data}
    assert {"Outer-face bars", "Inner-face bars"}.issubset(names)
    bar_traces = [trace for trace in enhanced.data if trace.name in {"Outer-face bars", "Inner-face bars"}]
    assert max(int(trace.marker.size) for trace in bar_traces) == 10
    assert len(true_scale.layout.shapes) > len(enhanced.layout.shapes)
    assert enhanced.layout.height == 500


def test_rb2a_page_uses_compact_table_columns_and_unverified_tendon_guard():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text()
    assert '"Zone", "Segment", "Start", "End", "Section", "Template"' in source
    for label in ("Template", "Role", "Construction", "Auto layout", "Adopted reinforcement", "Status"):
        assert f'"{label}"' in source
    assert "REQUIRED — NOT VERIFIED" in source
    assert "TENDONS ONLY" not in source
    assert "Enhanced markers" in source
    assert "True bar diameter" in source
    assert "st.tabs(" not in source
