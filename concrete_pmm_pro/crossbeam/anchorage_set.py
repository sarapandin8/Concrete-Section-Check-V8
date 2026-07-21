"""Crossbeam post-tensioned anchorage-set / draw-in calculation foundation.

PTLOSS2R2 retains the PTLOSS2R1 single-end friction-coupled reverse-slip method
and defines ``Jacking end = Both`` as simultaneous equal left/right stressing.
For the prestress-loss preview, both ends are also assumed to lock off / seat
simultaneously with the same adopted anchorage draw-in unless the project/PT
procedure states otherwise.

Single-end stressing uses:

    Delta_fpA(x) = max(Delta_fpA0 - 2*Delta_fpF(x), 0)

with Delta_fpA0 solved from full-path strain compatibility. Simultaneous both-end
seating first solves independent reverse-slip zones from the two anchors to the
pre-seating point of no movement. If the zones remain separated, the local
solutions are retained. If they reach/overlap the equilibrium region, a guarded
full-tendon mirror-slope compatibility solve finds a zero-displacement neutral
station and common meeting stress.

The both-end coupled formulation is an engineering extension of the published
force-diagram / equal-and-opposite friction concept, not a verbatim AASHTO
numbered equation. Pe/Pe_eff, elastic shortening, and time-dependent losses
remain locked.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import exp, isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.prestress_loss import DEFAULT_PRESTRESS_STEEL_EP_MPA


ANCHORAGE_SET_METHOD_BASIS = (
    "Single-end friction-coupled reverse-slip / force-diagram compatibility"
)

BOTH_END_SIMULTANEOUS_REVIEW_NOTE = (
    "Jack = Both is defined by this app as simultaneous equal left/right stressing. "
    "PTLOSS2R2 assumes simultaneous lock-off/seating with the same adopted Δa at both "
    "ends for this component preview; verify that the approved PT procedure matches "
    "this assumption before final design use."
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




def _friction_loss_from_anchor_mpa(branch_rows: list[dict[str, float]], x_m: float) -> float:
    """Return cumulative friction loss from the active anchorage to ``x_m``.

    The active-end post-friction stress is the reference. For a physically valid
    one-end trace the cumulative loss must be nonnegative and nondecreasing.
    """

    if not branch_rows:
        return 0.0
    f_anchor = _diagram_stress_mpa(branch_rows, 0.0)
    return max(f_anchor - _diagram_stress_mpa(branch_rows, x_m), 0.0)


def _single_end_anchor_loss_mpa(
    branch_rows: list[dict[str, float]],
    *,
    x_m: float,
    anchor_loss_mpa: float,
) -> float:
    """Return the reverse-slip anchorage-set loss at distance ``x_m``.

    This is the generalized form of the Caltrans/FHWA similar-triangle method:
    the reverse-slip friction slope is equal and opposite to the stressing
    friction slope, hence the ``2*Delta_fpF`` term.
    """

    return max(
        max(_float(anchor_loss_mpa, 0.0), 0.0)
        - 2.0 * _friction_loss_from_anchor_mpa(branch_rows, x_m),
        0.0,
    )


def _single_end_compatibility_mm(
    branch_rows: list[dict[str, float]],
    *,
    anchor_loss_mpa: float,
    ep_mpa: float,
) -> float:
    """Integrate the single-end anchor-set strain reduction over the full path."""

    if len(branch_rows) < 2:
        return 0.0
    ep = max(_float(ep_mpa, 0.0), 0.0)
    if ep <= 0.0:
        return 0.0
    area = 0.0
    for left, right in zip(branch_rows, branch_rows[1:]):
        x0 = left["x_m"]
        x1 = right["x_m"]
        dx = x1 - x0
        if dx <= 0.0:
            continue
        y0 = _single_end_anchor_loss_mpa(
            branch_rows, x_m=x0, anchor_loss_mpa=anchor_loss_mpa
        )
        y1 = _single_end_anchor_loss_mpa(
            branch_rows, x_m=x1, anchor_loss_mpa=anchor_loss_mpa
        )
        # Delta_fpF is linearly interpolated between accepted friction stations,
        # so Delta_fpA is also linear until it clips to zero. Handle a zero
        # crossing exactly rather than relying on coarse numerical integration.
        if y0 > 0.0 and y1 <= 0.0:
            loss0 = _friction_loss_from_anchor_mpa(branch_rows, x0)
            loss1 = _friction_loss_from_anchor_mpa(branch_rows, x1)
            denom = 2.0 * (loss1 - loss0)
            if denom > 1.0e-15:
                frac = min(max((anchor_loss_mpa - 2.0 * loss0) / denom, 0.0), 1.0)
                x_zero = x0 + frac * dx
                area += 0.5 * y0 * (x_zero - x0)
                continue
        area += 0.5 * (y0 + y1) * dx
    return 1000.0 * area / ep


def _single_end_affected_length_m(
    branch_rows: list[dict[str, float]],
    *,
    anchor_loss_mpa: float,
) -> tuple[float, bool]:
    """Return affected length and whether the full tendon remains affected."""

    if not branch_rows:
        return 0.0, False
    limit = branch_rows[-1]["x_m"]
    if _single_end_anchor_loss_mpa(
        branch_rows, x_m=limit, anchor_loss_mpa=anchor_loss_mpa
    ) > 1.0e-9:
        return limit, True
    for left, right in zip(branch_rows, branch_rows[1:]):
        x0, x1 = left["x_m"], right["x_m"]
        y0 = _single_end_anchor_loss_mpa(
            branch_rows, x_m=x0, anchor_loss_mpa=anchor_loss_mpa
        )
        y1 = _single_end_anchor_loss_mpa(
            branch_rows, x_m=x1, anchor_loss_mpa=anchor_loss_mpa
        )
        if y0 > 0.0 and y1 <= 1.0e-9:
            loss0 = _friction_loss_from_anchor_mpa(branch_rows, x0)
            loss1 = _friction_loss_from_anchor_mpa(branch_rows, x1)
            denom = 2.0 * (loss1 - loss0)
            if denom <= 1.0e-15:
                return x1, False
            frac = min(max((anchor_loss_mpa - 2.0 * loss0) / denom, 0.0), 1.0)
            return x0 + frac * (x1 - x0), False
    return limit, False


def _solve_single_end_friction_coupled(
    branch_rows: list[dict[str, float]],
    *,
    anchor_set_mm: float,
    ep_mpa: float,
) -> dict[str, Any]:
    """Solve the design-use single-end anchorage-set distribution.

    ``Delta_fpA0`` is solved from full-path compatibility. The method reproduces
    the published linear/similar-triangle anchor-set equations as a special case
    but also works on a piecewise-linear accepted friction profile.
    """

    target = max(_float(anchor_set_mm, 0.0), 0.0)
    ep = max(_float(ep_mpa, 0.0), 0.0)
    result: dict[str, Any] = {
        "status": "REVIEW REQUIRED",
        "issue": "",
        "anchor_loss_mpa": None,
        "lockoff_stress_mpa": None,
        "affected_length_m": None,
        "full_tendon_affected": False,
        "dead_end_loss_mpa": None,
        "set_check_mm": None,
        "residual_mm": None,
        "max_nonnegative_set_mm": None,
    }
    if target <= 0.0 or ep <= 0.0 or len(branch_rows) < 2:
        result["issue"] = "Positive anchorage set, Ep, and a complete one-end friction trace are required."
        return result
    if branch_rows[0]["x_m"] > 1.0e-8:
        result["issue"] = "The accepted one-end friction trace must start at the active anchorage (x = 0)."
        return result

    # Friction loss from one active jack should not decrease with distance. A
    # decrease would invalidate the reverse-slip/similar-triangle assumption.
    cumulative = [
        _friction_loss_from_anchor_mpa(branch_rows, row["x_m"]) for row in branch_rows
    ]
    if any(right + 1.0e-7 < left for left, right in zip(cumulative, cumulative[1:])):
        result["issue"] = (
            "The accepted one-end friction-loss trace is not monotone with distance from "
            "the active jack; reverse-slip compatibility requires engineering review."
        )
        return result

    f_anchor = max(_diagram_stress_mpa(branch_rows, 0.0), 0.0)
    if f_anchor <= 0.0:
        result["issue"] = "Positive post-friction stress at the active anchorage is required."
        return result

    max_set = _single_end_compatibility_mm(
        branch_rows, anchor_loss_mpa=f_anchor, ep_mpa=ep
    )
    result["max_nonnegative_set_mm"] = max_set
    tolerance = max(1.0e-6, target * 1.0e-6)
    if max_set + tolerance < target:
        result["issue"] = (
            "The adopted anchorage draw-in would require negative lock-off stress at the "
            "active anchorage under the current friction profile."
        )
        return result

    low, high = 0.0, f_anchor
    for _ in range(120):
        mid = 0.5 * (low + high)
        movement = _single_end_compatibility_mm(
            branch_rows, anchor_loss_mpa=mid, ep_mpa=ep
        )
        if movement < target:
            low = mid
        else:
            high = mid
    anchor_loss = 0.5 * (low + high)
    set_check = _single_end_compatibility_mm(
        branch_rows, anchor_loss_mpa=anchor_loss, ep_mpa=ep
    )
    affected_length, full_affected = _single_end_affected_length_m(
        branch_rows, anchor_loss_mpa=anchor_loss
    )
    dead_end_loss = _single_end_anchor_loss_mpa(
        branch_rows,
        x_m=branch_rows[-1]["x_m"],
        anchor_loss_mpa=anchor_loss,
    )
    lockoff = f_anchor - anchor_loss
    residual = set_check - target
    if lockoff < -1.0e-7:
        result["issue"] = "Solved anchor seating would require negative lock-off stress."
        return result
    if abs(residual) > tolerance:
        result["issue"] = "Single-end anchor-set compatibility residual exceeds tolerance."
        return result

    result.update(
        {
            "status": "PREVIEW READY + NOTE",
            "issue": "",
            "anchor_loss_mpa": anchor_loss,
            "lockoff_stress_mpa": max(lockoff, 0.0),
            "affected_length_m": affected_length,
            "full_tendon_affected": full_affected,
            "dead_end_loss_mpa": dead_end_loss,
            "set_check_mm": set_check,
            "residual_mm": residual,
        }
    )
    return result

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
            "initial_mpa": max(_float(left_raw, 0.0), _float(right_raw, 0.0), 0.0),
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


def _both_end_preseat_no_movement(
    rows: list[dict[str, float]],
) -> tuple[float | None, float | None, str]:
    """Return the simultaneous-jacking point of no movement from branch equilibrium.

    Caltrans defines the two-end point of no movement as the location where movement
    from the two stressing directions is countered and internal strand forces are in
    equilibrium.  In this implementation it is therefore the unique intersection of
    the independently traced left- and right-jacking stress branches.
    """

    if len(rows) < 2:
        return None, None, "Complete left/right jacking branch traces are required."
    length = rows[-1]["s_m"] - rows[0]["s_m"]
    tolerance = 1.0e-8
    diffs = [row["left_mpa"] - row["right_mpa"] for row in rows]
    if max((abs(value) for value in diffs), default=0.0) <= tolerance:
        station = rows[0]["s_m"] + 0.5 * length
        stress = 0.5 * (
            _full_trace_value(rows, station, "left_mpa")
            + _full_trace_value(rows, station, "right_mpa")
        )
        return station, stress, ""

    roots: list[float] = []
    for left, right, d0, d1 in zip(rows, rows[1:], diffs, diffs[1:]):
        x0, x1 = left["s_m"], right["s_m"]
        if abs(d0) <= tolerance:
            roots.append(x0)
        if d0 * d1 < 0.0:
            ratio = -d0 / (d1 - d0)
            roots.append(x0 + ratio * (x1 - x0))
    if abs(diffs[-1]) <= tolerance:
        roots.append(rows[-1]["s_m"])

    unique: list[float] = []
    for root in sorted(roots):
        if not unique or abs(root - unique[-1]) > 1.0e-7:
            unique.append(root)
    interior = [root for root in unique if rows[0]["s_m"] - 1.0e-9 <= root <= rows[-1]["s_m"] + 1.0e-9]
    if len(interior) != 1:
        return None, None, (
            "A unique simultaneous-jacking point of no movement could not be established "
            "from the left/right friction branch equilibrium."
        )
    station = interior[0]
    stress = 0.5 * (
        _full_trace_value(rows, station, "left_mpa")
        + _full_trace_value(rows, station, "right_mpa")
    )
    return station, stress, ""


def _branch_rows_to_no_movement(
    rows: list[dict[str, float]],
    *,
    end: str,
    neutral_station_m: float,
) -> list[dict[str, float]]:
    """Return x-from-anchor branch rows ending exactly at pre-seat no movement."""

    if not rows:
        return []
    length = rows[-1]["s_m"]
    neutral = min(max(_float(neutral_station_m, 0.0), 0.0), length)
    target = str(end).strip().casefold()
    stations = {0.0, neutral} if target == "left" else {neutral, length}
    stations.update(
        row["s_m"]
        for row in rows
        if (0.0 < row["s_m"] < neutral if target == "left" else neutral < row["s_m"] < length)
    )
    output: list[dict[str, float]] = []
    for station in sorted(stations):
        if target == "left":
            x_m = station
            stress = _full_trace_value(rows, station, "left_mpa")
        else:
            x_m = length - station
            stress = _full_trace_value(rows, station, "right_mpa")
        output.append({"x_m": x_m, "stress_mpa": stress, "k_per_m": 0.0})
    output.sort(key=lambda row: row["x_m"])
    return output


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


def _solve_both_end_simultaneous_interaction(
    tendon_rows: list[dict[str, Any]],
    *,
    length_m: float,
    anchor_set_left_mm: float,
    anchor_set_right_mm: float,
    ep_mpa: float,
) -> dict[str, Any]:
    """Solve simultaneous both-end seating when reverse-slip zones interact.

    The app definition is equal simultaneous left/right stressing followed by
    simultaneous lock-off/seating with the same adopted draw-in at both ends.
    This is a guarded engineering extension of the published graphical
    equal-and-opposite friction / area-compatibility method, not a verbatim
    AASHTO numbered equation.
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
    """Return one anchorage-seating audit row per active stressing end.

    Single-end tendons use the PTLOSS2R1 full-path friction-coupled method.
    ``Jack = Both`` is defined as simultaneous equal left/right stressing.  The
    PTLOSS2R2 preview assumes simultaneous lock-off/seating with the same adopted
    draw-in at both ends.  Independent local seating zones are retained when they
    terminate before the pre-seat point of no movement; otherwise a guarded
    full-tendon simultaneous compatibility solve is used.
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
        normalized_jack = jacking_end.strip().casefold()
        aps_total = max(_float(first.get("Aps total (mm²)"), 0.0), 0.0)
        pj_kn = max(_float(first.get("Pj (kN)"), 0.0), 0.0)
        fpj_mpa = max(_float(first.get("fpj (MPa)"), 0.0), 0.0)
        friction_blocking = _deduplicated(
            [str(row.get("Blocking issue") or "") for row in tendon_rows]
        )
        friction_notes = _deduplicated(
            [str(row.get("Review note") or "") for row in tendon_rows]
        )
        ends = _active_seating_ends(jacking_end) or ("Unknown",)

        base_issues = list(friction_blocking)
        if adopted_set <= 0.0:
            base_issues.append(
                "Adopt a positive project/PT supplier anchorage-set value before calculating draw-in loss."
            )
        if ep <= 0.0:
            base_issues.append("Positive prestressing-steel modulus Ep is required.")
        if aps_total <= 0.0 or pj_kn <= 0.0 or fpj_mpa <= 0.0:
            base_issues.append("Positive Aps, fpj, and Pj are required from the tendon force source.")
        if ends == ("Unknown",):
            base_issues.append("Jacking end must be Left, Right, or Both.")

        single_branches: dict[str, list[dict[str, float]]] = {}
        both_solution: dict[str, Any] | None = None
        preseat_no_movement: float | None = None
        preseat_no_movement_stress: float | None = None
        both_local_solutions: dict[str, dict[str, Any]] = {}
        both_mode = ""
        full_rows: list[dict[str, float]] = []
        both_issue = ""

        if normalized_jack in {"left", "right"}:
            active_end = "Left" if normalized_jack == "left" else "Right"
            single_branches[active_end] = _canonical_branch_rows(
                tendon_rows,
                end=active_end,
                jacking_end=jacking_end,
                length_m=length,
            )
        elif normalized_jack == "both" and not base_issues:
            full_rows = _canonical_full_tendon_rows(tendon_rows, length_m=length)
            preseat_no_movement, preseat_no_movement_stress, both_issue = (
                _both_end_preseat_no_movement(full_rows)
            )
            if not both_issue and preseat_no_movement is not None:
                left_branch = _branch_rows_to_no_movement(
                    full_rows, end="Left", neutral_station_m=preseat_no_movement
                )
                right_branch = _branch_rows_to_no_movement(
                    full_rows, end="Right", neutral_station_m=preseat_no_movement
                )
                single_branches = {"Left": left_branch, "Right": right_branch}
                left_local = _solve_single_end_friction_coupled(
                    left_branch, anchor_set_mm=adopted_set, ep_mpa=ep
                )
                right_local = _solve_single_end_friction_coupled(
                    right_branch, anchor_set_mm=adopted_set, ep_mpa=ep
                )
                both_local_solutions = {"Left": left_local, "Right": right_local}
                local_ready = all(
                    solved.get("status") == "PREVIEW READY + NOTE"
                    for solved in both_local_solutions.values()
                )
                zones_separate = local_ready and all(
                    not bool(solved.get("full_tendon_affected"))
                    for solved in both_local_solutions.values()
                )
                if zones_separate:
                    both_mode = "BOTH-END SIMULTANEOUS LOCAL"
                else:
                    both_solution = _solve_both_end_simultaneous_interaction(
                        tendon_rows,
                        length_m=length,
                        anchor_set_left_mm=adopted_set,
                        anchor_set_right_mm=adopted_set,
                        ep_mpa=ep,
                    )
                    if both_solution.get("status") == "PREVIEW READY + NOTE":
                        both_mode = "BOTH-END SIMULTANEOUS COUPLED"
                    else:
                        both_issue = str(
                            both_solution.get("issue")
                            or "Simultaneous both-end anchorage-set compatibility requires review."
                        )

        for end in ends:
            issues = list(base_issues)
            notes = list(friction_notes)
            status = "STORED ONLY" if not active else "PREVIEW READY"
            interaction_mode = "SINGLE-END FRICTION-COUPLED"
            affected_length: float | None = None
            full_tendon_affected = False
            reaches_neutral = False
            lockoff_stress: float | None = None
            lockoff_force: float | None = None
            anchor_loss_mpa: float | None = None
            anchor_loss_kn: float | None = None
            anchor_loss_percent: float | None = None
            dead_end_loss_mpa: float | None = None
            neutral_region_loss_mpa: float | None = None
            compatibility_set_check_mm: float | None = None
            residual: float | None = None
            max_nonnegative_set_mm: float | None = None
            zero_movement_stress: float | None = None
            stress_integral_mpa_m: float | None = None
            one_side_stress_area_mpa_m: float | None = None
            mirrored_stress_area_mpa_m: float | None = None
            neutral_point: float | None = None
            meeting_stress: float | None = None
            continuity_residual: float | None = None
            max_stress_gain: float | None = None
            minimum_final_stress: float | None = None

            branch_rows = single_branches.get(end, []) if end in {"Left", "Right"} else []
            if active and end in {"Left", "Right"} and not branch_rows:
                issues.append(f"Accepted friction trace has no {end.lower()}-end branch.")

            if normalized_jack == "both":
                interaction_mode = both_mode or "BOTH-END SIMULTANEOUS REVIEW"
                notes.append(BOTH_END_SIMULTANEOUS_REVIEW_NOTE)
                if both_issue:
                    issues.append(both_issue)
                elif both_mode == "BOTH-END SIMULTANEOUS LOCAL":
                    solved = both_local_solutions[end]
                    if solved.get("status") != "PREVIEW READY + NOTE":
                        issues.append(str(solved.get("issue") or "Local simultaneous seating solution requires review."))
                    else:
                        status = "PREVIEW READY + NOTE"
                        affected_length = _float(solved.get("affected_length_m"), 0.0)
                        anchor_loss_mpa = _float(solved.get("anchor_loss_mpa"), 0.0)
                        lockoff_stress = _float(solved.get("lockoff_stress_mpa"), 0.0)
                        compatibility_set_check_mm = _float(solved.get("set_check_mm"), 0.0)
                        residual = _float(solved.get("residual_mm"), 0.0)
                        max_nonnegative_set_mm = solved.get("max_nonnegative_set_mm")
                        zero_movement_stress = (
                            _diagram_stress_mpa(branch_rows, affected_length)
                            if affected_length is not None
                            else None
                        )
                        reaches_neutral = bool(
                            affected_length is not None
                            and abs(affected_length - branch_rows[-1]["x_m"]) <= 1.0e-6
                        )
                elif both_mode == "BOTH-END SIMULTANEOUS COUPLED" and both_solution:
                    status = "PREVIEW READY + NOTE"
                    neutral_point = _float(both_solution.get("neutral_station_m"), 0.0)
                    meeting_stress = _float(both_solution.get("meeting_stress_mpa"), 0.0)
                    continuity_residual = _float(both_solution.get("continuity_residual_mpa"), 0.0)
                    max_stress_gain = _float(both_solution.get("max_stress_gain_mpa"), 0.0)
                    minimum_final_stress = _float(both_solution.get("min_final_stress_mpa"), 0.0)
                    affected_length = neutral_point if end == "Left" else max(length - neutral_point, 0.0)
                    reaches_neutral = True
                    final_anchor = _coupled_final_stress_mpa(
                        full_rows,
                        station_m=0.0 if end == "Left" else length,
                        neutral_station_m=neutral_point,
                        meeting_stress_mpa=meeting_stress,
                    )
                    initial_anchor = _full_trace_value(
                        full_rows, 0.0 if end == "Left" else length, "initial_mpa"
                    )
                    anchor_loss_mpa = max(initial_anchor - final_anchor, 0.0)
                    lockoff_stress = max(final_anchor, 0.0)
                    compatibility_set_check_mm = _float(
                        both_solution.get("left_set_check_mm" if end == "Left" else "right_set_check_mm"),
                        0.0,
                    )
                    residual = _float(
                        both_solution.get("left_residual_mm" if end == "Left" else "right_residual_mm"),
                        0.0,
                    )
                    initial_neutral = _full_trace_value(full_rows, neutral_point, "initial_mpa")
                    neutral_region_loss_mpa = max(initial_neutral - meeting_stress, 0.0)
                    zero_movement_stress = meeting_stress
            elif (
                active
                and end in {"Left", "Right"}
                and branch_rows
                and adopted_set > 0.0
                and ep > 0.0
                and aps_total > 0.0
                and pj_kn > 0.0
                and fpj_mpa > 0.0
                and not issues
            ):
                solved = _solve_single_end_friction_coupled(
                    branch_rows,
                    anchor_set_mm=adopted_set,
                    ep_mpa=ep,
                )
                max_nonnegative_set_mm = solved.get("max_nonnegative_set_mm")
                if solved.get("status") != "PREVIEW READY + NOTE":
                    issues.append(str(solved.get("issue") or "Single-end anchorage-set solution requires review."))
                else:
                    status = "PREVIEW READY + NOTE"
                    affected_length = _float(solved.get("affected_length_m"), 0.0)
                    full_tendon_affected = bool(solved.get("full_tendon_affected"))
                    anchor_loss_mpa = _float(solved.get("anchor_loss_mpa"), 0.0)
                    lockoff_stress = _float(solved.get("lockoff_stress_mpa"), 0.0)
                    dead_end_loss_mpa = _float(solved.get("dead_end_loss_mpa"), 0.0)
                    compatibility_set_check_mm = _float(solved.get("set_check_mm"), 0.0)
                    residual = _float(solved.get("residual_mm"), 0.0)
                    if full_tendon_affected:
                        notes.append(
                            "Adopted draw-in affects the full tendon; anchorage-set loss remains nonzero at the dead end."
                        )
                    else:
                        zero_movement_stress = _diagram_stress_mpa(branch_rows, affected_length)
                        if affected_length > 0.0:
                            stress_integral_mpa_m = _diagram_integral_mpa_m(branch_rows, affected_length)
                            one_side_stress_area_mpa_m = max(
                                stress_integral_mpa_m - affected_length * (zero_movement_stress or 0.0),
                                0.0,
                            )
                            mirrored_stress_area_mpa_m = 2.0 * one_side_stress_area_mpa_m

            if anchor_loss_mpa is not None and lockoff_stress is not None:
                lockoff_force = aps_total * lockoff_stress / 1000.0
                anchor_loss_kn = aps_total * anchor_loss_mpa / 1000.0
                anchor_loss_percent = 100.0 * anchor_loss_kn / pj_kn if pj_kn > 0.0 else None

            if active and issues:
                status = "INPUT REQUIRED" if adopted_set <= 0.0 else "REVIEW REQUIRED"

            if normalized_jack == "both" and preseat_no_movement is not None:
                branch_limit = preseat_no_movement if end == "Left" else max(length - preseat_no_movement, 0.0)
            else:
                branch_limit = length
            initial_anchor_stress = _diagram_stress_mpa(branch_rows, 0.0) if branch_rows else None
            method = (
                ANCHORAGE_SET_METHOD_BASIS
                if normalized_jack != "both"
                else "Simultaneous both-end reverse-slip / force-diagram compatibility"
            )
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
                    "Max compatible set (mm)": max_nonnegative_set_mm,
                    "Max nonnegative set (mm)": max_nonnegative_set_mm,
                    "Influence length (m)": affected_length,
                    "Affected length (m)": affected_length,
                    "Full tendon affected": full_tendon_affected,
                    "Seating reaches neutral point": reaches_neutral,
                    "Initial stress at anchorage after friction (MPa)": initial_anchor_stress,
                    "Pre-seat no-movement s (m)": preseat_no_movement,
                    "Pre-seat no-movement stress (MPa)": preseat_no_movement_stress,
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
                    "Dead-end anchorage-set loss (MPa)": dead_end_loss_mpa,
                    "Neutral-region anchorage-set loss (MPa)": neutral_region_loss_mpa,
                    "Compatibility residual (mm)": residual,
                    "Interaction mode": interaction_mode,
                    "Neutral point s (m)": neutral_point,
                    "Neutral-point initial stress (MPa)": (
                        None if neutral_point is None or not full_rows else _full_trace_value(full_rows, neutral_point, "initial_mpa")
                    ),
                    "Meeting stress after seating (MPa)": meeting_stress,
                    "Force continuity residual (MPa)": continuity_residual,
                    "Max stress gain check (MPa)": (
                        0.0 if anchor_loss_mpa is not None and max_stress_gain is None else max_stress_gain
                    ),
                    "Minimum final stress check (MPa)": (
                        lockoff_stress if minimum_final_stress is None else minimum_final_stress
                    ),
                    "Method": method,
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
    """Return station trace after single- or simultaneous-both-end seating preview."""

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
    full_cache: dict[str, list[dict[str, float]]] = {}
    preseat_cache: dict[str, float | None] = {}
    for tendon_id, tendon_rows in grouped.items():
        if not tendon_rows:
            continue
        jacking_end = str(tendon_rows[0].get("Jacking end") or "")
        normalized = jacking_end.strip().casefold()
        tendon_length_m = (
            max(_float(length_m, 0.0), 0.0)
            if length_m is not None
            else max(_float(row.get("s (m)"), 0.0) for row in tendon_rows)
        )
        if normalized == "both":
            full = _canonical_full_tendon_rows(tendon_rows, length_m=tendon_length_m)
            full_cache[tendon_id] = full
            preseat, _, _ = _both_end_preseat_no_movement(full)
            preseat_cache[tendon_id] = preseat
            if preseat is not None:
                branch_cache[(tendon_id, "Left")] = _branch_rows_to_no_movement(
                    full, end="Left", neutral_station_m=preseat
                )
                branch_cache[(tendon_id, "Right")] = _branch_rows_to_no_movement(
                    full, end="Right", neutral_station_m=preseat
                )
        else:
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
        jacking_end = str(row.get("Jacking end") or "")
        normalized = jacking_end.strip().casefold()
        station = max(_float(row.get("s (m)"), 0.0), 0.0)
        friction_stress = max(_float(row.get("Stress after friction (MPa)"), 0.0), 0.0)
        friction_force = max(_float(row.get("P after friction (kN)"), 0.0), 0.0)
        aps_total = max(_float(row.get("Aps total (mm²)"), 0.0), 0.0)

        final_stress: float | None = None
        final_force: float | None = None
        component_loss_mpa: float | None = None
        component_loss_kn: float | None = None
        affected_length: float | None = None
        applied = False
        status = "NOT CALCULATED"
        issue = "No validated anchorage-set solution is available for this stressing route."
        seating_end = _source_end_name(row)

        if normalized == "both":
            left_result = end_map.get((tendon_id, "Left"))
            right_result = end_map.get((tendon_id, "Right"))
            controlling = left_result or right_result
            mode = str((controlling or {}).get("Interaction mode") or "")
            preseat = preseat_cache.get(tendon_id)
            if mode == "BOTH-END SIMULTANEOUS LOCAL" and preseat is not None:
                seating_end = "Left" if station <= preseat else "Right"
                end_result = end_map.get((tendon_id, seating_end))
                branch = branch_cache.get((tendon_id, seating_end), [])
                x_m = station if seating_end == "Left" else max(
                    (max(_float(length_m, 0.0), 0.0) if length_m is not None else branch[-1]["x_m"] + preseat) - station,
                    0.0,
                )
                if (
                    end_result is not None
                    and branch
                    and end_result.get("Anchorage-set loss at anchorage (MPa)") is not None
                    and str(end_result.get("Status") or "").startswith("PREVIEW READY")
                ):
                    anchor_loss = _float(end_result.get("Anchorage-set loss at anchorage (MPa)"), 0.0)
                    affected_length = _float(end_result.get("Affected length (m)"), 0.0)
                    component_loss_mpa = _single_end_anchor_loss_mpa(
                        branch, x_m=x_m, anchor_loss_mpa=anchor_loss
                    )
                    final_stress = max(friction_stress - component_loss_mpa, 0.0)
                    status = str(end_result.get("Status") or "PREVIEW READY + NOTE")
                    issue = str(end_result.get("Issue") or "")
            elif mode == "BOTH-END SIMULTANEOUS COUPLED" and controlling is not None:
                full = full_cache.get(tendon_id, [])
                neutral = controlling.get("Neutral point s (m)")
                meeting = controlling.get("Meeting stress after seating (MPa)")
                if full and neutral is not None and meeting is not None:
                    neutral_value = _float(neutral, 0.0)
                    seating_end = "Left" if station <= neutral_value else "Right"
                    end_result = end_map.get((tendon_id, seating_end)) or controlling
                    affected_length = _float(end_result.get("Affected length (m)"), 0.0)
                    final_stress = max(
                        _coupled_final_stress_mpa(
                            full,
                            station_m=station,
                            neutral_station_m=neutral_value,
                            meeting_stress_mpa=_float(meeting, 0.0),
                        ),
                        0.0,
                    )
                    component_loss_mpa = max(friction_stress - final_stress, 0.0)
                    status = str(end_result.get("Status") or "PREVIEW READY + NOTE")
                    issue = str(end_result.get("Issue") or "")
            else:
                if controlling is not None:
                    status = str(controlling.get("Status") or "REVIEW REQUIRED")
                    issue = str(controlling.get("Issue") or controlling.get("Blocking issue") or issue)
        else:
            seating_end = _source_end_name(row)
            end_result = end_map.get((tendon_id, seating_end))
            x_m = max(_float(row.get("x from jack (m)"), 0.0), 0.0)
            if (
                end_result is not None
                and str(end_result.get("Interaction mode") or "") == "SINGLE-END FRICTION-COUPLED"
                and end_result.get("Anchorage-set loss at anchorage (MPa)") is not None
                and str(end_result.get("Status") or "").startswith("PREVIEW READY")
            ):
                branch = branch_cache.get((tendon_id, seating_end), [])
                anchor_loss = _float(end_result.get("Anchorage-set loss at anchorage (MPa)"), 0.0)
                affected_length = _float(end_result.get("Affected length (m)"), 0.0)
                component_loss_mpa = (
                    _single_end_anchor_loss_mpa(branch, x_m=x_m, anchor_loss_mpa=anchor_loss)
                    if branch
                    else None
                )
                if component_loss_mpa is not None:
                    final_stress = max(friction_stress - component_loss_mpa, 0.0)
                    status = str(end_result.get("Status") or "PREVIEW READY + NOTE")
                    issue = str(end_result.get("Issue") or "")
            elif end_result is not None:
                status = str(end_result.get("Status") or "REVIEW REQUIRED")
                issue = str(end_result.get("Issue") or end_result.get("Blocking issue") or issue)

        if final_stress is not None:
            final_force = aps_total * final_stress / 1000.0
            component_loss_kn = max(friction_force - final_force, 0.0)
            applied = bool(component_loss_mpa is not None and component_loss_mpa > 1.0e-9)

        output.append(
            {
                **row,
                "Seating end": seating_end,
                "Anchorage set applied": applied,
                "Influence length (m)": affected_length,
                "Affected length (m)": affected_length,
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
    """Return dashboard values for the active PTLOSS2R2 anchorage-set methodology."""

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
