"""Incremental tendon-group contact QA for the Crossbeam stressing stage.

This module advances the accepted gravity-only rigid unilateral-contact kernel
through the user-confirmed symmetric stressing sequence.  It deliberately uses
accepted tendon force *after Friction and Anchorage Set* and keeps prior groups
active while each new group is added.

Released scope:
- gravity equilibrium with full-length rigid vertical compression-only contact;
- cumulative G1 -> ... -> Gn post-anchor tendon loads;
- active-set update after every group, including tensile-reaction release and
  penetration re-closure;
- stage-wise contact state, reactions, gaps, frame actions, equilibrium, and
  final cumulative-versus-one-shot consistency QA.

Still locked:
- source-derived f_cgp extraction and bonded/unbonded routing;
- Elastic Shortening feedback to tendon force;
- P after ES, Pe/Pe_eff, time-dependent losses, Result Summary, and Report/QA.

Internal units are mm, MPa, N, and N-mm.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

import numpy as np

from concrete_pmm_pro.crossbeam.construction_stage import (
    stressing_pair_sequence_summary,
)
from concrete_pmm_pro.crossbeam.stressing_stage_contact import (
    solve_vertical_compression_contact,
)
from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    DEFAULT_MESH_SENSITIVITY_LENGTHS_M,
    _beam_response_rows,
    _column_action_rows,
    build_crossbeam_linear_stage_model,
    prestress_equivalent_nodal_loads,
)

PTLOSS3B2B2_METHOD = (
    "INCREMENTAL TENDON-GROUP RIGID COMPRESSION-CONTACT — POST-ANCHOR QA"
)
PTLOSS3B2B2_GRAVITY_STAGE = "G0 — GRAVITY / INITIAL CONTACT"
DEFAULT_STAGE_CONSISTENCY_FORCE_TOLERANCE_RATIO = 1.0e-8
DEFAULT_STAGE_CONSISTENCY_GAP_TOLERANCE_MM = 1.0e-8


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


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


def _merge_nodal_loads(
    *sources: Mapping[int, tuple[float, float, float]],
) -> dict[int, tuple[float, float, float]]:
    output: dict[int, np.ndarray] = {}
    for source in sources:
        for node_id, values in source.items():
            vector = np.asarray(values, dtype=float)
            if vector.shape != (3,):
                continue
            output.setdefault(int(node_id), np.zeros(3, dtype=float))
            output[int(node_id)] += vector
    return {
        node_id: tuple(float(value) for value in vector)
        for node_id, vector in output.items()
        if np.linalg.norm(vector) > 1.0e-12
    }


def _tendon_ids_from_group(row: Mapping[str, Any]) -> list[str]:
    explicit = [
        str(row.get("Left tendon") or "").strip(),
        str(row.get("Right tendon") or "").strip(),
    ]
    tendon_ids = [value for value in explicit if value]
    if not tendon_ids:
        text = str(
            row.get("Tendons") or row.get("Tendons stressed together") or ""
        )
        tendon_ids = [value.strip() for value in text.split("+") if value.strip()]
    return list(dict.fromkeys(tendon_ids))


def _solution_metrics(solution: Mapping[str, Any]) -> dict[str, float]:
    response_rows = list(solution.get("beam_response_rows") or [])
    return {
        "max_abs_N_kN": max(
            (
                abs(_float(row.get("N compression-positive (kN)")))
                for row in response_rows
            ),
            default=0.0,
        ),
        "max_abs_V_kN": max(
            (abs(_float(row.get("V (kN)"))) for row in response_rows),
            default=0.0,
        ),
        "max_abs_M_kNm": max(
            (
                abs(_float(row.get("M sagging-positive (kN-m)")))
                for row in response_rows
            ),
            default=0.0,
        ),
        "max_abs_v_mm": max(
            (abs(_float(row.get("v_up (mm)"))) for row in response_rows),
            default=0.0,
        ),
        "max_up_mm": max(
            (_float(row.get("v_up (mm)")) for row in response_rows),
            default=0.0,
        ),
        "max_down_mm": min(
            (_float(row.get("v_up (mm)")) for row in response_rows),
            default=0.0,
        ),
    }


def _enrich_contact_solution(result: dict[str, Any], *, case: str) -> dict[str, Any]:
    solution = dict(result.get("solution") or {})
    response_rows = _beam_response_rows(solution)
    solution["case"] = case
    solution["beam_response_rows"] = response_rows
    solution["column_action_rows"] = _column_action_rows(solution)
    solution["metrics"] = _solution_metrics(solution)
    result["solution"] = solution
    result["beam_response_rows"] = response_rows
    result["column_action_rows"] = solution.get("column_action_rows", [])
    result["metrics"] = dict(solution.get("metrics") or {})
    return result


def _fixed_base_reaction_fy_kN(
    solution: Mapping[str, Any], fixed_node_ids: list[int] | tuple[int, ...]
) -> float:
    fixed = set(int(value) for value in fixed_node_ids)
    return sum(
        _float(row.get("reaction_fy_N")) / 1000.0
        for row in solution.get("nodes", [])
        if int(row.get("id") or 0) in fixed
    )


def _contact_intervals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: _float(row.get("station_m")))
    if not ordered:
        return []
    output: list[dict[str, Any]] = []
    start = ordered[0]
    previous = ordered[0]
    for row in ordered[1:]:
        if str(row.get("state")) != str(previous.get("state")):
            output.append(
                {
                    "State": str(previous.get("state") or "—"),
                    "Start s (m)": _float(start.get("station_m")),
                    "End s (m)": _float(previous.get("station_m")),
                    "Node count": sum(
                        1
                        for candidate in ordered
                        if str(candidate.get("state"))
                        == str(previous.get("state"))
                        and _float(start.get("station_m"))
                        <= _float(candidate.get("station_m"))
                        <= _float(previous.get("station_m"))
                    ),
                }
            )
            start = row
        previous = row
    output.append(
        {
            "State": str(previous.get("state") or "—"),
            "Start s (m)": _float(start.get("station_m")),
            "End s (m)": _float(previous.get("station_m")),
            "Node count": sum(
                1
                for candidate in ordered
                if str(candidate.get("state")) == str(previous.get("state"))
                and _float(start.get("station_m"))
                <= _float(candidate.get("station_m"))
                <= _float(previous.get("station_m"))
            ),
        }
    )
    return output


def _stage_summary_row(stage: Mapping[str, Any]) -> dict[str, Any]:
    metrics = dict(stage.get("metrics") or {})
    result = dict(stage.get("contact_result") or {})
    return {
        "Stage": str(stage.get("stage_id") or "—"),
        "Added group": str(stage.get("added_group") or "—"),
        "Tendons added": str(stage.get("tendons") or "—"),
        "Cumulative groups": int(stage.get("cumulative_group_count") or 0),
        "Cumulative tendons": int(stage.get("cumulative_tendon_count") or 0),
        "Status": str(result.get("status") or "SOURCE BLOCKED"),
        "Active / candidate": (
            f"{int(result.get('active_count') or 0)} / "
            f"{int(result.get('candidate_count') or 0)}"
        ),
        "Open nodes": int(result.get("open_count") or 0),
        "Newly open": len(stage.get("newly_open_node_ids") or []),
        "Re-closed": len(stage.get("reclosed_node_ids") or []),
        "Max gap (mm)": _float(result.get("max_gap_mm")),
        "Total contact R (kN)": _float(result.get("total_contact_reaction_N"))
        / 1000.0,
        "Fixed-base Ry (kN)": _float(stage.get("fixed_base_reaction_fy_kN")),
        "Max |N| (kN)": _float(metrics.get("max_abs_N_kN")),
        "Max |V| (kN)": _float(metrics.get("max_abs_V_kN")),
        "Max |M| (kN-m)": _float(metrics.get("max_abs_M_kNm")),
        "Max |v| (mm)": _float(metrics.get("max_abs_v_mm")),
        "Iterations": int(result.get("iterations") or 0),
        "Complementarity": str(result.get("complementarity_status") or "REVIEW"),
        "Equilibrium residual": _float(result.get("equilibrium_residual_ratio"), 1.0),
    }


def solve_incremental_vertical_contact_stages(
    *,
    nodes: list[dict[str, Any]],
    elements: list[dict[str, Any]],
    contact_node_ids: list[int] | tuple[int, ...],
    fixed_node_ids: list[int] | tuple[int, ...],
    uniform_local_y_by_element: Mapping[str, float] | None,
    group_loads: list[dict[str, Any]],
) -> dict[str, Any]:
    """Solve gravity followed by cumulative contact-aware group load stages."""

    issues: list[str] = []
    stages: list[dict[str, Any]] = []
    cumulative_loads: dict[int, tuple[float, float, float]] = {}

    gravity = solve_vertical_compression_contact(
        nodes=nodes,
        elements=elements,
        contact_node_ids=contact_node_ids,
        nodal_loads={},
        uniform_local_y_by_element=uniform_local_y_by_element,
        fixed_node_ids=fixed_node_ids,
    )
    gravity = _enrich_contact_solution(gravity, case=PTLOSS3B2B2_GRAVITY_STAGE)
    gravity_stage = {
        "stage_index": 0,
        "stage_id": "G0",
        "stage_label": PTLOSS3B2B2_GRAVITY_STAGE,
        "added_group": "GRAVITY",
        "tendons": "—",
        "cumulative_group_count": 0,
        "cumulative_tendon_count": 0,
        "newly_open_node_ids": [],
        "reclosed_node_ids": [],
        "fixed_base_reaction_fy_kN": _fixed_base_reaction_fy_kN(
            gravity.get("solution", {}), fixed_node_ids
        ),
        "contact_result": gravity,
        "contact_rows": list(gravity.get("contact_rows") or []),
        "contact_interval_rows": _contact_intervals(
            list(gravity.get("contact_rows") or [])
        ),
        "beam_response_rows": list(gravity.get("beam_response_rows") or []),
        "column_action_rows": list(gravity.get("column_action_rows") or []),
        "metrics": dict(gravity.get("metrics") or {}),
        "cumulative_nodal_loads": {},
    }
    stages.append(gravity_stage)
    if not gravity.get("ready"):
        issues.extend(gravity.get("issues") or ["Gravity contact stage is not ready."])

    previous_active = set(int(value) for value in gravity.get("active_node_ids", []))
    cumulative_tendons: list[str] = []
    for index, group in enumerate(group_loads, start=1):
        group_id = str(group.get("group_id") or f"G{index}")
        tendon_ids = [str(value) for value in group.get("tendon_ids", []) if str(value)]
        cumulative_tendons.extend(tendon_ids)
        cumulative_loads = _merge_nodal_loads(
            cumulative_loads, dict(group.get("nodal_loads") or {})
        )
        result = solve_vertical_compression_contact(
            nodes=nodes,
            elements=elements,
            contact_node_ids=contact_node_ids,
            nodal_loads=cumulative_loads,
            uniform_local_y_by_element=uniform_local_y_by_element,
            fixed_node_ids=fixed_node_ids,
            initial_active_contact_node_ids=sorted(previous_active),
        )
        stage_label = f"{group_id} — {' + '.join(tendon_ids) or 'UNRESOLVED'}"
        result = _enrich_contact_solution(result, case=stage_label)
        current_active = set(int(value) for value in result.get("active_node_ids", []))
        newly_open = sorted(previous_active - current_active)
        reclosed = sorted(current_active - previous_active)
        stage = {
            "stage_index": index,
            "stage_id": group_id,
            "stage_label": stage_label,
            "added_group": group_id,
            "tendons": " + ".join(tendon_ids),
            "group_source": dict(group),
            "cumulative_group_count": index,
            "cumulative_tendon_count": len(set(cumulative_tendons)),
            "newly_open_node_ids": newly_open,
            "reclosed_node_ids": reclosed,
            "fixed_base_reaction_fy_kN": _fixed_base_reaction_fy_kN(
                result.get("solution", {}), fixed_node_ids
            ),
            "contact_result": result,
            "contact_rows": list(result.get("contact_rows") or []),
            "contact_interval_rows": _contact_intervals(
                list(result.get("contact_rows") or [])
            ),
            "beam_response_rows": list(result.get("beam_response_rows") or []),
            "column_action_rows": list(result.get("column_action_rows") or []),
            "metrics": dict(result.get("metrics") or {}),
            "cumulative_nodal_loads": dict(cumulative_loads),
        }
        stages.append(stage)
        if not result.get("ready"):
            issues.extend(
                f"{group_id}: {issue}"
                for issue in result.get("issues")
                or ["Incremental contact stage is not ready."]
            )
        previous_active = current_active

    final_direct: dict[str, Any] | None = None
    consistency = {
        "status": "NOT AVAILABLE",
        "ready": False,
        "state_match": False,
        "max_gap_delta_mm": None,
        "max_reaction_delta_kN": None,
        "max_displacement_delta_mm": None,
    }
    if group_loads and stages:
        final_stage = stages[-1]
        final_direct = solve_vertical_compression_contact(
            nodes=nodes,
            elements=elements,
            contact_node_ids=contact_node_ids,
            nodal_loads=cumulative_loads,
            uniform_local_y_by_element=uniform_local_y_by_element,
            fixed_node_ids=fixed_node_ids,
        )
        final_direct = _enrich_contact_solution(
            final_direct, case="FINAL CUMULATIVE — ONE-SHOT CHECK"
        )
        staged_rows = {
            int(row.get("node_id") or 0): row
            for row in final_stage.get("contact_rows", [])
        }
        direct_rows = {
            int(row.get("node_id") or 0): row
            for row in final_direct.get("contact_rows", [])
        }
        common = sorted(set(staged_rows) & set(direct_rows))
        state_match = bool(common) and all(
            str(staged_rows[node].get("state"))
            == str(direct_rows[node].get("state"))
            for node in common
        )
        max_gap_delta = max(
            (
                abs(
                    _float(staged_rows[node].get("gap_mm"))
                    - _float(direct_rows[node].get("gap_mm"))
                )
                for node in common
            ),
            default=0.0,
        )
        max_reaction_delta = max(
            (
                abs(
                    _float(staged_rows[node].get("reaction_kN"))
                    - _float(direct_rows[node].get("reaction_kN"))
                )
                for node in common
            ),
            default=0.0,
        )
        staged_nodes = {
            int(row.get("id") or 0): row
            for row in final_stage.get("contact_result", {})
            .get("solution", {})
            .get("nodes", [])
        }
        direct_nodes = {
            int(row.get("id") or 0): row
            for row in final_direct.get("solution", {}).get("nodes", [])
        }
        common_nodes = sorted(set(staged_nodes) & set(direct_nodes))
        max_displacement_delta = max(
            (
                abs(
                    _float(staged_nodes[node].get("v_mm"))
                    - _float(direct_nodes[node].get("v_mm"))
                )
                for node in common_nodes
            ),
            default=0.0,
        )
        force_scale = max(
            abs(_float(final_stage.get("contact_result", {}).get("total_contact_reaction_N")))
            / 1000.0,
            1.0,
        )
        force_tol = max(
            DEFAULT_STAGE_CONSISTENCY_FORCE_TOLERANCE_RATIO * force_scale,
            1.0e-6,
        )
        gap_tol = DEFAULT_STAGE_CONSISTENCY_GAP_TOLERANCE_MM
        consistency_ready = (
            bool(final_direct.get("ready"))
            and state_match
            and max_gap_delta <= gap_tol
            and max_reaction_delta <= force_tol
            and max_displacement_delta <= gap_tol
        )
        consistency = {
            "status": "PASS" if consistency_ready else "REVIEW",
            "ready": consistency_ready,
            "state_match": state_match,
            "max_gap_delta_mm": max_gap_delta,
            "max_reaction_delta_kN": max_reaction_delta,
            "max_displacement_delta_mm": max_displacement_delta,
            "force_tolerance_kN": force_tol,
            "gap_tolerance_mm": gap_tol,
        }
        if not consistency_ready:
            issues.append(
                "Final cumulative staged contact result does not match the independent one-shot solution within the adopted QA tolerances."
            )

    stage_rows = [_stage_summary_row(stage) for stage in stages]
    ready = (
        bool(group_loads)
        and not issues
        and all(
            bool(stage.get("contact_result", {}).get("ready")) for stage in stages
        )
        and bool(consistency.get("ready"))
    )
    return {
        "status": "INCREMENTAL CONTACT QA READY" if ready else "REVIEW REQUIRED",
        "ready": ready,
        "method": PTLOSS3B2B2_METHOD,
        "issues": _dedupe(issues),
        "stages": stages,
        "stage_rows": stage_rows,
        "final_stage": stages[-1] if stages else None,
        "final_direct_check": final_direct,
        "final_consistency": consistency,
        "group_count": len(group_loads),
        "stage_count": len(stages),
        "fcgp_status": "LOCKED — STAGE STRESS EXTRACTION + BOND ROUTING NOT RELEASED",
        "elastic_shortening_status": "LOCKED — TENDON FORCE FEEDBACK NOT RELEASED",
        "solver_boundary": (
            "Incremental contact QA preserves accepted P after Anchorage Set and updates rigid compression-only falsework contact after every stressing group. It does not calculate f_cgp, Elastic Shortening, P after ES, Pe/Pe_eff, or reportable design results."
        ),
    }


def run_crossbeam_incremental_contact_qa(
    *,
    model: Mapping[str, Any],
    profile_rows: Any,
    anchorage_station_rows: Any,
    group_rows: Any,
    pair_sequence: Any,
) -> dict[str, Any]:
    """Resolve the project stressing groups and run cumulative contact stages."""

    issues: list[str] = []
    if not bool(model.get("ready")):
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "issues": list(model.get("issues") or ["Frame model is not ready."]),
            "stages": [],
            "stage_rows": [],
            "group_source_rows": [],
            "fcgp_status": "LOCKED — FRAME MODEL SOURCE REQUIRED",
        }

    source_group_rows = _records(group_rows)
    sequence = stressing_pair_sequence_summary(source_group_rows, pair_sequence)
    if not sequence.get("ready"):
        issues.extend(sequence.get("issues") or ["Stressing-pair sequence is not ready."])
    by_group_id = {
        str(row.get("Group ID") or ""): row for row in source_group_rows
    }
    profile = _records(profile_rows)
    force_rows = _records(anchorage_station_rows)
    active_force_tendons = sorted(
        {
            str(row.get("Tendon ID") or "").strip()
            for row in force_rows
            if str(row.get("Tendon ID") or "").strip()
            and bool(row.get("Active", True))
            and row.get("P after anchorage set (kN)") is not None
        }
    )

    resolved_groups: list[dict[str, Any]] = []
    assigned_tendons: list[str] = []
    source_audit_rows: list[dict[str, Any]] = []
    for sequence_row in sequence.get("rows", []):
        group_id = str(sequence_row.get("Group ID") or "").strip()
        source_row = dict(by_group_id.get(group_id) or sequence_row)
        tendon_ids = _tendon_ids_from_group(source_row)
        assigned_tendons.extend(tendon_ids)
        if str(source_row.get("Status") or "") != "PAIR READY":
            issues.append(f"{group_id}: symmetric stressing pair is not ready.")
        if not tendon_ids:
            issues.append(f"{group_id}: no Tendon IDs are resolved.")
            continue
        profile_subset = [
            row for row in profile if str(row.get("Tendon ID") or "").strip() in tendon_ids
        ]
        force_subset = [
            row
            for row in force_rows
            if str(row.get("Tendon ID") or "").strip() in tendon_ids
        ]
        load_source = prestress_equivalent_nodal_loads(
            model=model,
            profile_rows=profile_subset,
            anchorage_station_rows=force_subset,
        )
        if not load_source.get("ready"):
            issues.extend(
                f"{group_id}: {issue}"
                for issue in load_source.get("issues")
                or ["Post-anchor tendon load source is not ready."]
            )
        force_values = [
            _float(row.get("P after anchorage set (kN)"))
            for row in force_subset
            if row.get("P after anchorage set (kN)") is not None
        ]
        resolved = {
            "group_id": group_id,
            "sequence": int(sequence_row.get("Sequence") or 0),
            "tendon_ids": tendon_ids,
            "tendons": " + ".join(tendon_ids),
            "group_pj_kN": _float(source_row.get("Group Pj (kN)")),
            "nodal_loads": dict(load_source.get("nodal_loads") or {}),
            "load_source": load_source,
        }
        resolved_groups.append(resolved)
        source_audit_rows.append(
            {
                "Sequence": int(sequence_row.get("Sequence") or 0),
                "Group": group_id,
                "Tendons": " + ".join(tendon_ids),
                "Group Pj (kN)": _float(source_row.get("Group Pj (kN)")),
                "Post-anchor tendon count": int(load_source.get("tendon_count") or 0),
                "Min P after anchor (kN)": min(force_values, default=0.0),
                "Max P after anchor (kN)": max(force_values, default=0.0),
                "Equivalent nodal-load nodes": len(load_source.get("nodal_loads") or {}),
                "Load source": str(load_source.get("status") or "SOURCE BLOCKED"),
            }
        )

    duplicate_tendons = sorted(
        {tendon for tendon in assigned_tendons if assigned_tendons.count(tendon) > 1}
    )
    missing_tendons = sorted(set(active_force_tendons) - set(assigned_tendons))
    extra_tendons = sorted(set(assigned_tendons) - set(active_force_tendons))
    if duplicate_tendons:
        issues.append(
            "A Tendon appears in more than one stressing group: "
            + ", ".join(duplicate_tendons)
            + "."
        )
    if missing_tendons:
        issues.append(
            "Active post-anchor Tendons are missing from the stressing sequence: "
            + ", ".join(missing_tendons)
            + "."
        )
    if extra_tendons:
        issues.append(
            "The stressing sequence references Tendons without an active post-anchor force source: "
            + ", ".join(extra_tendons)
            + "."
        )

    if issues:
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "issues": _dedupe(issues),
            "stages": [],
            "stage_rows": [],
            "group_source_rows": source_audit_rows,
            "sequence_source": sequence,
            "fcgp_status": "LOCKED — INCREMENTAL STAGE SOURCE REQUIRED",
            "elastic_shortening_status": "LOCKED — INCREMENTAL STAGE SOURCE REQUIRED",
        }

    contact_node_ids = sorted(
        int(value) for value in dict(model.get("beam_node_by_station") or {}).values()
    )
    result = solve_incremental_vertical_contact_stages(
        nodes=list(model.get("nodes") or []),
        elements=list(model.get("elements") or []),
        contact_node_ids=contact_node_ids,
        fixed_node_ids=list(model.get("fixed_node_ids") or []),
        uniform_local_y_by_element=dict(
            model.get("self_weight_uniform_N_per_mm") or {}
        ),
        group_loads=resolved_groups,
    )
    return {
        **result,
        "model": model,
        "sequence_source": sequence,
        "group_sources": resolved_groups,
        "group_source_rows": source_audit_rows,
    }


def incremental_contact_benchmark_rows() -> list[dict[str, Any]]:
    """Return independent benchmarks for cumulative stage/contact logic."""

    nodes = [
        {
            "id": index,
            "label": f"B{index}",
            "kind": "beam",
            "station_m": float(index),
            "x_mm": 1000.0 * index,
            "y_mm": 0.0,
        }
        for index in range(5)
    ]
    elements = [
        {
            "id": f"B{index + 1}",
            "kind": "beam",
            "node_i": index,
            "node_j": index + 1,
            "station_i_m": float(index),
            "station_j_m": float(index + 1),
            "E_MPa": 30_000.0,
            "A_mm2": 100_000.0,
            "I_mm4": 8.0e9,
        }
        for index in range(4)
    ]
    fixed = [0, 4]
    contact = [1, 2, 3]
    base_uniform = {element["id"]: -0.25 for element in elements}
    groups = [
        {
            "group_id": "G1",
            "tendon_ids": ["T1", "T5"],
            "nodal_loads": {2: (0.0, 1400.0, 0.0)},
        },
        {
            "group_id": "G2",
            "tendon_ids": ["T2", "T6"],
            "nodal_loads": {1: (0.0, -350.0, 0.0), 3: (0.0, -350.0, 0.0)},
        },
    ]
    result = solve_incremental_vertical_contact_stages(
        nodes=nodes,
        elements=elements,
        contact_node_ids=contact,
        fixed_node_ids=fixed,
        uniform_local_y_by_element=base_uniform,
        group_loads=groups,
    )
    stage_g1 = result.get("stages", [{}, {}])[1]
    stage_g2 = result.get("stages", [{}, {}, {}])[2]
    g1_rows = {
        int(row.get("node_id") or 0): row for row in stage_g1.get("contact_rows", [])
    }
    g2_rows = {
        int(row.get("node_id") or 0): row for row in stage_g2.get("contact_rows", [])
    }
    symmetry_residual = max(
        abs(_float(g2_rows.get(1, {}).get("gap_mm")) - _float(g2_rows.get(3, {}).get("gap_mm"))),
        abs(_float(g2_rows.get(1, {}).get("reaction_N")) - _float(g2_rows.get(3, {}).get("reaction_N"))) / 1000.0,
    )
    rows = [
        {
            "Benchmark": "Prestress-group uplift releases contact",
            "Expected": "G1 opens at least one candidate contact",
            "Observed": f"open={int(stage_g1.get('contact_result', {}).get('open_count') or 0)}",
            "Residual": 0.0 if int(stage_g1.get("contact_result", {}).get("open_count") or 0) > 0 else 1.0,
            "Status": "PASS" if int(stage_g1.get("contact_result", {}).get("open_count") or 0) > 0 else "REVIEW",
        },
        {
            "Benchmark": "Later group preserves prior loads and may re-close",
            "Expected": "G2 cumulative solution differs from G1 and remains contact-ready",
            "Observed": (
                f"G1 open={int(stage_g1.get('contact_result', {}).get('open_count') or 0)}; "
                f"G2 open={int(stage_g2.get('contact_result', {}).get('open_count') or 0)}"
            ),
            "Residual": abs(
                _float(stage_g2.get("metrics", {}).get("max_abs_M_kNm"))
                - _float(stage_g1.get("metrics", {}).get("max_abs_M_kNm"))
            ),
            "Status": "PASS" if stage_g2.get("contact_result", {}).get("ready") else "REVIEW",
        },
        {
            "Benchmark": "Symmetric cumulative stage remains mirrored",
            "Expected": "Mirrored gaps/reactions at contact nodes 1 and 3",
            "Observed": f"mirror residual={symmetry_residual:.3e}",
            "Residual": symmetry_residual,
            "Status": "PASS" if symmetry_residual <= 1.0e-8 else "REVIEW",
        },
        {
            "Benchmark": "Final staged result matches one-shot cumulative solve",
            "Expected": "Same active set, gap, reaction, and displacement",
            "Observed": str(result.get("final_consistency", {}).get("status") or "—"),
            "Residual": max(
                _float(result.get("final_consistency", {}).get("max_gap_delta_mm")),
                _float(result.get("final_consistency", {}).get("max_reaction_delta_kN")),
                _float(result.get("final_consistency", {}).get("max_displacement_delta_mm")),
            ),
            "Status": "PASS" if result.get("final_consistency", {}).get("ready") else "REVIEW",
        },
    ]
    return rows



def run_crossbeam_incremental_contact_mesh_sensitivity(
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
    concrete_materials: Any,
    column_rows: Any,
    profile_rows: Any,
    anchorage_station_rows: Any,
    group_rows: Any,
    pair_sequence: Any,
    crossbeam_stressing_strength_ratio: float,
    mesh_lengths_m: tuple[float, ...] = DEFAULT_MESH_SENSITIVITY_LENGTHS_M,
) -> dict[str, Any]:
    """Check global incremental-contact response across three contact meshes.

    The open/active boundary is discrete and its exact station is limited by the
    contact-node spacing.  Therefore the stability gate uses global structural
    quantities (total contact reaction, maximum gap, moment, and displacement),
    while open tributary length is reported as an informational boundary metric.
    The finest-grid half spacing is stated explicitly as the contact-boundary
    resolution; it is not hidden inside a misleading percentage PASS.
    """

    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    previous: dict[str, float] | None = None
    last_deltas: dict[str, float] = {}
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
        result = run_crossbeam_incremental_contact_qa(
            model=model,
            profile_rows=profile_rows,
            anchorage_station_rows=anchorage_station_rows,
            group_rows=group_rows,
            pair_sequence=pair_sequence,
        )
        if not result.get("ready"):
            issues.extend(
                f"{float(target):.3f} m: {issue}"
                for issue in result.get("issues")
                or ["Incremental contact QA is not ready."]
            )
        final_stage = dict(result.get("final_stage") or {})
        contact = dict(final_stage.get("contact_result") or {})
        metrics = dict(final_stage.get("metrics") or {})
        open_length = sum(
            _float(row.get("tributary_length_m"))
            for row in contact.get("contact_rows", [])
            if str(row.get("state")) == "OPEN"
        )
        current = {
            "total_contact_R_kN": _float(contact.get("total_contact_reaction_N"))
            / 1000.0,
            "max_gap_mm": _float(contact.get("max_gap_mm")),
            "max_abs_M_kNm": _float(metrics.get("max_abs_M_kNm")),
            "max_abs_v_mm": _float(metrics.get("max_abs_v_mm")),
            "open_length_m": open_length,
        }
        deltas: dict[str, float | None] = {key: None for key in current}
        if previous is not None:
            for key, value in current.items():
                scale = max(abs(value), abs(previous[key]), 1.0e-12)
                deltas[key] = 100.0 * abs(value - previous[key]) / scale
            last_deltas = {
                key: _float(value) for key, value in deltas.items() if value is not None
            }
        rows.append(
            {
                "Target max element (m)": float(target),
                "Beam elements": sum(
                    str(element.get("kind")) == "beam"
                    for element in model.get("elements", [])
                ),
                "Stage status": str(result.get("status") or "SOURCE BLOCKED"),
                "Final active / candidate": (
                    f"{int(contact.get('active_count') or 0)} / "
                    f"{int(contact.get('candidate_count') or 0)}"
                ),
                "Final open nodes": int(contact.get("open_count") or 0),
                "Open tributary length (m)": open_length,
                "Total contact R (kN)": current["total_contact_R_kN"],
                "Max gap (mm)": current["max_gap_mm"],
                "Max |M| (kN-m)": current["max_abs_M_kNm"],
                "Max |v| (mm)": current["max_abs_v_mm"],
                "Equilibrium residual": _float(
                    contact.get("equilibrium_residual_ratio"), 1.0
                ),
                "ΔR from coarser (%)": deltas["total_contact_R_kN"],
                "Δgap from coarser (%)": deltas["max_gap_mm"],
                "ΔM from coarser (%)": deltas["max_abs_M_kNm"],
                "Δv from coarser (%)": deltas["max_abs_v_mm"],
                "Δopen length from coarser (%)": deltas["open_length_m"],
            }
        )
        previous = current

    global_delta_keys = (
        "total_contact_R_kN",
        "max_gap_mm",
        "max_abs_M_kNm",
        "max_abs_v_mm",
    )
    max_last_global_delta = max(
        (_float(last_deltas.get(key), 1.0e9) for key in global_delta_keys),
        default=1.0e9,
    )
    equilibrium_pass = bool(rows) and all(
        _float(row.get("Equilibrium residual"), 1.0) <= 1.0e-8 for row in rows
    )
    stage_ready = bool(rows) and all(
        str(row.get("Stage status")) == "INCREMENTAL CONTACT QA READY"
        for row in rows
    )
    stable = (
        not issues
        and stage_ready
        and equilibrium_pass
        and len(rows) >= 2
        and max_last_global_delta <= 1.0
    )
    finest_spacing = min((float(value) for value in mesh_lengths_m), default=0.0)
    return {
        "status": "QA STABLE" if stable else ("REVIEW" if stage_ready else "SOURCE BLOCKED"),
        "ready": stable,
        "rows": rows,
        "issues": _dedupe(issues),
        "max_last_global_delta_percent": max_last_global_delta,
        "last_open_length_delta_percent": _float(
            last_deltas.get("open_length_m"), 0.0
        ),
        "contact_boundary_resolution_m": 0.5 * finest_spacing,
        "criterion": (
            "Last-refinement changes ≤ 1.0% for final total contact reaction, maximum gap, maximum |M|, and maximum |v|, with stage complementarity/consistency and equilibrium passing. Open tributary length is informational because the contact boundary remains discretized."
        ),
        "boundary_note": (
            f"The finest contact spacing is {finest_spacing:.3f} m, so reported active/open boundary stations have an approximate half-grid resolution of ±{0.5 * finest_spacing:.4f} m."
        ),
    }
