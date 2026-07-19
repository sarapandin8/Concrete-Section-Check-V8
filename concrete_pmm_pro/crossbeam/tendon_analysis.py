"""Solver-neutral prestress force source audit for Crossbeam tendons.

CROSSBEAM.PTA1 derives the jacking force source from Tendon System rows and
joins that source to the Tendon Profile station audit.  It deliberately stops
at input traceability: no friction, wobble, anchorage set, elastic shortening,
time-dependent loss, SLS stress, ULS strength, anchorage-zone, deviator-force,
or D-region calculation is performed here.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.tendon import (
    canonical_tendon_system_rows,
    tendon_station_audit_rows,
)
from concrete_pmm_pro.crossbeam.workflow import calculated_fpj_mpa


DEFAULT_MINIMUM_ACTIVE_TENDONS = 3


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


def _deduplicated(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(str(message).strip() for message in messages if str(message).strip()))


def tendon_force_source_rows(system_values: Any) -> list[dict[str, Any]]:
    """Return per-tendon jacking-force source rows from Tendon System inputs.

    ``Pj`` is the tendon jacking-force magnitude at the source state:

    ``Pj (kN) = Aps total (mm2) x fpj (MPa) / 1000``.

    Both-end jacking is still one tendon force source; it is not doubled.
    """

    source_rows = canonical_tendon_system_rows(system_values)
    tendon_ids = [str(row.get("Tendon ID") or "").strip() for row in source_rows]
    duplicate_ids = {
        tendon_id
        for tendon_id in tendon_ids
        if tendon_id and tendon_ids.count(tendon_id) > 1
    }
    rows: list[dict[str, Any]] = []
    for tendon in source_rows:
        tendon_id = str(tendon.get("Tendon ID") or "").strip()
        active = bool(tendon.get("Active", True))
        strands = _int(tendon.get("Strands"), 0)
        aps_per_strand = _float(tendon.get("Aps/strand mm²"), 0.0)
        fpu_mpa = _float(tendon.get("fpu MPa"), 0.0)
        fpj_ratio = _float(tendon.get("fpj/fpu"), 0.0)
        fpj_mpa = calculated_fpj_mpa(fpu_mpa, fpj_ratio)
        aps_total = strands * aps_per_strand
        pj_kn = aps_total * fpj_mpa / 1000.0
        issues: list[str] = []
        if not tendon_id:
            issues.append("Tendon ID is required.")
        if tendon_id in duplicate_ids:
            issues.append("Duplicate Tendon ID cannot be used for force-source trace.")
        if strands <= 0:
            issues.append("Strands must be positive.")
        if aps_per_strand <= 0.0:
            issues.append("Aps/strand must be positive.")
        if aps_total <= 0.0:
            issues.append("Aps total is not positive.")
        if fpu_mpa <= 0.0:
            issues.append("fpu must be positive.")
        if not (0.0 < fpj_ratio <= 1.0):
            issues.append("fpj/fpu must be greater than 0 and no greater than 1.0.")
        if fpj_mpa <= 0.0:
            issues.append("fpj is not positive.")
        if pj_kn <= 0.0:
            issues.append("Pj is not positive.")

        status = "SOURCE READY"
        if issues:
            status = "REVIEW REQUIRED"
        elif not active:
            status = "STORED ONLY"

        rows.append(
            {
                "Tendon ID": tendon_id,
                "Active": active,
                "Type": str(tendon.get("Type") or ""),
                "Jacking end": str(tendon.get("Jacking end") or ""),
                "Strands": strands,
                "Strand system": str(tendon.get("Strand system") or ""),
                "Area source": "Strands x Aps/strand",
                "Aps/strand (mm²)": aps_per_strand,
                "Aps total (mm²)": aps_total,
                "fpu (MPa)": fpu_mpa,
                "fpj/fpu": fpj_ratio,
                "fpj (MPa)": fpj_mpa,
                "Pj (kN)": pj_kn,
                "Active Pj credit (kN)": pj_kn if active and not issues else 0.0,
                "Force source status": status,
                "Issue": "OK" if not issues else " ".join(_deduplicated(issues)),
            }
        )
    return rows


def tendon_force_source_summary(
    force_rows: Any,
    *,
    minimum_active_tendons: int = DEFAULT_MINIMUM_ACTIVE_TENDONS,
) -> dict[str, Any]:
    """Return dashboard-ready summary values for the PTA1 force source audit."""

    rows = _records(force_rows)
    stored_count = len(rows)
    active_count = sum(bool(row.get("Active")) for row in rows)
    review_count = sum(
        str(row.get("Force source status") or "").upper() == "REVIEW REQUIRED"
        for row in rows
    )
    total_active_aps = sum(
        _float(row.get("Aps total (mm²)"), 0.0)
        for row in rows
        if bool(row.get("Active"))
        and str(row.get("Force source status") or "").upper() != "REVIEW REQUIRED"
    )
    total_active_pj = sum(_float(row.get("Active Pj credit (kN)"), 0.0) for row in rows)
    issues: list[str] = []
    if stored_count == 0:
        issues.append("No Tendon System rows are available.")
    if active_count < int(minimum_active_tendons):
        issues.append(
            f"At least {int(minimum_active_tendons)} active tendons are required for the Crossbeam source audit."
        )
    if review_count:
        issues.append(f"{review_count} tendon force source row(s) require review.")
    ready = not issues
    return {
        "value": "SOURCE READY" if ready else "REVIEW REQUIRED",
        "status": "ready" if ready else "warning",
        "detail": f"{active_count} active tendon(s); active Pj = {total_active_pj:,.1f} kN",
        "stored_count": stored_count,
        "active_count": active_count,
        "review_count": review_count,
        "active_aps_total_mm2": total_active_aps,
        "active_pj_total_kN": total_active_pj,
        "issues": issues,
    }


def tendon_force_trace_rows(
    profile_values: Any,
    system_values: Any,
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
) -> list[dict[str, Any]]:
    """Join force-source rows to the station/profile audit rows."""

    force_by_id = {
        str(row.get("Tendon ID") or ""): row
        for row in tendon_force_source_rows(system_values)
        if str(row.get("Tendon ID") or "")
    }
    station_rows = tendon_station_audit_rows(
        profile_values,
        system_values,
        length_m=length_m,
        segment_rows=segment_rows,
        section_definitions=section_definitions,
    )
    trace_rows: list[dict[str, Any]] = []
    for station in station_rows:
        tendon_id = str(station.get("Tendon ID") or "")
        force = force_by_id.get(tendon_id)
        if force is None:
            force = {
                "Active": False,
                "Type": str(station.get("Type") or ""),
                "Jacking end": str(station.get("Jacking end") or ""),
                "Aps total (mm²)": 0.0,
                "fpj (MPa)": 0.0,
                "Pj (kN)": 0.0,
                "Active Pj credit (kN)": 0.0,
                "Force source status": "REVIEW REQUIRED",
                "Issue": "Tendon ID is missing from Tendon System.",
            }
        trace_rows.append(
            {
                "Tendon ID": tendon_id,
                "Active": bool(force.get("Active")),
                "Point": str(station.get("Point") or ""),
                "s (m)": _float(station.get("s (m)"), 0.0),
                "s/L": _float(station.get("s/L"), 0.0),
                "Segment": str(station.get("Segment") or ""),
                "Section ID": str(station.get("Section ID") or ""),
                "Station face": str(station.get("Station face") or ""),
                "x (mm)": _float(station.get("x (mm)"), 0.0),
                "dtop (mm)": _float(station.get("dtop (mm)"), 0.0),
                "e(s) (mm)": _float(station.get("e(s) (mm)"), 0.0),
                "Type": str(force.get("Type") or station.get("Type") or ""),
                "Jacking end": str(force.get("Jacking end") or station.get("Jacking end") or ""),
                "Aps total (mm²)": _float(force.get("Aps total (mm²)"), 0.0),
                "fpj (MPa)": _float(force.get("fpj (MPa)"), 0.0),
                "Pj (kN)": _float(force.get("Pj (kN)"), 0.0),
                "Active Pj credit (kN)": _float(force.get("Active Pj credit (kN)"), 0.0),
                "Force source status": str(force.get("Force source status") or "REVIEW REQUIRED"),
                "Issue": str(force.get("Issue") or ""),
            }
        )
    return trace_rows
