"""Crossbeam-only transverse/shear reinforcement input and preview foundation.

CROSSBEAM.TR1 adds segment/zone-local transverse reinforcement templates for
Portal Frame Crossbeams.  The model is deliberately separate from the generic
Beam/Girder stirrup workflow because Crossbeam hollow sections may require
independent left/right web legs, while solid CIP regions may use multi-leg
closed ties.  This module does not calculate shear capacity and does not give
segment-joint shear-transfer credit.

CROSSBEAM.RB2G adds solver-neutral centerline geometry for combined section
review: 25 mm preview bends, bottom-fillet-following Solid ties, rectangular
Hollow web cages, and conservative longitudinal-bar containment checks.
CROSSBEAM.RB2G1 adds cage-relative placement so web/corner longitudinal bars
sit exactly one transverse-plus-longitudinal radius sum inside the actual path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import cos, isfinite, pi, sin
from typing import Any

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points

TR_HOLLOW_MIN = "TR-HOLLOW-MIN"
TR_HOLLOW_END = "TR-HOLLOW-END"
TR_SOLID_COLUMN = "TR-SOLID-COLUMN"
TR_SOLID_ANCHORAGE = "TR-SOLID-ANCHORAGE"

TRANSVERSE_ROLE_OPTIONS = ("Hollow", "Solid", "Any")
TRANSVERSE_CONSTRUCTION_OPTIONS = ("Factory precast", "Cast in place", "Project-defined")
TRANSVERSE_BAR_SIZE_OPTIONS = ("DB10", "DB12", "DB16", "DB20", "DB25")
TRANSVERSE_MATERIAL_OPTIONS = ("SD40", "SD50")
TRANSVERSE_FY_OPTIONS = (390.0, 490.0)
TRANSVERSE_FY_BY_MATERIAL = {"SD40": 390.0, "SD50": 490.0}
TRANSVERSE_MATERIAL_BY_FY = {390.0: "SD40", 490.0: "SD50"}
TRANSVERSE_DIAMETER_BY_SIZE = {
    "DB10": 10.0,
    "DB12": 12.0,
    "DB16": 16.0,
    "DB20": 20.0,
    "DB25": 25.0,
}

TRANSVERSE_PREVIEW_BEND_RADIUS_MM = 25.0


@dataclass(frozen=True)
class TransverseCagePath:
    """One closed transverse centerline used by the Crossbeam previews."""

    label: str
    points: tuple[tuple[float, float], ...]
    envelope: tuple[float, float, float, float]
    effective_legs: int


@dataclass(frozen=True)
class TransverseCageGeometry:
    """Preview-only cage geometry and conservative detailing diagnostics."""

    role: str
    center_offset_mm: float
    bend_radius_mm: float
    bar_diameter_mm: float
    paths: tuple[TransverseCagePath, ...]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return bool(self.paths) and not self.errors


@dataclass(frozen=True)
class LongitudinalContainmentReview:
    """Check that generated longitudinal bar circles fit inside a cage."""

    status: str
    checked_bars: int
    conflict_count: int
    messages: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.status == "READY FOR DETAILING REVIEW"


@dataclass(frozen=True)
class CageRelativeLongitudinalPlacement:
    """Preview bars placed directly behind their active transverse cage."""

    rebars: tuple[Any, ...]
    adjusted_count: int
    cage_associated_count: int


def _float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if isfinite(result) else float(default)


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    return bool(value)


def transverse_bar_diameter_mm(bar_size: Any, default: float = 12.0) -> float:
    return float(TRANSVERSE_DIAMETER_BY_SIZE.get(str(bar_size or "").strip().upper(), default))


def transverse_bar_area_mm2(bar_size: Any) -> float:
    diameter = transverse_bar_diameter_mm(bar_size)
    return pi * diameter * diameter / 4.0


def _template_defaults(role: str, template_id: str) -> dict[str, Any]:
    role_text = str(role or "Any").strip().title()
    end_zone = str(template_id) in {TR_HOLLOW_END, TR_SOLID_ANCHORAGE}
    solid_column = str(template_id) == TR_SOLID_COLUMN
    return {
        "Rebar material": "SD40",
        "fy MPa": 390.0,
        "Bar size": "DB16" if role_text == "Solid" else "DB12",
        "Spacing mm": 100.0 if end_zone or solid_column else 200.0,
        "Left web legs": 2,
        "Right web legs": 2,
        "Effective legs": 6 if solid_column else (8 if end_zone and role_text == "Solid" else 4),
        "Closed cage": True,
        "Center offset mm": 50.0,
        "First bar offset mm": 75.0,
        "Last bar offset mm": 75.0,
    }


def default_crossbeam_transverse_templates() -> list[dict[str, Any]]:
    rows = [
        {
            "Active": True,
            "Template ID": TR_HOLLOW_MIN,
            "Template name": "Factory-cast hollow segment minimum shear reinforcement",
            "Applicable role": "Hollow",
            "Construction": "Factory precast",
            "Credit inside segment": True,
            **_template_defaults("Hollow", TR_HOLLOW_MIN),
            "Notes": "Local web reinforcement only; no automatic segment-joint shear-transfer credit.",
        },
        {
            "Active": True,
            "Template ID": TR_HOLLOW_END,
            "Template name": "Hollow segment end-zone shear reinforcement",
            "Applicable role": "Hollow",
            "Construction": "Factory precast",
            "Credit inside segment": True,
            **_template_defaults("Hollow", TR_HOLLOW_END),
            "Notes": "Dense local reinforcement near segment ends; joint shear remains a separate check.",
        },
        {
            "Active": True,
            "Template ID": TR_SOLID_COLUMN,
            "Template name": "Solid CIP column-region multi-leg ties",
            "Applicable role": "Solid",
            "Construction": "Cast in place",
            "Credit inside segment": True,
            **_template_defaults("Solid", TR_SOLID_COLUMN),
            "Notes": "Local solid-region shear reinforcement; column D-region review remains separate.",
        },
        {
            "Active": True,
            "Template ID": TR_SOLID_ANCHORAGE,
            "Template name": "Solid anchorage/end-block transverse reinforcement",
            "Applicable role": "Solid",
            "Construction": "Cast in place",
            "Credit inside segment": False,
            **_template_defaults("Solid", TR_SOLID_ANCHORAGE),
            "Notes": "Local anchorage/bursting reinforcement only; not a joint-shear certification.",
        },
    ]
    return canonical_transverse_templates(rows)


def canonical_transverse_templates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical: list[dict[str, Any]] = []
    for index, source in enumerate(rows):
        row = dict(source or {})
        template_id = str(row.get("Template ID") or f"TR-{index + 1}").strip()
        role = str(row.get("Applicable role") or "Any").strip().title()
        if role not in TRANSVERSE_ROLE_OPTIONS:
            role = "Any"
        construction = str(row.get("Construction") or "Project-defined").strip()
        if construction not in TRANSVERSE_CONSTRUCTION_OPTIONS:
            construction = "Project-defined"
        defaults = _template_defaults(role, template_id)
        bar_size = str(row.get("Bar size") or defaults["Bar size"]).strip().upper()
        if bar_size not in TRANSVERSE_BAR_SIZE_OPTIONS:
            bar_size = str(defaults["Bar size"])
        raw_material = str(row.get("Rebar material") or "").strip().upper()
        raw_fy = _float(row.get("fy MPa"), 390.0)
        if raw_material in TRANSVERSE_MATERIAL_OPTIONS:
            material = raw_material
            fy_mpa = TRANSVERSE_FY_BY_MATERIAL[material]
        else:
            fy_mpa = 490.0 if abs(raw_fy - 490.0) < abs(raw_fy - 390.0) else 390.0
            material = TRANSVERSE_MATERIAL_BY_FY[fy_mpa]
        canonical.append(
            {
                "Active": _bool(row.get("Active"), True),
                "Template ID": template_id,
                "Template name": str(row.get("Template name") or template_id).strip(),
                "Applicable role": role,
                "Construction": construction,
                "Credit inside segment": _bool(row.get("Credit inside segment"), True),
                "Rebar material": material,
                "fy MPa": fy_mpa,
                "Bar size": bar_size,
                "Spacing mm": max(_float(row.get("Spacing mm"), float(defaults["Spacing mm"])), 1.0),
                "Left web legs": max(int(round(_float(row.get("Left web legs"), float(defaults["Left web legs"])))), 1),
                "Right web legs": max(int(round(_float(row.get("Right web legs"), float(defaults["Right web legs"])))), 1),
                "Effective legs": max(int(round(_float(row.get("Effective legs"), float(defaults["Effective legs"])))), 2),
                "Closed cage": _bool(row.get("Closed cage"), True),
                "Center offset mm": max(_float(row.get("Center offset mm"), float(defaults["Center offset mm"])), 1.0),
                "First bar offset mm": max(_float(row.get("First bar offset mm"), float(defaults["First bar offset mm"])), 0.0),
                "Last bar offset mm": max(_float(row.get("Last bar offset mm"), float(defaults["Last bar offset mm"])), 0.0),
                "Notes": str(row.get("Notes") or "").strip(),
            }
        )
    return canonical


def transverse_template_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["Template ID"]): row
        for row in canonical_transverse_templates(rows)
        if row.get("Active") and str(row.get("Template ID") or "").strip()
    }


def next_transverse_template_id(role: str, existing_ids: list[str] | tuple[str, ...] | set[str]) -> str:
    prefix = "TR-H" if str(role).strip().title() == "Hollow" else "TR-S"
    used = {str(value or "").strip().upper() for value in existing_ids}
    index = 1
    while f"{prefix}{index:02d}" in used:
        index += 1
    return f"{prefix}{index:02d}"


def new_transverse_template(role: str, existing_ids: list[str] | tuple[str, ...] | set[str]) -> dict[str, Any]:
    role_text = "Hollow" if str(role).strip().title() == "Hollow" else "Solid"
    template_id = next_transverse_template_id(role_text, existing_ids)
    row = {
        "Active": True,
        "Template ID": template_id,
        "Template name": f"New {role_text.lower()} transverse template",
        "Applicable role": role_text,
        "Construction": "Factory precast" if role_text == "Hollow" else "Cast in place",
        "Credit inside segment": True,
        **_template_defaults(role_text, template_id),
        "Notes": "Project-defined local transverse reinforcement; no automatic segment-joint shear-transfer credit.",
    }
    return canonical_transverse_templates([row])[0]


def duplicate_transverse_template(
    source: Mapping[str, Any],
    existing_ids: list[str] | tuple[str, ...] | set[str],
) -> dict[str, Any]:
    role = str(source.get("Applicable role") or "Solid")
    row = dict(source)
    row["Template ID"] = next_transverse_template_id(role, existing_ids)
    row["Template name"] = f"{str(source.get('Template name') or source.get('Template ID') or 'Template')} — Copy"
    return canonical_transverse_templates([row])[0]


def default_transverse_template_id(role: str, rows: list[dict[str, Any]]) -> str:
    role_text = str(role or "Solid").strip().title()
    preferred = TR_HOLLOW_MIN if role_text == "Hollow" else TR_SOLID_COLUMN
    active = list(transverse_template_map(rows).values())
    if any(str(row.get("Template ID") or "") == preferred for row in active):
        return preferred
    compatible = [row for row in active if str(row.get("Applicable role") or "") in {role_text, "Any"}]
    candidates = compatible or active
    return str(candidates[0].get("Template ID") or "") if candidates else ""


def transverse_avs_record(template: Mapping[str, Any]) -> dict[str, Any]:
    row = canonical_transverse_templates([dict(template)])[0]
    area = transverse_bar_area_mm2(row["Bar size"])
    spacing = max(float(row["Spacing mm"]), 1.0)
    role = str(row["Applicable role"])
    if role == "Hollow":
        left = float(row["Left web legs"]) * area / spacing
        right = float(row["Right web legs"]) * area / spacing
        total = left + right
    else:
        left = 0.0
        right = 0.0
        total = float(row["Effective legs"]) * area / spacing
    return {
        "Template ID": row["Template ID"],
        "Role": role,
        "Bar": row["Bar size"],
        "Spacing mm": spacing,
        "Av,left/s mm²/mm": left,
        "Av,right/s mm²/mm": right,
        "Av,total/s mm²/mm": total,
        "Status": "INPUT READY" if row["Active"] else "INACTIVE",
    }


def transverse_set_stations(
    template: Mapping[str, Any],
    start_m: float,
    end_m: float,
    *,
    maximum_sets: int = 500,
) -> list[float]:
    row = canonical_transverse_templates([dict(template)])[0]
    start_mm = float(start_m) * 1000.0 + float(row["First bar offset mm"])
    end_mm = float(end_m) * 1000.0 - float(row["Last bar offset mm"])
    spacing = max(float(row["Spacing mm"]), 1.0)
    if end_mm < start_mm:
        return []
    count = min(int((end_mm - start_mm) // spacing) + 1, int(maximum_sets))
    return [(start_mm + index * spacing) / 1000.0 for index in range(max(count, 0))]


def validate_transverse_templates(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    canonical = canonical_transverse_templates(rows)
    errors: list[str] = []
    warnings: list[str] = []
    ids = [str(row.get("Template ID") or "").strip() for row in canonical if row.get("Active")]
    duplicates = sorted({value for value in ids if value and ids.count(value) > 1})
    if duplicates:
        errors.append("Duplicate active Transverse Template IDs: " + ", ".join(duplicates) + ".")
    if not canonical:
        errors.append("At least one Transverse / Shear Template is required.")
    for row in canonical:
        template_id = str(row.get("Template ID") or "")
        if not template_id:
            errors.append("Every Transverse Template requires a Template ID.")
            continue
        if float(row["Spacing mm"]) <= 0.0:
            errors.append(f"{template_id}: spacing must be positive.")
        if str(row["Applicable role"]) == "Hollow" and not bool(row["Closed cage"]):
            warnings.append(f"{template_id}: open web reinforcement is a detailing preview only; closed-cage/tie review remains required.")
        if float(row["First bar offset mm"]) + float(row["Last bar offset mm"]) > 2000.0:
            warnings.append(f"{template_id}: large end offsets may leave short zones without transverse sets.")
    return canonical, errors, warnings


def _arc_points(
    center_x: float,
    center_y: float,
    radius: float,
    start_angle: float,
    end_angle: float,
    *,
    segments: int = 8,
) -> list[tuple[float, float]]:
    count = max(int(segments), 2)
    return [
        (
            center_x + radius * cos(start_angle + (end_angle - start_angle) * index / count),
            center_y + radius * sin(start_angle + (end_angle - start_angle) * index / count),
        )
        for index in range(count + 1)
    ]


def _rounded_rectangle_centerline(
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    radius: float,
) -> tuple[tuple[float, float], ...]:
    """Return a clockwise closed rectangle with true circular corner bends."""

    if x1 <= x0 or y1 <= y0:
        return ()
    r = min(float(radius), 0.5 * (x1 - x0), 0.5 * (y1 - y0))
    if r <= 0.0:
        return ((x0, y0), (x0, y1), (x1, y1), (x1, y0), (x0, y0))
    points: list[tuple[float, float]] = [(x0, y0 + r), (x0, y1 - r)]
    points.extend(_arc_points(x0 + r, y1 - r, r, pi, pi / 2.0)[1:])
    points.append((x1 - r, y1))
    points.extend(_arc_points(x1 - r, y1 - r, r, pi / 2.0, 0.0)[1:])
    points.append((x1, y0 + r))
    points.extend(_arc_points(x1 - r, y0 + r, r, 0.0, -pi / 2.0)[1:])
    points.append((x0 + r, y0))
    points.extend(_arc_points(x0 + r, y0 + r, r, -pi / 2.0, -pi)[1:])
    points.append(points[0])
    return tuple(points)


def _solid_filleted_tie_centerline(
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
    *,
    center_offset_mm: float,
    concrete_bottom_fillet_mm: float,
    bend_radius_mm: float,
) -> tuple[tuple[float, float], ...]:
    """Return the inward-offset solid tie, retaining the concrete bottom fillets."""

    offset = float(center_offset_mm)
    x0, x1 = min_x + offset, max_x - offset
    y0, y1 = min_y + offset, max_y - offset
    outer_radius = max(float(concrete_bottom_fillet_mm), 0.0)
    tie_bottom_radius = outer_radius - offset
    if outer_radius <= 0.0 or tie_bottom_radius <= 0.0:
        return _rounded_rectangle_centerline(x0, x1, y0, y1, bend_radius_mm)

    top_bend = min(float(bend_radius_mm), 0.5 * (x1 - x0), 0.5 * (y1 - y0))
    if top_bend <= 0.0:
        return ()
    right_center_x = max_x - outer_radius
    left_center_x = min_x + outer_radius
    bottom_center_y = min_y + outer_radius
    if left_center_x > right_center_x:
        return ()

    points: list[tuple[float, float]] = [(x0, y1 - top_bend)]
    points.extend(_arc_points(x0 + top_bend, y1 - top_bend, top_bend, pi, pi / 2.0)[1:])
    points.append((x1 - top_bend, y1))
    points.extend(_arc_points(x1 - top_bend, y1 - top_bend, top_bend, pi / 2.0, 0.0)[1:])
    points.append((x1, bottom_center_y))
    points.extend(_arc_points(right_center_x, bottom_center_y, tie_bottom_radius, 0.0, -pi / 2.0, segments=12)[1:])
    points.append((left_center_x, y0))
    points.extend(_arc_points(left_center_x, bottom_center_y, tie_bottom_radius, -pi / 2.0, -pi, segments=12)[1:])
    points.append((x0, y1 - top_bend))
    return tuple(points)


def _section_polygon(geometry: Any) -> Polygon:
    outer = [(float(point.x), float(point.y)) for point in list(getattr(geometry, "outer_polygon", []) or [])]
    holes = [
        [(float(point.x), float(point.y)) for point in list(hole)]
        for hole in list(getattr(geometry, "holes", []) or [])
    ]
    return Polygon(outer, holes)


def _fit_rectangular_cage_bottom_to_outer_boundary(
    outer_polygon: Polygon,
    *,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    bend_radius_mm: float,
    transverse_radius_mm: float,
) -> tuple[tuple[tuple[float, float], ...], float]:
    """Raise a rectangular cage only as needed to clear an outer bottom fillet."""

    def candidate(bottom: float) -> tuple[tuple[float, float], ...]:
        return _rounded_rectangle_centerline(x0, x1, bottom, y1, bend_radius_mm)

    def fits(points: tuple[tuple[float, float], ...]) -> bool:
        if not points:
            return False
        steel = LineString(points).buffer(transverse_radius_mm, cap_style=1, join_style=1)
        return outer_polygon.buffer(1e-7).covers(steel)

    initial = candidate(y0)
    if fits(initial):
        return initial, y0
    upper = y1 - 2.0 * bend_radius_mm
    if upper <= y0:
        return initial, y0
    upper_candidate = candidate(upper)
    if not fits(upper_candidate):
        return initial, y0
    low, high = y0, upper
    for _index in range(48):
        mid = 0.5 * (low + high)
        if fits(candidate(mid)):
            high = mid
        else:
            low = mid
    return candidate(high), high


def build_transverse_cage_geometry(
    geometry: Any,
    definition: Mapping[str, Any],
    template: Mapping[str, Any],
    *,
    bend_radius_mm: float = TRANSVERSE_PREVIEW_BEND_RADIUS_MM,
) -> TransverseCageGeometry:
    """Build Crossbeam-only transverse centerlines without changing inputs.

    Solid ties are true inward offsets of the bottom-filleted outer profile.
    Hollow cages deliberately remain rectangular and web-controlled; invalid
    cages are reported for review instead of being reshaped around a chamfer.
    """

    row = canonical_transverse_templates([dict(template)])[0]
    role = str(definition.get("Section role") or row.get("Applicable role") or "Solid").title()
    offset = float(row.get("Center offset mm") or 50.0)
    bar_diameter = transverse_bar_diameter_mm(row.get("Bar size"))
    bend_radius = float(bend_radius_mm)
    errors: list[str] = []
    warnings: list[str] = []
    paths: list[TransverseCagePath] = []

    outer = list(getattr(geometry, "outer_polygon", []) or [])
    if len(outer) < 3:
        errors.append("Concrete outer boundary is unavailable.")
        return TransverseCageGeometry(role, offset, bend_radius, bar_diameter, (), tuple(errors), ())
    min_x = min(float(point.x) for point in outer)
    max_x = max(float(point.x) for point in outer)
    min_y = min(float(point.y) for point in outer)
    max_y = max(float(point.y) for point in outer)
    if offset <= 0.0:
        errors.append("Transverse center offset must be positive.")
    if bend_radius <= 0.0:
        errors.append("Transverse preview bend radius must be positive.")

    if role == "Hollow":
        holes = list(getattr(geometry, "holes", []) or [])
        if not holes:
            errors.append("Hollow transverse template requires a section void.")
        else:
            hole = list(holes[0])
            hole_min_x = min(float(point.x) for point in hole)
            hole_max_x = max(float(point.x) for point in hole)
            outer_only = Polygon([(float(point.x), float(point.y)) for point in outer])
            envelopes = (
                ("Left-web cage", min_x + offset, hole_min_x - offset, min_y + offset, max_y - offset, int(row["Left web legs"])),
                ("Right-web cage", hole_max_x + offset, max_x - offset, min_y + offset, max_y - offset, int(row["Right web legs"])),
            )
            for label, x0, x1, y0, y1, effective_legs in envelopes:
                if x1 - x0 < 2.0 * bend_radius or y1 - y0 < 2.0 * bend_radius:
                    errors.append(
                        f"{label}: available cage width/height cannot accommodate the {bend_radius:.0f} mm corner bend."
                    )
                    continue
                points, fitted_y0 = _fit_rectangular_cage_bottom_to_outer_boundary(
                    outer_only,
                    x0=x0,
                    x1=x1,
                    y0=y0,
                    y1=y1,
                    bend_radius_mm=bend_radius,
                    transverse_radius_mm=0.5 * bar_diameter,
                )
                if fitted_y0 > y0 + 0.5:
                    warnings.append(
                        f"{label}: rectangular bottom centerline raised {fitted_y0 - y0:.1f} mm to clear the outer concrete fillet."
                    )
                paths.append(TransverseCagePath(label, points, (x0, x1, fitted_y0, y1), max(effective_legs, 2)))
    else:
        x0, x1 = min_x + offset, max_x - offset
        y0, y1 = min_y + offset, max_y - offset
        if x1 - x0 < 2.0 * bend_radius or y1 - y0 < 2.0 * bend_radius:
            errors.append(f"Closed tie: available width/height cannot accommodate the {bend_radius:.0f} mm corner bend.")
        else:
            concrete_fillet = float(
                dict(getattr(geometry, "metadata", {}) or {}).get(
                    "bottom_fillet_radius_mm",
                    dict(definition.get("Parameters") or {}).get("bottom_fillet_radius_mm", 0.0),
                )
                or 0.0
            )
            points = _solid_filleted_tie_centerline(
                min_x,
                max_x,
                min_y,
                max_y,
                center_offset_mm=offset,
                concrete_bottom_fillet_mm=concrete_fillet,
                bend_radius_mm=bend_radius,
            )
            if not points:
                errors.append("Closed tie centerline could not be generated from the selected offset and section fillets.")
            else:
                paths.append(
                    TransverseCagePath(
                        "Closed tie",
                        points,
                        (x0, x1, y0, y1),
                        max(int(row.get("Effective legs") or 2), 2),
                    )
                )

    concrete = _section_polygon(geometry)
    transverse_radius = 0.5 * bar_diameter
    for path in paths:
        line = LineString(path.points)
        cage_polygon = Polygon(path.points)
        if not line.is_simple or not cage_polygon.is_valid or cage_polygon.area <= 0.0:
            errors.append(f"{path.label}: generated centerline is self-intersecting or invalid.")
            continue
        steel_envelope = line.buffer(transverse_radius, cap_style=1, join_style=1)
        if not concrete.buffer(1e-7).covers(steel_envelope):
            errors.append(
                f"{path.label}: rectangular/offset cage intrudes outside the concrete or into the void/chamfer."
            )
    if not bool(row.get("Closed cage")):
        warnings.append("Template is not flagged as a closed cage/tie; the preview does not certify confinement or torsion detailing.")

    return TransverseCageGeometry(
        role=role,
        center_offset_mm=offset,
        bend_radius_mm=bend_radius,
        bar_diameter_mm=bar_diameter,
        paths=tuple(paths),
        errors=tuple(dict.fromkeys(errors)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def place_longitudinal_bars_relative_to_cages(
    cages: TransverseCageGeometry,
    rebars: list[Any] | tuple[Any, ...],
    *,
    tolerance_mm: float = 1.0e-3,
) -> CageRelativeLongitudinalPlacement:
    """Place cage-associated longitudinal centers one radius-sum inside.

    Solid ties govern every generated perimeter bar.  Hollow sections retain
    independent left/right rectangular web cages, so only bars whose centers
    fall within a web-cage envelope (or already touch its line) are snapped to
    that cage.  Top/bottom flange-face bars between the web cages are not
    incorrectly pulled sideways into a web cage.
    """

    bars = list(rebars or [])
    if not bars or not cages.paths:
        return CageRelativeLongitudinalPlacement(tuple(bars), 0, 0)
    path_data = [
        (path, LineString(path.points), Polygon(path.points))
        for path in cages.paths
        if len(path.points) >= 4
    ]
    adjusted: list[Any] = []
    adjusted_count = 0
    associated_count = 0
    tolerance = max(float(tolerance_mm), 1.0e-7)

    for bar in bars:
        point = Point(float(getattr(bar, "x_mm", 0.0)), float(getattr(bar, "y_mm", 0.0)))
        longitudinal_diameter = max(float(getattr(bar, "diameter_mm", 0.0) or 0.0), 0.0)
        clearance = 0.5 * (longitudinal_diameter + cages.bar_diameter_mm)
        relevant: list[tuple[TransverseCagePath, LineString, Polygon]] = []
        for path, line, polygon in path_data:
            x0, x1, _y0, _y1 = path.envelope
            if cages.role != "Hollow" or x0 - tolerance <= point.x <= x1 + tolerance:
                relevant.append((path, line, polygon))
            elif line.distance(point) <= clearance + tolerance:
                relevant.append((path, line, polygon))
        if not relevant:
            adjusted.append(bar)
            continue
        associated_count += 1

        candidates: list[tuple[float, Point]] = []
        for _path, _line, polygon in relevant:
            available = polygon.buffer(-clearance, join_style=1)
            if available.is_empty:
                continue
            target = nearest_points(point, available.boundary)[1]
            candidates.append((point.distance(target), target))
        if not candidates:
            adjusted.append(bar)
            continue
        distance, target = min(candidates, key=lambda item: item[0])
        if distance <= tolerance:
            adjusted.append(bar)
            continue
        if hasattr(bar, "model_copy"):
            adjusted.append(bar.model_copy(update={"x_mm": float(target.x), "y_mm": float(target.y)}))
        else:
            adjusted.append(bar)
            continue
        adjusted_count += 1

    return CageRelativeLongitudinalPlacement(tuple(adjusted), adjusted_count, associated_count)


def review_longitudinal_bar_containment(
    cages: TransverseCageGeometry,
    rebars: list[Any] | tuple[Any, ...],
) -> LongitudinalContainmentReview:
    """Check cage containment for Solid and cage clash/web fit for Hollow."""

    bars = list(rebars or [])
    messages: list[str] = list(cages.errors)
    if not bars:
        messages.append("No generated longitudinal bars are available for the transverse-outside-longitudinal check.")
        return LongitudinalContainmentReview("REVIEW REQUIRED", 0, 0, tuple(dict.fromkeys(messages)))
    cage_polygons = [Polygon(path.points) for path in cages.paths if len(path.points) >= 4]
    cage_lines = [LineString(path.points) for path in cages.paths if len(path.points) >= 4]
    if not cage_polygons:
        messages.append("No valid transverse cage/tie envelope is available for containment review.")
        return LongitudinalContainmentReview("REVIEW REQUIRED", len(bars), len(bars), tuple(dict.fromkeys(messages)))

    conflicts: dict[str, int] = {}
    for bar in bars:
        bar_diameter = max(float(getattr(bar, "diameter_mm", 0.0) or 0.0), 0.0)
        clearance = 0.5 * (bar_diameter + cages.bar_diameter_mm)
        point = Point(float(getattr(bar, "x_mm", 0.0)), float(getattr(bar, "y_mm", 0.0)))
        if any(line.distance(point) < clearance - 1.0e-3 for line in cage_lines):
            contained = False
        elif cages.role == "Hollow":
            relevant = [
                (path, polygon)
                for path, polygon in zip(cages.paths, cage_polygons)
                if path.envelope[0] - 1.0e-3 <= point.x <= path.envelope[1] + 1.0e-3
            ]
            contained = not relevant or any(
                not (available := polygon.buffer(-(clearance - 1.0e-3), join_style=1)).is_empty
                and available.covers(point)
                for _path, polygon in relevant
            )
        else:
            contained = any(
                not (available := polygon.buffer(-(clearance - 1.0e-3), join_style=1)).is_empty
                and available.covers(point)
                for polygon in cage_polygons
            )
        if contained:
            continue
        raw_label = str(getattr(bar, "label", "") or "Longitudinal")
        layer = raw_label.split(":", 1)[0].strip() or "Longitudinal"
        conflicts[layer] = conflicts.get(layer, 0) + 1

    conflict_count = sum(conflicts.values())
    for layer, count in sorted(conflicts.items()):
        messages.append(
            f"{layer} face/layer: {count} generated bar(s) are outside the cage interior or clash with transverse steel."
        )
    if conflict_count or cages.errors:
        return LongitudinalContainmentReview(
            "REVIEW REQUIRED",
            len(bars),
            conflict_count,
            tuple(dict.fromkeys(messages)),
        )
    if cages.role == "Hollow":
        messages.append(
            "Geometric ordering confirmed: web-associated bars fit inside the rectangular cages; flange-face bars between cages do not clash with transverse steel."
        )
    else:
        messages.append(
            "Geometric ordering confirmed for the generated preview: concrete surface → transverse centerline → longitudinal bar circle."
        )
    return LongitudinalContainmentReview(
        "READY FOR DETAILING REVIEW",
        len(bars),
        0,
        tuple(dict.fromkeys(messages)),
    )
