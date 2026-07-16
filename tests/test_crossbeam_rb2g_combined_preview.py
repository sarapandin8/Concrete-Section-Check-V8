from copy import deepcopy
from pathlib import Path

import pytest
from shapely.geometry import LineString, Point

from concrete_pmm_pro.core.models import Rebar
from concrete_pmm_pro.crossbeam.rebar import (
    cage_relative_longitudinal_center_offset_mm,
    default_crossbeam_rebar_templates,
    rebar_diameter_mm,
)
from concrete_pmm_pro.crossbeam.section_library import (
    build_geometry_for_definition,
    default_section_definitions,
    definition_map,
)
from concrete_pmm_pro.crossbeam.transverse import (
    TRANSVERSE_PATH_CLOSED_LOOP,
    TRANSVERSE_PATH_STRAIGHT_BAR,
    TRANSVERSE_PATH_U_BAR,
    TRANSVERSE_PREVIEW_BEND_RADIUS_MM,
    build_transverse_cage_geometry,
    default_crossbeam_transverse_templates,
    place_longitudinal_bars_relative_to_cages,
    review_longitudinal_bar_containment,
    transverse_bar_diameter_mm,
)
from concrete_pmm_pro.geometry.rebar_layout import (
    generate_inner_face_rebar_layout,
    generate_perimeter_rebar_layout,
)
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


def test_rb2g2_hollow_builds_two_closed_web_loops_four_flange_u_bars_and_four_chamfer_bars():
    definition = _definitions()["CB-H01"]
    geometry = build_geometry_for_definition(definition)
    cages = build_transverse_cage_geometry(geometry, definition, _transverse("Hollow"))
    assert cages.ok, cages.errors
    assert [path.label for path in cages.paths] == [
        "Left web closed loop",
        "Right web closed loop",
        "Top outer flange U-bar",
        "Top inner flange U-bar",
        "Bottom outer flange U-bar",
        "Bottom inner flange U-bar",
        "Top-left chamfer straight bar",
        "Top-right chamfer straight bar",
        "Bottom-left chamfer straight bar",
        "Bottom-right chamfer straight bar",
    ]
    assert [path.kind for path in cages.paths].count(TRANSVERSE_PATH_CLOSED_LOOP) == 2
    assert [path.kind for path in cages.paths].count(TRANSVERSE_PATH_U_BAR) == 4
    assert [path.kind for path in cages.paths].count(TRANSVERSE_PATH_STRAIGHT_BAR) == 4
    assert all(path.points[0] == path.points[-1] for path in cages.closed_loops)
    assert all(path.points[0] != path.points[-1] for path in cages.u_bars)
    assert all(len(path.points) == 2 for path in cages.straight_bars)
    hole = geometry.holes[0]
    hole_chamfers = [
        LineString(((start.x, start.y), (end.x, end.y)))
        for start, end in zip(hole, hole[1:] + hole[:1])
        if abs(start.x - end.x) > 1.0e-9 and abs(start.y - end.y) > 1.0e-9
    ]
    assert len(hole_chamfers) == 4
    assert all(
        min(LineString(path.points).distance(chamfer) for chamfer in hole_chamfers)
        == pytest.approx(cages.center_offset_mm, abs=1.0e-6)
        for path in cages.straight_bars
    )
    hole_min_x = min(point.x for point in hole)
    hole_max_x = max(point.x for point in hole)
    left, right = cages.closed_loops
    assert left.envelope[1] == hole_min_x - cages.center_offset_mm
    assert right.envelope[0] == hole_max_x + cages.center_offset_mm
    assert left.envelope[1] - left.envelope[0] == 200.0
    assert right.envelope[1] - right.envelope[0] == 200.0
    left_bottom_curve = [(x, y) for x, y in left.points if y <= left.envelope[2] + 160.0]
    assert len({round(y, 3) for _x, y in left_bottom_curve}) > 6
    assert not any("raised" in warning for warning in cages.warnings)


def test_rb2g_hollow_reports_review_when_web_cannot_fit_25_mm_corner_bend():
    definition = deepcopy(_definitions()["CB-H01"])
    definition["Parameters"]["t_left_mm"] = 130.0
    geometry = build_geometry_for_definition(definition)
    cages = build_transverse_cage_geometry(geometry, definition, _transverse("Hollow"))
    assert not cages.ok
    assert any("Left web closed loop" in message and "25 mm" in message for message in cages.errors)


def test_rb2g_cage_relative_offset_uses_transverse_and_longitudinal_radii():
    assert cage_relative_longitudinal_center_offset_mm(50.0, 12.0, 16.0) == 64.0
    assert cage_relative_longitudinal_center_offset_mm(50.0, 16.0, 20.0) == 68.0


def test_rb2g_solid_places_longitudinal_centers_exactly_one_radius_sum_inside_tie():
    definition = _definitions()["CB-S01"]
    geometry = build_geometry_for_definition(definition)
    template = next(row for row in default_crossbeam_rebar_templates() if row["Applicable role"] == "Solid")
    transverse = _transverse("Solid")
    cages = build_transverse_cage_geometry(geometry, definition, transverse)
    longitudinal_diameter = rebar_diameter_mm(template["Outer bar size"])
    transverse_diameter = transverse_bar_diameter_mm(transverse["Bar size"])
    effective_offset = cage_relative_longitudinal_center_offset_mm(
        transverse["Center offset mm"],
        transverse_diameter,
        longitudinal_diameter,
    )

    layout = generate_perimeter_rebar_layout(
        geometry,
        bar_size=template["Outer bar size"],
        diameter_mm=longitudinal_diameter,
        material="SD40",
        edge_offset_mm=effective_offset,
        target_spacing_mm=200.0,
        min_bars=4,
        label_prefix="O",
    )
    source_bars = _result_rebars(layout, layer="Outer")
    source_coordinates = [(bar.x_mm, bar.y_mm) for bar in source_bars]
    placement = place_longitudinal_bars_relative_to_cages(cages, source_bars)
    assert placement.adjusted_count > 0
    assert [(bar.x_mm, bar.y_mm) for bar in source_bars] == source_coordinates
    review = review_longitudinal_bar_containment(cages, placement.rebars)
    assert review.status == "READY FOR DETAILING REVIEW"
    assert review.conflict_count == 0
    tie_line = LineString(cages.paths[0].points)
    required = 0.5 * (transverse_diameter + longitudinal_diameter)
    assert all(
        tie_line.distance(Point(bar.x_mm, bar.y_mm)) == pytest.approx(required, abs=1.0e-6)
        for bar in placement.rebars
    )


def test_rb2g_hollow_web_bars_follow_cages_while_flange_bars_remain_between_webs():
    definition = _definitions()["CB-H01"]
    geometry = build_geometry_for_definition(definition)
    template = next(row for row in default_crossbeam_rebar_templates() if row["Applicable role"] == "Hollow")
    transverse = _transverse("Hollow")
    cages = build_transverse_cage_geometry(geometry, definition, transverse)
    transverse_diameter = transverse_bar_diameter_mm(transverse["Bar size"])
    longitudinal_diameter = rebar_diameter_mm(template["Outer bar size"])
    effective_offset = cage_relative_longitudinal_center_offset_mm(
        transverse["Center offset mm"],
        transverse_diameter,
        longitudinal_diameter,
    )
    outer = generate_perimeter_rebar_layout(
        geometry,
        bar_size=template["Outer bar size"],
        diameter_mm=longitudinal_diameter,
        material="SD40",
        edge_offset_mm=effective_offset,
        target_spacing_mm=150.0,
        min_bars=4,
        label_prefix="O",
    )
    inner = generate_inner_face_rebar_layout(
        geometry,
        hole_index=0,
        bar_size=template["Inner bar size"],
        diameter_mm=rebar_diameter_mm(template["Inner bar size"]),
        material="SD40",
        edge_offset_mm=effective_offset,
        target_spacing_mm=150.0,
        min_bars=4,
        label_prefix="I",
    )
    outer_placement = place_longitudinal_bars_relative_to_cages(cages, _result_rebars(outer, layer="Outer"))
    inner_placement = place_longitudinal_bars_relative_to_cages(cages, _result_rebars(inner, layer="Inner"))
    bars = outer_placement.rebars + inner_placement.rebars
    assert outer_placement.adjusted_count + inner_placement.adjusted_count > 0
    review = review_longitudinal_bar_containment(cages, bars)
    assert review.ok, review.messages
    assert review.status == "NO GEOMETRIC CLASH — PREVIEW"
    cage_lines = [LineString(path.points) for path in cages.closed_loops]
    all_transverse_lines = [LineString(path.points) for path in cages.paths]
    required = 0.5 * (transverse_diameter + longitudinal_diameter)
    associated = [
        bar
        for bar in bars
        if any(path.envelope[0] <= bar.x_mm <= path.envelope[1] for path in cages.closed_loops)
    ]
    flange_only = [bar for bar in bars if bar not in associated]
    assert associated and flange_only
    assert all(
        min(line.distance(Point(bar.x_mm, bar.y_mm)) for line in cage_lines)
        == pytest.approx(required, abs=1.0e-6)
        for bar in associated
    )
    assert all(
        min(line.distance(Point(bar.x_mm, bar.y_mm)) for line in all_transverse_lines)
        == pytest.approx(required, abs=0.6)
        for bar in bars
    )


def test_rb2g2_hollow_combined_figure_reports_the_full_piece_topology():
    definition = _definitions()["CB-H01"]
    geometry = build_geometry_for_definition(definition)
    fig, _review = _combined_reinforcement_preview_figure(
        geometry,
        definition,
        _transverse("Hollow"),
        outer_rebars=[],
        inner_rebars=[],
        title="RB2G2",
    )
    meta = fig.layout.meta["crossbeam_rb2g"]
    assert meta["closed_loop_count"] == 2
    assert meta["u_bar_count"] == 4
    assert meta["straight_bar_count"] == 4
    transverse_names = [str(trace.name) for trace in fig.data]
    assert "Transverse cage / tie" in transverse_names
    assert "Top outer flange U-bar" in transverse_names
    assert "Top-left chamfer straight bar" in transverse_names


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
    assert "cage_relative_longitudinal_center_offset_mm" in source
    assert "place_longitudinal_bars_relative_to_cages" in source
    assert "calculate_shear" not in source
    assert "calculate_torsion" not in source
