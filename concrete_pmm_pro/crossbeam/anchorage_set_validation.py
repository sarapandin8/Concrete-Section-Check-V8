"""Independent QA checks for Crossbeam anchorage-set calculations.

This module deliberately does not import or call the production anchorage-set
solver helpers.  PTLOSS2R3A uses it only as an audit layer so an independently
implemented dense-grid force/compatibility calculation can be compared with the
production simultaneous-both-end result.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any, Callable


DEFAULT_DENSE_GRID_STEPS = 8000
DEFAULT_STATION_TOLERANCE_M = 1.0e-3
DEFAULT_STRESS_TOLERANCE_MPA = 1.0e-2


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


def _piecewise_linear_value(
    rows: list[dict[str, float]],
    station_m: float,
    field: str,
) -> float:
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


def _integrate_dense(
    start_m: float,
    end_m: float,
    fn: Callable[[float], float],
    *,
    length_m: float,
    n_steps: int,
) -> float:
    if end_m <= start_m:
        return 0.0
    span = end_m - start_m
    steps = max(80, int(max(n_steps, 200) * span / max(length_m, 1.0e-9)))
    h = span / steps
    total = 0.5 * (fn(start_m) + fn(end_m))
    for index in range(1, steps):
        total += fn(start_m + index * h)
    return total * h


def _canonical_tendon_trace(
    friction_rows: list[dict[str, Any]],
    *,
    tendon_id: str,
    length_m: float,
) -> list[dict[str, float]]:
    selected: dict[float, dict[str, float]] = {}
    for row in friction_rows:
        if str(row.get("Tendon ID") or "") != str(tendon_id):
            continue
        left = row.get("Stress from left jack (MPa)")
        right = row.get("Stress from right jack (MPa)")
        initial = row.get("Stress after friction (MPa)")
        if left is None or right is None or initial is None:
            continue
        station = min(max(_float(row.get("s (m)"), 0.0), 0.0), max(length_m, 0.0))
        selected[round(station, 9)] = {
            "s_m": station,
            "left_mpa": _float(left, 0.0),
            "right_mpa": _float(right, 0.0),
            "initial_mpa": _float(initial, 0.0),
        }
    return [selected[key] for key in sorted(selected)]


def _solve_independent_coupled(
    rows: list[dict[str, float]],
    *,
    length_m: float,
    anchor_set_mm: float,
    ep_mpa: float,
    n_steps: int,
) -> dict[str, float] | None:
    if len(rows) < 2 or length_m <= 0.0 or anchor_set_mm <= 0.0 or ep_mpa <= 0.0:
        return None

    def f_left(s: float) -> float:
        return _piecewise_linear_value(rows, s, "left_mpa")

    def f_right(s: float) -> float:
        return _piecewise_linear_value(rows, s, "right_mpa")

    def f_initial(s: float) -> float:
        return _piecewise_linear_value(rows, s, "initial_mpa")

    target_area = anchor_set_mm * ep_mpa / 1000.0

    def meeting_from_left(sn: float) -> float:
        initial_area = _integrate_dense(
            0.0, sn, f_initial, length_m=length_m, n_steps=n_steps
        )
        left_area = _integrate_dense(
            0.0, sn, f_left, length_m=length_m, n_steps=n_steps
        )
        return (initial_area + left_area - sn * f_left(sn) - target_area) / sn

    def right_residual(sn: float) -> tuple[float, float]:
        meeting = meeting_from_left(sn)
        final_area = _integrate_dense(
            sn,
            length_m,
            lambda s: meeting + f_right(sn) - f_right(s),
            length_m=length_m,
            n_steps=n_steps,
        )
        initial_area = _integrate_dense(
            sn, length_m, f_initial, length_m=length_m, n_steps=n_steps
        )
        return initial_area - final_area - target_area, meeting

    epsilon = max(length_m * 1.0e-8, 1.0e-7)
    sample_count = 240
    samples = [
        epsilon + (length_m - 2.0 * epsilon) * index / sample_count
        for index in range(sample_count + 1)
    ]
    bracket: tuple[float, float, float, float] | None = None
    previous_x = samples[0]
    previous_r, _ = right_residual(previous_x)
    for current_x in samples[1:]:
        current_r, _ = right_residual(current_x)
        if abs(previous_r) <= 1.0e-10:
            bracket = (previous_x, previous_x, previous_r, previous_r)
            break
        if previous_r * current_r <= 0.0:
            bracket = (previous_x, current_x, previous_r, current_r)
            break
        previous_x = current_x
        previous_r = current_r
    if bracket is None:
        return None

    lo, hi, r_lo, _ = bracket
    if hi > lo:
        for _ in range(90):
            mid = 0.5 * (lo + hi)
            residual, _ = right_residual(mid)
            if abs(residual) <= 1.0e-11:
                lo = hi = mid
                break
            if r_lo * residual <= 0.0:
                hi = mid
            else:
                lo = mid
                r_lo = residual
    sn = 0.5 * (lo + hi)
    _, meeting = right_residual(sn)
    final_left_anchor = meeting + f_left(sn) - f_left(0.0)
    final_right_anchor = meeting + f_right(sn) - f_right(length_m)
    return {
        "neutral_station_m": sn,
        "meeting_stress_mpa": meeting,
        "left_anchor_loss_mpa": f_initial(0.0) - final_left_anchor,
        "right_anchor_loss_mpa": f_initial(length_m) - final_right_anchor,
    }


def independent_both_end_dense_grid_validation(
    friction_rows: Any,
    end_rows: Any,
    *,
    length_m: float,
    anchor_set_mm: float,
    ep_mpa: float,
    n_steps: int = DEFAULT_DENSE_GRID_STEPS,
    station_tolerance_m: float = DEFAULT_STATION_TOLERANCE_M,
    stress_tolerance_mpa: float = DEFAULT_STRESS_TOLERANCE_MPA,
) -> dict[str, Any]:
    """Compare production coupled results with an independent dense-grid solve.

    The verifier reconstructs only the accepted left/right/initial friction
    traces and numerically integrates them on its own dense grid.  It does not
    call production anchorage-set interpolation, area, or coupled-solver helpers.
    """

    friction = _records(friction_rows)
    ends = _records(end_rows)
    coupled_by_tendon: dict[str, list[dict[str, Any]]] = {}
    for row in ends:
        tendon = str(row.get("Tendon ID") or "")
        if not tendon:
            continue
        if "BOTH-END SIMULTANEOUS COUPLED" not in str(row.get("Interaction mode") or ""):
            continue
        if not str(row.get("Status") or "").startswith("PREVIEW READY"):
            continue
        coupled_by_tendon.setdefault(tendon, []).append(row)

    tendon_rows: list[dict[str, Any]] = []
    for tendon_id, production_rows in sorted(coupled_by_tendon.items()):
        trace = _canonical_tendon_trace(friction, tendon_id=tendon_id, length_m=length_m)
        independent = _solve_independent_coupled(
            trace,
            length_m=length_m,
            anchor_set_mm=anchor_set_mm,
            ep_mpa=ep_mpa,
            n_steps=n_steps,
        )
        by_end = {str(row.get("Seating end") or ""): row for row in production_rows}
        left = by_end.get("Left")
        right = by_end.get("Right")
        if independent is None or left is None or right is None:
            tendon_rows.append(
                {
                    "Tendon ID": tendon_id,
                    "Status": "REVIEW",
                    "Issue": "Independent dense-grid solution could not be established.",
                }
            )
            continue

        production_neutral = _float(left.get("Neutral point s (m)"), 0.0)
        production_meeting = _float(left.get("Meeting stress after seating (MPa)"), 0.0)
        production_left_loss = _float(left.get("Anchorage-set loss at anchorage (MPa)"), 0.0)
        production_right_loss = _float(right.get("Anchorage-set loss at anchorage (MPa)"), 0.0)
        neutral_diff = abs(production_neutral - independent["neutral_station_m"])
        meeting_diff = abs(production_meeting - independent["meeting_stress_mpa"])
        left_diff = abs(production_left_loss - independent["left_anchor_loss_mpa"])
        right_diff = abs(production_right_loss - independent["right_anchor_loss_mpa"])
        status = (
            "PASS"
            if neutral_diff <= station_tolerance_m
            and max(meeting_diff, left_diff, right_diff) <= stress_tolerance_mpa
            else "REVIEW"
        )
        tendon_rows.append(
            {
                "Tendon ID": tendon_id,
                "Status": status,
                "Neutral station diff (m)": neutral_diff,
                "Meeting stress diff (MPa)": meeting_diff,
                "Left anchor-loss diff (MPa)": left_diff,
                "Right anchor-loss diff (MPa)": right_diff,
                "Independent neutral s (m)": independent["neutral_station_m"],
                "Independent meeting stress (MPa)": independent["meeting_stress_mpa"],
                "Independent left loss (MPa)": independent["left_anchor_loss_mpa"],
                "Independent right loss (MPa)": independent["right_anchor_loss_mpa"],
                "Issue": "",
            }
        )

    applicable = bool(tendon_rows)
    passed = applicable and all(row.get("Status") == "PASS" for row in tendon_rows)
    numeric_rows = [row for row in tendon_rows if row.get("Status") in {"PASS", "REVIEW"} and row.get("Neutral station diff (m)") is not None]
    return {
        "status": "PASS" if passed else ("NOT APPLICABLE" if not applicable else "REVIEW"),
        "tendon_rows": tendon_rows,
        "station_tolerance_m": float(station_tolerance_m),
        "stress_tolerance_mpa": float(stress_tolerance_mpa),
        "max_neutral_station_diff_m": max((float(row["Neutral station diff (m)"]) for row in numeric_rows), default=0.0),
        "max_meeting_stress_diff_mpa": max((float(row["Meeting stress diff (MPa)"]) for row in numeric_rows), default=0.0),
        "max_left_anchor_loss_diff_mpa": max((float(row["Left anchor-loss diff (MPa)"]) for row in numeric_rows), default=0.0),
        "max_right_anchor_loss_diff_mpa": max((float(row["Right anchor-loss diff (MPa)"]) for row in numeric_rows), default=0.0),
    }
