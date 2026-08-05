"""Station-dependent Effective Prestress source for Crossbeam ULS checks.

The Crossbeam loss workflow produces tendon-specific effective stress at
projected member stations.  ULS Flexure, Shear, Torsion, and Combined V+T must
consume that local source rather than a single system-average ``fpe`` scalar.

This module owns only source canonicalization, coverage validation, and linear
interpolation.  It does not calculate prestress losses or structural capacity.
Internal units are m, MPa, and kN for this source contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence


CROSSBEAM_ULS_EFFECTIVE_PRESTRESS_PROFILE_SCHEMA = (
    "crossbeam-uls-effective-prestress-profile-v1"
)
PROFILE_BASIS_PROJECTED_STATION = (
    "TENDON_SPECIFIC_PROJECTED_STATION_LINEAR_INTERPOLATION"
)
PROFILE_MODE_STATION_DEPENDENT = "STATION_DEPENDENT"
PROFILE_MODE_UNIFORM_OVERRIDE = "UNIFORM_AVERAGE_OVERRIDE"


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and math.isnan(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _float(value: Any, default: float | None = None) -> float | None:
    if value is None or _text(value) == "":
        return default
    try:
        result = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _records(value: Any) -> list[dict[str, Any]]:
    if hasattr(value, "to_dict"):
        try:
            return [dict(row) for row in value.to_dict(orient="records")]
        except Exception:
            return []
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _first(row: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in row and row.get(key) is not None and _text(row.get(key)) != "":
            return row.get(key)
    return None


def canonical_effective_prestress_profile_rows(value: Any) -> list[dict[str, Any]]:
    """Return duplicate-safe tendon/station effective-prestress rows.

    Upstream loss tables can contain two face rows at one projected station.
    The physical tendon source is represented once per tendon/station in the
    ULS contract, so duplicate rows are collapsed deterministically.  The
    source spread remains visible for QA instead of being discarded silently.
    """

    grouped: dict[tuple[str, float], list[dict[str, Any]]] = {}
    for raw in _records(value):
        tendon_id = _text(_first(raw, ("Tendon", "Tendon ID", "TendonID")))
        station = _float(_first(raw, ("Station s (m)", "s (m)", "Station")))
        fpe = _float(
            _first(
                raw,
                (
                    "fpe (MPa)",
                    "fpe preview (MPa)",
                    "Effective stress (MPa)",
                    "Remaining stress (MPa)",
                ),
            )
        )
        if not tendon_id or station is None or fpe is None:
            continue
        if station < -1.0e-9 or fpe <= 0.0:
            continue
        key = (tendon_id, round(float(station), 9))
        grouped.setdefault(key, []).append(dict(raw))

    result: list[dict[str, Any]] = []
    for (tendon_id, station), source_rows in sorted(grouped.items()):
        fpe_values = [
            float(value)
            for row in source_rows
            if (
                value := _float(
                    _first(
                        row,
                        (
                            "fpe (MPa)",
                            "fpe preview (MPa)",
                            "Effective stress (MPa)",
                            "Remaining stress (MPa)",
                        ),
                    )
                )
            )
            is not None
        ]
        if not fpe_values:
            continue
        aps_values = [
            float(value)
            for row in source_rows
            if (value := _float(_first(row, ("Aps (mm²)", "Aps mm²", "Aps_mm2"))))
            is not None
            and value > 0.0
        ]
        fpj_values = [
            float(value)
            for row in source_rows
            if (value := _float(_first(row, ("fpj (MPa)", "fpj MPa")))) is not None
            and value > 0.0
        ]
        pe_values = [
            float(value)
            for row in source_rows
            if (
                value := _float(
                    _first(row, ("Pe (kN)", "Pe preview (kN)", "Effective force (kN)"))
                )
            )
            is not None
        ]
        point_labels = sorted(
            {
                _text(_first(row, ("Point", "Point / face source", "Profile point")))
                for row in source_rows
                if _text(_first(row, ("Point", "Point / face source", "Profile point")))
            }
        )
        existing_spreads = [
            float(value)
            for row in source_rows
            if (value := _float(row.get("Duplicate fpe spread (MPa)"))) is not None
            and value >= 0.0
        ]
        fpe_mean = sum(fpe_values) / len(fpe_values)
        aps_mean = sum(aps_values) / len(aps_values) if aps_values else 0.0
        pe_mean = (
            sum(pe_values) / len(pe_values)
            if pe_values
            else aps_mean * fpe_mean / 1000.0
            if aps_mean > 0.0
            else 0.0
        )
        result.append(
            {
                "Tendon": tendon_id,
                "Station s (m)": float(station),
                "Point": " / ".join(point_labels),
                "Aps (mm²)": aps_mean,
                "fpj (MPa)": sum(fpj_values) / len(fpj_values) if fpj_values else 0.0,
                "fpe (MPa)": fpe_mean,
                "Pe (kN)": pe_mean,
                "Source rows collapsed": len(source_rows),
                "Duplicate fpe spread (MPa)": max(
                    max(fpe_values) - min(fpe_values),
                    max(existing_spreads, default=0.0),
                ),
            }
        )
    return result


def effective_prestress_profile_fingerprint(rows: Any) -> str:
    canonical = canonical_effective_prestress_profile_rows(rows)
    payload = json.dumps(
        canonical,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _profiles_by_tendon(rows: Any) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for row in canonical_effective_prestress_profile_rows(rows):
        result.setdefault(str(row["Tendon"]), []).append(row)
    for tendon_rows in result.values():
        tendon_rows.sort(key=lambda row: float(row["Station s (m)"]))
    return result


@dataclass(frozen=True)
class EffectivePrestressProfileValidation:
    ready: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    tendon_count: int
    point_count: int
    fingerprint: str


@dataclass(frozen=True)
class EffectivePrestressResolution:
    ready: bool
    tendon_id: str
    station_m: float
    fpe_mpa: float | None
    mode: str
    source_station_1_m: float | None
    source_station_2_m: float | None
    interpolation_ratio: float | None
    exact: bool
    message: str


def validate_effective_prestress_profiles(
    rows: Any,
    *,
    tendon_ids: Iterable[str],
    member_length_m: float,
) -> EffectivePrestressProfileValidation:
    canonical = canonical_effective_prestress_profile_rows(rows)
    by_tendon = _profiles_by_tendon(canonical)
    errors: list[str] = []
    warnings: list[str] = []
    length = float(member_length_m)
    tolerance = max(1.0e-8, 1.0e-7 * max(abs(length), 1.0))
    requested = list(dict.fromkeys(_text(item) for item in tendon_ids if _text(item)))

    if length <= 0.0:
        errors.append("Crossbeam member length must be positive for Effective Prestress profile validation.")
    if not canonical:
        errors.append("No tendon/station Effective Prestress profile rows are available.")

    for tendon_id in requested:
        points = by_tendon.get(tendon_id, [])
        if not points:
            errors.append(f"{tendon_id}: Effective Prestress profile is missing.")
            continue
        stations = [float(row["Station s (m)"]) for row in points]
        if abs(stations[0]) > tolerance or abs(stations[-1] - length) > tolerance:
            errors.append(
                f"{tendon_id}: Effective Prestress profile must cover s=0 and s={length:.3f} m; "
                f"available range is {stations[0]:.3f} to {stations[-1]:.3f} m."
            )
        if any(station < -tolerance or station > length + tolerance for station in stations):
            errors.append(f"{tendon_id}: Effective Prestress profile contains a station outside the member length.")
        if any(float(row["fpe (MPa)"]) <= 0.0 for row in points):
            errors.append(f"{tendon_id}: Effective Prestress profile contains non-positive fpe.")
        spread = max(float(row.get("Duplicate fpe spread (MPa)") or 0.0) for row in points)
        if spread > 1.0e-6:
            warnings.append(
                f"{tendon_id}: duplicate face rows at one or more stations differed by up to {spread:.3f} MPa; "
                "the ULS source uses the duplicate-safe station average and keeps the spread in audit data."
            )

    return EffectivePrestressProfileValidation(
        ready=bool(not errors and requested),
        errors=tuple(dict.fromkeys(errors)),
        warnings=tuple(dict.fromkeys(warnings)),
        tendon_count=len(by_tendon),
        point_count=len(canonical),
        fingerprint=effective_prestress_profile_fingerprint(canonical),
    )


def resolve_tendon_effective_prestress(
    rows: Any,
    *,
    tendon_id: str,
    station_m: float,
    member_length_m: float,
    average_effective_stress_mpa: float = 0.0,
    allow_uniform_average_override: bool = False,
) -> EffectivePrestressResolution:
    """Resolve local tendon fpe using exact-match or bracketed interpolation.

    Extrapolation is never permitted.  A uniform-average fallback is available
    only when the caller passes an explicit engineering override flag.
    """

    tendon = _text(tendon_id)
    station = float(station_m)
    length = float(member_length_m)
    tolerance = max(1.0e-8, 1.0e-7 * max(abs(length), 1.0))
    points = _profiles_by_tendon(rows).get(tendon, [])

    if points:
        for point in points:
            source_station = float(point["Station s (m)"])
            if abs(source_station - station) <= tolerance:
                return EffectivePrestressResolution(
                    ready=True,
                    tendon_id=tendon,
                    station_m=station,
                    fpe_mpa=float(point["fpe (MPa)"]),
                    mode=PROFILE_MODE_STATION_DEPENDENT,
                    source_station_1_m=source_station,
                    source_station_2_m=source_station,
                    interpolation_ratio=0.0,
                    exact=True,
                    message=f"{tendon}: exact Effective Prestress source at s={source_station:.6f} m.",
                )
        for left, right in zip(points, points[1:]):
            s0 = float(left["Station s (m)"])
            s1 = float(right["Station s (m)"])
            if s0 - tolerance <= station <= s1 + tolerance and s1 - s0 > tolerance:
                ratio = min(max((station - s0) / (s1 - s0), 0.0), 1.0)
                f0 = float(left["fpe (MPa)"])
                f1 = float(right["fpe (MPa)"])
                return EffectivePrestressResolution(
                    ready=True,
                    tendon_id=tendon,
                    station_m=station,
                    fpe_mpa=f0 + ratio * (f1 - f0),
                    mode=PROFILE_MODE_STATION_DEPENDENT,
                    source_station_1_m=s0,
                    source_station_2_m=s1,
                    interpolation_ratio=ratio,
                    exact=False,
                    message=(
                        f"{tendon}: linearly interpolated Effective Prestress between "
                        f"s={s0:.6f} and {s1:.6f} m (r={ratio:.6f})."
                    ),
                )

    average = float(average_effective_stress_mpa or 0.0)
    if allow_uniform_average_override and average > 0.0:
        return EffectivePrestressResolution(
            ready=True,
            tendon_id=tendon,
            station_m=station,
            fpe_mpa=average,
            mode=PROFILE_MODE_UNIFORM_OVERRIDE,
            source_station_1_m=None,
            source_station_2_m=None,
            interpolation_ratio=None,
            exact=False,
            message=(
                f"{tendon}: explicit uniform-average ULS override uses fpe={average:.3f} MPa; "
                "station-dependent source is unavailable."
            ),
        )

    available = "none"
    if points:
        available = (
            f"{float(points[0]['Station s (m)']):.3f} to "
            f"{float(points[-1]['Station s (m)']):.3f} m"
        )
    return EffectivePrestressResolution(
        ready=False,
        tendon_id=tendon,
        station_m=station,
        fpe_mpa=None,
        mode="SOURCE_BLOCKED",
        source_station_1_m=None,
        source_station_2_m=None,
        interpolation_ratio=None,
        exact=False,
        message=(
            f"{tendon}: no Effective Prestress profile value can be resolved at s={station:.6f} m; "
            f"available range is {available}. Refresh Effective Prestress or adopt an explicit uniform-average override."
        ),
    )
