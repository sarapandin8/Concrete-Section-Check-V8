"""Imported FEA later-permanent-load response for Crossbeam time-dependent losses.

PTLOSS4B3A reuses the app's established Excel/CSV import workflow inside Time-Dependent.  Active rows
represent one adopted incremental FEA case/combination for the permanent loads
that become active at age ``tp``.  The imported force tuple P/V2/M3 remains
row-coupled; the module never builds an artificial envelope by mixing force
components from different rows or cases.

Input convention (the Time-Dependent construction-stage import uses this locked
SI exchange basis before the module is called):
- station: metres along the physical Crossbeam, s = 0 .. L;
- P/N: kN, compression positive;
- V2: kN, retained for response/source audit;
- M3: kN-m, sagging positive in the Crossbeam s-vertical plane.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from math import isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.lightweight_elastic_shortening import (
    _tendon_cg_depth_source,
)


CB_LATER_FEA_RESPONSE_TABLE_KEY = "crossbeam_ptloss4b3_later_fea_response_table"
CB_LATER_FEA_RESPONSE_EDITOR_KEY = "crossbeam_ptloss4b3a_td_fea_response_editor"
CB_TD_FEA_SOURCE_DECLARATION_KEY = "crossbeam_ptloss4b3a_td_fea_source_declaration"
CB_TD_FEA_RESPONSE_METADATA_KEY = "crossbeam_time_dependent_fea_response"
CB_TD_FEA_RESPONSE_SCHEMA_VERSION = 1

TD_FEA_IMPORT_MODE_INCREMENTAL = "Incremental response — permanent loads activated at tp"


LATER_FEA_RESPONSE_COLUMNS = (
    "Active",
    "Station x (m)",
    "Case Name",
    "Step Type",
    "Step Num",
    "FEA Object",
    "FEA Element",
    "End / Side",
    "Section ID",
    "P",
    "V2",
    "M3",
    "Note",
)


_SIDE_ALIASES = {
    "": "",
    "left": "Left-side limit",
    "left side": "Left-side limit",
    "left-side": "Left-side limit",
    "left-side limit": "Left-side limit",
    "j": "Left-side limit",
    "j-end": "Left-side limit",
    "end j": "Left-side limit",
    "right": "Right-side limit",
    "right side": "Right-side limit",
    "right-side": "Right-side limit",
    "right-side limit": "Right-side limit",
    "i": "Right-side limit",
    "i-end": "Right-side limit",
    "end i": "Right-side limit",
    "interior": "Interior sample",
    "interior sample": "Interior sample",
}


def _float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) else default


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "yes", "y", "1", "on", "active", "use", "include", "ใช้", "ใช่"}:
        return True
    if text in {"false", "no", "n", "0", "off", "inactive", "", "ไม่ใช้", "ไม่"}:
        return False
    return default


def _records(values: Any) -> list[dict[str, Any]]:
    if hasattr(values, "to_dict"):
        try:
            return [dict(row) for row in values.to_dict(orient="records") if isinstance(row, Mapping)]
        except (TypeError, ValueError):
            return []
    if isinstance(values, (list, tuple)):
        return [dict(row) for row in values if isinstance(row, Mapping)]
    return []


def _dedupe(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item).strip() for item in messages if str(item).strip()))


def canonical_later_fea_response_rows(values: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in _records(values):
        side_raw = str(raw.get("End / Side") or "").strip()
        side = _SIDE_ALIASES.get(side_raw.casefold(), side_raw)
        rows.append(
            {
                "Active": _bool(raw.get("Active"), False),
                "Station x (m)": raw.get("Station x (m)", ""),
                "Case Name": str(raw.get("Case Name") or "").strip(),
                "Step Type": str(raw.get("Step Type") or "").strip(),
                "Step Num": raw.get("Step Num", ""),
                "FEA Object": str(raw.get("FEA Object") or "").strip(),
                "FEA Element": str(raw.get("FEA Element") or "").strip(),
                "End / Side": side,
                "Section ID": str(raw.get("Section ID") or "").strip(),
                "P": raw.get("P", ""),
                "V2": raw.get("V2", ""),
                "M3": raw.get("M3", ""),
                "Note": str(raw.get("Note") or "").strip(),
            }
        )
    return rows




def default_td_fea_source_declaration() -> dict[str, Any]:
    """Return the safe default source declaration for the tp FEA response import."""

    return {
        "import_mode": TD_FEA_IMPORT_MODE_INCREMENTAL,
        "fea_program": "",
        "source_case_stage": "",
        "permanent_load_groups": "",
        "unfactored_confirmed": False,
        "incremental_not_total_confirmed": False,
        "excluded_transient_confirmed": False,
        "common_activation_age_confirmed": False,
    }


def canonical_td_fea_source_declaration(value: Any) -> dict[str, Any]:
    raw = dict(value) if isinstance(value, Mapping) else {}
    default = default_td_fea_source_declaration()
    return {
        "import_mode": str(raw.get("import_mode") or default["import_mode"]).strip(),
        "fea_program": str(raw.get("fea_program") or "").strip(),
        "source_case_stage": str(raw.get("source_case_stage") or "").strip(),
        "permanent_load_groups": str(raw.get("permanent_load_groups") or "").strip(),
        "unfactored_confirmed": _bool(raw.get("unfactored_confirmed"), False),
        "incremental_not_total_confirmed": _bool(raw.get("incremental_not_total_confirmed"), False),
        "excluded_transient_confirmed": _bool(raw.get("excluded_transient_confirmed"), False),
        "common_activation_age_confirmed": _bool(raw.get("common_activation_age_confirmed"), False),
    }


def td_fea_source_declaration_status(value: Any) -> dict[str, Any]:
    declaration = canonical_td_fea_source_declaration(value)
    issues: list[str] = []
    if declaration["import_mode"] != TD_FEA_IMPORT_MODE_INCREMENTAL:
        issues.append("Only incremental FEA response for permanent loads activated at tp is supported in PTLOSS4B3A.")
    if not declaration["fea_program"]:
        issues.append("FEA Program is required for source traceability.")
    if not declaration["source_case_stage"]:
        issues.append("FEA Load Case / Construction Stage name is required.")
    if not declaration["permanent_load_groups"]:
        issues.append("Permanent load groups included at tp must be identified.")
    confirmations = [
        ("unfactored_confirmed", "Confirm that the imported response is unfactored permanent load only."),
        ("incremental_not_total_confirmed", "Confirm that the response is incremental, not a total Final Stage response."),
        ("excluded_transient_confirmed", "Confirm that Live, Wind, Seismic, Temperature, Prestress, and time-dependent effects are excluded."),
        ("common_activation_age_confirmed", "Confirm that all included permanent load groups are reasonably represented by the same activation age tp."),
    ]
    for key, message in confirmations:
        if not declaration[key]:
            issues.append(message)
    return {
        "ready": not issues,
        "status": "SOURCE DECLARATION VERIFIED" if not issues else "SOURCE DECLARATION REQUIRED",
        "issues": issues,
        "declaration": declaration,
    }


def default_later_fea_response_template(length_m: float = 20.0) -> list[dict[str, Any]]:
    length = max(float(_float(length_m, 20.0) or 20.0), 0.0)
    stations = [0.0, min(1.5, length), 0.5 * length, max(length - 1.5, 0.0), length]
    return [
        {
            "Active": False,
            "Station x (m)": station,
            "Case Name": "LATER-PERM",
            "Step Type": "",
            "Step Num": "",
            "FEA Object": "",
            "FEA Element": "",
            "End / Side": "",
            "Section ID": "",
            "P": 0.0,
            "V2": 0.0,
            "M3": 0.0,
            "Note": "Replace with verified incremental FEA resultants; then set Active.",
        }
        for station in stations
    ]


def _beam_elements(model: Mapping[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        [dict(row) for row in model.get("elements", []) if str(row.get("kind") or "") == "beam"],
        key=lambda row: (float(_float(row.get("station_i_m"), 0.0) or 0.0), float(_float(row.get("station_j_m"), 0.0) or 0.0)),
    )


def _element_side(element: Mapping[str, Any], station_m: float, tolerance: float = 1.0e-7) -> str:
    si = float(_float(element.get("station_i_m"), 0.0) or 0.0)
    sj = float(_float(element.get("station_j_m"), 0.0) or 0.0)
    if abs(station_m - si) <= tolerance:
        return "Right-side limit"
    if abs(station_m - sj) <= tolerance:
        return "Left-side limit"
    return "Interior sample"


def _resolve_element(
    *, model: Mapping[str, Any], station_m: float, section_id: str, side: str
) -> tuple[dict[str, Any] | None, list[str]]:
    tolerance = 1.0e-7
    candidates = [
        row
        for row in _beam_elements(model)
        if float(_float(row.get("station_i_m"), 0.0) or 0.0) - tolerance
        <= station_m
        <= float(_float(row.get("station_j_m"), 0.0) or 0.0) + tolerance
    ]
    if section_id:
        candidates = [row for row in candidates if str(row.get("section_id") or row.get("Section ID") or "") == section_id]
    if side:
        candidates = [row for row in candidates if _element_side(row, station_m) == side]
    if len(candidates) == 1:
        return candidates[0], []
    if not candidates:
        return None, [
            f"No Crossbeam analysis element matches s = {station_m:.6f} m"
            + (f", Section ID {section_id}" if section_id else "")
            + (f", {side}" if side else "")
            + "."
        ]
    unique_sections = sorted({str(row.get("section_id") or row.get("Section ID") or "") for row in candidates})
    return None, [
        f"s = {station_m:.6f} m is ambiguous across {len(candidates)} element sides"
        + (f" ({', '.join(item for item in unique_sections if item)})" if any(unique_sections) else "")
        + "; provide End / Side or Section ID."
    ]


def _route_candidates(model: Mapping[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    columns = sorted(float(_float(row.get("Station s (m)"), 0.0) or 0.0) for row in model.get("column_sources", []))
    length_m = float(_float(model.get("length_m"), 0.0) or 0.0)
    if len(columns) >= 2:
        left, right = columns[0], columns[-1]
        mid = 0.5 * (left + right)
        between = [row for row in rows if left - 1.0e-9 <= float(row["Station x (m)"]) <= right + 1.0e-9]
        max_m = max(between, key=lambda row: abs(float(row["M3 (kN-m; sagging +)"])), default=None)
        targets: list[tuple[str, float]] = [
            ("Left column centerline", left),
            ("Span center", mid),
            ("Right column centerline", right),
        ]
        if max_m is not None:
            targets.append(("Maximum |M3| within column lines", float(max_m["Station x (m)"])))
    else:
        targets = [("Member center", 0.5 * length_m)]

    output: list[dict[str, Any]] = []
    for role, target in targets:
        distance = min(abs(float(row["Station x (m)"]) - target) for row in rows)
        nearest = [row for row in rows if abs(abs(float(row["Station x (m)"]) - target) - distance) <= 1.0e-7]
        output.extend({**row, "Evaluation role": role, "Target station (m)": target} for row in nearest)
    unique: dict[tuple[str, float, str, str], dict[str, Any]] = {}
    for row in output:
        key = (
            str(row.get("Evaluation role") or ""),
            round(float(row.get("Station x (m)") or 0.0), 9),
            str(row.get("Internal Element") or ""),
            str(row.get("End / Side") or ""),
        )
        unique[key] = row
    return list(unique.values())


def resolve_imported_later_fea_response(
    *,
    model: Mapping[str, Any],
    load_rows: Any,
    profile_rows: Any,
    system_rows: Any,
    source_declaration: Any = None,
) -> dict[str, Any]:
    """Validate imported incremental FEA resultants and calculate Δfcd.

    The returned scalar is the governing *representative-route* concrete-stress
    increment.  It is suitable for the current PTLOSS4 schedule QA, but it does
    not replace the future station/tendon-dependent effective-prestress chain.
    """

    rows = canonical_later_fea_response_rows(load_rows)
    active = [row for row in rows if bool(row.get("Active"))]
    if not active:
        return {
            "ready": False,
            "status": "TD EVENT RESPONSE IMPORT REQUIRED",
            "issues": [],
            "warnings": ["No active imported Later Permanent Load FEA response rows are available."],
            "canonical_rows": rows,
            "active_count": 0,
            "audit_rows": [],
            "route_rows": [],
            "governing_row": None,
            "delta_fcgp_mpa": None,
            "fingerprint": "",
        }

    issues: list[str] = []
    warnings: list[str] = []
    declaration_status = td_fea_source_declaration_status(source_declaration) if source_declaration is not None else None
    if declaration_status is not None and not declaration_status["ready"]:
        issues.extend(declaration_status["issues"])
    length_m = float(_float(model.get("length_m"), 0.0) or 0.0)
    if not bool(model.get("ready")) or length_m <= 0.0:
        issues.extend(model.get("issues") or ["Crossbeam analysis model is not ready."])
    cases = sorted({str(row.get("Case Name") or "").strip() for row in active if str(row.get("Case Name") or "").strip()})
    if len(cases) != 1:
        issues.append(
            "Active imported rows must belong to exactly one adopted FEA case/combination; "
            f"found {len(cases)} ({', '.join(cases) if cases else 'none'})."
        )
    if declaration_status is not None and declaration_status.get("ready") and len(cases) == 1:
        declared_case = str(declaration_status["declaration"].get("source_case_stage") or "").strip()
        if declared_case.casefold() != cases[0].casefold():
            issues.append(
                f"Declared FEA Load Case / Construction Stage '{declared_case}' does not match active imported Case Name '{cases[0]}'."
            )

    cg_source = _tendon_cg_depth_source(profile_rows=profile_rows, system_rows=system_rows, length_m=length_m)
    if not bool(cg_source.get("ready")):
        issues.extend(cg_source.get("issues") or ["Tendon CG depth source is not ready."])
    depth_at = cg_source.get("depth_at")
    section_sources = dict(model.get("section_sources") or {})
    audit_rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[Any, ...]] = set()
    for index, row in enumerate(active, start=1):
        station = _float(row.get("Station x (m)"), None)
        p_kn = _float(row.get("P"), None)
        v2_kn = _float(row.get("V2"), None)
        m3_knm = _float(row.get("M3"), None)
        row_issues: list[str] = []
        if not str(row.get("Case Name") or "").strip():
            row_issues.append("Case Name is required")
        if station is None or station < -1.0e-9 or station > length_m + 1.0e-9:
            row_issues.append(f"Station x must lie within 0 to {length_m:.3f} m")
        if p_kn is None:
            row_issues.append("P must be numeric")
        if v2_kn is None:
            row_issues.append("V2 must be numeric")
        if m3_knm is None:
            row_issues.append("M3 must be numeric")
        side_raw = str(row.get("End / Side") or "").strip()
        side = _SIDE_ALIASES.get(side_raw.casefold(), side_raw)
        if side and side not in {"Left-side limit", "Right-side limit", "Interior sample"}:
            row_issues.append("End / Side must be Left-side limit, Right-side limit, or Interior sample")
        element = None
        if station is not None:
            element, element_issues = _resolve_element(
                model=model,
                station_m=float(station),
                section_id=str(row.get("Section ID") or "").strip(),
                side=side,
            )
            row_issues.extend(element_issues)
        if row_issues:
            issues.append(f"Later FEA row {index}: " + "; ".join(row_issues) + ".")
            continue
        assert station is not None and p_kn is not None and v2_kn is not None and m3_knm is not None and element is not None
        section_id = str(element.get("section_id") or element.get("Section ID") or "")
        section = section_sources.get(section_id)
        dtop = depth_at(float(station)) if callable(depth_at) else None
        if not isinstance(section, Mapping) or dtop is None:
            issues.append(f"Later FEA row {index}: Section/tendon source is unavailable at s = {float(station):.6f} m.")
            continue
        area = float(_float(section.get("A_mm2"), 0.0) or 0.0)
        inertia = float(_float(section.get("I_mm4"), 0.0) or 0.0)
        centroid = float(_float(section.get("centroid_from_top_mm"), 0.0) or 0.0)
        if area <= 0.0 or inertia <= 0.0:
            issues.append(f"Later FEA row {index}: Section {section_id} has invalid gross properties.")
            continue
        y_below = float(dtop) - centroid
        axial = float(p_kn) * 1000.0 / area
        bending = -float(m3_knm) * 1.0e6 * y_below / inertia
        delta = axial + bending
        key = (
            str(row.get("Case Name") or "").casefold(),
            round(float(station), 9),
            str(row.get("FEA Element") or "").casefold(),
            side.casefold(),
            section_id.casefold(),
        )
        if key in seen_keys:
            issues.append(f"Later FEA row {index}: duplicate case/station/element/side key.")
            continue
        seen_keys.add(key)
        audit_rows.append(
            {
                **row,
                "Station x (m)": float(station),
                "End / Side": side or _element_side(element, float(station)),
                "Section ID": section_id,
                "Internal Element": str(element.get("id") or ""),
                "P (kN; compression +)": float(p_kn),
                "V2 (kN)": float(v2_kn),
                "M3 (kN-m; sagging +)": float(m3_knm),
                "Tendon CG dtop (mm)": float(dtop),
                "y_p below centroid (mm)": y_below,
                "P/A (MPa; compression +)": axial,
                "-M3*y/I (MPa; compression +)": bending,
                "Δf_cd (MPa; compression +)": delta,
            }
        )

    if issues:
        return {
            "ready": False,
            "status": "REVIEW REQUIRED",
            "issues": _dedupe(issues),
            "warnings": warnings,
            "canonical_rows": rows,
            "active_count": len(active),
            "audit_rows": audit_rows,
            "route_rows": [],
            "governing_row": None,
            "delta_fcgp_mpa": None,
            "fingerprint": "",
        }

    route_rows = _route_candidates(model, audit_rows)
    if not route_rows:
        issues.append("Representative Later Permanent Load response route could not be assembled.")
    governing = max(route_rows, key=lambda row: float(row.get("Δf_cd (MPa; compression +)") or 0.0), default=None)
    delta_fcgp = float(governing.get("Δf_cd (MPa; compression +)")) if governing else None
    if governing is not None:
        nearest_offset = abs(float(governing.get("Station x (m)") or 0.0) - float(governing.get("Target station (m)") or 0.0))
        if nearest_offset > 0.25:
            warnings.append(
                f"Nearest imported row for {governing.get('Evaluation role')} is {nearest_offset:.3f} m from the target station; import a denser FEA station set for stronger traceability."
            )
    payload = {
        "case": cases[0] if cases else "",
        "source_declaration": (declaration_status or {}).get("declaration", {}),
        "rows": [
            {
                key: (round(float(value), 10) if isinstance(value, (int, float)) else value)
                for key, value in row.items()
                if key not in {"Note"}
            }
            for row in sorted(audit_rows, key=lambda item: (float(item["Station x (m)"]), str(item.get("FEA Element") or ""), str(item.get("End / Side") or "")))
        ],
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    ready = not issues and governing is not None and delta_fcgp is not None
    return {
        "ready": ready,
        "status": "VERIFIED IMPORTED FEA SOURCE" if ready else "REVIEW REQUIRED",
        "issues": _dedupe(issues),
        "warnings": _dedupe(warnings),
        "canonical_rows": rows,
        "active_count": len(active),
        "case_name": cases[0] if cases else "",
        "audit_rows": audit_rows,
        "route_rows": route_rows,
        "governing_row": governing,
        "delta_fcgp_mpa": delta_fcgp,
        "fingerprint": fingerprint,
        "source_declaration": (declaration_status or {}).get("declaration", {}),
        "source_declaration_status": (declaration_status or {}).get("status", "LEGACY SOURCE DECLARATION NOT PROVIDED"),
        "basis": (
            "Imported P/V2/M3 are unfactored incremental resultants from one adopted permanent-load event at tp. "
            "P and M3 remain paired by row; Δfcd = P/A − M3·yp/I at the tendon CG. "
            "Total Final Stage response is not accepted as an incremental source."
        ),
        "scope_guard": (
            "The current Time-Dependent schedule uses one governing representative-route Δfcd scalar. "
            "Station/tendon-dependent Pe(s) and Pe,eff(s) assembly remains locked for a later milestone."
        ),
    }
