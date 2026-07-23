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
from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_PRECAST,
    DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
    DEFAULT_PRECAST_CLOSURE_STRENGTH_MPA,
    normalize_construction_method,
)


CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY = "crossbeam_prestress_loss_settings"
CROSSBEAM_PRESTRESS_LOSS_SCHEMA_VERSION = 5

CB_LOSS_INTERNAL_MU_KEY = "crossbeam_ptloss1_internal_mu"
CB_LOSS_INTERNAL_K_PER_M_KEY = "crossbeam_ptloss1_internal_k_per_m"
CB_LOSS_EXTERNAL_MU_KEY = "crossbeam_ptloss1_external_deviator_mu"
CB_LOSS_EXTERNAL_INADVERTENT_ANGLE_KEY = "crossbeam_ptloss1_external_inadvertent_angle_rad"
CB_LOSS_ANCHORAGE_SET_MM_KEY = "crossbeam_ptloss2_anchorage_set_mm"
CB_LOSS_EP_MPA_KEY = "crossbeam_ptloss2_ep_mpa"
CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY = "crossbeam_ptloss3_fcgp_override_enabled"
CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY = "crossbeam_ptloss3_fcgp_override_mpa"
CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY = "crossbeam_ptloss3_eci_override_enabled"
CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY = "crossbeam_ptloss3_eci_override_mpa"
CB_LOSS_ES_CONSTRUCTION_METHOD_KEY = "crossbeam_ptloss3b1_construction_method"
CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY = "crossbeam_ptloss3b1_stressing_strength_ratio"
CB_LOSS_ES_CLOSURE_REQUIRED_MPA_KEY = "crossbeam_ptloss3b1_closure_required_mpa"
CB_LOSS_ES_COLUMN_ROWS_KEY = "crossbeam_ptloss3b1_column_rows"
CB_LOSS_ES_PAIR_SEQUENCE_KEY = "crossbeam_ptloss3b1_pair_sequence"

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
DEFAULT_ANCHORAGE_SET_MM = 6.0
DEFAULT_PRESTRESS_STEEL_EP_MPA = 195000.0
DEFAULT_ES_FCGP_OVERRIDE_MPA = 0.0
DEFAULT_ES_ECI_OVERRIDE_MPA = 31500.0
EXTERNAL_HDPE_REVIEW_NOTE = "HDPE note: verify PT supplier, angle tolerances, sequence."
EXTERNAL_NO_DEVIATOR_ISSUE = "No Deviator point: +0.04 rad not applied."


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)



def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"true", "yes", "1", "on", "enabled"}:
        return True
    if text in {"false", "no", "0", "off", "disabled"}:
        return False
    return bool(default)

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


def default_crossbeam_prestress_loss_settings() -> dict[str, Any]:
    """Return PTLOSS1 defaults using SI units for app inputs."""

    return {
        "schema_version": CROSSBEAM_PRESTRESS_LOSS_SCHEMA_VERSION,
        "basis": AASHTO_PTL_FRICTION_BASIS,
        "internal_mu": DEFAULT_INTERNAL_FRICTION_MU,
        "internal_k_per_m": DEFAULT_INTERNAL_WOBBLE_K_PER_M,
        "external_deviator_mu": DEFAULT_EXTERNAL_DEVIATOR_MU,
        "external_inadvertent_angle_rad": DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD,
        "anchorage_set_mm": DEFAULT_ANCHORAGE_SET_MM,
        "ep_mpa": DEFAULT_PRESTRESS_STEEL_EP_MPA,
        "es_fcgp_override_enabled": False,
        "es_fcgp_override_mpa": DEFAULT_ES_FCGP_OVERRIDE_MPA,
        "es_eci_override_enabled": False,
        "es_eci_override_mpa": DEFAULT_ES_ECI_OVERRIDE_MPA,
        "es_construction_method": CONSTRUCTION_METHOD_PRECAST,
        "es_stressing_strength_ratio": DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
        "es_closure_required_mpa": DEFAULT_PRECAST_CLOSURE_STRENGTH_MPA,
        "es_column_rows": [],
        "es_pair_sequence": [],
    }


def normalize_crossbeam_prestress_loss_settings(value: Any) -> dict[str, Any]:
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
        "anchorage_set_mm": _clamp(
            _float(source.get("anchorage_set_mm"), float(defaults["anchorage_set_mm"])),
            0.0,
            50.0,
        ),
        "ep_mpa": _clamp(
            _float(source.get("ep_mpa"), float(defaults["ep_mpa"])),
            100000.0,
            250000.0,
        ),
        "es_fcgp_override_enabled": _bool(source.get("es_fcgp_override_enabled"), False),
        "es_fcgp_override_mpa": _clamp(
            _float(source.get("es_fcgp_override_mpa"), float(defaults["es_fcgp_override_mpa"])),
            0.0,
            200.0,
        ),
        "es_eci_override_enabled": _bool(source.get("es_eci_override_enabled"), False),
        "es_eci_override_mpa": _clamp(
            _float(source.get("es_eci_override_mpa"), float(defaults["es_eci_override_mpa"])),
            1000.0,
            100000.0,
        ),
        "es_construction_method": normalize_construction_method(
            source.get("es_construction_method") or defaults["es_construction_method"]
        ),
        "es_stressing_strength_ratio": _clamp(
            _float(source.get("es_stressing_strength_ratio"), float(defaults["es_stressing_strength_ratio"])),
            0.1,
            1.5,
        ),
        "es_closure_required_mpa": _clamp(
            _float(source.get("es_closure_required_mpa"), 0.0), 0.0, 200.0
        ),
        "es_column_rows": _records(source.get("es_column_rows")),
        "es_pair_sequence": [
            str(item) for item in (source.get("es_pair_sequence") or []) if str(item).strip()
        ] if isinstance(source.get("es_pair_sequence"), (list, tuple)) else [],
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
            CB_LOSS_ANCHORAGE_SET_MM_KEY,
            CB_LOSS_EP_MPA_KEY,
            CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY,
            CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY,
            CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY,
            CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY,
            CB_LOSS_ES_CONSTRUCTION_METHOD_KEY,
            CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY,
            CB_LOSS_ES_CLOSURE_REQUIRED_MPA_KEY,
            CB_LOSS_ES_COLUMN_ROWS_KEY,
            CB_LOSS_ES_PAIR_SEQUENCE_KEY,
        )
    ):
        return {}
    settings = normalize_crossbeam_prestress_loss_settings(
        {
            "internal_mu": session_state.get(CB_LOSS_INTERNAL_MU_KEY),
            "internal_k_per_m": session_state.get(CB_LOSS_INTERNAL_K_PER_M_KEY),
            "external_deviator_mu": session_state.get(CB_LOSS_EXTERNAL_MU_KEY),
            "external_inadvertent_angle_rad": session_state.get(CB_LOSS_EXTERNAL_INADVERTENT_ANGLE_KEY),
            "anchorage_set_mm": session_state.get(CB_LOSS_ANCHORAGE_SET_MM_KEY),
            "ep_mpa": session_state.get(CB_LOSS_EP_MPA_KEY),
            "es_fcgp_override_enabled": session_state.get(CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY),
            "es_fcgp_override_mpa": session_state.get(CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY),
            "es_eci_override_enabled": session_state.get(CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY),
            "es_eci_override_mpa": session_state.get(CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY),
            "es_construction_method": session_state.get(CB_LOSS_ES_CONSTRUCTION_METHOD_KEY),
            "es_stressing_strength_ratio": session_state.get(CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY),
            "es_closure_required_mpa": session_state.get(CB_LOSS_ES_CLOSURE_REQUIRED_MPA_KEY),
            "es_column_rows": session_state.get(CB_LOSS_ES_COLUMN_ROWS_KEY),
            "es_pair_sequence": session_state.get(CB_LOSS_ES_PAIR_SEQUENCE_KEY),
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
        CB_LOSS_ANCHORAGE_SET_MM_KEY,
        CB_LOSS_EP_MPA_KEY,
        CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY,
        CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY,
        CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY,
        CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY,
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY,
        CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY,
        CB_LOSS_ES_CLOSURE_REQUIRED_MPA_KEY,
        CB_LOSS_ES_COLUMN_ROWS_KEY,
        CB_LOSS_ES_PAIR_SEQUENCE_KEY,
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
    session_state[CB_LOSS_ANCHORAGE_SET_MM_KEY] = float(settings["anchorage_set_mm"])
    session_state[CB_LOSS_EP_MPA_KEY] = float(settings["ep_mpa"])
    session_state[CB_LOSS_ES_FCGP_OVERRIDE_ENABLED_KEY] = bool(settings["es_fcgp_override_enabled"])
    session_state[CB_LOSS_ES_FCGP_OVERRIDE_MPA_KEY] = float(settings["es_fcgp_override_mpa"])
    session_state[CB_LOSS_ES_ECI_OVERRIDE_ENABLED_KEY] = bool(settings["es_eci_override_enabled"])
    session_state[CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY] = float(settings["es_eci_override_mpa"])
    session_state[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] = str(settings["es_construction_method"])
    session_state[CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY] = float(settings["es_stressing_strength_ratio"])
    session_state[CB_LOSS_ES_CLOSURE_REQUIRED_MPA_KEY] = float(settings["es_closure_required_mpa"])
    session_state[CB_LOSS_ES_COLUMN_ROWS_KEY] = [dict(row) for row in settings["es_column_rows"]]
    session_state[CB_LOSS_ES_PAIR_SEQUENCE_KEY] = list(settings["es_pair_sequence"])
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



def friction_wobble_unit_audit(
    *,
    adopted_internal_k_per_m: float = DEFAULT_INTERNAL_WOBBLE_K_PER_M,
) -> dict[str, Any]:
    """Return explicit US-customary-to-SI conversion and dimensional checks.

    The accepted PTLOSS1 reference value is expressed per foot. The Crossbeam
    solver uses metres, therefore K must be converted to 1/m before forming the
    dimensionless exponent Kx + mu*alpha.
    """

    adopted_k = max(_float(adopted_internal_k_per_m, DEFAULT_INTERNAL_WOBBLE_K_PER_M), 0.0)
    reference_k_si = AASHTO_INTERNAL_WOBBLE_K_PER_FT * FT_PER_M
    source_roundtrip = reference_k_si / FT_PER_M
    return {
        "source_k_per_ft": AASHTO_INTERNAL_WOBBLE_K_PER_FT,
        "ft_per_m": FT_PER_M,
        "reference_k_per_m": reference_k_si,
        "source_roundtrip_k_per_ft": source_roundtrip,
        "source_conversion_residual": source_roundtrip - AASHTO_INTERNAL_WOBBLE_K_PER_FT,
        "adopted_k_per_m": adopted_k,
        "adopted_k_per_ft_equivalent": adopted_k / FT_PER_M,
        "kx_unit_check": "PASS — (1/m) × m is dimensionless",
        "mu_alpha_unit_check": "PASS — μ is dimensionless and α is in radians",
    }


def friction_wobble_formula_audit_rows(
    loss_rows: Any,
    *,
    external_inadvertent_angle_rad: float = DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD,
) -> list[dict[str, Any]]:
    """Return representative substituted-equation rows without changing the solver.

    One governing traced station is returned for each tendon type so the UI can
    expose the exact dimensionless terms used by the accepted PTLOSS1 solver.
    """

    rows = _records(loss_rows)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not bool(row.get("Active")):
            continue
        grouped.setdefault(str(row.get("Type") or "Internal"), []).append(row)

    audit_rows: list[dict[str, Any]] = []
    angle_add = max(_float(external_inadvertent_angle_rad, DEFAULT_EXTERNAL_INADVERTENT_ANGLE_RAD), 0.0)
    for tendon_type, type_rows in sorted(grouped.items()):
        if not type_rows:
            continue
        row = max(type_rows, key=lambda item: _float(item.get("Exponent"), 0.0))
        x_m = _float(row.get("x from jack (m)"), 0.0)
        alpha = _float(row.get("alpha total (rad)"), 0.0)
        mu = _float(row.get("mu"), 0.0)
        deviators = int(round(_float(row.get("Deviators counted"), 0.0)))
        k_value = row.get("K (/m)")
        kx = 0.0 if k_value is None else _float(k_value, 0.0) * x_m
        effective_angle = alpha
        if str(tendon_type).strip().casefold() == "external":
            effective_angle += angle_add * deviators
        mu_angle = mu * effective_angle
        recomputed_exponent = kx + mu_angle
        stored_exponent = _float(row.get("Exponent"), 0.0)
        fpj = _float(row.get("fpj (MPa)"), 0.0)
        remaining_ratio = exp(-recomputed_exponent) if recomputed_exponent < 80.0 else 0.0
        recomputed_stress = fpj * remaining_ratio
        stored_stress = _float(row.get("Stress after friction (MPa)"), 0.0)
        exponent_residual = recomputed_exponent - stored_exponent
        stress_residual = recomputed_stress - stored_stress
        audit_rows.append(
            {
                "Tendon type": tendon_type,
                "Tendon ID": str(row.get("Tendon ID") or ""),
                "Point": str(row.get("Point") or ""),
                "Source end": str(row.get("Source end") or ""),
                "x (m)": x_m,
                "Kx": kx,
                "alpha (rad)": alpha,
                "Angle add total (rad)": angle_add * deviators if str(tendon_type).strip().casefold() == "external" else 0.0,
                "mu": mu,
                "mu-angle term": mu_angle,
                "Exponent": stored_exponent,
                "Recomputed exponent": recomputed_exponent,
                "P/Pj": remaining_ratio,
                "fpj (MPa)": fpj,
                "f after friction (MPa)": stored_stress,
                "Equation": str(row.get("Equation") or ""),
                "Audit status": "PASS" if abs(exponent_residual) <= 1.0e-10 and abs(stress_residual) <= 1.0e-7 else "REVIEW",
                "Exponent residual": exponent_residual,
                "Stress residual (MPa)": stress_residual,
            }
        )
    return audit_rows

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

    For ``Jacking end = Both`` the app definition is simultaneous equal
    jacking from the left and right ends.  The accepted pre-seating force at
    each station is the higher of the two independently traced jacking-end
    stresses, with the point of no movement at their intersection.  This
    preserves a single tendon force field and never doubles the source jacking
    force.
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
            left_angles_at_point = left_lookup.get(key, {})
            right_angles_at_point = right_lookup.get(key, {})
            source_end, x_from_jack_m, angles = _source_end_values(
                jacking_end=jacking_end,
                station_m=station_m,
                length_m=length,
                left_angles=left_angles_at_point,
                right_angles=right_angles_at_point,
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
                review_notes.append(EXTERNAL_HDPE_REVIEW_NOTE)
                if tendon_deviator_count <= 0:
                    blocking_issues.append(EXTERNAL_NO_DEVIATOR_ISSUE)
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

            # PTLOSS2C branch traces are additive audit/source fields only. They
            # do not change the accepted PTLOSS1 nearest-jacking-end force. The
            # full left/right traces are needed only when a both-end anchorage
            # seating interaction extends beyond the independent half-length
            # branches.
            left_alpha_total = _float(left_angles_at_point.get("alpha_total_rad"), 0.0)
            right_alpha_total = _float(right_angles_at_point.get("alpha_total_rad"), 0.0)
            left_deviators = int(
                round(_float(left_angles_at_point.get("deviator_count"), 0.0))
            )
            right_deviators = int(
                round(_float(right_angles_at_point.get("deviator_count"), 0.0))
            )
            if tendon_type == "External":
                left_branch_exponent = mu_external * (
                    left_alpha_total + inadvertent * left_deviators
                )
                right_branch_exponent = mu_external * (
                    right_alpha_total + inadvertent * right_deviators
                )
            else:
                left_branch_exponent = k_internal * station_m + mu_internal * left_alpha_total
                right_branch_exponent = (
                    k_internal * max(length - station_m, 0.0)
                    + mu_internal * right_alpha_total
                )
            left_branch_exponent = max(left_branch_exponent, 0.0)
            right_branch_exponent = max(right_branch_exponent, 0.0)
            normalized_jack = str(jacking_end or "").strip().casefold()
            left_branch_stress = None
            if normalized_jack in {"left", "both"}:
                left_branch_stress = (
                    fpj_mpa * exp(-left_branch_exponent)
                    if left_branch_exponent < 80.0
                    else 0.0
                )
            right_branch_stress = None
            if normalized_jack in {"right", "both"}:
                right_branch_stress = (
                    fpj_mpa * exp(-right_branch_exponent)
                    if right_branch_exponent < 80.0
                    else 0.0
                )

            # For simultaneous equal both-end jacking, the physical pre-seating
            # tendon force is controlled by the jacking branch that delivers
            # the higher stress at the station.  The branch intersection is the
            # point of no movement (internal strand-force equilibrium).  Do not
            # switch branches merely at the geometric midpoint because unequal
            # curvature/wobble routes can move the equilibrium station.
            if normalized_jack == "both" and left_branch_stress is not None and right_branch_stress is not None:
                if left_branch_stress >= right_branch_stress:
                    source_end = "Left (controlling)"
                    x_from_jack_m = station_m
                    alpha_v = _float(left_angles_at_point.get("alpha_v_rad"), 0.0)
                    alpha_h = _float(left_angles_at_point.get("alpha_h_rad"), 0.0)
                    alpha_total = left_alpha_total
                    deviator_count = left_deviators
                    exponent = left_branch_exponent
                    f_after_mpa = left_branch_stress
                else:
                    source_end = "Right (controlling)"
                    x_from_jack_m = max(length - station_m, 0.0)
                    alpha_v = _float(right_angles_at_point.get("alpha_v_rad"), 0.0)
                    alpha_h = _float(right_angles_at_point.get("alpha_h_rad"), 0.0)
                    alpha_total = right_alpha_total
                    deviator_count = right_deviators
                    exponent = right_branch_exponent
                    f_after_mpa = right_branch_stress
                remaining_ratio = 0.0 if fpj_mpa <= 0.0 else f_after_mpa / fpj_mpa
                loss_mpa = max(fpj_mpa - f_after_mpa, 0.0)
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
                    "Left branch exponent": (
                        left_branch_exponent if left_branch_stress is not None else None
                    ),
                    "Right branch exponent": (
                        right_branch_exponent if right_branch_stress is not None else None
                    ),
                    "Stress from left jack (MPa)": left_branch_stress,
                    "Stress from right jack (MPa)": right_branch_stress,
                    "P from left jack (kN)": (
                        None
                        if left_branch_stress is None
                        else aps_total * left_branch_stress / 1000.0
                    ),
                    "P from right jack (kN)": (
                        None
                        if right_branch_stress is None
                        else aps_total * right_branch_stress / 1000.0
                    ),
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
