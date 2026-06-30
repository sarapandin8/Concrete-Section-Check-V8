"""Built-in metadata-addressable section geometry generators."""

from __future__ import annotations

import math

from shapely.geometry import Polygon
from shapely.validation import explain_validity

from concrete_pmm_pro.core.models import DimensionItem, Point2D, SectionGeometry
from concrete_pmm_pro.geometry.registry import GeometryRegistry


def _point(x: float, y: float) -> Point2D:
    return Point2D(x=float(x), y=float(y))


def _rectangle_points(width_mm: float, height_mm: float) -> list[Point2D]:
    w = width_mm / 2.0
    h = height_mm / 2.0
    return [_point(-w, -h), _point(w, -h), _point(w, h), _point(-w, h)]


def _rectangle_from_bounds(left: float, bottom: float, right: float, top: float) -> list[Point2D]:
    return [_point(left, bottom), _point(right, bottom), _point(right, top), _point(left, top)]


def _circle_points(radius_mm: float, segments: int = 96) -> list[Point2D]:
    return [
        _point(radius_mm * math.cos(2.0 * math.pi * i / segments), radius_mm * math.sin(2.0 * math.pi * i / segments))
        for i in range(segments)
    ]


def _translated_points(points: list[Point2D], dx_mm: float, dy_mm: float) -> list[Point2D]:
    return [_point(point.x + dx_mm, point.y + dy_mm) for point in points]


def _circular_hole_from_left_edge(
    *,
    B_mm: float,
    H_mm: float,
    diameter_mm: float,
    x_from_left_mm: float,
    y_from_bottom_mm: float,
    segments: int = 96,
) -> list[Point2D]:
    _require_positive("void diameter", diameter_mm)
    radius = float(diameter_mm) / 2.0
    if x_from_left_mm - radius < -1e-9 or x_from_left_mm + radius > B_mm + 1e-9:
        raise ValueError("Invalid geometry: circular void must remain within the overall plank width.")
    if y_from_bottom_mm - radius < -1e-9 or y_from_bottom_mm + radius > H_mm + 1e-9:
        raise ValueError("Invalid geometry: circular void must remain within the overall plank depth.")
    center_x = -float(B_mm) / 2.0 + float(x_from_left_mm)
    center_y = -float(H_mm) / 2.0 + float(y_from_bottom_mm)
    return _translated_points(_circle_points(radius, segments=segments), center_x, center_y)


def _ensure_valid_polygon_with_holes(outer: list[Point2D], holes: list[list[Point2D]], name: str) -> None:
    polygon = Polygon([point.as_tuple() for point in outer], [[point.as_tuple() for point in hole] for hole in holes])
    if not polygon.is_valid:
        raise ValueError(f"Invalid geometry: {name} polygon is invalid ({explain_validity(polygon)}).")
    if polygon.area <= 0:
        raise ValueError(f"Invalid geometry: {name} polygon area must be positive.")


def _rounded_rectangle_from_bounds(
    left: float,
    bottom: float,
    right: float,
    top: float,
    radius_mm: float,
    segments_per_corner: int = 12,
) -> list[Point2D]:
    width = right - left
    height = top - bottom
    radius = float(radius_mm)
    if radius <= 0:
        return _rectangle_from_bounds(left, bottom, right, top)
    if radius * 2.0 > min(width, height):
        raise ValueError("Invalid geometry: fillet radius is too large for the selected rectangle dimensions.")

    n = max(1, int(segments_per_corner))
    corners = [
        ((right - radius, bottom + radius), -math.pi / 2, 0.0),
        ((right - radius, top - radius), 0.0, math.pi / 2),
        ((left + radius, top - radius), math.pi / 2, math.pi),
        ((left + radius, bottom + radius), math.pi, 3 * math.pi / 2),
    ]
    points: list[Point2D] = []
    for (cx, cy), start_angle, end_angle in corners:
        for index in range(n + 1):
            if points and index == 0:
                continue
            angle = start_angle + (end_angle - start_angle) * index / n
            points.append(_point(cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points




def _chamfered_rectangle_from_bounds(
    left: float,
    bottom: float,
    right: float,
    top: float,
    chamfer_mm: float,
) -> list[Point2D]:
    """Return a rectangular ring with straight chamfered corners.

    The points are ordered counter-clockwise around the rectangle.  This is
    used for Box Beam voids where the inside corners are detailed as chamfers,
    not circular fillets.
    """
    width = right - left
    height = top - bottom
    chamfer = float(chamfer_mm)
    if chamfer <= 0.0:
        return _rectangle_from_bounds(left, bottom, right, top)
    if chamfer * 2.0 > min(width, height):
        raise ValueError("Invalid geometry: inner chamfer is too large for the selected void dimensions.")
    return [
        _point(left + chamfer, bottom),
        _point(right - chamfer, bottom),
        _point(right, bottom + chamfer),
        _point(right, top - chamfer),
        _point(right - chamfer, top),
        _point(left + chamfer, top),
        _point(left, top - chamfer),
        _point(left, bottom + chamfer),
    ]

def _rounded_rectangle_points(width_mm: float, height_mm: float, radius_mm: float, segments_per_corner: int = 12) -> list[Point2D]:
    return _rounded_rectangle_from_bounds(
        -width_mm / 2.0,
        -height_mm / 2.0,
        width_mm / 2.0,
        height_mm / 2.0,
        radius_mm,
        segments_per_corner,
    )

def _precast_box_beam_outer_points(
    width_mm: float,
    height_mm: float,
    *,
    side_recess_mm: float = 45.0,
    exterior_side: str | None = None,
) -> list[Point2D]:
    """Return a drawing-based precast box beam outer profile.

    The box-beam sketches used for this project show a full bottom width and
    a top edge inset from the side by about 45 mm.  The side face then breaks
    outward with a short straight chamfer before continuing down to the bottom
    corner.  This is intentionally *not* a filleted/rounded box section.

    ``exterior_side='right'`` keeps the right outside face straight for an
    exterior box beam while the opposite side keeps the interior-style break.
    Coordinates are returned counter-clockwise starting at the bottom-left
    corner.
    """

    w = float(width_mm) / 2.0
    d = float(height_mm) / 2.0
    inset = max(0.0, min(float(side_recess_mm), width_mm * 0.12, height_mm * 0.25))

    # Match the user drawing proportion: the break sits in the upper half of
    # the section, below the top flange but well above the prestressing rows.
    y_break_top = d - min(max(height_mm * 0.24, 150.0), height_mm * 0.36)
    y_break_bottom = y_break_top - min(max(height_mm * 0.07, 45.0), height_mm * 0.12)
    y_break_bottom = max(y_break_bottom, -d + height_mm * 0.35)

    exterior = (exterior_side or "").strip().casefold()

    points: list[Point2D] = [_point(-w, -d), _point(w, -d)]

    # Right side: either straight exterior face or drawing-style interior break.
    if exterior == "right" or inset <= 0.0:
        points.append(_point(w, d))
    else:
        points.extend(
            [
                _point(w, y_break_bottom),
                _point(w - inset, y_break_top),
                _point(w - inset, d),
            ]
        )

    # Top edge.  Exterior right keeps the full outside face; interior uses
    # inset top corners both sides.
    if exterior == "right":
        points.append(_point(-w + inset, d))
    else:
        points.append(_point(-w + inset, d))

    # Left side: either straight exterior face or drawing-style interior break.
    if exterior == "left" or inset <= 0.0:
        points.append(_point(-w, -d))
    else:
        points.extend(
            [
                _point(-w + inset, y_break_top),
                _point(-w, y_break_bottom),
                _point(-w, -d),
            ]
        )

    # Drop duplicated closing point; SectionGeometry polygons are implicitly closed.
    if len(points) > 1 and points[-1].x == points[0].x and points[-1].y == points[0].y:
        points.pop()
    return points


def _precast_box_beam_interior_outer_points(
    width_mm: float,
    height_mm: float,
    *,
    h7_mm: float,
    h8_mm: float,
    b4_mm: float,
    top_edge_offset_mm: float = 45.0,
) -> list[Point2D]:
    """Return the requested interior precast box beam outer profile.

    Geometry basis from the user's drawing for the *interior* box beam only:
    - full bottom width B
    - top edge inset 45 mm on each side
    - point 1 sits at the top of the lower outside vertical face at elevation h7
    - point 2 is offset inward by b4 and upward by h8 from point 1
    - the boundary segment from point 1 to point 2 is a straight diagonal
    - the upper side then continues as a straight diagonal from point 2 to the top corner B
    The section remains left-right symmetric about the center line.
    """

    _require_positive("width_mm", width_mm)
    _require_positive("height_mm", height_mm)
    _require_positive("h7_mm", h7_mm)
    _require_non_negative("h8_mm", h8_mm)
    _require_non_negative("b4_mm", b4_mm)
    _require_non_negative("top_edge_offset_mm", top_edge_offset_mm)

    w = float(width_mm) / 2.0
    d = float(height_mm) / 2.0
    inset = float(top_edge_offset_mm)
    b4 = float(b4_mm)
    h8 = float(h8_mm)
    y_break_lower = -d + float(h7_mm)
    y_break_middle = y_break_lower + h8
    y_break_upper = d

    if inset >= w:
        raise ValueError("Invalid geometry: top edge offset must be less than B/2.")
    if b4 >= w:
        raise ValueError("Invalid geometry: b4 must be less than B/2.")
    if y_break_lower <= -d or y_break_lower >= y_break_upper:
        raise ValueError("Invalid geometry: h7 must place point 1 between the bottom edge and the top edge.")
    if y_break_middle >= y_break_upper:
        raise ValueError("Invalid geometry: h7 + h8 must remain below the top edge.")

    points = [
        _point(-w, -d),
        _point(w, -d),
        _point(w, y_break_lower),
        _point(w - b4, y_break_middle),
        _point(w - inset, y_break_upper),
        _point(-w + inset, y_break_upper),
        _point(-w + b4, y_break_middle),
        _point(-w, y_break_lower),
    ]
    _ensure_valid_simple_polygon(points, "Precast Box Beam – Interior outer polygon")
    return points


def _precast_box_beam_interior_void_points(
    width_mm: float,
    height_mm: float,
    *,
    h1_mm: float | None = None,
    h3_mm: float,
    h4_mm: float,
    h5_mm: float,
    b2_mm: float,
    b3_mm: float,
) -> list[Point2D]:
    """Return the chamfered interior-box-beam void using the user drawing variables.

    Vertical stack: bottom cover h3, lower chamfer h4, side wall h5,
    upper chamfer h4, and top cover h1. Because H is also an input, h1 is
    checked against H - (h3 + 2*h4 + h5) instead of silently distorting the void.

    Horizontal stack about the center line: top/bottom flat width b3, with
    chamfer projection b2 on each side.
    """

    for name, value in {
        "h1_mm": 180.0 if h1_mm is None else h1_mm,
        "h3_mm": h3_mm,
        "h4_mm": h4_mm,
        "h5_mm": h5_mm,
        "b2_mm": b2_mm,
        "b3_mm": b3_mm,
    }.items():
        _require_positive(name, float(value))

    top_cover = float(180.0 if h1_mm is None else h1_mm)
    derived_top_cover = float(height_mm) - (float(h3_mm) + 2.0 * float(h4_mm) + float(h5_mm))
    if derived_top_cover <= 0.0:
        raise ValueError("Invalid geometry: H must be greater than h3 + 2*h4 + h5 for the interior box-beam void.")
    if abs(top_cover - derived_top_cover) > 1e-6:
        raise ValueError("Invalid geometry: h1 is inconsistent. h1 must equal H - h3 - 2*h4 - h5 for the interior box-beam void.")

    d = float(height_mm) / 2.0
    half_b3 = float(b3_mm) / 2.0
    chamfer_run = float(b2_mm)
    y0 = -d + float(h3_mm)
    y1 = y0 + float(h4_mm)
    y2 = y1 + float(h5_mm)
    y3 = y2 + float(h4_mm)
    x0 = half_b3
    x1 = half_b3 + chamfer_run
    if x1 * 2.0 >= float(width_mm):
        raise ValueError("Invalid geometry: b3 + 2*b2 must be less than B for the interior box-beam void.")

    points = [
        _point(-x0, y0),
        _point(x0, y0),
        _point(x1, y1),
        _point(x1, y2),
        _point(x0, y3),
        _point(-x0, y3),
        _point(-x1, y2),
        _point(-x1, y1),
    ]
    _ensure_valid_simple_polygon(points, "Precast Box Beam – Interior void polygon")
    return points


def _precast_box_beam_exterior_void_points(
    width_mm: float,
    height_mm: float,
    *,
    h1_mm: float | None = None,
    h3_mm: float,
    h4_mm: float,
    h5_mm: float,
    b2_mm: float,
    b3_mm: float,
    right_flat_clear_to_edge_mm: float = 280.0,
) -> list[Point2D]:
    """Return the chamfered exterior-box-beam void using the user drawing variables.

    The left side follows the interior-box-beam rules, while the void is shifted
    toward the straight exterior face on the right. The user rule is that the
    right end of b3 is b2 + 180 mm from the rightmost outside edge.
    """

    for name, value in {
        "h1_mm": 180.0 if h1_mm is None else h1_mm,
        "h3_mm": h3_mm,
        "h4_mm": h4_mm,
        "h5_mm": h5_mm,
        "b2_mm": b2_mm,
        "b3_mm": b3_mm,
        "right_flat_clear_to_edge_mm": right_flat_clear_to_edge_mm,
    }.items():
        _require_positive(name, float(value))

    top_cover = float(180.0 if h1_mm is None else h1_mm)
    derived_top_cover = float(height_mm) - (float(h3_mm) + 2.0 * float(h4_mm) + float(h5_mm))
    if derived_top_cover <= 0.0:
        raise ValueError("Invalid geometry: H must be greater than h3 + 2*h4 + h5 for the exterior box-beam void.")
    if abs(top_cover - derived_top_cover) > 1e-6:
        raise ValueError("Invalid geometry: h1 is inconsistent. h1 must equal H - h3 - 2*h4 - h5 for the exterior box-beam void.")

    d = float(height_mm) / 2.0
    w = float(width_mm) / 2.0
    y0 = -d + float(h3_mm)
    y1 = y0 + float(h4_mm)
    y2 = y1 + float(h5_mm)
    y3 = y2 + float(h4_mm)

    right_flat = w - float(right_flat_clear_to_edge_mm)
    left_flat = right_flat - float(b3_mm)
    left_outer = left_flat - float(b2_mm)
    right_outer = right_flat + float(b2_mm)

    if right_flat <= left_flat:
        raise ValueError("Invalid geometry: b3 must be positive and produce a valid flat width.")
    if left_outer <= -w or right_outer >= w:
        raise ValueError("Invalid geometry: exterior void must remain inside the outer concrete boundary.")

    points = [
        _point(left_flat, y0),
        _point(right_flat, y0),
        _point(right_outer, y1),
        _point(right_outer, y2),
        _point(right_flat, y3),
        _point(left_flat, y3),
        _point(left_outer, y2),
        _point(left_outer, y1),
    ]
    _ensure_valid_simple_polygon(points, "Precast Box Beam – Exterior void polygon")
    return points


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"Invalid geometry: {name} must be greater than zero.")


def _require_non_negative(name: str, value: float) -> None:
    if value < 0:
        raise ValueError(f"Invalid geometry: {name} must be zero or greater.")


def _resolve_wall_thicknesses(
    *,
    t_top_mm: float | None = None,
    t_bottom_mm: float | None = None,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    wall_thickness_mm: float | None = None,
) -> tuple[float, float, float, float]:
    if wall_thickness_mm is not None:
        t_top_mm = wall_thickness_mm if t_top_mm is None else t_top_mm
        t_bottom_mm = wall_thickness_mm if t_bottom_mm is None else t_bottom_mm
        t_left_mm = wall_thickness_mm if t_left_mm is None else t_left_mm
        t_right_mm = wall_thickness_mm if t_right_mm is None else t_right_mm

    missing = [
        name
        for name, value in {
            "t_top_mm": t_top_mm,
            "t_bottom_mm": t_bottom_mm,
            "t_left_mm": t_left_mm,
            "t_right_mm": t_right_mm,
        }.items()
        if value is None
    ]
    if missing:
        raise ValueError(f"Invalid geometry: missing wall thickness parameter(s): {', '.join(missing)}.")

    values = (float(t_top_mm), float(t_bottom_mm), float(t_left_mm), float(t_right_mm))
    for name, value in zip(("t_top_mm", "t_bottom_mm", "t_left_mm", "t_right_mm"), values):
        _require_positive(name, value)
    return values


def _inner_rect_bounds(
    *,
    width_mm: float,
    height_mm: float,
    t_top_mm: float,
    t_bottom_mm: float,
    t_left_mm: float,
    t_right_mm: float,
) -> tuple[float, float, float, float]:
    _require_positive("width_mm", width_mm)
    _require_positive("height_mm", height_mm)
    inner_width = width_mm - t_left_mm - t_right_mm
    inner_height = height_mm - t_top_mm - t_bottom_mm
    if inner_width <= 0:
        raise ValueError("Invalid geometry: t_left + t_right must be less than B.")
    if inner_height <= 0:
        raise ValueError("Invalid geometry: t_top + t_bottom must be less than H.")
    return (
        -width_mm / 2.0 + t_left_mm,
        -height_mm / 2.0 + t_bottom_mm,
        width_mm / 2.0 - t_right_mm,
        height_mm / 2.0 - t_top_mm,
    )


def _ensure_valid_simple_polygon(points: list[Point2D], name: str) -> None:
    polygon = Polygon([point.as_tuple() for point in points])
    if not polygon.is_valid:
        raise ValueError(f"Invalid geometry: {name} polygon is self-intersecting ({explain_validity(polygon)}).")
    if polygon.area <= 0:
        raise ValueError(f"Invalid geometry: {name} polygon area must be positive.")


def rectangle(width_mm: float, height_mm: float, name: str = "Rectangle") -> SectionGeometry:
    _require_positive("B", width_mm)
    _require_positive("H", height_mm)
    return SectionGeometry(name=name, outer_polygon=_rectangle_points(width_mm, height_mm), holes=[], metadata={"preset": "rectangle"})


def rectangular_chamfered(
    width_mm: float,
    height_mm: float,
    chamfer_mm: float | None = None,
    chamfer_x_mm: float | None = None,
    chamfer_y_mm: float | None = None,
    name: str = "Rectangular chamfered",
) -> SectionGeometry:
    _require_positive("B", width_mm)
    _require_positive("H", height_mm)
    legacy_chamfer = 0.0 if chamfer_mm is None else float(chamfer_mm)
    cx_raw = legacy_chamfer if chamfer_x_mm is None else float(chamfer_x_mm)
    cy_raw = legacy_chamfer if chamfer_y_mm is None else float(chamfer_y_mm)
    _require_non_negative("chamfer_x_mm", cx_raw)
    _require_non_negative("chamfer_y_mm", cy_raw)
    if cx_raw * 2.0 >= width_mm:
        raise ValueError("Invalid geometry: chamfer_x_mm must be smaller than B/2.")
    if cy_raw * 2.0 >= height_mm:
        raise ValueError("Invalid geometry: chamfer_y_mm must be smaller than H/2.")
    w = width_mm / 2.0
    h = height_mm / 2.0
    cx = cx_raw
    cy = cy_raw
    points = [
        _point(-w + cx, -h),
        _point(w - cx, -h),
        _point(w, -h + cy),
        _point(w, h - cy),
        _point(w - cx, h),
        _point(-w + cx, h),
        _point(-w, h - cy),
        _point(-w, -h + cy),
    ]
    return SectionGeometry(
        name=name,
        outer_polygon=points,
        holes=[],
        metadata={
            "preset": "rectangular_chamfered",
            "chamfer_x_mm": cx_raw,
            "chamfer_y_mm": cy_raw,
            "legacy_chamfer_mm": chamfer_mm,
        },
    )


def rectangular_filleted(
    width_mm: float,
    height_mm: float,
    corner_radius_mm: float,
    n_fillet: int = 16,
    name: str = "Rectangular filleted",
) -> SectionGeometry:
    _require_positive("B", width_mm)
    _require_positive("H", height_mm)
    _require_non_negative("corner_radius_mm", corner_radius_mm)
    if corner_radius_mm * 2.0 > min(width_mm, height_mm):
        raise ValueError("Invalid geometry: corner_radius_mm must be smaller than or equal to min(B, H)/2.")
    if n_fillet < 4:
        raise ValueError("Invalid geometry: n_fillet must be at least 4.")
    points = _rounded_rectangle_points(width_mm, height_mm, corner_radius_mm, n_fillet)
    _ensure_valid_simple_polygon(points, name)
    return SectionGeometry(
        name=name,
        outer_polygon=points,
        holes=[],
        metadata={
            "preset": "rectangular_filleted",
            "corner_radius_mm": float(corner_radius_mm),
            "n_fillet": int(n_fillet),
        },
    )


def circle(diameter_mm: float, segments: int = 128, name: str = "Circle") -> SectionGeometry:
    _require_positive("D", diameter_mm)
    return SectionGeometry(name=name, outer_polygon=_circle_points(diameter_mm / 2.0, segments), holes=[], metadata={"preset": "circle"})


def circular_hollow(outer_diameter_mm: float, inner_diameter_mm: float, segments: int = 128, name: str = "Circular hollow") -> SectionGeometry:
    _require_positive("D_outer", outer_diameter_mm)
    _require_positive("D_inner", inner_diameter_mm)
    if inner_diameter_mm >= outer_diameter_mm:
        raise ValueError("Invalid geometry: D_inner must be smaller than D_outer.")
    return SectionGeometry(
        name=name,
        outer_polygon=_circle_points(outer_diameter_mm / 2.0, segments),
        holes=[list(reversed(_circle_points(inner_diameter_mm / 2.0, segments)))],
        metadata={"preset": "circular_hollow"},
    )


def rectangular_hollow(
    width_mm: float,
    height_mm: float,
    t_top_mm: float | None = None,
    t_bottom_mm: float | None = None,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    wall_thickness_mm: float | None = None,
    name: str = "Rectangular hollow",
) -> SectionGeometry:
    top, bottom, left, right = _resolve_wall_thicknesses(
        t_top_mm=t_top_mm,
        t_bottom_mm=t_bottom_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        wall_thickness_mm=wall_thickness_mm,
    )
    inner_bounds = _inner_rect_bounds(
        width_mm=width_mm,
        height_mm=height_mm,
        t_top_mm=top,
        t_bottom_mm=bottom,
        t_left_mm=left,
        t_right_mm=right,
    )
    return SectionGeometry(
        name=name,
        outer_polygon=_rectangle_points(width_mm, height_mm),
        holes=[list(reversed(_rectangle_from_bounds(*inner_bounds)))],
        metadata={"preset": "rectangular_hollow", "wall_thicknesses_mm": {"top": top, "bottom": bottom, "left": left, "right": right}},
    )


def rectangular_hollow_filleted(
    width_mm: float,
    height_mm: float,
    t_top_mm: float | None = None,
    t_bottom_mm: float | None = None,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    r_outer_mm: float = 0.0,
    r_inner_mm: float = 0.0,
    n_fillet: int = 16,
    wall_thickness_mm: float | None = None,
    name: str = "Rectangular hollow filleted",
) -> SectionGeometry:
    top, bottom, left, right = _resolve_wall_thicknesses(
        t_top_mm=t_top_mm,
        t_bottom_mm=t_bottom_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        wall_thickness_mm=wall_thickness_mm,
    )
    outer_radius = float(r_outer_mm)
    inner_radius = float(r_inner_mm)
    _require_non_negative("r_outer_mm", outer_radius)
    _require_non_negative("r_inner_mm", inner_radius)
    if n_fillet < 4:
        raise ValueError("Invalid geometry: n_fillet must be at least 4.")
    if outer_radius * 2.0 > min(width_mm, height_mm):
        raise ValueError("Invalid geometry: r_outer_mm is too large for the selected outer dimensions.")
    inner_bounds = _inner_rect_bounds(
        width_mm=width_mm,
        height_mm=height_mm,
        t_top_mm=top,
        t_bottom_mm=bottom,
        t_left_mm=left,
        t_right_mm=right,
    )
    inner_width = inner_bounds[2] - inner_bounds[0]
    inner_height = inner_bounds[3] - inner_bounds[1]
    if inner_radius * 2.0 > min(inner_width, inner_height):
        raise ValueError("Invalid geometry: r_inner_mm is too large for the inner void dimensions.")
    outer_polygon = _rounded_rectangle_points(width_mm, height_mm, outer_radius, n_fillet)
    inner_hole = list(reversed(_rounded_rectangle_from_bounds(*inner_bounds, inner_radius, segments_per_corner=n_fillet)))
    _ensure_valid_polygon_with_holes(outer_polygon, [inner_hole], name)
    return SectionGeometry(
        name=name,
        outer_polygon=outer_polygon,
        holes=[inner_hole],
        metadata={
            "preset": "rectangular_hollow_filleted",
            "wall_thicknesses_mm": {"top": top, "bottom": bottom, "left": left, "right": right},
            "r_outer_mm": outer_radius,
            "r_inner_mm": inner_radius,
            "n_fillet": int(n_fillet),
        },
    )


def rectangular_hollow_outer_filleted_inner_chamfered(
    width_mm: float,
    height_mm: float,
    t_top_mm: float | None = None,
    t_bottom_mm: float | None = None,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    r_outer_mm: float = 0.0,
    inner_chamfer_mm: float = 0.0,
    n_fillet: int = 16,
    wall_thickness_mm: float | None = None,
    name: str = "Rectangular hollow outer filleted inner chamfered",
) -> SectionGeometry:
    top, bottom, left, right = _resolve_wall_thicknesses(
        t_top_mm=t_top_mm,
        t_bottom_mm=t_bottom_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        wall_thickness_mm=wall_thickness_mm,
    )
    outer_radius = float(r_outer_mm)
    inner_chamfer = float(inner_chamfer_mm)
    _require_non_negative("r_outer_mm", outer_radius)
    _require_non_negative("inner_chamfer_mm", inner_chamfer)
    if n_fillet < 4:
        raise ValueError("Invalid geometry: n_fillet must be at least 4.")
    if outer_radius * 2.0 > min(width_mm, height_mm):
        raise ValueError("Invalid geometry: r_outer_mm is too large for the selected outer dimensions.")
    inner_bounds = _inner_rect_bounds(
        width_mm=width_mm,
        height_mm=height_mm,
        t_top_mm=top,
        t_bottom_mm=bottom,
        t_left_mm=left,
        t_right_mm=right,
    )
    inner_width = inner_bounds[2] - inner_bounds[0]
    inner_height = inner_bounds[3] - inner_bounds[1]
    if inner_chamfer * 2.0 > min(inner_width, inner_height):
        raise ValueError("Invalid geometry: inner_chamfer_mm is too large for the inner void dimensions.")
    outer_polygon = _rounded_rectangle_points(width_mm, height_mm, outer_radius, n_fillet)
    inner_hole = list(reversed(_chamfered_rectangle_from_bounds(*inner_bounds, inner_chamfer)))
    _ensure_valid_polygon_with_holes(outer_polygon, [inner_hole], name)
    return SectionGeometry(
        name=name,
        outer_polygon=outer_polygon,
        holes=[inner_hole],
        metadata={
            "preset": "rectangular_hollow_outer_filleted_inner_chamfered",
            "wall_thicknesses_mm": {"top": top, "bottom": bottom, "left": left, "right": right},
            "r_outer_mm": outer_radius,
            "inner_chamfer_mm": inner_chamfer,
            "n_fillet": int(n_fillet),
        },
    )


def box_section_fillet(
    width_mm: float,
    height_mm: float,
    t_top_mm: float | None = None,
    t_bottom_mm: float | None = None,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    r_inner_mm: float | None = None,
    r_outer_mm: float = 0.0,
    n_fillet: int = 12,
    wall_thickness_mm: float | None = None,
    fillet_radius_mm: float | None = None,
    h1_mm: float | None = None,
    h3_mm: float | None = None,
    h4_mm: float | None = None,
    h5_mm: float | None = None,
    h6_mm: float | None = None,
    h7_mm: float | None = None,
    h8_mm: float | None = None,
    b2_mm: float | None = None,
    b3_mm: float | None = None,
    b4_mm: float | None = None,
    b2_start_from_left_mm: float | None = None,
    name: str = "Precast Box Beam – Interior",
) -> SectionGeometry:
    # New drawing-variable branch for the interior precast box beam. Legacy
    # wall-thickness inputs are intentionally preserved for project-file
    # compatibility when the new parameters are absent.
    use_drawing_parameters = any(value is not None for value in (h1_mm, h3_mm, h4_mm, h5_mm, h6_mm, h7_mm, h8_mm, b2_mm, b3_mm, b4_mm, b2_start_from_left_mm))
    if use_drawing_parameters:
        h1 = float(180.0 if h1_mm is None else h1_mm)
        h3 = float(160.0 if h3_mm is None else h3_mm)
        h4 = float(80.0 if h4_mm is None else h4_mm)
        h5 = float(200.0 if h5_mm is None else h5_mm)
        h6 = float(300.0 if h6_mm is None else h6_mm)
        h7 = float(400.0 if h7_mm is None else h7_mm)
        h8 = float(70.0 if h8_mm is None else h8_mm)
        b2 = float(100.0 if b2_mm is None else b2_mm)
        b3 = float(290.0 if b3_mm is None else b3_mm)
        b4 = float(70.0 if b4_mm is None else b4_mm)
        outer_radius = float(r_outer_mm)
        if n_fillet < 4:
            raise ValueError("Invalid geometry: n_fillet must be at least 4.")
        _require_non_negative("r_outer_mm", outer_radius)
        if outer_radius > 0.0:
            raise ValueError("Invalid geometry: r_outer_mm must remain 0 for the drawing-based interior box beam.")

        # Ruthless check: h6 and h7 describe the same outer break from opposite
        # reference edges in the drawing. Allow a small numerical tolerance but
        # reject inconsistent free-form inputs instead of silently distorting
        # the section.
        if abs((float(height_mm) - h7) - h6) > 1e-6:
            raise ValueError("Invalid geometry: h6 and h7 are inconsistent. For the interior box beam, h6 must equal H - h7.")

        derived_b2_start = (float(width_mm) - (2.0 * b2 + b3)) / 2.0
        if derived_b2_start <= 0.0:
            raise ValueError("Invalid geometry: B must be greater than 2*b2 + b3 for the centered interior void.")
        if b2_start_from_left_mm is not None and abs(derived_b2_start - float(b2_start_from_left_mm)) > 1e-6:
            raise ValueError(
                "Invalid geometry: b2_start_from_left must equal (B - (2*b2 + b3)) / 2 for the centered interior void."
            )

        outer_polygon = _precast_box_beam_interior_outer_points(width_mm, height_mm, h7_mm=h7, h8_mm=h8, b4_mm=b4)
        hole = _precast_box_beam_interior_void_points(width_mm, height_mm, h1_mm=h1, h3_mm=h3, h4_mm=h4, h5_mm=h5, b2_mm=b2, b3_mm=b3)
        top_cover = h1
        left_inner_x = -(b3 / 2.0 + b2)
        right_inner_x = (b3 / 2.0 + b2)
        bottom_y = -float(height_mm) / 2.0 + h3
        top_y = -float(height_mm) / 2.0 + h3 + 2.0 * h4 + h5
        return SectionGeometry(
            name=name,
            outer_polygon=outer_polygon,
            holes=[list(reversed(hole))],
            metadata={
                "preset": "box_section_fillet",
                "geometry_branch": "drawing_variable_interior_box_beam",
                "drawing_parameters_mm": {
                    "B": float(width_mm),
                    "H": float(height_mm),
                    "h1": h1,
                    "h3": h3,
                    "h4": h4,
                    "h5": h5,
                    "h6": h6,
                    "h7": h7,
                    "h8": h8,
                    "b2": b2,
                    "b3": b3,
                    "b4": b4,
                    "b2_start_from_left": derived_b2_start,
                    "top_cover": top_cover,
                    "top_edge_offset": 45.0,
                    "top_side_drop": 70.0,
                    "side_slope_connects_to_top_corner": True,
                    "point_1_left": {"x": -float(width_mm) / 2.0, "y": -float(height_mm) / 2.0 + h7},
                    "point_2_left": {"x": -(float(width_mm) / 2.0 - b4), "y": -float(height_mm) / 2.0 + h7 + h8},
                    "point_B_left": {"x": -(float(width_mm) / 2.0 - 45.0), "y": float(height_mm) / 2.0},
                    "point_1_right": {"x": float(width_mm) / 2.0, "y": -float(height_mm) / 2.0 + h7},
                    "point_2_right": {"x": float(width_mm) / 2.0 - b4, "y": -float(height_mm) / 2.0 + h7 + h8},
                    "point_B_right": {"x": float(width_mm) / 2.0 - 45.0, "y": float(height_mm) / 2.0},
                },
                "wall_thicknesses_mm": {
                    "top": top_cover,
                    "bottom": h3,
                    "left": float(width_mm) / 2.0 + left_inner_x,
                    "right": float(width_mm) / 2.0 - right_inner_x,
                },
                "inner_chamfer_mm": b2,
                "r_inner_mm": b2,
                "r_outer_mm": outer_radius,
                "n_fillet": n_fillet,
                "inner_bounds_mm": {
                    "left": left_inner_x,
                    "right": right_inner_x,
                    "bottom": bottom_y,
                    "top": top_y,
                },
            },
        )

    top, bottom, left, right = _resolve_wall_thicknesses(
        t_top_mm=t_top_mm,
        t_bottom_mm=t_bottom_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        wall_thickness_mm=wall_thickness_mm,
    )
    # Historically this preset used a circular inner fillet parameter.  For the
    # Precast Box Beam workflow the inside void corners are now modeled as
    # straight chamfers.  Keep the legacy argument name for project-file
    # compatibility, but interpret it as the inner chamfer size.
    inner_chamfer = float(fillet_radius_mm if r_inner_mm is None and fillet_radius_mm is not None else r_inner_mm or 0.0)
    outer_radius = float(r_outer_mm)
    _require_non_negative("inner_chamfer_mm", inner_chamfer)
    _require_non_negative("r_outer_mm", outer_radius)
    if n_fillet < 4:
        raise ValueError("Invalid geometry: n_fillet must be at least 4.")
    inner_bounds = _inner_rect_bounds(
        width_mm=width_mm,
        height_mm=height_mm,
        t_top_mm=top,
        t_bottom_mm=bottom,
        t_left_mm=left,
        t_right_mm=right,
    )
    inner_width = inner_bounds[2] - inner_bounds[0]
    inner_height = inner_bounds[3] - inner_bounds[1]
    if outer_radius * 2.0 > min(width_mm, height_mm):
        raise ValueError("Invalid geometry: outer fillet radius is too large for the section dimensions.")
    if inner_chamfer * 2.0 > min(inner_width, inner_height):
        raise ValueError("Invalid geometry: inner chamfer is too large for inner void.")

    return SectionGeometry(
        name=name,
        outer_polygon=(
            _rounded_rectangle_points(width_mm, height_mm, outer_radius, n_fillet)
            if outer_radius > 0.0
            else _precast_box_beam_outer_points(width_mm, height_mm)
        ),
        holes=[list(reversed(_chamfered_rectangle_from_bounds(*inner_bounds, inner_chamfer)))],
        metadata={
            "preset": "box_section_fillet",
            "wall_thicknesses_mm": {"top": top, "bottom": bottom, "left": left, "right": right},
            "inner_chamfer_mm": inner_chamfer,
            # Legacy metadata alias retained so older project snapshots that look
            # for r_inner_mm still have a meaningful value.
            "r_inner_mm": inner_chamfer,
            "r_outer_mm": outer_radius,
            "n_fillet": n_fillet,
        },
    )


def precast_box_beam_exterior(
    width_mm: float,
    height_mm: float,
    t_top_mm: float | None = None,
    t_bottom_mm: float | None = None,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    r_inner_mm: float | None = None,
    r_outer_mm: float = 0.0,
    n_fillet: int = 12,
    wall_thickness_mm: float | None = None,
    fillet_radius_mm: float | None = None,
    h1_mm: float | None = None,
    h3_mm: float | None = None,
    h4_mm: float | None = None,
    h5_mm: float | None = None,
    h6_mm: float | None = None,
    h7_mm: float | None = None,
    h8_mm: float | None = None,
    b2_mm: float | None = None,
    b3_mm: float | None = None,
    b4_mm: float | None = None,
    name: str = "Precast Box Beam – Exterior",
) -> SectionGeometry:
    """Exterior precast box beam with drawing-based left break and straight right face."""

    use_drawing_parameters = any(value is not None for value in (h1_mm, h3_mm, h4_mm, h5_mm, h6_mm, h7_mm, h8_mm, b2_mm, b3_mm, b4_mm))
    if use_drawing_parameters:
        h1 = float(180.0 if h1_mm is None else h1_mm)
        h3 = float(160.0 if h3_mm is None else h3_mm)
        h4 = float(80.0 if h4_mm is None else h4_mm)
        h5 = float(200.0 if h5_mm is None else h5_mm)
        h6 = float(300.0 if h6_mm is None else h6_mm)
        h7 = float(400.0 if h7_mm is None else h7_mm)
        h8 = float(70.0 if h8_mm is None else h8_mm)
        b2 = float(100.0 if b2_mm is None else b2_mm)
        b3 = float(360.0 if b3_mm is None else b3_mm)
        b4 = float(70.0 if b4_mm is None else b4_mm)
        outer_radius = float(r_outer_mm)
        if n_fillet < 4:
            raise ValueError("Invalid geometry: n_fillet must be at least 4.")
        _require_non_negative("r_outer_mm", outer_radius)
        if outer_radius > 0.0:
            raise ValueError("Invalid geometry: r_outer_mm must remain 0 for the drawing-based exterior box beam.")
        if abs((float(height_mm) - h7) - h6) > 1e-6:
            raise ValueError("Invalid geometry: h6 and h7 are inconsistent. For the exterior box beam, h6 must equal H - h7.")

        # Outer polygon: left side like interior, right side straight with no notch.
        w = float(width_mm) / 2.0
        d = float(height_mm) / 2.0
        inset = 45.0
        y1 = -d + h7
        y2 = y1 + h8
        if y2 >= d:
            raise ValueError("Invalid geometry: h7 + h8 must remain below the top edge for the exterior box beam.")
        outer_polygon = [
            _point(-w, -d),
            _point(w, -d),
            _point(w, d),
            _point(-w + inset, d),
            _point(-w + b4, y2),
            _point(-w, y1),
        ]
        _ensure_valid_simple_polygon(outer_polygon, "Precast Box Beam – Exterior outer polygon")

        right_clear_from_b3_to_edge = b2 + 180.0
        hole = _precast_box_beam_exterior_void_points(
            width_mm,
            height_mm,
            h1_mm=h1,
            h3_mm=h3,
            h4_mm=h4,
            h5_mm=h5,
            b2_mm=b2,
            b3_mm=b3,
            right_flat_clear_to_edge_mm=right_clear_from_b3_to_edge,
        )
        top_cover = h1
        right_flat = float(width_mm) / 2.0 - right_clear_from_b3_to_edge
        left_flat = right_flat - b3
        left_outer = left_flat - b2
        right_outer = right_flat + b2
        bottom_y = -float(height_mm) / 2.0 + h3
        top_y = -float(height_mm) / 2.0 + h3 + 2.0 * h4 + h5
        return SectionGeometry(
            name=name,
            outer_polygon=outer_polygon,
            holes=[list(reversed(hole))],
            metadata={
                "preset": "precast_box_beam_exterior",
                "geometry_branch": "drawing_variable_exterior_box_beam",
                "exterior_side": "right",
                "drawing_parameters_mm": {
                    "B": float(width_mm),
                    "H": float(height_mm),
                    "h1": h1,
                    "h3": h3,
                    "h4": h4,
                    "h5": h5,
                    "h6": h6,
                    "h7": h7,
                    "h8": h8,
                    "b2": b2,
                    "b3": b3,
                    "b4": b4,
                    "right_end_b3_to_right_edge": right_clear_from_b3_to_edge,
                    "right_outer_chamfer_to_right_edge": 180.0,
                    "top_cover": top_cover,
                    "top_edge_offset_left": 45.0,
                    "point_1_left": {"x": -w, "y": y1},
                    "point_2_left": {"x": -w + b4, "y": y2},
                    "point_B_left": {"x": -w + inset, "y": d},
                    "point_B_right": {"x": w, "y": d},
                },
                "wall_thicknesses_mm": {
                    "top": top_cover,
                    "bottom": h3,
                    "left": left_outer + float(width_mm) / 2.0,
                    "right": float(width_mm) / 2.0 - right_outer,
                },
                "inner_chamfer_mm": b2,
                "r_inner_mm": b2,
                "r_outer_mm": outer_radius,
                "n_fillet": n_fillet,
                "inner_bounds_mm": {
                    "left_flat": left_flat,
                    "right_flat": right_flat,
                    "left_outer": left_outer,
                    "right_outer": right_outer,
                    "bottom": bottom_y,
                    "top": top_y,
                },
            },
        )

    # Legacy branch kept for backward compatibility.
    top, bottom, left, right = _resolve_wall_thicknesses(
        t_top_mm=t_top_mm,
        t_bottom_mm=t_bottom_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        wall_thickness_mm=wall_thickness_mm,
    )
    inner_chamfer = float(fillet_radius_mm if r_inner_mm is None and fillet_radius_mm is not None else r_inner_mm or 0.0)
    outer_radius = float(r_outer_mm)
    _require_non_negative("inner_chamfer_mm", inner_chamfer)
    _require_non_negative("r_outer_mm", outer_radius)
    if n_fillet < 4:
        raise ValueError("Invalid geometry: n_fillet must be at least 4.")
    inner_bounds = _inner_rect_bounds(
        width_mm=width_mm,
        height_mm=height_mm,
        t_top_mm=top,
        t_bottom_mm=bottom,
        t_left_mm=left,
        t_right_mm=right,
    )
    inner_width = inner_bounds[2] - inner_bounds[0]
    inner_height = inner_bounds[3] - inner_bounds[1]
    if outer_radius * 2.0 > min(width_mm, height_mm):
        raise ValueError("Invalid geometry: outer fillet radius is too large for the section dimensions.")
    if inner_chamfer * 2.0 > min(inner_width, inner_height):
        raise ValueError("Invalid geometry: inner chamfer is too large for inner void.")

    return SectionGeometry(
        name=name,
        outer_polygon=(
            _rounded_rectangle_points(width_mm, height_mm, outer_radius, n_fillet)
            if outer_radius > 0.0
            else _precast_box_beam_outer_points(width_mm, height_mm, exterior_side="right")
        ),
        holes=[list(reversed(_chamfered_rectangle_from_bounds(*inner_bounds, inner_chamfer)))],
        metadata={
            "preset": "precast_box_beam_exterior",
            "wall_thicknesses_mm": {"top": top, "bottom": bottom, "left": left, "right": right},
            "inner_chamfer_mm": inner_chamfer,
            "r_inner_mm": inner_chamfer,
            "r_outer_mm": outer_radius,
            "n_fillet": n_fillet,
            "exterior_side": "right",
        },
    )


def psc_i_girder(
    depth_mm: float,
    top_flange_width_mm: float,
    top_flange_thickness_mm: float,
    web_width_mm: float,
    bottom_flange_width_mm: float,
    bottom_flange_thickness_mm: float,
    name: str = "PSC I-girder",
) -> SectionGeometry:
    _require_positive("total depth", depth_mm)
    _require_positive("top flange width", top_flange_width_mm)
    _require_positive("bottom flange width", bottom_flange_width_mm)
    _require_positive("web thickness", web_width_mm)
    _require_positive("top flange thickness", top_flange_thickness_mm)
    _require_positive("bottom flange thickness", bottom_flange_thickness_mm)
    if top_flange_thickness_mm + bottom_flange_thickness_mm >= depth_mm:
        raise ValueError("Invalid geometry: top flange thickness + bottom flange thickness must be less than total depth.")
    if web_width_mm > top_flange_width_mm or web_width_mm > bottom_flange_width_mm:
        raise ValueError("Invalid geometry: web thickness must not exceed top or bottom flange width.")
    d = depth_mm / 2.0
    tw = top_flange_width_mm / 2.0
    bw = bottom_flange_width_mm / 2.0
    ww = web_width_mm / 2.0
    y_top_web = d - top_flange_thickness_mm
    y_bot_web = -d + bottom_flange_thickness_mm
    points = [
        _point(-bw, -d),
        _point(bw, -d),
        _point(bw, y_bot_web),
        _point(ww, y_bot_web),
        _point(ww, y_top_web),
        _point(tw, y_top_web),
        _point(tw, d),
        _point(-tw, d),
        _point(-tw, y_top_web),
        _point(-ww, y_top_web),
        _point(-ww, y_bot_web),
        _point(-bw, y_bot_web),
    ]
    _ensure_valid_simple_polygon(points, "PSC I-girder")
    return SectionGeometry(name=name, outer_polygon=points, holes=[], metadata={"preset": "psc_i_girder"})


def parametric_i_girder(
    B1_mm: float,
    B2_mm: float,
    D1_mm: float,
    D2_mm: float,
    D3_mm: float,
    D5_mm: float,
    D6_mm: float,
    T1_mm: float,
    T2_mm: float,
    C1_mm: float = 0.0,
    name: str = "Precast I-Girder",
) -> SectionGeometry:
    """Generate a symmetric parametric bridge I-girder section.

    Parameter naming intentionally follows the user's bridge-girder drafting
    convention rather than generic geometry names:
      B1 = top flange width, B2 = bottom flange width, D1 = total depth,
      D2 = top flange thickness, D3 = top haunch depth,
      D5 = bottom flange thickness, D6 = bottom haunch depth,
      T1 = upper web width, T2 = lower/main web width, C1 = corner chamfer.

    The first implementation is a left-right symmetric solid concrete polygon.
    It is intended as an analysis-ready section definition for PMM / future
    prestressed-girder checks, not merely a preview sketch.
    """
    for label, value in {
        "B1": B1_mm,
        "B2": B2_mm,
        "D1": D1_mm,
        "T1": T1_mm,
        "T2": T2_mm,
    }.items():
        _require_positive(label, value)
    for label, value in {"D2": D2_mm, "D3": D3_mm, "D5": D5_mm, "D6": D6_mm, "C1": C1_mm}.items():
        _require_non_negative(label, value)

    if T1_mm > B1_mm:
        raise ValueError("Invalid geometry: T1 must not exceed B1.")
    if T2_mm > B2_mm:
        raise ValueError("Invalid geometry: T2 must not exceed B2.")
    if T1_mm > B2_mm:
        raise ValueError("Invalid geometry: T1 must not exceed B2 so the web can connect through the section depth.")
    if T2_mm > B1_mm:
        raise ValueError("Invalid geometry: T2 must not exceed B1 so the web can connect through the section depth.")

    web_zone_mm = D1_mm - D2_mm - D3_mm - D5_mm - D6_mm
    if web_zone_mm <= 0:
        raise ValueError("Invalid geometry: D1 must be greater than D2 + D3 + D5 + D6.")

    chamfer_limit = max(0.0, min(B1_mm, B2_mm, D1_mm) / 2.0)
    if C1_mm > chamfer_limit:
        raise ValueError("Invalid geometry: C1 is too large for the selected girder dimensions.")

    top_y = D1_mm / 2.0
    bottom_y = -D1_mm / 2.0
    y_top_flange_bottom = top_y - D2_mm
    y_top_haunch_bottom = y_top_flange_bottom - D3_mm
    y_bottom_flange_top = bottom_y + D5_mm
    y_bottom_haunch_top = y_bottom_flange_top + D6_mm

    b1 = B1_mm / 2.0
    b2 = B2_mm / 2.0
    t1 = T1_mm / 2.0
    t2 = T2_mm / 2.0
    c = float(C1_mm)

    def add(points: list[Point2D], x: float, y: float) -> None:
        if points and abs(points[-1].x - x) < 1e-9 and abs(points[-1].y - y) < 1e-9:
            return
        points.append(_point(x, y))

    points: list[Point2D] = []
    # Clockwise/counter-clockwise orientation is not important to Shapely for
    # a solid polygon, but we keep an ordered perimeter without duplicate points.
    if c > 0:
        add(points, -b2 + c, bottom_y)
        add(points, b2 - c, bottom_y)
        add(points, b2, bottom_y + c)
    else:
        add(points, -b2, bottom_y)
        add(points, b2, bottom_y)
    add(points, b2, y_bottom_flange_top)
    add(points, t2, y_bottom_haunch_top)
    add(points, t1, y_top_haunch_bottom)
    add(points, b1, y_top_flange_bottom)
    if c > 0:
        add(points, b1, top_y - c)
        add(points, b1 - c, top_y)
        add(points, -b1 + c, top_y)
        add(points, -b1, top_y - c)
    else:
        add(points, b1, top_y)
        add(points, -b1, top_y)
    add(points, -b1, y_top_flange_bottom)
    add(points, -t1, y_top_haunch_bottom)
    add(points, -t2, y_bottom_haunch_top)
    add(points, -b2, y_bottom_flange_top)
    if c > 0:
        add(points, -b2, bottom_y + c)

    _ensure_valid_simple_polygon(points, "Precast I-Girder")
    return SectionGeometry(
        name=name,
        outer_polygon=points,
        holes=[],
        metadata={
            "preset": "parametric_i_girder",
            "girder_type": "I-Girder",
            "units": "mm",
            "parameters": {
                "B1_mm": B1_mm,
                "B2_mm": B2_mm,
                "D1_mm": D1_mm,
                "D2_mm": D2_mm,
                "D3_mm": D3_mm,
                "D5_mm": D5_mm,
                "D6_mm": D6_mm,
                "T1_mm": T1_mm,
                "T2_mm": T2_mm,
                "C1_mm": C1_mm,
            },
            "zone_depths_mm": {
                "top_flange": D2_mm,
                "top_haunch": D3_mm,
                "web_clear_zone": web_zone_mm,
                "bottom_haunch": D6_mm,
                "bottom_flange": D5_mm,
            },
            "analysis_compatibility": {
                "uls_pmm": "supported",
                "sls_stress": "planned",
                "beam_girder_assignment": "planned",
                "shear_torsion": "planned",
            },
        },
    )



def _plank_transformed_metadata(
    *,
    Tslab_mm: float,
    Be_mm: float,
    Ebeam_MPa: float,
    Edeck_MPa: float,
    girder_length_mm: float,
    overhang_mm: float = 0.0,
) -> dict[str, float | str]:
    _require_non_negative("Tslab", Tslab_mm)
    _require_positive("Be", Be_mm)
    _require_positive("Ebeam", Ebeam_MPa)
    _require_positive("Edeck", Edeck_MPa)
    _require_positive("Girder length", girder_length_mm)
    _require_non_negative("overhang", overhang_mm)
    n = Edeck_MPa / Ebeam_MPa
    return {
        "Tslab_mm": float(Tslab_mm),
        "Be_mm": float(Be_mm),
        "Ebeam_MPa": float(Ebeam_MPa),
        "Edeck_MPa": float(Edeck_MPa),
        "n_Edeck_over_Ebeam": float(n),
        "Btransformed_mm": float(n * Be_mm),
        "girder_length_mm": float(girder_length_mm),
        "overhang_mm": float(overhang_mm),
        "Be_calculation_mode": "manual_current__auto_aashto_planned",
    }


def parametric_plank_girder_interior(
    B_mm: float,
    b1_mm: float,
    b2_mm: float,
    b3_mm: float,
    H_mm: float,
    h1_mm: float,
    h2_mm: float,
    Tslab_mm: float = 100.0,
    Be_mm: float = 1000.0,
    Ebeam_MPa: float = 35000.0,
    Edeck_MPa: float = 28560.0,
    girder_length_mm: float = 12000.0,
    name: str = "Precast Plank Girder — Interior",
) -> SectionGeometry:
    """Generate a symmetric interior precast plank-girder polygon.

    The polygon represents the precast plank only. Composite deck metadata is
    retained for future AASHTO SLS/transformed-section checks, but the slab is
    not merged into the concrete polygon in this milestone.
    """
    for label, value in {"B": B_mm, "b3": b3_mm, "H": H_mm}.items():
        _require_positive(label, value)
    for label, value in {"b1": b1_mm, "b2": b2_mm, "h1": h1_mm, "h2": h2_mm}.items():
        _require_non_negative(label, value)
    if b3_mm >= B_mm:
        raise ValueError("Invalid geometry: b3 must be smaller than B for an interior plank with side offsets.")
    if h1_mm > h2_mm:
        raise ValueError("Invalid geometry: h1 must not exceed h2.")
    if h2_mm >= H_mm:
        raise ValueError("Invalid geometry: h2 must be less than H.")
    expected_b2 = (B_mm - b3_mm) / 2.0
    if abs(expected_b2 - b2_mm) > max(2.0, 0.05 * B_mm):
        raise ValueError("Invalid geometry: for interior plank, B should approximately equal b3 + 2*b2.")
    if b1_mm > (B_mm - b3_mm) / 2.0 + b1_mm + B_mm:
        raise ValueError("Invalid geometry: b1 is not compatible with the selected plank width.")

    top_y = H_mm / 2.0
    bottom_y = -H_mm / 2.0
    y1 = bottom_y + h1_mm
    y2 = bottom_y + h2_mm

    # User-confirmed interior plank convention:
    #   at y = 0      width = B
    #   at y = h1     width = B
    #   at y = h2     width = b3
    #   at y = H      width = B - 2*b1
    #   side recesses are symmetric.
    # Coordinates are centered on the plank reference centerline.
    x_outer = B_mm / 2.0
    x_top = (B_mm - 2.0 * b1_mm) / 2.0
    x_recess = b3_mm / 2.0

    if x_top <= 0.0:
        raise ValueError("Invalid geometry: B must be greater than 2*b1 for an interior plank.")
    if x_recess <= 0.0:
        raise ValueError("Invalid geometry: b3 must be greater than zero.")
    if x_recess >= x_outer:
        raise ValueError("Invalid geometry: b3 must be smaller than B for an interior plank recess.")

    points = [
        _point(-x_top, top_y),
        _point(x_top, top_y),
        _point(x_recess, y2),
        _point(x_outer, y1),
        _point(x_outer, bottom_y),
        _point(-x_outer, bottom_y),
        _point(-x_outer, y1),
        _point(-x_recess, y2),
    ]
    _ensure_valid_simple_polygon(points, "Parametric interior plank girder")
    transformed = _plank_transformed_metadata(
        Tslab_mm=Tslab_mm,
        Be_mm=Be_mm,
        Ebeam_MPa=Ebeam_MPa,
        Edeck_MPa=Edeck_MPa,
        girder_length_mm=girder_length_mm,
        overhang_mm=0.0,
    )
    return SectionGeometry(
        name=name,
        outer_polygon=points,
        holes=[],
        metadata={
            "preset": "parametric_plank_girder_interior",
            "girder_type": "Plank Girder",
            "plank_position": "Interior",
            "units": "mm",
            "parameters": {
                "B_mm": B_mm,
                "b1_mm": b1_mm,
                "b2_mm": b2_mm,
                "b3_mm": b3_mm,
                "H_mm": H_mm,
                "h1_mm": h1_mm,
                "h2_mm": h2_mm,
            },
            "composite_metadata": transformed,
            "analysis_compatibility": {
                "uls_pmm": "supported_precast_only",
                "sls_stress": "planned_composite_metadata_ready",
                "beam_girder_assignment": "planned",
                "aashto_effective_width_auto": "planned",
                "shear_torsion": "planned",
            },
        },
    )


def parametric_plank_girder_voided_interior(
    B_mm: float,
    b1_mm: float,
    b2_mm: float,
    b3_mm: float,
    H_mm: float,
    h1_mm: float,
    h2_mm: float,
    void_diameter_mm: float = 150.0,
    void_y_mm_from_bottom: float = 225.0,
    void_left_x_from_left_mm: float = 245.0,
    void_middle_x_from_left_mm: float = 495.0,
    void_right_x_from_left_mm: float = 745.0,
    Tslab_mm: float = 100.0,
    Be_mm: float = 1000.0,
    Ebeam_MPa: float = 35000.0,
    Edeck_MPa: float = 28560.0,
    girder_length_mm: float = 12000.0,
    name: str = "Precast Voided Plank Girder — Interior",
) -> SectionGeometry:
    """Generate an interior precast plank girder with three circular voids.

    The outer profile intentionally reuses the accepted interior plank girder
    geometry. The three circular voids are real section holes, not preview-only
    graphics, so gross properties and void-aware prestress validation use the
    reduced concrete polygon.
    """

    base = parametric_plank_girder_interior(
        B_mm=B_mm,
        b1_mm=b1_mm,
        b2_mm=b2_mm,
        b3_mm=b3_mm,
        H_mm=H_mm,
        h1_mm=h1_mm,
        h2_mm=h2_mm,
        Tslab_mm=Tslab_mm,
        Be_mm=Be_mm,
        Ebeam_MPa=Ebeam_MPa,
        Edeck_MPa=Edeck_MPa,
        girder_length_mm=girder_length_mm,
        name=name,
    )
    x_positions = [void_left_x_from_left_mm, void_middle_x_from_left_mm, void_right_x_from_left_mm]
    holes = [
        _circular_hole_from_left_edge(
            B_mm=B_mm,
            H_mm=H_mm,
            diameter_mm=void_diameter_mm,
            x_from_left_mm=x,
            y_from_bottom_mm=void_y_mm_from_bottom,
        )
        for x in x_positions
    ]
    _ensure_valid_polygon_with_holes(base.outer_polygon, holes, "Precast voided plank girder — Interior")
    metadata = dict(base.metadata)
    parameters = dict(metadata.get("parameters", {}))
    parameters.update(
        {
            "void_diameter_mm": void_diameter_mm,
            "void_y_mm_from_bottom": void_y_mm_from_bottom,
            "void_left_x_from_left_mm": void_left_x_from_left_mm,
            "void_middle_x_from_left_mm": void_middle_x_from_left_mm,
            "void_right_x_from_left_mm": void_right_x_from_left_mm,
        }
    )
    metadata.update(
        {
            "preset": "parametric_plank_girder_voided_interior",
            "girder_type": "Voided Plank Girder",
            "plank_position": "Interior",
            "void_type": "3 circular voids",
            "parameters": parameters,
        }
    )
    return SectionGeometry(name=name, outer_polygon=base.outer_polygon, holes=holes, metadata=metadata)




def parametric_plank_girder_exterior(
    B_mm: float,
    b1_mm: float,
    b2_mm: float,
    b3_mm: float,
    H_mm: float,
    h1_mm: float,
    h2_mm: float,
    Tslab_mm: float = 100.0,
    Be_mm: float = 1000.0,
    Ebeam_MPa: float = 35000.0,
    Edeck_MPa: float = 28560.0,
    girder_length_mm: float = 12000.0,
    overhang_mm: float = 500.0,
    name: str = "Precast Plank Girder — Exterior",
) -> SectionGeometry:
    """Generate an asymmetric exterior precast plank-girder polygon.

    The exterior side is kept vertical; the interior side follows the stepped
    plank profile. The polygon is precast-only. Effective slab width data are
    retained as metadata for future AASHTO composite checks.
    """
    for label, value in {"B": B_mm, "b3": b3_mm, "H": H_mm}.items():
        _require_positive(label, value)
    for label, value in {"b1": b1_mm, "b2": b2_mm, "h1": h1_mm, "h2": h2_mm, "overhang": overhang_mm}.items():
        _require_non_negative(label, value)
    if b3_mm >= B_mm:
        raise ValueError("Invalid geometry: b3 must be smaller than B for an exterior plank with one side offset.")
    if h1_mm > h2_mm:
        raise ValueError("Invalid geometry: h1 must not exceed h2.")
    if h2_mm >= H_mm:
        raise ValueError("Invalid geometry: h2 must be less than H.")
    expected_b2 = B_mm - b3_mm
    if abs(expected_b2 - b2_mm) > max(2.0, 0.05 * B_mm):
        raise ValueError("Invalid geometry: for exterior plank, B should approximately equal b3 + b2.")

    top_y = H_mm / 2.0
    bottom_y = -H_mm / 2.0
    y1 = bottom_y + h1_mm
    y2 = bottom_y + h2_mm

    # User-confirmed exterior plank convention:
    #   exterior side = right side, vertical for full height;
    #   interior side = left side with the same stepped/recessed profile;
    #   b1 and b2 are measured from the left reference edge;
    #   b3 is measured from the right edge, so B should equal b2 + b3.
    # Left boundary positions from the left reference edge are:
    #   y = 0  -> x = 0
    #   y = h1 -> x = 0
    #   y = h2 -> x = b2
    #   y = H  -> x = b1
    x_left = -B_mm / 2.0
    x_right = B_mm / 2.0
    x_top_left = x_left + b1_mm
    x_recess_left = x_left + b2_mm

    if x_top_left >= x_right:
        raise ValueError("Invalid geometry: B must be greater than b1 for an exterior plank.")
    if x_recess_left >= x_right:
        raise ValueError("Invalid geometry: b2 must be smaller than B for an exterior plank recess.")

    points = [
        _point(x_top_left, top_y),
        _point(x_right, top_y),
        _point(x_right, bottom_y),
        _point(x_left, bottom_y),
        _point(x_left, y1),
        _point(x_recess_left, y2),
    ]
    _ensure_valid_simple_polygon(points, "Parametric exterior plank girder")
    transformed = _plank_transformed_metadata(
        Tslab_mm=Tslab_mm,
        Be_mm=Be_mm,
        Ebeam_MPa=Ebeam_MPa,
        Edeck_MPa=Edeck_MPa,
        girder_length_mm=girder_length_mm,
        overhang_mm=overhang_mm,
    )
    return SectionGeometry(
        name=name,
        outer_polygon=points,
        holes=[],
        metadata={
            "preset": "parametric_plank_girder_exterior",
            "girder_type": "Plank Girder",
            "plank_position": "Exterior",
            "units": "mm",
            "parameters": {
                "B_mm": B_mm,
                "b1_mm": b1_mm,
                "b2_mm": b2_mm,
                "b3_mm": b3_mm,
                "H_mm": H_mm,
                "h1_mm": h1_mm,
                "h2_mm": h2_mm,
            },
            "composite_metadata": transformed,
            "analysis_compatibility": {
                "uls_pmm": "supported_precast_only",
                "sls_stress": "planned_composite_metadata_ready",
                "beam_girder_assignment": "planned",
                "aashto_effective_width_auto": "planned",
                "shear_torsion": "planned",
            },
        },
    )

def u_girder(
    depth_mm: float,
    top_width_mm: float,
    bottom_width_mm: float,
    wall_thickness_mm: float,
    bottom_slab_thickness_mm: float,
    name: str = "Precast U-Girder",
) -> SectionGeometry:
    _require_positive("total depth", depth_mm)
    _require_positive("top width", top_width_mm)
    _require_positive("bottom width", bottom_width_mm)
    _require_positive("web thickness", wall_thickness_mm)
    _require_positive("bottom slab thickness", bottom_slab_thickness_mm)
    if bottom_slab_thickness_mm >= depth_mm:
        raise ValueError("Invalid geometry: bottom slab thickness must be less than total depth.")
    if top_width_mm <= bottom_width_mm:
        raise ValueError("Invalid geometry: top width must be greater than bottom width for this U-girder generator.")
    if 2.0 * wall_thickness_mm >= top_width_mm or 2.0 * wall_thickness_mm >= bottom_width_mm:
        raise ValueError("Invalid geometry: web thickness is too large for the selected girder widths.")
    top_y = depth_mm / 2.0
    bot_y = -depth_mm / 2.0
    inner_bot_y = bot_y + bottom_slab_thickness_mm
    points = [
        _point(-top_width_mm / 2.0, top_y),
        _point(-top_width_mm / 2.0 + wall_thickness_mm, top_y),
        _point(-bottom_width_mm / 2.0 + wall_thickness_mm, inner_bot_y),
        _point(bottom_width_mm / 2.0 - wall_thickness_mm, inner_bot_y),
        _point(top_width_mm / 2.0 - wall_thickness_mm, top_y),
        _point(top_width_mm / 2.0, top_y),
        _point(bottom_width_mm / 2.0, bot_y),
        _point(-bottom_width_mm / 2.0, bot_y),
    ]
    _ensure_valid_simple_polygon(points, "Precast U-Girder")
    return SectionGeometry(name=name, outer_polygon=points, holes=[], metadata={"preset": "u_girder"})


def single_cell_box_girder(
    width_mm: float,
    depth_mm: float,
    top_slab_thickness_mm: float,
    bottom_slab_thickness_mm: float,
    web_thickness_mm: float,
    name: str = "Single cell box girder",
) -> SectionGeometry:
    _require_positive("B", width_mm)
    _require_positive("D", depth_mm)
    _require_positive("top slab thickness", top_slab_thickness_mm)
    _require_positive("bottom slab thickness", bottom_slab_thickness_mm)
    _require_positive("web thickness", web_thickness_mm)
    if top_slab_thickness_mm + bottom_slab_thickness_mm >= depth_mm:
        raise ValueError("Invalid geometry: top slab + bottom slab must be less than total depth.")
    if 2.0 * web_thickness_mm >= width_mm:
        raise ValueError("Invalid geometry: web thickness is too large; inner width must be positive.")
    inner_w = width_mm - 2.0 * web_thickness_mm
    inner_h = depth_mm - top_slab_thickness_mm - bottom_slab_thickness_mm
    if inner_w <= 0:
        raise ValueError("Invalid geometry: inner width must be greater than zero.")
    if inner_h <= 0:
        raise ValueError("Invalid geometry: inner height must be greater than zero.")
    cy = (bottom_slab_thickness_mm - top_slab_thickness_mm) / 2.0
    hole = [_point(p.x, p.y + cy) for p in _rectangle_points(inner_w, inner_h)]
    return SectionGeometry(
        name=name,
        outer_polygon=_rectangle_points(width_mm, depth_mm),
        holes=[list(reversed(hole))],
        metadata={"preset": "single_cell_box_girder"},
    )


def _dim(
    symbol: str,
    start: Point2D,
    end: Point2D,
    text: Point2D,
    kind: str = "aligned",
    value: float | None = None,
    unit: str = "mm",
) -> DimensionItem:
    label = f"{symbol} = {value:g} {unit}" if value is not None else symbol
    return DimensionItem(label=label, symbol=symbol, start=start, end=end, text_position=text, kind=kind, value_mm=value, unit=unit)


def rectangle_dimensions(width_mm: float, height_mm: float, **_: object) -> list[DimensionItem]:
    w = width_mm / 2.0
    h = height_mm / 2.0
    offset = max(width_mm, height_mm) * 0.08
    return [
        _dim("B", _point(-w, -h - offset), _point(w, -h - offset), _point(0, -h - 1.6 * offset), "horizontal", width_mm),
        _dim("H", _point(w + offset, -h), _point(w + offset, h), _point(w + 1.8 * offset, 0), "vertical", height_mm),
    ]


def rectangular_chamfered_dimensions(
    width_mm: float,
    height_mm: float,
    chamfer_mm: float | None = None,
    chamfer_x_mm: float | None = None,
    chamfer_y_mm: float | None = None,
    **kwargs: object,
) -> list[DimensionItem]:
    w = width_mm / 2.0
    h = height_mm / 2.0
    legacy_chamfer = 0.0 if chamfer_mm is None else float(chamfer_mm)
    cx = legacy_chamfer if chamfer_x_mm is None else float(chamfer_x_mm)
    cy = legacy_chamfer if chamfer_y_mm is None else float(chamfer_y_mm)
    offset = max(width_mm, height_mm) * 0.08

    # Keep the global B/H guides clear of local chamfer guides.  For this
    # section the local cy dimension sits near the top-right chamfer, so the
    # overall H dimension is pushed farther outward to avoid visually merging
    # the two vertical guides.
    cy_x = w + offset
    h_x = w + (2.0 * offset if cy > 0.0 else offset)

    dims = [
        _dim("B", _point(-w, -h - offset), _point(w, -h - offset), _point(0, -h - 1.6 * offset), "horizontal", width_mm),
        _dim("H", _point(h_x, -h), _point(h_x, h), _point(h_x + 0.8 * offset, 0), "vertical", height_mm),
    ]
    if cx > 0:
        dims.append(_dim("cx", _point(w - cx, h + offset), _point(w, h + offset), _point(w - cx / 2.0, h + 1.6 * offset), "horizontal", cx))
    if cy > 0:
        dims.append(_dim("cy", _point(cy_x, h - cy), _point(cy_x, h), _point(cy_x + 0.8 * offset, h - cy / 2.0), "vertical", cy))
    return dims


def rectangular_filleted_dimensions(
    width_mm: float,
    height_mm: float,
    corner_radius_mm: float,
    n_fillet: int = 16,
    **kwargs: object,
) -> list[DimensionItem]:
    # n_fillet is part of geometry discretization only; dimension guides show the analytical section size.
    _ = (n_fillet, kwargs)
    dims = rectangle_dimensions(width_mm, height_mm)
    if corner_radius_mm > 0:
        w = width_mm / 2.0
        h = height_mm / 2.0
        r = float(corner_radius_mm)
        arc_point = _point(w - r * (1.0 - math.cos(math.pi / 4.0)), -h + r * (1.0 - math.sin(math.pi / 4.0)))
        leader_end = _point(w + 0.6 * r, -h - 0.6 * r)
        text_point = _point(w + 0.38 * r, -h - 0.38 * r)
        dims.append(_dim("R", arc_point, leader_end, text_point, "radial", r))
    return dims


def circle_dimensions(diameter_mm: float, **_: object) -> list[DimensionItem]:
    r = diameter_mm / 2.0
    return [_dim("D", _point(-r, 0), _point(r, 0), _point(0, -0.18 * diameter_mm), "diameter", diameter_mm)]


def circular_hollow_dimensions(outer_diameter_mm: float, inner_diameter_mm: float, **_: object) -> list[DimensionItem]:
    r_outer = outer_diameter_mm / 2.0
    r_inner = inner_diameter_mm / 2.0
    return [
        _dim("D_outer", _point(-r_outer, 0), _point(r_outer, 0), _point(0, -0.18 * outer_diameter_mm), "diameter", outer_diameter_mm),
        _dim("D_inner", _point(-r_inner, 0), _point(r_inner, 0), _point(0, 0.18 * outer_diameter_mm), "diameter", inner_diameter_mm),
    ]


def rectangular_hollow_dimensions(
    width_mm: float,
    height_mm: float,
    t_top_mm: float | None = None,
    t_bottom_mm: float | None = None,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    wall_thickness_mm: float | None = None,
    **kwargs: object,
) -> list[DimensionItem]:
    top, bottom, left, right = _resolve_wall_thicknesses(
        t_top_mm=t_top_mm,
        t_bottom_mm=t_bottom_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        wall_thickness_mm=wall_thickness_mm,
    )
    dims = rectangle_dimensions(width_mm, height_mm, **kwargs)
    dims.extend(
        [
            _dim("t_left", _point(-width_mm / 2.0, 0), _point(-width_mm / 2.0 + left, 0), _point(-width_mm / 2.0, height_mm * 0.18), "horizontal", left),
            _dim("t_right", _point(width_mm / 2.0 - right, 0), _point(width_mm / 2.0, 0), _point(width_mm / 2.0, height_mm * 0.18), "horizontal", right),
            _dim("t_top", _point(0, height_mm / 2.0 - top), _point(0, height_mm / 2.0), _point(-width_mm * 0.18, height_mm / 2.0), "vertical", top),
            _dim("t_bottom", _point(0, -height_mm / 2.0), _point(0, -height_mm / 2.0 + bottom), _point(width_mm * 0.18, -height_mm / 2.0), "vertical", bottom),
        ]
    )
    return dims


def rectangular_hollow_filleted_dimensions(
    width_mm: float,
    height_mm: float,
    t_top_mm: float | None = None,
    t_bottom_mm: float | None = None,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    r_outer_mm: float = 0.0,
    r_inner_mm: float = 0.0,
    n_fillet: int = 16,
    wall_thickness_mm: float | None = None,
    **kwargs: object,
) -> list[DimensionItem]:
    _ = (n_fillet,)
    dims = rectangular_hollow_dimensions(
        width_mm,
        height_mm,
        t_top_mm=t_top_mm,
        t_bottom_mm=t_bottom_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        wall_thickness_mm=wall_thickness_mm,
        **kwargs,
    )
    w = width_mm / 2.0
    h = height_mm / 2.0
    if r_outer_mm > 0:
        dims.append(
            _dim(
                "Ro",
                _point(w - r_outer_mm * (1.0 - math.cos(math.pi / 4.0)), -h + r_outer_mm * (1.0 - math.sin(math.pi / 4.0))),
                _point(w + 0.6 * r_outer_mm, -h - 0.6 * r_outer_mm),
                _point(w + 0.38 * r_outer_mm, -h - 0.38 * r_outer_mm),
                "radial",
                r_outer_mm,
            )
        )
    if r_inner_mm > 0:
        top, bottom, left, right = _resolve_wall_thicknesses(
            t_top_mm=t_top_mm,
            t_bottom_mm=t_bottom_mm,
            t_left_mm=t_left_mm,
            t_right_mm=t_right_mm,
            wall_thickness_mm=wall_thickness_mm,
        )
        inner_right = width_mm / 2.0 - right
        inner_bottom = -height_mm / 2.0 + bottom
        dims.append(
            _dim(
                "Ri",
                _point(inner_right - r_inner_mm * (1.0 - math.cos(math.pi / 4.0)), inner_bottom + r_inner_mm * (1.0 - math.sin(math.pi / 4.0))),
                _point(inner_right + 0.42 * r_inner_mm, inner_bottom - 0.42 * r_inner_mm),
                _point(inner_right + 0.28 * r_inner_mm, inner_bottom - 0.28 * r_inner_mm),
                "radial",
                r_inner_mm,
            )
        )
    return dims


def rectangular_hollow_outer_filleted_inner_chamfered_dimensions(
    width_mm: float,
    height_mm: float,
    t_top_mm: float | None = None,
    t_bottom_mm: float | None = None,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    r_outer_mm: float = 0.0,
    inner_chamfer_mm: float = 0.0,
    n_fillet: int = 16,
    wall_thickness_mm: float | None = None,
    **kwargs: object,
) -> list[DimensionItem]:
    _ = (n_fillet,)
    dims = rectangular_hollow_dimensions(
        width_mm,
        height_mm,
        t_top_mm=t_top_mm,
        t_bottom_mm=t_bottom_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        wall_thickness_mm=wall_thickness_mm,
        **kwargs,
    )
    w = width_mm / 2.0
    h = height_mm / 2.0
    if r_outer_mm > 0:
        dims.append(
            _dim(
                "Ro",
                _point(w - r_outer_mm * (1.0 - math.cos(math.pi / 4.0)), -h + r_outer_mm * (1.0 - math.sin(math.pi / 4.0))),
                _point(w + 0.6 * r_outer_mm, -h - 0.6 * r_outer_mm),
                _point(w + 0.38 * r_outer_mm, -h - 0.38 * r_outer_mm),
                "radial",
                r_outer_mm,
            )
        )
    if inner_chamfer_mm > 0:
        top, bottom, left, right = _resolve_wall_thicknesses(
            t_top_mm=t_top_mm,
            t_bottom_mm=t_bottom_mm,
            t_left_mm=t_left_mm,
            t_right_mm=t_right_mm,
            wall_thickness_mm=wall_thickness_mm,
        )
        inner_right = width_mm / 2.0 - right
        inner_bottom = -height_mm / 2.0 + bottom
        dims.append(
            _dim(
                "Ci",
                _point(inner_right - inner_chamfer_mm, inner_bottom),
                _point(inner_right, inner_bottom + inner_chamfer_mm),
                _point(inner_right + 0.28 * inner_chamfer_mm, inner_bottom + 0.28 * inner_chamfer_mm),
                "aligned",
                inner_chamfer_mm,
            )
        )
    return dims


def box_section_fillet_dimensions(
    width_mm: float,
    height_mm: float,
    t_top_mm: float | None = None,
    t_bottom_mm: float | None = None,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    r_inner_mm: float | None = None,
    r_outer_mm: float = 0.0,
    n_fillet: int = 12,
    wall_thickness_mm: float | None = None,
    fillet_radius_mm: float | None = None,
    h1_mm: float | None = None,
    h3_mm: float | None = None,
    h4_mm: float | None = None,
    h5_mm: float | None = None,
    h6_mm: float | None = None,
    h7_mm: float | None = None,
    h8_mm: float | None = None,
    b2_mm: float | None = None,
    b3_mm: float | None = None,
    b4_mm: float | None = None,
    b2_start_from_left_mm: float | None = None,
    **kwargs: object,
) -> list[DimensionItem]:
    # n_fillet is intentionally kept in the dimension-helper signature to
    # mirror the geometry generator; dimension annotations do not discretize arcs.
    _ = n_fillet
    use_drawing_parameters = any(value is not None for value in (h1_mm, h3_mm, h4_mm, h5_mm, h6_mm, h7_mm, h8_mm, b2_mm, b3_mm, b4_mm, b2_start_from_left_mm))
    if use_drawing_parameters:
        h1 = float(180.0 if h1_mm is None else h1_mm)
        h3 = float(160.0 if h3_mm is None else h3_mm)
        h4 = float(80.0 if h4_mm is None else h4_mm)
        h5 = float(200.0 if h5_mm is None else h5_mm)
        h6 = float(300.0 if h6_mm is None else h6_mm)
        h7 = float(400.0 if h7_mm is None else h7_mm)
        h8 = float(70.0 if h8_mm is None else h8_mm)
        b2 = float(100.0 if b2_mm is None else b2_mm)
        b3 = float(290.0 if b3_mm is None else b3_mm)
        b4 = float(70.0 if b4_mm is None else b4_mm)
        derived_b2_start = (float(width_mm) - (2.0 * b2 + b3)) / 2.0
        b2_start = derived_b2_start if b2_start_from_left_mm is None else float(b2_start_from_left_mm)
        dims = rectangle_dimensions(width_mm, height_mm, **kwargs)
        w = width_mm / 2.0
        h = height_mm / 2.0
        half_b3 = b3 / 2.0
        top_cover = h1
        # Outer profile note dimensions.
        dims.extend(
            [
                _dim("h7", _point(-w - 80.0, -h), _point(-w - 80.0, -h + h7), _point(-w - 105.0, -h + h7 / 2.0), "vertical", h7),
                _dim("h6", _point(-w - 45.0, -h + h7), _point(-w - 45.0, h), _point(-w - 20.0, -h + h7 + (height_mm - h7) / 2.0), "vertical", h6),
                _dim("h8", _point(-w - 15.0, -h + h7), _point(-w - 15.0, -h + h7 + h8), _point(-w - 40.0, -h + h7 + h8 / 2.0), "vertical", h8),
                _dim("b4", _point(-w, -h + h7 - 28.0), _point(-w + b4, -h + h7 - 28.0), _point(-w + b4 / 2.0, -h + h7 - 58.0), "horizontal", b4),
                _dim("b3", _point(-half_b3, -h + h3 - 35.0), _point(half_b3, -h + h3 - 35.0), _point(0.0, -h + h3 - 65.0), "horizontal", b3),
                _dim("b2", _point(-half_b3 - b2, -h + h3 + 2.0 * h4 + h5 + 55.0), _point(-half_b3, -h + h3 + 2.0 * h4 + h5 + 55.0), _point(-half_b3 - b2 / 2.0, -h + h3 + 2.0 * h4 + h5 + 85.0), "horizontal", b2),
                _dim("h3", _point(-half_b3 - b2 - 55.0, -h), _point(-half_b3 - b2 - 55.0, -h + h3), _point(-half_b3 - b2 - 80.0, -h + h3 / 2.0), "vertical", h3),
                _dim("h4", _point(-half_b3 - b2 - 25.0, -h + h3), _point(-half_b3 - b2 - 25.0, -h + h3 + h4), _point(-half_b3 - b2 - 60.0, -h + h3 + h4 / 2.0), "vertical", h4),
                _dim("h5", _point(-half_b3 - b2 - 55.0, -h + h3 + h4), _point(-half_b3 - b2 - 55.0, -h + h3 + h4 + h5), _point(-half_b3 - b2 - 80.0, -h + h3 + h4 + h5 / 2.0), "vertical", h5),
                _dim("h4", _point(-half_b3 - b2 - 25.0, -h + h3 + h4 + h5), _point(-half_b3 - b2 - 25.0, -h + h3 + 2.0 * h4 + h5), _point(-half_b3 - b2 - 60.0, -h + h3 + h4 + h5 + h4 / 2.0), "vertical", h4),
            ]
        )
        if top_cover > 0:
            dims.append(_dim("h1", _point(half_b3 + b2 + 55.0, h - h1), _point(half_b3 + b2 + 55.0, h), _point(half_b3 + b2 + 85.0, h - h1 / 2.0), "vertical", h1))
        return dims

    top, bottom, left, right = _resolve_wall_thicknesses(
        t_top_mm=t_top_mm,
        t_bottom_mm=t_bottom_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        wall_thickness_mm=wall_thickness_mm,
    )
    inner_chamfer = float(fillet_radius_mm if r_inner_mm is None and fillet_radius_mm is not None else r_inner_mm or 0.0)
    dims = rectangular_hollow_dimensions(width_mm, height_mm, top, bottom, left, right, **kwargs)
    if inner_chamfer > 0:
        dims.append(
            _dim(
                "Ci",
                _point(width_mm / 2.0 - right - inner_chamfer, height_mm / 2.0 - top),
                _point(width_mm / 2.0 - right, height_mm / 2.0 - top - inner_chamfer),
                _point(width_mm / 2.0 - right + inner_chamfer * 0.35, height_mm / 2.0 - top - inner_chamfer * 0.35),
                "aligned",
                inner_chamfer,
            )
        )
    dims.append(
        _dim(
            "Ro",
            _point(width_mm / 2.0 - r_outer_mm, height_mm / 2.0),
            _point(width_mm / 2.0, height_mm / 2.0 - r_outer_mm),
            _point(width_mm / 2.0, height_mm / 2.0),
            "radial",
            r_outer_mm,
        )
    )
    return dims


def precast_box_beam_exterior_dimensions(
    width_mm: float,
    height_mm: float,
    t_top_mm: float | None = None,
    t_bottom_mm: float | None = None,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    r_inner_mm: float | None = None,
    r_outer_mm: float = 0.0,
    n_fillet: int = 12,
    wall_thickness_mm: float | None = None,
    fillet_radius_mm: float | None = None,
    h1_mm: float | None = None,
    h3_mm: float | None = None,
    h4_mm: float | None = None,
    h5_mm: float | None = None,
    h6_mm: float | None = None,
    h7_mm: float | None = None,
    h8_mm: float | None = None,
    b2_mm: float | None = None,
    b3_mm: float | None = None,
    b4_mm: float | None = None,
    **kwargs: object,
) -> list[DimensionItem]:
    _ = (n_fillet, wall_thickness_mm, fillet_radius_mm, r_inner_mm, r_outer_mm, t_top_mm, t_bottom_mm, t_left_mm, t_right_mm)
    use_drawing_parameters = any(value is not None for value in (h1_mm, h3_mm, h4_mm, h5_mm, h6_mm, h7_mm, h8_mm, b2_mm, b3_mm, b4_mm))
    if use_drawing_parameters:
        h1 = float(180.0 if h1_mm is None else h1_mm)
        h3 = float(160.0 if h3_mm is None else h3_mm)
        h4 = float(80.0 if h4_mm is None else h4_mm)
        h5 = float(200.0 if h5_mm is None else h5_mm)
        h6 = float(300.0 if h6_mm is None else h6_mm)
        h7 = float(400.0 if h7_mm is None else h7_mm)
        h8 = float(70.0 if h8_mm is None else h8_mm)
        b2 = float(100.0 if b2_mm is None else b2_mm)
        b3 = float(360.0 if b3_mm is None else b3_mm)
        b4 = float(70.0 if b4_mm is None else b4_mm)
        dims = rectangle_dimensions(width_mm, height_mm, **kwargs)
        w = width_mm / 2.0
        h = height_mm / 2.0
        top_cover = h1
        right_clear_from_b3_to_edge = b2 + 180.0
        right_flat = w - right_clear_from_b3_to_edge
        left_flat = right_flat - b3
        left_outer = left_flat - b2
        right_outer = right_flat + b2
        dims.extend(
            [
                _dim("h7", _point(-w - 80.0, -h), _point(-w - 80.0, -h + h7), _point(-w - 105.0, -h + h7 / 2.0), "vertical", h7),
                _dim("h6", _point(-w - 45.0, -h + h7), _point(-w - 45.0, h), _point(-w - 20.0, -h + h7 + (height_mm - h7) / 2.0), "vertical", h6),
                _dim("h8", _point(-w - 15.0, -h + h7), _point(-w - 15.0, -h + h7 + h8), _point(-w - 40.0, -h + h7 + h8 / 2.0), "vertical", h8),
                _dim("b4", _point(-w, -h + h7 - 28.0), _point(-w + b4, -h + h7 - 28.0), _point(-w + b4 / 2.0, -h + h7 - 58.0), "horizontal", b4),
                _dim("b3", _point(left_flat, -h + h3 - 35.0), _point(right_flat, -h + h3 - 35.0), _point((left_flat + right_flat) / 2.0, -h + h3 - 65.0), "horizontal", b3),
                _dim("b2", _point(left_outer, -h + h3 + 2.0 * h4 + h5 + 55.0), _point(left_flat, -h + h3 + 2.0 * h4 + h5 + 55.0), _point((left_outer + left_flat) / 2.0, -h + h3 + 2.0 * h4 + h5 + 85.0), "horizontal", b2),
                _dim("b2+180", _point(right_flat, -h + h3 - 90.0), _point(w, -h + h3 - 90.0), _point((right_flat + w) / 2.0, -h + h3 - 120.0), "horizontal", right_clear_from_b3_to_edge),
                _dim("h3", _point(left_outer - 55.0, -h), _point(left_outer - 55.0, -h + h3), _point(left_outer - 80.0, -h + h3 / 2.0), "vertical", h3),
                _dim("h4", _point(left_outer - 25.0, -h + h3), _point(left_outer - 25.0, -h + h3 + h4), _point(left_outer - 60.0, -h + h3 + h4 / 2.0), "vertical", h4),
                _dim("h5", _point(left_outer - 55.0, -h + h3 + h4), _point(left_outer - 55.0, -h + h3 + h4 + h5), _point(left_outer - 80.0, -h + h3 + h4 + h5 / 2.0), "vertical", h5),
                _dim("h4", _point(left_outer - 25.0, -h + h3 + h4 + h5), _point(left_outer - 25.0, -h + h3 + 2.0 * h4 + h5), _point(left_outer - 60.0, -h + h3 + h4 + h5 + h4 / 2.0), "vertical", h4),
            ]
        )
        if top_cover > 0:
            dims.append(_dim("h1", _point(right_outer + 40.0, h - h1), _point(right_outer + 40.0, h), _point(right_outer + 70.0, h - h1 / 2.0), "vertical", h1))
        return dims

    # Legacy dimensions fallback.
    return box_section_fillet_dimensions(
        width_mm,
        height_mm,
        t_top_mm=t_top_mm,
        t_bottom_mm=t_bottom_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        r_inner_mm=r_inner_mm,
        r_outer_mm=r_outer_mm,
        n_fillet=n_fillet,
        wall_thickness_mm=wall_thickness_mm,
        fillet_radius_mm=fillet_radius_mm,
        **kwargs,
    )


def parametric_i_girder_dimensions(
    B1_mm: float,
    B2_mm: float,
    D1_mm: float,
    D2_mm: float,
    D3_mm: float,
    D5_mm: float,
    D6_mm: float,
    T1_mm: float,
    T2_mm: float,
    C1_mm: float = 0.0,
    **_: object,
) -> list[DimensionItem]:
    top_y = D1_mm / 2.0
    bottom_y = -D1_mm / 2.0
    y_top_flange_bottom = top_y - D2_mm
    y_top_haunch_bottom = y_top_flange_bottom - D3_mm
    y_bottom_flange_top = bottom_y + D5_mm
    y_bottom_haunch_top = y_bottom_flange_top + D6_mm
    offset = max(B1_mm, B2_mm, D1_mm) * 0.08
    right = max(B1_mm, B2_mm) / 2.0
    dims = [
        _dim("D1", _point(right + offset, bottom_y), _point(right + offset, top_y), _point(right + 2.0 * offset, 0.0), "vertical", D1_mm),
        _dim("B1", _point(-B1_mm / 2.0, top_y + offset), _point(B1_mm / 2.0, top_y + offset), _point(0.0, top_y + 1.6 * offset), "horizontal", B1_mm),
        _dim("B2", _point(-B2_mm / 2.0, bottom_y - offset), _point(B2_mm / 2.0, bottom_y - offset), _point(0.0, bottom_y - 1.6 * offset), "horizontal", B2_mm),
        _dim("T1", _point(-T1_mm / 2.0, y_top_haunch_bottom), _point(T1_mm / 2.0, y_top_haunch_bottom), _point(0.0, y_top_haunch_bottom + offset), "horizontal", T1_mm),
        _dim("T2", _point(-T2_mm / 2.0, y_bottom_haunch_top), _point(T2_mm / 2.0, y_bottom_haunch_top), _point(0.0, y_bottom_haunch_top - offset), "horizontal", T2_mm),
        _dim("D2", _point(-right - offset, y_top_flange_bottom), _point(-right - offset, top_y), _point(-right - 2.0 * offset, top_y - D2_mm / 2.0), "vertical", D2_mm),
        _dim("D3", _point(-right - offset, y_top_haunch_bottom), _point(-right - offset, y_top_flange_bottom), _point(-right - 2.0 * offset, y_top_flange_bottom - D3_mm / 2.0), "vertical", D3_mm),
        _dim("D5", _point(-right - offset, bottom_y), _point(-right - offset, y_bottom_flange_top), _point(-right - 2.0 * offset, bottom_y + D5_mm / 2.0), "vertical", D5_mm),
        _dim("D6", _point(-right - offset, y_bottom_flange_top), _point(-right - offset, y_bottom_haunch_top), _point(-right - 2.0 * offset, y_bottom_flange_top + D6_mm / 2.0), "vertical", D6_mm),
    ]
    if C1_mm > 0:
        dims.append(
            _dim(
                "C1",
                _point(B2_mm / 2.0 - C1_mm, bottom_y),
                _point(B2_mm / 2.0, bottom_y + C1_mm),
                _point(B2_mm / 2.0 + offset * 0.7, bottom_y + offset * 0.35),
                "aligned",
                C1_mm,
            )
        )
    return dims



def parametric_plank_girder_voided_exterior(
    B_mm: float,
    b1_mm: float,
    b2_mm: float,
    b3_mm: float,
    H_mm: float,
    h1_mm: float,
    h2_mm: float,
    void_diameter_mm: float = 150.0,
    void_y_mm_from_bottom: float = 225.0,
    void_left_x_from_left_mm: float = 240.0,
    void_middle_x_from_left_mm: float = 540.0,
    void_right_x_from_left_mm: float = 810.0,
    Tslab_mm: float = 100.0,
    Be_mm: float = 1000.0,
    Ebeam_MPa: float = 35000.0,
    Edeck_MPa: float = 28560.0,
    girder_length_mm: float = 12000.0,
    overhang_mm: float = 500.0,
    name: str = "Precast Voided Plank Girder — Exterior",
) -> SectionGeometry:
    """Generate an exterior precast plank girder with three circular voids."""

    base = parametric_plank_girder_exterior(
        B_mm=B_mm,
        b1_mm=b1_mm,
        b2_mm=b2_mm,
        b3_mm=b3_mm,
        H_mm=H_mm,
        h1_mm=h1_mm,
        h2_mm=h2_mm,
        Tslab_mm=Tslab_mm,
        Be_mm=Be_mm,
        Ebeam_MPa=Ebeam_MPa,
        Edeck_MPa=Edeck_MPa,
        girder_length_mm=girder_length_mm,
        overhang_mm=overhang_mm,
        name=name,
    )
    x_positions = [void_left_x_from_left_mm, void_middle_x_from_left_mm, void_right_x_from_left_mm]
    holes = [
        _circular_hole_from_left_edge(
            B_mm=B_mm,
            H_mm=H_mm,
            diameter_mm=void_diameter_mm,
            x_from_left_mm=x,
            y_from_bottom_mm=void_y_mm_from_bottom,
        )
        for x in x_positions
    ]
    _ensure_valid_polygon_with_holes(base.outer_polygon, holes, "Precast voided plank girder — Exterior")
    metadata = dict(base.metadata)
    parameters = dict(metadata.get("parameters", {}))
    parameters.update(
        {
            "void_diameter_mm": void_diameter_mm,
            "void_y_mm_from_bottom": void_y_mm_from_bottom,
            "void_left_x_from_left_mm": void_left_x_from_left_mm,
            "void_middle_x_from_left_mm": void_middle_x_from_left_mm,
            "void_right_x_from_left_mm": void_right_x_from_left_mm,
        }
    )
    metadata.update(
        {
            "preset": "parametric_plank_girder_voided_exterior",
            "girder_type": "Voided Plank Girder",
            "plank_position": "Exterior",
            "void_type": "3 circular voids",
            "parameters": parameters,
        }
    )
    return SectionGeometry(name=name, outer_polygon=base.outer_polygon, holes=holes, metadata=metadata)





def slab_bridge(
    width_mm: float,
    edge_depth_mm: float,
    center_depth_mm: float,
    name: str = "Slab Bridge",
) -> SectionGeometry:
    """Generate a solid bridge slab section with a center crown.

    Geometry basis from the user-provided slab-bridge cross-section:
    - total width B = 5100 mm by default,
    - left and right half-widths = B/2,
    - edge depth = 400 mm by default,
    - centerline depth = 450 mm by default,
    - bottom soffit is flat and the top surface is linearly crowned to the
      centerline.  No chamfer/fillet is inferred because none is dimensioned.
    """

    _require_positive("width_mm", width_mm)
    _require_positive("edge_depth_mm", edge_depth_mm)
    _require_positive("center_depth_mm", center_depth_mm)
    if center_depth_mm < edge_depth_mm:
        raise ValueError(
            "Invalid geometry: center_depth_mm must be greater than or equal to "
            "edge_depth_mm for a crowned slab bridge section."
        )

    half_width = float(width_mm) / 2.0
    bottom_y = -float(center_depth_mm) / 2.0
    top_center_y = float(center_depth_mm) / 2.0
    top_edge_y = bottom_y + float(edge_depth_mm)
    crown_rise = float(center_depth_mm) - float(edge_depth_mm)

    points = [
        _point(-half_width, bottom_y),
        _point(half_width, bottom_y),
        _point(half_width, top_edge_y),
        _point(0.0, top_center_y),
        _point(-half_width, top_edge_y),
    ]
    _ensure_valid_simple_polygon(points, "Slab Bridge")
    return SectionGeometry(
        name=name,
        outer_polygon=points,
        holes=[],
        metadata={
            "preset": "slab_bridge",
            "girder_type": "Slab Bridge",
            "units": "mm",
            "parameters": {
                "width_mm": width_mm,
                "edge_depth_mm": edge_depth_mm,
                "center_depth_mm": center_depth_mm,
            },
            "crown_rise_mm": crown_rise,
            "analysis_compatibility": {
                "uls_pmm": "supported_gross_solid_section_preview",
                "sls_stress": "guarded_gross_section_preview",
                "beam_girder_assignment": "supported_bridge_beam_girder_preset",
                "shear_torsion": "guarded_preview",
            },
        },
    )


def parametric_plank_girder_interior_dimensions(
    B_mm: float,
    b1_mm: float,
    b2_mm: float,
    b3_mm: float,
    H_mm: float,
    h1_mm: float,
    h2_mm: float,
    **_: object,
) -> list[DimensionItem]:
    x_outer = B_mm / 2.0
    x_bottom = b3_mm / 2.0
    top_y = H_mm / 2.0
    bottom_y = -H_mm / 2.0
    offset = max(B_mm, H_mm) * 0.07
    return [
        _dim("B", _point(-x_outer, top_y + offset), _point(x_outer, top_y + offset), _point(0, top_y + 1.6 * offset), "horizontal", B_mm),
        _dim("b3", _point(-x_bottom, bottom_y - offset), _point(x_bottom, bottom_y - offset), _point(0, bottom_y - 1.6 * offset), "horizontal", b3_mm),
        _dim("H", _point(x_outer + offset, bottom_y), _point(x_outer + offset, top_y), _point(x_outer + 1.8 * offset, 0), "vertical", H_mm),
        _dim("h1", _point(-x_outer - offset, bottom_y), _point(-x_outer - offset, bottom_y + h1_mm), _point(-x_outer - 1.8 * offset, bottom_y + h1_mm / 2.0), "vertical", h1_mm),
        _dim("h2", _point(-x_outer - 2.1 * offset, bottom_y), _point(-x_outer - 2.1 * offset, bottom_y + h2_mm), _point(-x_outer - 2.9 * offset, bottom_y + h2_mm / 2.0), "vertical", h2_mm),
        _dim("b1", _point(x_outer - b1_mm, top_y + 0.35 * offset), _point(x_outer, top_y + 0.35 * offset), _point(x_outer - b1_mm / 2.0, top_y + 0.9 * offset), "horizontal", b1_mm),
        _dim("b2", _point(x_bottom, bottom_y - 0.35 * offset), _point(x_outer, bottom_y - 0.35 * offset), _point((x_bottom + x_outer) / 2.0, bottom_y - 0.9 * offset), "horizontal", b2_mm),
    ]


def parametric_plank_girder_exterior_dimensions(
    B_mm: float,
    b1_mm: float,
    b2_mm: float,
    b3_mm: float,
    H_mm: float,
    h1_mm: float,
    h2_mm: float,
    **_: object,
) -> list[DimensionItem]:
    x_left = -B_mm / 2.0
    x_right = B_mm / 2.0
    x_bottom_left = x_right - b3_mm
    top_y = H_mm / 2.0
    bottom_y = -H_mm / 2.0
    offset = max(B_mm, H_mm) * 0.07
    return [
        _dim("B", _point(x_left, top_y + offset), _point(x_right, top_y + offset), _point(0, top_y + 1.6 * offset), "horizontal", B_mm),
        _dim("b3", _point(x_bottom_left, bottom_y - offset), _point(x_right, bottom_y - offset), _point((x_bottom_left + x_right) / 2.0, bottom_y - 1.6 * offset), "horizontal", b3_mm),
        _dim("H", _point(x_right + offset, bottom_y), _point(x_right + offset, top_y), _point(x_right + 1.8 * offset, 0), "vertical", H_mm),
        _dim("h1", _point(x_left - offset, bottom_y), _point(x_left - offset, bottom_y + h1_mm), _point(x_left - 1.8 * offset, bottom_y + h1_mm / 2.0), "vertical", h1_mm),
        _dim("h2", _point(x_left - 2.1 * offset, bottom_y), _point(x_left - 2.1 * offset, bottom_y + h2_mm), _point(x_left - 2.9 * offset, bottom_y + h2_mm / 2.0), "vertical", h2_mm),
        _dim("b1", _point(x_left, top_y + 0.35 * offset), _point(x_left + b1_mm, top_y + 0.35 * offset), _point(x_left + b1_mm / 2.0, top_y + 0.9 * offset), "horizontal", b1_mm),
        _dim("b2", _point(x_left, bottom_y - 0.35 * offset), _point(x_bottom_left, bottom_y - 0.35 * offset), _point((x_left + x_bottom_left) / 2.0, bottom_y - 0.9 * offset), "horizontal", b2_mm),
    ]




def _coalesce_float(value: object, fallback: object, name: str) -> float:
    selected = fallback if value is None else value
    _require_positive(name, selected)
    return float(selected)


def railway_u_girder(
    width_mm: float,
    depth_mm: float,
    top_wall_width_mm: float,
    bottom_side_width_mm: float,
    haunch_x_mm: float | None = None,
    haunch_y_mm: float | None = None,
    h1_step_height_mm: float | None = None,
    h2_bottom_opening_mm: float | None = None,
    h3_floor_side_thickness_mm: float | None = None,
    h4_floor_center_thickness_mm: float | None = None,
    # Backward-compatible aliases from SECTION.RAIL.UGIRDER1 saved projects.
    inner_vertical_depth_mm: float | None = None,
    haunch_size_mm: float | None = None,
    floor_side_thickness_mm: float | None = None,
    floor_center_thickness_mm: float | None = None,
    name: str = "Railway U-Girder",
) -> SectionGeometry:
    """Generate a non-composite railway through U-girder section.

    The preset follows the user-provided railway U-girder drawing.  Primary
    section dimensions are exposed in the Section Builder.  The outside notch
    is derived from ``bottom_side_width_mm - top_wall_width_mm``; the six
    25 mm chamfers remain fixed drawing details so the UI does not become
    cluttered with secondary drafting inputs.

    Newer presets drive the vertical geometry with ``h1`` through ``h4``:
    ``h1`` is the outside step height from bottom, ``h2`` is the bottom opening
    depth below the floor underside, ``h3`` is the side floor thickness, and
    ``h4`` is the centerline floor thickness.  Older saved projects that still
    provide ``inner_vertical_depth_mm``, ``haunch_size_mm``, and floor thickness
    aliases are accepted and mapped to the same geometry.
    """

    _require_positive("width_mm", width_mm)
    _require_positive("depth_mm", depth_mm)
    _require_positive("top_wall_width_mm", top_wall_width_mm)
    _require_positive("bottom_side_width_mm", bottom_side_width_mm)

    width = float(width_mm)
    depth = float(depth_mm)
    top_wall_width = float(top_wall_width_mm)
    bottom_side_width = float(bottom_side_width_mm)

    # Backward-compatible defaults preserve the originally accepted drawing.
    legacy_haunch = 300.0 if haunch_size_mm is None else float(haunch_size_mm)
    haunch_x = _coalesce_float(haunch_x_mm, legacy_haunch, "haunch_x_mm")
    haunch_y = _coalesce_float(haunch_y_mm, legacy_haunch, "haunch_y_mm")
    h3_side = _coalesce_float(
        h3_floor_side_thickness_mm,
        395.0 if floor_side_thickness_mm is None else floor_side_thickness_mm,
        "h3_floor_side_thickness_mm",
    )
    h4_center = _coalesce_float(
        h4_floor_center_thickness_mm,
        450.0 if floor_center_thickness_mm is None else floor_center_thickness_mm,
        "h4_floor_center_thickness_mm",
    )
    h2_bottom = _coalesce_float(h2_bottom_opening_mm, 305.0, "h2_bottom_opening_mm")

    if h1_step_height_mm is None:
        if inner_vertical_depth_mm is not None:
            # Original default: inner vertical 600 + haunch 300 + 10% haunch =
            # step y from top 930, so h1 from bottom = 670 for H=1600.
            legacy_step_from_top = float(inner_vertical_depth_mm) + legacy_haunch + 0.10 * legacy_haunch
            h1_step = depth - legacy_step_from_top
        else:
            h1_step = 670.0
    else:
        h1_step = _coalesce_float(h1_step_height_mm, 670.0, "h1_step_height_mm")

    chamfer = 25.0
    half_width = width / 2.0
    inner_half_width = half_width - bottom_side_width
    if inner_half_width <= 0.0:
        raise ValueError("Invalid geometry: bottom side width must be less than half the total width.")
    if top_wall_width >= bottom_side_width:
        raise ValueError(
            "Invalid geometry: top wall width must be less than bottom side width so the outside notch can be derived."
        )
    notch = bottom_side_width - top_wall_width
    upper_outer_half_width = half_width - notch
    if min(top_wall_width, bottom_side_width, inner_half_width) <= 2.0 * chamfer:
        raise ValueError("Invalid geometry: chamfer is too large for the selected side wall dimensions.")
    if haunch_x >= inner_half_width:
        raise ValueError("Invalid geometry: haunch X must be smaller than the inner half width.")

    outside_step_y = depth - h1_step
    floor_underside_y = depth - h2_bottom
    floor_side_top_y = floor_underside_y - h3_side
    floor_center_top_y = floor_underside_y - h4_center
    haunch_start_y = floor_side_top_y - haunch_y

    if outside_step_y <= chamfer or outside_step_y >= depth - chamfer:
        raise ValueError("Invalid geometry: h1 step height places the outside notch too close to the top or bottom.")
    if h2_bottom <= chamfer or floor_underside_y >= depth or floor_underside_y <= chamfer:
        raise ValueError("Invalid geometry: h2 bottom opening leaves an invalid floor underside level.")
    if floor_side_top_y <= chamfer:
        raise ValueError("Invalid geometry: h2 and h3 place the side floor top too close to the section top.")
    if floor_center_top_y <= chamfer:
        raise ValueError("Invalid geometry: h2 and h4 place the center floor top too close to the section top.")
    if haunch_start_y <= chamfer:
        raise ValueError("Invalid geometry: haunch Y is too large for the side floor level.")
    if floor_underside_y >= depth - chamfer:
        raise ValueError("Invalid geometry: floor underside is too close to the bottom chamfer.")
    if upper_outer_half_width <= inner_half_width:
        raise ValueError("Invalid geometry: derived upper outside face must remain outside the inner face.")

    # Drawing coordinates: x is from bridge centerline, y is measured downward
    # from the top of side wall.  They are converted to the app's centered
    # coordinate system where +y is upward.
    drawing_points = [
        (-upper_outer_half_width + chamfer, 0.0),
        (-inner_half_width - chamfer, 0.0),
        (-inner_half_width, chamfer),
        (-inner_half_width, haunch_start_y),
        (-(inner_half_width - haunch_x), floor_side_top_y),
        (0.0, floor_center_top_y),
        (inner_half_width - haunch_x, floor_side_top_y),
        (inner_half_width, haunch_start_y),
        (inner_half_width, chamfer),
        (inner_half_width + chamfer, 0.0),
        (upper_outer_half_width - chamfer, 0.0),
        (upper_outer_half_width, chamfer),
        (upper_outer_half_width, outside_step_y),
        (half_width, outside_step_y),
        (half_width, depth - chamfer),
        (half_width - chamfer, depth),
        (inner_half_width, depth),
        (inner_half_width, floor_underside_y),
        (-inner_half_width, floor_underside_y),
        (-inner_half_width, depth),
        (-half_width + chamfer, depth),
        (-half_width, depth - chamfer),
        (-half_width, outside_step_y),
        (-upper_outer_half_width, outside_step_y),
        (-upper_outer_half_width, chamfer),
    ]
    points = [_point(x, depth / 2.0 - y_down) for x, y_down in drawing_points]
    _ensure_valid_simple_polygon(points, "Railway U-Girder")
    return SectionGeometry(
        name=name,
        outer_polygon=points,
        holes=[],
        metadata={
            "preset": "railway_u_girder",
            "girder_type": "Railway U-Girder",
            "units": "mm",
            "parameters": {
                "width_mm": width_mm,
                "depth_mm": depth_mm,
                "top_wall_width_mm": top_wall_width_mm,
                "bottom_side_width_mm": bottom_side_width_mm,
                "haunch_x_mm": haunch_x,
                "haunch_y_mm": haunch_y,
                "h1_step_height_mm": h1_step,
                "h2_bottom_opening_mm": h2_bottom,
                "h3_floor_side_thickness_mm": h3_side,
                "h4_floor_center_thickness_mm": h4_center,
            },
            "derived_details": {
                "outside_notch_mm": notch,
                "outside_step_y_from_top_mm": outside_step_y,
                "chamfer_mm": chamfer,
                "inner_half_width_mm": inner_half_width,
                "haunch_start_y_from_top_mm": haunch_start_y,
                "floor_side_top_y_from_top_mm": floor_side_top_y,
                "floor_center_top_y_from_top_mm": floor_center_top_y,
                "floor_underside_y_from_top_mm": floor_underside_y,
            },
            "analysis_compatibility": {
                "uls_pmm": "supported_gross_solid_section_preview",
                "sls_stress": "guarded_gross_section_preview",
                "beam_girder_assignment": "supported_bridge_beam_girder_preset",
                "shear_torsion": "guarded_preview",
            },
        },
    )


def railway_u_girder_dimensions(
    width_mm: float,
    depth_mm: float,
    top_wall_width_mm: float,
    bottom_side_width_mm: float,
    haunch_x_mm: float | None = None,
    haunch_y_mm: float | None = None,
    h1_step_height_mm: float | None = None,
    h2_bottom_opening_mm: float | None = None,
    h3_floor_side_thickness_mm: float | None = None,
    h4_floor_center_thickness_mm: float | None = None,
    # Backward-compatible aliases from SECTION.RAIL.UGIRDER1 saved projects.
    inner_vertical_depth_mm: float | None = None,
    haunch_size_mm: float | None = None,
    floor_side_thickness_mm: float | None = None,
    floor_center_thickness_mm: float | None = None,
    **_: object,
) -> list[DimensionItem]:
    width = float(width_mm)
    depth = float(depth_mm)
    half_width = width / 2.0
    bottom_side_width = float(bottom_side_width_mm)
    top_wall_width = float(top_wall_width_mm)
    inner_half_width = half_width - bottom_side_width
    notch = bottom_side_width - top_wall_width
    upper_outer_half_width = half_width - notch
    legacy_haunch = 300.0 if haunch_size_mm is None else float(haunch_size_mm)
    haunch_x = _coalesce_float(haunch_x_mm, legacy_haunch, "haunch_x_mm")
    haunch_y = _coalesce_float(haunch_y_mm, legacy_haunch, "haunch_y_mm")
    h3_side = _coalesce_float(
        h3_floor_side_thickness_mm,
        395.0 if floor_side_thickness_mm is None else floor_side_thickness_mm,
        "h3_floor_side_thickness_mm",
    )
    h4_center = _coalesce_float(
        h4_floor_center_thickness_mm,
        450.0 if floor_center_thickness_mm is None else floor_center_thickness_mm,
        "h4_floor_center_thickness_mm",
    )
    h2_bottom = _coalesce_float(h2_bottom_opening_mm, 305.0, "h2_bottom_opening_mm")
    if h1_step_height_mm is None:
        if inner_vertical_depth_mm is not None:
            legacy_step_from_top = float(inner_vertical_depth_mm) + legacy_haunch + 0.10 * legacy_haunch
            h1_step = depth - legacy_step_from_top
        else:
            h1_step = 670.0
    else:
        h1_step = _coalesce_float(h1_step_height_mm, 670.0, "h1_step_height_mm")

    outside_step_y = depth - h1_step
    floor_underside_y = depth - h2_bottom
    floor_side_top_y = floor_underside_y - h3_side
    floor_center_top_y = floor_underside_y - h4_center
    haunch_start_y = floor_side_top_y - haunch_y
    offset = max(width, depth) * 0.055

    def y_app(y_down: float) -> float:
        return depth / 2.0 - y_down

    return [
        _dim("B", _point(-half_width, y_app(0.0) + 2.2 * offset), _point(half_width, y_app(0.0) + 2.2 * offset), _point(0.0, y_app(0.0) + 2.75 * offset), "horizontal", width),
        _dim("B/2 L", _point(-half_width, y_app(0.0) + 1.25 * offset), _point(0.0, y_app(0.0) + 1.25 * offset), _point(-half_width / 2.0, y_app(0.0) + 1.75 * offset), "horizontal", half_width),
        _dim("B/2 R", _point(0.0, y_app(0.0) + 1.25 * offset), _point(half_width, y_app(0.0) + 1.25 * offset), _point(half_width / 2.0, y_app(0.0) + 1.75 * offset), "horizontal", half_width),
        _dim("t_wall_top", _point(-upper_outer_half_width, y_app(0.0) + 0.30 * offset), _point(-inner_half_width, y_app(0.0) + 0.30 * offset), _point(-(upper_outer_half_width + inner_half_width) / 2.0, y_app(0.0) + 0.85 * offset), "horizontal", top_wall_width),
        _dim("clear_half", _point(-inner_half_width, y_app(0.0) + 0.30 * offset), _point(0.0, y_app(0.0) + 0.30 * offset), _point(-inner_half_width / 2.0, y_app(0.0) + 0.85 * offset), "horizontal", inner_half_width),
        _dim("H", _point(-half_width - 0.75 * offset, y_app(depth)), _point(-half_width - 0.75 * offset, y_app(0.0)), _point(-half_width - 1.25 * offset, 0.0), "vertical", depth),
        _dim("h1", _point(-half_width - 0.25 * offset, y_app(depth)), _point(-half_width - 0.25 * offset, y_app(outside_step_y)), _point(-half_width - 0.65 * offset, y_app((depth + outside_step_y) / 2.0)), "vertical", h1_step),
        _dim("h2", _point(inner_half_width + 0.25 * offset, y_app(depth)), _point(inner_half_width + 0.25 * offset, y_app(floor_underside_y)), _point(inner_half_width + 0.72 * offset, y_app((depth + floor_underside_y) / 2.0)), "vertical", h2_bottom),
        _dim("h3", _point(inner_half_width + 0.35 * offset, y_app(floor_side_top_y)), _point(inner_half_width + 0.35 * offset, y_app(floor_underside_y)), _point(inner_half_width + 0.85 * offset, y_app((floor_side_top_y + floor_underside_y) / 2.0)), "vertical", h3_side),
        _dim("h4", _point(0.0, y_app(floor_center_top_y)), _point(0.0, y_app(floor_underside_y)), _point(0.35 * offset, y_app((floor_center_top_y + floor_underside_y) / 2.0)), "vertical", h4_center),
        # Keep haunch-X and haunch-Y labels on opposite sides of the trough.
        # When both were drawn on the right-side haunch their annotation boxes
        # overlapped, visually truncating the 300 mm hx label as "30" in
        # Streamlit/Plotly.  The section is symmetric, so showing hx on the
        # left haunch and hy on the right haunch preserves the same geometry
        # meaning while keeping the dimension text legible.
        _dim("hx", _point(-inner_half_width, y_app(floor_side_top_y) + 0.22 * offset), _point(-(inner_half_width - haunch_x), y_app(floor_side_top_y) + 0.22 * offset), _point(-(inner_half_width - haunch_x / 2.0), y_app(floor_side_top_y) + 0.65 * offset), "horizontal", haunch_x),
        _dim("hy", _point(inner_half_width + 0.18 * offset, y_app(floor_side_top_y)), _point(inner_half_width + 0.18 * offset, y_app(haunch_start_y)), _point(inner_half_width + 0.78 * offset, y_app((floor_side_top_y + haunch_start_y) / 2.0)), "vertical", haunch_y),
        _dim("bottom_leg", _point(-half_width, y_app(depth) - 0.30 * offset), _point(-inner_half_width, y_app(depth) - 0.30 * offset), _point(-(half_width + inner_half_width) / 2.0, y_app(depth) - 0.85 * offset), "horizontal", bottom_side_width),
        _dim("notch", _point(-half_width, y_app(outside_step_y)), _point(-upper_outer_half_width, y_app(outside_step_y)), _point(-(half_width + upper_outer_half_width) / 2.0, y_app(outside_step_y) + 0.45 * offset), "horizontal", notch),
        _dim("CL", _point(0.0, y_app(depth) - 0.75 * offset), _point(0.0, y_app(0.0) + 3.0 * offset), _point(0.0, y_app(0.0) + 3.25 * offset), "vertical", None),
    ]


def slab_bridge_dimensions(
    width_mm: float,
    edge_depth_mm: float,
    center_depth_mm: float,
    **_: object,
) -> list[DimensionItem]:
    half_width = float(width_mm) / 2.0
    bottom_y = -float(center_depth_mm) / 2.0
    top_center_y = float(center_depth_mm) / 2.0
    top_edge_y = bottom_y + float(edge_depth_mm)
    offset = max(float(width_mm), float(center_depth_mm)) * 0.06

    return [
        _dim(
            "B",
            _point(-half_width, top_center_y + 2.0 * offset),
            _point(half_width, top_center_y + 2.0 * offset),
            _point(0.0, top_center_y + 2.55 * offset),
            "horizontal",
            width_mm,
        ),
        _dim(
            "B/2 L",
            _point(-half_width, top_center_y + 1.15 * offset),
            _point(0.0, top_center_y + 1.15 * offset),
            _point(-half_width / 2.0, top_center_y + 1.6 * offset),
            "horizontal",
            half_width,
        ),
        _dim(
            "B/2 R",
            _point(0.0, top_center_y + 1.15 * offset),
            _point(half_width, top_center_y + 1.15 * offset),
            _point(half_width / 2.0, top_center_y + 1.6 * offset),
            "horizontal",
            half_width,
        ),
        _dim(
            "Hc",
            _point(0.0, bottom_y),
            _point(0.0, top_center_y),
            _point(-0.23 * offset, (bottom_y + top_center_y) / 2.0),
            "vertical",
            center_depth_mm,
        ),
        _dim(
            "He L",
            _point(-half_width - 0.42 * offset, bottom_y),
            _point(-half_width - 0.42 * offset, top_edge_y),
            _point(-half_width - 0.93 * offset, (bottom_y + top_edge_y) / 2.0),
            "vertical",
            edge_depth_mm,
        ),
        _dim(
            "He R",
            _point(half_width + 0.42 * offset, bottom_y),
            _point(half_width + 0.42 * offset, top_edge_y),
            _point(half_width + 0.93 * offset, (bottom_y + top_edge_y) / 2.0),
            "vertical",
            edge_depth_mm,
        ),
        _dim(
            "CL",
            _point(0.0, bottom_y - 0.75 * offset),
            _point(0.0, top_center_y + 2.95 * offset),
            _point(0.0, top_center_y + 3.2 * offset),
            "vertical",
            None,
        ),
    ]


def psc_i_girder_dimensions(depth_mm: float, top_flange_width_mm: float, bottom_flange_width_mm: float, web_width_mm: float, **_: object) -> list[DimensionItem]:
    d = depth_mm / 2.0
    offset = depth_mm * 0.08
    return [
        _dim("D", _point(max(top_flange_width_mm, bottom_flange_width_mm) / 2.0 + offset, -d), _point(max(top_flange_width_mm, bottom_flange_width_mm) / 2.0 + offset, d), _point(max(top_flange_width_mm, bottom_flange_width_mm) / 2.0 + 2 * offset, 0), "vertical", depth_mm),
        _dim("B_top", _point(-top_flange_width_mm / 2.0, d + offset), _point(top_flange_width_mm / 2.0, d + offset), _point(0, d + 1.6 * offset), "horizontal", top_flange_width_mm),
        _dim("t_web", _point(-web_width_mm / 2.0, 0), _point(web_width_mm / 2.0, 0), _point(0, -offset), "horizontal", web_width_mm),
    ]


def u_girder_dimensions(depth_mm: float, top_width_mm: float, bottom_width_mm: float, wall_thickness_mm: float, **_: object) -> list[DimensionItem]:
    d = depth_mm / 2.0
    offset = depth_mm * 0.08
    return [
        _dim("D", _point(top_width_mm / 2.0 + offset, -d), _point(top_width_mm / 2.0 + offset, d), _point(top_width_mm / 2.0 + 2 * offset, 0), "vertical", depth_mm),
        _dim("B_top", _point(-top_width_mm / 2.0, d + offset), _point(top_width_mm / 2.0, d + offset), _point(0, d + 1.6 * offset), "horizontal", top_width_mm),
        _dim("B_bot", _point(-bottom_width_mm / 2.0, -d - offset), _point(bottom_width_mm / 2.0, -d - offset), _point(0, -d - 1.6 * offset), "horizontal", bottom_width_mm),
        _dim("t_web", _point(top_width_mm / 2.0 - wall_thickness_mm, d - offset), _point(top_width_mm / 2.0, d - offset), _point(top_width_mm / 2.0, d - 2 * offset), "horizontal", wall_thickness_mm),
    ]


def single_cell_box_girder_dimensions(width_mm: float, depth_mm: float, web_thickness_mm: float, top_slab_thickness_mm: float, **kwargs: object) -> list[DimensionItem]:
    dims = rectangle_dimensions(width_mm, depth_mm, **kwargs)
    dims.append(_dim("t_web", _point(width_mm / 2.0 - web_thickness_mm, 0), _point(width_mm / 2.0, 0), _point(width_mm / 2.0, depth_mm * 0.18), "horizontal", web_thickness_mm))
    dims.append(_dim("t_top", _point(0, depth_mm / 2.0 - top_slab_thickness_mm), _point(0, depth_mm / 2.0), _point(-width_mm * 0.18, depth_mm / 2.0), "vertical", top_slab_thickness_mm))
    return dims


def register_builtin_generators(registry: GeometryRegistry) -> None:
    entries = {
        "rectangle": (rectangle, rectangle_dimensions),
        "rectangular_chamfered": (rectangular_chamfered, rectangular_chamfered_dimensions),
        "rectangular_filleted": (rectangular_filleted, rectangular_filleted_dimensions),
        "circle": (circle, circle_dimensions),
        "circular_hollow": (circular_hollow, circular_hollow_dimensions),
        "rectangular_hollow": (rectangular_hollow, rectangular_hollow_dimensions),
        "rectangular_hollow_filleted": (rectangular_hollow_filleted, rectangular_hollow_filleted_dimensions),
        "rectangular_hollow_outer_filleted_inner_chamfered": (
            rectangular_hollow_outer_filleted_inner_chamfered,
            rectangular_hollow_outer_filleted_inner_chamfered_dimensions,
        ),
        "box_section_fillet": (box_section_fillet, box_section_fillet_dimensions),
        "precast_box_beam_exterior": (precast_box_beam_exterior, precast_box_beam_exterior_dimensions),
        "psc_i_girder": (psc_i_girder, psc_i_girder_dimensions),
        "parametric_i_girder": (parametric_i_girder, parametric_i_girder_dimensions),
        "parametric_plank_girder_interior": (parametric_plank_girder_interior, parametric_plank_girder_interior_dimensions),
        "parametric_plank_girder_exterior": (parametric_plank_girder_exterior, parametric_plank_girder_exterior_dimensions),
        "parametric_plank_girder_voided_interior": (parametric_plank_girder_voided_interior, parametric_plank_girder_interior_dimensions),
        "parametric_plank_girder_voided_exterior": (parametric_plank_girder_voided_exterior, parametric_plank_girder_exterior_dimensions),
        "slab_bridge": (slab_bridge, slab_bridge_dimensions),
        "railway_u_girder": (railway_u_girder, railway_u_girder_dimensions),
        "u_girder": (u_girder, u_girder_dimensions),
        "single_cell_box_girder": (single_cell_box_girder, single_cell_box_girder_dimensions),
    }
    for name, (geometry_func, dimension_func) in entries.items():
        registry.register_geometry(name, geometry_func)
        registry.register_dimensions(name, dimension_func)
