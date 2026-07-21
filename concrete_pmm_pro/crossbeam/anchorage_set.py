"""Crossbeam post-tensioned anchorage-set / draw-in interaction preview.

PTLOSS2C keeps anchorage seating isolated from final effective prestress. The
calculation consumes the accepted PTLOSS1 friction/wobble force diagram and
first attempts the local force-diagram compatibility (area) method at each
stressing anchorage. For both-end jacking, when the adopted seating movement
exceeds the independent half-length branch capacity, a guarded full-length
coupled compatibility extension solves a common neutral/meeting station from
the accepted left- and right-jacking branch traces.

The coupled solution is an engineering implementation extension of the FHWA
graphical mirror-image/area compatibility concept, not a verbatim numbered
AASHTO equation and not an explicit first-end/second-end stressing-sequence
simulation. This module intentionally does *not* assemble Pe/Pe_eff, elastic
shortening, time-dependent losses, or dead-end anchorage history.
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
    normalized_jack = str(jacking_end or "").strip().casefold()
    branch_field = (
        "Stress from left jack (MPa)" if target == "left" else "Stress from right jack (MPa)"
    )
    has_full_branch_trace = normalized_jack == "both" and any(
        row.get(branch_field) is not None for row in tendon_rows
    )
    for row in tendon_rows:
        if has_full_branch_trace:
            station_m = min(
                max(_float(row.get("s (m)"), 0.0), 0.0),
                max(_float(length_m, 0.0), 0.0),
            )
            x_m = station_m if target == "left" else max(_float(length_m, 0.0) - station_m, 0.0)
            stress_mpa = max(_float(row.get(branch_field), 0.0), 0.0)
        else:
            if _source_end_name(row).casefold() != target:
                continue
            x_m = max(_float(row.get("x from jack (m)"), 0.0), 0.0)
            stress_mpa = max(_float(row.get("Stress after friction (MPa)"), 0.0), 0.0)
        if x_m > branch_limit + 1.0e-9:
            continue
        selected.append(
            {
                "x_m": x_m,
                "stress_mpa": stress_mpa,
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



def _canonical_full_tendon_rows(
    tendon_rows: list[dict[str, Any]],
    *,
    length_m: float,
) -> list[dict[str, float]]:
    """Return full-tendon accepted/left/right stress traces for PTLOSS2C.

    PTLOSS1 keeps the accepted both-end force as the nearest-jacking-end value.
    PTLOSS2C additionally consumes the additive left/right jack branch stresses
    written by PTLOSS1 so a coupled seating interaction can be solved without
    changing that accepted pre-seating force diagram.
    """

    length = max(_float(length_m, 0.0), 0.0)
    by_s: dict[float, dict[str, float]] = {}
    for row in tendon_rows:
        station = min(max(_float(row.get("s (m)"), 0.0), 0.0), length)
        left_raw = row.get("Stress from left jack (MPa)")
        right_raw = row.get("Stress from right jack (MPa)")
        if left_raw is None or right_raw is None:
            continue
        by_s[round(station, 9)] = {
            "s_m": station,
            "initial_mpa": max(_float(row.get("Stress after friction (MPa)"), 0.0), 0.0),
            "left_mpa": max(_float(left_raw, 0.0), 0.0),
            "right_mpa": max(_float(right_raw, 0.0), 0.0),
        }
    rows = [by_s[key] for key in sorted(by_s)]
    if not rows:
        return []
    if rows[0]["s_m"] > 1.0e-8 or abs(rows[-1]["s_m"] - length) > 1.0e-8:
        return []
    rows[0]["s_m"] = 0.0
    rows[-1]["s_m"] = length
    return rows


def _full_trace_value(
    rows: list[dict[str, float]],
    station_m: float,
    field: str,
) -> float:
    if not rows:
        return 0.0
    x = min(max(_float(station_m, 0.0), rows[0]["s_m"]), rows[-1]["s_m"])
    if x <= rows[0]["s_m"]:
        return rows[0][field]
    for left, right in zip(rows, rows[1:]):
        if x <= right["s_m"] + 1.0e-12:
            dx = right["s_m"] - left["s_m"]
            if dx <= 1.0e-12:
                return right[field]
            ratio = min(max((x - left["s_m"]) / dx, 0.0), 1.0)
            return left[field] + ratio * (right[field] - left[field])
    return rows[-1][field]


def _full_trace_integral(
    rows: list[dict[str, float]],
    start_m: float,
    end_m: float,
    field: str,
) -> float:
    """Integrate a piecewise-linear full-tendon trace in MPa.m."""

    if not rows:
        return 0.0
    start = min(max(_float(start_m, 0.0), rows[0]["s_m"]), rows[-1]["s_m"])
    end = min(max(_float(end_m, 0.0), rows[0]["s_m"]), rows[-1]["s_m"])
    if end <= start:
        return 0.0
    breakpoints = [start]
    breakpoints.extend(row["s_m"] for row in rows if start < row["s_m"] < end)
    breakpoints.append(end)
    area = 0.0
    for x0, x1 in zip(breakpoints, breakpoints[1:]):
        y0 = _full_trace_value(rows, x0, field)
        y1 = _full_trace_value(rows, x1, field)
        area += 0.5 * (y0 + y1) * (x1 - x0)
    return area


def _coupled_final_stress_mpa(
    rows: list[dict[str, float]],
    *,
    station_m: float,
    neutral_station_m: float,
    meeting_stress_mpa: float,
) -> float:
    station = _float(station_m, 0.0)
    neutral = _float(neutral_station_m, 0.0)
    meeting = _float(meeting_stress_mpa, 0.0)
    if station <= neutral:
        branch_at_neutral = _full_trace_value(rows, neutral, "left_mpa")
        return meeting + branch_at_neutral - _full_trace_value(rows, station, "left_mpa")
    branch_at_neutral = _full_trace_value(rows, neutral, "right_mpa")
    return meeting + branch_at_neutral - _full_trace_value(rows, station, "right_mpa")


def _solve_both_end_full_length_interaction(
    tendon_rows: list[dict[str, Any]],
    *,
    length_m: float,
    anchor_set_left_mm: float,
    anchor_set_right_mm: float,
    ep_mpa: float,
) -> dict[str, Any]:
    """Solve coupled full-length seating after independent branches overlap.

    This is an engineering implementation extension of the FHWA graphical
    mirror-image/area compatibility method. The accepted PTLOSS1 pre-seating
    force diagram is preserved. Reverse-slip branch shapes are taken from the
    full left/right jack traces and joined at one zero-displacement neutral
    station. The neutral station and meeting stress are solved from left and
    right elongation compatibility.
    """

    length = max(_float(length_m, 0.0), 0.0)
    ep = max(_float(ep_mpa, 0.0), 0.0)
    left_set = max(_float(anchor_set_left_mm, 0.0), 0.0)
    right_set = max(_float(anchor_set_right_mm, 0.0), 0.0)
    rows = _canonical_full_tendon_rows(tendon_rows, length_m=length)
    result: dict[str, Any] = {
        "status": "REVIEW REQUIRED",
        "issue": "",
        "rows": rows,
        "neutral_station_m": None,
        "meeting_stress_mpa": None,
        "left_set_check_mm": None,
        "right_set_check_mm": None,
        "left_residual_mm": None,
        "right_residual_mm": None,
        "continuity_residual_mpa": None,
        "max_stress_gain_mpa": None,
        "min_final_stress_mpa": None,
    }
    if length <= 0.0 or ep <= 0.0 or left_set <= 0.0 or right_set <= 0.0:
        result["issue"] = "Positive length, Ep, and anchorage seating values are required."
        return result
    if len(rows) < 2:
        result["issue"] = (
            "Full left/right jacking branch traces are incomplete; regenerate the accepted "
            "friction/wobble trace before coupled both-end seating."
        )
        return result

    target_left_area = ep * left_set / 1000.0
    target_right_area = ep * right_set / 1000.0
    epsilon = max(length * 1.0e-9, 1.0e-8)

    def meeting_from_left(neutral: float) -> float:
        span = neutral
        initial_area = _full_trace_integral(rows, 0.0, neutral, "initial_mpa")
        branch_area = _full_trace_integral(rows, 0.0, neutral, "left_mpa")
        branch_at_neutral = _full_trace_value(rows, neutral, "left_mpa")
        return (
            initial_area + branch_area - span * branch_at_neutral - target_left_area
        ) / span

    def meeting_from_right(neutral: float) -> float:
        span = length - neutral
        initial_area = _full_trace_integral(rows, neutral, length, "initial_mpa")
        branch_area = _full_trace_integral(rows, neutral, length, "right_mpa")
        branch_at_neutral = _full_trace_value(rows, neutral, "right_mpa")
        return (
            initial_area + branch_area - span * branch_at_neutral - target_right_area
        ) / span

    def balance(neutral: float) -> float:
        return meeting_from_left(neutral) - meeting_from_right(neutral)

    samples = {epsilon, length - epsilon}
    samples.update(
        row["s_m"] for row in rows if epsilon < row["s_m"] < length - epsilon
    )
    subdivisions = max(80, min(800, len(rows) * 40))
    samples.update(length * index / subdivisions for index in range(1, subdivisions))
    ordered = sorted(samples)
    roots: list[float] = []
    previous_x = ordered[0]
    previous_value = balance(previous_x)
    if abs(previous_value) <= 1.0e-10:
        roots.append(previous_x)
    for current_x in ordered[1:]:
        current_value = balance(current_x)
        if abs(current_value) <= 1.0e-10:
            roots.append(current_x)
        elif previous_value * current_value < 0.0:
            low, high = previous_x, current_x
            low_value = previous_value
            for _ in range(100):
                mid = 0.5 * (low + high)
                mid_value = balance(mid)
                if abs(mid_value) <= 1.0e-12:
                    low = high = mid
                    break
                if low_value * mid_value <= 0.0:
                    high = mid
                else:
                    low = mid
                    low_value = mid_value
            roots.append(0.5 * (low + high))
        previous_x = current_x
        previous_value = current_value

    unique_roots: list[float] = []
    for root in roots:
        if not unique_roots or abs(root - unique_roots[-1]) > max(1.0e-7, length * 1.0e-8):
            unique_roots.append(root)
    if not unique_roots:
        result["issue"] = (
            "No unique full-length neutral-station solution closes left/right seating "
            "compatibility for the adopted force diagram."
        )
        return result
    if len(unique_roots) > 1:
        result["issue"] = (
            "Multiple full-length neutral-station roots were found; stressing/seating sequence "
            "is ambiguous and requires project-specific review."
        )
        return result

    neutral = unique_roots[0]
    meeting_left = meeting_from_left(neutral)
    meeting_right = meeting_from_right(neutral)
    meeting = 0.5 * (meeting_left + meeting_right)
    continuity_residual = meeting_left - meeting_right

    check_points = {0.0, neutral, length}
    check_points.update(row["s_m"] for row in rows)
    final_values: list[float] = []
    stress_gains: list[float] = []
    for station in sorted(check_points):
        final_stress = _coupled_final_stress_mpa(
            rows,
            station_m=station,
            neutral_station_m=neutral,
            meeting_stress_mpa=meeting,
        )
        initial_stress = _full_trace_value(rows, station, "initial_mpa")
        final_values.append(final_stress)
        stress_gains.append(final_stress - initial_stress)

    min_final = min(final_values, default=0.0)
    max_gain = max(stress_gains, default=0.0)
    left_initial_area = _full_trace_integral(rows, 0.0, neutral, "initial_mpa")
    left_branch_area = _full_trace_integral(rows, 0.0, neutral, "left_mpa")
    left_branch_neutral = _full_trace_value(rows, neutral, "left_mpa")
    left_final_area = neutral * (meeting + left_branch_neutral) - left_branch_area
    right_initial_area = _full_trace_integral(rows, neutral, length, "initial_mpa")
    right_branch_area = _full_trace_integral(rows, neutral, length, "right_mpa")
    right_branch_neutral = _full_trace_value(rows, neutral, "right_mpa")
    right_span = length - neutral
    right_final_area = right_span * (meeting + right_branch_neutral) - right_branch_area
    left_check = 1000.0 * (left_initial_area - left_final_area) / ep
    right_check = 1000.0 * (right_initial_area - right_final_area) / ep
    left_residual = left_check - left_set
    right_residual = right_check - right_set

    result.update(
        {
            "neutral_station_m": neutral,
            "meeting_stress_mpa": meeting,
            "left_set_check_mm": left_check,
            "right_set_check_mm": right_check,
            "left_residual_mm": left_residual,
            "right_residual_mm": right_residual,
            "continuity_residual_mpa": continuity_residual,
            "max_stress_gain_mpa": max(max_gain, 0.0),
            "min_final_stress_mpa": min_final,
        }
    )
    set_tolerance = max(1.0e-5, max(left_set, right_set) * 1.0e-5)
    stress_tolerance = 1.0e-5
    if abs(left_residual) > set_tolerance or abs(right_residual) > set_tolerance:
        result["issue"] = "Coupled seating compatibility residual exceeds tolerance."
        return result
    if abs(continuity_residual) > 1.0e-5:
        result["issue"] = "Coupled left/right force continuity residual exceeds tolerance."
        return result
    if min_final < -stress_tolerance:
        result["issue"] = (
            "Coupled full-length seating would require negative tendon stress; adopted seating "
            "or force-profile assumptions require review."
        )
        return result
    if max_gain > stress_tolerance:
        result["issue"] = (
            "Coupled seating solution increases stress above the accepted post-friction diagram "
            "at one or more stations; stressing/seating sequence requires review."
        )
        return result

    result["status"] = "PREVIEW READY + NOTE"
    result["issue"] = ""
    return result

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

        branch_by_end: dict[str, list[dict[str, float]]] = {}
        for active_end in ends:
            if active_end in {"Left", "Right"}:
                branch_by_end[active_end] = _canonical_branch_rows(
                    tendon_rows,
                    end=active_end,
                    jacking_end=jacking_end,
                    length_m=length,
                )

        coupled_solution: dict[str, Any] | None = None
        coupled_attempted = False
        if (
            active
            and str(jacking_end).strip().casefold() == "both"
            and adopted_set > 0.0
            and ep > 0.0
        ):
            branch_limit = _branch_limit_m(jacking_end, length)
            local_capacities = []
            for active_end in ("Left", "Right"):
                branch = branch_by_end.get(active_end, [])
                local_capacities.append(
                    _compatibility_set_mm(
                        branch,
                        influence_length_m=branch_limit,
                        ep_mpa=ep,
                    )
                    if branch
                    else 0.0
                )
            tolerance = max(1.0e-5, adopted_set * 1.0e-5)
            if any(capacity + tolerance < adopted_set for capacity in local_capacities):
                coupled_attempted = True
                coupled_solution = _solve_both_end_full_length_interaction(
                    tendon_rows,
                    length_m=length,
                    anchor_set_left_mm=adopted_set,
                    anchor_set_right_mm=adopted_set,
                    ep_mpa=ep,
                )

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
            branch_rows = branch_by_end.get(end, []) if end in {"Left", "Right"} else []
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
            interaction_mode = "ISOLATED LOCAL"
            neutral_station_m: float | None = None
            meeting_stress_mpa: float | None = None
            neutral_initial_stress_mpa: float | None = None
            continuity_residual_mpa: float | None = None
            max_stress_gain_mpa: float | None = None
            min_final_stress_mpa: float | None = None

            coupled_ready = bool(
                coupled_solution
                and str(coupled_solution.get("status") or "") == "PREVIEW READY + NOTE"
            )
            if coupled_ready and end in {"Left", "Right"}:
                interaction_mode = "FULL-LENGTH COUPLED"
                full_rows = coupled_solution.get("rows") or []
                neutral_station_m = _float(
                    coupled_solution.get("neutral_station_m"), 0.0
                )
                meeting_stress_mpa = _float(
                    coupled_solution.get("meeting_stress_mpa"), 0.0
                )
                neutral_initial_stress_mpa = _full_trace_value(
                    full_rows, neutral_station_m, "initial_mpa"
                )
                continuity_residual_mpa = _float(
                    coupled_solution.get("continuity_residual_mpa"), 0.0
                )
                max_stress_gain_mpa = _float(
                    coupled_solution.get("max_stress_gain_mpa"), 0.0
                )
                min_final_stress_mpa = _float(
                    coupled_solution.get("min_final_stress_mpa"), 0.0
                )
                anchor_station = 0.0 if end == "Left" else length
                anchor_initial = _full_trace_value(
                    full_rows, anchor_station, "initial_mpa"
                )
                lockoff_stress = max(
                    _coupled_final_stress_mpa(
                        full_rows,
                        station_m=anchor_station,
                        neutral_station_m=neutral_station_m,
                        meeting_stress_mpa=meeting_stress_mpa,
                    ),
                    0.0,
                )
                influence = (
                    neutral_station_m
                    if end == "Left"
                    else max(length - neutral_station_m, 0.0)
                )
                max_compatible_set = _compatibility_set_mm(
                    branch_rows,
                    influence_length_m=branch_limit,
                    ep_mpa=ep,
                )
                compatibility_set_check_mm = _float(
                    coupled_solution.get(
                        "left_set_check_mm" if end == "Left" else "right_set_check_mm"
                    ),
                    0.0,
                )
                residual = _float(
                    coupled_solution.get(
                        "left_residual_mm" if end == "Left" else "right_residual_mm"
                    ),
                    0.0,
                )
                anchor_loss_mpa = max(anchor_initial - lockoff_stress, 0.0)
                anchor_loss_kn = aps_total * anchor_loss_mpa / 1000.0
                lockoff_force = aps_total * lockoff_stress / 1000.0
                anchor_loss_percent = (
                    100.0 * anchor_loss_kn / pj_kn if pj_kn > 0.0 else None
                )
            elif branch_rows and adopted_set > 0.0 and ep > 0.0:
                influence, max_compatible_set, residual = _solve_influence_length_m(
                    branch_rows,
                    branch_limit_m=branch_limit,
                    anchor_set_mm=adopted_set,
                    ep_mpa=ep,
                )
                if influence is None:
                    if coupled_attempted and coupled_solution is not None:
                        issues.append(
                            str(coupled_solution.get("issue") or "Full-length both-end interaction requires review.")
                        )
                    else:
                        issues.append(
                            "Required seating movement exceeds the compatibility capacity of the current isolated branch; full-length/opposing-end interaction requires review."
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
                if coupled_ready:
                    notes.append(
                        "PTLOSS2C solved a coupled full-length both-end seating interaction after the independent half-length capacity was exceeded. The same adopted Δa is applied at both ends as a final-state compatibility preview; explicit first-end/second-end stressing and seating sequence is not modeled and must be verified for the approved PT procedure."
                    )
                else:
                    notes.append(
                        "Both-end seating uses independent local branches while valid; if those branches are exceeded, PTLOSS2C attempts a coupled full-length zero-displacement neutral-station solution."
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
                    "Interaction mode": interaction_mode,
                    "Neutral point s (m)": neutral_station_m,
                    "Neutral-point initial stress (MPa)": neutral_initial_stress_mpa,
                    "Meeting stress after seating (MPa)": meeting_stress_mpa,
                    "Force continuity residual (MPa)": continuity_residual_mpa,
                    "Max stress gain check (MPa)": max_stress_gain_mpa,
                    "Minimum final stress check (MPa)": min_final_stress_mpa,
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
    full_trace_cache: dict[str, list[dict[str, float]]] = {}
    coupled_end_map: dict[str, dict[str, Any]] = {}
    for end_row in ends:
        tendon_id = str(end_row.get("Tendon ID") or "")
        if (
            tendon_id
            and str(end_row.get("Interaction mode") or "") == "FULL-LENGTH COUPLED"
            and end_row.get("Neutral point s (m)") is not None
            and end_row.get("Meeting stress after seating (MPa)") is not None
        ):
            coupled_end_map.setdefault(tendon_id, end_row)

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
        if tendon_id in coupled_end_map:
            full_trace_cache[tendon_id] = _canonical_full_tendon_rows(
                tendon_rows,
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

        coupled_result = coupled_end_map.get(tendon_id)
        if coupled_result is not None:
            full_rows = full_trace_cache.get(tendon_id, [])
            neutral = _float(coupled_result.get("Neutral point s (m)"), 0.0)
            meeting = _float(
                coupled_result.get("Meeting stress after seating (MPa)"), 0.0
            )
            if full_rows:
                station_m = max(_float(row.get("s (m)"), 0.0), 0.0)
                final_stress = max(
                    _coupled_final_stress_mpa(
                        full_rows,
                        station_m=station_m,
                        neutral_station_m=neutral,
                        meeting_stress_mpa=meeting,
                    ),
                    0.0,
                )
                component_loss_mpa = max(friction_stress - final_stress, 0.0)
                final_force = aps_total * final_stress / 1000.0
                component_loss_kn = max(friction_force - final_force, 0.0)
                influence_length = neutral if station_m <= neutral else max(
                    (max(_float(length_m, 0.0), 0.0) if length_m is not None else full_rows[-1]["s_m"])
                    - neutral,
                    0.0,
                )
                applied = True
                status = str(coupled_result.get("Status") or "PREVIEW READY + NOTE")
                issue = str(coupled_result.get("Issue") or "")
        elif end_result is not None:
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
