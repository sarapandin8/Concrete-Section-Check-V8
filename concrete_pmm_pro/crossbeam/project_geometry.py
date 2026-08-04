"""Crossbeam Project-JSON geometry consistency audit.

``CROSSBEAM.PROJECT.JSON1`` keeps saved station coordinates authoritative.
This module is deliberately read-only: it reports mismatches after restore but
never scales, clamps, or rebuilds engineering input rows.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any


CROSSBEAM_PROJECT_GEOMETRY_AUDIT_KEY = "crossbeam_project_json1_geometry_audit"

CROSSBEAM_LENGTH_KEY = "crossbeam_ui1_length_m"
CROSSBEAM_SEGMENT_ROWS_KEY = "crossbeam_ui1_segment_layout_rows"
CROSSBEAM_REBAR_ZONE_ROWS_KEY = "crossbeam_rb1_zone_assignment_rows"
CROSSBEAM_CIP_REBAR_ZONE_ROWS_KEY = "crossbeam_rb_cip2a_zone_assignment_rows"
CROSSBEAM_CONSTRUCTION_METHOD_KEY = "crossbeam_ptloss3b1_construction_method"
CONSTRUCTION_METHOD_CIP = "Cast-in-Place"
CROSSBEAM_TENDON_SYSTEM_ROWS_KEY = "crossbeam_pt1_tendon_system_rows"
CROSSBEAM_TENDON_PROFILE_ROWS_KEY = "crossbeam_ui1_tendon_profile_points"
CROSSBEAM_COLUMN_ROWS_KEY = "crossbeam_ptloss3b1_column_rows"
CROSSBEAM_ULS_LOAD_ROWS_KEY = "crossbeam_uls_loads_table"
CROSSBEAM_SLS_LOAD_ROWS_KEY = "crossbeam_sls_loads_table"


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            return [dict(row) for row in value.to_dict(orient="records")]
        except TypeError:
            pass
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    if isinstance(value, tuple):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if isfinite(result) else default


def _station(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in row:
            continue
        try:
            value = float(row.get(key))
        except (TypeError, ValueError):
            continue
        if isfinite(value):
            return value
    return None


def _extent(rows: list[dict[str, Any]], start_keys: tuple[str, ...], end_keys: tuple[str, ...]) -> tuple[float, float] | None:
    starts = [_station(row, *start_keys) for row in rows]
    ends = [_station(row, *end_keys) for row in rows]
    finite_starts = [value for value in starts if value is not None]
    finite_ends = [value for value in ends if value is not None]
    if not finite_starts or not finite_ends:
        return None
    return min(finite_starts), max(finite_ends)


def _issue(component: str, detail: str, where_to_fix: str, *, blocks_rebar_solver: bool = False) -> dict[str, Any]:
    return {
        "Component": component,
        "Status": "INCONSISTENT",
        "Detail": detail,
        "Where to fix": where_to_fix,
        "Blocks rebar solver": bool(blocks_rebar_solver),
    }


def _coverage_issues(
    *,
    component: str,
    rows: list[dict[str, Any]],
    length_m: float,
    start_keys: tuple[str, ...],
    end_keys: tuple[str, ...],
    where_to_fix: str,
    blocks_rebar_solver: bool = False,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    extent = _extent(rows, start_keys, end_keys)
    if extent is None:
        return [
            _issue(
                component,
                f"{component} station extent cannot be read from the restored rows.",
                where_to_fix,
                blocks_rebar_solver=blocks_rebar_solver,
            )
        ]
    start_m, end_m = extent
    tolerance = max(1e-6, abs(length_m) * 1e-6)
    if abs(start_m) <= tolerance and abs(end_m - length_m) <= tolerance:
        return []
    return [
        _issue(
            component,
            f"{component} extent = {start_m:.3f}–{end_m:.3f} m, but Crossbeam length = {length_m:.3f} m.",
            where_to_fix,
            blocks_rebar_solver=blocks_rebar_solver,
        )
    ]


def _rebar_alignment(
    segment_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
    length_m: float,
) -> dict[str, Any]:
    extent = _extent(zone_rows, ("s_start_m", "s_start (m)"), ("s_end_m", "s_end (m)"))
    segment_by_id = {
        str(row.get("Segment") or "").strip(): row
        for row in segment_rows
        if str(row.get("Segment") or "").strip()
    }
    zones_by_segment: dict[str, list[dict[str, Any]]] = {}
    for row in zone_rows:
        zones_by_segment.setdefault(str(row.get("Segment") or "").strip(), []).append(row)
    one_zone_per_segment = bool(segment_by_id) and set(zones_by_segment) == set(segment_by_id) and all(
        len(zones_by_segment.get(segment_id, [])) == 1 for segment_id in segment_by_id
    )

    tolerance = max(1e-6, abs(length_m) * 1e-6)
    geometry_consistent = bool(zone_rows) and set(zones_by_segment) == set(segment_by_id)
    if geometry_consistent:
        for segment_id, segment in segment_by_id.items():
            zones = sorted(
                zones_by_segment.get(segment_id, []),
                key=lambda row: _number(row.get("s_start_m", row.get("s_start (m)")), 0.0),
            )
            segment_start = _station(segment, "x_start_m", "s_start (m)")
            segment_end = _station(segment, "x_end_m", "s_end (m)")
            if not zones or segment_start is None or segment_end is None:
                geometry_consistent = False
                break
            zone_starts = [_station(zone, "s_start_m", "s_start (m)") for zone in zones]
            zone_ends = [_station(zone, "s_end_m", "s_end (m)") for zone in zones]
            if any(value is None for value in [*zone_starts, *zone_ends]):
                geometry_consistent = False
                break
            if abs(float(zone_starts[0]) - float(segment_start)) > tolerance or abs(float(zone_ends[-1]) - float(segment_end)) > tolerance:
                geometry_consistent = False
                break
            for zone_start, zone_end in zip(zone_starts, zone_ends):
                if float(zone_end) <= float(zone_start) + tolerance:
                    geometry_consistent = False
                    break
                if float(zone_start) < float(segment_start) - tolerance or float(zone_end) > float(segment_end) + tolerance:
                    geometry_consistent = False
                    break
            if not geometry_consistent:
                break
            for previous_end, current_start in zip(zone_ends, zone_starts[1:]):
                if abs(float(current_start) - float(previous_end)) > tolerance:
                    geometry_consistent = False
                    break
            if not geometry_consistent:
                break

    return {
        "extent_start_m": None if extent is None else extent[0],
        "extent_end_m": None if extent is None else extent[1],
        "layout_ids": sorted(segment_by_id),
        "zone_segment_ids": sorted(zones_by_segment),
        "one_zone_per_segment": one_zone_per_segment,
        "geometry_consistent": geometry_consistent,
        "aligned_one_to_one": geometry_consistent and one_zone_per_segment,
        "reset_supported": one_zone_per_segment,
    }


def crossbeam_project_geometry_audit(session_state: Mapping[str, Any]) -> dict[str, Any]:
    """Return a no-mutation station audit for restored Crossbeam inputs."""

    length_m = max(_number(session_state.get(CROSSBEAM_LENGTH_KEY), 0.0), 0.0)
    segment_rows = _records(session_state.get(CROSSBEAM_SEGMENT_ROWS_KEY))
    construction_method = str(
        session_state.get(CROSSBEAM_CONSTRUCTION_METHOD_KEY) or ""
    ).strip()
    cip_mode = construction_method == CONSTRUCTION_METHOD_CIP
    active_rebar_zone_key = (
        CROSSBEAM_CIP_REBAR_ZONE_ROWS_KEY
        if cip_mode
        else CROSSBEAM_REBAR_ZONE_ROWS_KEY
    )
    # Precast and Cast-in-Place reinforcement inputs are intentionally stored
    # independently.  Audit only the source owned by the active construction
    # mode; dormant assignments must never create a false geometry blocker.
    zone_rows = _records(session_state.get(active_rebar_zone_key))
    profile_rows = _records(session_state.get(CROSSBEAM_TENDON_PROFILE_ROWS_KEY))
    column_rows = _records(session_state.get(CROSSBEAM_COLUMN_ROWS_KEY))
    uls_rows = _records(session_state.get(CROSSBEAM_ULS_LOAD_ROWS_KEY))
    sls_rows = _records(session_state.get(CROSSBEAM_SLS_LOAD_ROWS_KEY))
    issues: list[dict[str, Any]] = []

    if length_m <= 0.0 or not segment_rows:
        return {
            "status": "NOT APPLICABLE",
            "length_m": length_m,
            "construction_method": construction_method,
            "active_rebar_zone_key": active_rebar_zone_key,
            "issues": [],
            "rebar": _rebar_alignment(segment_rows, zone_rows, length_m),
        }

    issues.extend(
        _coverage_issues(
            component="Segment Layout",
            rows=segment_rows,
            length_m=length_m,
            start_keys=("x_start_m", "s_start (m)"),
            end_keys=("x_end_m", "s_end (m)"),
            where_to_fix="Sections → Section Builder → Segment Layout",
        )
    )

    rebar = _rebar_alignment(segment_rows, zone_rows, length_m)
    if zone_rows and not rebar["geometry_consistent"]:
        start_m = rebar.get("extent_start_m")
        end_m = rebar.get("extent_end_m")
        tolerance = max(1e-6, abs(length_m) * 1e-6)
        extent_matches = (
            start_m is not None
            and end_m is not None
            and abs(float(start_m)) <= tolerance
            and abs(float(end_m) - length_m) <= tolerance
        )
        layout_ids = set(rebar.get("layout_ids") or [])
        zone_ids = set(rebar.get("zone_segment_ids") or [])
        if layout_ids != zone_ids:
            missing = sorted(layout_ids - zone_ids)
            extra = sorted(zone_ids - layout_ids)
            parts: list[str] = []
            if missing:
                parts.append("missing active IDs: " + ", ".join(missing))
            if extra:
                parts.append("inactive/dormant IDs: " + ", ".join(extra))
            detail = (
                "Rebar assignments do not match the active "
                + ("Section/Zone layout" if cip_mode else "Segment layout")
                + (" (" + "; ".join(parts) + ")." if parts else ".")
            )
        elif start_m is not None and end_m is not None and not extent_matches:
            detail = f"Rebar Zone extent = {float(start_m):.3f}–{float(end_m):.3f} m, but Crossbeam length = {length_m:.3f} m."
        elif extent_matches:
            detail = (
                "Rebar assignments span the full member but contain a gap, overlap, "
                "or boundary mismatch within the active layout."
            )
        else:
            detail = "Rebar Zone station extent cannot be read from the restored rows."
        issues.append(
            _issue(
                "Rebar Zones",
                detail,
                (
                    "Sections → Rebar → Section / Zone"
                    if cip_mode
                    else "Sections → Rebar → Segment / Zone"
                ),
                blocks_rebar_solver=True,
            )
        )

    # Tendon profiles are expected to span the member for each active tendon.
    active_tendon_ids = {
        str(row.get("Tendon ID") or "").strip()
        for row in _records(session_state.get(CROSSBEAM_TENDON_SYSTEM_ROWS_KEY))
        if bool(row.get("Active", True)) and str(row.get("Tendon ID") or "").strip()
    }
    grouped_profiles: dict[str, list[dict[str, Any]]] = {}
    for row in profile_rows:
        tendon_id = str(row.get("Tendon ID") or "").strip()
        if active_tendon_ids and tendon_id not in active_tendon_ids:
            continue
        grouped_profiles.setdefault(tendon_id or "(blank)", []).append(row)
    tolerance = max(1e-6, abs(length_m) * 1e-6)
    for tendon_id, rows in grouped_profiles.items():
        stations = [_station(row, "s (m)", "x_m", "Station s (m)") for row in rows]
        stations = [value for value in stations if value is not None]
        if stations and (abs(min(stations)) > tolerance or abs(max(stations) - length_m) > tolerance):
            issues.append(
                _issue(
                    "Tendon Profile",
                    f"{tendon_id} extent = {min(stations):.3f}–{max(stations):.3f} m, but Crossbeam length = {length_m:.3f} m.",
                    "Sections → Tendon Profile",
                )
            )

    for component, rows, where in (
        ("Column / Support", column_rows, "Sections → Section Builder → Column / Support Layout"),
        ("ULS Loads", uls_rows, "Loads → Crossbeam ULS"),
        ("SLS Loads", sls_rows, "Loads → Crossbeam SLS"),
    ):
        for row in rows:
            if not bool(row.get("Active", True)):
                continue
            station_m = _station(row, "Station s (m)", "s (m)", "x_m")
            if station_m is not None and (station_m < -tolerance or station_m > length_m + tolerance):
                issues.append(
                    _issue(
                        component,
                        f"Station {station_m:.3f} m lies outside Crossbeam 0.000–{length_m:.3f} m.",
                        where,
                    )
                )

    unique_issues: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        token = (str(issue.get("Component")), str(issue.get("Detail")))
        if token not in seen:
            seen.add(token)
            unique_issues.append(issue)
    return {
        "status": "READY" if not unique_issues else "INCONSISTENT",
        "length_m": length_m,
        "construction_method": construction_method,
        "active_rebar_zone_key": active_rebar_zone_key,
        "segment_count": len(segment_rows),
        "rebar_zone_count": len(zone_rows),
        "issues": unique_issues,
        "rebar": rebar,
    }
