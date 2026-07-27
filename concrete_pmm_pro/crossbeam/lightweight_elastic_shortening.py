"""Lightweight AASHTO elastic-shortening design route for Crossbeam PT.

The production-oriented route intentionally avoids the detailed Gravity -> G1 -> ...
construction-stage contact history.  It performs one cumulative stressing-stage
solve using self-weight plus every accepted tendon force after Friction and
Anchorage Set, then evaluates concrete stress at the prestressing-steel centroid
using the AASHTO LRFD 5.9.3.2.3b bonded/unbonded routing.

The detailed incremental contact solver remains an optional construction-stage QA
route and is not required to obtain the ordinary design estimate.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.elastic_shortening import (
    elastic_shortening_station_rows,
    elastic_shortening_summary,
)
from concrete_pmm_pro.crossbeam.stressing_stage_contact import (
    solve_vertical_compression_contact,
)
from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    _beam_response_rows,
    _column_action_rows,
    prestress_equivalent_nodal_loads,
)
from concrete_pmm_pro.crossbeam.tendon import (
    TENDON_BOND_STATE_BONDED,
    TENDON_BOND_STATE_UNBONDED,
    canonical_tendon_profile_points,
    canonical_tendon_system_rows,
    tendon_bond_state_summary,
)

LIGHTWEIGHT_ES_METHOD = (
    "AASHTO SINGLE CUMULATIVE STAGE — ONE CONTACT SOLVE + GROUP FACTOR"
)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _records(values: Any) -> list[dict[str, Any]]:
    if hasattr(values, "to_dict"):
        try:
            return [
                dict(row)
                for row in values.to_dict(orient="records")
                if isinstance(row, Mapping)
            ]
        except (TypeError, ValueError):
            return []
    if isinstance(values, (list, tuple)):
        return [dict(row) for row in values if isinstance(row, Mapping)]
    return []


def _dedupe(messages: list[str]) -> list[str]:
    return list(
        dict.fromkeys(str(message).strip() for message in messages if str(message).strip())
    )


def _interpolate(points: list[tuple[float, float]], station: float) -> float | None:
    if not points:
        return None
    ordered = sorted(points)
    if station <= ordered[0][0]:
        return ordered[0][1]
    if station >= ordered[-1][0]:
        return ordered[-1][1]
    for (s0, v0), (s1, v1) in zip(ordered, ordered[1:]):
        if s0 <= station <= s1:
            if abs(s1 - s0) <= 1.0e-12:
                return v1
            ratio = (station - s0) / (s1 - s0)
            return v0 + ratio * (v1 - v0)
    return None


def _tendon_cg_depth_source(
    *, profile_rows: Any, system_rows: Any, length_m: float
) -> dict[str, Any]:
    system = [
        row
        for row in canonical_tendon_system_rows(system_rows)
        if bool(row.get("Active", True))
    ]
    aps_by_tendon = {
        str(row.get("Tendon ID") or "").strip(): max(
            int(round(_float(row.get("Strands"))))
            * _float(row.get("Aps/strand mm²")),
            0.0,
        )
        for row in system
        if str(row.get("Tendon ID") or "").strip()
    }
    profiles: dict[str, list[tuple[float, float]]] = {}
    for row in canonical_tendon_profile_points(profile_rows, length_m):
        tendon_id = str(row.get("Tendon ID") or "").strip()
        if tendon_id in aps_by_tendon:
            profiles.setdefault(tendon_id, []).append(
                (_float(row.get("s (m)")), _float(row.get("dtop (mm)")))
            )
    issues: list[str] = []
    for tendon_id, area in aps_by_tendon.items():
        if area <= 0.0:
            issues.append(f"{tendon_id}: prestressing-steel area is not positive.")
        if not profiles.get(tendon_id):
            issues.append(f"{tendon_id}: tendon profile is not available.")
    total_aps = sum(aps_by_tendon.values())

    def depth_at(station: float) -> float | None:
        if total_aps <= 0.0:
            return None
        weighted = 0.0
        for tendon_id, area in aps_by_tendon.items():
            depth = _interpolate(profiles.get(tendon_id, []), station)
            if depth is None:
                return None
            weighted += area * depth
        return weighted / total_aps

    return {
        "ready": bool(aps_by_tendon) and not issues and total_aps > 0.0,
        "issues": _dedupe(issues),
        "total_aps_mm2": total_aps,
        "depth_at": depth_at,
    }


def _stress_rows_at_tendon_cg(
    *, model: Mapping[str, Any], response_rows: list[dict[str, Any]], profile_rows: Any, system_rows: Any
) -> list[dict[str, Any]]:
    length_m = _float(model.get("length_m"))
    cg_source = _tendon_cg_depth_source(
        profile_rows=profile_rows, system_rows=system_rows, length_m=length_m
    )
    if not cg_source.get("ready"):
        return []
    depth_at = cg_source["depth_at"]
    section_sources = dict(model.get("section_sources") or {})
    output: list[dict[str, Any]] = []
    for row in response_rows:
        station = _float(row.get("s (m)"))
        section_id = str(row.get("Section ID") or "")
        section = section_sources.get(section_id)
        dtop = depth_at(station)
        if not section or dtop is None:
            continue
        area = _float(section.get("A_mm2"))
        inertia = _float(section.get("I_mm4"))
        centroid = _float(section.get("centroid_from_top_mm"))
        if area <= 0.0 or inertia <= 0.0:
            continue
        y_below = dtop - centroid
        n_n = _float(row.get("N compression-positive (kN)")) * 1000.0
        m_nmm = _float(row.get("M sagging-positive (kN-m)")) * 1.0e6
        axial = n_n / area
        bending = -m_nmm * y_below / inertia
        output.append(
            {
                "s (m)": station,
                "Element": str(row.get("Element") or ""),
                "Region": str(row.get("Region") or ""),
                "Section ID": section_id,
                "N (kN; compression +)": n_n / 1000.0,
                "M (kN-m; sagging +)": m_nmm / 1.0e6,
                "Tendon CG dtop (mm)": dtop,
                "y_p below section centroid (mm)": y_below,
                "N/A (MPa; compression +)": axial,
                "-M*y/I (MPa; compression +)": bending,
                "f_cgp (MPa; compression +)": axial + bending,
            }
        )
    output.sort(key=lambda item: (_float(item.get("s (m)")), str(item.get("Element") or "")))
    return output


def _rows_near_station(rows: list[dict[str, Any]], station: float, tolerance: float = 1.0e-7) -> list[dict[str, Any]]:
    exact = [row for row in rows if abs(_float(row.get("s (m)")) - station) <= tolerance]
    if exact:
        return exact
    if not rows:
        return []
    distance = min(abs(_float(row.get("s (m)")) - station) for row in rows)
    return [row for row in rows if abs(abs(_float(row.get("s (m)")) - station) - distance) <= tolerance]


def _bonded_fcgp_route(model: Mapping[str, Any], stress_rows: list[dict[str, Any]]) -> dict[str, Any]:
    columns = sorted(
        _float(row.get("Station s (m)")) for row in model.get("column_sources", [])
    )
    length_m = _float(model.get("length_m"))
    if len(columns) >= 2:
        left, right = columns[0], columns[-1]
        midspan = 0.5 * (left + right)
        clear_span_rows = [
            row for row in stress_rows if left - 1.0e-9 <= _float(row.get("s (m)")) <= right + 1.0e-9
        ]
        max_m_row = max(clear_span_rows, key=lambda row: abs(_float(row.get("M (kN-m; sagging +)"))), default=None)
        candidates = [
            ("Left column centerline", left),
            ("Span center", midspan),
            ("Right column centerline", right),
        ]
        if max_m_row is not None:
            candidates.append(("Maximum |M| within column lines", _float(max_m_row.get("s (m)"))))
    else:
        candidates = [("Member center", 0.5 * length_m)]

    candidate_rows: list[dict[str, Any]] = []
    for role, station in candidates:
        for row in _rows_near_station(stress_rows, station):
            candidate_rows.append({**row, "Evaluation role": role})
    # Duplicate roles/stations are harmless but make the audit noisy.
    unique: dict[tuple[str, float, str], dict[str, Any]] = {}
    for row in candidate_rows:
        key = (
            str(row.get("Evaluation role") or ""),
            round(_float(row.get("s (m)")), 9),
            str(row.get("Element") or ""),
        )
        unique[key] = row
    candidate_rows = list(unique.values())
    governing = max(
        candidate_rows,
        key=lambda row: _float(row.get("f_cgp (MPa; compression +)")),
        default=None,
    )
    return {
        "route": "BONDED — REPRESENTATIVE CONTINUOUS-MEMBER SECTION",
        "fcgp_mpa": max(_float(governing.get("f_cgp (MPa; compression +)")) if governing else 0.0, 0.0),
        "governing_row": governing,
        "evaluation_rows": candidate_rows,
        "note": (
            "Bonded post-tensioning route: evaluate the prestressing-steel centroid at the span center, column centerlines, and the maximum-|M| station between columns; use the governing compressive value."
        ),
    }


def _unbonded_fcgp_route(stress_rows: list[dict[str, Any]], length_m: float) -> dict[str, Any]:
    grouped: dict[float, list[float]] = {}
    for row in stress_rows:
        grouped.setdefault(round(_float(row.get("s (m)")), 9), []).append(
            _float(row.get("f_cgp (MPa; compression +)"))
        )
    points = sorted((station, sum(values) / len(values)) for station, values in grouped.items())
    integral = 0.0
    for (s0, f0), (s1, f1) in zip(points, points[1:]):
        integral += 0.5 * (f0 + f1) * (s1 - s0)
    average = integral / length_m if length_m > 0.0 and len(points) >= 2 else 0.0
    audit_rows = [
        {"s (m)": station, "f_cgp (MPa; compression +)": value}
        for station, value in points
    ]
    return {
        "route": "UNBONDED — MEMBER-LENGTH AVERAGE",
        "fcgp_mpa": max(average, 0.0),
        "governing_row": None,
        "evaluation_rows": audit_rows,
        "note": (
            "Permanently unbonded route: use the member-length average concrete stress at the prestressing-steel centroid."
        ),
    }


def run_crossbeam_lightweight_elastic_shortening(
    *,
    model: Mapping[str, Any],
    profile_rows: Any,
    system_rows: Any,
    anchorage_station_rows: Any,
    ordered_group_rows: Any,
    ep_mpa: float,
    eci_mpa: float,
) -> dict[str, Any]:
    """Run one cumulative contact solve and the simplified AASHTO ES estimate."""

    issues: list[str] = []
    if not bool(model.get("ready")):
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "issues": list(model.get("issues") or ["Frame model is not ready."]),
            "method": LIGHTWEIGHT_ES_METHOD,
            "solve_count": 0,
        }
    bond_summary = tendon_bond_state_summary(system_rows)
    if not bond_summary.get("ready"):
        issues.extend(bond_summary.get("issues") or ["Final tendon bond system is required."])

    active_system = [
        row
        for row in canonical_tendon_system_rows(system_rows)
        if bool(row.get("Active", True))
    ]
    bond_states = sorted({str(row.get("Bond state") or "") for row in active_system})
    if len(bond_states) > 1:
        issues.append(
            "The lightweight design route requires one common final bond system for all active Tendons; mixed systems require an engineer-specific evaluation."
        )

    load_source = prestress_equivalent_nodal_loads(
        model=model,
        profile_rows=profile_rows,
        anchorage_station_rows=anchorage_station_rows,
    )
    if not load_source.get("ready"):
        issues.extend(load_source.get("issues") or ["Cumulative post-anchor tendon load source is not ready."])

    if issues:
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "issues": _dedupe(issues),
            "method": LIGHTWEIGHT_ES_METHOD,
            "solve_count": 0,
            "bond_summary": bond_summary,
            "load_source": load_source,
        }

    contact_node_ids = sorted(
        int(value) for value in dict(model.get("beam_node_by_station") or {}).values()
    )
    contact = solve_vertical_compression_contact(
        nodes=list(model.get("nodes") or []),
        elements=list(model.get("elements") or []),
        contact_node_ids=contact_node_ids,
        nodal_loads=dict(load_source.get("nodal_loads") or {}),
        uniform_local_y_by_element=dict(model.get("self_weight_uniform_N_per_mm") or {}),
        fixed_node_ids=list(model.get("fixed_node_ids") or []),
    )
    solution = dict(contact.get("solution") or {})
    response_rows = _beam_response_rows(solution)
    solution["beam_response_rows"] = response_rows
    solution["column_action_rows"] = _column_action_rows(solution)
    contact["solution"] = solution
    contact["beam_response_rows"] = response_rows
    contact["column_action_rows"] = solution.get("column_action_rows", [])
    if not contact.get("ready"):
        issues.extend(contact.get("issues") or ["Cumulative compression-contact solve requires review."])

    stress_rows = _stress_rows_at_tendon_cg(
        model=model,
        response_rows=response_rows,
        profile_rows=profile_rows,
        system_rows=system_rows,
    )
    if not stress_rows:
        issues.append("Concrete stress at the prestressing-steel centroid could not be evaluated.")

    bond_state = bond_states[0] if bond_states else ""
    if bond_state == TENDON_BOND_STATE_BONDED:
        fcgp_route = _bonded_fcgp_route(model, stress_rows)
    elif bond_state == TENDON_BOND_STATE_UNBONDED:
        fcgp_route = _unbonded_fcgp_route(stress_rows, _float(model.get("length_m")))
    else:
        fcgp_route = {
            "route": "SOURCE BLOCKED",
            "fcgp_mpa": None,
            "evaluation_rows": [],
            "governing_row": None,
            "note": "Final tendon bond system is required.",
        }
        issues.append("Final tendon bond-system routing is unresolved.")

    fcgp = fcgp_route.get("fcgp_mpa")
    es_summary = elastic_shortening_summary(
        ordered_group_rows,
        ep_mpa=ep_mpa,
        eci_mpa=eci_mpa,
        fcgp_mpa=float(fcgp) if fcgp is not None else None,
    )
    if es_summary.get("average_loss_mpa") is None:
        issues.extend(es_summary.get("issues") or ["Elastic Shortening estimate is not available."])
    after_es_rows = elastic_shortening_station_rows(
        anchorage_station_rows, es_summary.get("sequence_rows", [])
    )

    ready = not issues and bool(contact.get("ready")) and es_summary.get("average_loss_mpa") is not None
    return {
        "status": "DESIGN ESTIMATE READY" if ready else "REVIEW REQUIRED",
        "ready": ready,
        "method": LIGHTWEIGHT_ES_METHOD,
        "issues": _dedupe(issues),
        "solve_count": 1,
        "bond_summary": bond_summary,
        "bond_state": bond_state,
        "load_source": load_source,
        "contact_result": contact,
        "stress_rows": stress_rows,
        "fcgp_route": fcgp_route,
        "fcgp_mpa": fcgp,
        "es_summary": es_summary,
        "after_es_station_rows": after_es_rows,
        "solver_boundary": (
            "Ordinary design estimate: one cumulative self-weight + accepted post-anchor tendon contact solve followed by the AASHTO identical-group sequence factor. Detailed G0→G4 contact history is optional construction-stage QA, not a prerequisite."
        ),
    }
