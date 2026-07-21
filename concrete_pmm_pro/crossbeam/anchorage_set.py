"""Crossbeam post-tensioned anchorage-set / draw-in preview foundation.

PTLOSS2 keeps anchorage seating isolated from final effective prestress.  The
calculation consumes the already accepted friction/wobble station force diagram
and applies a force-diagram compatibility (area) method to estimate the local
zone affected by seating at an active stressing anchorage.

This module intentionally does *not* assemble Pe/Pe_eff, elastic shortening, or
time-dependent losses.  It also does not silently resolve overlapping two-end
seating zones or dead-end anchorage history; those conditions remain explicit
engineering-review items.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import exp, isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.prestress_loss import DEFAULT_PRESTRESS_STEEL_EP_MPA


ANCHORAGE_SET_METHOD_BASIS = (
    "AASHTO anchorage-set component; FHWA force-diagram area compatibility preview"
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
            rows = values.to_dict(orient="records")
            return [dict(row) for row in rows if isinstance(row, Mapping)]
        except (TypeError, ValueError):
            return []
    if isinstance(values, (list, tuple)):
        return [dict(row) for row in values if isinstance(row, Mapping)]
    return []


def _deduplicated(messages: list[str]) -> list[str]:
    return list(
        dict.fromkeys(
            str(message).strip() for message in messages if str(message).strip()
        )
    )


def _source_end_name(row: Mapping[str, Any]) -> str:
    source = str(row.get("Source end") or "").strip().casefold()
    if source.startswith("left"):
        return "Left"
    if source.startswith("right"):
        return "Right"
    return ""


def _active_seating_ends(jacking_end: str) -> tuple[str, ...]:
    normalized = str(jacking_end or "").strip().casefold()
    if normalized == "left":
        return ("Left",)
    if normalized == "right":
        return ("Right",)
    if normalized == "both":
        return ("Left", "Right")
    return ()


def _branch_limit_m(jacking_end: str, length_m: float) -> float:
    length = max(_float(length_m, 0.0), 0.0)
    return 0.5 * length if str(jacking_end or "").strip().casefold() == "both" else length


def _canonical_branch_rows(
    tendon_rows: list[dict[str, Any]],
    *,
    end: str,
    jacking_end: str,
    length_m: float,
) -> list[dict[str, float]]:
    """Return a monotone x-from-seating-end force diagram for one stressing end.

    The accepted PTLOSS1 station rows are treated as the force-diagram source of
    truth.  Between traced stations, PTLOSS2 uses linear diagram interpolation
    for the compatibility-area preview.  If a both-end branch has no point
    exactly at the branch limit, a synthetic limit point is extended from the
    last accepted station using only the already adopted K term (or zero for an
    external tendon), because no untraced profile vertex exists before the
    geometric branch limit.
    """

    target = str(end).strip().casefold()
    branch_limit = _branch_limit_m(jacking_end, length_m)
    selected: list[dict[str, float]] = []
    for row in tendon_rows:
        if _source_end_name(row).casefold() != target:
            continue
        x_m = max(_float(row.get("x from jack (m)"), 0.0), 0.0)
        if x_m > branch_limit + 1.0e-9:
            continue
        selected.append(
            {
                "x_m": x_m,
                "stress_mpa": max(_float(row.get("Stress after friction (MPa)"), 0.0), 0.0),
                "k_per_m": max(_float(row.get("K (/m)"), 0.0), 0.0),
            }
        )
    if not selected:
        return []

    by_x: dict[float, dict[str, float]] = {}
    for row in sorted(selected, key=lambda item: item["x_m"]):
        by_x[round(row["x_m"], 9)] = row
    rows = [by_x[key] for key in sorted(by_x)]

    # A stressing-end branch must start at the anchorage.  Do not invent the
    # anchorage force if the accepted friction trace itself is incomplete.
    if rows[0]["x_m"] > 1.0e-8:
        return rows

    if branch_limit > rows[-1]["x_m"] + 1.0e-9:
        dx = branch_limit - rows[-1]["x_m"]
        k_per_m = rows[-1]["k_per_m"]
        end_stress = rows[-1]["stress_mpa"] * exp(-k_per_m * dx)
        rows.append(
            {
                "x_m": branch_limit,
                "stress_mpa": max(end_stress, 0.0),
                "k_per_m": k_per_m,
            }
        )
    elif abs(branch_limit - rows[-1]["x_m"]) <= 1.0e-9:
        rows[-1]["x_m"] = branch_limit
    return rows


def _diagram_stress_mpa(branch_rows: list[dict[str, float]], x_m: float) -> float:
    if not branch_rows:
        return 0.0
    x = max(_float(x_m, 0.0), 0.0)
    if x <= branch_rows[0]["x_m"]:
        return branch_rows[0]["stress_mpa"]
    for left, right in zip(branch_rows, branch_rows[1:]):
        if x <= right["x_m"] + 1.0e-12:
            dx = right["x_m"] - left["x_m"]
            if dx <= 1.0e-12:
                return right["stress_mpa"]
            ratio = min(max((x - left["x_m"]) / dx, 0.0), 1.0)
            return left["stress_mpa"] + ratio * (
                right["stress_mpa"] - left["stress_mpa"]
            )
    return branch_rows[-1]["stress_mpa"]


def _diagram_integral_mpa_m(branch_rows: list[dict[str, float]], x_m: float) -> float:
    """Return integral of the linearly interpolated accepted stress diagram."""

    if not branch_rows:
        return 0.0
    target = min(max(_float(x_m, 0.0), 0.0), branch_rows[-1]["x_m"])
    area = 0.0
    for left, right in zip(branch_rows, branch_rows[1:]):
        if target <= left["x_m"]:
            break
        segment_end = min(target, right["x_m"])
        dx = segment_end - left["x_m"]
        if dx <= 0.0:
            continue
        full_dx = right["x_m"] - left["x_m"]
        if full_dx <= 1.0e-12:
            continue
        end_stress = left["stress_mpa"] + (dx / full_dx) * (
            right["stress_mpa"] - left["stress_mpa"]
        )
        area += 0.5 * (left["stress_mpa"] + end_stress) * dx
        if segment_end >= target - 1.0e-12:
            break
    return area


def _compatibility_set_mm(
    branch_rows: list[dict[str, float]],
    *,
    influence_length_m: float,
    ep_mpa: float,
) -> float:
    """Return seating movement compatible with a mirrored force diagram.

    For the graphical mirror approximation, the stress reduction inside the
    affected length ``La`` is ``2 * (f_i(x) - f_i(La))``.  Integrating that
    strain change along the tendon gives the anchorage movement.
    """

    ep = max(_float(ep_mpa, 0.0), 0.0)
    la = max(_float(influence_length_m, 0.0), 0.0)
    if not branch_rows or ep <= 0.0 or la <= 0.0:
        return 0.0
    f_zero = _diagram_stress_mpa(branch_rows, la)
    integral = _diagram_integral_mpa_m(branch_rows, la)
    stress_area = max(integral - la * f_zero, 0.0)
    return 2.0 * 1000.0 * stress_area / ep


def _solve_influence_length_m(
    branch_rows: list[dict[str, float]],
    *,
    branch_limit_m: float,
    anchor_set_mm: float,
    ep_mpa: float,
) -> tuple[float | None, float, float]:
    """Return influence length, max compatible set, and compatibility residual."""

    target = max(_float(anchor_set_mm, 0.0), 0.0)
    limit = max(_float(branch_limit_m, 0.0), 0.0)
    if not branch_rows or target <= 0.0 or limit <= 0.0 or ep_mpa <= 0.0:
        return None, 0.0, target

    max_set = _compatibility_set_mm(
        branch_rows,
        influence_length_m=limit,
        ep_mpa=ep_mpa,
    )
    tolerance = max(1.0e-5, target * 1.0e-5)
    if max_set + tolerance < target:
        return None, max_set, target - max_set

    low = 0.0
    high = limit
    for _ in range(100):
        mid = 0.5 * (low + high)
        value = _compatibility_set_mm(
            branch_rows,
            influence_length_m=mid,
            ep_mpa=ep_mpa,
        )
        if value < target:
            low = mid
        else:
            high = mid
    influence = 0.5 * (low + high)
    achieved = _compatibility_set_mm(
        branch_rows,
        influence_length_m=influence,
        ep_mpa=ep_mpa,
    )
    return influence, max_set, achieved - target


def anchorage_set_end_rows(
    friction_rows: Any,
    *,
    length_m: float,
    anchor_set_mm: float,
    ep_mpa: float = DEFAULT_PRESTRESS_STEEL_EP_MPA,
) -> list[dict[str, Any]]:
    """Return one anchorage-seating preview row per active stressing end.

    The input is the accepted friction/wobble force diagram.  A positive
    ``anchor_set_mm`` is intentionally required; zero means that a project/PT
    supplier value has not yet been adopted and the component remains locked.
    """

    rows = _records(friction_rows)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("Tendon ID") or ""), []).append(row)

    result: list[dict[str, Any]] = []
    adopted_set = max(_float(anchor_set_mm, 0.0), 0.0)
    ep = max(_float(ep_mpa, DEFAULT_PRESTRESS_STEEL_EP_MPA), 0.0)
    length = max(_float(length_m, 0.0), 0.0)

    for tendon_id, tendon_rows in sorted(grouped.items()):
        if not tendon_rows:
            continue
        first = tendon_rows[0]
        active = any(bool(row.get("Active")) for row in tendon_rows)
        tendon_type = str(first.get("Type") or "")
        jacking_end = str(first.get("Jacking end") or "")
        aps_total = max(_float(first.get("Aps total (mm²)"), 0.0), 0.0)
        pj_kn = max(_float(first.get("Pj (kN)"), 0.0), 0.0)
        fpj_mpa = max(_float(first.get("fpj (MPa)"), 0.0), 0.0)
        friction_blocking = _deduplicated(
            [
                str(row.get("Blocking issue") or "")
                for row in tendon_rows
                if str(row.get("Blocking issue") or "").strip()
            ]
        )
        friction_notes = _deduplicated(
            [
                str(row.get("Review note") or "")
                for row in tendon_rows
                if str(row.get("Review note") or "").strip()
            ]
        )
        ends = _active_seating_ends(jacking_end)
        if not ends:
            ends = ("Unknown",)

        for end in ends:
            issues: list[str] = list(friction_blocking)
            notes: list[str] = list(friction_notes)
            if not active:
                status = "STORED ONLY"
            else:
                status = "PREVIEW READY"
            if adopted_set <= 0.0:
                issues.append(
                    "Adopt a positive project/PT supplier anchorage-set value before calculating draw-in loss."
                )
            if ep <= 0.0:
                issues.append("Positive prestressing-steel modulus Ep is required.")
            if aps_total <= 0.0 or pj_kn <= 0.0 or fpj_mpa <= 0.0:
                issues.append("Positive Aps, fpj, and Pj are required from the tendon force source.")
            if end == "Unknown":
                issues.append("Jacking end must be Left, Right, or Both.")

            branch_limit = _branch_limit_m(jacking_end, length)
            branch_rows = (
                _canonical_branch_rows(
                    tendon_rows,
                    end=end,
                    jacking_end=jacking_end,
                    length_m=length,
                )
                if end in {"Left", "Right"}
                else []
            )
            if active and end in {"Left", "Right"}:
                if not branch_rows:
                    issues.append(f"Accepted friction trace has no {end.lower()}-end branch.")
                elif branch_rows[0]["x_m"] > 1.0e-8:
                    issues.append(
                        f"Accepted friction trace does not start at the {end.lower()} anchorage (x = 0)."
                    )

            influence: float | None = None
            max_compatible_set = 0.0
            residual = adopted_set
            zero_movement_stress: float | None = None
            lockoff_stress: float | None = None
            lockoff_force: float | None = None
            anchor_loss_mpa: float | None = None
            anchor_loss_kn: float | None = None
            anchor_loss_percent: float | None = None
            stress_integral_mpa_m: float | None = None
            one_side_stress_area_mpa_m: float | None = None
            mirrored_stress_area_mpa_m: float | None = None
            compatibility_set_check_mm: float | None = None

            if branch_rows and adopted_set > 0.0 and ep > 0.0:
                influence, max_compatible_set, residual = _solve_influence_length_m(
                    branch_rows,
                    branch_limit_m=branch_limit,
                    anchor_set_mm=adopted_set,
                    ep_mpa=ep,
                )
                if influence is None:
                    issues.append(
                        "Required seating movement exceeds the compatibility capacity of the current isolated branch; full-length/opposing-end interaction requires a later stressing-sequence solver."
                    )
                else:
                    zero_movement_stress = _diagram_stress_mpa(branch_rows, influence)
                    anchor_initial = _diagram_stress_mpa(branch_rows, 0.0)
                    stress_integral_mpa_m = _diagram_integral_mpa_m(branch_rows, influence)
                    one_side_stress_area_mpa_m = max(
                        stress_integral_mpa_m - influence * zero_movement_stress,
                        0.0,
                    )
                    mirrored_stress_area_mpa_m = 2.0 * one_side_stress_area_mpa_m
                    compatibility_set_check_mm = (
                        1000.0 * mirrored_stress_area_mpa_m / ep if ep > 0.0 else None
                    )
                    lockoff_stress = 2.0 * zero_movement_stress - anchor_initial
                    if lockoff_stress < -1.0e-6:
                        issues.append(
                            "Mirrored force diagram gives negative anchorage stress; adopted seating value is outside the valid preview range."
                        )
                    lockoff_stress = max(lockoff_stress, 0.0)
                    anchor_loss_mpa = max(anchor_initial - lockoff_stress, 0.0)
                    anchor_loss_kn = aps_total * anchor_loss_mpa / 1000.0
                    lockoff_force = aps_total * lockoff_stress / 1000.0
                    anchor_loss_percent = (
                        100.0 * anchor_loss_kn / pj_kn if pj_kn > 0.0 else None
                    )

            if str(jacking_end).strip().casefold() in {"left", "right"}:
                notes.append(
                    "This milestone models final seating at the active stressing end only; dead-end anchorage seating/history must be verified from the actual PT procedure."
                )
            if str(jacking_end).strip().casefold() == "both":
                notes.append(
                    "Both-end seating is treated as independent local branches and is valid only while each influence zone remains inside its half-length branch."
                )
            notes.append(
                "PTLOSS2 uses linear interpolation of the accepted friction/wobble force diagram for compatibility-area audit; it is not final Pe/Pe_eff."
            )

            if not active:
                status = "STORED ONLY"
            elif adopted_set <= 0.0:
                status = "INPUT REQUIRED"
            elif issues:
                status = "REVIEW REQUIRED"
            elif notes:
                status = "PREVIEW READY + NOTE"
            else:
                status = "PREVIEW READY"

            result.append(
                {
                    "Tendon ID": tendon_id,
                    "Active": active,
                    "Type": tendon_type,
                    "Jacking end": jacking_end,
                    "Seating end": end,
                    "Anchorage set (mm)": adopted_set,
                    "Ep (MPa)": ep,
                    "Aps total (mm²)": aps_total,
                    "fpj (MPa)": fpj_mpa,
                    "Pj (kN)": pj_kn,
                    "Branch limit (m)": branch_limit,
                    "Branch points": len(branch_rows),
                    "Max compatible set (mm)": max_compatible_set,
                    "Influence length (m)": influence,
                    "Initial stress at anchorage after friction (MPa)": (
                        _diagram_stress_mpa(branch_rows, 0.0) if branch_rows else None
                    ),
                    "Zero movement stress (MPa)": zero_movement_stress,
                    "Stress integral to La (MPa·m)": stress_integral_mpa_m,
                    "One-side stress area (MPa·m)": one_side_stress_area_mpa_m,
                    "Mirrored stress-difference area (MPa·m)": mirrored_stress_area_mpa_m,
                    "Compatibility set check (mm)": compatibility_set_check_mm,
                    "Lock-off stress at anchorage (MPa)": lockoff_stress,
                    "Lock-off force at anchorage (kN)": lockoff_force,
                    "Anchorage-set loss at anchorage (MPa)": anchor_loss_mpa,
                    "Anchorage-set loss at anchorage (kN)": anchor_loss_kn,
                    "Anchorage-set loss at anchorage (%)": anchor_loss_percent,
                    "Compatibility residual (mm)": residual,
                    "Method": ANCHORAGE_SET_METHOD_BASIS,
                    "Status": status,
                    "Blocking issue": " ".join(_deduplicated(issues)),
                    "Review note": " ".join(_deduplicated(notes)),
                    "Issue": "OK" if not issues and not notes else " ".join(_deduplicated(issues + notes)),
                }
            )
    return result


def anchorage_set_station_rows(
    friction_rows: Any,
    end_rows: Any,
    *,
    length_m: float | None = None,
) -> list[dict[str, Any]]:
    """Return station trace after the isolated anchorage-set component.

    Rows remain explicitly component-scoped.  ``P after anchorage set`` is not
    exported as Pe/Pe_eff and is left blank whenever the corresponding seating
    end has no valid influence-length solution.
    """

    rows = _records(friction_rows)
    ends = _records(end_rows)
    end_map = {
        (str(row.get("Tendon ID") or ""), str(row.get("Seating end") or "")): row
        for row in ends
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("Tendon ID") or ""), []).append(row)

    branch_cache: dict[tuple[str, str], list[dict[str, float]]] = {}
    for tendon_id, tendon_rows in grouped.items():
        if not tendon_rows:
            continue
        jacking_end = str(tendon_rows[0].get("Jacking end") or "")
        tendon_length_m = (
            max(_float(length_m, 0.0), 0.0)
            if length_m is not None
            else max(_float(row.get("s (m)"), 0.0) for row in tendon_rows)
        )
        for end in _active_seating_ends(jacking_end):
            branch_cache[(tendon_id, end)] = _canonical_branch_rows(
                tendon_rows,
                end=end,
                jacking_end=jacking_end,
                length_m=tendon_length_m,
            )

    output: list[dict[str, Any]] = []
    for row in rows:
        tendon_id = str(row.get("Tendon ID") or "")
        end = _source_end_name(row)
        end_result = end_map.get((tendon_id, end))
        friction_stress = max(_float(row.get("Stress after friction (MPa)"), 0.0), 0.0)
        friction_force = max(_float(row.get("P after friction (kN)"), 0.0), 0.0)
        aps_total = max(_float(row.get("Aps total (mm²)"), 0.0), 0.0)
        x_m = max(_float(row.get("x from jack (m)"), 0.0), 0.0)
        final_stress: float | None = None
        final_force: float | None = None
        component_loss_mpa: float | None = None
        component_loss_kn: float | None = None
        influence_length: float | None = None
        zero_stress: float | None = None
        applied = False
        status = "NOT CALCULATED"
        issue = "No valid anchorage-set solution is available for this source-end branch."

        if end_result is not None:
            influence_raw = end_result.get("Influence length (m)")
            influence_length = (
                _float(influence_raw, 0.0) if influence_raw is not None else None
            )
            zero_raw = end_result.get("Zero movement stress (MPa)")
            zero_stress = _float(zero_raw, 0.0) if zero_raw is not None else None
            status = str(end_result.get("Status") or "NOT CALCULATED")
            issue = str(end_result.get("Issue") or "")
            if influence_length is not None and zero_stress is not None:
                branch = branch_cache.get((tendon_id, end), [])
                initial_diagram_stress = _diagram_stress_mpa(branch, x_m) if branch else friction_stress
                if x_m <= influence_length + 1.0e-9:
                    final_stress = max(2.0 * zero_stress - initial_diagram_stress, 0.0)
                    applied = True
                else:
                    final_stress = friction_stress
                component_loss_mpa = max(friction_stress - final_stress, 0.0)
                final_force = aps_total * final_stress / 1000.0
                component_loss_kn = max(friction_force - final_force, 0.0)

        output.append(
            {
                **row,
                "Seating end": end,
                "Anchorage set applied": applied,
                "Influence length (m)": influence_length,
                "Anchorage-set loss (MPa)": component_loss_mpa,
                "Anchorage-set loss (kN)": component_loss_kn,
                "Stress after anchorage set (MPa)": final_stress,
                "P after anchorage set (kN)": final_force,
                "Anchorage-set status": status,
                "Anchorage-set issue": issue,
            }
        )
    return output


def anchorage_set_summary(end_rows: Any) -> dict[str, Any]:
    """Return dashboard values for the isolated PTLOSS2 component."""

    rows = _records(end_rows)
    active = [row for row in rows if bool(row.get("Active"))]
    input_required = [row for row in active if str(row.get("Status") or "") == "INPUT REQUIRED"]
    review = [row for row in active if str(row.get("Status") or "") == "REVIEW REQUIRED"]
    calculated = [
        row
        for row in active
        if row.get("Influence length (m)") is not None
        and row.get("Anchorage-set loss at anchorage (kN)") is not None
    ]
    if input_required:
        value = "INPUT REQUIRED"
        status = "warning"
    elif review:
        value = "REVIEW REQUIRED"
        status = "warning"
    elif active:
        value = "PREVIEW READY"
        status = "ready"
    else:
        value = "NO ACTIVE TENDONS"
        status = "warning"

    loss_percents = [
        _float(row.get("Anchorage-set loss at anchorage (%)"), 0.0)
        for row in calculated
        if row.get("Anchorage-set loss at anchorage (%)") is not None
    ]
    influence_lengths = [
        _float(row.get("Influence length (m)"), 0.0)
        for row in calculated
        if row.get("Influence length (m)") is not None
    ]
    issues = _deduplicated(
        [
            str(row.get("Blocking issue") or "")
            for row in active
            if str(row.get("Blocking issue") or "").strip()
        ]
    )
    notes = _deduplicated(
        [
            str(row.get("Review note") or "")
            for row in active
            if str(row.get("Review note") or "").strip()
        ]
    )
    return {
        "value": value,
        "status": status,
        "active_tendon_count": len({str(row.get("Tendon ID") or "") for row in active}),
        "active_seating_end_count": len(active),
        "calculated_end_count": len(calculated),
        "input_required_end_count": len(input_required),
        "review_end_count": len(review),
        "worst_anchor_loss_percent": max(loss_percents, default=0.0),
        "max_influence_length_m": max(influence_lengths, default=0.0),
        "blocking_issues": issues,
        "review_notes": notes,
    }
