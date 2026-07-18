"""Solver-neutral tendon input model for Portal Frame Crossbeams.

``CROSSBEAM.PT1`` promotes the accepted UI1 tendon tables into one canonical
source of truth shared by Tendon System, Tendon Profile, Project JSON, and the
station audit.  It deliberately performs no loss, stress, strength, joint, or
anchorage-zone calculation.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.section_library import (
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


def _preset_shape(
    preset: str,
    *,
    span_mode: str = DEFAULT_TENDON_PROFILE_SPAN_MODE,
    bend_offset_mm: float,
) -> list[tuple[str, float, float, str]]:
    """Return point-name, s/L, dtop-offset, and role tuples for a profile preset."""

    offset = max(_float(bend_offset_mm, 0.0), 0.0)
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
            return [
                ("P1", 0.0, 0.0, "Anchorage"),
                ("P2", 0.125, offset, "Low point"),
                ("P3", 0.375, offset, "Low point"),
                ("P4", 0.5, 0.0, "High point"),
                ("P5", 0.625, offset, "Low point"),
                ("P6", 0.875, offset, "Low point"),
                ("P7", 1.0, 0.0, "Anchorage"),
            ]
        return [
            ("P1", 0.0, 0.0, "Anchorage"),
            ("P2", 0.25, offset, "Low point"),
            ("P3", 0.75, offset, "Low point"),
            ("P4", 1.0, 0.0, "Anchorage"),
        ]
    if preset == "Parabolic Tendon":
        if is_two_span:
            return [
                ("P1", 0.0, 0.0, "Anchorage"),
                ("P2", 0.125, 0.75 * offset, "Profile point"),
                ("P3", 0.25, offset, "Low point"),
                ("P4", 0.375, 0.75 * offset, "Profile point"),
                ("P5", 0.5, 0.0, "High point"),
                ("P6", 0.625, 0.75 * offset, "Profile point"),
                ("P7", 0.75, offset, "Low point"),
                ("P8", 0.875, 0.75 * offset, "Profile point"),
                ("P9", 1.0, 0.0, "Anchorage"),
            ]
        return [
            ("P1", 0.0, 0.0, "Anchorage"),
            ("P2", 0.25, 0.75 * offset, "Profile point"),
            ("P3", 0.5, offset, "Low point"),
            ("P4", 0.75, 0.75 * offset, "Profile point"),
            ("P5", 1.0, 0.0, "Anchorage"),
        ]
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
) -> int:
    return len(_preset_shape(preset, span_mode=span_mode, bend_offset_mm=1.0))


def tendon_profile_preset_shape_preview(
    preset: str,
    span_mode: str,
) -> list[tuple[float, float, str]]:
    """Return normalized preview coordinates for quick-start diagrams."""

    return [
        (ratio, offset, role)
        for _point, ratio, offset, role in _preset_shape(
            preset,
            span_mode=span_mode,
            bend_offset_mm=1.0,
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
