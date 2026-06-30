from __future__ import annotations

import math
from dataclasses import dataclass

import pytest

from concrete_pmm_pro.geometry.generators import (
    rectangular_hollow,
    rectangular_hollow_filleted,
    rectangular_hollow_outer_filleted_inner_chamfered,
)
from concrete_pmm_pro.geometry.summary import summarize_geometry


@dataclass(frozen=True)
class _ClosedFormSectionProperties:
    area_mm2: float
    centroid_x_mm: float
    centroid_y_mm: float
    ix_nmm4: float
    iy_nmm4: float
    ixy_nmm4: float


def _rectangular_hollow_closed_form(
    *,
    width_mm: float,
    height_mm: float,
    t_top_mm: float,
    t_bottom_mm: float,
    t_left_mm: float,
    t_right_mm: float,
) -> _ClosedFormSectionProperties:
    """Independent closed-form benchmark for a sharp rectangular hollow section."""

    outer_area = width_mm * height_mm
    inner_width = width_mm - t_left_mm - t_right_mm
    inner_height = height_mm - t_top_mm - t_bottom_mm
    inner_area = inner_width * inner_height
    inner_cx = (-width_mm / 2.0 + t_left_mm + width_mm / 2.0 - t_right_mm) / 2.0
    inner_cy = (-height_mm / 2.0 + t_bottom_mm + height_mm / 2.0 - t_top_mm) / 2.0

    net_area = outer_area - inner_area
    cx = -inner_area * inner_cx / net_area
    cy = -inner_area * inner_cy / net_area

    ix_outer_origin = width_mm * height_mm**3 / 12.0
    iy_outer_origin = height_mm * width_mm**3 / 12.0
    ix_inner_origin = inner_width * inner_height**3 / 12.0 + inner_area * inner_cy**2
    iy_inner_origin = inner_height * inner_width**3 / 12.0 + inner_area * inner_cx**2
    ixy_inner_origin = inner_area * inner_cx * inner_cy

    ix_origin = ix_outer_origin - ix_inner_origin
    iy_origin = iy_outer_origin - iy_inner_origin
    ixy_origin = -ixy_inner_origin

    return _ClosedFormSectionProperties(
        area_mm2=net_area,
        centroid_x_mm=cx,
        centroid_y_mm=cy,
        ix_nmm4=ix_origin - net_area * cy**2,
        iy_nmm4=iy_origin - net_area * cx**2,
        ixy_nmm4=ixy_origin - net_area * cx * cy,
    )


def _rounded_rectangle_area(width_mm: float, height_mm: float, radius_mm: float) -> float:
    return width_mm * height_mm - (4.0 - math.pi) * radius_mm**2


def _chamfered_rectangle_area(width_mm: float, height_mm: float, chamfer_mm: float) -> float:
    return width_mm * height_mm - 2.0 * chamfer_mm**2


def test_rectangular_hollow_filleted_zero_radii_matches_closed_form_sharp_hollow() -> None:
    geometry = rectangular_hollow_filleted(
        width_mm=1000,
        height_mm=800,
        t_top_mm=120,
        t_bottom_mm=140,
        t_left_mm=110,
        t_right_mm=130,
        r_outer_mm=0,
        r_inner_mm=0,
    )
    summary = summarize_geometry(geometry)
    expected = _rectangular_hollow_closed_form(
        width_mm=1000,
        height_mm=800,
        t_top_mm=120,
        t_bottom_mm=140,
        t_left_mm=110,
        t_right_mm=130,
    )

    assert summary.area_mm2 == pytest.approx(expected.area_mm2, rel=1e-12)
    assert summary.centroid_x_mm == pytest.approx(expected.centroid_x_mm, rel=1e-12)
    assert summary.centroid_y_mm == pytest.approx(expected.centroid_y_mm, rel=1e-12)
    assert summary.ix_nmm4 == pytest.approx(expected.ix_nmm4, rel=1e-12)
    assert summary.iy_nmm4 == pytest.approx(expected.iy_nmm4, rel=1e-12)
    assert summary.ixy_nmm4 == pytest.approx(expected.ixy_nmm4, rel=1e-12)


def test_outer_filleted_inner_chamfered_zero_features_matches_closed_form_sharp_hollow() -> None:
    geometry = rectangular_hollow_outer_filleted_inner_chamfered(
        width_mm=1000,
        height_mm=800,
        t_top_mm=120,
        t_bottom_mm=140,
        t_left_mm=110,
        t_right_mm=130,
        r_outer_mm=0,
        inner_chamfer_mm=0,
    )
    summary = summarize_geometry(geometry)
    expected = _rectangular_hollow_closed_form(
        width_mm=1000,
        height_mm=800,
        t_top_mm=120,
        t_bottom_mm=140,
        t_left_mm=110,
        t_right_mm=130,
    )

    assert summary.area_mm2 == pytest.approx(expected.area_mm2, rel=1e-12)
    assert summary.centroid_x_mm == pytest.approx(expected.centroid_x_mm, rel=1e-12)
    assert summary.centroid_y_mm == pytest.approx(expected.centroid_y_mm, rel=1e-12)
    assert summary.ix_nmm4 == pytest.approx(expected.ix_nmm4, rel=1e-12)
    assert summary.iy_nmm4 == pytest.approx(expected.iy_nmm4, rel=1e-12)
    assert summary.ixy_nmm4 == pytest.approx(expected.ixy_nmm4, rel=1e-12)


def test_rectangular_hollow_filleted_area_matches_independent_rounded_rectangle_area_formula() -> None:
    width = 1000.0
    height = 800.0
    t = 120.0
    ro = 120.0
    ri = 60.0
    geometry = rectangular_hollow_filleted(
        width_mm=width,
        height_mm=height,
        t_top_mm=t,
        t_bottom_mm=t,
        t_left_mm=t,
        t_right_mm=t,
        r_outer_mm=ro,
        r_inner_mm=ri,
        n_fillet=96,
    )
    summary = summarize_geometry(geometry)
    expected_area = _rounded_rectangle_area(width, height, ro) - _rounded_rectangle_area(width - 2.0 * t, height - 2.0 * t, ri)

    assert summary.area_mm2 == pytest.approx(expected_area, rel=2.0e-4)
    assert summary.centroid_x_mm == pytest.approx(0.0, abs=0.01)
    assert summary.centroid_y_mm == pytest.approx(0.0, abs=0.01)
    assert abs(summary.ixy_nmm4 or 0.0) / max(summary.ix_nmm4 or 1.0, summary.iy_nmm4 or 1.0) < 5.0e-6


def test_outer_filleted_inner_chamfered_area_matches_independent_area_formula() -> None:
    width = 1000.0
    height = 800.0
    t = 120.0
    ro = 120.0
    ci = 60.0
    geometry = rectangular_hollow_outer_filleted_inner_chamfered(
        width_mm=width,
        height_mm=height,
        t_top_mm=t,
        t_bottom_mm=t,
        t_left_mm=t,
        t_right_mm=t,
        r_outer_mm=ro,
        inner_chamfer_mm=ci,
        n_fillet=96,
    )
    summary = summarize_geometry(geometry)
    expected_area = _rounded_rectangle_area(width, height, ro) - _chamfered_rectangle_area(width - 2.0 * t, height - 2.0 * t, ci)

    assert summary.area_mm2 == pytest.approx(expected_area, rel=2.0e-4)
    assert summary.centroid_x_mm == pytest.approx(0.0, abs=0.01)
    assert summary.centroid_y_mm == pytest.approx(0.0, abs=0.01)
    assert abs(summary.ixy_nmm4 or 0.0) / max(summary.ix_nmm4 or 1.0, summary.iy_nmm4 or 1.0) < 5.0e-6


def test_asymmetric_hollow_filleted_centroid_moves_toward_thicker_concrete_regions() -> None:
    geometry = rectangular_hollow_filleted(
        width_mm=1000,
        height_mm=800,
        t_top_mm=120,
        t_bottom_mm=160,
        t_left_mm=100,
        t_right_mm=140,
        r_outer_mm=100,
        r_inner_mm=50,
    )
    summary = summarize_geometry(geometry)

    assert summary.centroid_x_mm > 0.0  # thicker right wall
    assert summary.centroid_y_mm < 0.0  # thicker bottom wall in centered coordinates
    assert summary.centroid_y_from_bottom_mm is not None
    assert summary.centroid_y_from_bottom_mm < 400.0


def test_asymmetric_outer_fillet_inner_chamfered_centroid_moves_toward_thicker_concrete_regions() -> None:
    geometry = rectangular_hollow_outer_filleted_inner_chamfered(
        width_mm=1000,
        height_mm=800,
        t_top_mm=120,
        t_bottom_mm=160,
        t_left_mm=100,
        t_right_mm=140,
        r_outer_mm=100,
        inner_chamfer_mm=50,
    )
    summary = summarize_geometry(geometry)

    assert summary.centroid_x_mm > 0.0  # thicker right wall
    assert summary.centroid_y_mm < 0.0  # thicker bottom wall in centered coordinates
    assert summary.centroid_y_from_bottom_mm is not None
    assert summary.centroid_y_from_bottom_mm < 400.0


def test_filleted_hollow_zero_radii_is_equivalent_to_existing_rectangular_hollow_generator() -> None:
    params = dict(width_mm=1000, height_mm=800, t_top_mm=120, t_bottom_mm=140, t_left_mm=110, t_right_mm=130)
    baseline = summarize_geometry(rectangular_hollow(**params))
    filleted_zero = summarize_geometry(rectangular_hollow_filleted(**params, r_outer_mm=0, r_inner_mm=0))
    chamfered_zero = summarize_geometry(rectangular_hollow_outer_filleted_inner_chamfered(**params, r_outer_mm=0, inner_chamfer_mm=0))

    for candidate in (filleted_zero, chamfered_zero):
        assert candidate.area_mm2 == pytest.approx(baseline.area_mm2, rel=1e-12)
        assert candidate.centroid_x_mm == pytest.approx(baseline.centroid_x_mm, rel=1e-12)
        assert candidate.centroid_y_mm == pytest.approx(baseline.centroid_y_mm, rel=1e-12)
        assert candidate.ix_nmm4 == pytest.approx(baseline.ix_nmm4, rel=1e-12)
        assert candidate.iy_nmm4 == pytest.approx(baseline.iy_nmm4, rel=1e-12)
        assert candidate.ixy_nmm4 == pytest.approx(baseline.ixy_nmm4, rel=1e-12)
