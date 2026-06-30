from __future__ import annotations

from math import dist

import pytest
from shapely.geometry import Point, Polygon

from concrete_pmm_pro.geometry import generators as g
from concrete_pmm_pro.geometry.rebar_layout import _minimum_center_spacing_for_layout, generate_perimeter_rebar_layout
from concrete_pmm_pro.geometry.summary import to_shapely_polygon


def _bar_points(result) -> list[tuple[float, float]]:
    return [(float(row.x_mm), float(row.y_mm)) for row in result.table.itertuples()]


def _nearest_spacing(points: list[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 1.0e9
    return min(dist(a, b) for index, a in enumerate(points) for b in points[index + 1 :])


def _hole_polygons(geometry):
    return [Polygon([point.as_tuple() for point in hole]) for hole in geometry.holes]


@pytest.mark.parametrize(
    ("case_name", "geometry"),
    [
        ("rectangular_chamfered", g.rectangular_chamfered(1000.0, 600.0, chamfer_mm=90.0)),
        ("rectangular_filleted", g.rectangular_filleted(1000.0, 600.0, corner_radius_mm=80.0, n_fillet=12)),
        ("rectangular_hollow", g.rectangular_hollow(1000.0, 800.0, wall_thickness_mm=140.0)),
        (
            "rectangular_hollow_filleted",
            g.rectangular_hollow_filleted(
                1000.0,
                800.0,
                wall_thickness_mm=150.0,
                r_outer_mm=60.0,
                r_inner_mm=40.0,
                n_fillet=12,
            ),
        ),
        (
            "box_section_fillet",
            g.box_section_fillet(
                width_mm=1200.0,
                height_mm=650.0,
                wall_thickness_mm=150.0,
                r_inner_mm=45.0,
                r_outer_mm=25.0,
            ),
        ),
        (
            "parametric_i_girder",
            g.parametric_i_girder(
                B1_mm=800.0,
                B2_mm=500.0,
                D1_mm=1400.0,
                D2_mm=200.0,
                D3_mm=150.0,
                D5_mm=250.0,
                D6_mm=150.0,
                T1_mm=200.0,
                T2_mm=200.0,
                C1_mm=40.0,
            ),
        ),
        (
            "plank_girder_interior",
            g.parametric_plank_girder_interior(
                B_mm=990.0,
                b1_mm=45.0,
                b2_mm=70.0,
                b3_mm=850.0,
                H_mm=450.0,
                h1_mm=80.0,
                h2_mm=140.0,
            ),
        ),
        (
            "voided_plank_girder_interior",
            g.parametric_plank_girder_voided_interior(
                B_mm=990.0,
                b1_mm=45.0,
                b2_mm=70.0,
                b3_mm=850.0,
                H_mm=450.0,
                h1_mm=80.0,
                h2_mm=140.0,
            ),
        ),
        (
            "plank_girder_exterior",
            g.parametric_plank_girder_exterior(
                B_mm=920.0,
                b1_mm=45.0,
                b2_mm=70.0,
                b3_mm=850.0,
                H_mm=450.0,
                h1_mm=80.0,
                h2_mm=140.0,
                overhang_mm=420.0,
            ),
        ),
    ],
)
def test_rebar_auto_perimeter_qa1_keeps_generated_bars_separated_inside_concrete(case_name: str, geometry) -> None:
    result = generate_perimeter_rebar_layout(
        geometry,
        bar_size="DB20",
        diameter_mm=20.0,
        material="SD40",
        edge_offset_mm=75.0,
        target_spacing_mm=150.0,
        min_bars=4,
        label_prefix="B",
    )

    assert result.ok, case_name
    points = _bar_points(result)
    guard = _minimum_center_spacing_for_layout(20.0, 150.0)
    assert _nearest_spacing(points) >= guard - 1.0e-6, case_name

    section_polygon = to_shapely_polygon(geometry)
    holes = _hole_polygons(geometry)
    for x_mm, y_mm in points:
        point = Point(x_mm, y_mm)
        assert section_polygon.covers(point), case_name
        assert not any(hole.covers(point) for hole in holes), case_name

    assert len(points) == len({(round(x, 3), round(y, 3)) for x, y in points}), case_name


def test_rebar_auto_perimeter_qa1_merges_spatially_close_i_girder_web_face_bars() -> None:
    geometry = g.parametric_i_girder(
        B1_mm=800.0,
        B2_mm=500.0,
        D1_mm=1400.0,
        D2_mm=200.0,
        D3_mm=150.0,
        D5_mm=250.0,
        D6_mm=150.0,
        T1_mm=200.0,
        T2_mm=200.0,
        C1_mm=40.0,
    )

    result = generate_perimeter_rebar_layout(
        geometry,
        bar_size="DB20",
        diameter_mm=20.0,
        material="SD40",
        edge_offset_mm=75.0,
        target_spacing_mm=150.0,
        min_bars=4,
        label_prefix="B",
    )

    assert result.ok
    assert any("Merged 6 spatially close" in warning for warning in result.warnings)
    points = _bar_points(result)
    assert _nearest_spacing(points) >= _minimum_center_spacing_for_layout(20.0, 150.0)
    # The narrow web no longer draws two nearly coincident offset-face bar lines;
    # merged bars land on the web centerline where the two lines would collide.
    centerline_web_bars = [(x, y) for x, y in points if abs(x) <= 1.0e-6 and -360.0 < y < 420.0]
    assert len(centerline_web_bars) >= 4


def test_rebar_auto_perimeter_qa1_closeout_document_records_matrix_scope() -> None:
    source = (pytest.importorskip("pathlib").Path(__file__).resolve().parents[1] / "docs" / "design" / "rebar_auto_perimeter_qa1.md").read_text(encoding="utf-8")

    assert "REBAR.AUTO.PERIMETER.QA1" in source
    assert "rectangular / chamfered / filleted" in source
    assert "hollow / box / I-girder / plank / voided plank" in source
    assert "spatially close" in source
