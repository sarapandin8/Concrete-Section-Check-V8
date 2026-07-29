"""Lightweight event-based concrete-stress sources for Crossbeam PT losses.

PTLOSS4B2B1 solves only structural events that change the support/load state. It
reuses the accepted stressing-stage frame model and stored post-ES source; it
does not run a structural solver at every material-aging time step. The B2B
hardening adds explicit response-source verification so a completed solve is not
mistaken for a verified event effect.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from math import isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.lightweight_elastic_shortening import (
    _bonded_fcgp_route,
    _stress_rows_at_tendon_cg,
)
from concrete_pmm_pro.crossbeam.later_permanent_response import resolve_imported_later_fea_response
from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    _beam_response_rows,
    prestress_equivalent_nodal_loads,
    solve_linear_frame,
)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _dedupe(messages: list[str]) -> list[str]:
    return list(
        dict.fromkeys(str(message).strip() for message in messages if str(message).strip())
    )


def _response_key(row: Mapping[str, Any]) -> tuple[str, float]:
    return str(row.get("Element") or ""), round(_float(row.get("s (m)")), 9)


def _response_fingerprint(rows: list[dict[str, Any]]) -> str:
    fields = (
        "Element",
        "Region",
        "Section ID",
        "s (m)",
        "N compression-positive (kN)",
        "V (kN)",
        "M sagging-positive (kN-m)",
        "u_s (mm)",
        "v_up (mm)",
    )
    payload = [
        {
            field: (
                round(_float(row.get(field)), 10)
                if field not in {"Element", "Region", "Section ID"}
                else str(row.get(field) or "")
            )
            for field in fields
        }
        for row in sorted(rows, key=_response_key)
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _element_limit_side(model: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    element_id = str(row.get("Element") or "")
    station = _float(row.get("s (m)"))
    element = next(
        (
            item
            for item in model.get("elements", [])
            if str(item.get("id") or "") == element_id
        ),
        None,
    )
    if not isinstance(element, Mapping):
        return "—"
    station_i = _float(element.get("station_i_m"))
    station_j = _float(element.get("station_j_m"))
    tolerance = 1.0e-8
    if abs(station - station_i) <= tolerance:
        return "Right-side limit"
    if abs(station - station_j) <= tolerance:
        return "Left-side limit"
    return "Interior sample"


def _governing_stress_audit_row(
    *,
    event: str,
    source: str,
    model: Mapping[str, Any],
    route: Mapping[str, Any],
    later_delta_fcgp_mpa: float = 0.0,
) -> dict[str, Any]:
    row = dict(route.get("governing_row") or {})
    base_fcgp = _float(row.get("f_cgp (MPa; compression +)"))
    return {
        "Event": event,
        "Stress source": source,
        "Evaluation role": str(row.get("Evaluation role") or "—"),
        "Station s (m)": _float(row.get("s (m)")),
        "Limit side": _element_limit_side(model, row),
        "Element": str(row.get("Element") or "—"),
        "Section ID": str(row.get("Section ID") or "—"),
        "N (kN; compression +)": _float(row.get("N (kN; compression +)")),
        "M (kN-m; sagging +)": _float(row.get("M (kN-m; sagging +)")),
        "N/A (MPa; compression +)": _float(row.get("N/A (MPa; compression +)")),
        "-M*y/I (MPa; compression +)": _float(
            row.get("-M*y/I (MPa; compression +)")
        ),
        "Later-load Δf_cd (MPa)": _float(later_delta_fcgp_mpa),
        "f_cgp (MPa; compression +)": max(base_fcgp + _float(later_delta_fcgp_mpa), 0.0),
    }


def _max_abs_value(rows: list[dict[str, Any]], field: str) -> float:
    return max((abs(_float(row.get(field))) for row in rows), default=0.0)


def _max_paired_delta(
    before_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    field: str,
) -> dict[str, Any]:
    before = {_response_key(row): row for row in before_rows}
    after = {_response_key(row): row for row in after_rows}
    candidates: list[dict[str, Any]] = []
    for key in before.keys() & after.keys():
        before_value = _float(before[key].get(field))
        after_value = _float(after[key].get(field))
        candidates.append(
            {
                "Element": key[0],
                "Station s (m)": key[1],
                "Before": before_value,
                "After": after_value,
                "Change": after_value - before_value,
                "Absolute change": abs(after_value - before_value),
            }
        )
    return max(candidates, key=lambda item: item["Absolute change"], default={})


def _max_stress_delta(
    before_rows: list[dict[str, Any]], after_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    field = "f_cgp (MPa; compression +)"
    before = {_response_key(row): row for row in before_rows}
    after = {_response_key(row): row for row in after_rows}
    candidates: list[dict[str, Any]] = []
    for key in before.keys() & after.keys():
        before_value = _float(before[key].get(field))
        after_value = _float(after[key].get(field))
        candidates.append(
            {
                "Element": key[0],
                "Station s (m)": key[1],
                "Before": before_value,
                "After": after_value,
                "Change": after_value - before_value,
                "Absolute change": abs(after_value - before_value),
            }
        )
    return max(candidates, key=lambda item: item["Absolute change"], default={})


def _event_response_verification(
    *,
    contact_result: Mapping[str, Any],
    before_response_rows: list[dict[str, Any]],
    after_response_rows: list[dict[str, Any]],
    before_stress_rows: list[dict[str, Any]],
    after_stress_rows: list[dict[str, Any]],
    initial_fcgp_mpa: float,
    released_fcgp_mpa: float,
) -> dict[str, Any]:
    moment_delta = _max_paired_delta(
        before_response_rows, after_response_rows, "M sagging-positive (kN-m)"
    )
    axial_delta = _max_paired_delta(
        before_response_rows, after_response_rows, "N compression-positive (kN)"
    )
    shear_delta = _max_paired_delta(before_response_rows, after_response_rows, "V (kN)")
    displacement_delta = _max_paired_delta(
        before_response_rows, after_response_rows, "v_up (mm)"
    )
    stress_delta = _max_stress_delta(before_stress_rows, after_stress_rows)
    active_count = int(contact_result.get("active_count") or 0)
    total_reaction_kn = _float(contact_result.get("total_contact_reaction_N")) / 1000.0
    contact_carried_force = active_count > 0 and total_reaction_kn > 1.0e-6
    response_changed = any(
        (
            _float(moment_delta.get("Absolute change")) > 1.0e-3,
            _float(axial_delta.get("Absolute change")) > 1.0e-3,
            _float(shear_delta.get("Absolute change")) > 1.0e-3,
            _float(displacement_delta.get("Absolute change")) > 1.0e-6,
            _float(stress_delta.get("Absolute change")) > 1.0e-6,
        )
    )
    governing_delta = _float(released_fcgp_mpa) - _float(initial_fcgp_mpa)
    governing_changed = abs(governing_delta) > 1.0e-6
    verification_ready = not contact_carried_force or response_changed
    if not verification_ready:
        status = "EVENT EFFECT NEGLIGIBLE — VERIFY RESPONSE SOURCE"
    elif governing_changed:
        status = "EVENT EFFECT VERIFIED"
    else:
        status = "RESPONSE EFFECT VERIFIED — GOVERNING f_cgp UNCHANGED"

    before_fingerprint = _response_fingerprint(before_response_rows)
    after_fingerprint = _response_fingerprint(after_response_rows)
    summary_rows = [
        {
            "Quantity": "Active falsework contact nodes",
            "Post-ES contact state": active_count,
            "After falsework removal": 0,
            "Change / evidence": -active_count,
            "Basis": f"{int(contact_result.get('candidate_count') or 0)} candidate nodes",
        },
        {
            "Quantity": "Total falsework reaction (kN)",
            "Post-ES contact state": total_reaction_kn,
            "After falsework removal": 0.0,
            "Change / evidence": -total_reaction_kn,
            "Basis": "compression-only contact reaction removed",
        },
        {
            "Quantity": "Stage max |M| (kN-m)",
            "Post-ES contact state": _max_abs_value(
                before_response_rows, "M sagging-positive (kN-m)"
            ),
            "After falsework removal": _max_abs_value(
                after_response_rows, "M sagging-positive (kN-m)"
            ),
            "Change / evidence": _float(moment_delta.get("Absolute change")),
            "Basis": "event columns are stage maxima; evidence is max stationwise |ΔM|",
        },
        {
            "Quantity": "Stage max |V| (kN)",
            "Post-ES contact state": _max_abs_value(before_response_rows, "V (kN)"),
            "After falsework removal": _max_abs_value(after_response_rows, "V (kN)"),
            "Change / evidence": _float(shear_delta.get("Absolute change")),
            "Basis": "event columns are stage maxima; evidence is max stationwise |ΔV|",
        },
        {
            "Quantity": "Stage max |v| (mm)",
            "Post-ES contact state": _max_abs_value(before_response_rows, "v_up (mm)"),
            "After falsework removal": _max_abs_value(after_response_rows, "v_up (mm)"),
            "Change / evidence": _float(displacement_delta.get("Absolute change")),
            "Basis": "event columns are stage maxima; evidence is max stationwise |Δv|",
        },
        {
            "Quantity": "Governing f_cgp (MPa)",
            "Post-ES contact state": _float(initial_fcgp_mpa),
            "After falsework removal": _float(released_fcgp_mpa),
            "Change / evidence": governing_delta,
            "Basis": "event-specific bonded representative route",
        },
        {
            "Quantity": "f_cgp at max-change row (MPa)",
            "Post-ES contact state": _float(stress_delta.get("Before")),
            "After falsework removal": _float(stress_delta.get("After")),
            "Change / evidence": _float(stress_delta.get("Absolute change")),
            "Basis": (
                "evidence is max stationwise |Δf_cgp|; "
                f"{stress_delta.get('Element') or '—'} at s = "
                f"{_float(stress_delta.get('Station s (m)')):.3f} m"
            ),
        },
    ]
    delta_rows = []
    for label, units, row in (
        ("Moment M", "kN-m", moment_delta),
        ("Axial N", "kN", axial_delta),
        ("Shear V", "kN", shear_delta),
        ("Vertical displacement v", "mm", displacement_delta),
        ("Concrete stress f_cgp", "MPa", stress_delta),
    ):
        delta_rows.append(
            {
                "Response": label,
                "Units": units,
                "Station s (m)": _float(row.get("Station s (m)")),
                "Element": str(row.get("Element") or "—"),
                "Before": _float(row.get("Before")),
                "After": _float(row.get("After")),
                "Change": _float(row.get("Change")),
                "Max |change|": _float(row.get("Absolute change")),
            }
        )
    notes: list[str] = []
    if verification_ready and response_changed and not governing_changed:
        notes.append(
            "Falsework removal changes the structural response and local tendon-CG stresses, but the same representative limit row remains governing; therefore the scalar governing f_cgp is unchanged within tolerance."
        )
    if not verification_ready:
        notes.append(
            "The stored contact state carries compression reaction, but the no-contact response is unchanged within tolerance; verify that the released solution, not the stored contact solution, feeds the event audit."
        )
    return {
        "ready": verification_ready,
        "status": status,
        "response_changed": response_changed,
        "governing_fcgp_changed": governing_changed,
        "contact_carried_force": contact_carried_force,
        "initial_response_fingerprint": before_fingerprint,
        "released_response_fingerprint": after_fingerprint,
        "fingerprints_differ": before_fingerprint != after_fingerprint,
        "summary_rows": summary_rows,
        "delta_rows": delta_rows,
        "notes": notes,
        "max_response_deltas": {
            "moment_kNm": _float(moment_delta.get("Absolute change")),
            "axial_kN": _float(axial_delta.get("Absolute change")),
            "shear_kN": _float(shear_delta.get("Absolute change")),
            "vertical_displacement_mm": _float(
                displacement_delta.get("Absolute change")
            ),
            "fcgp_mpa": _float(stress_delta.get("Absolute change")),
            "governing_fcgp_mpa": governing_delta,
        },
    }


def run_crossbeam_event_stage_stress_sources(
    *,
    model: Mapping[str, Any],
    lightweight_es_result: Mapping[str, Any],
    profile_rows: Any,
    system_rows: Any,
    later_permanent_load_delta_fcgp_mpa: float = 0.0,
    later_fea_response_rows: Any = None,
    later_fea_source_declaration: Any = None,
) -> dict[str, Any]:
    """Resolve and verify stress sources at grouting, release, and later load.

    Falsework removal is represented by one fixed-base frame solve with all
    temporary vertical contact removed, while preserving self-weight and the
    accepted tendon force distribution after Elastic Shortening. The later-load
    increment is sourced from imported FEA P/V2/M3 rows when available; the
    legacy scalar remains only a backward-compatible QA fallback.
    """

    issues: list[str] = []
    es_result = dict(lightweight_es_result or {})
    if not bool(model.get("ready")):
        issues.extend(model.get("issues") or ["Stressing-stage frame model is not ready."])
    if not bool(es_result.get("ready")):
        issues.append("A CURRENT source-derived Lightweight ES result is required.")
    after_es_rows = list(es_result.get("after_es_station_rows") or [])
    load_source = prestress_equivalent_nodal_loads(
        model=model,
        profile_rows=profile_rows,
        anchorage_station_rows=after_es_rows,
    )
    if not bool(load_source.get("ready")):
        issues.append("Stored post-ES tendon equivalent loads are not ready.")
    if issues:
        return {
            "ready": False,
            "status": "SOURCE BLOCKED",
            "issues": _dedupe(issues),
            "solve_count": 0,
        }

    initial_fcgp = max(_float(es_result.get("fcgp_mpa")), 0.0)
    contact_result = dict(es_result.get("contact_result") or {})
    initial_response_rows = list(contact_result.get("beam_response_rows") or [])
    initial_stress_rows = list(es_result.get("stress_rows") or [])
    initial_route = dict(es_result.get("fcgp_route") or {})
    solution = solve_linear_frame(
        nodes=list(model.get("nodes") or []),
        elements=list(model.get("elements") or []),
        nodal_loads=dict(load_source.get("nodal_loads") or {}),
        uniform_local_y_by_element=dict(model.get("self_weight_uniform_N_per_mm") or {}),
        fixed_node_ids=list(model.get("fixed_node_ids") or []),
    )
    response_rows = _beam_response_rows(solution)
    stress_rows = _stress_rows_at_tendon_cg(
        model=model,
        response_rows=response_rows,
        profile_rows=profile_rows,
        system_rows=system_rows,
    )
    released_route = _bonded_fcgp_route(model, stress_rows) if stress_rows else {}
    released_fcgp = released_route.get("fcgp_mpa")
    if solution.get("status") != "LINEAR QA READY":
        issues.extend(solution.get("issues") or ["Falsework-removal frame solve requires review."])
    if released_fcgp is None:
        issues.append("Concrete stress after falsework removal could not be evaluated.")

    verification: dict[str, Any] = {}
    if released_fcgp is not None:
        verification = _event_response_verification(
            contact_result=contact_result,
            before_response_rows=initial_response_rows,
            after_response_rows=response_rows,
            before_stress_rows=initial_stress_rows,
            after_stress_rows=stress_rows,
            initial_fcgp_mpa=initial_fcgp,
            released_fcgp_mpa=_float(released_fcgp),
        )
        if not verification.get("ready"):
            issues.append(str(verification.get("status") or "Event response source requires review."))

    imported_later_source = resolve_imported_later_fea_response(
        model=model,
        load_rows=later_fea_response_rows,
        profile_rows=profile_rows,
        system_rows=system_rows,
        source_declaration=later_fea_source_declaration,
    )
    imported_active_count = int(imported_later_source.get("active_count") or 0)
    imported_ready = bool(imported_later_source.get("ready"))
    if imported_active_count > 0 and not imported_ready:
        issues.extend(imported_later_source.get("issues") or [
            "Imported Later Permanent Load FEA response requires review."
        ])

    if imported_ready:
        later_delta = _float(imported_later_source.get("delta_fcgp_mpa"))
        later_source_label = "Imported incremental FEA P/V2/M3 response at tp"
        later_audit_source = "Released-stage source + imported tp Δf_cd"
        later_source_mode = "VERIFIED IMPORTED FEA SOURCE"
    else:
        later_delta = _float(later_permanent_load_delta_fcgp_mpa)
        later_source_label = "Legacy engineer Δf_cd QA fallback"
        later_audit_source = "Released-stage source + legacy engineer Δf_cd"
        later_source_mode = "LEGACY QA FALLBACK"

    later_fcgp = (
        max(_float(released_fcgp) + later_delta, 0.0)
        if released_fcgp is not None
        else None
    )
    ready = not issues and released_fcgp is not None
    event_rows = [
        {
            "Event": "Post-ES / grouting",
            "Stress source": "Stored cumulative contact solution",
            "f_cgp (MPa; compression +)": initial_fcgp,
            "Δf_cgp from prior event (MPa)": 0.0,
            "Structural solves": 0,
        },
        {
            "Event": "After falsework removal",
            "Stress source": "One no-contact fixed-base frame solve",
            "f_cgp (MPa; compression +)": (
                _float(released_fcgp) if released_fcgp is not None else None
            ),
            "Δf_cgp from prior event (MPa)": (
                _float(released_fcgp) - initial_fcgp
                if released_fcgp is not None
                else None
            ),
            "Structural solves": 1,
        },
        {
            "Event": "After later permanent load",
            "Stress source": later_source_label,
            "f_cgp (MPa; compression +)": later_fcgp,
            "Δf_cgp from prior event (MPa)": later_delta,
            "Structural solves": 0,
        },
    ]
    stress_audit_rows = [
        _governing_stress_audit_row(
            event="Post-ES / grouting",
            source="Stored cumulative contact solution",
            model=model,
            route=initial_route,
        ),
        _governing_stress_audit_row(
            event="After falsework removal",
            source="One no-contact fixed-base frame solve",
            model=model,
            route=released_route,
        ),
        _governing_stress_audit_row(
            event="After later permanent load",
            source=later_audit_source,
            model=model,
            route=released_route,
            later_delta_fcgp_mpa=later_delta,
        ),
    ]
    return {
        "ready": ready,
        "status": "EVENT STRESS SOURCES VERIFIED" if ready else "REVIEW REQUIRED",
        "issues": _dedupe(issues),
        "solve_count": 1,
        "event_rows": event_rows,
        "stress_audit_rows": stress_audit_rows,
        "response_verification": verification,
        "initial_fcgp_mpa": initial_fcgp,
        "falsework_removed_fcgp_mpa": (
            _float(released_fcgp) if released_fcgp is not None else None
        ),
        "later_permanent_load_delta_fcgp_mpa": later_delta,
        "later_permanent_load_fcgp_mpa": later_fcgp,
        "later_permanent_load_source_mode": later_source_mode,
        "later_fea_response_source": imported_later_source,
        "falsework_solution": solution,
        "falsework_response_rows": response_rows,
        "falsework_stress_rows": stress_rows,
        "falsework_fcgp_route": released_route,
        "scope_guard": (
            "Falsework removal is solved once with temporary vertical contact removed and is verified against the stored contact response. "
            + (
                "Later permanent-load Δf_cd is calculated from one adopted imported FEA P/V2/M3 response without another internal structural solve."
                if imported_ready
                else "Later permanent-load Δf_cd is using the legacy engineer QA fallback because no verified imported FEA source is active."
            )
        ),
    }
