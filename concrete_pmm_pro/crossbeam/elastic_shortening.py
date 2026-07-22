"""Crossbeam PTLOSS3 elastic-shortening foundation.

This module keeps the Crossbeam implementation deliberately scoped to the
post-tensioned elastic-shortening component.  AASHTO LRFD 5.9.3.2.3b provides
an average sequential-stressing expression for identical post-tensioning
operations.  The Crossbeam construction intent stresses geometrically
symmetric tendon pairs simultaneously, so PTLOSS3 treats each verified pair as
one stressing *group* and applies the AASHTO sequential factor to the number of
verified equivalent groups, not blindly to the raw tendon count.

The stage concrete stress ``f_cgp`` remains an explicit source gate.  This
module does not invent a frame/self-weight moment or silently substitute a
prestress-only stress state.  Until a source-derived stressing-stage ``f_cgp``
is available, only an engineer-QA override may exercise the formula preview.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.tendon import (
    canonical_tendon_profile_points,
    canonical_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.workflow import calculated_fpj_mpa

AASHTO_PTL_ELASTIC_SHORTENING_BASIS = "AASHTO LRFD 5.9.3.2.3b"
PTLOSS3_PAIR_METHOD = "SIMULTANEOUS SYMMETRIC-PAIR STRESSING GROUPS"


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
    return list(dict.fromkeys(message.strip() for message in messages if message.strip()))


def _profile_by_tendon(profile_values: Any, length_m: float) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in canonical_tendon_profile_points(profile_values, length_m):
        tendon_id = str(row.get("Tendon ID") or "").strip()
        if tendon_id:
            grouped.setdefault(tendon_id, []).append(row)
    for tendon_id in grouped:
        grouped[tendon_id].sort(key=lambda row: (_float(row.get("s (m)")), str(row.get("Point") or "")))
    return grouped


def _mirror_profile_mismatch(
    left_points: list[Mapping[str, Any]],
    right_points: list[Mapping[str, Any]],
) -> tuple[float, float, float] | None:
    """Return max station/depth/mirror-lateral mismatch for a candidate pair."""

    if len(left_points) != len(right_points) or not left_points:
        return None
    station_error = 0.0
    depth_error = 0.0
    lateral_error = 0.0
    for left, right in zip(left_points, right_points):
        station_error = max(
            station_error,
            abs(_float(left.get("s (m)")) - _float(right.get("s (m)"))),
        )
        depth_error = max(
            depth_error,
            abs(_float(left.get("dtop (mm)")) - _float(right.get("dtop (mm)"))),
        )
        lateral_error = max(
            lateral_error,
            abs(_float(left.get("x lateral (mm)")) + _float(right.get("x lateral (mm)"))),
        )
    return station_error, depth_error, lateral_error


def symmetric_stressing_group_rows(
    profile_values: Any,
    system_values: Any,
    *,
    length_m: float,
    station_tolerance_m: float = 1.0e-6,
    coordinate_tolerance_mm: float = 1.0,
    force_tolerance_ratio: float = 0.005,
) -> list[dict[str, Any]]:
    """Return verified simultaneous symmetric tendon-pair stressing groups.

    Pairing is derived from the actual adopted profile geometry rather than from
    tendon names.  A valid pair must have mirrored lateral coordinates, matching
    longitudinal/depth profile points, the same tendon type, and effectively the
    same jacking-force source.  This protects the ES sequence factor from silently
    pairing unrelated tendons.
    """

    system = canonical_tendon_system_rows(system_values)
    profiles = _profile_by_tendon(profile_values, length_m)
    active = [row for row in system if bool(row.get("Active", True)) and str(row.get("Tendon ID") or "").strip()]
    order = {str(row.get("Tendon ID") or ""): index for index, row in enumerate(active)}

    def tendon_source(row: Mapping[str, Any]) -> dict[str, Any]:
        strands = max(int(round(_float(row.get("Strands"), 0.0))), 0)
        aps_per = max(_float(row.get("Aps/strand mm²"), 0.0), 0.0)
        fpj = calculated_fpj_mpa(_float(row.get("fpu MPa")), _float(row.get("fpj/fpu")))
        return {
            "tendon_id": str(row.get("Tendon ID") or ""),
            "type": str(row.get("Type") or ""),
            "aps_total": strands * aps_per,
            "fpj": fpj,
            "pj": strands * aps_per * fpj / 1000.0,
        }

    sources = {str(row.get("Tendon ID") or ""): tendon_source(row) for row in active}
    left_ids: list[str] = []
    right_ids: list[str] = []
    center_ids: list[str] = []
    for row in active:
        tendon_id = str(row.get("Tendon ID") or "")
        points = profiles.get(tendon_id, [])
        if not points:
            center_ids.append(tendon_id)
            continue
        avg_x = sum(_float(point.get("x lateral (mm)")) for point in points) / len(points)
        if avg_x < -coordinate_tolerance_mm:
            left_ids.append(tendon_id)
        elif avg_x > coordinate_tolerance_mm:
            right_ids.append(tendon_id)
        else:
            center_ids.append(tendon_id)

    used_right: set[str] = set()
    rows: list[dict[str, Any]] = []
    group_index = 0
    for left_id in sorted(left_ids, key=lambda item: order.get(item, 10**9)):
        left_points = profiles.get(left_id, [])
        left_source = sources[left_id]
        candidates: list[tuple[float, str, tuple[float, float, float], list[str]]] = []
        for right_id in right_ids:
            if right_id in used_right:
                continue
            right_points = profiles.get(right_id, [])
            mismatch = _mirror_profile_mismatch(left_points, right_points)
            if mismatch is None:
                continue
            right_source = sources[right_id]
            issues: list[str] = []
            if mismatch[0] > station_tolerance_m:
                issues.append("station profile mismatch")
            if mismatch[1] > coordinate_tolerance_mm:
                issues.append("depth profile mismatch")
            if mismatch[2] > coordinate_tolerance_mm:
                issues.append("lateral mirror mismatch")
            if left_source["type"] != right_source["type"]:
                issues.append("tendon type mismatch")
            max_pj = max(left_source["pj"], right_source["pj"], 1.0)
            if abs(left_source["pj"] - right_source["pj"]) / max_pj > force_tolerance_ratio:
                issues.append("jacking-force mismatch")
            score = mismatch[0] * 1.0e6 + mismatch[1] + mismatch[2]
            candidates.append((score, right_id, mismatch, issues))

        if not candidates:
            group_index += 1
            rows.append(
                {
                    "Group ID": f"G{group_index}",
                    "Sequence": group_index,
                    "Left tendon": left_id,
                    "Right tendon": "",
                    "Tendons": left_id,
                    "Tendon count": 1,
                    "Group Aps (mm²)": left_source["aps_total"],
                    "Group Pj (kN)": left_source["pj"],
                    "Status": "REVIEW REQUIRED",
                    "Issue": "No geometrically symmetric right-side tendon pair was found.",
                }
            )
            continue

        _score, right_id, mismatch, issues = min(candidates, key=lambda item: item[0])
        used_right.add(right_id)
        right_source = sources[right_id]
        group_index += 1
        status = "PAIR READY" if not issues else "REVIEW REQUIRED"
        rows.append(
            {
                "Group ID": f"G{group_index}",
                "Sequence": group_index,
                "Left tendon": left_id,
                "Right tendon": right_id,
                "Tendons": f"{left_id} + {right_id}",
                "Tendon count": 2,
                "Type": left_source["type"],
                "Group Aps (mm²)": left_source["aps_total"] + right_source["aps_total"],
                "Group Pj (kN)": left_source["pj"] + right_source["pj"],
                "Station mismatch (m)": mismatch[0],
                "Depth mismatch (mm)": mismatch[1],
                "Mirror-x mismatch (mm)": mismatch[2],
                "Status": status,
                "Issue": "OK" if not issues else "; ".join(issues),
            }
        )

    for right_id in sorted((item for item in right_ids if item not in used_right), key=lambda item: order.get(item, 10**9)):
        group_index += 1
        source = sources[right_id]
        rows.append(
            {
                "Group ID": f"G{group_index}",
                "Sequence": group_index,
                "Left tendon": "",
                "Right tendon": right_id,
                "Tendons": right_id,
                "Tendon count": 1,
                "Group Aps (mm²)": source["aps_total"],
                "Group Pj (kN)": source["pj"],
                "Status": "REVIEW REQUIRED",
                "Issue": "No geometrically symmetric left-side tendon pair was found.",
            }
        )

    for tendon_id in sorted(center_ids, key=lambda item: order.get(item, 10**9)):
        group_index += 1
        source = sources.get(tendon_id, {"aps_total": 0.0, "pj": 0.0})
        rows.append(
            {
                "Group ID": f"G{group_index}",
                "Sequence": group_index,
                "Left tendon": "",
                "Right tendon": "",
                "Tendons": tendon_id,
                "Tendon count": 1,
                "Group Aps (mm²)": source["aps_total"],
                "Group Pj (kN)": source["pj"],
                "Status": "REVIEW REQUIRED",
                "Issue": "Active tendon lies on/near the centerline or has no valid profile; symmetric-pair stressing is unresolved.",
            }
        )

    return rows


def stressing_group_summary(group_rows: Any, *, equivalence_tolerance_ratio: float = 0.005) -> dict[str, Any]:
    rows = _records(group_rows)
    issues = [str(row.get("Issue") or "") for row in rows if str(row.get("Status") or "") != "PAIR READY"]
    ready_rows = [row for row in rows if str(row.get("Status") or "") == "PAIR READY"]
    if not rows:
        issues.append("No active symmetric stressing groups are available.")
    if rows and len(ready_rows) != len(rows):
        issues.append("Every active tendon must belong to one verified symmetric stressing pair.")

    group_forces = [_float(row.get("Group Pj (kN)")) for row in ready_rows]
    equivalent = True
    if group_forces:
        reference = max(sum(group_forces) / len(group_forces), 1.0)
        equivalent = max(abs(value - reference) / reference for value in group_forces) <= equivalence_tolerance_ratio
    if ready_rows and not equivalent:
        issues.append(
            "AASHTO identical-group average factor is not released because symmetric stressing groups do not have equivalent total jacking force."
        )

    issues = _dedupe(issues)
    ready = bool(rows) and not issues and equivalent
    return {
        "status": "PAIR SOURCE READY" if ready else "REVIEW REQUIRED",
        "ready": ready,
        "group_count": len(ready_rows),
        "active_tendon_count": sum(int(row.get("Tendon count") or 0) for row in ready_rows),
        "equivalent_groups": equivalent and bool(ready_rows),
        "issues": issues,
    }


def average_sequence_factor(group_count: int) -> float:
    count = int(group_count)
    if count <= 0:
        raise ValueError("Stressing-group count must be positive.")
    return (count - 1.0) / (2.0 * count)


def group_sequence_factor(group_count: int, sequence_index: int) -> float:
    count = int(group_count)
    index = int(sequence_index)
    if count <= 0:
        raise ValueError("Stressing-group count must be positive.")
    if index < 1 or index > count:
        raise ValueError("Sequence index must be between 1 and the stressing-group count.")
    return (count - index) / count


def elastic_shortening_average_loss_mpa(
    *,
    group_count: int,
    ep_mpa: float,
    eci_mpa: float,
    fcgp_mpa: float,
) -> float:
    if ep_mpa <= 0.0 or eci_mpa <= 0.0 or fcgp_mpa < 0.0:
        raise ValueError("Ep and Eci must be positive and f_cgp must be nonnegative.")
    return average_sequence_factor(group_count) * (ep_mpa / eci_mpa) * fcgp_mpa


def elastic_shortening_sequence_rows(
    group_rows: Any,
    *,
    ep_mpa: float,
    eci_mpa: float,
    fcgp_mpa: float,
) -> list[dict[str, Any]]:
    rows = [row for row in _records(group_rows) if str(row.get("Status") or "") == "PAIR READY"]
    count = len(rows)
    if count <= 0:
        return []
    output: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        factor = group_sequence_factor(count, index)
        loss = factor * (ep_mpa / eci_mpa) * fcgp_mpa
        output.append(
            {
                **row,
                "Sequence": index,
                "Sequence factor": factor,
                "Ep/Eci": ep_mpa / eci_mpa,
                "f_cgp (MPa)": fcgp_mpa,
                "ΔfpES (MPa)": loss,
            }
        )
    return output


def elastic_shortening_summary(
    group_rows: Any,
    *,
    ep_mpa: float,
    eci_mpa: float,
    fcgp_mpa: float | None,
) -> dict[str, Any]:
    group_summary = stressing_group_summary(group_rows)
    if not group_summary["ready"]:
        return {
            **group_summary,
            "value": "SOURCE BLOCKED",
            "component_status": "SOURCE BLOCKED",
            "average_loss_mpa": None,
            "max_sequence_loss_mpa": None,
            "sequence_rows": [],
            "average_factor": None,
        }
    if fcgp_mpa is None:
        return {
            **group_summary,
            "value": "SOURCE BLOCKED",
            "component_status": "STAGE STRESS REQUIRED",
            "average_loss_mpa": None,
            "max_sequence_loss_mpa": None,
            "sequence_rows": [],
            "average_factor": average_sequence_factor(int(group_summary["group_count"])),
        }
    if ep_mpa <= 0.0 or eci_mpa <= 0.0 or fcgp_mpa < 0.0:
        return {
            **group_summary,
            "value": "REVIEW REQUIRED",
            "component_status": "REVIEW REQUIRED",
            "average_loss_mpa": None,
            "max_sequence_loss_mpa": None,
            "sequence_rows": [],
            "average_factor": average_sequence_factor(int(group_summary["group_count"])),
            "issues": _dedupe([*group_summary["issues"], "Ep/Eci/f_cgp source values are invalid."]),
        }

    sequence = elastic_shortening_sequence_rows(
        group_rows,
        ep_mpa=ep_mpa,
        eci_mpa=eci_mpa,
        fcgp_mpa=fcgp_mpa,
    )
    average = elastic_shortening_average_loss_mpa(
        group_count=int(group_summary["group_count"]),
        ep_mpa=ep_mpa,
        eci_mpa=eci_mpa,
        fcgp_mpa=fcgp_mpa,
    )
    return {
        **group_summary,
        "value": "PREVIEW READY",
        "component_status": "PREVIEW READY — STAGE SOURCE REVIEW",
        "average_loss_mpa": average,
        "max_sequence_loss_mpa": max((_float(row.get("ΔfpES (MPa)")) for row in sequence), default=0.0),
        "sequence_rows": sequence,
        "average_factor": average_sequence_factor(int(group_summary["group_count"])),
        "ep_over_eci": ep_mpa / eci_mpa,
        "fcgp_mpa": fcgp_mpa,
    }


def elastic_shortening_station_rows(
    anchorage_station_rows: Any,
    sequence_rows: Any,
) -> list[dict[str, Any]]:
    """Apply group-sequence ES component loss to the accepted post-anchor rows.

    The upstream ``P after anchorage set``/stress is never reconstructed from
    ``fpj``.  PTLOSS3 subtracts only the ES component from that accepted state,
    preserving the loss chain ``Pj -> friction -> anchorage set -> ES``.
    """

    loss_by_tendon: dict[str, float] = {}
    group_by_tendon: dict[str, str] = {}
    for row in _records(sequence_rows):
        loss = max(_float(row.get("ΔfpES (MPa)")), 0.0)
        group_id = str(row.get("Group ID") or "")
        for key in ("Left tendon", "Right tendon"):
            tendon_id = str(row.get(key) or "").strip()
            if tendon_id:
                loss_by_tendon[tendon_id] = loss
                group_by_tendon[tendon_id] = group_id

    output: list[dict[str, Any]] = []
    for row in _records(anchorage_station_rows):
        tendon_id = str(row.get("Tendon ID") or "").strip()
        stress_before = row.get("Stress after anchorage set (MPa)")
        force_before = row.get("P after anchorage set (kN)")
        aps_total = max(_float(row.get("Aps total (mm²)")), 0.0)
        loss = loss_by_tendon.get(tendon_id)
        if stress_before is None or force_before is None or loss is None or aps_total <= 0.0:
            output.append(
                {
                    **row,
                    "ES Group ID": group_by_tendon.get(tendon_id, ""),
                    "Elastic-shortening loss (MPa)": None,
                    "Elastic-shortening loss (kN)": None,
                    "Stress after ES (MPa)": None,
                    "P after ES (kN)": None,
                    "ES status": "NOT CALCULATED",
                }
            )
            continue
        final_stress = max(_float(stress_before) - loss, 0.0)
        loss_kn = aps_total * loss / 1000.0
        final_force = aps_total * final_stress / 1000.0
        output.append(
            {
                **row,
                "ES Group ID": group_by_tendon.get(tendon_id, ""),
                "Elastic-shortening loss (MPa)": loss,
                "Elastic-shortening loss (kN)": loss_kn,
                "Stress after ES (MPa)": final_stress,
                "P after ES (kN)": final_force,
                "ES status": "PREVIEW READY",
            }
        )
    return output
