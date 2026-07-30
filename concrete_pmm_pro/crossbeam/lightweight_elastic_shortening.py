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

import numpy as np

from concrete_pmm_pro.crossbeam.elastic_shortening import (
    elastic_shortening_station_rows,
    elastic_shortening_summary,
)
from concrete_pmm_pro.crossbeam.construction_stage import (
    canonical_column_stage_rows,
    column_loss_evaluation_regions,
)
from concrete_pmm_pro.crossbeam.stressing_stage_contact import (
    solve_vertical_compression_contact,
)
from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    _beam_response_rows,
    _column_action_rows,
    frame_rigid_offset_matrix,
    frame_transformation,
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
JOINT_EQUILIBRIUM_TOLERANCE = 1.0e-8


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
                "End / Side": str(row.get("End / Side") or ""),
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


def _limit_side_label(row: Mapping[str, Any]) -> str:
    raw = str(row.get("End / Side") or row.get("Limit side") or "").strip()
    normalized = raw.upper()
    if "LEFT LIMIT" in normalized or normalized.startswith("J-END"):
        return "LEFT LIMIT (s−)"
    if "RIGHT LIMIT" in normalized or normalized.startswith("I-END"):
        return "RIGHT LIMIT (s+)"
    if "INTERIOR" in normalized:
        return "INTERIOR SAMPLE"
    return "CENTERLINE SAMPLE"


def _reference_end_action_global(
    element: Mapping[str, Any], *, node_id: int
) -> np.ndarray | None:
    """Return the element action at one reference node in global DOF signs.

    The returned components are ``[Fx right+, Fy up+, M CCW+]``.  The action
    is the element resisting action at the shared reference node, including
    the exact centroid rigid-offset transformation used by the frame solve.
    """

    try:
        node_i = int(element.get("node_i"))
        node_j = int(element.get("node_j"))
    except (TypeError, ValueError):
        return None
    if node_id not in (node_i, node_j):
        return None
    actions = np.asarray(list(element.get("end_action_local") or []), dtype=float)
    if actions.shape != (6,):
        return None
    transform = frame_transformation(
        c=_float(element.get("c")),
        s=_float(element.get("s")),
    )
    rigid_offset = frame_rigid_offset_matrix(
        offset_i_y_mm=_float(element.get("offset_i_y_mm")),
        offset_j_y_mm=_float(element.get("offset_j_y_mm")),
    )
    reference_to_local = transform @ rigid_offset
    global_actions = reference_to_local.T @ actions
    return global_actions[:3] if node_id == node_i else global_actions[3:]


def _column_joint_equilibrium_audit(
    *,
    model: Mapping[str, Any],
    solution: Mapping[str, Any],
    explicit_nodal_loads: Mapping[int, tuple[float, float, float]] | None,
    tolerance: float = JOINT_EQUILIBRIUM_TOLERANCE,
) -> dict[str, Any]:
    """Audit one-sided beam limits against the column-top joint equilibrium.

    Element end actions already include each element's distributed load fixed-
    end contribution.  Therefore the local node balance is checked as:

    ``Σ(element resisting actions) − explicit nodal load − nodal reaction = 0``.

    Temporary-support contact reactions are included through the stored nodal
    reaction.  Prestress equivalent nodal actions are included through the
    explicit nodal-load source.
    """

    columns = canonical_column_stage_rows(
        model.get("column_sources", []),
        length_m=_float(model.get("length_m")),
    )
    node_by_station = {
        round(_float(station), 9): int(node_id)
        for station, node_id in dict(model.get("beam_node_by_station") or {}).items()
    }
    nodes = {
        int(row.get("id")): row
        for row in _records(solution.get("nodes"))
        if row.get("id") is not None
    }
    elements = _records(solution.get("elements"))
    explicit = dict(explicit_nodal_loads or {})
    rows: list[dict[str, Any]] = []

    for column in columns:
        column_id = str(column.get("Column ID") or "?")
        station = _float(column.get("Station s (m)"))
        node_id = node_by_station.get(round(station, 9))
        if node_id is None:
            rows.append(
                {
                    "Column": column_id,
                    "s (m)": station,
                    "Status": "REVIEW",
                    "Issue": "Column centerline is not present in the solved beam mesh.",
                }
            )
            continue

        contribution_rows: list[tuple[str, np.ndarray]] = []
        for element in elements:
            action = _reference_end_action_global(element, node_id=node_id)
            if action is None:
                continue
            kind = str(element.get("kind") or "")
            if kind == "beam":
                if int(element.get("node_j")) == node_id:
                    label = "Left beam (s−)"
                elif int(element.get("node_i")) == node_id:
                    label = "Right beam (s+)"
                else:
                    label = "Beam"
            elif kind == "column":
                label = "Column top"
            else:
                label = str(element.get("id") or kind or "Element")
            contribution_rows.append((label, action))

        node = nodes.get(node_id, {})
        applied = np.asarray(explicit.get(node_id, (0.0, 0.0, 0.0)), dtype=float)
        reaction = np.asarray(
            [
                _float(node.get("reaction_fx_N")),
                _float(node.get("reaction_fy_N")),
                _float(node.get("reaction_moment_Nmm")),
            ],
            dtype=float,
        )
        internal = (
            np.sum([action for _, action in contribution_rows], axis=0)
            if contribution_rows
            else np.zeros(3, dtype=float)
        )
        residual = internal - applied - reaction

        force_scale = max(
            sum(abs(action[0]) + abs(action[1]) for _, action in contribution_rows)
            + abs(applied[0])
            + abs(applied[1])
            + abs(reaction[0])
            + abs(reaction[1]),
            1.0,
        )
        moment_scale = max(
            sum(abs(action[2]) for _, action in contribution_rows)
            + abs(applied[2])
            + abs(reaction[2]),
            1.0,
        )
        force_ratio = float(np.hypot(residual[0], residual[1]) / force_scale)
        moment_ratio = float(abs(residual[2]) / moment_scale)
        residual_ratio = max(force_ratio, moment_ratio)

        by_label = {label: action for label, action in contribution_rows}
        has_column = "Column top" in by_label
        has_beam = any(label.startswith(("Left beam", "Right beam")) for label in by_label)
        status = (
            "PASS"
            if has_column and has_beam and residual_ratio <= tolerance
            else "REVIEW"
        )
        issue = (
            "OK"
            if status == "PASS"
            else "Joint connectivity or equilibrium residual requires review."
        )

        def component(label: str, index: int, divisor: float) -> float | None:
            action = by_label.get(label)
            return None if action is None else float(action[index] / divisor)

        rows.append(
            {
                "Column": column_id,
                "s (m)": station,
                "Left beam Fx (kN; right +)": component("Left beam (s−)", 0, 1000.0),
                "Left beam Fy (kN; up +)": component("Left beam (s−)", 1, 1000.0),
                "Left beam M (kN-m; CCW +)": component("Left beam (s−)", 2, 1.0e6),
                "Right beam Fx (kN; right +)": component("Right beam (s+)", 0, 1000.0),
                "Right beam Fy (kN; up +)": component("Right beam (s+)", 1, 1000.0),
                "Right beam M (kN-m; CCW +)": component("Right beam (s+)", 2, 1.0e6),
                "Column-top Fx (kN; right +)": component("Column top", 0, 1000.0),
                "Column-top Fy (kN; up +)": component("Column top", 1, 1000.0),
                "Column-top M (kN-m; CCW +)": component("Column top", 2, 1.0e6),
                "Explicit nodal Fx (kN)": float(applied[0] / 1000.0),
                "Explicit nodal Fy (kN)": float(applied[1] / 1000.0),
                "Explicit nodal M (kN-m)": float(applied[2] / 1.0e6),
                "Contact / restraint Rx (kN)": float(reaction[0] / 1000.0),
                "Contact / restraint Ry (kN)": float(reaction[1] / 1000.0),
                "Contact / restraint M (kN-m)": float(reaction[2] / 1.0e6),
                "Residual Fx (kN)": float(residual[0] / 1000.0),
                "Residual Fy (kN)": float(residual[1] / 1000.0),
                "Residual M (kN-m)": float(residual[2] / 1.0e6),
                "Residual ratio": residual_ratio,
                "Status": status,
                "Issue": issue,
            }
        )

    pass_count = sum(str(row.get("Status")) == "PASS" for row in rows)
    ready = bool(rows) and pass_count == len(rows)
    return {
        "status": "COLUMN-JOINT EQUILIBRIUM PASS" if ready else "COLUMN-JOINT EQUILIBRIUM REVIEW",
        "ready": ready,
        "count": len(rows),
        "pass_count": pass_count,
        "tolerance": tolerance,
        "rows": rows,
        "note": (
            "One-sided beam limit actions are balanced with the Column-top action, explicit prestress nodal action, and any active temporary-support contact reaction at the same frame joint."
        ),
    }


def _bonded_fcgp_route(model: Mapping[str, Any], stress_rows: list[dict[str, Any]]) -> dict[str, Any]:
    column_rows = canonical_column_stage_rows(
        model.get("column_sources", []),
        length_m=_float(model.get("length_m")),
    )
    length_m = _float(model.get("length_m"))
    candidate_rows: list[dict[str, Any]] = []
    for column in column_rows:
        station = _float(column.get("Station s (m)"))
        column_id = str(column.get("Column ID") or "?")
        for row in _rows_near_station(stress_rows, station):
            limit_side = _limit_side_label(row)
            candidate_rows.append(
                {
                    **row,
                    "Evaluation role": f"Column {column_id} centerline — {limit_side}",
                    "Evaluation class": "COLUMN",
                    "Evaluation ID": column_id,
                    "Limit side": limit_side,
                }
            )

    regions = column_loss_evaluation_regions(column_rows, length_m=length_m)
    for region in regions:
        start = _float(region.get("Start s (m)"))
        end = _float(region.get("End s (m)"))
        label = str(region.get("Region label") or "Region")
        midpoint = 0.5 * (start + end)
        for row in _rows_near_station(stress_rows, midpoint):
            candidate_rows.append(
                {
                    **row,
                    "Evaluation role": f"{label} midpoint",
                    "Evaluation class": "REGION MIDPOINT",
                    "Evaluation ID": str(region.get("Region ID") or label),
                    "Limit side": _limit_side_label(row),
                }
            )
        region_rows = [
            row
            for row in stress_rows
            if start - 1.0e-9 <= _float(row.get("s (m)")) <= end + 1.0e-9
        ]
        governing_region_row = max(
            region_rows,
            key=lambda row: _float(row.get("f_cgp (MPa; compression +)")),
            default=None,
        )
        if governing_region_row is not None:
            candidate_rows.append(
                {
                    **governing_region_row,
                    "Evaluation role": f"{label} governing f_cgp",
                    "Evaluation class": "REGION GOVERNING",
                    "Evaluation ID": str(region.get("Region ID") or label),
                    "Limit side": _limit_side_label(governing_region_row),
                }
            )

    if not candidate_rows and stress_rows:
        for row in _rows_near_station(stress_rows, 0.5 * length_m):
            candidate_rows.append(
                {
                    **row,
                    "Evaluation role": "Member center",
                    "Evaluation class": "MEMBER",
                    "Evaluation ID": "MEMBER",
                    "Limit side": _limit_side_label(row),
                }
            )
        governing_member_row = max(
            stress_rows,
            key=lambda row: _float(row.get("f_cgp (MPa; compression +)")),
            default=None,
        )
        if governing_member_row is not None:
            candidate_rows.append(
                {
                    **governing_member_row,
                    "Evaluation role": "Member governing f_cgp",
                    "Evaluation class": "MEMBER GOVERNING",
                    "Evaluation ID": "MEMBER",
                    "Limit side": _limit_side_label(governing_member_row),
                }
            )
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
    column_ids_evaluated = {
        str(row.get("Evaluation ID") or "")
        for row in candidate_rows
        if str(row.get("Evaluation class") or "") == "COLUMN"
    }
    region_midpoints = {
        str(row.get("Evaluation ID") or "")
        for row in candidate_rows
        if str(row.get("Evaluation class") or "") == "REGION MIDPOINT"
    }
    region_governing = {
        str(row.get("Evaluation ID") or "")
        for row in candidate_rows
        if str(row.get("Evaluation class") or "") == "REGION GOVERNING"
    }
    expected_column_ids = {
        str(row.get("Column ID") or "") for row in column_rows if str(row.get("Column ID") or "")
    }
    expected_region_ids = {
        str(row.get("Region ID") or "") for row in regions if str(row.get("Region ID") or "")
    }
    evaluated_region_ids = region_midpoints & region_governing
    bay_count = sum(str(row.get("Region type") or "") == "BAY" for row in regions)
    overhang_count = sum(
        str(row.get("Region type") or "") == "OVERHANG" for row in regions
    )
    expected_locations = len(expected_column_ids) + len(expected_region_ids)
    evaluated_locations = len(column_ids_evaluated & expected_column_ids) + len(
        evaluated_region_ids & expected_region_ids
    )
    coverage = {
        "ready": expected_locations > 0 and evaluated_locations == expected_locations,
        "columns_expected": len(expected_column_ids),
        "columns_evaluated": len(column_ids_evaluated & expected_column_ids),
        "bays_expected": bay_count,
        "overhangs_expected": overhang_count,
        "regions_expected": len(expected_region_ids),
        "regions_evaluated": len(evaluated_region_ids & expected_region_ids),
        "physical_locations_expected": expected_locations,
        "physical_locations_evaluated": evaluated_locations,
        "audit_row_count": len(candidate_rows),
    }
    governing = max(
        candidate_rows,
        key=lambda row: _float(row.get("f_cgp (MPa; compression +)")),
        default=None,
    )
    return {
        "route": "BONDED — ALL COLUMN / BAY REPRESENTATIVE SECTIONS",
        "fcgp_mpa": max(_float(governing.get("f_cgp (MPa; compression +)")) if governing else 0.0, 0.0),
        "governing_row": governing,
        "evaluation_rows": candidate_rows,
        "coverage": coverage,
        "note": (
            "Bonded post-tensioning route: evaluate the LEFT (s−) and RIGHT (s+) one-sided limits at every column centerline, every bay/overhang midpoint, and the actual governing f_cgp row within each region; use the governing compressive value."
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
    joint_equilibrium = _column_joint_equilibrium_audit(
        model=model,
        solution=solution,
        explicit_nodal_loads=dict(load_source.get("nodal_loads") or {}),
    )
    contact["column_joint_equilibrium"] = joint_equilibrium
    if not contact.get("ready"):
        issues.extend(contact.get("issues") or ["Cumulative compression-contact solve requires review."])
    if not joint_equilibrium.get("ready"):
        issues.append(
            "Column-joint one-sided beam actions do not close with the Column-top action, explicit prestress nodal action, and active contact reaction within the adopted equilibrium tolerance."
        )

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
        "column_joint_equilibrium": joint_equilibrium,
        "stress_rows": stress_rows,
        "fcgp_route": fcgp_route,
        "fcgp_mpa": fcgp,
        "es_summary": es_summary,
        "after_es_station_rows": after_es_rows,
        "solver_boundary": (
            "Ordinary design estimate: one cumulative self-weight + accepted post-anchor tendon contact solve followed by the AASHTO identical-group sequence factor. Detailed G0→G4 contact history is optional construction-stage QA, not a prerequisite."
        ),
    }
