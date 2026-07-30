"""Linear 2D stressing-stage Portal-Frame response foundation.

The module provides a small, auditable Euler-Bernoulli 2D frame kernel for the
Portal Frame Crossbeam in the longitudinal ``s``-vertical plane.  It is a
*linear QA foundation* only:

- Crossbeam and fixed-base columns are modeled with auditable gross ``EA``/``EI``.
- Crossbeam ``Eci`` is resolved at the adopted stressing strength; column
  stiffness remains a separate stressing-stage source.
- Section centroid changes use exact rigid-offset transformations to one
  common reference axis instead of a straight-centroid approximation.
- Crossbeam self-weight and the accepted post-anchorage tendon force state are
  solved as separate linear load cases and as a superposed QA case.
- Tendon loads are assembled from the actual piecewise tendon profile and
  ``P after anchorage set``; no force is reconstructed from ``fpj``.
- Independent centroid-tendon, ``P·e`` sign, symmetry, and optional mesh
  sensitivity diagnostics harden the linear kernel without feeding results.
- Continuous temporary support/contact, lift-off iteration, final
  Primary/Secondary Prestress decomposition, source-derived ``f_cgp``, and the
  final Elastic Shortening handoff remain explicitly outside this milestone.

Internal units are mm, MPa, N, and N-mm.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import ceil, hypot, isfinite, sqrt
from typing import Any

import numpy as np

from concrete_pmm_pro.crossbeam.construction_stage import (
    canonical_column_stage_rows,
    column_section_properties,
    column_support_footprint_summary,
)
from concrete_pmm_pro.core.concrete_materials import aci_concrete_ec_mpa
from concrete_pmm_pro.crossbeam.section_library import (
    canonical_section_definitions,
    section_property_records,
)
from concrete_pmm_pro.crossbeam.tendon import canonical_tendon_profile_points

PTLOSS3B2A1_METHOD = "STAGE-MODULUS + RIGID-OFFSET 2D PORTAL-FRAME QA"
# Backward-compatible public name retained for tests/imports from B2A.
PTLOSS3B2A_METHOD = PTLOSS3B2A1_METHOD
PTLOSS3B2A_SELF_WEIGHT_CASE = "SELF-WEIGHT — PORTAL FRAME ONLY"
PTLOSS3B2A_PRESTRESS_CASE = "PRESTRESS AFTER ANCHORAGE SET"
PTLOSS3B2A_COMBINED_CASE = "LINEAR SUPERPOSITION QA"
PTLOSS3B2A_CASES = (
    PTLOSS3B2A_SELF_WEIGHT_CASE,
    PTLOSS3B2A_PRESTRESS_CASE,
    PTLOSS3B2A_COMBINED_CASE,
)

DEFAULT_MAX_BEAM_ELEMENT_LENGTH_M = 0.50
DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO = 0.80
MIN_CROSSBEAM_STRESSING_STRENGTH_RATIO = 0.50
DEFAULT_MESH_SENSITIVITY_LENGTHS_M = (0.50, 0.25, 0.125)
GRAVITY_M_S2 = 9.80665


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
    return list(dict.fromkeys(str(message).strip() for message in messages if str(message).strip()))


def _segment_id(row: Mapping[str, Any], index: int = 0) -> str:
    return str(row.get("Segment") or row.get("Zone") or f"R{index + 1}").strip()


def _segment_start(row: Mapping[str, Any]) -> float:
    return _float(row.get("x_start_m", row.get("s_start (m)", row.get("Start (m)"))))


def _segment_end(row: Mapping[str, Any]) -> float:
    return _float(row.get("x_end_m", row.get("s_end (m)", row.get("End (m)"))))


def _material_record(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        name = str(value.get("name") or value.get("Name") or "").strip()
        fc = _float(value.get("fc_MPa", value.get("fc_mpa", value.get("f'c (MPa)"))))
        density = _float(value.get("density_kg_m3", value.get("Density kg/m³")), 2400.0)
        ec_manual = value.get("Ec_MPa", value.get("ec_mpa"))
        ec_method = str(value.get("Ec_method", value.get("ec_method", "ACI auto")))
        if ec_method.casefold() == "manual" and _float(ec_manual) > 0.0:
            ec = _float(ec_manual)
        else:
            ec = 4700.0 * fc**0.5 if fc > 0.0 else 0.0
        return {
            "name": name,
            "fc_mpa": fc,
            "density_kg_m3": density,
            "ec_mpa": ec,
            "ec_method": ec_method,
        }
    name = str(getattr(value, "name", "") or "").strip()
    fc = _float(getattr(value, "fc_MPa", getattr(value, "fc_mpa", 0.0)))
    density = _float(getattr(value, "density_kg_m3", 2400.0), 2400.0)
    ec = _float(getattr(value, "effective_Ec_MPa", 0.0))
    ec_method = str(getattr(value, "Ec_method", "ACI auto") or "ACI auto")
    if ec <= 0.0 and fc > 0.0:
        ec = 4700.0 * fc**0.5
    return {
        "name": name,
        "fc_mpa": fc,
        "density_kg_m3": density,
        "ec_mpa": ec,
        "ec_method": ec_method,
    }


def _material_map(values: Any) -> dict[str, dict[str, Any]]:
    return {
        row["name"]: row
        for row in (_material_record(value) for value in (values or []))
        if row["name"]
    }


def frame_element_local_stiffness(
    *,
    length_mm: float,
    e_mpa: float,
    area_mm2: float,
    inertia_mm4: float,
) -> np.ndarray:
    """Return the standard 6x6 Euler-Bernoulli local frame stiffness matrix."""

    length = float(length_mm)
    e = float(e_mpa)
    area = float(area_mm2)
    inertia = float(inertia_mm4)
    if length <= 0.0 or e <= 0.0 or area <= 0.0 or inertia <= 0.0:
        raise ValueError("Frame element L, E, A, and I must all be positive.")
    ea_l = e * area / length
    ei = e * inertia
    b12 = 12.0 * ei / length**3
    b6 = 6.0 * ei / length**2
    b4 = 4.0 * ei / length
    b2 = 2.0 * ei / length
    return np.array(
        [
            [ea_l, 0.0, 0.0, -ea_l, 0.0, 0.0],
            [0.0, b12, b6, 0.0, -b12, b6],
            [0.0, b6, b4, 0.0, -b6, b2],
            [-ea_l, 0.0, 0.0, ea_l, 0.0, 0.0],
            [0.0, -b12, -b6, 0.0, b12, -b6],
            [0.0, b6, b2, 0.0, -b6, b4],
        ],
        dtype=float,
    )


def frame_transformation(*, c: float, s: float) -> np.ndarray:
    """Return the 6x6 global-to-local frame displacement transformation."""

    return np.array(
        [
            [c, s, 0.0, 0.0, 0.0, 0.0],
            [-s, c, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, c, s, 0.0],
            [0.0, 0.0, 0.0, -s, c, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def frame_rigid_offset_matrix(
    *,
    offset_i_y_mm: float = 0.0,
    offset_j_y_mm: float = 0.0,
) -> np.ndarray:
    """Map reference-node DOFs to centroidal element-end DOFs.

    The frame reference node and the member centroid may differ vertically.
    For a rigid arm ``r = (0, y)`` and small rotation ``theta``:

    ``u_centroid = u_reference - y * theta``
    ``v_centroid = v_reference``

    The transformation avoids artificial high-stiffness link elements and
    permits adjacent section regions with different centroid depths to share
    one auditable physical reference node.
    """

    matrix = np.eye(6, dtype=float)
    matrix[0, 2] = -float(offset_i_y_mm)
    matrix[3, 5] = -float(offset_j_y_mm)
    return matrix


def frame_uniform_local_y_load(*, q_n_per_mm: float, length_mm: float) -> np.ndarray:
    """Return the consistent local nodal vector for uniform local-y load ``q``."""

    q = float(q_n_per_mm)
    length = float(length_mm)
    return np.array(
        [
            0.0,
            q * length / 2.0,
            q * length**2 / 12.0,
            0.0,
            q * length / 2.0,
            -q * length**2 / 12.0,
        ],
        dtype=float,
    )


def _element_dofs(element: Mapping[str, Any]) -> list[int]:
    i = int(element["node_i"])
    j = int(element["node_j"])
    return [3 * i, 3 * i + 1, 3 * i + 2, 3 * j, 3 * j + 1, 3 * j + 2]


def solve_linear_frame(
    *,
    nodes: list[dict[str, Any]],
    elements: list[dict[str, Any]],
    nodal_loads: Mapping[int, tuple[float, float, float]] | None = None,
    uniform_local_y_by_element: Mapping[str, float] | None = None,
    fixed_node_ids: list[int] | tuple[int, ...] | None = None,
    restrained_dofs: list[int] | tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Solve a small linear 2D frame and return auditable reactions/actions.

    Node ids are list indices.  DOF order is ``[u_s, v_up, theta_ccw]``.
    Element loads use positive local-y.  For a horizontal left-to-right beam,
    downward gravity is therefore negative.
    """

    count = len(nodes)
    dof_count = 3 * count
    if count < 2 or not elements:
        return {
            "status": "SOURCE BLOCKED",
            "issues": ["At least two nodes and one frame element are required."],
        }

    stiffness = np.zeros((dof_count, dof_count), dtype=float)
    load = np.zeros(dof_count, dtype=float)
    element_cache: dict[str, dict[str, Any]] = {}
    issues: list[str] = []

    for node_id, values in (nodal_loads or {}).items():
        if int(node_id) < 0 or int(node_id) >= count:
            issues.append(f"Nodal load references unknown node {node_id}.")
            continue
        fx, fy, moment = values
        base = 3 * int(node_id)
        load[base : base + 3] += np.array([fx, fy, moment], dtype=float)

    node_by_id = {int(node["id"]): node for node in nodes}
    for element in elements:
        element_id = str(element.get("id") or "")
        try:
            node_i = node_by_id[int(element["node_i"])]
            node_j = node_by_id[int(element["node_j"])]
        except (KeyError, TypeError, ValueError):
            issues.append(f"Element {element_id or '?'} references an unknown node.")
            continue
        dx = _float(node_j.get("x_mm")) - _float(node_i.get("x_mm"))
        dy = _float(node_j.get("y_mm")) - _float(node_i.get("y_mm"))
        length = hypot(dx, dy)
        if length <= 1.0e-9:
            issues.append(f"Element {element_id or '?'} has zero length.")
            continue
        c = dx / length
        s = dy / length
        try:
            k_local = frame_element_local_stiffness(
                length_mm=length,
                e_mpa=_float(element.get("E_MPa")),
                area_mm2=_float(element.get("A_mm2")),
                inertia_mm4=_float(element.get("I_mm4")),
            )
        except ValueError as exc:
            issues.append(f"Element {element_id or '?'}: {exc}")
            continue
        transform = frame_transformation(c=c, s=s)
        rigid_offset = frame_rigid_offset_matrix(
            offset_i_y_mm=_float(element.get("offset_i_y_mm")),
            offset_j_y_mm=_float(element.get("offset_j_y_mm")),
        )
        reference_to_local = transform @ rigid_offset
        k_global = reference_to_local.T @ k_local @ reference_to_local
        dofs = _element_dofs(element)
        stiffness[np.ix_(dofs, dofs)] += k_global

        q_local_y = _float((uniform_local_y_by_element or {}).get(element_id), 0.0)
        f_local = frame_uniform_local_y_load(q_n_per_mm=q_local_y, length_mm=length)
        f_global = reference_to_local.T @ f_local
        load[dofs] += f_global
        element_cache[element_id] = {
            "length_mm": length,
            "c": c,
            "s": s,
            "k_local": k_local,
            "transform": transform,
            "rigid_offset": rigid_offset,
            "reference_to_local": reference_to_local,
            "f_local": f_local,
            "dofs": dofs,
            "q_local_y": q_local_y,
        }

    if issues:
        return {"status": "SOURCE BLOCKED", "issues": _dedupe(issues)}

    restrained: list[int] = []
    for node_id in fixed_node_ids or []:
        restrained.extend([3 * int(node_id), 3 * int(node_id) + 1, 3 * int(node_id) + 2])
    restrained.extend(int(value) for value in (restrained_dofs or []))
    restrained = sorted(set(restrained))
    invalid_restrained = [value for value in restrained if value < 0 or value >= dof_count]
    if invalid_restrained:
        return {
            "status": "SOURCE BLOCKED",
            "issues": [
                "Restrained DOF index is outside the assembled frame range: "
                + ", ".join(str(value) for value in invalid_restrained)
                + "."
            ],
        }
    free = [index for index in range(dof_count) if index not in restrained]
    displacement = np.zeros(dof_count, dtype=float)

    try:
        if free:
            k_ff = stiffness[np.ix_(free, free)]
            f_f = load[free]
            displacement[free] = np.linalg.solve(k_ff, f_f)
    except np.linalg.LinAlgError as exc:
        return {
            "status": "SOURCE BLOCKED",
            "issues": [f"Linear frame stiffness matrix could not be solved: {exc}."],
        }

    reaction = stiffness @ displacement - load
    element_results: list[dict[str, Any]] = []
    for element in elements:
        element_id = str(element.get("id") or "")
        cache = element_cache.get(element_id)
        if cache is None:
            continue
        d_global = displacement[cache["dofs"]]
        d_local = cache["reference_to_local"] @ d_global
        end_action_local = cache["k_local"] @ d_local - cache["f_local"]
        element_results.append(
            {
                **element,
                "length_mm": cache["length_mm"],
                "c": cache["c"],
                "s": cache["s"],
                "q_local_y_N_per_mm": cache["q_local_y"],
                "d_local": d_local.tolist(),
                "end_action_local": end_action_local.tolist(),
            }
        )

    node_rows: list[dict[str, Any]] = []
    fixed_set = set(fixed_node_ids or [])
    restrained_set = set(restrained)
    for node in nodes:
        node_id = int(node["id"])
        base = 3 * node_id
        restrained_u = base in restrained_set
        restrained_v = base + 1 in restrained_set
        restrained_theta = base + 2 in restrained_set
        node_rows.append(
            {
                **node,
                "u_mm": displacement[base],
                "v_mm": displacement[base + 1],
                "theta_rad": displacement[base + 2],
                "applied_fx_N": load[base],
                "applied_fy_N": load[base + 1],
                "applied_moment_Nmm": load[base + 2],
                "reaction_fx_N": reaction[base] if restrained_u else 0.0,
                "reaction_fy_N": reaction[base + 1] if restrained_v else 0.0,
                "reaction_moment_Nmm": reaction[base + 2] if restrained_theta else 0.0,
                "restrained_u": restrained_u,
                "restrained_v": restrained_v,
                "restrained_theta": restrained_theta,
                "fixed": node_id in fixed_set,
            }
        )

    applied_fx = sum(row["applied_fx_N"] for row in node_rows)
    applied_fy = sum(row["applied_fy_N"] for row in node_rows)
    applied_moment = sum(
        row["applied_moment_Nmm"]
        + row["x_mm"] * row["applied_fy_N"]
        - row["y_mm"] * row["applied_fx_N"]
        for row in node_rows
    )
    reaction_fx = sum(row["reaction_fx_N"] for row in node_rows)
    reaction_fy = sum(row["reaction_fy_N"] for row in node_rows)
    reaction_moment = sum(
        row["reaction_moment_Nmm"]
        + row["x_mm"] * row["reaction_fy_N"]
        - row["y_mm"] * row["reaction_fx_N"]
        for row in node_rows
    )
    residual_fx = applied_fx + reaction_fx
    residual_fy = applied_fy + reaction_fy
    residual_moment = applied_moment + reaction_moment
    force_scale = max(
        sum(abs(row["applied_fx_N"]) + abs(row["applied_fy_N"]) for row in node_rows),
        1.0,
    )
    moment_scale = max(
        sum(
            abs(row["applied_moment_Nmm"])
            + abs(row["x_mm"] * row["applied_fy_N"] - row["y_mm"] * row["applied_fx_N"])
            for row in node_rows
        ),
        1.0,
    )
    force_residual_ratio = hypot(residual_fx, residual_fy) / force_scale
    moment_residual_ratio = abs(residual_moment) / moment_scale
    equilibrium_ratio = max(force_residual_ratio, moment_residual_ratio)

    return {
        "status": "LINEAR QA READY" if equilibrium_ratio <= 1.0e-8 else "EQUILIBRIUM REVIEW",
        "issues": [],
        "nodes": node_rows,
        "elements": element_results,
        "displacement_vector": displacement.tolist(),
        "load_vector": load.tolist(),
        "reaction_vector": reaction.tolist(),
        "equilibrium": {
            "applied_fx_N": applied_fx,
            "applied_fy_N": applied_fy,
            "applied_moment_Nmm": applied_moment,
            "reaction_fx_N": reaction_fx,
            "reaction_fy_N": reaction_fy,
            "reaction_moment_Nmm": reaction_moment,
            "residual_fx_N": residual_fx,
            "residual_fy_N": residual_fy,
            "residual_moment_Nmm": residual_moment,
            "force_residual_ratio": force_residual_ratio,
            "moment_residual_ratio": moment_residual_ratio,
            "max_residual_ratio": equilibrium_ratio,
        },
    }


def _canonical_ranges(segment_values: Any, *, length_m: float) -> tuple[list[dict[str, Any]], list[str]]:
    length = max(_float(length_m), 0.0)
    rows = _records(segment_values)
    normalized: list[dict[str, Any]] = []
    issues: list[str] = []
    for index, row in enumerate(rows):
        start = _segment_start(row)
        end = _segment_end(row)
        section_id = str(row.get("Section ID") or "").strip()
        if end <= start:
            issues.append(f"{_segment_id(row, index)} has non-positive station extent.")
        if start < -1.0e-9 or end > length + 1.0e-9:
            issues.append(f"{_segment_id(row, index)} lies outside s = 0 to L.")
        if not section_id:
            issues.append(f"{_segment_id(row, index)} has no Section ID.")
        normalized.append(
            {
                "Region": _segment_id(row, index),
                "start_m": start,
                "end_m": end,
                "section_id": section_id,
            }
        )
    normalized.sort(key=lambda row: (row["start_m"], row["end_m"], row["Region"]))
    if not normalized:
        issues.append("No active Segment/Section-Zone ranges are available.")
    else:
        if abs(normalized[0]["start_m"]) > 1.0e-8:
            issues.append("Active Crossbeam ranges do not start at s = 0.")
        if abs(normalized[-1]["end_m"] - length) > 1.0e-8:
            issues.append("Active Crossbeam ranges do not end at s = L.")
        for left, right in zip(normalized, normalized[1:]):
            if abs(left["end_m"] - right["start_m"]) > 1.0e-8:
                issues.append(
                    f"{left['Region']} -> {right['Region']} contains a gap or overlap in station coverage."
                )
    return normalized, _dedupe(issues)


def _range_at_station(ranges: list[dict[str, Any]], station_m: float, *, length_m: float) -> dict[str, Any] | None:
    station = float(station_m)
    tolerance = max(1.0e-9, float(length_m) * 1.0e-10)
    for index, row in enumerate(ranges):
        is_last = index == len(ranges) - 1
        if station >= row["start_m"] - tolerance and (
            station < row["end_m"] - tolerance or (is_last and station <= row["end_m"] + tolerance)
        ):
            return row
    return None


def _subdivided_stations(base_stations: list[float], *, max_length_m: float) -> list[float]:
    maximum = max(float(max_length_m), 0.05)
    values = sorted(set(round(float(value), 9) for value in base_stations))
    output: list[float] = []
    for start, end in zip(values, values[1:]):
        if not output:
            output.append(start)
        span = end - start
        count = max(int(ceil(span / maximum)), 1)
        for index in range(1, count + 1):
            output.append(start + span * index / count)
    return [round(value, 9) for value in output]


def _interpolate(points: list[tuple[float, float]], station_m: float) -> float | None:
    if not points:
        return None
    station = float(station_m)
    if station < points[0][0] - 1.0e-8 or station > points[-1][0] + 1.0e-8:
        return None
    if station <= points[0][0] + 1.0e-8:
        return points[0][1]
    if station >= points[-1][0] - 1.0e-8:
        return points[-1][1]
    for (s0, value0), (s1, value1) in zip(points, points[1:]):
        if s0 - 1.0e-9 <= station <= s1 + 1.0e-9:
            if abs(s1 - s0) <= 1.0e-12:
                return value1
            ratio = (station - s0) / (s1 - s0)
            return value0 + ratio * (value1 - value0)
    return None


def build_crossbeam_linear_stage_model(
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
    concrete_materials: Any,
    column_rows: Any,
    profile_rows: Any,
    crossbeam_stressing_strength_ratio: float = DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
    max_beam_element_length_m: float = DEFAULT_MAX_BEAM_ELEMENT_LENGTH_M,
    enforce_support_footprint: bool = False,
) -> dict[str, Any]:
    """Resolve a piecewise-gross Crossbeam + fixed-base column frame model.

    Crossbeam stiffness is evaluated at the adopted stressing strength
    ``f'ci = ratio * f'c`` using the app's ACI normal-weight concrete modulus
    route.  Column ``f'c`` inputs are treated as the available column strength
    at stressing because the current construction source does not define a
    separate column-age ratio.

    A common physical reference axis is placed at the centroid depth of the
    first active Crossbeam region.  Other region centroids are connected to
    that reference axis through exact small-displacement rigid-offset
    transformations in the element stiffness assembly.
    """

    length = max(_float(length_m), 0.0)
    issues: list[str] = []
    notes: list[str] = []
    if length <= 0.0:
        issues.append("Crossbeam length must be positive.")
    stressing_ratio = _float(
        crossbeam_stressing_strength_ratio,
        DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
    )
    if stressing_ratio < MIN_CROSSBEAM_STRESSING_STRENGTH_RATIO or stressing_ratio > 1.0:
        issues.append(
            "Crossbeam stressing-strength ratio f'ci/f'c must be between "
            f"{MIN_CROSSBEAM_STRESSING_STRENGTH_RATIO:.2f} and 1.00."
        )

    ranges, range_issues = _canonical_ranges(segment_rows, length_m=length)
    issues.extend(range_issues)
    definitions = canonical_section_definitions(section_definitions)
    definition_by_id = {row["Section ID"]: row for row in definitions}
    property_by_id = {row["Section ID"]: row for row in section_property_records(definitions)}
    materials = _material_map(concrete_materials)

    section_sources: dict[str, dict[str, Any]] = {}
    for row in ranges:
        section_id = row["section_id"]
        definition = definition_by_id.get(section_id)
        prop = property_by_id.get(section_id)
        if definition is None or prop is None:
            issues.append(f"{row['Region']} references unknown Section ID {section_id or '(blank)' }.")
            continue
        if str(prop.get("Status")) not in {"READY", "REVIEW"}:
            issues.append(f"Section {section_id} gross properties are not ready.")
            continue
        material_name = str(definition.get("Material") or "").strip()
        material = materials.get(material_name)
        if material is None:
            issues.append(f"Section {section_id} material '{material_name}' is not available.")
            continue
        if material["ec_mpa"] <= 0.0 or material["density_kg_m3"] <= 0.0:
            issues.append(f"Section {section_id} material stiffness/density source is invalid.")
            continue
        fci_mpa = material["fc_mpa"] * stressing_ratio
        if (
            str(material.get("ec_method") or "").casefold() == "manual"
            and material["ec_mpa"] > 0.0
            and material["fc_mpa"] > 0.0
        ):
            eci_mpa = material["ec_mpa"] * sqrt(fci_mpa / material["fc_mpa"])
            modulus_source = (
                "Manual Ec at f'c scaled by sqrt(f'ci/f'c) for stressing stage"
            )
        else:
            eci_mpa = aci_concrete_ec_mpa(fci_mpa) if fci_mpa > 0.0 else 0.0
            modulus_source = "ACI Ec = 4700 sqrt(f'ci); f'ci = ratio x f'c"
        if eci_mpa <= 0.0:
            issues.append(f"Section {section_id} stressing-stage Eci source is invalid.")
            continue
        ctop = _float(prop.get("Centroid from top mm"))
        height = _float(definition.get("Parameters", {}).get("height_mm"))
        section_sources[section_id] = {
            "Section ID": section_id,
            "Material": material_name,
            "fc_28_mpa": material["fc_mpa"],
            "Ec_28_MPa": material["ec_mpa"],
            "fci_mpa": fci_mpa,
            "Eci_MPa": eci_mpa,
            "E_MPa": eci_mpa,
            "stressing_strength_ratio": stressing_ratio,
            "modulus_source": modulus_source,
            "density_kg_m3": material["density_kg_m3"],
            "A_mm2": _float(prop.get("Area mm²")),
            "I_mm4": _float(prop.get("Ix mm4")),
            "centroid_from_top_mm": ctop,
            "height_mm": height,
            "status": str(prop.get("Status")),
        }
        if section_sources[section_id]["A_mm2"] <= 0.0 or section_sources[section_id]["I_mm4"] <= 0.0:
            issues.append(f"Section {section_id} A/I source is invalid.")

    columns = canonical_column_stage_rows(column_rows, length_m=length)
    support_footprint_qa = column_support_footprint_summary(
        columns,
        segment_rows,
        length_m=length,
    )
    if enforce_support_footprint and not support_footprint_qa.get("ready"):
        for row in support_footprint_qa.get("rows", []):
            if str(row.get("Status") or "") == "COMPATIBLE":
                continue
            issues.append(
                f"{row.get('Column') or 'Column'} support footprint: {row.get('Issue') or 'review required'}"
            )
    if len(columns) < 2:
        issues.append("At least two columns are required for the Portal-Frame QA model.")
    column_sources: list[dict[str, Any]] = []
    seen_stations: set[float] = set()
    seen_column_ids: set[str] = set()
    for row in columns:
        column_id = str(row.get("Column ID") or "").strip()
        column_id_key = column_id.casefold()
        if column_id_key in seen_column_ids:
            issues.append("Column IDs must be unique.")
        seen_column_ids.add(column_id_key)
        station = round(_float(row.get("Station s (m)")), 9)
        if station in seen_stations:
            issues.append("Column stations must be unique.")
        seen_stations.add(station)
        props = column_section_properties(row)
        if not props.get("ready") or _float(row.get("Height (m)")) <= 0.0:
            issues.extend([f"{row.get('Column ID')}: {issue}" for issue in props.get("issues", [])])
            if _float(row.get("Height (m)")) <= 0.0:
                issues.append(f"{row.get('Column ID')}: Column height must be positive.")
            continue
        column_sources.append(
            {
                **row,
                "A_mm2": _float(props.get("Area (mm²)")),
                "I_mm4": _float(props.get("I_perp_s (mm⁴)")),
                "fc_stage_mpa": _float(row.get("f'c (MPa)")),
                "E_stage_MPa": _float(props.get("Ec (MPa)")),
                "E_MPa": _float(props.get("Ec (MPa)")),
                "modulus_source": "ACI Ec = 4700 sqrt(column f'c input); column input treated as available stressing-stage strength",
            }
        )

    profile = canonical_tendon_profile_points(profile_rows, length)
    base_stations = [0.0, length]
    for row in ranges:
        base_stations.extend([row["start_m"], row["end_m"]])
    for row in column_sources:
        base_stations.append(_float(row.get("Station s (m)")))
    for row in profile:
        base_stations.append(_float(row.get("s (m)")))
    stations = _subdivided_stations(
        base_stations,
        max_length_m=max_beam_element_length_m,
    ) if length > 0.0 else []
    mandatory_stations = sorted(
        set(round(float(value), 9) for value in base_stations)
    )
    station_set = set(round(float(value), 9) for value in stations)
    missing_mandatory_stations = [
        value for value in mandatory_stations if value not in station_set
    ]
    if missing_mandatory_stations:
        issues.append(
            "Mandatory Section/Column/Tendon stations are missing from the beam mesh: "
            + ", ".join(f"{value:.6f}" for value in missing_mandatory_stations)
            + "."
        )

    reference_section_id = ranges[0]["section_id"] if ranges else ""
    reference_section = section_sources.get(reference_section_id, {})
    reference_centroid_from_top_mm = _float(
        reference_section.get("centroid_from_top_mm")
    )
    if not reference_section:
        issues.append("A Crossbeam reference-axis section could not be resolved from the first active region.")

    for section in section_sources.values():
        section["centroid_offset_from_reference_mm"] = (
            reference_centroid_from_top_mm
            - _float(section.get("centroid_from_top_mm"))
        )

    nodes: list[dict[str, Any]] = []
    beam_node_by_station: dict[float, int] = {}
    for station in stations:
        node_id = len(nodes)
        nodes.append(
            {
                "id": node_id,
                "label": f"B@{station:.3f}",
                "kind": "beam",
                "station_m": station,
                "x_mm": station * 1000.0,
                "y_mm": 0.0,
            }
        )
        beam_node_by_station[round(station, 9)] = node_id

    elements: list[dict[str, Any]] = []
    self_weight_uniform: dict[str, float] = {}
    for index, (station_i, station_j) in enumerate(zip(stations, stations[1:]), start=1):
        midpoint = 0.5 * (station_i + station_j)
        region = _range_at_station(ranges, midpoint, length_m=length)
        if region is None:
            issues.append(f"No Section ID is resolved at s = {midpoint:.6f} m.")
            continue
        section = section_sources.get(region["section_id"])
        if section is None:
            continue
        element_id = f"B{index}"
        elements.append(
            {
                "id": element_id,
                "kind": "beam",
                "node_i": beam_node_by_station[round(station_i, 9)],
                "node_j": beam_node_by_station[round(station_j, 9)],
                "station_i_m": station_i,
                "station_j_m": station_j,
                "region": region["Region"],
                "section_id": region["section_id"],
                "E_MPa": section["E_MPa"],
                "A_mm2": section["A_mm2"],
                "I_mm4": section["I_mm4"],
                "offset_i_y_mm": section["centroid_offset_from_reference_mm"],
                "offset_j_y_mm": section["centroid_offset_from_reference_mm"],
            }
        )
        weight_n_per_mm = (
            section["A_mm2"]
            * section["density_kg_m3"]
            * GRAVITY_M_S2
            * 1.0e-9
        )
        self_weight_uniform[element_id] = -weight_n_per_mm

    fixed_node_ids: list[int] = []
    for index, column in enumerate(column_sources, start=1):
        station = round(_float(column.get("Station s (m)")), 9)
        top_node = beam_node_by_station.get(station)
        if top_node is None:
            issues.append(f"Column {column.get('Column ID')} station is not present in the beam mesh.")
            continue
        base_node = len(nodes)
        nodes.append(
            {
                "id": base_node,
                "label": f"{column.get('Column ID')} base",
                "kind": "column_base",
                "column_id": str(column.get("Column ID") or f"C{index}"),
                "station_m": station,
                "x_mm": station * 1000.0,
                "y_mm": -_float(column.get("Height (m)")) * 1000.0,
            }
        )
        fixed_node_ids.append(base_node)
        elements.append(
            {
                "id": f"C{index}",
                "kind": "column",
                "column_id": str(column.get("Column ID") or f"C{index}"),
                "node_i": base_node,
                "node_j": top_node,
                "station_i_m": station,
                "station_j_m": station,
                "E_MPa": column["E_MPa"],
                "A_mm2": column["A_mm2"],
                "I_mm4": column["I_mm4"],
            }
        )

    ctop_values = [source["centroid_from_top_mm"] for source in section_sources.values()]
    centroid_spread = max(ctop_values) - min(ctop_values) if ctop_values else 0.0
    if centroid_spread > 1.0e-6:
        notes.append(
            "Multiple section centroid depths are active. The linear stressing-stage model uses exact element-end rigid-offset transformations to a common reference axis; no high-stiffness dummy links are used."
        )
    notes.append(
        "Closure/joint concrete is not modeled as a separate frame stiffness region in this gross-section QA. Its specified stressing strength remains a construction acceptance source only."
    )

    issues = _dedupe(issues)
    return {
        "status": "MODEL READY" if nodes and elements and not issues else "SOURCE BLOCKED",
        "ready": bool(nodes and elements) and not issues,
        "method": PTLOSS3B2A_METHOD,
        "length_m": length,
        "stations_m": stations,
        "nodes": nodes,
        "elements": elements,
        "fixed_node_ids": fixed_node_ids,
        "beam_node_by_station": beam_node_by_station,
        "ranges": ranges,
        "section_sources": section_sources,
        "column_sources": column_sources,
        "support_footprint_qa": support_footprint_qa,
        "support_footprint_gate": (
            "ENFORCED" if enforce_support_footprint else "AUDIT ONLY"
        ),
        "reference_axis": {
            "status": "READY" if reference_section else "SOURCE BLOCKED",
            "reference_section_id": reference_section_id,
            "reference_centroid_from_top_mm": reference_centroid_from_top_mm,
            "centroid_spread_mm": centroid_spread,
            "method": "Common reference axis + exact centroidal rigid-offset transformation",
        },
        "stage_modulus": {
            "crossbeam_stressing_strength_ratio": stressing_ratio,
            "crossbeam_method": (
                "Per-section material basis at f'ci = ratio x f'c: ACI auto uses "
                "4700 sqrt(f'ci); Manual Ec uses Ec(f'c) sqrt(f'ci/f'c)"
            ),
            "column_method": "ACI Ec = 4700 sqrt(column f'c input)",
            "closure_joint_model": "NOT MODELED AS SEPARATE FRAME STIFFNESS REGION",
        },
        "mesh": {
            "target_max_element_length_m": max(float(max_beam_element_length_m), 0.05),
            "beam_element_count": sum(str(row.get("kind")) == "beam" for row in elements),
            "column_element_count": sum(str(row.get("kind")) == "column" for row in elements),
            "mandatory_station_count": len(mandatory_stations),
            "mandatory_stations_m": mandatory_stations,
            "missing_mandatory_stations_m": missing_mandatory_stations,
            "mandatory_station_status": (
                "PASS" if not missing_mandatory_stations else "REVIEW"
            ),
        },
        "self_weight_uniform_N_per_mm": self_weight_uniform,
        "issues": issues,
        "notes": _dedupe(notes),
        "solver_boundary": (
            "Fixed-base stressing-stage gross-section linear frame with stage Eci and centroidal rigid offsets only; continuous temporary-support contact/lift-off is excluded, so this model does not release stressing-stage f_cgp or final Elastic Shortening."
        ),
    }


def prestress_equivalent_nodal_loads(
    *,
    model: Mapping[str, Any],
    profile_rows: Any,
    anchorage_station_rows: Any,
) -> dict[str, Any]:
    """Assemble tendon equivalent nodal forces/moments on beam centroid nodes."""

    if not bool(model.get("ready")):
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "nodal_loads": {},
            "audit_rows": [],
            "issues": list(model.get("issues") or ["Frame model is not ready."]),
        }
    length = _float(model.get("length_m"))
    stations = [float(value) for value in model.get("stations_m", [])]
    ranges = list(model.get("ranges", []))
    section_sources = dict(model.get("section_sources", {}))
    reference_centroid_value = model.get("reference_axis", {}).get(
        "reference_centroid_from_top_mm"
    )
    if reference_centroid_value is None and section_sources:
        reference_centroid_value = next(iter(section_sources.values())).get(
            "centroid_from_top_mm"
        )
    reference_centroid_from_top_mm = _float(reference_centroid_value)
    node_by_station = dict(model.get("beam_node_by_station", {}))
    profiles = canonical_tendon_profile_points(profile_rows, length)
    force_rows = _records(anchorage_station_rows)
    issues: list[str] = []

    profile_by_tendon: dict[str, list[tuple[float, float]]] = {}
    for row in profiles:
        tendon_id = str(row.get("Tendon ID") or "").strip()
        if tendon_id:
            profile_by_tendon.setdefault(tendon_id, []).append(
                (_float(row.get("s (m)")), _float(row.get("dtop (mm)")))
            )
    force_by_tendon: dict[str, list[tuple[float, float]]] = {}
    active_by_tendon: dict[str, bool] = {}
    for row in force_rows:
        tendon_id = str(row.get("Tendon ID") or "").strip()
        if not tendon_id:
            continue
        active_by_tendon[tendon_id] = bool(row.get("Active", True))
        value = row.get("P after anchorage set (kN)")
        if value is not None:
            force_by_tendon.setdefault(tendon_id, []).append(
                (_float(row.get("s (m)")), _float(value))
            )
    for values in profile_by_tendon.values():
        values.sort()
    for values in force_by_tendon.values():
        values.sort()

    nodal: dict[int, np.ndarray] = {
        int(node_id): np.zeros(3, dtype=float)
        for node_id in node_by_station.values()
    }
    audit_rows: list[dict[str, Any]] = []
    station_reference: dict[float, dict[str, float]] = {}
    tendon_count = 0
    for tendon_id, profile_points in sorted(profile_by_tendon.items()):
        if active_by_tendon.get(tendon_id, True) is False:
            continue
        force_points = force_by_tendon.get(tendon_id, [])
        if not force_points:
            issues.append(f"{tendon_id}: P after Anchorage Set station source is not available.")
            continue
        if abs(profile_points[0][0]) > 1.0e-8 or abs(profile_points[-1][0] - length) > 1.0e-8:
            issues.append(f"{tendon_id}: tendon profile must extend from s = 0 to L for the frame load route.")
            continue
        tendon_count += 1
        tendon_values: list[dict[str, float]] = []
        for station in stations:
            dtop = _interpolate(profile_points, station)
            force_kn = _interpolate(force_points, station)
            region = _range_at_station(ranges, station, length_m=length)
            section = section_sources.get(region["section_id"]) if region else None
            if dtop is None or force_kn is None or section is None:
                issues.append(f"{tendon_id}: profile/force/section source is incomplete at s = {station:.6f} m.")
                tendon_values = []
                break
            centroid_from_top = _float(section.get("centroid_from_top_mm"))
            e_below_local = dtop - centroid_from_top
            y_tendon_from_reference = reference_centroid_from_top_mm - dtop
            tendon_values.append(
                {
                    "station_m": station,
                    "dtop_mm": dtop,
                    "force_N": force_kn * 1000.0,
                    "centroid_from_top_mm": centroid_from_top,
                    "e_below_local_mm": e_below_local,
                    "y_tendon_from_reference_mm": y_tendon_from_reference,
                    "primary_M_sagging_Nmm": -force_kn * 1000.0 * e_below_local,
                }
            )
            station_key = round(station, 9)
            station_reference.setdefault(
                station_key,
                {
                    "s (m)": station,
                    "Total P after anchorage (kN)": 0.0,
                    "Primary P·e moment (kN-m; sagging +)": 0.0,
                    "Tendon vertical resultant (kN; up +)": 0.0,
                    "Tendon count": 0.0,
                },
            )
            station_reference[station_key]["Total P after anchorage (kN)"] += force_kn
            station_reference[station_key][
                "Primary P·e moment (kN-m; sagging +)"
            ] += (-force_kn * e_below_local / 1000.0)
            station_reference[station_key]["Tendon count"] += 1.0
        if not tendon_values:
            continue

        for index, (left, right) in enumerate(zip(tendon_values, tendon_values[1:]), start=1):
            dx = (right["station_m"] - left["station_m"]) * 1000.0
            dy = (
                right["y_tendon_from_reference_mm"]
                - left["y_tendon_from_reference_mm"]
            )
            length_seg = hypot(dx, dy)
            if length_seg <= 1.0e-9:
                issues.append(f"{tendon_id}: zero-length tendon load segment at s = {left['station_m']:.6f} m.")
                continue
            ux = dx / length_seg
            uy = dy / length_seg
            force_i = np.array(
                [
                    left["force_N"] * ux,
                    left["force_N"] * uy,
                    -left["y_tendon_from_reference_mm"]
                    * left["force_N"]
                    * ux,
                ],
                dtype=float,
            )
            force_j = np.array(
                [
                    -right["force_N"] * ux,
                    -right["force_N"] * uy,
                    right["y_tendon_from_reference_mm"]
                    * right["force_N"]
                    * ux,
                ],
                dtype=float,
            )
            node_i = int(node_by_station[round(left["station_m"], 9)])
            node_j = int(node_by_station[round(right["station_m"], 9)])
            nodal[node_i] += force_i
            nodal[node_j] += force_j
            audit_rows.append(
                {
                    "Tendon": tendon_id,
                    "Path segment": index,
                    "s_i (m)": left["station_m"],
                    "s_j (m)": right["station_m"],
                    "P_i (kN)": left["force_N"] / 1000.0,
                    "P_j (kN)": right["force_N"] / 1000.0,
                    "e_i below local centroid (mm)": left["e_below_local_mm"],
                    "e_j below local centroid (mm)": right["e_below_local_mm"],
                    "y_i from reference (mm; up +)": left[
                        "y_tendon_from_reference_mm"
                    ],
                    "y_j from reference (mm; up +)": right[
                        "y_tendon_from_reference_mm"
                    ],
                    "Primary M_i (kN-m; sagging +)": left[
                        "primary_M_sagging_Nmm"
                    ]
                    / 1.0e6,
                    "Primary M_j (kN-m; sagging +)": right[
                        "primary_M_sagging_Nmm"
                    ]
                    / 1.0e6,
                    "Fx_i (kN)": force_i[0] / 1000.0,
                    "Fy_i (kN)": force_i[1] / 1000.0,
                    "M_i (kN-m)": force_i[2] / 1.0e6,
                    "Fx_j (kN)": force_j[0] / 1000.0,
                    "Fy_j (kN)": force_j[1] / 1000.0,
                    "M_j (kN-m)": force_j[2] / 1.0e6,
                }
            )

    nodal_output = {
        node_id: tuple(float(value) for value in vector)
        for node_id, vector in nodal.items()
        if np.linalg.norm(vector) > 1.0e-12
    }
    issues = _dedupe(issues)
    primary_reference_rows = [station_reference[key] for key in sorted(station_reference)]
    return {
        "status": "LOAD SOURCE READY" if tendon_count > 0 and not issues else "SOURCE BLOCKED",
        "ready": tendon_count > 0 and not issues,
        "tendon_count": tendon_count,
        "nodal_loads": nodal_output,
        "audit_rows": audit_rows,
        "primary_reference_rows": primary_reference_rows,
        "issues": issues,
        "source": "Accepted P after Anchorage Set + adopted tendon profile + common physical reference axis",
    }


def _merge_nodal_loads(
    left: Mapping[int, tuple[float, float, float]],
    right: Mapping[int, tuple[float, float, float]],
) -> dict[int, tuple[float, float, float]]:
    output: dict[int, np.ndarray] = {}
    for source in (left, right):
        for node_id, values in source.items():
            output.setdefault(int(node_id), np.zeros(3, dtype=float))
            output[int(node_id)] += np.array(values, dtype=float)
    return {node_id: tuple(float(value) for value in vector) for node_id, vector in output.items()}


def _beam_response_rows(solution: Mapping[str, Any], *, samples_per_element: int = 4) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for element in solution.get("elements", []):
        if str(element.get("kind")) != "beam":
            continue
        length = _float(element.get("length_mm"))
        if length <= 0.0:
            continue
        actions = list(element.get("end_action_local") or [0.0] * 6)
        displacements = list(element.get("d_local") or [0.0] * 6)
        q = _float(element.get("q_local_y_N_per_mm"))
        station_i = _float(element.get("station_i_m"))
        station_j = _float(element.get("station_j_m"))
        count = max(int(samples_per_element), 1)
        for sample in range(count + 1):
            ratio = sample / count
            x = ratio * length
            station = station_i + ratio * (station_j - station_i)
            # Compression-positive axial; sagging-positive moment.  V = dM/dx.
            n_comp = _float(actions[0])
            shear = _float(actions[1]) + q * x
            moment = -_float(actions[2]) + _float(actions[1]) * x + 0.5 * q * x**2
            h1 = 1.0 - 3.0 * ratio**2 + 2.0 * ratio**3
            h2 = length * (ratio - 2.0 * ratio**2 + ratio**3)
            h3 = 3.0 * ratio**2 - 2.0 * ratio**3
            h4 = length * (-ratio**2 + ratio**3)
            v_local = (
                h1 * _float(displacements[1])
                + h2 * _float(displacements[2])
                + h3 * _float(displacements[4])
                + h4 * _float(displacements[5])
            )
            u_local = (1.0 - ratio) * _float(displacements[0]) + ratio * _float(displacements[3])
            rows.append(
                {
                    "Element": str(element.get("id") or ""),
                    "Region": str(element.get("region") or ""),
                    "Section ID": str(element.get("section_id") or ""),
                    "s (m)": station,
                    "N compression-positive (kN)": n_comp / 1000.0,
                    "V (kN)": shear / 1000.0,
                    "M sagging-positive (kN-m)": moment / 1.0e6,
                    "u_s (mm)": u_local,
                    "v_up (mm)": v_local,
                }
            )
    rows.sort(key=lambda row: (round(row["s (m)"], 9), row["Element"]))
    return rows


def _column_action_rows(solution: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for element in solution.get("elements", []):
        if str(element.get("kind")) != "column":
            continue
        actions = list(element.get("end_action_local") or [0.0] * 6)
        rows.append(
            {
                "Column": str(element.get("column_id") or element.get("id") or ""),
                "Axial at base (kN)": _float(actions[0]) / 1000.0,
                "Shear at base (kN)": _float(actions[1]) / 1000.0,
                "Moment at base (kN-m)": -_float(actions[2]) / 1.0e6,
                "Axial at top (kN)": -_float(actions[3]) / 1000.0,
                "Shear at top (kN)": -_float(actions[4]) / 1000.0,
                "Moment at top (kN-m)": _float(actions[5]) / 1.0e6,
            }
        )
    return rows



def linear_response_event_audit_rows(
    *,
    model: Mapping[str, Any],
    profile_rows: Any,
    prestress_load_source: Mapping[str, Any],
    solution: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return station events that explain apparent local-moment steps.

    The audit does not certify a physical discontinuity.  It co-locates the
    Section/Zone transition, column line, tendon control-point roles, assembled
    equivalent nodal force/couple, and left/right section-local actions.  The
    ``|N·Δy|`` value is a reference-axis shift magnitude only; concentrated
    tendon couples and column-joint actions may coexist at the same station.
    """

    if not bool(model.get("ready")) or not solution:
        return []
    length = _float(model.get("length_m"))
    tolerance = max(length * 1.0e-9, 1.0e-8)
    ranges = list(model.get("ranges") or [])
    section_sources = dict(model.get("section_sources") or {})
    nodes_by_station = dict(model.get("beam_node_by_station") or {})
    nodal_loads = dict(prestress_load_source.get("nodal_loads") or {})

    events: dict[float, dict[str, Any]] = {}

    def event(station: float) -> dict[str, Any]:
        key = round(float(station), 9)
        events.setdefault(
            key,
            {
                "s (m)": float(station),
                "event_types": set(),
                "profile_roles": set(),
                "tendon_ids": set(),
            },
        )
        return events[key]

    event(0.0)["event_types"].add("Left anchorage / member end")
    event(length)["event_types"].add("Right anchorage / member end")

    for left, right in zip(ranges, ranges[1:]):
        station = _float(left.get("end_m"))
        row = event(station)
        row["event_types"].add("Section/Zone boundary")
        row["left_region"] = str(left.get("Region") or "")
        row["right_region"] = str(right.get("Region") or "")
        row["left_section"] = str(left.get("section_id") or "")
        row["right_section"] = str(right.get("section_id") or "")

    for column in model.get("column_sources", []):
        station = _float(column.get("Station s (m)"))
        row = event(station)
        row["event_types"].add("Column centerline")
        row.setdefault("columns", set()).add(str(column.get("Column ID") or ""))

    for point in canonical_tendon_profile_points(profile_rows, length):
        station = _float(point.get("s (m)"))
        row = event(station)
        role = str(point.get("Curve role") or "Profile point").strip()
        tendon_id = str(point.get("Tendon ID") or "").strip()
        row["event_types"].add("Tendon profile control station")
        if role:
            row["profile_roles"].add(role)
        if tendon_id:
            row["tendon_ids"].add(tendon_id)

    element_results = [
        row for row in solution.get("elements", []) if str(row.get("kind")) == "beam"
    ]

    def end_action(element: Mapping[str, Any], *, at_right: bool) -> dict[str, float]:
        actions = list(element.get("end_action_local") or [0.0] * 6)
        length_mm = _float(element.get("length_mm"))
        q = _float(element.get("q_local_y_N_per_mm"))
        x = length_mm if at_right else 0.0
        return {
            "N": _float(actions[0]) / 1000.0,
            "V": (_float(actions[1]) + q * x) / 1000.0,
            "M": (
                -_float(actions[2]) + _float(actions[1]) * x + 0.5 * q * x**2
            )
            / 1.0e6,
        }

    rows: list[dict[str, Any]] = []
    for station_key in sorted(events):
        source = events[station_key]
        station = _float(source.get("s (m)"))
        left_elements = [
            row
            for row in element_results
            if abs(_float(row.get("station_j_m")) - station) <= tolerance
        ]
        right_elements = [
            row
            for row in element_results
            if abs(_float(row.get("station_i_m")) - station) <= tolerance
        ]
        left_action = end_action(left_elements[-1], at_right=True) if left_elements else None
        right_action = end_action(right_elements[0], at_right=False) if right_elements else None

        eps = max(length * 1.0e-8, 1.0e-7)
        left_range = _range_at_station(
            ranges, max(0.0, station - eps), length_m=length
        )
        right_range = _range_at_station(
            ranges, min(length, station + eps), length_m=length
        )
        left_section = str(
            source.get("left_section")
            or (left_range or {}).get("section_id")
            or ""
        )
        right_section = str(
            source.get("right_section")
            or (right_range or {}).get("section_id")
            or ""
        )
        left_offset = _float(
            section_sources.get(left_section, {}).get(
                "centroid_offset_from_reference_mm"
            )
        )
        right_offset = _float(
            section_sources.get(right_section, {}).get(
                "centroid_offset_from_reference_mm"
            )
        )
        offset_jump = right_offset - left_offset
        n_values = [
            value["N"]
            for value in (left_action, right_action)
            if value is not None
        ]
        n_reference = sum(n_values) / len(n_values) if n_values else 0.0
        expected_axis_shift = abs(n_reference * offset_jump / 1000.0)

        node_id = nodes_by_station.get(round(station, 9))
        nodal = nodal_loads.get(int(node_id), (0.0, 0.0, 0.0)) if node_id is not None else (0.0, 0.0, 0.0)
        fx, fy, moment = (list(nodal) + [0.0, 0.0, 0.0])[:3]
        left_m = None if left_action is None else left_action["M"]
        right_m = None if right_action is None else right_action["M"]
        observed_jump = (
            None if left_m is None or right_m is None else right_m - left_m
        )

        interpretation: list[str] = []
        if abs(offset_jump) > 1.0e-9:
            interpretation.append("local-centroid axis shift")
        if abs(_float(moment)) > 1.0e-3:
            interpretation.append("equivalent tendon couple")
        if abs(_float(fy)) > 1.0e-3:
            interpretation.append("equivalent tendon vertical force")
        if "Column centerline" in source["event_types"]:
            interpretation.append("frame joint / column restraint")
        if not interpretation:
            interpretation.append("station reference only")

        rows.append(
            {
                "s (m)": station,
                "Event type": "; ".join(sorted(source["event_types"])),
                "Tendon roles": ", ".join(sorted(source["profile_roles"])),
                "Tendons": ", ".join(sorted(source["tendon_ids"])),
                "Column": ", ".join(sorted(source.get("columns", set()))),
                "Left region / section": " / ".join(
                    value
                    for value in (
                        str(source.get("left_region") or ""),
                        left_section,
                    )
                    if value
                ),
                "Right region / section": " / ".join(
                    value
                    for value in (
                        str(source.get("right_region") or ""),
                        right_section,
                    )
                    if value
                ),
                "Centroid offset jump Δy (mm; up +)": offset_jump,
                "N reference (kN; comp. +)": n_reference,
                "|N·Δy| axis-shift reference (kN-m)": expected_axis_shift,
                "M left local (kN-m; sagging +)": left_m,
                "M right local (kN-m; sagging +)": right_m,
                "Observed ΔM right-left (kN-m)": observed_jump,
                "Equivalent nodal Fx (kN)": _float(fx) / 1000.0,
                "Equivalent nodal Fy (kN; up +)": _float(fy) / 1000.0,
                "Equivalent nodal couple (kN-m; CCW +)": _float(moment) / 1.0e6,
                "Interpretation sources": "; ".join(interpretation),
            }
        )
    return rows


def run_crossbeam_linear_stage_response(
    *,
    model: Mapping[str, Any],
    profile_rows: Any,
    anchorage_station_rows: Any,
) -> dict[str, Any]:
    """Run B2A self-weight, prestress, and linear-superposition QA cases."""

    if not bool(model.get("ready")):
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "issues": list(model.get("issues") or ["Frame model is not ready."]),
            "cases": {},
        }
    prestress = prestress_equivalent_nodal_loads(
        model=model,
        profile_rows=profile_rows,
        anchorage_station_rows=anchorage_station_rows,
    )
    if not prestress.get("ready"):
        return {
            "status": "SOURCE BLOCKED",
            "ready": False,
            "issues": list(prestress.get("issues") or ["Prestress load source is not ready."]),
            "cases": {},
            "prestress_load_source": prestress,
        }

    nodes = list(model.get("nodes", []))
    elements = list(model.get("elements", []))
    fixed = list(model.get("fixed_node_ids", []))
    self_weight_uniform = dict(model.get("self_weight_uniform_N_per_mm", {}))
    prestress_nodal = dict(prestress.get("nodal_loads", {}))

    solutions: dict[str, dict[str, Any]] = {}
    for case_name, nodal, uniform in (
        (PTLOSS3B2A_SELF_WEIGHT_CASE, {}, self_weight_uniform),
        (PTLOSS3B2A_PRESTRESS_CASE, prestress_nodal, {}),
        (
            PTLOSS3B2A_COMBINED_CASE,
            _merge_nodal_loads({}, prestress_nodal),
            self_weight_uniform,
        ),
    ):
        solution = solve_linear_frame(
            nodes=nodes,
            elements=elements,
            nodal_loads=nodal,
            uniform_local_y_by_element=uniform,
            fixed_node_ids=fixed,
        )
        response_rows = _beam_response_rows(solution)
        solution["case"] = case_name
        solution["beam_response_rows"] = response_rows
        solution["column_action_rows"] = _column_action_rows(solution)
        if response_rows:
            solution["metrics"] = {
                "max_abs_N_kN": max(abs(_float(row.get("N compression-positive (kN)"))) for row in response_rows),
                "max_abs_V_kN": max(abs(_float(row.get("V (kN)"))) for row in response_rows),
                "max_abs_M_kNm": max(abs(_float(row.get("M sagging-positive (kN-m)"))) for row in response_rows),
                "max_abs_v_mm": max(abs(_float(row.get("v_up (mm)"))) for row in response_rows),
                "max_up_mm": max(_float(row.get("v_up (mm)")) for row in response_rows),
                "max_down_mm": min(_float(row.get("v_up (mm)")) for row in response_rows),
            }
        else:
            solution["metrics"] = {}
        solutions[case_name] = solution

    prestress_solution = solutions.get(PTLOSS3B2A_PRESTRESS_CASE, {})
    response_event_rows = linear_response_event_audit_rows(
        model=model,
        profile_rows=profile_rows,
        prestress_load_source=prestress,
        solution=prestress_solution,
    )

    issues = [
        f"{case_name}: {issue}"
        for case_name, solution in solutions.items()
        for issue in solution.get("issues", [])
    ]
    residuals = [
        _float(solution.get("equilibrium", {}).get("max_residual_ratio"), 1.0)
        for solution in solutions.values()
        if solution.get("equilibrium")
    ]
    max_residual = max(residuals, default=1.0)
    ready = not issues and all(solution.get("status") == "LINEAR QA READY" for solution in solutions.values())
    return {
        "status": "LINEAR QA READY" if ready else "REVIEW REQUIRED",
        "ready": ready,
        "method": PTLOSS3B2A_METHOD,
        "model": model,
        "prestress_load_source": prestress,
        "cases": solutions,
        "response_event_rows": response_event_rows,
        "max_equilibrium_residual_ratio": max_residual,
        "issues": _dedupe(issues),
        "fcgp_status": "LOCKED — CONTACT + STAGE STRESS EXTRACTION NOT RELEASED",
        "temporary_support_status": "EXCLUDED — CONTACT-AWARE SOLVER NOT RELEASED",
        "solver_boundary": (
            "This is a fixed-base gross-section linear response QA. It does not represent the final stressing stage while continuous compression-only falsework contact is active and therefore cannot feed f_cgp or Elastic Shortening."
        ),
    }



def linear_stage_stiffness_source_rows(model: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return grouped stage-stiffness sources for UI/report QA."""

    element_counts: dict[tuple[str, str], int] = {}
    for element in model.get("elements", []):
        kind = str(element.get("kind") or "")
        source_id = (
            str(element.get("region") or "")
            if kind == "beam"
            else str(element.get("column_id") or "")
        )
        element_counts[(kind, source_id)] = element_counts.get((kind, source_id), 0) + 1

    rows: list[dict[str, Any]] = []
    section_sources = dict(model.get("section_sources", {}))
    for region in model.get("ranges", []):
        section_id = str(region.get("section_id") or "")
        source = section_sources.get(section_id, {})
        e = _float(source.get("E_MPa"))
        area = _float(source.get("A_mm2"))
        inertia = _float(source.get("I_mm4"))
        rows.append(
            {
                "Member": "Crossbeam",
                "Region / Column": str(region.get("Region") or ""),
                "Section / Shape": section_id,
                "Strength source": (
                    f"f'ci={_float(source.get('fci_mpa')):.3f} MPa "
                    f"({_float(source.get('stressing_strength_ratio')):.3f} f'c)"
                ),
                "E used (MPa)": e,
                "A (mm²)": area,
                "I⊥s (mm⁴)": inertia,
                "EA (N)": e * area,
                "EI⊥s (N-mm²)": e * inertia,
                "Centroid from top (mm)": _float(source.get("centroid_from_top_mm")),
                "Rigid offset to reference (mm; up +)": _float(
                    source.get("centroid_offset_from_reference_mm")
                ),
                "Element count": element_counts.get(
                    ("beam", str(region.get("Region") or "")), 0
                ),
                "Source / axis": str(source.get("modulus_source") or ""),
            }
        )

    for column in model.get("column_sources", []):
        e = _float(column.get("E_MPa"))
        area = _float(column.get("A_mm2"))
        inertia = _float(column.get("I_mm4"))
        column_id = str(column.get("Column ID") or "")
        rows.append(
            {
                "Member": "Column",
                "Region / Column": column_id,
                "Section / Shape": str(column.get("Shape") or ""),
                "Strength source": f"column f'c={_float(column.get('fc_stage_mpa')):.3f} MPa",
                "E used (MPa)": e,
                "A (mm²)": area,
                "I⊥s (mm⁴)": inertia,
                "EA (N)": e * area,
                "EI⊥s (N-mm²)": e * inertia,
                "Centroid from top (mm)": None,
                "Rigid offset to reference (mm; up +)": 0.0,
                "Element count": element_counts.get(("column", column_id), 0),
                "Source / axis": (
                    str(column.get("modulus_source") or "")
                    + "; I⊥s = column I22 about axis normal to Crossbeam s"
                ),
            }
        )
    return rows


def _response_metrics(solution: Mapping[str, Any]) -> dict[str, float]:
    rows = _beam_response_rows(solution)
    if not rows:
        return {}
    return {
        "max_abs_N_kN": max(
            abs(_float(row.get("N compression-positive (kN)"))) for row in rows
        ),
        "max_abs_V_kN": max(abs(_float(row.get("V (kN)"))) for row in rows),
        "max_abs_M_kNm": max(
            abs(_float(row.get("M sagging-positive (kN-m)"))) for row in rows
        ),
        "max_abs_v_mm": max(abs(_float(row.get("v_up (mm)"))) for row in rows),
        "max_up_mm": max(_float(row.get("v_up (mm)")) for row in rows),
        "max_down_mm": min(_float(row.get("v_up (mm)")) for row in rows),
    }


def run_crossbeam_linear_mesh_sensitivity(
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
    concrete_materials: Any,
    column_rows: Any,
    profile_rows: Any,
    anchorage_station_rows: Any,
    crossbeam_stressing_strength_ratio: float = DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
    mesh_lengths_m: tuple[float, ...] = DEFAULT_MESH_SENSITIVITY_LENGTHS_M,
) -> dict[str, Any]:
    """Run prestress-only linear QA on progressively refined beam meshes."""

    rows: list[dict[str, Any]] = []
    previous: dict[str, float] | None = None
    issues: list[str] = []
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
        if not model.get("ready"):
            issues.extend(
                f"Mesh {target:.3f} m: {issue}" for issue in model.get("issues", [])
            )
            rows.append(
                {
                    "Target max element (m)": float(target),
                    "Beam elements": int(model.get("mesh", {}).get("beam_element_count") or 0),
                    "Status": "SOURCE BLOCKED",
                }
            )
            continue
        prestress = prestress_equivalent_nodal_loads(
            model=model,
            profile_rows=profile_rows,
            anchorage_station_rows=anchorage_station_rows,
        )
        if not prestress.get("ready"):
            issues.extend(
                f"Mesh {target:.3f} m: {issue}"
                for issue in prestress.get("issues", [])
            )
            rows.append(
                {
                    "Target max element (m)": float(target),
                    "Beam elements": int(model.get("mesh", {}).get("beam_element_count") or 0),
                    "Status": "SOURCE BLOCKED",
                }
            )
            continue
        solution = solve_linear_frame(
            nodes=list(model.get("nodes", [])),
            elements=list(model.get("elements", [])),
            nodal_loads=dict(prestress.get("nodal_loads", {})),
            fixed_node_ids=list(model.get("fixed_node_ids", [])),
        )
        metrics = _response_metrics(solution)
        row = {
            "Target max element (m)": float(target),
            "Beam elements": int(model.get("mesh", {}).get("beam_element_count") or 0),
            "Max |N| (kN)": metrics.get("max_abs_N_kN"),
            "Max |V| (kN)": metrics.get("max_abs_V_kN"),
            "Max |M| (kN-m)": metrics.get("max_abs_M_kNm"),
            "Max |v| (mm)": metrics.get("max_abs_v_mm"),
            "Equilibrium residual": _float(
                solution.get("equilibrium", {}).get("max_residual_ratio"), 1.0
            ),
            "Status": str(solution.get("status") or "REVIEW REQUIRED"),
        }
        if previous:
            for key, output_key in (
                ("max_abs_N_kN", "ΔN from coarser (%)"),
                ("max_abs_V_kN", "ΔV from coarser (%)"),
                ("max_abs_M_kNm", "ΔM from coarser (%)"),
                ("max_abs_v_mm", "Δv from coarser (%)"),
            ):
                current_value = _float(metrics.get(key))
                previous_value = _float(previous.get(key))
                scale = max(abs(current_value), abs(previous_value), 1.0e-12)
                row[output_key] = 100.0 * abs(current_value - previous_value) / scale
        rows.append(row)
        previous = metrics

    final_deltas = []
    if rows:
        last = rows[-1]
        final_deltas = [
            _float(last.get(key))
            for key in (
                "ΔN from coarser (%)",
                "ΔV from coarser (%)",
                "ΔM from coarser (%)",
                "Δv from coarser (%)",
            )
            if last.get(key) is not None
        ]
    max_delta = max(final_deltas, default=None)
    ready = not issues and len(rows) == len(mesh_lengths_m) and all(
        row.get("Status") == "LINEAR QA READY" for row in rows
    )
    return {
        "status": (
            "QA STABLE"
            if ready and max_delta is not None and max_delta <= 1.0
            else "MESH REVIEW"
            if ready
            else "SOURCE BLOCKED"
        ),
        "ready": ready,
        "rows": rows,
        "max_fine_mesh_delta_percent": max_delta,
        "issues": _dedupe(issues),
        "criterion": "Last refinement change <= 1.0% for N, V, M, and v (linear QA only)",
    }


def _manual_benchmark_model(
    *,
    stations_m: list[float],
    column_stations_m: tuple[float, float] | None = None,
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    node_by_station: dict[float, int] = {}
    for station in stations_m:
        node_id = len(nodes)
        nodes.append(
            {
                "id": node_id,
                "label": f"B@{station:.3f}",
                "kind": "beam",
                "station_m": station,
                "x_mm": station * 1000.0,
                "y_mm": 0.0,
            }
        )
        node_by_station[round(station, 9)] = node_id
    elements: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(stations_m, stations_m[1:]), start=1):
        elements.append(
            {
                "id": f"B{index}",
                "kind": "beam",
                "region": "Z1",
                "section_id": "S1",
                "node_i": node_by_station[round(left, 9)],
                "node_j": node_by_station[round(right, 9)],
                "station_i_m": left,
                "station_j_m": right,
                "E_MPa": 30_000.0,
                "A_mm2": 1.0e6,
                "I_mm4": 2.0e11,
                "offset_i_y_mm": 0.0,
                "offset_j_y_mm": 0.0,
            }
        )
    fixed: list[int] = []
    if column_stations_m:
        for index, station in enumerate(column_stations_m, start=1):
            base = len(nodes)
            nodes.append(
                {
                    "id": base,
                    "label": f"C{index} base",
                    "kind": "column_base",
                    "column_id": f"C{index}",
                    "station_m": station,
                    "x_mm": station * 1000.0,
                    "y_mm": -5_000.0,
                }
            )
            fixed.append(base)
            elements.append(
                {
                    "id": f"C{index}",
                    "kind": "column",
                    "column_id": f"C{index}",
                    "node_i": base,
                    "node_j": node_by_station[round(station, 9)],
                    "station_i_m": station,
                    "station_j_m": station,
                    "E_MPa": 30_000.0,
                    "A_mm2": 1.0e6,
                    "I_mm4": 2.0e11,
                }
            )
    return {
        "ready": True,
        "length_m": max(stations_m),
        "stations_m": stations_m,
        "nodes": nodes,
        "elements": elements,
        "fixed_node_ids": fixed,
        "beam_node_by_station": node_by_station,
        "ranges": [
            {
                "Region": "Z1",
                "start_m": 0.0,
                "end_m": max(stations_m),
                "section_id": "S1",
            }
        ],
        "section_sources": {
            "S1": {
                "centroid_from_top_mm": 750.0,
                "centroid_offset_from_reference_mm": 0.0,
            }
        },
        "reference_axis": {
            "reference_centroid_from_top_mm": 750.0,
            "method": "benchmark reference",
        },
    }


def _station_mean(rows: list[dict[str, Any]], field: str) -> dict[float, float]:
    values: dict[float, list[float]] = {}
    for row in rows:
        station = round(_float(row.get("s (m)")), 9)
        values.setdefault(station, []).append(_float(row.get(field)))
    return {
        station: sum(items) / len(items)
        for station, items in values.items()
        if items
    }


def ptloss3b2a1_benchmark_rows() -> list[dict[str, Any]]:
    """Return independent sign, P·e, and symmetry benchmarks."""

    rows: list[dict[str, Any]] = []
    force = [
        {
            "Tendon ID": "T1",
            "Active": True,
            "s (m)": station,
            "P after anchorage set (kN)": 1000.0,
        }
        for station in (0.0, 10.0)
    ]
    base_model = _manual_benchmark_model(stations_m=[0.0, 10.0])
    base_model["fixed_node_ids"] = [0]

    centroid_profile = [
        {"Tendon ID": "T1", "s (m)": 0.0, "dtop (mm)": 750.0},
        {"Tendon ID": "T1", "s (m)": 10.0, "dtop (mm)": 750.0},
    ]
    centroid_source = prestress_equivalent_nodal_loads(
        model=base_model,
        profile_rows=centroid_profile,
        anchorage_station_rows=force,
    )
    centroid_solution = solve_linear_frame(
        nodes=list(base_model["nodes"]),
        elements=list(base_model["elements"]),
        nodal_loads=dict(centroid_source.get("nodal_loads", {})),
        fixed_node_ids=[0],
    )
    centroid_metrics = _response_metrics(centroid_solution)
    centroid_residual = max(
        abs(_float(centroid_metrics.get("max_abs_M_kNm"))),
        abs(_float(centroid_metrics.get("max_abs_v_mm"))),
    )
    rows.append(
        {
            "Benchmark": "Straight tendon through centroid",
            "Expected": "N = P; M = 0; v = 0",
            "Observed": (
                f"N={_float(centroid_metrics.get('max_abs_N_kN')):.3f} kN; "
                f"|M|max={_float(centroid_metrics.get('max_abs_M_kNm')):.3e} kN-m; "
                f"|v|max={_float(centroid_metrics.get('max_abs_v_mm')):.3e} mm"
            ),
            "Residual": centroid_residual,
            "Status": "PASS" if centroid_residual <= 1.0e-8 else "REVIEW",
        }
    )

    below_profile = [
        {"Tendon ID": "T1", "s (m)": 0.0, "dtop (mm)": 950.0},
        {"Tendon ID": "T1", "s (m)": 10.0, "dtop (mm)": 950.0},
    ]
    below_source = prestress_equivalent_nodal_loads(
        model=base_model,
        profile_rows=below_profile,
        anchorage_station_rows=force,
    )
    below_solution = solve_linear_frame(
        nodes=list(base_model["nodes"]),
        elements=list(base_model["elements"]),
        nodal_loads=dict(below_source.get("nodal_loads", {})),
        fixed_node_ids=[0],
    )
    below_rows = _beam_response_rows(below_solution)
    observed_m = _station_mean(below_rows, "M sagging-positive (kN-m)")
    mean_m = sum(observed_m.values()) / max(len(observed_m), 1)
    expected_m = -200.0
    tip_v = _float(below_solution.get("nodes", [])[-1].get("v_mm"))
    residual = abs(mean_m - expected_m) / max(abs(expected_m), 1.0)
    rows.append(
        {
            "Benchmark": "Straight tendon 200 mm below centroid",
            "Expected": "Primary P·e = -200.000 kN-m (sagging +); cantilever tip v < 0",
            "Observed": f"mean M={mean_m:.3f} kN-m; tip v={tip_v:.6f} mm",
            "Residual": residual,
            "Status": "PASS" if residual <= 1.0e-9 and tip_v < 0.0 else "REVIEW",
        }
    )

    symmetric_model = _manual_benchmark_model(
        stations_m=[0.0, 2.0, 5.0, 8.0, 10.0],
        column_stations_m=(2.0, 8.0),
    )
    symmetric_profile = [
        {"Tendon ID": "T1", "s (m)": 0.0, "dtop (mm)": 750.0},
        {"Tendon ID": "T1", "s (m)": 5.0, "dtop (mm)": 1050.0},
        {"Tendon ID": "T1", "s (m)": 10.0, "dtop (mm)": 750.0},
    ]
    symmetric_force = [
        {
            "Tendon ID": "T1",
            "Active": True,
            "s (m)": station,
            "P after anchorage set (kN)": 1000.0,
        }
        for station in (0.0, 5.0, 10.0)
    ]
    symmetric_source = prestress_equivalent_nodal_loads(
        model=symmetric_model,
        profile_rows=symmetric_profile,
        anchorage_station_rows=symmetric_force,
    )
    symmetric_solution = solve_linear_frame(
        nodes=list(symmetric_model["nodes"]),
        elements=list(symmetric_model["elements"]),
        nodal_loads=dict(symmetric_source.get("nodal_loads", {})),
        fixed_node_ids=list(symmetric_model["fixed_node_ids"]),
    )
    response = _beam_response_rows(symmetric_solution)
    v_by_s = _station_mean(response, "v_up (mm)")
    m_by_s = _station_mean(response, "M sagging-positive (kN-m)")
    symmetry_errors: list[float] = []
    for station, value in v_by_s.items():
        mirror = round(10.0 - station, 9)
        if mirror in v_by_s:
            symmetry_errors.append(abs(value - v_by_s[mirror]))
    for station, value in m_by_s.items():
        mirror = round(10.0 - station, 9)
        if mirror in m_by_s:
            symmetry_errors.append(abs(value - m_by_s[mirror]))
    fixed_rows = [
        row for row in symmetric_solution.get("nodes", []) if bool(row.get("fixed"))
    ]
    if len(fixed_rows) == 2:
        left_reaction, right_reaction = fixed_rows
        symmetry_errors.extend(
            [
                abs(
                    _float(left_reaction.get("reaction_fx_N"))
                    + _float(right_reaction.get("reaction_fx_N"))
                )
                / 1000.0,
                abs(
                    _float(left_reaction.get("reaction_fy_N"))
                    - _float(right_reaction.get("reaction_fy_N"))
                )
                / 1000.0,
                abs(
                    _float(left_reaction.get("reaction_moment_Nmm"))
                    + _float(right_reaction.get("reaction_moment_Nmm"))
                )
                / 1.0e6,
            ]
        )
    scale = max(
        max((abs(value) for value in v_by_s.values()), default=0.0),
        max((abs(value) for value in m_by_s.values()), default=0.0),
        1.0,
    )
    symmetry_residual = max(symmetry_errors, default=0.0) / scale
    rows.append(
        {
            "Benchmark": "Symmetric parabolic tendon in symmetric portal",
            "Expected": "M(s)=M(L-s), v(s)=v(L-s), mirrored base reactions, equilibrium closed",
            "Observed": (
                f"symmetry residual={symmetry_residual:.3e}; "
                f"equilibrium={_float(symmetric_solution.get('equilibrium', {}).get('max_residual_ratio')):.3e}"
            ),
            "Residual": symmetry_residual,
            "Status": "PASS" if symmetry_residual <= 1.0e-9 else "REVIEW",
        }
    )
    return rows

def linear_stage_case_summary_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_name in PTLOSS3B2A_CASES:
        solution = result.get("cases", {}).get(case_name, {})
        equilibrium = solution.get("equilibrium", {})
        metrics = solution.get("metrics", {})
        rows.append(
            {
                "Load case": case_name,
                "Status": str(solution.get("status") or "NOT CALCULATED"),
                "Applied Fx (kN)": _float(equilibrium.get("applied_fx_N")) / 1000.0,
                "Applied Fy (kN)": _float(equilibrium.get("applied_fy_N")) / 1000.0,
                "Reaction Fx (kN)": _float(equilibrium.get("reaction_fx_N")) / 1000.0,
                "Reaction Fy (kN)": _float(equilibrium.get("reaction_fy_N")) / 1000.0,
                "Max |N| (kN)": _float(metrics.get("max_abs_N_kN")),
                "Max |V| (kN)": _float(metrics.get("max_abs_V_kN")),
                "Max |M| (kN-m)": _float(metrics.get("max_abs_M_kNm")),
                "Max |v| (mm)": _float(metrics.get("max_abs_v_mm")),
                "Equilibrium residual": _float(equilibrium.get("max_residual_ratio"), 1.0),
            }
        )
    return rows
