from copy import deepcopy
from pathlib import Path

from concrete_pmm_pro.core.models import Rebar
from concrete_pmm_pro.crossbeam.rebar import default_crossbeam_rebar_templates
from concrete_pmm_pro.crossbeam.section_library import (
    build_geometry_for_definition,
    default_section_definitions,
    definition_map,
)
from concrete_pmm_pro.crossbeam.transverse import (
    TRANSVERSE_PREVIEW_BEND_RADIUS_MM,
    build_transverse_cage_geometry,
    default_crossbeam_transverse_templates,
    review_longitudinal_bar_containment,
)
from concrete_pmm_pro.geometry.rebar_layout import generate_perimeter_rebar_layout
from concrete_pmm_pro.ui.crossbeam_rebar_page import (
    _combined_reinforcement_preview_figure,
    _result_rebars,
)


def _definitions():
    return definition_map(default_section_definitions())


def _transverse(role: str):
    return next(row for row in default_crossbeam_transverse_templates() if row["Applicable role"] == role)


def test_rb2g_solid_tie_follows_bottom_concrete_fillets_and_uses_25_mm_top_bends():
    definition = _definitions()["CB-S01"]
    geometry = build_geometry_for_definition(definition)
    cages = build_transverse_cage_geometry(geometry, definition, _transverse("Solid"))
    assert cages.ok, cages.errors
    assert cages.bend_radius_mm == TRANSVERSE_PREVIEW_BEND_RADIUS_MM == 25.0
    assert len(cages.paths) == 1
    path = cages.paths[0]
    assert path.label == "Closed tie"
    assert len(path.points) > 30
    x0, x1, y0, _y1 = path.envelope
    bottom_curve = [(x, y) for x, y in path.points if y <= y0 + 170.0]
    assert len({round(y, 3) for _x, y in bottom_curve}) > 6
    assert min(x for x, _y in path.points) == x0
    assert max(x for x, _y in path.points) == x1


def test_rb2g_hollow_keeps_two_rectangular_web_cages_and_does_not_follow_void_chamfers():
    definition = _definitions()["CB-H01"]
    geometry = build_geometry_for_definition(definition)
    cages = build_transverse_cage_geometry(geometry, definition, _transverse("Hollow"))
    assert not cages.errors
    assert [path.label for path in cages.paths] == ["Left-web cage", "Right-web cage"]
    hole = geometry.holes[0]
    hole_min_x = min(point.x for point in hole)
    hole_max_x = max(point.x for point in hole)
    left, right = cages.paths
    assert left.envelope[1] == hole_min_x - cages.center_offset_mm
    assert right.envelope[0] == hole_max_x + cages.center_offset_mm
    assert left.envelope[1] - left.envelope[0] == 200.0
    assert right.envelope[1] - right.envelope[0] == 200.0
    assert any("raised" in warning for warning in cages.warnings)


def test_rb2g_hollow_reports_review_when_web_cannot_fit_25_mm_corner_bend():
    definition = deepcopy(_definitions()["CB-H01"])
    definition["Parameters"]["t_left_mm"] = 130.0
    geometry = build_geometry_for_definition(definition)
    cages = build_transverse_cage_geometry(geometry, definition, _transverse("Hollow"))
    assert not cages.ok
    assert any("Left-web cage" in message and "25 mm" in message for message in cages.errors)


def test_rb2g_containment_includes_bar_radii_and_never_moves_longitudinal_inputs():
    definition = _definitions()["CB-S01"]
    geometry = build_geometry_for_definition(definition)
    template = next(row for row in default_crossbeam_rebar_templates() if row["Applicable role"] == "Solid")
    cages = build_transverse_cage_geometry(geometry, definition, _transverse("Solid"))

    default_layout = generate_perimeter_rebar_layout(
        geometry,
        bar_size=template["Outer bar size"],
        diameter_mm=20.0,
        material="SD40",
        edge_offset_mm=50.0,
        target_spacing_mm=200.0,
        min_bars=4,
        label_prefix="O",
    )
    default_bars = _result_rebars(default_layout, layer="Outer")
    default_coordinates = [(bar.x_mm, bar.y_mm) for bar in default_bars]
    review = review_longitudinal_bar_containment(cages, default_bars)
    assert review.status == "REVIEW REQUIRED"
    assert review.conflict_count > 0
    assert any("Outer face/layer" in message for message in review.messages)
    assert [(bar.x_mm, bar.y_mm) for bar in default_bars] == default_coordinates

    inset_layout = generate_perimeter_rebar_layout(
        geometry,
        bar_size=template["Outer bar size"],
        diameter_mm=20.0,
        material="SD40",
        edge_offset_mm=80.0,
        target_spacing_mm=200.0,
        min_bars=4,
        label_prefix="O",
    )
    inset_review = review_longitudinal_bar_containment(cages, _result_rebars(inset_layout, layer="Outer"))
    assert inset_review.status == "READY FOR DETAILING REVIEW"
    assert inset_review.conflict_count == 0


def test_rb2g_combined_figure_uses_required_layer_and_legend_order():
    definition = _definitions()["CB-S01"]
    geometry = build_geometry_for_definition(definition)
    rebars = [
        Rebar(x_mm=-900.0, y_mm=-450.0, diameter_mm=20.0, label="Outer: B1"),
        Rebar(x_mm=900.0, y_mm=-450.0, diameter_mm=20.0, label="Outer: B2"),
        Rebar(x_mm=900.0, y_mm=450.0, diameter_mm=20.0, label="Outer: B3"),
        Rebar(x_mm=-900.0, y_mm=450.0, diameter_mm=20.0, label="Outer: B4"),
    ]
    fig, review = _combined_reinforcement_preview_figure(
        geometry,
        definition,
        _transverse("Solid"),
        outer_rebars=rebars,
        inner_rebars=[],
        title="RB2G",
    )
    names = [str(trace.name) for trace in fig.data]
    assert names[0] == "Concrete"
    cage_index = names.index("Transverse cage / tie")
    longitudinal_index = names.index("Longitudinal bars")
    centroid_index = names.index("Centroid")
    assert cage_index < longitudinal_index < centroid_index
    assert review.ok
    assert fig.layout.meta["crossbeam_rb2g"]["bend_radius_mm"] == 25.0


def test_rb2g_combined_mode_is_one_section_figure_plus_retained_full_length_elevation_and_solver_free():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text()
    assert "_combined_reinforcement_preview_figure" in source
    assert "_render_combined_reinforcement_preview" in source
    assert "transverse_full_elevation_figure" in source
    assert 'if preview_mode == "Transverse / Shear"' in source
    assert "Scope guard" in source
    assert "No solver credit is created" in source
    assert "calculate_shear" not in source
    assert "calculate_torsion" not in source
