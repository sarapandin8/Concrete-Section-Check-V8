"""Solver-neutral tendon input model for Portal Frame Crossbeams.

``CROSSBEAM.PT1`` promotes the accepted UI1 tendon tables into one canonical
source of truth shared by Tendon System, Tendon Profile, Project JSON, and the
station audit.  It deliberately performs no loss, stress, strength, or
anchorage-zone calculation; PTQA1 adds only segment-joint geometry continuity
review.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from shapely.geometry import Point

from concrete_pmm_pro.crossbeam.section_library import (
    build_geometry_for_definition,
    canonical_section_definitions,
    section_property_records,
)
from concrete_pmm_pro.crossbeam.workflow import (
    DEFAULT_FPJ_RATIO,
    DEFAULT_JACKING_END,
    DEFAULT_STRAND_APS_MM2,
    DEFAULT_STRAND_FPU_MPA,
    DEFAULT_STRANDS_PER_TENDON,
    DEFAULT_TENDON_COUNT,
    DEFAULT_TENDON_TYPE,
    JACKING_END_OPTIONS,
    TENDON_TYPE_OPTIONS,
    calculated_fpj_mpa,
    normalize_jacking_end,
    normalize_tendon_type,
)
from concrete_pmm_pro.geometry.summary import to_shapely_polygon


PROFILE_ROLE_OPTIONS = (
    "Anchorage",
    "Profile point",
    "High point",
    "Low point",
    "Deviator",
)
TENDON_PROFILE_PRESET_OPTIONS = (
    "Straight Tendon",
    "Straight Tendon With Bends",
    "Parabolic Tendon",
)
TENDON_PROFILE_SPAN_MODE_OPTIONS = ("Single Span", "2 Span")
DEFAULT_TENDON_PROFILE_PRESET = TENDON_PROFILE_PRESET_OPTIONS[0]
DEFAULT_TENDON_PROFILE_SPAN_MODE = TENDON_PROFILE_SPAN_MODE_OPTIONS[0]
DEFAULT_STRAND_SYSTEM = "Seven-wire low-relaxation strand"
DEFAULT_WEB_TENDONS_PER_SIDE = 4
DEFAULT_TENDON_TOP_OFFSET_MM = 500.0
DEFAULT_TENDON_BOTTOM_OFFSET_MM = 300.0
DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M = 1.0
TENDON_PROFILE_IMPORT_REQUIRED_COLUMNS = (
    "Tendon ID",
    "Point",
    "s (m)",
    "x lateral (mm)",
    "dtop (mm)",
    "Curve role",
)
TENDON_PROFILE_IMPORT_SCHEMA = (
    {
        "Column": "Tendon ID",
        "Required": True,
        "Description": "Tendon identifier already defined in Tendon System, for example T1.",
    },
    {
        "Column": "Point",
        "Required": True,
        "Description": "Profile point label within that tendon, for example P1, P2, P3.",
    },
    {
        "Column": "s (m)",
        "Required": True,
        "Description": "Longitudinal station measured from the left anchorage; must be between 0 and L.",
    },
    {
        "Column": "x lateral (mm)",
        "Required": True,
        "Description": "Cross-section lateral x coordinate; x = 0 is the member centerline.",
    },
    {
        "Column": "dtop (mm)",
        "Required": True,
        "Description": "Vertical depth measured downward from the top surface.",
    },
    {
        "Column": "Curve role",
        "Required": True,
        "Description": "One of Anchorage, Profile point, High point, Low point, or Deviator.",
    },
)
_TENDON_PROFILE_IMPORT_COLUMN_ALIASES = {
    "tendon": "Tendon ID",
    "tendonid": "Tendon ID",
    "tendonname": "Tendon ID",
    "point": "Point",
    "pointid": "Point",
    "station": "s (m)",
    "stationm": "s (m)",
    "sm": "s (m)",
    "s": "s (m)",
    "xlateral": "x lateral (mm)",
    "xlateralmm": "x lateral (mm)",
    "xmm": "x lateral (mm)",
    "x": "x lateral (mm)",
    "dtop": "dtop (mm)",
    "dtopmm": "dtop (mm)",
    "depthfromtopmm": "dtop (mm)",
    "depthfromtop": "dtop (mm)",
    "curverole": "Curve role",
    "role": "Curve role",
}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return int(default)


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"true", "yes", "1", "on", "active"}:
        return True
    if text in {"false", "no", "0", "off", "inactive"}:
        return False
    return bool(default)


def _records(values: Any) -> list[dict[str, Any]]:
    if hasattr(values, "to_dict"):
        try:
            rows = values.to_dict(orient="records")
            return [dict(row) for row in rows if isinstance(row, Mapping)]
        except (TypeError, ValueError):
            return []
    if isinstance(values, (list, tuple)):
        return [dict(row) for row in values if isinstance(row, Mapping)]
    return []


def default_tendon_system_rows(
    tendon_count: int = DEFAULT_TENDON_COUNT,
) -> list[dict[str, Any]]:
    """Return the PT1 seed system with more than two complete tendons."""

    count = max(_int(tendon_count, DEFAULT_TENDON_COUNT), 3)
    return [
        {
            "Tendon ID": f"T{index + 1}",
            "Active": True,
            "Type": DEFAULT_TENDON_TYPE,
            "Strands": DEFAULT_STRANDS_PER_TENDON,
            "Strand system": DEFAULT_STRAND_SYSTEM,
            "Aps/strand mm²": DEFAULT_STRAND_APS_MM2,
            "fpu MPa": DEFAULT_STRAND_FPU_MPA,
            "fpj/fpu": DEFAULT_FPJ_RATIO,
            "Jacking end": DEFAULT_JACKING_END,
            "Left anchorage": "s = 0",
            "Right anchorage": "s = L",
        }
        for index in range(count)
    ]


def canonical_tendon_system_rows(values: Any) -> list[dict[str, Any]]:
    """Return JSON-safe tendon-system rows while preserving validation inputs."""

    rows: list[dict[str, Any]] = []
    for source in _records(values):
        rows.append(
            {
                "Tendon ID": str(source.get("Tendon ID") or "").strip(),
                "Active": _bool(source.get("Active"), True),
                "Type": normalize_tendon_type(source.get("Type")),
                "Strands": _int(source.get("Strands"), DEFAULT_STRANDS_PER_TENDON),
                "Strand system": str(
                    source.get("Strand system") or DEFAULT_STRAND_SYSTEM
                ).strip(),
                "Aps/strand mm²": _float(
                    source.get("Aps/strand mm²"), DEFAULT_STRAND_APS_MM2
                ),
                "fpu MPa": _float(source.get("fpu MPa"), DEFAULT_STRAND_FPU_MPA),
                "fpj/fpu": _float(source.get("fpj/fpu"), DEFAULT_FPJ_RATIO),
                "Jacking end": normalize_jacking_end(source.get("Jacking end")),
                "Left anchorage": "s = 0",
                "Right anchorage": "s = L",
            }
        )
    return rows


def validate_tendon_system(
    values: Any,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    rows = canonical_tendon_system_rows(values)
    errors: list[str] = []
    warnings: list[str] = []
    ids = [str(row.get("Tendon ID") or "") for row in rows]
    active_count = sum(bool(row.get("Active")) for row in rows)
    if len(rows) < 3:
        errors.append("Portal Frame Crossbeam requires more than two tendon rows.")
    if active_count < 3:
        errors.append("Portal Frame Crossbeam requires at least three active tendons.")
    if any(not tendon_id for tendon_id in ids):
        errors.append("Every tendon row requires a Tendon ID.")
    duplicates = sorted({item for item in ids if item and ids.count(item) > 1})
    if duplicates:
        errors.append("Duplicate Tendon IDs are not allowed: " + ", ".join(duplicates) + ".")
    for row in rows:
        tendon_id = row["Tendon ID"] or "Unnamed tendon"
        if row["Type"] not in TENDON_TYPE_OPTIONS:
            errors.append(f"{tendon_id}: Type must be Internal or External.")
        if row["Jacking end"] not in JACKING_END_OPTIONS:
            errors.append(f"{tendon_id}: Jacking end must be Left, Right, or Both.")
        if row["Strands"] <= 0:
            errors.append(f"{tendon_id}: strand count must be positive.")
        if row["Strand system"] != DEFAULT_STRAND_SYSTEM:
            errors.append(
                f"{tendon_id}: Strand system must be {DEFAULT_STRAND_SYSTEM}."
            )
        if row["Aps/strand mm²"] <= 0.0:
            errors.append(f"{tendon_id}: Aps/strand must be positive.")
        if row["fpu MPa"] <= 0.0:
            errors.append(f"{tendon_id}: fpu must be positive.")
        if not (0.0 < row["fpj/fpu"] <= 1.0):
            errors.append(f"{tendon_id}: fpj/fpu must be greater than 0 and no greater than 1.0.")
    if rows and any(not row["Active"] for row in rows):
        warnings.append("Inactive tendons remain stored but receive no future PTQA active-tendon credit.")
    return rows, list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def _default_web_thickness(value: Any, width_mm: float) -> float:
    fallback = max(0.12 * float(width_mm), 1.0)
    thickness = _float(value, fallback)
    return min(max(thickness, 1.0), max(0.5 * float(width_mm), 1.0))


def _default_tendon_depths(height_mm: float, tendon_count_per_side: int) -> list[float]:
    count = max(_int(tendon_count_per_side, DEFAULT_WEB_TENDONS_PER_SIDE), 1)
    height = max(_float(height_mm, 1500.0), 1.0)
    top_depth = min(max(DEFAULT_TENDON_TOP_OFFSET_MM, 0.0), height)
    bottom_depth = min(max(height - DEFAULT_TENDON_BOTTOM_OFFSET_MM, 0.0), height)
    if bottom_depth <= top_depth:
        top_depth = height / float(count + 1)
        bottom_depth = height * float(count) / float(count + 1)
    if count == 1:
        return [round(0.5 * (top_depth + bottom_depth), 3)]
    step = (bottom_depth - top_depth) / float(count - 1)
    return [round(top_depth + index * step, 3) for index in range(count)]


def _web_tendon_coordinates(
    tendon_ids: list[str],
    *,
    width_mm: float,
    height_mm: float,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
) -> dict[str, tuple[float, float]]:
    if not tendon_ids:
        return {}
    width = max(_float(width_mm, 2500.0), 1.0)
    left_thickness = _default_web_thickness(t_left_mm, width)
    right_thickness = _default_web_thickness(t_right_mm, width)
    left_x = -0.5 * width + 0.5 * left_thickness
    right_x = 0.5 * width - 0.5 * right_thickness
    tendon_count_per_side = max((len(tendon_ids) + 1) // 2, 1)
    depths = _default_tendon_depths(height_mm, tendon_count_per_side)

    coordinates: dict[str, tuple[float, float]] = {}
    for index, tendon_id in enumerate(tendon_ids):
        if index < tendon_count_per_side:
            x_value = left_x
            depth_index = index
        else:
            x_value = right_x
            depth_index = index - tendon_count_per_side
        depth = depths[min(depth_index, len(depths) - 1)]
        coordinates[tendon_id] = (round(x_value, 3), depth)
    return coordinates


def normalize_tendon_profile_preset(value: Any) -> str:
    text = str(value or "").strip()
    if text in TENDON_PROFILE_PRESET_OPTIONS:
        return text
    aliases = {
        "straight": "Straight Tendon",
        "straight tendon": "Straight Tendon",
        "straight constant-depth": "Straight Tendon",
        "constant": "Straight Tendon",
        "line": "Straight Tendon",
        "linear": "Straight Tendon",
        "straight tendon 1": "Straight Tendon",
        "straight tendon 2": "Straight Tendon",
        "low": "Straight Tendon With Bends",
        "low point": "Straight Tendon With Bends",
        "bent": "Straight Tendon With Bends",
        "bend": "Straight Tendon With Bends",
        "straight low-point bend": "Straight Tendon With Bends",
        "straight low-zone bends": "Straight Tendon With Bends",
        "straight tendon with bends": "Straight Tendon With Bends",
        "straight tendon with bends 1": "Straight Tendon With Bends",
        "straight tendon with bends 2": "Straight Tendon With Bends",
        "straight tendon with bends 3": "Straight Tendon With Bends",
        "straight tendon with bends 4": "Straight Tendon With Bends",
        "parabolic": "Parabolic Tendon",
        "parabola": "Parabolic Tendon",
        "parabolic low-point": "Parabolic Tendon",
        "parabolic high-point": "Parabolic Tendon",
        "parabolic tendon 1": "Parabolic Tendon",
        "parabolic tendon 2": "Parabolic Tendon",
        "parabolic tendon 3": "Parabolic Tendon",
        "hog": "Parabolic Tendon",
        "high": "Parabolic Tendon",
        "multi": "Straight Tendon With Bends",
        "multiple": "Straight Tendon With Bends",
        "multi-span draped": "Straight Tendon With Bends",
    }
    return aliases.get(text.casefold(), DEFAULT_TENDON_PROFILE_PRESET)


def normalize_tendon_profile_span_mode(value: Any) -> str:
    text = str(value or "").strip()
    if text in TENDON_PROFILE_SPAN_MODE_OPTIONS:
        return text
    aliases = {
        "single": "Single Span",
        "single span": "Single Span",
        "1": "Single Span",
        "multiple": "2 Span",
        "multi": "2 Span",
        "multi span": "2 Span",
        "multiple span": "2 Span",
        "two span": "2 Span",
        "2 span": "2 Span",
        "2": "2 Span",
    }
    return aliases.get(text.casefold(), DEFAULT_TENDON_PROFILE_SPAN_MODE)


def _clip_depth(depth_mm: float, height_mm: float) -> float:
    height = max(_float(height_mm, 1500.0), 1.0)
    return round(min(max(_float(depth_mm, 0.0), 0.0), height), 3)


def _support_half_ratio(
    length_m: float,
    support_width_m: float,
    *,
    multiplier: float,
) -> float:
    length = max(_float(length_m, 20.0), 0.1)
    width = max(_float(support_width_m, DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M), 0.0)
    return min(max(multiplier * width / length, 0.0), 0.10)


def _renumber_shape(points: list[tuple[float, float, str]]) -> list[tuple[str, float, float, str]]:
    priority = {"Anchorage": 4, "High point": 3, "Low point": 3, "Deviator": 2, "Profile point": 1}
    merged: dict[float, tuple[float, str]] = {}
    for ratio, offset, role in points:
        key = round(min(max(_float(ratio, 0.0), 0.0), 1.0), 9)
        if key not in merged:
            merged[key] = (offset, role)
            continue
        existing_offset, existing_role = merged[key]
        if priority.get(role, 0) > priority.get(existing_role, 0):
            merged[key] = (offset, role)
        else:
            merged[key] = (min(existing_offset, offset), existing_role)
    return [
        (f"P{index + 1}", ratio, offset, role)
        for index, (ratio, (offset, role)) in enumerate(sorted(merged.items()))
    ]


def _parabolic_offset(local_ratio: float, offset: float) -> float:
    local = min(max(_float(local_ratio, 0.0), 0.0), 1.0)
    return offset * 4.0 * local * (1.0 - local)


def _parabolic_span_points(
    start_ratio: float,
    end_ratio: float,
    *,
    offset: float,
    start_role: str,
    end_role: str,
) -> list[tuple[float, float, str]]:
    points: list[tuple[float, float, str]] = []
    span = end_ratio - start_ratio
    for index in range(7):
        local = index / 6.0
        ratio = start_ratio + span * local
        if index == 0:
            role = start_role
        elif index == 6:
            role = end_role
        elif index == 3:
            role = "Low point"
        else:
            role = "Profile point"
        points.append((ratio, _parabolic_offset(local, offset), role))
    return points


def _two_span_parabolic_offset(ratio: float, offset: float) -> float:
    if ratio <= 0.5:
        return _parabolic_offset(ratio / 0.5, offset)
    return _parabolic_offset((ratio - 0.5) / 0.5, offset)


def _parabolic_crown_points(
    center_ratio: float,
    half_width_ratio: float,
    *,
    edge_offset: float,
) -> list[tuple[float, float, str]]:
    """Return an inverted support parabola with a smooth crown at center."""

    half_width = max(_float(half_width_ratio, 0.0), 0.0)
    if half_width <= 0.0:
        return [(center_ratio, 0.0, "High point")]
    points: list[tuple[float, float, str]] = []
    for step in (-1.0, -2.0 / 3.0, -1.0 / 3.0, 0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0):
        ratio = center_ratio + step * half_width
        role = "High point" if abs(step) < 1.0e-9 else "Profile point"
        points.append((ratio, edge_offset * step * step, role))
    return points


def _preset_shape(
    preset: str,
    *,
    span_mode: str = DEFAULT_TENDON_PROFILE_SPAN_MODE,
    bend_offset_mm: float,
    length_m: float = 20.0,
    support_width_m: float = DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M,
) -> list[tuple[str, float, float, str]]:
    """Return point-name, s/L, dtop-offset, and role tuples for a profile preset."""

    offset = max(_float(bend_offset_mm, 0.0), 0.0)
    length = max(_float(length_m, 20.0), 0.1)
    preset = normalize_tendon_profile_preset(preset)
    span_mode = normalize_tendon_profile_span_mode(span_mode)
    is_two_span = span_mode == "2 Span"
    if preset == "Straight Tendon":
        if is_two_span:
            return [
                ("P1", 0.0, 0.0, "Anchorage"),
                ("P2", 0.5, 0.0, "High point"),
                ("P3", 1.0, 0.0, "Anchorage"),
            ]
        return [
            ("P1", 0.0, 0.0, "Anchorage"),
            ("P2", 0.5, 0.0, "Profile point"),
            ("P3", 1.0, 0.0, "Anchorage"),
        ]
    if preset == "Straight Tendon With Bends":
        if is_two_span:
            half_support = _support_half_ratio(
                length,
                support_width_m,
                multiplier=0.5,
            )
            return _renumber_shape(
                [
                    (0.0, 0.0, "Anchorage"),
                    (0.125, offset, "Low point"),
                    (0.375, offset, "Low point"),
                    (0.5 - half_support, 0.0, "High point"),
                    (0.5, 0.0, "High point"),
                    (0.5 + half_support, 0.0, "High point"),
                    (0.625, offset, "Low point"),
                    (0.875, offset, "Low point"),
                    (1.0, 0.0, "Anchorage"),
                ]
            )
        return [
            ("P1", 0.0, 0.0, "Anchorage"),
            ("P2", 0.25, offset, "Low point"),
            ("P3", 0.75, offset, "Low point"),
            ("P4", 1.0, 0.0, "Anchorage"),
        ]
    if preset == "Parabolic Tendon":
        if is_two_span:
            points = [
                *_parabolic_span_points(
                    0.0,
                    0.5,
                    offset=offset,
                    start_role="Anchorage",
                    end_role="High point",
                ),
                *_parabolic_span_points(
                    0.5,
                    1.0,
                    offset=offset,
                    start_role="High point",
                    end_role="Anchorage",
                ),
            ]
            half_support = _support_half_ratio(
                length,
                support_width_m,
                multiplier=1.0,
            )
            crown_edge_offset = _two_span_parabolic_offset(0.5 - half_support, offset)
            points.extend(
                _parabolic_crown_points(
                    0.5,
                    half_support,
                    edge_offset=crown_edge_offset,
                )
            )
            return _renumber_shape(points)
        return _renumber_shape(
            _parabolic_span_points(
                0.0,
                1.0,
                offset=offset,
                start_role="Anchorage",
                end_role="Anchorage",
            )
        )
    return [
        ("P1", 0.0, 0.0, "Anchorage"),
        ("P2", 0.5, 0.0, "Profile point"),
        ("P3", 1.0, 0.0, "Anchorage"),
    ]


def tendon_profile_points_for_preset(
    length_m: float,
    *,
    tendon_ids: list[str],
    coordinate_tendon_ids: list[str] | None = None,
    width_mm: float,
    height_mm: float,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
    preset: str = DEFAULT_TENDON_PROFILE_PRESET,
    span_mode: str = DEFAULT_TENDON_PROFILE_SPAN_MODE,
    bend_offset_mm: float = 200.0,
    support_width_m: float = DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M,
) -> list[dict[str, Any]]:
    """Return web-centered control points for a selected tendon profile preset.

    Presets are geometry quick-starts only.  The returned rows remain ordinary
    ``s-x-dtop`` profile points so downstream interpolation, Project JSON, and
    review figures do not need a new schema or solver.
    """

    length = max(_float(length_m, 20.0), 0.1)
    height = max(_float(height_mm, 1500.0), 1.0)
    coordinate_ids = list(coordinate_tendon_ids or tendon_ids)
    coordinates = _web_tendon_coordinates(
        coordinate_ids,
        width_mm=max(_float(width_mm, 2500.0), 1.0),
        height_mm=height,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
    )
    shape = _preset_shape(
        preset,
        span_mode=span_mode,
        bend_offset_mm=bend_offset_mm,
        length_m=length,
        support_width_m=support_width_m,
    )
    rows: list[dict[str, Any]] = []
    for tendon_id in tendon_ids:
        lateral, base_depth = coordinates.get(tendon_id, (0.0, 0.5 * height))
        for point, ratio, depth_offset, role in shape:
            rows.append(
                {
                    "Tendon ID": tendon_id,
                    "Point": point,
                    "s/L": ratio,
                    "s (m)": round(ratio * length, 6),
                    "x lateral (mm)": round(lateral, 3),
                    "dtop (mm)": _clip_depth(base_depth + depth_offset, height),
                    "Curve role": role,
                }
            )
    return rows


def default_tendon_profile_points(
    length_m: float,
    *,
    tendon_ids: list[str],
    width_mm: float,
    height_mm: float,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
) -> list[dict[str, Any]]:
    """Return three constant-depth web-centered control points for each tendon."""

    return tendon_profile_points_for_preset(
        length_m,
        tendon_ids=tendon_ids,
        width_mm=width_mm,
        height_mm=height_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        preset=DEFAULT_TENDON_PROFILE_PRESET,
        span_mode=DEFAULT_TENDON_PROFILE_SPAN_MODE,
        bend_offset_mm=0.0,
    )


def profile_preset_point_count(
    preset: str,
    span_mode: str = DEFAULT_TENDON_PROFILE_SPAN_MODE,
    *,
    length_m: float = 20.0,
    support_width_m: float = DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M,
) -> int:
    return len(
        _preset_shape(
            preset,
            span_mode=span_mode,
            bend_offset_mm=1.0,
            length_m=length_m,
            support_width_m=support_width_m,
        )
    )


def tendon_profile_preset_shape_preview(
    preset: str,
    span_mode: str,
    *,
    length_m: float = 20.0,
    support_width_m: float = DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M,
) -> list[tuple[float, float, str]]:
    """Return normalized preview coordinates for quick-start diagrams."""

    return [
        (ratio, offset, role)
        for _point, ratio, offset, role in _preset_shape(
            preset,
            span_mode=span_mode,
            bend_offset_mm=1.0,
            length_m=length_m,
            support_width_m=support_width_m,
        )
    ]


def canonical_tendon_profile_points(values: Any, length_m: float) -> list[dict[str, Any]]:
    length = max(_float(length_m, 20.0), 0.1)
    rows: list[dict[str, Any]] = []
    for index, source in enumerate(_records(values)):
        ratio = _float(source.get("s/L"), 0.0)
        station = _float(source.get("s (m)", source.get("x_m")), ratio * length)
        ratio = station / length
        role = str(source.get("Curve role") or "Profile point").strip()
        if role not in PROFILE_ROLE_OPTIONS:
            role = "Profile point"
        rows.append(
            {
                "Tendon ID": str(source.get("Tendon ID") or "").strip(),
                "Point": str(source.get("Point") or f"P{index + 1}").strip(),
                "s/L": ratio,
                "s (m)": station,
                "x lateral (mm)": _float(source.get("x lateral (mm)"), 0.0),
                "dtop (mm)": _float(
                    source.get("dtop (mm)", source.get("Depth from top mm")),
                    0.0,
                ),
                "Curve role": role,
            }
        )
    rows.sort(key=lambda row: (row["Tendon ID"], row["s (m)"], row["Point"]))
    return rows


def tendon_profile_import_schema_rows() -> list[dict[str, Any]]:
    """Return the public tendon-profile import contract for UI display."""

    return [dict(row) for row in TENDON_PROFILE_IMPORT_SCHEMA]


def tendon_profile_import_template_rows(
    profile_values: Any,
    *,
    length_m: float,
) -> list[dict[str, Any]]:
    """Return current profile rows in the exact import-template column order."""

    return [
        {column: row[column] for column in TENDON_PROFILE_IMPORT_REQUIRED_COLUMNS}
        for row in canonical_tendon_profile_points(profile_values, length_m)
    ]


def _import_column_token(value: Any) -> str:
    return "".join(
        character
        for character in str(value or "").strip().casefold()
        if character.isalnum()
    )


def _import_column_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    columns = list(dict.fromkeys(key for row in rows for key in row))
    aliases = {
        _import_column_token(column): column
        for column in TENDON_PROFILE_IMPORT_REQUIRED_COLUMNS
    }
    aliases.update(_TENDON_PROFILE_IMPORT_COLUMN_ALIASES)
    mapped: dict[str, str] = {}
    for column in columns:
        canonical = aliases.get(_import_column_token(column))
        if canonical in TENDON_PROFILE_IMPORT_REQUIRED_COLUMNS and canonical not in mapped:
            mapped[canonical] = column
    return mapped


def _import_value_is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and not isfinite(value):
        return True
    return not str(value).strip()


def _import_text(value: Any) -> str:
    if _import_value_is_blank(value):
        return ""
    return str(value).strip()


def _import_required_float(
    value: Any,
    *,
    column: str,
    row_number: int,
    errors: list[str],
) -> float | None:
    if _import_value_is_blank(value):
        errors.append(f"Row {row_number}: {column} is required.")
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"Row {row_number}: {column} must be numeric.")
        return None
    if not isfinite(number):
        errors.append(f"Row {row_number}: {column} must be finite.")
        return None
    return number


def normalize_tendon_profile_import_rows(
    import_values: Any,
    system_values: Any,
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Preview-normalize imported tendon profile rows without mutating state.

    The returned rows are canonical and validated against the live Tendon
    System, Segment Layout, and Section Builder context.  Callers decide whether
    an explicit guarded apply/writeback action is available.
    """

    raw_rows = _records(import_values)
    if not raw_rows:
        return [], ["Import file contains no tendon profile rows."], []

    column_map = _import_column_map(raw_rows)
    missing = [
        column
        for column in TENDON_PROFILE_IMPORT_REQUIRED_COLUMNS
        if column not in column_map
    ]
    if missing:
        return [], ["Import file is missing required column(s): " + ", ".join(missing) + "."], []

    cleaned: list[dict[str, Any]] = []
    row_errors: list[str] = []
    for row_number, source in enumerate(raw_rows, start=2):
        if all(
            _import_value_is_blank(source.get(column_map[column]))
            for column in TENDON_PROFILE_IMPORT_REQUIRED_COLUMNS
        ):
            continue

        tendon_id = _import_text(source.get(column_map["Tendon ID"]))
        point = _import_text(source.get(column_map["Point"]))
        role = _import_text(source.get(column_map["Curve role"]))
        if not tendon_id:
            row_errors.append(f"Row {row_number}: Tendon ID is required.")
        if not point:
            row_errors.append(f"Row {row_number}: Point is required.")
        if not role:
            row_errors.append(f"Row {row_number}: Curve role is required.")
        elif role not in PROFILE_ROLE_OPTIONS:
            row_errors.append(
                f"Row {row_number}: Curve role must be one of "
                + ", ".join(PROFILE_ROLE_OPTIONS)
                + "."
            )

        station = _import_required_float(
            source.get(column_map["s (m)"]),
            column="s (m)",
            row_number=row_number,
            errors=row_errors,
        )
        lateral = _import_required_float(
            source.get(column_map["x lateral (mm)"]),
            column="x lateral (mm)",
            row_number=row_number,
            errors=row_errors,
        )
        depth = _import_required_float(
            source.get(column_map["dtop (mm)"]),
            column="dtop (mm)",
            row_number=row_number,
            errors=row_errors,
        )
        if tendon_id and point and role in PROFILE_ROLE_OPTIONS and station is not None and lateral is not None and depth is not None:
            cleaned.append(
                {
                    "Tendon ID": tendon_id,
                    "Point": point,
                    "s (m)": station,
                    "x lateral (mm)": lateral,
                    "dtop (mm)": depth,
                    "Curve role": role,
                }
            )

    normalized = canonical_tendon_profile_points(cleaned, length_m)
    if row_errors:
        return normalized, list(dict.fromkeys(row_errors)), []
    if not normalized:
        return [], ["Import file contains no usable tendon profile rows."], []
    return validate_tendon_profile(
        normalized,
        system_values,
        length_m=length_m,
        segment_rows=segment_rows,
        section_definitions=section_definitions,
    )


def _profile_import_row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("Tendon ID") or ""), str(row.get("Point") or ""))


def _profile_import_row_signature(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row.get("Tendon ID") or ""),
        str(row.get("Point") or ""),
        round(_float(row.get("s (m)"), 0.0), 6),
        round(_float(row.get("x lateral (mm)"), 0.0), 3),
        round(_float(row.get("dtop (mm)"), 0.0), 3),
        str(row.get("Curve role") or ""),
    )


def _profile_import_diff_record(
    change: str,
    *,
    current: Mapping[str, Any] | None = None,
    imported: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    basis = imported if imported is not None else current or {}

    def _value(row: Mapping[str, Any] | None, column: str) -> Any:
        return None if row is None else row.get(column)

    return {
        "Change": change,
        "Tendon ID": str(basis.get("Tendon ID") or ""),
        "Point": str(basis.get("Point") or ""),
        "Current s (m)": _value(current, "s (m)"),
        "Import s (m)": _value(imported, "s (m)"),
        "Current x (mm)": _value(current, "x lateral (mm)"),
        "Import x (mm)": _value(imported, "x lateral (mm)"),
        "Current dtop (mm)": _value(current, "dtop (mm)"),
        "Import dtop (mm)": _value(imported, "dtop (mm)"),
        "Current role": _value(current, "Curve role"),
        "Import role": _value(imported, "Curve role"),
    }


def tendon_profile_import_diff_rows(
    current_values: Any,
    import_values: Any,
    *,
    length_m: float,
) -> list[dict[str, Any]]:
    """Return row-level import differences for preview and audit tables."""

    current = canonical_tendon_profile_points(current_values, length_m)
    imported = canonical_tendon_profile_points(import_values, length_m)
    current_keys = [_profile_import_row_key(row) for row in current]
    imported_keys = [_profile_import_row_key(row) for row in imported]
    duplicate_keys = (
        len(current_keys) != len(set(current_keys))
        or len(imported_keys) != len(set(imported_keys))
    )

    if duplicate_keys:
        current_remaining = list(current)
        imported_remaining = list(imported)
        for signature in {
            _profile_import_row_signature(row)
            for row in current_remaining
        } & {
            _profile_import_row_signature(row)
            for row in imported_remaining
        }:
            current_matches = [
                row
                for row in current_remaining
                if _profile_import_row_signature(row) == signature
            ]
            imported_matches = [
                row
                for row in imported_remaining
                if _profile_import_row_signature(row) == signature
            ]
            match_count = min(len(current_matches), len(imported_matches))
            for _index in range(match_count):
                current_remaining.remove(current_matches[_index])
                imported_remaining.remove(imported_matches[_index])

        rows = [
            _profile_import_diff_record("Added", imported=row)
            for row in imported_remaining
        ]
        rows.extend(
            _profile_import_diff_record("Removed", current=row)
            for row in current_remaining
        )
        return sorted(
            rows,
            key=lambda row: (
                str(row.get("Tendon ID") or ""),
                str(row.get("Point") or ""),
                str(row.get("Change") or ""),
            ),
        )

    current_by_key = {_profile_import_row_key(row): row for row in current}
    imported_by_key = {_profile_import_row_key(row): row for row in imported}
    current_key_set = set(current_by_key)
    imported_key_set = set(imported_by_key)
    added_keys = imported_key_set - current_key_set
    removed_keys = current_key_set - imported_key_set
    shared_keys = current_key_set & imported_key_set
    changed_keys = {
        key
        for key in shared_keys
        if _profile_import_row_signature(current_by_key[key])
        != _profile_import_row_signature(imported_by_key[key])
    }

    rows: list[dict[str, Any]] = []
    for key in sorted(changed_keys):
        rows.append(
            _profile_import_diff_record(
                "Changed",
                current=current_by_key[key],
                imported=imported_by_key[key],
            )
        )
    for key in sorted(added_keys):
        rows.append(_profile_import_diff_record("Added", imported=imported_by_key[key]))
    for key in sorted(removed_keys):
        rows.append(_profile_import_diff_record("Removed", current=current_by_key[key]))
    return rows


def tendon_profile_import_change_summary(
    current_values: Any,
    import_values: Any,
    *,
    length_m: float,
) -> dict[str, Any]:
    """Return compact row-diff counts for a validated import preview."""

    current = canonical_tendon_profile_points(current_values, length_m)
    imported = canonical_tendon_profile_points(import_values, length_m)
    current_keys = [_profile_import_row_key(row) for row in current]
    imported_keys = [_profile_import_row_key(row) for row in imported]
    duplicate_keys = (
        len(current_keys) != len(set(current_keys))
        or len(imported_keys) != len(set(imported_keys))
    )
    if duplicate_keys:
        current_signatures = [_profile_import_row_signature(row) for row in current]
        imported_signatures = [_profile_import_row_signature(row) for row in imported]
        unchanged = sum(
            min(current_signatures.count(signature), imported_signatures.count(signature))
            for signature in set(current_signatures) | set(imported_signatures)
        )
        added = max(len(imported) - unchanged, 0)
        removed = max(len(current) - unchanged, 0)
        changed = 0
        affected = {
            signature[0]
            for signature in set(current_signatures).symmetric_difference(set(imported_signatures))
            if signature[0]
        }
        return {
            "current_rows": len(current),
            "imported_rows": len(imported),
            "added_rows": added,
            "removed_rows": removed,
            "changed_rows": changed,
            "unchanged_rows": unchanged,
            "affected_tendons": len(affected),
            "key_mode": "signature",
        }

    current_by_key = {
        _profile_import_row_key(row): _profile_import_row_signature(row)
        for row in current
    }
    imported_by_key = {
        _profile_import_row_key(row): _profile_import_row_signature(row)
        for row in imported
    }
    current_key_set = set(current_by_key)
    imported_key_set = set(imported_by_key)
    added_keys = imported_key_set - current_key_set
    removed_keys = current_key_set - imported_key_set
    shared_keys = current_key_set & imported_key_set
    changed_keys = {
        key
        for key in shared_keys
        if current_by_key[key] != imported_by_key[key]
    }
    unchanged_keys = shared_keys - changed_keys
    affected = {
        key[0]
        for key in added_keys | removed_keys | changed_keys
        if key[0]
    }
    return {
        "current_rows": len(current),
        "imported_rows": len(imported),
        "added_rows": len(added_keys),
        "removed_rows": len(removed_keys),
        "changed_rows": len(changed_keys),
        "unchanged_rows": len(unchanged_keys),
        "affected_tendons": len(affected),
        "key_mode": "tendon-point",
    }


def tendon_positions_at_station(
    profile_values: Any,
    system_values: Any,
    *,
    station_m: float,
    length_m: float,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    """Interpolate the shared s-x-dtop source at one review station.

    PT1 uses piecewise-linear display segments between engineer-entered profile
    points.  This helper feeds Cross Section and 3D review only; it is not a
    tendon-curvature, friction, loss, or force solver.
    """

    length = max(_float(length_m, 20.0), 0.1)
    station = min(max(_float(station_m, 0.0), 0.0), length)
    system = canonical_tendon_system_rows(system_values)
    by_id: dict[str, list[dict[str, Any]]] = {}
    for point in canonical_tendon_profile_points(profile_values, length):
        by_id.setdefault(point["Tendon ID"], []).append(point)

    positions: list[dict[str, Any]] = []
    tolerance = max(1.0e-9, length * 1.0e-9)
    for tendon in system:
        tendon_id = tendon["Tendon ID"]
        if not tendon_id or (active_only and not tendon["Active"]):
            continue
        points = sorted(by_id.get(tendon_id, []), key=lambda row: row["s (m)"])
        if not points or station < points[0]["s (m)"] - tolerance or station > points[-1]["s (m)"] + tolerance:
            continue

        left = points[0]
        right = points[-1]
        for point in points:
            if abs(point["s (m)"] - station) <= tolerance:
                left = right = point
                break
        else:
            for first, second in zip(points, points[1:]):
                if first["s (m)"] <= station <= second["s (m)"]:
                    left, right = first, second
                    break

        span = right["s (m)"] - left["s (m)"]
        ratio = 0.0 if abs(span) <= tolerance else (station - left["s (m)"]) / span
        lateral = left["x lateral (mm)"] + ratio * (
            right["x lateral (mm)"] - left["x lateral (mm)"]
        )
        depth = left["dtop (mm)"] + ratio * (
            right["dtop (mm)"] - left["dtop (mm)"]
        )
        positions.append(
            {
                "Tendon ID": tendon_id,
                "Active": bool(tendon["Active"]),
                "Type": tendon["Type"],
                "s (m)": station,
                "s/L": station / length,
                "x lateral (mm)": lateral,
                "dtop (mm)": depth,
                "Left point": left["Point"],
                "Right point": right["Point"],
                "Interpolation": "Profile point" if left is right else "Piecewise linear",
            }
        )
    return positions


def section_context_records(definitions: Any) -> dict[str, dict[str, Any]]:
    """Return dimension/property context keyed by project Section ID."""

    records = section_property_records(canonical_section_definitions(definitions))
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        params = record.get("Parameters") if isinstance(record.get("Parameters"), Mapping) else {}
        height = _float(params.get("height_mm"), 0.0)
        width = _float(params.get("width_mm"), 0.0)
        centroid = _float(record.get("Centroid from top mm"), 0.5 * height)
        result[str(record.get("Section ID") or "")] = {
            "Section ID": str(record.get("Section ID") or ""),
            "Section name": str(record.get("Section name") or ""),
            "Section role": str(record.get("Section role") or ""),
            "Width mm": width,
            "Height mm": height,
            "Centroid from top mm": centroid,
            "Status": str(record.get("Status") or "NOT READY"),
        }
    return result


def station_section_contexts(
    station_m: float,
    segment_rows: Any,
    definitions: Any,
    *,
    length_m: float,
) -> list[dict[str, Any]]:
    """Return every section face applicable at a station.

    At an internal segment joint both adjacent Section IDs are returned so a
    tendon point does not silently use only one side's centroid.
    """

    station = _float(station_m, 0.0)
    length = max(_float(length_m, 20.0), 0.1)
    tolerance = max(1.0e-6, length * 1.0e-8)
    by_section = section_context_records(definitions)
    contexts: list[dict[str, Any]] = []
    segments = sorted(
        _records(segment_rows),
        key=lambda row: _float(row.get("x_start_m", row.get("s_start (m)")), 0.0),
    )
    for segment in segments:
        start = _float(segment.get("x_start_m", segment.get("s_start (m)")), 0.0)
        end = _float(segment.get("x_end_m", segment.get("s_end (m)")), 0.0)
        if station < start - tolerance or station > end + tolerance:
            continue
        section_id = str(segment.get("Section ID") or "").strip()
        context = dict(by_section.get(section_id, {}))
        context.update(
            {
                "Segment": str(segment.get("Segment") or ""),
                "Section ID": section_id,
                "s_start_m": start,
                "s_end_m": end,
                "Station face": (
                    "Left end"
                    if abs(station - start) <= tolerance
                    else "Right end"
                    if abs(station - end) <= tolerance
                    else "Within segment"
                ),
            }
        )
        contexts.append(context)
    return contexts


def validate_tendon_profile(
    profile_values: Any,
    system_values: Any,
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    points = canonical_tendon_profile_points(profile_values, length_m)
    system = canonical_tendon_system_rows(system_values)
    system_by_id = {row["Tendon ID"]: row for row in system if row["Tendon ID"]}
    active_ids = [row["Tendon ID"] for row in system if row["Tendon ID"] and row["Active"]]
    errors: list[str] = []
    warnings: list[str] = []
    by_id: dict[str, list[dict[str, Any]]] = {tendon_id: [] for tendon_id in system_by_id}
    length = max(_float(length_m, 20.0), 0.1)
    tolerance = max(1.0e-6, length * 1.0e-6)

    for point in points:
        tendon_id = point["Tendon ID"]
        if tendon_id not in system_by_id:
            errors.append(f"Profile point references unknown Tendon ID '{tendon_id or '(blank)'}'.")
            continue
        by_id[tendon_id].append(point)
        station = point["s (m)"]
        if not (0.0 <= station <= length):
            errors.append(f"{tendon_id} {point['Point']}: station s must lie between 0 and L.")
            continue
        contexts = station_section_contexts(
            station,
            segment_rows,
            section_definitions,
            length_m=length,
        )
        if not contexts:
            errors.append(f"{tendon_id} {point['Point']}: station s has no assigned Segment/Section ID.")
            continue
        if system_by_id[tendon_id]["Type"] == "Internal":
            for context in contexts:
                width = _float(context.get("Width mm"), 0.0)
                height = _float(context.get("Height mm"), 0.0)
                section_id = str(context.get("Section ID") or "(missing section)")
                if width <= 0.0 or height <= 0.0:
                    errors.append(
                        f"{tendon_id} {point['Point']}: Section ID {section_id} has no valid width/depth context."
                    )
                    continue
                if abs(point["x lateral (mm)"]) > 0.5 * width + 1.0e-9:
                    errors.append(
                        f"{tendon_id} {point['Point']}: lateral x lies outside Section ID {section_id}."
                    )
                if not (0.0 <= point["dtop (mm)"] <= height):
                    errors.append(
                        f"{tendon_id} {point['Point']}: dtop lies outside Section ID {section_id}."
                    )

    for tendon_id in active_ids:
        tendon_points = sorted(by_id.get(tendon_id, []), key=lambda row: row["s (m)"])
        if len(tendon_points) < 2:
            errors.append(f"{tendon_id}: at least two geometry points are required.")
            continue
        stations = [round(point["s (m)"], 9) for point in tendon_points]
        if len(stations) != len(set(stations)):
            errors.append(f"{tendon_id}: duplicate profile stations are not allowed.")
        if abs(tendon_points[0]["s (m)"]) > tolerance:
            errors.append(f"{tendon_id}: first point must be at the left anchorage s = 0.")
        if abs(tendon_points[-1]["s (m)"] - length) > tolerance:
            errors.append(f"{tendon_id}: final point must be at the right anchorage s = L.")
        if tendon_points[0]["Curve role"] != "Anchorage" or tendon_points[-1]["Curve role"] != "Anchorage":
            warnings.append(f"{tendon_id}: end profile points should use Curve role = Anchorage.")

    return points, list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def tendon_station_audit_rows(
    profile_values: Any,
    system_values: Any,
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
) -> list[dict[str, Any]]:
    """Return section-aware audit rows; joint points expand to both faces."""

    points = canonical_tendon_profile_points(profile_values, length_m)
    system = {
        row["Tendon ID"]: row
        for row in canonical_tendon_system_rows(system_values)
        if row["Tendon ID"]
    }
    rows: list[dict[str, Any]] = []
    for point in points:
        tendon = system.get(point["Tendon ID"], {})
        contexts = station_section_contexts(
            point["s (m)"],
            segment_rows,
            section_definitions,
            length_m=length_m,
        ) or [{}]
        for context in contexts:
            centroid = _float(context.get("Centroid from top mm"), 0.0)
            strands = _int(tendon.get("Strands"), DEFAULT_STRANDS_PER_TENDON)
            aps = _float(tendon.get("Aps/strand mm²"), DEFAULT_STRAND_APS_MM2)
            fpu = _float(tendon.get("fpu MPa"), DEFAULT_STRAND_FPU_MPA)
            ratio = _float(tendon.get("fpj/fpu"), DEFAULT_FPJ_RATIO)
            rows.append(
                {
                    "Tendon ID": point["Tendon ID"],
                    "Active": bool(tendon.get("Active", True)),
                    "Point": point["Point"],
                    "s/L": point["s/L"],
                    "s (m)": point["s (m)"],
                    "Segment": str(context.get("Segment") or ""),
                    "Section ID": str(context.get("Section ID") or ""),
                    "Station face": str(context.get("Station face") or ""),
                    "x (mm)": point["x lateral (mm)"],
                    "dtop (mm)": point["dtop (mm)"],
                    "centroid from top (mm)": centroid,
                    "e(s) (mm)": point["dtop (mm)"] - centroid,
                    "Type": str(tendon.get("Type") or DEFAULT_TENDON_TYPE),
                    "Jacking end": str(tendon.get("Jacking end") or DEFAULT_JACKING_END),
                    "fpj (MPa)": calculated_fpj_mpa(fpu, ratio),
                    "Aps total (mm²)": strands * aps,
                }
            )
    return rows


def segment_joint_stations(segment_rows: Any, *, length_m: float) -> list[float]:
    """Return unique internal segment-joint stations for continuity review."""

    length = max(_float(length_m, 20.0), 0.1)
    tolerance = max(1.0e-6, length * 1.0e-8)
    stations: set[float] = set()
    for segment in _records(segment_rows):
        for key in ("x_start_m", "x_end_m", "s_start (m)", "s_end (m)"):
            if key not in segment:
                continue
            station = _float(segment.get(key), 0.0)
            if tolerance < station < length - tolerance:
                stations.add(round(station, 6))
    return sorted(stations)


def _definition_by_section_id(section_definitions: Any) -> dict[str, dict[str, Any]]:
    return {
        str(definition.get("Section ID") or ""): definition
        for definition in canonical_section_definitions(section_definitions)
    }


def _continuity_fit_status(
    position: Mapping[str, Any],
    tendon: Mapping[str, Any],
    context: Mapping[str, Any],
    definitions: Mapping[str, Mapping[str, Any]],
) -> tuple[str, str]:
    tendon_type = str(tendon.get("Type") or DEFAULT_TENDON_TYPE)
    if tendon_type == "External":
        return "EXTERNAL - LOCATION SHOWN", ""

    section_id = str(context.get("Section ID") or "")
    definition = definitions.get(section_id)
    if not definition:
        return "SECTION MISSING", f"Section ID {section_id or '(blank)'} is not defined."
    try:
        concrete = to_shapely_polygon(build_geometry_for_definition(definition))
    except Exception as exc:
        return "SECTION REVIEW", f"Section ID {section_id} geometry could not be built: {exc}"

    _min_x, _min_y, _max_x, top_y = concrete.bounds
    x_mm = _float(position.get("x lateral (mm)"), 0.0)
    section_y = top_y - _float(position.get("dtop (mm)"), 0.0)
    if concrete.covers(Point(x_mm, section_y)):
        return "IN CONCRETE", ""
    return "OUTSIDE / VOID - REVIEW", "Internal tendon center is outside concrete or inside a void."


def tendon_continuity_audit_rows(
    profile_values: Any,
    system_values: Any,
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
) -> list[dict[str, Any]]:
    """Return segment-joint PT geometry continuity rows.

    This is a geometry/input audit only.  It verifies that active tendons have
    interpolated s-x-dtop positions, positive tendon material/stressing source,
    and acceptable internal-tendon fit at every internal segment joint face.
    """

    length = max(_float(length_m, 20.0), 0.1)
    system = canonical_tendon_system_rows(system_values)
    active = [row for row in system if row["Tendon ID"] and row["Active"]]
    definitions = _definition_by_section_id(section_definitions)
    joints = segment_joint_stations(segment_rows, length_m=length)
    rows: list[dict[str, Any]] = []
    for station in joints:
        contexts = station_section_contexts(
            station,
            segment_rows,
            section_definitions,
            length_m=length,
        )
        positions = {
            row["Tendon ID"]: row
            for row in tendon_positions_at_station(
                profile_values,
                system,
                station_m=station,
                length_m=length,
                active_only=False,
            )
        }
        for tendon in active:
            tendon_id = tendon["Tendon ID"]
            position = positions.get(tendon_id)
            strands = _int(tendon.get("Strands"), DEFAULT_STRANDS_PER_TENDON)
            aps = _float(tendon.get("Aps/strand mm²"), DEFAULT_STRAND_APS_MM2)
            fpu = _float(tendon.get("fpu MPa"), DEFAULT_STRAND_FPU_MPA)
            ratio = _float(tendon.get("fpj/fpu"), DEFAULT_FPJ_RATIO)
            aps_total = strands * aps
            fpj = calculated_fpj_mpa(fpu, ratio)
            source_issues: list[str] = []
            if aps_total <= 0.0:
                source_issues.append("Aps total is not positive.")
            if fpj <= 0.0:
                source_issues.append("fpj is not positive.")
            if position is None:
                rows.append(
                    {
                        "Joint s (m)": station,
                        "Segment": "",
                        "Section ID": "",
                        "Station face": "",
                        "Tendon ID": tendon_id,
                        "Type": tendon["Type"],
                        "x (mm)": None,
                        "dtop (mm)": None,
                        "Fit": "MISSING PROFILE",
                        "Aps total (mm²)": aps_total,
                        "fpj (MPa)": fpj,
                        "Continuity status": "REVIEW REQUIRED",
                        "Issue": "No tendon profile segment covers this joint station.",
                    }
                )
                continue
            for context in contexts or [{}]:
                fit, fit_issue = _continuity_fit_status(position, tendon, context, definitions)
                issues = [issue for issue in [fit_issue, *source_issues] if issue]
                rows.append(
                    {
                        "Joint s (m)": station,
                        "Segment": str(context.get("Segment") or ""),
                        "Section ID": str(context.get("Section ID") or ""),
                        "Station face": str(context.get("Station face") or ""),
                        "Tendon ID": tendon_id,
                        "Type": tendon["Type"],
                        "x (mm)": position["x lateral (mm)"],
                        "dtop (mm)": position["dtop (mm)"],
                        "Fit": fit,
                        "Aps total (mm²)": aps_total,
                        "fpj (MPa)": fpj,
                        "Continuity status": "PASS" if not issues else "REVIEW REQUIRED",
                        "Issue": "OK" if not issues else " ".join(issues),
                    }
                )
    return rows


def tendon_continuity_summary(
    continuity_rows: Any,
    *,
    profile_errors: list[str] | None = None,
    profile_warnings: list[str] | None = None,
) -> dict[str, Any]:
    rows = _records(continuity_rows)
    errors = list(profile_errors or [])
    warnings = list(profile_warnings or [])
    issue_rows = [
        row
        for row in rows
        if str(row.get("Continuity status") or "").upper() != "PASS"
    ]
    joint_count = len({round(_float(row.get("Joint s (m)"), 0.0), 6) for row in rows})
    tendon_count = len({str(row.get("Tendon ID") or "") for row in rows if row.get("Tendon ID")})
    issue_count = len(issue_rows) + len(errors)

    if issue_count:
        return {
            "value": "REVIEW REQUIRED",
            "detail": f"{issue_count} issue(s) across {joint_count} joint(s)",
            "status": "warning",
            "issue_count": issue_count,
            "joint_count": joint_count,
            "tendon_count": tendon_count,
        }
    if not rows:
        return {
            "value": "NO JOINTS",
            "detail": "0 internal segment joint(s) to check",
            "status": "neutral",
            "issue_count": 0,
            "joint_count": 0,
            "tendon_count": tendon_count,
        }
    return {
        "value": "GEOMETRY VERIFIED",
        "detail": f"{tendon_count} tendon(s) across {joint_count} joint(s)"
        + (f" - {len(warnings)} note(s)" if warnings else ""),
        "status": "ready",
        "issue_count": 0,
        "joint_count": joint_count,
        "tendon_count": tendon_count,
    }
