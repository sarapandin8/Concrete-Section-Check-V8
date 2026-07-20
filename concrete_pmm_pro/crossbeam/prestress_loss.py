"""AASHTO LRFD prestress-loss foundation for Crossbeam tendons.

PTLOSS1 implements the post-tensioned friction/wobble component from AASHTO
LRFD 5.9.3.2.2b.  It deliberately stops before anchorage set, elastic
shortening, creep, shrinkage, relaxation, SLS stress, ULS strength,
anchorage-zone, deviator-force, and D-region calculations.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from math import atan, exp, hypot, isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.tendon import canonical_tendon_profile_points
from concrete_pmm_pro.crossbeam.tendon_analysis import tendon_force_source_rows


CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY = "crossbeam_prestress_loss_settings"
CROSSBEAM_PRESTRESS_LOSS_SCHEMA_VERSION = 1

CB_LOSS_INTERNAL_MU_KEY = "crossbeam_ptloss1_internal_mu"
CB_LOSS_INTERNAL_K_PER_M_KEY = "crossbeam_ptloss1_internal_k_per_m"
CB_LOSS_EXTERNAL_MU_KEY = "crossbeam_ptloss1_external_deviator_mu"
CB_LOSS_EXTERNAL_INADVERTENT_ANGLE_KEY = "crossbeam_ptloss1_external_inadvertent_angle_rad"

AASHTO_PTL_FRICTION_BASIS = "AASHTO LRFD 5.9.3.2.2b"
AASHTO_INTERNAL_WOBBLE_K_PER_FT = 0.0002
AASHTO_POLYETHYLENE_DUCT_MU = 0.23
AASHTO_EXTERNAL_RIGID_STEEL_PIPE_DEVIATOR_MU = 0.25
FT_PER_M = 3.280839895013123
DEFAULT_INTERNAL_WOBBLE_K_PER_M = AASHTO_INTERNAL_WOBBLE_K_PER_FT * FT_PER_M
DEFAULT_INTERNAL_FRICTION_MU = 0.20
DEFAULT_EXTERNAL_HDPE_LINED_CONSERVATIVE_MU = AASHTO_EXTERNAL_RIGID_STEEL_PIPE_DEVIATOR_MU
DEFAULT_EXTERNAL_DEVIATOR_MU = DEFAULT_EXTERNAL_HDPE_LINED_CONSERVATIVE_MU
DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD = 0.04


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(max(float(value), float(lower)), float(upper))


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


def default_crossbeam_prestress_loss_settings() -> dict[str, float | int | str]:
    """Return PTLOSS1 defaults using SI units for app inputs."""

    return {
        "schema_version": CROSSBEAM_PRESTRESS_LOSS_SCHEMA_VERSION,
        "basis": AASHTO_PTL_FRICTION_BASIS,
        "internal_mu": DEFAULT_INTERNAL_FRICTION_MU,
        "internal_k_per_m": DEFAULT_INTERNAL_WOBBLE_K_PER_M,
        "external_deviator_mu": DEFAULT_EXTERNAL_DEVIATOR_MU,
        "external_inadvertent_angle_rad": DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD,
    }


def normalize_crossbeam_prestress_loss_settings(value: Any) -> dict[str, float | int | str]:
    """Return bounded PTLOSS1 settings from metadata or session state values."""

    defaults = default_crossbeam_prestress_loss_settings()
    source = value if isinstance(value, Mapping) else {}
    return {
        "schema_version": CROSSBEAM_PRESTRESS_LOSS_SCHEMA_VERSION,
        "basis": AASHTO_PTL_FRICTION_BASIS,
        "internal_mu": _clamp(
            _float(source.get("internal_mu"), float(defaults["internal_mu"])),
            0.0,
            1.0,
        ),
        "internal_k_per_m": _clamp(
            _float(source.get("internal_k_per_m"), float(defaults["internal_k_per_m"])),
            0.0,
            0.02,
        ),
        "external_deviator_mu": _clamp(
            _float(source.get("external_deviator_mu"), float(defaults["external_deviator_mu"])),
            0.0,
            1.0,
        ),
        "external_inadvertent_angle_rad": _clamp(
            _float(
                source.get("external_inadvertent_angle_rad"),
                float(defaults["external_inadvertent_angle_rad"]),
            ),
            0.0,
            0.25,
        ),
    }


def crossbeam_prestress_loss_settings_from_session_state(session_state: Any) -> dict[str, Any]:
    """Return JSON-safe loss settings when the PTLOSS1 page has been used."""

    if not any(
        key in session_state
        for key in (
            CB_LOSS_INTERNAL_MU_KEY,
            CB_LOSS_INTERNAL_K_PER_M_KEY,
            CB_LOSS_EXTERNAL_MU_KEY,
            CB_LOSS_EXTERNAL_INADVERTENT_ANGLE_KEY,
        )
    ):
        return {}
    settings = normalize_crossbeam_prestress_loss_settings(
        {
            "internal_mu": session_state.get(CB_LOSS_INTERNAL_MU_KEY),
            "internal_k_per_m": session_state.get(CB_LOSS_INTERNAL_K_PER_M_KEY),
            "external_deviator_mu": session_state.get(CB_LOSS_EXTERNAL_MU_KEY),
            "external_inadvertent_angle_rad": session_state.get(CB_LOSS_EXTERNAL_INADVERTENT_ANGLE_KEY),
        }
    )
    return dict(settings)


def restore_crossbeam_prestress_loss_project_state(
    project_metadata: Mapping[str, Any] | None,
    session_state: MutableMapping[str, Any],
) -> dict[str, Any] | None:
    """Restore PTLOSS1 settings from Project JSON metadata."""

    for key in (
        CB_LOSS_INTERNAL_MU_KEY,
        CB_LOSS_INTERNAL_K_PER_M_KEY,
        CB_LOSS_EXTERNAL_MU_KEY,
        CB_LOSS_EXTERNAL_INADVERTENT_ANGLE_KEY,
    ):
        session_state.pop(key, None)

    source = project_metadata if isinstance(project_metadata, Mapping) else {}
    raw = source.get(CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY)
    if not isinstance(raw, Mapping):
        return None

    settings = normalize_crossbeam_prestress_loss_settings(raw)
    session_state[CB_LOSS_INTERNAL_MU_KEY] = float(settings["internal_mu"])
    session_state[CB_LOSS_INTERNAL_K_PER_M_KEY] = float(settings["internal_k_per_m"])
    session_state[CB_LOSS_EXTERNAL_MU_KEY] = float(settings["external_deviator_mu"])
    session_state[CB_LOSS_EXTERNAL_INADVERTENT_ANGLE_KEY] = float(
        settings["external_inadvertent_angle_rad"]
    )
    return settings


def _profile_points_by_tendon(profile_values: Any, length_m: float) -> dict[str, list[dict[str, Any]]]:
    by_id: dict[str, list[dict[str, Any]]] = {}
    for point in canonical_tendon_profile_points(profile_values, length_m):
        by_id.setdefault(str(point.get("Tendon ID") or ""), []).append(point)
    for tendon_id, points in by_id.items():
        by_id[tendon_id] = sorted(points, key=lambda row: _float(row.get("s (m)"), 0.0))
    return by_id


def _interval_angles(points: list[Mapping[str, Any]]) -> tuple[list[float], list[float]]:
    vertical: list[float] = []
    horizontal: list[float] = []
    for left, right in zip(points, points[1:]):
        ds_m = _float(right.get("s (m)"), 0.0) - _float(left.get("s (m)"), 0.0)
        if abs(ds_m) <= 1.0e-12:
            vertical.append(0.0)
            horizontal.append(0.0)
            continue
        ddtop_m = (
            _float(right.get("dtop (mm)"), 0.0)
            - _float(left.get("dtop (mm)"), 0.0)
        ) / 1000.0
        dx_m = (
            _float(right.get("x lateral (mm)"), 0.0)
            - _float(left.get("x lateral (mm)"), 0.0)
        ) / 1000.0
        vertical.append(atan(ddtop_m / ds_m))
        horizontal.append(atan(dx_m / ds_m))
    return vertical, horizontal


def _cumulative_angle_rows(points: list[Mapping[str, Any]]) -> list[dict[str, float]]:
    if not points:
        return []
    vertical_angles, horizontal_angles = _interval_angles(points)
    rows: list[dict[str, float]] = []
    alpha_v = 0.0
    alpha_h = 0.0
    alpha_total = 0.0
    deviators = 0
    last_interior_index = max(len(points) - 2, 0)
    for index, point in enumerate(points):
        if 0 < index <= last_interior_index:
            delta_v = abs(vertical_angles[index] - vertical_angles[index - 1])
            delta_h = abs(horizontal_angles[index] - horizontal_angles[index - 1])
            alpha_v += delta_v
            alpha_h += delta_h
            alpha_total += hypot(delta_v, delta_h)
            if str(point.get("Curve role") or "").strip() == "Deviator":
                deviators += 1
        rows.append(
            {
                "alpha_v_rad": alpha_v,
                "alpha_h_rad": alpha_h,
                "alpha_total_rad": alpha_total,
                "deviator_count": float(deviators),
            }
        )
    return rows


def _angle_lookup_from_left(points: list[dict[str, Any]]) -> dict[tuple[str, float], dict[str, float]]:
    rows = _cumulative_angle_rows(points)
    return {
        (str(point.get("Point") or ""), round(_float(point.get("s (m)"), 0.0), 9)): rows[index]
        for index, point in enumerate(points)
    }


def _angle_lookup_from_right(points: list[dict[str, Any]]) -> dict[tuple[str, float], dict[str, float]]:
    reversed_points = list(reversed(points))
    reversed_rows = _cumulative_angle_rows(reversed_points)
    lookup: dict[tuple[str, float], dict[str, float]] = {}
    for point, row in zip(reversed_points, reversed_rows):
        lookup[(str(point.get("Point") or ""), round(_float(point.get("s (m)"), 0.0), 9))] = row
    return lookup


def _source_end_values(
    *,
    jacking_end: str,
    station_m: float,
    length_m: float,
    left_angles: Mapping[str, float],
    right_angles: Mapping[str, float],
) -> tuple[str, float, Mapping[str, float]]:
    left_x = max(station_m, 0.0)
    right_x = max(length_m - station_m, 0.0)
    normalized = str(jacking_end or "").strip().casefold()
    if normalized == "left":
        return "Left", left_x, left_angles
    if normalized == "right":
        return "Right", right_x, right_angles
    if left_x <= right_x:
        return "Left (nearest)", left_x, left_angles
    return "Right (nearest)", right_x, right_angles


def aashto_friction_wobble_station_rows(
    profile_values: Any,
    system_values: Any,
    *,
    length_m: float,
    internal_mu: float = DEFAULT_INTERNAL_FRICTION_MU,
    internal_k_per_m: float = DEFAULT_INTERNAL_WOBBLE_K_PER_M,
    external_deviator_mu: float = DEFAULT_EXTERNAL_DEVIATOR_MU,
    external_inadvertent_angle_rad: float = DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD,
) -> list[dict[str, Any]]:
    """Return station-level AASHTO friction/wobble loss rows.

    Internal tendons use AASHTO Eq. 5.9.3.2.2b-1:
    ``Delta fpF = fpj * (1 - exp(-(Kx + mu alpha)))``.

    Both-end jacking follows the AASHTO definition of ``alpha`` from the
    nearest jacking end when tensioning is done equally at both ends.  The
    source jacking force is never doubled.
    """

    length = max(_float(length_m, 20.0), 0.1)
    mu_internal = _clamp(_float(internal_mu, DEFAULT_INTERNAL_FRICTION_MU), 0.0, 1.0)
    k_internal = _clamp(
        _float(internal_k_per_m, DEFAULT_INTERNAL_WOBBLE_K_PER_M),
        0.0,
        0.02,
    )
    mu_external = _clamp(
        _float(external_deviator_mu, DEFAULT_EXTERNAL_DEVIATOR_MU),
        0.0,
        1.0,
    )
    inadvertent = _clamp(
        _float(external_inadvertent_angle_rad, DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD),
        0.0,
        0.25,
    )
    force_by_id = {
        str(row.get("Tendon ID") or ""): row
        for row in tendon_force_source_rows(system_values)
        if str(row.get("Tendon ID") or "")
    }
    points_by_id = _profile_points_by_tendon(profile_values, length)
    rows: list[dict[str, Any]] = []
    for tendon_id, points in points_by_id.items():
        force = force_by_id.get(tendon_id)
        if force is None:
            continue
        left_lookup = _angle_lookup_from_left(points)
        right_lookup = _angle_lookup_from_right(points)
        tendon_type = str(force.get("Type") or "Internal")
        jacking_end = str(force.get("Jacking end") or "Both")
        tendon_deviator_count = sum(
            1 for point in points if str(point.get("Curve role") or "").strip() == "Deviator"
        )
        for point in points:
            station_m = min(max(_float(point.get("s (m)"), 0.0), 0.0), length)
            key = (str(point.get("Point") or ""), round(station_m, 9))
            source_end, x_from_jack_m, angles = _source_end_values(
                jacking_end=jacking_end,
                station_m=station_m,
                length_m=length,
                left_angles=left_lookup.get(key, {}),
                right_angles=right_lookup.get(key, {}),
            )
            alpha_v = _float(angles.get("alpha_v_rad"), 0.0)
            alpha_h = _float(angles.get("alpha_h_rad"), 0.0)
            alpha_total = _float(angles.get("alpha_total_rad"), 0.0)
            deviator_count = int(round(_float(angles.get("deviator_count"), 0.0)))

            fpj_mpa = _float(force.get("fpj (MPa)"), 0.0)
            aps_total = _float(force.get("Aps total (mm²)"), 0.0)
            pj_kn = _float(force.get("Pj (kN)"), 0.0)
            blocking_issues: list[str] = []
            review_notes: list[str] = []
            force_status = str(force.get("Force source status") or "REVIEW REQUIRED")
            if force_status == "REVIEW REQUIRED":
                blocking_issues.append(
                    str(force.get("Issue") or "Tendon force source requires review.")
                )
            if len(points) < 2:
                blocking_issues.append("At least two profile points are required for friction loss.")
            if aps_total <= 0.0 or fpj_mpa <= 0.0 or pj_kn <= 0.0:
                blocking_issues.append("Positive Aps, fpj, and Pj are required.")

            if tendon_type == "External":
                k_used = None
                mu_used = mu_external
                exponent = mu_used * (alpha_total + inadvertent * deviator_count)
                equation = "AASHTO 5.9.3.2.2b-2 external HDPE-lined deviator preview"
                k_basis = "External: N/A, no Kx"
                mu_basis = "HDPE-lined: adopted 0.25"
                review_notes.append(
                    "External tendon friction is an HDPE-lined deviator preview; verify PT supplier data, angle tolerances, and stressing sequence."
                )
                if tendon_deviator_count <= 0:
                    blocking_issues.append(
                        "External tendon has no Deviator point; AASHTO 0.04 rad/deviator is not applied."
                    )
            else:
                k_used = k_internal
                mu_used = mu_internal
                exponent = k_used * x_from_jack_m + mu_used * alpha_total
                equation = "AASHTO 5.9.3.2.2b-1 internal duct friction/wobble"
                k_basis = "Internal: AASHTO K"
                mu_basis = "Internal duct mu"

            exponent = max(exponent, 0.0)
            remaining_ratio = exp(-exponent) if exponent < 80.0 else 0.0
            loss_mpa = fpj_mpa * (1.0 - remaining_ratio)
            f_after_mpa = max(fpj_mpa - loss_mpa, 0.0)
            p_after_kn = aps_total * f_after_mpa / 1000.0
            loss_kn = max(pj_kn - p_after_kn, 0.0)
            active = bool(force.get("Active"))
            if not active:
                status = "STORED ONLY"
            elif blocking_issues:
                status = "REVIEW REQUIRED"
            elif review_notes:
                status = "LOSS READY + NOTE"
            else:
                status = "LOSS READY"
            issue_text = " ".join(dict.fromkeys(blocking_issues + review_notes))
            blocking_issue_text = " ".join(dict.fromkeys(blocking_issues))
            review_note_text = " ".join(dict.fromkeys(review_notes))

            rows.append(
                {
                    "Tendon ID": tendon_id,
                    "Active": active,
                    "Type": tendon_type,
                    "Jacking end": jacking_end,
                    "Source end": source_end,
                    "Point": str(point.get("Point") or ""),
                    "Curve role": str(point.get("Curve role") or ""),
                    "s (m)": station_m,
                    "x from jack (m)": x_from_jack_m,
                    "alpha_v (rad)": alpha_v,
                    "alpha_h (rad)": alpha_h,
                    "alpha total (rad)": alpha_total,
                    "Deviators counted": deviator_count,
                    "K (/m)": k_used,
                    "K basis": k_basis,
                    "mu": mu_used,
                    "mu basis": mu_basis,
                    "Exponent": exponent,
                    "Aps total (mm²)": aps_total,
                    "fpj (MPa)": fpj_mpa,
                    "Pj (kN)": pj_kn,
                    "Friction loss (MPa)": loss_mpa,
                    "Friction loss (kN)": loss_kn,
                    "Stress after friction (MPa)": f_after_mpa,
                    "P after friction (kN)": p_after_kn,
                    "P/Pj after friction": 0.0 if pj_kn <= 0.0 else p_after_kn / pj_kn,
                    "Equation": equation,
                    "Status": status,
                    "Issue": "OK" if not issue_text else issue_text,
                    "Blocking issue": blocking_issue_text,
                    "Review note": review_note_text,
                }
            )
    return rows


def aashto_friction_wobble_tendon_summary_rows(loss_rows: Any) -> list[dict[str, Any]]:
    """Return one worst traced station summary row per tendon."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in _records(loss_rows):
        grouped.setdefault(str(row.get("Tendon ID") or ""), []).append(row)

    summaries: list[dict[str, Any]] = []
    for tendon_id, rows in sorted(grouped.items()):
        if not rows:
            continue
        active = any(bool(row.get("Active")) for row in rows)
        review = any(str(row.get("Status") or "") == "REVIEW REQUIRED" for row in rows)
        note = any(str(row.get("Status") or "") == "LOSS READY + NOTE" for row in rows)
        stored_only = all(str(row.get("Status") or "") == "STORED ONLY" for row in rows)
        worst = max(rows, key=lambda row: _float(row.get("Friction loss (kN)"), 0.0))
        status = (
            "STORED ONLY"
            if stored_only
            else "REVIEW REQUIRED"
            if review
            else "LOSS READY + NOTE"
            if note
            else "LOSS READY"
        )
        blocking_issues = list(
            dict.fromkeys(
                str(row.get("Blocking issue") or "")
                for row in rows
                if str(row.get("Blocking issue") or "")
            )
        )
        review_notes = list(
            dict.fromkeys(
                str(row.get("Review note") or "")
                for row in rows
                if str(row.get("Review note") or "")
            )
        )
        summaries.append(
            {
                "Tendon ID": tendon_id,
                "Active": active,
                "Type": str(worst.get("Type") or ""),
                "Jacking end": str(worst.get("Jacking end") or ""),
                "Worst point": str(worst.get("Point") or ""),
                "Worst s (m)": _float(worst.get("s (m)"), 0.0),
                "Pj (kN)": _float(worst.get("Pj (kN)"), 0.0),
                "Min P after friction (kN)": min(
                    _float(row.get("P after friction (kN)"), 0.0) for row in rows
                ),
                "Max friction loss (kN)": _float(worst.get("Friction loss (kN)"), 0.0),
                "Max friction loss (%)": 100.0
                * (
                    1.0
                    - min(_float(row.get("P/Pj after friction"), 0.0) for row in rows)
                ),
                "Max alpha (rad)": max(_float(row.get("alpha total (rad)"), 0.0) for row in rows),
                "Max exponent": max(_float(row.get("Exponent"), 0.0) for row in rows),
                "Status": status,
                "Issue": "OK" if not blocking_issues and not review_notes else " ".join(blocking_issues + review_notes),
            }
        )
    return summaries


def _is_calculated_loss_row(row: Mapping[str, Any]) -> bool:
    if not bool(row.get("Active")):
        return False
    if str(row.get("Status") or "") == "STORED ONLY":
        return False
    pj_kn = _float(row.get("Pj (kN)"), 0.0)
    ratio = _float(row.get("P/Pj after friction"), 1.0)
    return pj_kn > 0.0 and 0.0 <= ratio <= 1.0


def aashto_friction_wobble_summary(loss_rows: Any) -> dict[str, Any]:
    """Return dashboard values for the PTLOSS1 friction/wobble foundation."""

    rows = _records(loss_rows)
    active_rows = [row for row in rows if bool(row.get("Active"))]
    required_review_rows = [
        row
        for row in active_rows
        if str(row.get("Status") or "") == "REVIEW REQUIRED"
    ]
    review_note_rows = [
        row
        for row in active_rows
        if str(row.get("Status") or "") == "LOSS READY + NOTE"
    ]
    ready_rows = [
        row
        for row in active_rows
        if str(row.get("Status") or "") in {"LOSS READY", "LOSS READY + NOTE"}
    ]
    calculated_rows = [row for row in active_rows if _is_calculated_loss_row(row)]
    active_tendons = {str(row.get("Tendon ID") or "") for row in active_rows if str(row.get("Tendon ID") or "")}
    worst_loss_percent = max(
        (100.0 * (1.0 - _float(row.get("P/Pj after friction"), 0.0)) for row in calculated_rows),
        default=0.0,
    )
    min_ratio = min(
        (_float(row.get("P/Pj after friction"), 1.0) for row in calculated_rows),
        default=1.0,
    )
    blocking_issues = list(
        dict.fromkeys(
            str(row.get("Blocking issue") or "")
            for row in required_review_rows
            if str(row.get("Blocking issue") or "")
        )
    )
    review_notes = list(
        dict.fromkeys(
            str(row.get("Review note") or "")
            for row in review_note_rows
            if str(row.get("Review note") or "")
        )
    )
    if not rows:
        blocking_issues.append("No tendon profile rows are available for loss calculation.")
    if not rows or required_review_rows:
        value = "REVIEW REQUIRED"
        status = "warning"
    elif review_note_rows:
        value = "LOSS READY + NOTES"
        status = "warning"
    else:
        value = "LOSS READY"
        status = "ready"
    return {
        "value": value,
        "status": status,
        "basis": AASHTO_PTL_FRICTION_BASIS,
        "active_tendon_count": len(active_tendons),
        "station_row_count": len(rows),
        "ready_station_row_count": len(ready_rows),
        "review_station_row_count": len(required_review_rows),
        "review_note_station_row_count": len(review_note_rows),
        "calculated_station_row_count": len(calculated_rows),
        "worst_loss_percent": worst_loss_percent,
        "minimum_p_over_pj": min_ratio,
        "issues": blocking_issues + review_notes,
        "blocking_issues": blocking_issues,
        "review_notes": review_notes,
    }
