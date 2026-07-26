"""Gravity-only compression-contact QA for the Crossbeam stressing stage.

The module builds on the accepted linear 2D Portal-Frame kernel but adds a
rigid, frictionless, vertical unilateral contact set beneath every Crossbeam
mesh node.  It is deliberately limited to the self-weight stage:

- support reaction is upward/compressive only;
- the Crossbeam may separate upward from the falsework;
- an active-set iteration releases tensile reactions and re-closes penetrated
  open nodes;
- equilibrium, gap/reaction complementarity, synthetic benchmarks, and mesh
  sensitivity are diagnostic outputs only;
- prestress groups, source-derived f_cgp, Elastic Shortening, Pe/Pe_eff, Result
  Summary, and Report/QA remain locked.

Internal units are mm, MPa, N, and N-mm.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

import numpy as np

from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    DEFAULT_MESH_SENSITIVITY_LENGTHS_M,
    _beam_response_rows,
    _column_action_rows,
    build_crossbeam_linear_stage_model,
    solve_linear_frame,
)

PTLOSS3B2B1_METHOD = "RIGID VERTICAL COMPRESSION-ONLY CONTACT — GRAVITY-ONLY QA"
PTLOSS3B2B1_CASE = "SELF-WEIGHT + COMPRESSION-ONLY FALSEWORK CONTACT"
DEFAULT_CONTACT_MAX_ITERATIONS = 80
DEFAULT_CONTACT_FORCE_TOLERANCE_RATIO = 1.0e-8
DEFAULT_CONTACT_GAP_TOLERANCE_MM = 1.0e-8


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _dedupe(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(str(message).strip() for message in messages if str(message).strip()))


def _with_contact_reaction_semantics(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach tributary length and equivalent line reaction to contact rows.

    The active-set solver owns raw nodal reactions in ``N``/``kN``.  Those
    nodal values depend on contact-node spacing and therefore must not be
    presented as a mesh-independent distributed reaction.  For engineering
    review, each node is assigned the half-distance to its neighboring contact
    stations on each side.  The line-equivalent reaction is then
    ``q_i = R_i / L_trib,i`` in kN/m.  Endpoint nodes receive one half of the
    adjacent spacing, so the tributary lengths sum to the supported extent.
    """

    output = [dict(row) for row in rows]
    ordered = sorted(
        output,
        key=lambda row: (_float(row.get("station_m")), int(row.get("node_id") or 0)),
    )
    if len(ordered) == 1:
        ordered[0]["tributary_length_m"] = 0.0
        ordered[0]["line_reaction_kN_per_m"] = None
        return output

    tributary_by_node: dict[int, float] = {}
    for index, row in enumerate(ordered):
        station = _float(row.get("station_m"))
        left_half = 0.0
        right_half = 0.0
        if index > 0:
            left_half = 0.5 * max(
                station - _float(ordered[index - 1].get("station_m")), 0.0
            )
        if index + 1 < len(ordered):
            right_half = 0.5 * max(
                _float(ordered[index + 1].get("station_m")) - station, 0.0
            )
        tributary_by_node[int(row.get("node_id") or 0)] = left_half + right_half

    for row in output:
        tributary = tributary_by_node.get(int(row.get("node_id") or 0), 0.0)
        row["tributary_length_m"] = tributary
        row["line_reaction_kN_per_m"] = (
            _float(row.get("reaction_kN")) / tributary
            if tributary > 1.0e-12
            else None
        )
    return output


def _node_rows_by_id(solution: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(row.get("id")): dict(row) for row in solution.get("nodes", [])}


def solve_vertical_compression_contact(
    *,
    nodes: list[dict[str, Any]],
    elements: list[dict[str, Any]],
    contact_node_ids: list[int] | tuple[int, ...],
    nodal_loads: Mapping[int, tuple[float, float, float]] | None = None,
    uniform_local_y_by_element: Mapping[str, float] | None = None,
    fixed_node_ids: list[int] | tuple[int, ...] | None = None,
    permanent_restrained_dofs: list[int] | tuple[int, ...] | None = None,
    initial_active_contact_node_ids: list[int] | tuple[int, ...] | None = None,
    max_iterations: int = DEFAULT_CONTACT_MAX_ITERATIONS,
    force_tolerance_ratio: float = DEFAULT_CONTACT_FORCE_TOLERANCE_RATIO,
    gap_tolerance_mm: float = DEFAULT_CONTACT_GAP_TOLERANCE_MM,
) -> dict[str, Any]:
    """Solve rigid vertical unilateral contact with a primal active set.

    Coordinate/sign convention:
    - vertical displacement/gap ``g = v_up`` is positive when the member lifts
      away from the support and negative when it penetrates the support datum;
    - contact reaction ``r`` is positive upward/compressive;
    - accepted contact states satisfy ``g >= 0``, ``r >= 0``, and ``r*g = 0``.

    The algorithm starts with all candidate nodes active unless an explicit
    initial set is supplied.  At every iteration it removes active nodes with
    tensile reaction and adds open nodes with negative gap.  The underlying
    structural solve remains linear for each active set.
    """

    node_count = len(nodes)
    candidates = sorted(set(int(value) for value in contact_node_ids))
    issues: list[str] = []
    for node_id in candidates:
        if node_id < 0 or node_id >= node_count:
            issues.append(f"Contact node {node_id} is outside the frame node range.")
    if not candidates:
        issues.append("At least one compression-contact node is required.")
    if issues:
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "issues": _dedupe(issues),
            "contact_rows": [],
            "iteration_rows": [],
        }

    if initial_active_contact_node_ids is None:
        active = set(candidates)
    else:
        active = set(int(value) for value in initial_active_contact_node_ids if int(value) in candidates)

    permanent = sorted(set(int(value) for value in (permanent_restrained_dofs or [])))
    history: list[dict[str, Any]] = []
    seen_states: set[tuple[int, ...]] = set()
    final_solution: dict[str, Any] | None = None
    final_rows: list[dict[str, Any]] = []
    force_tolerance_n = 0.0
    gap_tolerance = max(abs(_float(gap_tolerance_mm)), 1.0e-12)
    max_iter = max(int(max_iterations), 1)

    for iteration in range(1, max_iter + 1):
        state = tuple(sorted(active))
        if state in seen_states:
            issues.append("Compression-contact active set cycled before convergence.")
            break
        seen_states.add(state)

        contact_dofs = [3 * node_id + 1 for node_id in sorted(active)]
        solution = solve_linear_frame(
            nodes=nodes,
            elements=elements,
            nodal_loads=nodal_loads,
            uniform_local_y_by_element=uniform_local_y_by_element,
            fixed_node_ids=fixed_node_ids,
            restrained_dofs=[*permanent, *contact_dofs],
        )
        if solution.get("status") == "SOURCE BLOCKED":
            issues.extend(solution.get("issues", []))
            final_solution = solution
            break

        by_id = _node_rows_by_id(solution)
        load_scale = max(
            sum(
                abs(_float(row.get("applied_fx_N"))) + abs(_float(row.get("applied_fy_N")))
                for row in solution.get("nodes", [])
            ),
            1.0,
        )
        force_tolerance_n = max(abs(_float(force_tolerance_ratio)) * load_scale, 1.0e-6)

        rows: list[dict[str, Any]] = []
        release: list[int] = []
        close: list[int] = []
        for node_id in candidates:
            node = by_id.get(node_id, {})
            is_active = node_id in active
            gap = _float(node.get("v_mm"))
            reaction = _float(node.get("reaction_fy_N")) if is_active else 0.0
            if is_active and reaction < -force_tolerance_n:
                release.append(node_id)
            if not is_active and gap < -gap_tolerance:
                close.append(node_id)
            rows.append(
                {
                    "node_id": node_id,
                    "label": str(node.get("label") or f"Node {node_id}"),
                    "station_m": _float(node.get("station_m")),
                    "state": "ACTIVE" if is_active else "OPEN",
                    "gap_mm": gap,
                    "reaction_N": reaction,
                    "reaction_kN": reaction / 1000.0,
                    "tensile_violation_N": max(-reaction, 0.0),
                    "penetration_mm": max(-gap, 0.0),
                    "complementarity_Nmm": abs(reaction * gap),
                }
            )

        history.append(
            {
                "Iteration": iteration,
                "Active contact nodes": len(active),
                "Open nodes": len(candidates) - len(active),
                "Released": ", ".join(str(value) for value in release) or "—",
                "Re-closed": ", ".join(str(value) for value in close) or "—",
                "Equilibrium residual": _float(solution.get("equilibrium", {}).get("max_residual_ratio"), 1.0),
            }
        )
        final_solution = solution
        final_rows = rows

        if not release and not close:
            break
        active.difference_update(release)
        active.update(close)
    else:
        issues.append(f"Compression-contact active set did not converge within {max_iter} iterations.")

    if final_solution is None:
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "issues": _dedupe(issues or ["Compression-contact solution was not produced."]),
            "contact_rows": [],
            "iteration_rows": history,
        }

    # Rebuild the final rows from the actual converged/review solution so state,
    # gap, and reaction remain aligned even when the last loop exited on a guard.
    by_id = _node_rows_by_id(final_solution)
    final_rows = []
    for node_id in candidates:
        node = by_id.get(node_id, {})
        is_active = node_id in active
        gap = _float(node.get("v_mm"))
        reaction = _float(node.get("reaction_fy_N")) if is_active else 0.0
        final_rows.append(
            {
                "node_id": node_id,
                "label": str(node.get("label") or f"Node {node_id}"),
                "station_m": _float(node.get("station_m")),
                "state": "ACTIVE" if is_active else "OPEN",
                "gap_mm": gap,
                "reaction_N": reaction,
                "reaction_kN": reaction / 1000.0,
                "tensile_violation_N": max(-reaction, 0.0),
                "penetration_mm": max(-gap, 0.0),
                "complementarity_Nmm": abs(reaction * gap),
            }
        )

    final_rows = _with_contact_reaction_semantics(final_rows)

    max_tensile = max((row["tensile_violation_N"] for row in final_rows), default=0.0)
    max_penetration = max((row["penetration_mm"] for row in final_rows), default=0.0)
    max_complementarity = max((row["complementarity_Nmm"] for row in final_rows), default=0.0)
    min_active_reaction = min(
        (row["reaction_N"] for row in final_rows if row["state"] == "ACTIVE"),
        default=0.0,
    )
    min_open_gap = min(
        (row["gap_mm"] for row in final_rows if row["state"] == "OPEN"),
        default=0.0,
    )
    equilibrium_ratio = _float(
        final_solution.get("equilibrium", {}).get("max_residual_ratio"), 1.0
    )
    complementarity_pass = (
        max_tensile <= force_tolerance_n
        and max_penetration <= gap_tolerance
        and min_active_reaction >= -force_tolerance_n
        and min_open_gap >= -gap_tolerance
    )
    converged = not issues and complementarity_pass and equilibrium_ratio <= 1.0e-8

    return {
        "status": "CONTACT QA READY" if converged else "REVIEW REQUIRED",
        "ready": converged,
        "method": PTLOSS3B2B1_METHOD,
        "issues": _dedupe(issues),
        "solution": final_solution,
        "contact_rows": final_rows,
        "iteration_rows": history,
        "candidate_count": len(candidates),
        "active_count": sum(row["state"] == "ACTIVE" for row in final_rows),
        "open_count": sum(row["state"] == "OPEN" for row in final_rows),
        "active_node_ids": sorted(active),
        "open_node_ids": sorted(set(candidates) - active),
        "total_contact_reaction_N": sum(row["reaction_N"] for row in final_rows),
        "total_contact_tributary_length_m": sum(
            _float(row.get("tributary_length_m")) for row in final_rows
        ),
        "max_gap_mm": max((row["gap_mm"] for row in final_rows), default=0.0),
        "min_gap_mm": min((row["gap_mm"] for row in final_rows), default=0.0),
        "min_active_reaction_N": min_active_reaction,
        "min_open_gap_mm": min_open_gap,
        "max_tensile_violation_N": max_tensile,
        "max_penetration_mm": max_penetration,
        "max_complementarity_Nmm": max_complementarity,
        "force_tolerance_N": force_tolerance_n,
        "gap_tolerance_mm": gap_tolerance,
        "equilibrium_residual_ratio": equilibrium_ratio,
        "complementarity_status": "PASS" if complementarity_pass else "REVIEW",
        "iterations": len(history),
    }


def run_crossbeam_gravity_contact_qa(*, model: Mapping[str, Any]) -> dict[str, Any]:
    """Run the active-project self-weight/contact QA without prestress loads."""

    if not bool(model.get("ready")):
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "issues": list(model.get("issues") or ["Frame model is not ready."]),
            "contact_rows": [],
            "iteration_rows": [],
            "case": PTLOSS3B2B1_CASE,
        }

    contact_node_ids = sorted(
        int(value) for value in dict(model.get("beam_node_by_station") or {}).values()
    )
    result = solve_vertical_compression_contact(
        nodes=list(model.get("nodes") or []),
        elements=list(model.get("elements") or []),
        contact_node_ids=contact_node_ids,
        uniform_local_y_by_element=dict(model.get("self_weight_uniform_N_per_mm") or {}),
        fixed_node_ids=list(model.get("fixed_node_ids") or []),
    )
    solution = dict(result.get("solution") or {})
    response_rows = _beam_response_rows(solution)
    solution["case"] = PTLOSS3B2B1_CASE
    solution["beam_response_rows"] = response_rows
    solution["column_action_rows"] = _column_action_rows(solution)
    metrics = {
        "max_abs_N_kN": max((abs(_float(row.get("N compression-positive (kN)"))) for row in response_rows), default=0.0),
        "max_abs_V_kN": max((abs(_float(row.get("V (kN)"))) for row in response_rows), default=0.0),
        "max_abs_M_kNm": max((abs(_float(row.get("M sagging-positive (kN-m)"))) for row in response_rows), default=0.0),
        "max_abs_v_mm": max((abs(_float(row.get("v_up (mm)"))) for row in response_rows), default=0.0),
        "max_up_mm": max((_float(row.get("v_up (mm)")) for row in response_rows), default=0.0),
        "max_down_mm": min((_float(row.get("v_up (mm)")) for row in response_rows), default=0.0),
    }
    solution["metrics"] = metrics
    return {
        **result,
        "case": PTLOSS3B2B1_CASE,
        "model": model,
        "solution": solution,
        "beam_response_rows": response_rows,
        "column_action_rows": solution.get("column_action_rows", []),
        "metrics": metrics,
        "fcgp_status": "LOCKED — PRESTRESS GROUP STAGES + STRESS EXTRACTION NOT RELEASED",
        "stage_sequence_status": "LOCKED — GRAVITY-ONLY CONTACT FOUNDATION",
        "solver_boundary": (
            "Gravity-only rigid vertical contact QA. It validates compression-only support and automatic lift-off mechanics but does not include tendon stressing groups and cannot feed f_cgp or Elastic Shortening."
        ),
    }


def _benchmark_beam_model(node_count: int = 3) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = [
        {"id": i, "label": f"B{i}", "kind": "beam", "station_m": float(i), "x_mm": 1000.0 * i, "y_mm": 0.0}
        for i in range(node_count)
    ]
    elements = [
        {
            "id": f"B{i+1}",
            "kind": "beam",
            "node_i": i,
            "node_j": i + 1,
            "station_i_m": float(i),
            "station_j_m": float(i + 1),
            "E_MPa": 30000.0,
            "A_mm2": 100000.0,
            "I_mm4": 8.0e9,
        }
        for i in range(node_count - 1)
    ]
    return nodes, elements


def compression_contact_benchmark_rows() -> list[dict[str, Any]]:
    """Return independent synthetic benchmarks for the unilateral kernel."""

    rows: list[dict[str, Any]] = []
    nodes, elements = _benchmark_beam_model(3)
    permanent = [0, 1, 3 * 2 + 1]  # u0, v0, v2

    downward = solve_vertical_compression_contact(
        nodes=nodes,
        elements=elements,
        contact_node_ids=[1],
        nodal_loads={1: (0.0, -1000.0, 0.0)},
        permanent_restrained_dofs=permanent,
    )
    down_contact = (downward.get("contact_rows") or [{}])[0]
    down_pass = (
        downward.get("ready")
        and down_contact.get("state") == "ACTIVE"
        and _float(down_contact.get("reaction_N")) >= 999.999
    )
    rows.append(
        {
            "Benchmark": "Downward load closes contact",
            "Expected": "Middle contact ACTIVE; upward reaction ≈ 1.000 kN",
            "Observed": f"{down_contact.get('state', '—')}; R={_float(down_contact.get('reaction_kN')):.6f} kN",
            "Residual": abs(_float(down_contact.get("reaction_N")) - 1000.0) / 1000.0,
            "Status": "PASS" if down_pass else "REVIEW",
        }
    )

    upward = solve_vertical_compression_contact(
        nodes=nodes,
        elements=elements,
        contact_node_ids=[1],
        nodal_loads={1: (0.0, 1000.0, 0.0)},
        permanent_restrained_dofs=permanent,
    )
    up_contact = (upward.get("contact_rows") or [{}])[0]
    up_pass = (
        upward.get("ready")
        and up_contact.get("state") == "OPEN"
        and _float(up_contact.get("gap_mm")) > 0.0
        and abs(_float(up_contact.get("reaction_N"))) <= _float(upward.get("force_tolerance_N"), 1.0)
    )
    rows.append(
        {
            "Benchmark": "Upward load causes lift-off",
            "Expected": "Middle contact OPEN; positive gap; zero reaction",
            "Observed": f"{up_contact.get('state', '—')}; g={_float(up_contact.get('gap_mm')):.6e} mm; R={_float(up_contact.get('reaction_kN')):.6f} kN",
            "Residual": max(0.0, -_float(up_contact.get("gap_mm"))),
            "Status": "PASS" if up_pass else "REVIEW",
        }
    )

    reclose = solve_vertical_compression_contact(
        nodes=nodes,
        elements=elements,
        contact_node_ids=[1],
        nodal_loads={1: (0.0, -1000.0, 0.0)},
        permanent_restrained_dofs=permanent,
        initial_active_contact_node_ids=[],
    )
    reclose_contact = (reclose.get("contact_rows") or [{}])[0]
    reclose_pass = (
        reclose.get("ready")
        and reclose_contact.get("state") == "ACTIVE"
        and any(str(row.get("Re-closed")) == "1" for row in reclose.get("iteration_rows", []))
    )
    rows.append(
        {
            "Benchmark": "Penetrated open node re-closes",
            "Expected": "Open start penetrates, active set adds middle contact",
            "Observed": f"{reclose_contact.get('state', '—')}; iterations={int(reclose.get('iterations') or 0)}",
            "Residual": _float(reclose.get("max_penetration_mm")),
            "Status": "PASS" if reclose_pass else "REVIEW",
        }
    )

    nodes5, elements5 = _benchmark_beam_model(5)
    permanent5 = [0, 1, 3 * 4 + 1]  # u0, v0, v4
    symmetric = solve_vertical_compression_contact(
        nodes=nodes5,
        elements=elements5,
        contact_node_ids=[1, 2, 3],
        nodal_loads={1: (0.0, -500.0, 0.0), 2: (0.0, 1500.0, 0.0), 3: (0.0, -500.0, 0.0)},
        permanent_restrained_dofs=permanent5,
    )
    sym_rows = {int(row.get("node_id")): row for row in symmetric.get("contact_rows", [])}
    mirror_state = sym_rows.get(1, {}).get("state") == sym_rows.get(3, {}).get("state")
    mirror_gap = abs(_float(sym_rows.get(1, {}).get("gap_mm")) - _float(sym_rows.get(3, {}).get("gap_mm")))
    mirror_reaction = abs(_float(sym_rows.get(1, {}).get("reaction_N")) - _float(sym_rows.get(3, {}).get("reaction_N")))
    sym_pass = symmetric.get("ready") and mirror_state and mirror_gap <= 1.0e-9 and mirror_reaction <= 1.0e-6
    rows.append(
        {
            "Benchmark": "Symmetric partial lift-off",
            "Expected": "Mirrored contact states, gaps, and reactions",
            "Observed": f"states {sym_rows.get(1, {}).get('state', '—')}/{sym_rows.get(3, {}).get('state', '—')}; Δg={mirror_gap:.3e} mm; ΔR={mirror_reaction:.3e} N",
            "Residual": max(mirror_gap, mirror_reaction / 1000.0),
            "Status": "PASS" if sym_pass else "REVIEW",
        }
    )
    return rows


def run_crossbeam_gravity_contact_mesh_sensitivity(
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
    concrete_materials: Any,
    column_rows: Any,
    profile_rows: Any,
    crossbeam_stressing_strength_ratio: float,
    mesh_lengths_m: tuple[float, ...] = DEFAULT_MESH_SENSITIVITY_LENGTHS_M,
) -> dict[str, Any]:
    """Run current-input gravity/contact QA at three beam mesh sizes.

    For a fully active rigid support, between-node bending and displacement
    converge to zero with the contact spacing; percentage changes in those
    already tiny quantities are therefore not a useful stability criterion.
    The audit instead checks global reaction/equilibrium stability and verifies
    monotonic decay of the residual between-contact M/v fields.  If lift-off
    occurs, the physical M/v/gap metrics must converge by the ordinary 1% rule.
    """

    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    previous: dict[str, float] | None = None
    reaction_delta_max = 0.0
    physical_delta_max = 0.0
    all_full_contact = True
    for target in mesh_lengths_m:
        model = build_crossbeam_linear_stage_model(
            length_m=length_m,
            segment_rows=segment_rows,
            section_definitions=section_definitions,
            concrete_materials=concrete_materials,
            column_rows=column_rows,
            profile_rows=profile_rows,
            crossbeam_stressing_strength_ratio=crossbeam_stressing_strength_ratio,
            max_beam_element_length_m=float(target),
        )
        result = run_crossbeam_gravity_contact_qa(model=model)
        if not result.get("ready"):
            issues.extend(f"{target:.3f} m: {issue}" for issue in result.get("issues", []))
        metrics = dict(result.get("metrics") or {})
        full_contact = int(result.get("active_count") or 0) == int(result.get("candidate_count") or -1)
        all_full_contact = all_full_contact and full_contact
        current = {
            "contact_reaction_kN": _float(result.get("total_contact_reaction_N")) / 1000.0,
            "max_gap_mm": _float(result.get("max_gap_mm")),
            "max_abs_M_kNm": _float(metrics.get("max_abs_M_kNm")),
            "max_abs_v_mm": _float(metrics.get("max_abs_v_mm")),
        }
        deltas: dict[str, float | None] = {key: None for key in current}
        if previous is not None:
            for key, value in current.items():
                scale = max(abs(value), abs(previous[key]), 1.0e-12)
                deltas[key] = 100.0 * abs(value - previous[key]) / scale
            reaction_delta_max = max(reaction_delta_max, _float(deltas["contact_reaction_kN"]))
            physical_delta_max = max(
                physical_delta_max,
                _float(deltas["max_gap_mm"]),
                _float(deltas["max_abs_M_kNm"]),
                _float(deltas["max_abs_v_mm"]),
            )
        rows.append(
            {
                "Target max element (m)": float(target),
                "Beam elements": int(model.get("mesh", {}).get("beam_element_count") or 0),
                "Contact status": result.get("status"),
                "Active / candidate": f"{int(result.get('active_count') or 0)} / {int(result.get('candidate_count') or 0)}",
                "Total contact R (kN)": current["contact_reaction_kN"],
                "Max gap (mm)": current["max_gap_mm"],
                "Max |M| (kN-m)": current["max_abs_M_kNm"],
                "Max |v| (mm)": current["max_abs_v_mm"],
                "Equilibrium residual": _float(result.get("equilibrium_residual_ratio"), 1.0),
                "ΔR from coarser (%)": deltas["contact_reaction_kN"],
                "Δgap from coarser (%)": deltas["max_gap_mm"],
                "ΔM from coarser (%)": deltas["max_abs_M_kNm"],
                "Δv from coarser (%)": deltas["max_abs_v_mm"],
            }
        )
        previous = current

    ready = not issues and all(str(row.get("Contact status")) == "CONTACT QA READY" for row in rows)
    monotonic_m = all(
        _float(rows[i]["Max |M| (kN-m)"]) <= _float(rows[i - 1]["Max |M| (kN-m)"]) + 1.0e-12
        for i in range(1, len(rows))
    )
    monotonic_v = all(
        _float(rows[i]["Max |v| (mm)"]) <= _float(rows[i - 1]["Max |v| (mm)"]) + 1.0e-12
        for i in range(1, len(rows))
    )
    equilibrium_ok = all(_float(row.get("Equilibrium residual"), 1.0) <= 1.0e-8 for row in rows)
    if all_full_contact:
        stable = ready and equilibrium_ok and reaction_delta_max <= 1.0 and monotonic_m and monotonic_v
        criterion = (
            "Fully active rigid-support route: total contact reaction change ≤ 1.0%, equilibrium passes, and residual between-contact M/v decrease monotonically with refinement."
        )
        reported_delta = reaction_delta_max
    else:
        stable = ready and equilibrium_ok and max(reaction_delta_max, physical_delta_max) <= 1.0
        criterion = (
            "Lift-off route: last-refinement changes ≤ 1.0% for total contact reaction, maximum gap, M, and v, with equilibrium and complementarity passing."
        )
        reported_delta = max(reaction_delta_max, physical_delta_max)
    return {
        "status": "QA STABLE" if stable else ("REVIEW" if ready else "SOURCE BLOCKED"),
        "ready": stable,
        "rows": rows,
        "issues": _dedupe(issues),
        "max_fine_mesh_delta_percent": reported_delta,
        "all_full_contact": all_full_contact,
        "criterion": criterion,
    }

