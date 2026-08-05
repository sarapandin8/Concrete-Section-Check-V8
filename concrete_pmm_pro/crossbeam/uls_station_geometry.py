"""Shared ULS station-eligibility and geometry routing for Crossbeams.

This module owns only station geometry and row-coupled demand recovery.  It does
not calculate Flexure, Shear, Torsion, or Combined V+T resistance.  All ULS
modules use the same Column/support footprints, beam-side support-face recovery,
full-member sectional eligibility, and construction-mode terminology.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Any

from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    CONSTRUCTION_METHOD_PRECAST,
    column_support_footprint_rows,
    normalize_construction_method,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.project_geometry import CROSSBEAM_COLUMN_ROWS_KEY
from concrete_pmm_pro.crossbeam.section_library import build_geometry_for_definition, definition_map
from concrete_pmm_pro.crossbeam.tendon import station_section_contexts
from concrete_pmm_pro.geometry.summary import to_shapely_polygon


CB_ULS_PT_END_ZONE_BASIS_KEY = "crossbeam_uls_pt_end_zone_basis"
CB_ULS_PT_END_ZONE_LEFT_M_KEY = "crossbeam_uls_pt_end_zone_left_m"
CB_ULS_PT_END_ZONE_RIGHT_M_KEY = "crossbeam_uls_pt_end_zone_right_m"
CB_ULS_PT_END_ZONE_BASIS_LOCAL_DEPTH = "Local section depth h"
CB_ULS_PT_END_ZONE_BASIS_MANUAL = "Manual engineer-adopted lengths"
CB_ULS_PT_END_ZONE_BASIS_OPTIONS = (
    CB_ULS_PT_END_ZONE_BASIS_LOCAL_DEPTH,
    CB_ULS_PT_END_ZONE_BASIS_MANUAL,
)

_SUPPORT_EXTRAPOLATION_LIMIT_RATIO = 0.25


@dataclass(frozen=True)
class CrossbeamPtEndZoneSettings:
    basis: str
    left_length_m: float
    right_length_m: float
    left_boundary_m: float
    right_boundary_m: float
    ready: bool
    errors: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "Basis": self.basis,
            "Left length m": self.left_length_m,
            "Right length m": self.right_length_m,
            "Left boundary s (m)": self.left_boundary_m,
            "Right boundary s (m)": self.right_boundary_m,
            "Ready": self.ready,
            "Errors": list(self.errors),
            "Notes": list(self.notes),
        }


def _get(state: Any, key: str, default: Any = None) -> Any:
    if hasattr(state, "get"):
        return state.get(key, default)
    return getattr(state, key, default)


def _records(value: Any) -> list[dict[str, Any]]:
    if hasattr(value, "to_dict"):
        try:
            return [dict(row) for row in value.to_dict(orient="records")]
        except Exception:
            return []
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _dedupe(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(str(message).strip() for message in messages if str(message).strip()))


def construction_region_noun(construction_method: str) -> str:
    return "Zone" if normalize_construction_method(construction_method) == CONSTRUCTION_METHOD_CIP else "Segment"


def interior_location_type(construction_method: str) -> str:
    return "ZONE INTERIOR" if normalize_construction_method(construction_method) == CONSTRUCTION_METHOD_CIP else "SEGMENT INTERIOR"


def trace_owner_label(construction_method: str) -> str:
    return "Zone-owned" if normalize_construction_method(construction_method) == CONSTRUCTION_METHOD_CIP else "Segment-owned"


def support_footprints_from_state(
    state: Any,
    *,
    member_length_m: float,
    segment_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    rows = _records(_get(state, CROSSBEAM_COLUMN_ROWS_KEY, []))
    if not rows:
        return [], ["Applied Column / Support Layout is missing for Crossbeam ULS station routing."]
    footprints = column_support_footprint_rows(rows, segment_rows, length_m=member_length_m)
    errors: list[str] = []
    tolerance = max(1.0e-7, member_length_m * 1.0e-9)
    for footprint in footprints:
        support_id = str(footprint.get("Column") or "Column / Support")
        left = _finite(footprint.get("s_left (m)"), float("nan"))
        right = _finite(footprint.get("s_right (m)"), float("nan"))
        center = _finite(footprint.get("Center s (m)"), float("nan"))
        if not all(math.isfinite(value) for value in (left, right, center)) or right <= left + tolerance:
            errors.append(f"{support_id}: invalid support-footprint limits for Crossbeam ULS station routing.")
    return list(footprints), _dedupe(errors)


def station_inside_support_interior(
    station_m: float,
    support_footprints: list[dict[str, Any]],
    *,
    tolerance: float,
) -> bool:
    for footprint in support_footprints:
        left = _finite(footprint.get("s_left (m)"), float("nan"))
        right = _finite(footprint.get("s_right (m)"), float("nan"))
        if math.isfinite(left) and math.isfinite(right) and left + tolerance < station_m < right - tolerance:
            return True
    return False


def _section_depth_at_probe(
    *,
    probe_m: float,
    segment_rows: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    member_length_m: float,
) -> tuple[float | None, str | None]:
    contexts = station_section_contexts(probe_m, segment_rows, definitions, length_m=member_length_m)
    section_ids = list(dict.fromkeys(str(row.get("Section ID") or "") for row in contexts if str(row.get("Section ID") or "")))
    if len(section_ids) != 1:
        if not section_ids:
            return None, f"no Section ID is assigned at s = {probe_m:.6f} m."
        return None, f"multiple Section IDs are active at s = {probe_m:.6f} m: {', '.join(section_ids)}."
    definition = definition_map(definitions).get(section_ids[0])
    if definition is None:
        return None, f"Section ID {section_ids[0]} is unavailable."
    try:
        polygon = to_shapely_polygon(build_geometry_for_definition(definition))
        depth_m = (float(polygon.bounds[3]) - float(polygon.bounds[1])) / 1000.0
    except Exception as exc:
        return None, f"unable to determine section depth: {exc}"
    if not math.isfinite(depth_m) or depth_m <= 0.0:
        return None, "section depth h is invalid."
    return depth_m, None


def canonical_pt_end_zone_settings(
    state: Any,
    *,
    member_length_m: float,
    segment_rows: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
) -> CrossbeamPtEndZoneSettings:
    """Return the compatibility payload for full-member sectional ULS checks.

    ANALYSIS4C6B1 restores every valid end station to the Flexure, Shear,
    Torsion, and Combined V+T envelopes.  Historical Project JSON end-zone
    fields remain readable for backward compatibility, but they no longer clip
    traces, remove rows, change governing searches, or stale ULS results.
    Anchorage local-zone/general-zone verification remains a separate project
    check and is stated in the ULS scope notes instead.
    """

    del state, segment_rows, definitions  # Retained in the public API for compatibility.
    errors: list[str] = []
    if not math.isfinite(float(member_length_m)) or float(member_length_m) <= 0.0:
        errors.append("Crossbeam member length must be positive.")
    length = max(0.0, _finite(member_length_m, 0.0))
    return CrossbeamPtEndZoneSettings(
        basis="Full-member sectional ULS (no automatic PT end-zone exclusion)",
        left_length_m=0.0,
        right_length_m=0.0,
        left_boundary_m=0.0,
        right_boundary_m=length,
        ready=not errors,
        errors=tuple(_dedupe(errors)),
        notes=(
            "All valid stations from s = 0 to s = L remain eligible for sectional ULS governing.",
            "PT anchorage local-zone and general-zone verification remains a separate project check.",
        ),
    )

def pt_end_zone_side(
    station_m: float,
    settings: CrossbeamPtEndZoneSettings,
    *,
    tolerance: float,
) -> str:
    """Return no exclusion side; full-member sectional ULS is intentional."""

    del station_m, settings, tolerance
    return ""

def end_zone_exclusion_record(row: Mapping[str, Any], *, side: str, source_kind: str) -> dict[str, Any]:
    return {
        "Status": "REVIEW",
        "Station s (m)": _finite(row.get("Station s (m)"), 0.0),
        "Check Point": str(row.get("Check Point") or ""),
        "Case": str(row.get("Case Name") or "ULS"),
        "Location type": "PT END ZONE / D-REGION",
        "End": side,
        "Demand source": str(row.get("__Demand source") or source_kind or "IMPORTED"),
        "Reason": "Excluded from ordinary ULS B-region sectional governing; PT anchorage/end-zone design remains separate.",
    }


def _rows_at_unique_station(
    rows: list[dict[str, Any]],
    *,
    station_m: float,
    side: str,
    tolerance: float,
) -> tuple[dict[str, Any] | None, str | None]:
    candidates = [row for row in rows if abs(_finite(row.get("Station s (m)"), float("nan")) - station_m) <= tolerance]
    if not candidates:
        return None, None
    explicit = [row for row in candidates if side in str(row.get("Check Point") or "").strip().casefold()]
    if explicit:
        candidates = explicit
    reference = candidates[0]
    for other in candidates[1:]:
        if any(abs(_finite(other.get(field)) - _finite(reference.get(field))) > 1.0e-8 for field in ("P", "V2", "T", "M3")):
            return None, (
                f"multiple non-identical station-force rows exist at s = {station_m:.6f} m; "
                f"label an explicit {side.title()} Check Point or keep one row-coupled source state."
            )
    return dict(reference), None


def interpolate_support_demand(
    *,
    case_rows: list[dict[str, Any]],
    target_m: float,
    support_center_m: float,
    side: str,
    support_footprints: list[dict[str, Any]],
    tolerance: float,
    station_label: str,
) -> tuple[dict[str, Any] | None, str | None, str]:
    exact, exact_error = _rows_at_unique_station(case_rows, station_m=target_m, side=side, tolerance=tolerance)
    if exact_error:
        return None, exact_error, ""
    if exact is not None:
        exact.update({
            "__Demand source": "EXACT",
            "__Source station 1 (m)": target_m,
            "__Source station 2 (m)": target_m,
            "__Source ratio": 0.0,
            "__Extrapolation ratio": 0.0,
        })
        return exact, None, f"Exact imported row at s = {target_m:.6f} m."
    support_centers = sorted({
        round(_finite(item.get("Center s (m)"), float("nan")), 9)
        for item in support_footprints
        if math.isfinite(_finite(item.get("Center s (m)"), float("nan")))
    })

    def crosses_reaction(station_m: float) -> bool:
        if side == "left" and station_m >= support_center_m - tolerance:
            return True
        if side == "right" and station_m <= support_center_m + tolerance:
            return True
        low, high = sorted((station_m, target_m))
        return any(
            abs(station_m - float(center)) <= tolerance or low + tolerance < float(center) < high - tolerance
            for center in support_centers
        )

    eligible = [
        row for row in case_rows
        if math.isfinite(_finite(row.get("Station s (m)"), float("nan")))
        and not crosses_reaction(_finite(row.get("Station s (m)"), float("nan")))
    ]
    station_groups: dict[float, list[dict[str, Any]]] = {}
    for row in eligible:
        station_groups.setdefault(round(_finite(row.get("Station s (m)")), 9), []).append(row)
    unique_rows: list[dict[str, Any]] = []
    for key in sorted(station_groups):
        selected, ambiguity = _rows_at_unique_station(station_groups[key], station_m=float(key), side=side, tolerance=tolerance)
        if ambiguity:
            return None, ambiguity, ""
        if selected is not None:
            unique_rows.append(selected)
    if len(unique_rows) < 2:
        return None, (
            f"{station_label} s = {target_m:.6f} m requires at least two active row-coupled "
            f"station-force rows on the {side} beam side without crossing a support centerline."
        ), ""
    lower = [row for row in unique_rows if _finite(row.get("Station s (m)"), float("nan")) < target_m - tolerance]
    upper = [row for row in unique_rows if _finite(row.get("Station s (m)"), float("nan")) > target_m + tolerance]
    method = "INTERPOLATED"
    extrapolation_ratio = 0.0
    if lower and upper:
        lo = max(lower, key=lambda row: _finite(row.get("Station s (m)"), -1.0e99))
        hi = min(upper, key=lambda row: _finite(row.get("Station s (m)"), 1.0e99))
    elif not lower:
        lo, hi = unique_rows[0], unique_rows[1]
        method = "EXTRAPOLATED"
    else:
        lo, hi = unique_rows[-2], unique_rows[-1]
        method = "EXTRAPOLATED"
    x0 = _finite(lo.get("Station s (m)"), float("nan"))
    x1 = _finite(hi.get("Station s (m)"), float("nan"))
    if not math.isfinite(x0) or not math.isfinite(x1) or x1 <= x0 + tolerance:
        return None, f"invalid one-sided source bracket for s = {target_m:.6f} m.", ""
    ratio = (target_m - x0) / (x1 - x0)
    if method == "EXTRAPOLATED":
        extrapolation_ratio = min(abs(target_m - x0), abs(target_m - x1)) / (x1 - x0)
        if extrapolation_ratio > _SUPPORT_EXTRAPOLATION_LIMIT_RATIO + 1.0e-12:
            return None, (
                f"{station_label} s = {target_m:.6f} m needs one-sided extrapolation of "
                f"{100.0 * extrapolation_ratio:.1f}% of the source-row spacing, exceeding the "
                f"{100.0 * _SUPPORT_EXTRAPOLATION_LIMIT_RATIO:.0f}% safety limit."
            ), ""
    derived = {
        "Active": True,
        "Station s (m)": target_m,
        "Case Name": str(lo.get("Case Name") or hi.get("Case Name") or "ULS"),
        **{
            field: _finite(lo.get(field)) + ratio * (_finite(hi.get(field)) - _finite(lo.get(field)))
            for field in ("P", "V2", "T", "M3")
        },
        "__Demand source": method,
        "__Source station 1 (m)": x0,
        "__Source station 2 (m)": x1,
        "__Source ratio": ratio,
        "__Extrapolation ratio": extrapolation_ratio,
    }
    if method == "INTERPOLATED":
        note = f"Row-coupled one-sided interpolation from s = {x0:.6f} and {x1:.6f} m (r = {ratio:.6f})."
    else:
        note = (
            f"Row-coupled limited one-sided extrapolation from s = {x0:.6f} and {x1:.6f} m "
            f"(r = {ratio:.6f}; extrapolation = {100.0 * extrapolation_ratio:.1f}% of spacing)."
        )
    return derived, None, note


def _support_side_section_depth(
    *,
    face_m: float,
    side: str,
    segment_rows: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    member_length_m: float,
) -> tuple[float | None, float, str | None]:
    tolerance = max(1.0e-7, member_length_m * 1.0e-9)
    probe_offset = max(1.0e-6, member_length_m * 1.0e-8)
    probe = min(max(face_m - probe_offset if side == "left" else face_m + probe_offset, 0.0), member_length_m)
    if side == "left" and face_m <= tolerance:
        return None, probe, None
    if side == "right" and face_m >= member_length_m - tolerance:
        return None, probe, None
    depth_m, error = _section_depth_at_probe(
        probe_m=probe,
        segment_rows=segment_rows,
        definitions=definitions,
        member_length_m=member_length_m,
    )
    return (None if depth_m is None else depth_m * 1000.0), probe, error


def generate_support_check_demands(
    *,
    active_demands: list[dict[str, Any]],
    support_footprints: list[dict[str, Any]],
    segment_rows: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    member_length_m: float,
    include_h2: bool,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    tolerance = max(1.0e-7, member_length_m * 1.0e-9)
    cases: dict[str, list[dict[str, Any]]] = {}
    for row in active_demands:
        cases.setdefault(str(row.get("Case Name") or "ULS"), []).append(row)
    output: list[dict[str, Any]] = []
    errors: list[str] = []
    info: list[str] = []
    seen: set[tuple[str, str, str, str]] = set()
    ordered = sorted(support_footprints, key=lambda row: _finite(row.get("Center s (m)"), float("inf")))
    for case_name, case_rows in cases.items():
        for footprint in ordered:
            support_id = str(footprint.get("Column") or "Column / Support")
            center = _finite(footprint.get("Center s (m)"), float("nan"))
            left = _finite(footprint.get("s_left (m)"), float("nan"))
            right = _finite(footprint.get("s_right (m)"), float("nan"))
            if not all(math.isfinite(value) for value in (center, left, right)) or right <= left + tolerance:
                errors.append(f"{support_id}: invalid support-footprint limits for Crossbeam ULS station routing.")
                continue
            for side, face in (("left", left), ("right", right)):
                h_mm, context_station, depth_error = _support_side_section_depth(
                    face_m=face,
                    side=side,
                    segment_rows=segment_rows,
                    definitions=definitions,
                    member_length_m=member_length_m,
                )
                if depth_error:
                    errors.append(f"{case_name} · {support_id}: {depth_error}")
                    continue
                if h_mm is None:
                    continue
                side_label = "L" if side == "left" else "R"
                face_source, face_error, face_note = interpolate_support_demand(
                    case_rows=case_rows,
                    target_m=face,
                    support_center_m=center,
                    side=side,
                    support_footprints=ordered,
                    tolerance=tolerance,
                    station_label="Column Face",
                )
                if face_error or face_source is None:
                    errors.append(f"{case_name} · {support_id}-{side_label}: {face_error}")
                    continue
                key = (case_name, support_id, side, "COLUMN FACE")
                if key not in seen:
                    seen.add(key)
                    row = dict(face_source)
                    row.update({
                        "Active": True,
                        "Station s (m)": face,
                        "Check Point": f"{support_id}-{side_label} Face",
                        "Case Name": case_name,
                        "Note": face_note,
                        "__Derived support check": True,
                        "__Location type": "COLUMN FACE",
                        "__Context station s (m)": context_station,
                        "__Support ID": support_id,
                        "__Support side": side.upper(),
                    })
                    output.append(row)
                if not include_h2:
                    continue
                critical = face - h_mm / 2000.0 if side == "left" else face + h_mm / 2000.0
                if critical < -tolerance or critical > member_length_m + tolerance:
                    info.append(f"{case_name} · {support_id}-{side_label}: ACI h/2 station lies outside the modeled member; the Column Face check remains active.")
                    continue
                critical = min(max(critical, 0.0), member_length_m)
                if station_inside_support_interior(critical, ordered, tolerance=tolerance):
                    errors.append(f"{case_name} · {support_id}-{side_label}: ACI h/2 station s = {critical:.6f} m lies inside a support footprint.")
                    continue
                critical_source, critical_error, critical_note = interpolate_support_demand(
                    case_rows=case_rows,
                    target_m=critical,
                    support_center_m=center,
                    side=side,
                    support_footprints=ordered,
                    tolerance=tolerance,
                    station_label="ACI h/2 critical section",
                )
                if critical_error or critical_source is None:
                    errors.append(f"{case_name} · {support_id}-{side_label}: {critical_error}")
                    continue
                key = (case_name, support_id, side, "ACI h/2 CRITICAL SECTION")
                if key not in seen:
                    seen.add(key)
                    row = dict(critical_source)
                    row.update({
                        "Active": True,
                        "Station s (m)": critical,
                        "Check Point": f"{support_id}-{side_label} h/2",
                        "Case Name": case_name,
                        "Note": critical_note,
                        "__Derived support check": True,
                        "__Location type": "ACI h/2 CRITICAL SECTION",
                        "__Context station s (m)": critical,
                        "__Support ID": support_id,
                        "__Support side": side.upper(),
                    })
                    output.append(row)
    output.sort(key=lambda row: (str(row.get("Case Name") or ""), _finite(row.get("Station s (m)")), str(row.get("Check Point") or "")))
    return output, _dedupe(errors), _dedupe(info)
