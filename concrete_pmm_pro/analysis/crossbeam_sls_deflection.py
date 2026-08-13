"""Crossbeam SLS deflection / camber checks from verified external-FEA displacements.

``CROSSBEAM.SLS2`` deliberately does **not** infer absolute Portal-Frame
vertical displacement from the imported beam force diagram.  A Crossbeam is a
frame member connected to columns, so beam M/EI alone is insufficient to
recover total vertical displacement without the column/frame deformation
state.  The adopted route therefore consumes a dedicated external-FEA vertical
movement source and performs read-through serviceability checks only.

Canonical displacement convention used by Concrete Section Pro:

* positive = upward movement / camber;
* negative = downward movement / deflection.

For each adjacent column pair the service check is based on displacement
relative to the straight chord joining the two column-centre displacement
values.  This removes support translation from the span-deflection measure
without fabricating zero support movement.  Overhang response remains visible
but is not certified by the span L/n acceptance check.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

from concrete_pmm_pro.crossbeam.construction_stage import canonical_column_stage_rows, normalize_construction_method
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.project_geometry import CROSSBEAM_COLUMN_ROWS_KEY
from concrete_pmm_pro.crossbeam.station_force_contract import canonical_sls_stage


CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY = "crossbeam_sls_displacement_table"
CROSSBEAM_SLS_DEFLECTION_RESULT_KEY = "crossbeam_sls2_deflection_camber_result"
CROSSBEAM_SLS_DEFLECTION_RESULT_HASH_KEY = "crossbeam_sls2_deflection_camber_input_hash"
CROSSBEAM_LENGTH_KEY = "crossbeam_ui1_length_m"

TRANSFER_STAGE = "Transfer stage"
FINAL_SERVICE_STAGE = "Final service stage"
_STAGE_ORDER = {TRANSFER_STAGE: 0, FINAL_SERVICE_STAGE: 1}

DEFAULT_LIMIT_BASIS = "Review only"
LIMIT_BASIS_OPTIONS = ("Review only", "L/240", "L/360", "L/480", "L/1000", "Custom")


@dataclass(frozen=True)
class CrossbeamDeflectionPreparation:
    ready: bool
    rows: tuple[dict[str, Any], ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    info: tuple[str, ...]
    fingerprint: str
    member_length_m: float
    construction_method: str
    column_rows: tuple[dict[str, Any], ...]
    limit_basis: str
    custom_limit_ratio: float | None


def _get(state: Any, key: str, default: Any = None) -> Any:
    if hasattr(state, "get"):
        return state.get(key, default)
    return getattr(state, key, default)


def _records(value: Any) -> list[dict[str, Any]]:
    if hasattr(value, "to_dict"):
        try:
            return [dict(row) for row in value.to_dict(orient="records") if isinstance(row, Mapping)]
        except Exception:
            return []
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _active(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    if text in {"", "0", "false", "no", "off", "n"}:
        return False
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    return bool(value)


def _hashable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return round(value, 9) if math.isfinite(value) else str(value)
    if isinstance(value, Mapping):
        return {str(key): _hashable(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_hashable(item) for item in value]
    return repr(value)


def _fingerprint(value: Any) -> str:
    payload = json.dumps(_hashable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dedupe(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item).strip() for item in messages if str(item).strip()))


def _canonical_limit_basis(value: Any) -> str:
    text = str(value or "").strip()
    return text if text in LIMIT_BASIS_OPTIONS else DEFAULT_LIMIT_BASIS


def _limit_ratio(basis: str, custom_ratio: float | None) -> float | None:
    if basis == "Review only":
        return None
    if basis == "Custom":
        return custom_ratio if custom_ratio is not None and custom_ratio > 0.0 else None
    try:
        ratio = float(str(basis).split("/")[-1])
    except (TypeError, ValueError):
        return None
    return ratio if ratio > 0.0 else None


def _normalized_rows(state: Any, *, member_length_m: float) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    output: list[dict[str, Any]] = []
    for index, raw in enumerate(_records(_get(state, CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY)), start=1):
        if not _active(raw.get("Active")):
            continue
        station = _finite(raw.get("Station s (m)"))
        displacement = _finite(raw.get("Vertical displacement (mm)"))
        stage = canonical_sls_stage(raw.get("Stage"))
        case = str(raw.get("Case Name") or "").strip()
        if station is None:
            errors.append(f"Displacement row {index}: Station s (m) must be numeric.")
            continue
        if station < -1.0e-9 or station > member_length_m + 1.0e-9:
            errors.append(
                f"Displacement row {index}: station {station:.6f} m is outside Crossbeam length 0–{member_length_m:.6f} m."
            )
            continue
        if displacement is None:
            errors.append(f"Displacement row {index}: Vertical displacement (mm) must be numeric.")
            continue
        if stage not in {TRANSFER_STAGE, FINAL_SERVICE_STAGE}:
            errors.append(f"Displacement row {index}: Stage must be Transfer stage or Final service stage.")
            continue
        if not case:
            errors.append(f"Displacement row {index}: Case Name is required.")
            continue
        output.append(
            {
                "Active": True,
                "Station s (m)": float(station),
                "Case Name": case,
                "Stage": stage,
                "Vertical displacement (mm)": float(displacement),
                "Source point": str(raw.get("Source point") or "").strip(),
                "Note": str(raw.get("Note") or "").strip(),
            }
        )
    output.sort(key=lambda row: (_STAGE_ORDER.get(str(row["Stage"]), 99), str(row["Case Name"]), float(row["Station s (m)"])))
    seen: set[tuple[str, str, float]] = set()
    for row in output:
        key = (str(row["Stage"]), str(row["Case Name"]), round(float(row["Station s (m)"]), 9))
        if key in seen:
            errors.append(
                f"{row['Stage']} / {row['Case Name']}: duplicate active displacement station at s={float(row['Station s (m)']):.6f} m."
            )
        seen.add(key)
    return output, errors


def build_crossbeam_deflection_preparation(state: Any) -> CrossbeamDeflectionPreparation:
    """Validate the dedicated external-FEA displacement source without solving a frame."""

    length = _finite(_get(state, CROSSBEAM_LENGTH_KEY)) or 0.0
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    if length <= 0.0:
        errors.append("Crossbeam member length must be positive before SLS Deflection / Camber can run.")
    rows, row_errors = _normalized_rows(state, member_length_m=max(length, 0.0))
    errors.extend(row_errors)
    columns = canonical_column_stage_rows(_get(state, CROSSBEAM_COLUMN_ROWS_KEY), length_m=max(length, 0.0))
    if len(columns) < 2:
        errors.append("At least two Crossbeam columns are required to define a support-to-support deflection chord.")
    else:
        for left, right in zip(columns, columns[1:]):
            if float(right["Station s (m)"]) <= float(left["Station s (m)"]) + 1.0e-9:
                errors.append("Crossbeam column stations must be strictly increasing for span deflection checks.")
                break

    by_group: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        by_group.setdefault((str(row["Stage"]), str(row["Case Name"])), []).append(row)
    if not rows:
        errors.append("No active Crossbeam SLS displacement rows are available. Import verified external-FEA vertical displacements on Loads → SLS Loads.")
    for (stage, case), group in by_group.items():
        if len(group) < 2:
            errors.append(f"{stage} / {case}: at least two displacement stations are required.")
            continue
        stations = [float(row["Station s (m)"]) for row in group]
        if columns:
            first_col = float(columns[0]["Station s (m)"])
            last_col = float(columns[-1]["Station s (m)"])
            if min(stations) > first_col + 1.0e-9 or max(stations) < last_col - 1.0e-9:
                errors.append(
                    f"{stage} / {case}: displacement rows must bracket the outer column centre-lines "
                    f"({first_col:.3f}–{last_col:.3f} m) so support-chord values can be recovered without extrapolation."
                )
    stages = {str(row["Stage"]) for row in rows}
    if TRANSFER_STAGE not in stages:
        warnings.append("No active Transfer-stage displacement source is present; transfer camber response will remain unavailable.")
    if FINAL_SERVICE_STAGE not in stages:
        warnings.append("No active Final-service displacement source is present; service deflection acceptance will remain unavailable.")

    limit_basis = _canonical_limit_basis(_get(state, "crossbeam_sls_deflection_limit_basis", DEFAULT_LIMIT_BASIS))
    custom_ratio = _finite(_get(state, "crossbeam_sls_deflection_custom_ratio"))
    if limit_basis == "Custom" and (custom_ratio is None or custom_ratio <= 0.0):
        errors.append("Custom deflection limit requires a positive L/n denominator.")
    if limit_basis == "Review only":
        warnings.append(
            "No project-specific downward-deflection acceptance ratio is selected. Final Service will report RESPONSE / REVIEW rather than fabricate a code PASS."
        )

    construction = normalize_construction_method(_get(state, CB_LOSS_ES_CONSTRUCTION_METHOD_KEY))
    info.extend(
        [
            "Source route: verified external-FEA vertical displacement; beam-force M/EI is not used to fabricate Portal-Frame displacement.",
            "Canonical sign: positive = upward camber; negative = downward deflection.",
            "Span deflection is evaluated relative to the straight chord joining adjacent column-centre displacement values.",
        ]
    )
    payload = {
        "schema": "crossbeam-sls2-displacement-source-v1",
        "length": length,
        "construction": construction,
        "columns": columns,
        "rows": rows,
        "limit_basis": limit_basis,
        "custom_ratio": custom_ratio,
    }
    return CrossbeamDeflectionPreparation(
        ready=bool(rows) and not errors,
        rows=tuple(rows),
        errors=tuple(_dedupe(errors)),
        warnings=tuple(_dedupe(warnings)),
        info=tuple(_dedupe(info)),
        fingerprint=_fingerprint(payload),
        member_length_m=float(length),
        construction_method=construction,
        column_rows=tuple(columns),
        limit_basis=limit_basis,
        custom_limit_ratio=custom_ratio,
    )


def _interp_no_extrapolation(rows: list[dict[str, Any]], station_m: float) -> tuple[float | None, str]:
    rows = sorted(rows, key=lambda row: float(row["Station s (m)"]))
    for row in rows:
        if abs(float(row["Station s (m)"]) - station_m) <= 1.0e-9:
            return float(row["Vertical displacement (mm)"]), "EXACT"
    left = [row for row in rows if float(row["Station s (m)"]) < station_m]
    right = [row for row in rows if float(row["Station s (m)"]) > station_m]
    if not left or not right:
        return None, "UNAVAILABLE"
    a = left[-1]
    b = right[0]
    xa = float(a["Station s (m)"])
    xb = float(b["Station s (m)"])
    if xb <= xa + 1.0e-12:
        return None, "UNAVAILABLE"
    ratio = (station_m - xa) / (xb - xa)
    value = float(a["Vertical displacement (mm)"]) + ratio * (
        float(b["Vertical displacement (mm)"]) - float(a["Vertical displacement (mm)"])
    )
    return float(value), f"INTERPOLATED {xa:.3f}–{xb:.3f} m"


def _stage_case_rows(preparation: CrossbeamDeflectionPreparation) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in preparation.rows:
        groups.setdefault((str(row["Stage"]), str(row["Case Name"])), []).append(dict(row))
    for key in groups:
        groups[key].sort(key=lambda row: float(row["Station s (m)"]))
    return groups


def run_crossbeam_deflection_camber(preparation: CrossbeamDeflectionPreparation) -> dict[str, Any]:
    """Evaluate imported displacement response and span-relative service deflection."""

    if not preparation.ready:
        raise ValueError("Crossbeam SLS Deflection / Camber source is not ready.")
    groups = _stage_case_rows(preparation)
    columns = list(preparation.column_rows)
    ratio = _limit_ratio(preparation.limit_basis, preparation.custom_limit_ratio)
    response_rows: list[dict[str, Any]] = []
    span_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    required_actions: list[dict[str, Any]] = []

    for (stage, case), rows in groups.items():
        # Preserve every imported source point for the full-member absolute-response plot.
        for row in rows:
            response_rows.append(
                {
                    "Stage": stage,
                    "Case": case,
                    "Station s (m)": float(row["Station s (m)"]),
                    "Vertical displacement mm": float(row["Vertical displacement (mm)"]),
                    "Source point": row.get("Source point", ""),
                    "Source": "IMPORTED",
                    "Note": row.get("Note", ""),
                }
            )

        support_values: dict[float, float] = {}
        for column in columns:
            x = float(column["Station s (m)"])
            value, source = _interp_no_extrapolation(rows, x)
            if value is None:
                continue
            support_values[x] = float(value)
            support_rows.append(
                {
                    "Stage": stage,
                    "Case": case,
                    "Column": str(column.get("Column ID") or ""),
                    "Station s (m)": x,
                    "Vertical displacement mm": float(value),
                    "Demand source": source,
                }
            )

        for span_index, (left, right) in enumerate(zip(columns, columns[1:]), start=1):
            x1 = float(left["Station s (m)"])
            x2 = float(right["Station s (m)"])
            if x1 not in support_values or x2 not in support_values or x2 <= x1:
                continue
            d1 = support_values[x1]
            d2 = support_values[x2]
            span_length = x2 - x1
            stations = sorted(
                {
                    x1,
                    x2,
                    *[
                        float(row["Station s (m)"])
                        for row in rows
                        if x1 - 1.0e-9 <= float(row["Station s (m)"]) <= x2 + 1.0e-9
                    ],
                }
            )
            local: list[dict[str, Any]] = []
            for x in stations:
                disp, source = _interp_no_extrapolation(rows, x)
                if disp is None:
                    continue
                chord = d1 + (d2 - d1) * ((x - x1) / span_length)
                relative = float(disp) - chord
                local.append(
                    {
                        "Stage": stage,
                        "Case": case,
                        "Span": f"{left.get('Column ID', '')}–{right.get('Column ID', '')}",
                        "Span index": span_index,
                        "Span length m": span_length,
                        "Station s (m)": x,
                        "Absolute displacement mm": float(disp),
                        "Support chord mm": float(chord),
                        "Relative displacement mm": relative,
                        "Demand source": source,
                    }
                )
            if not local:
                continue
            upward = max(local, key=lambda row: float(row["Relative displacement mm"]))
            downward = min(local, key=lambda row: float(row["Relative displacement mm"]))
            max_up = max(float(upward["Relative displacement mm"]), 0.0)
            max_down = max(-float(downward["Relative displacement mm"]), 0.0)
            limit_mm = span_length * 1000.0 / ratio if ratio else None
            utilization = max_down / limit_mm if limit_mm and limit_mm > 0.0 else None
            if stage == FINAL_SERVICE_STAGE:
                if limit_mm is None:
                    status = "REVIEW"
                else:
                    status = "PASS" if max_down <= limit_mm + 1.0e-9 else "FAIL"
            else:
                status = "RESPONSE"
            span_rows.append(
                {
                    "Stage": stage,
                    "Case": case,
                    "Span": local[0]["Span"],
                    "Span index": span_index,
                    "Span length m": span_length,
                    "Status": status,
                    "Max upward camber mm": max_up,
                    "x up m": float(upward["Station s (m)"]),
                    "Max downward deflection mm": max_down,
                    "x down m": float(downward["Station s (m)"]),
                    "Limit basis": preparation.limit_basis,
                    "Limit mm": limit_mm,
                    "Utilization": utilization,
                }
            )
            response_rows.extend(local)

    final_spans = [row for row in span_rows if row["Stage"] == FINAL_SERVICE_STAGE]
    transfer_spans = [row for row in span_rows if row["Stage"] == TRANSFER_STAGE]
    if any(row["Status"] == "FAIL" for row in final_spans):
        status = "FAIL"
    elif final_spans and all(row["Status"] == "PASS" for row in final_spans):
        status = "PASS"
    elif final_spans:
        status = "REVIEW"
    else:
        status = "REVIEW"

    governing = None
    if final_spans:
        if ratio:
            governing = max(
                final_spans,
                key=lambda row: float(row.get("Utilization") or 0.0),
            )
        else:
            governing = max(
                final_spans,
                key=lambda row: float(row.get("Max downward deflection mm") or 0.0),
            )
    transfer_governing = (
        max(transfer_spans, key=lambda row: float(row.get("Max upward camber mm") or 0.0))
        if transfer_spans
        else None
    )

    if status == "FAIL" and governing:
        required_actions.append(
            {
                "Priority": "High",
                "Module": "SLS Deflection / Camber",
                "Issue": (
                    f"Final-service downward deflection exceeds {governing['Limit basis']} in span {governing['Span']}: "
                    f"{float(governing['Max downward deflection mm']):.3f} mm > {float(governing['Limit mm']):.3f} mm."
                ),
                "Required Action": (
                    "Review the external-FEA displacement case, span stiffness/support assumptions, prestress state, section stiffness, and project deflection criterion before report issue."
                ),
            }
        )
    elif status == "REVIEW":
        required_actions.append(
            {
                "Priority": "Medium",
                "Module": "SLS Deflection / Camber",
                "Issue": "External-FEA displacement response is available but no adopted project downward-deflection limit is active.",
                "Required Action": "Select the project-specific L/n or custom deflection criterion before final report issue.",
            }
        )

    warnings = list(preparation.warnings)
    warnings.extend(
        [
            "Connected displacement traces are visual interpolation between imported source stations; no unverified local extremum is inferred between stations.",
            "Span checks use movement relative to the chord joining adjacent column-centre displacements. Column/support translation is retained in the absolute-response audit and removed only from the relative span check.",
            "Overhang displacement is shown in the full-member response but is not assigned an L/n span acceptance limit by this milestone.",
            "Creep, shrinkage, staged stiffness change, cracked-section stiffness, construction tolerance, and differential foundation settlement are not generated by this route unless already present in the imported external-FEA displacement result.",
        ]
    )
    return {
        "schema": "crossbeam-sls2-deflection-result-v1",
        "status": status,
        "construction_method": preparation.construction_method,
        "code_basis": "Project serviceability criterion applied to verified external-FEA Crossbeam vertical displacement",
        "limit_basis": preparation.limit_basis,
        "custom_limit_ratio": preparation.custom_limit_ratio,
        "member_length_m": preparation.member_length_m,
        "source_rows": [dict(row) for row in preparation.rows],
        "response_rows": response_rows,
        "support_rows": support_rows,
        "span_rows": span_rows,
        "governing_row": governing,
        "transfer_governing_row": transfer_governing,
        "required_actions": required_actions,
        "warnings": _dedupe(warnings),
        "scope": (
            "Crossbeam SLS Deflection / Camber uses verified external-FEA vertical displacements only. "
            "Positive is upward camber and negative is downward deflection. Final-service span deflection is measured relative to adjacent column-centre displacement chords; this route does not reconstruct Portal-Frame displacement from beam forces."
        ),
        "fingerprint": preparation.fingerprint,
    }
