"""Lightweight event-based concrete-stress sources for Crossbeam PT losses.

PTLOSS4B2 solves only structural events that change the support/load state.  It
reuses the accepted stressing-stage frame model and stored post-ES source; it
does not run a structural solver at every material-aging time step.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.lightweight_elastic_shortening import (
    _bonded_fcgp_route,
    _stress_rows_at_tendon_cg,
)
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


def run_crossbeam_event_stage_stress_sources(
    *,
    model: Mapping[str, Any],
    lightweight_es_result: Mapping[str, Any],
    profile_rows: Any,
    system_rows: Any,
    later_permanent_load_delta_fcgp_mpa: float = 0.0,
) -> dict[str, Any]:
    """Resolve stress sources at grouting, falsework removal, and later load.

    The falsework-removal event is represented by one fixed-base frame solve
    with all temporary vertical contact removed, while preserving self-weight
    and the accepted tendon force distribution after Elastic Shortening.  A later permanent-load stress increment is an explicit engineering
    input until the Loads workspace supplies a verified load case.
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
            "issues": list(dict.fromkeys(str(item) for item in issues if str(item))),
            "solve_count": 0,
        }

    initial_fcgp = max(_float(es_result.get("fcgp_mpa")), 0.0)
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

    later_delta = _float(later_permanent_load_delta_fcgp_mpa)
    later_fcgp = max(_float(released_fcgp) + later_delta, 0.0) if released_fcgp is not None else None
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
            "f_cgp (MPa; compression +)": _float(released_fcgp) if released_fcgp is not None else None,
            "Δf_cgp from prior event (MPa)": (_float(released_fcgp) - initial_fcgp) if released_fcgp is not None else None,
            "Structural solves": 1,
        },
        {
            "Event": "After later permanent load",
            "Stress source": "Engineer input Δf_cd at tendon CG",
            "f_cgp (MPa; compression +)": later_fcgp,
            "Δf_cgp from prior event (MPa)": later_delta,
            "Structural solves": 0,
        },
    ]
    return {
        "ready": ready,
        "status": "EVENT STRESS SOURCES READY" if ready else "REVIEW REQUIRED",
        "issues": list(dict.fromkeys(str(item) for item in issues if str(item))),
        "solve_count": 1,
        "event_rows": event_rows,
        "initial_fcgp_mpa": initial_fcgp,
        "falsework_removed_fcgp_mpa": _float(released_fcgp) if released_fcgp is not None else None,
        "later_permanent_load_delta_fcgp_mpa": later_delta,
        "later_permanent_load_fcgp_mpa": later_fcgp,
        "falsework_solution": solution,
        "falsework_response_rows": response_rows,
        "falsework_stress_rows": stress_rows,
        "falsework_fcgp_route": released_route,
        "scope_guard": (
            "Falsework removal is solved once with temporary vertical contact removed. "
            "Later permanent-load Δf_cd remains an explicit engineer input until a verified Loads-workspace source is available."
        ),
    }
