"""Verified later-permanent-load source for Portal Frame Crossbeam PT losses.

PTLOSS4B3 keeps load definition, validation, and frame-load assembly outside the
Streamlit page and outside the time-dependent material equations.  Active rows
represent one cumulative gravity event applied after falsework removal.

Internal frame units are mm, MPa, N, and N-mm.  User load magnitudes are kN for
point loads and kN/m for uniform line loads.  Downward is entered as positive in
the Loads workspace and converted to negative frame local/global y.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from math import isfinite
from typing import Any


CB_LATER_PERMANENT_LOAD_TABLE_KEY = "crossbeam_ptloss4b3_later_permanent_load_table"
CB_LATER_PERMANENT_LOAD_EDITOR_KEY = "crossbeam_ptloss4b3_later_permanent_load_editor"

POINT_LOAD = "Point load"
UNIFORM_LINE_LOAD = "Uniform line load"
LOAD_TYPE_OPTIONS = (POINT_LOAD, UNIFORM_LINE_LOAD)
LOAD_TABLE_COLUMNS = (
    "Active",
    "Load ID",
    "Load Type",
    "Station s (m)",
    "End station s (m)",
    "Magnitude",
    "Note",
)


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
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "yes", "y", "1", "on"}:
        return True
    if text in {"false", "no", "n", "0", "off", ""}:
        return False
    return default


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


def default_later_permanent_load_rows(length_m: float = 20.0) -> list[dict[str, Any]]:
    """Return safe inactive examples; no fake event load is active by default."""

    length = max(_float(length_m, 20.0), 0.0)
    right_station = max(length - 1.5, 0.0)
    return [
        {
            "Active": False,
            "Load ID": "LP1",
            "Load Type": POINT_LOAD,
            "Station s (m)": min(1.5, length),
            "End station s (m)": "",
            "Magnitude": 0.0,
            "Note": "Enter verified downward point load in kN, then set Active.",
        },
        {
            "Active": False,
            "Load ID": "LP2",
            "Load Type": POINT_LOAD,
            "Station s (m)": right_station,
            "End station s (m)": "",
            "Magnitude": 0.0,
            "Note": "Typical second support/girder reaction placeholder; inactive.",
        },
    ]


def canonical_later_permanent_load_rows(values: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(_records(values), start=1):
        load_type = str(raw.get("Load Type") or POINT_LOAD).strip()
        if load_type not in LOAD_TYPE_OPTIONS:
            load_type = str(raw.get("Load Type") or "").strip()
        rows.append(
            {
                "Active": _bool(raw.get("Active"), False),
                "Load ID": str(raw.get("Load ID") or f"LP{index}").strip(),
                "Load Type": load_type,
                "Station s (m)": raw.get("Station s (m)", ""),
                "End station s (m)": raw.get("End station s (m)", ""),
                "Magnitude": raw.get("Magnitude", ""),
                "Note": str(raw.get("Note") or "").strip(),
            }
        )
    return rows


def _beam_elements(model: Mapping[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        [dict(row) for row in model.get("elements", []) if str(row.get("kind")) == "beam"],
        key=lambda row: (_float(row.get("station_i_m")), _float(row.get("station_j_m"))),
    )


def _add_nodal(
    output: dict[int, list[float]], node_id: int, fx_n: float, fy_n: float, moment_nmm: float
) -> None:
    vector = output.setdefault(int(node_id), [0.0, 0.0, 0.0])
    vector[0] += float(fx_n)
    vector[1] += float(fy_n)
    vector[2] += float(moment_nmm)


def later_permanent_load_source(
    *, model: Mapping[str, Any], load_rows: Any
) -> dict[str, Any]:
    """Validate active rows and assemble exact mesh-compatible frame loads.

    PTLOSS4B3 deliberately requires load application stations to coincide with
    the accepted frame mesh.  This preserves exact internal-force recovery:
    point loads are nodal and uniform line loads are assigned directly to full
    beam elements rather than being smeared into approximate equivalent loads.
    """

    rows = canonical_later_permanent_load_rows(load_rows)
    active_rows = [row for row in rows if bool(row.get("Active"))]
    length_m = _float(model.get("length_m"))
    elements = _beam_elements(model)
    mesh_stations = sorted({_float(value) for value in model.get("stations_m", [])})
    node_by_station = {
        round(_float(station), 9): int(node_id)
        for station, node_id in dict(model.get("beam_node_by_station") or {}).items()
    }
    issues: list[str] = []
    warnings: list[str] = []
    if not bool(model.get("ready")):
        issues.extend(model.get("issues") or ["Crossbeam frame model is not ready."])
    if length_m <= 0.0 or not elements or not mesh_stations:
        issues.append("Crossbeam beam mesh is not available for later permanent loads.")
    if not active_rows:
        return {
            "ready": False,
            "status": "LAYOUT REQUIRED",
            "issues": [],
            "warnings": ["No active later permanent-load rows are available."],
            "active_count": 0,
            "valid_count": 0,
            "canonical_rows": rows,
            "nodal_loads": {},
            "uniform_local_y_by_element": {},
            "audit_rows": [],
            "equivalent_nodal_rows": [],
            "uniform_element_rows": [],
            "total_downward_load_kN": 0.0,
            "vertical_force_residual_kN": 0.0,
            "fingerprint": "",
        }

    tolerance = 1.0e-8

    def mesh_station(value: float) -> float | None:
        if not mesh_stations:
            return None
        nearest = min(mesh_stations, key=lambda candidate: abs(candidate - value))
        return nearest if abs(nearest - value) <= tolerance else None

    def nearest_text(value: float) -> str:
        if not mesh_stations:
            return "—"
        nearest = min(mesh_stations, key=lambda candidate: abs(candidate - value))
        return f"{nearest:.6f} m"

    seen_ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows, start=1):
        if not bool(row.get("Active")):
            continue
        load_id = str(row.get("Load ID") or "").strip()
        load_type = str(row.get("Load Type") or "").strip()
        station = _float(row.get("Station s (m)"), float("nan"))
        end_station = _float(row.get("End station s (m)"), float("nan"))
        magnitude = _float(row.get("Magnitude"), float("nan"))
        row_issues: list[str] = []
        if not load_id:
            row_issues.append("Load ID is required")
        elif load_id in seen_ids:
            row_issues.append(f"duplicate Load ID '{load_id}'")
        seen_ids.add(load_id)
        if load_type not in LOAD_TYPE_OPTIONS:
            row_issues.append("Load Type must be Point load or Uniform line load")
        if not isfinite(station) or station < -tolerance or station > length_m + tolerance:
            row_issues.append(f"Station s must lie within 0 to {length_m:.3f} m")
            station_mesh = None
        else:
            station_mesh = mesh_station(station)
            if station_mesh is None:
                row_issues.append(
                    f"Station s must coincide with an analysis mesh station; nearest is {nearest_text(station)}"
                )
        if not isfinite(magnitude) or magnitude <= 0.0:
            row_issues.append("Magnitude must be greater than zero; downward is entered positive")
        end_mesh = None
        if load_type == UNIFORM_LINE_LOAD:
            if not isfinite(end_station):
                row_issues.append("End station is required for a uniform line load")
            elif end_station <= station + tolerance:
                row_issues.append("End station must be greater than start station")
            elif end_station > length_m + tolerance:
                row_issues.append(f"End station must not exceed {length_m:.3f} m")
            else:
                end_mesh = mesh_station(end_station)
                if end_mesh is None:
                    row_issues.append(
                        f"End station must coincide with an analysis mesh station; nearest is {nearest_text(end_station)}"
                    )
        if row_issues:
            issues.append(
                f"Later permanent-load row {row_index}: "
                + "; ".join(row_issues)
                + "."
            )
            continue
        validated.append(
            {
                **row,
                "Station s (m)": float(station_mesh),
                "End station s (m)": (
                    float(end_mesh) if load_type == UNIFORM_LINE_LOAD else None
                ),
                "Magnitude": magnitude,
            }
        )

    if issues:
        return {
            "ready": False,
            "status": "REVIEW REQUIRED",
            "issues": _dedupe(issues),
            "warnings": warnings,
            "active_count": len(active_rows),
            "valid_count": len(validated),
            "canonical_rows": rows,
            "nodal_loads": {},
            "uniform_local_y_by_element": {},
            "audit_rows": [],
            "equivalent_nodal_rows": [],
            "uniform_element_rows": [],
            "total_downward_load_kN": 0.0,
            "vertical_force_residual_kN": 0.0,
            "fingerprint": "",
        }

    nodal: dict[int, list[float]] = {}
    uniform: dict[str, float] = {}
    audit_rows: list[dict[str, Any]] = []
    equivalent_rows: list[dict[str, Any]] = []
    uniform_rows: list[dict[str, Any]] = []
    total_downward_kn = 0.0
    for row in validated:
        load_id = str(row["Load ID"])
        load_type = str(row["Load Type"])
        start_m = _float(row["Station s (m)"])
        magnitude = _float(row["Magnitude"])
        row_downward_kn = 0.0
        touched_elements: list[str] = []
        if load_type == POINT_LOAD:
            row_downward_kn = magnitude
            node_id = node_by_station.get(round(start_m, 9))
            if node_id is None:
                issues.append(f"{load_id}: mesh node at s = {start_m:.6f} m is missing.")
                continue
            _add_nodal(nodal, node_id, 0.0, -magnitude * 1000.0, 0.0)
        else:
            end_m = _float(row["End station s (m)"])
            row_downward_kn = magnitude * (end_m - start_m)
            q_n_per_mm = -magnitude  # 1 kN/m = 1 N/mm
            for element in elements:
                element_start = _float(element.get("station_i_m"))
                element_end = _float(element.get("station_j_m"))
                if (
                    element_start >= start_m - tolerance
                    and element_end <= end_m + tolerance
                    and element_end > element_start + tolerance
                ):
                    element_id = str(element.get("id") or "")
                    touched_elements.append(element_id)
                    uniform[element_id] = uniform.get(element_id, 0.0) + q_n_per_mm
                    uniform_rows.append(
                        {
                            "Load ID": load_id,
                            "Element": element_id,
                            "s0 (m)": element_start,
                            "s1 (m)": element_end,
                            "q local-y (N/mm; up +)": q_n_per_mm,
                            "Downward element load (kN)": magnitude
                            * (element_end - element_start),
                        }
                    )
            covered_length = sum(
                _float(item["s1 (m)"]) - _float(item["s0 (m)"])
                for item in uniform_rows
                if str(item.get("Load ID")) == load_id
            )
            if abs(covered_length - (end_m - start_m)) > tolerance:
                issues.append(
                    f"{load_id}: uniform-load element coverage {covered_length:.9f} m does not close to input length {end_m - start_m:.9f} m."
                )
                continue
        total_downward_kn += row_downward_kn
        equivalent_vertical_kn = (
            magnitude
            if load_type == POINT_LOAD
            else sum(
                _float(item.get("Downward element load (kN)"))
                for item in uniform_rows
                if str(item.get("Load ID")) == load_id
            )
        )
        audit_rows.append(
            {
                "Load ID": load_id,
                "Load Type": load_type,
                "Start s (m)": start_m,
                "End s (m)": row.get("End station s (m)"),
                "Magnitude": magnitude,
                "Magnitude unit": "kN" if load_type == POINT_LOAD else "kN/m",
                "Total downward load (kN)": row_downward_kn,
                "Equivalent frame downward sum (kN)": equivalent_vertical_kn,
                "Vertical closure residual (kN)": equivalent_vertical_kn
                - row_downward_kn,
                "Elements": ", ".join(dict.fromkeys(touched_elements)),
                "Note": str(row.get("Note") or ""),
            }
        )

    if issues:
        return {
            "ready": False,
            "status": "REVIEW REQUIRED",
            "issues": _dedupe(issues),
            "warnings": warnings,
            "active_count": len(active_rows),
            "valid_count": len(validated),
            "canonical_rows": rows,
            "nodal_loads": {},
            "uniform_local_y_by_element": {},
            "audit_rows": audit_rows,
            "equivalent_nodal_rows": [],
            "uniform_element_rows": uniform_rows,
            "total_downward_load_kN": total_downward_kn,
            "vertical_force_residual_kN": 0.0,
            "fingerprint": "",
        }

    nodal_output = {
        node_id: tuple(float(value) for value in vector)
        for node_id, vector in sorted(nodal.items())
        if any(abs(float(value)) > 1.0e-12 for value in vector)
    }
    node_lookup = {int(row.get("id")): row for row in model.get("nodes", [])}
    for node_id, vector in nodal_output.items():
        node = node_lookup.get(int(node_id), {})
        equivalent_rows.append(
            {
                "Node": str(node.get("label") or node_id),
                "Station s (m)": _float(node.get("station_m")),
                "Fx (kN)": _float(vector[0]) / 1000.0,
                "Fy (kN; up +)": _float(vector[1]) / 1000.0,
                "Moment (kN-m; CCW +)": _float(vector[2]) / 1.0e6,
            }
        )
    point_downward_kn = -sum(vector[1] for vector in nodal_output.values()) / 1000.0
    uniform_downward_kn = sum(
        -_float(q) * (
            _float(next(row for row in elements if str(row.get("id")) == element_id).get("station_j_m"))
            - _float(next(row for row in elements if str(row.get("id")) == element_id).get("station_i_m"))
        )
        for element_id, q in uniform.items()
    )
    equivalent_downward_kn = point_downward_kn + uniform_downward_kn
    residual_kn = equivalent_downward_kn - total_downward_kn
    tolerance_kn = max(1.0e-8, 1.0e-9 * max(total_downward_kn, 1.0))
    if abs(residual_kn) > tolerance_kn:
        issues.append(
            f"Frame-load vertical-force closure residual {residual_kn:.6e} kN exceeds tolerance."
        )

    fingerprint_payload = {
        "length_m": round(length_m, 9),
        "active_rows": [
            {
                key: (
                    round(_float(row.get(key)), 9)
                    if key in {"Station s (m)", "End station s (m)", "Magnitude"}
                    else row.get(key)
                )
                for key in LOAD_TABLE_COLUMNS
            }
            for row in validated
        ],
        "nodal_loads": {
            str(node_id): [round(float(value), 8) for value in values]
            for node_id, values in nodal_output.items()
        },
        "uniform_local_y_by_element": {
            element_id: round(float(value), 10)
            for element_id, value in sorted(uniform.items())
        },
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    ready = not issues and bool(validated) and total_downward_kn > 0.0
    return {
        "ready": ready,
        "status": "VERIFIED LOAD SOURCE READY" if ready else "REVIEW REQUIRED",
        "issues": _dedupe(issues),
        "warnings": warnings,
        "active_count": len(active_rows),
        "valid_count": len(validated),
        "canonical_rows": rows,
        "validated_rows": validated,
        "nodal_loads": nodal_output,
        "uniform_local_y_by_element": uniform,
        "audit_rows": audit_rows,
        "equivalent_nodal_rows": equivalent_rows,
        "uniform_element_rows": uniform_rows,
        "total_downward_load_kN": total_downward_kn,
        "equivalent_frame_downward_kN": equivalent_downward_kn,
        "vertical_force_residual_kN": residual_kn,
        "fingerprint": fingerprint,
        "mesh_station_count": len(mesh_stations),
        "basis": (
            "Active Point loads (kN) are applied at accepted frame nodes and Uniform line loads (kN/m) are applied directly to complete beam elements. Downward-positive user inputs are converted to negative frame local/global y."
        ),
    }
