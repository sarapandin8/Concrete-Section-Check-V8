"""PTLOSS3B2A linear 2D stressing-stage Portal-Frame response foundation.

The module provides a small, auditable Euler-Bernoulli 2D frame kernel for the
Portal Frame Crossbeam in the longitudinal ``s``-vertical plane.  It is a
*linear QA foundation* only:

- Crossbeam and fixed-base columns are modeled with gross ``EA``/``EI``.
- Crossbeam self-weight and the accepted post-anchorage tendon force state are
  solved as separate linear load cases and as a superposed QA case.
- Tendon loads are assembled from the actual piecewise tendon profile and
  ``P after anchorage set``; no force is reconstructed from ``fpj``.
- Continuous temporary support/contact, lift-off iteration, final
  Primary/Secondary Prestress decomposition, source-derived ``f_cgp``, and the
  final Elastic Shortening handoff remain explicitly outside this milestone.

Internal units are mm, MPa, N, and N-mm.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import ceil, hypot, isfinite
from typing import Any

import numpy as np

from concrete_pmm_pro.crossbeam.construction_stage import (
    canonical_column_stage_rows,
    column_section_properties,
)
from concrete_pmm_pro.crossbeam.section_library import (
    canonical_section_definitions,
    section_property_records,
)
from concrete_pmm_pro.crossbeam.tendon import canonical_tendon_profile_points

PTLOSS3B2A_METHOD = "LINEAR 2D s-VERTICAL PORTAL-FRAME QA"
PTLOSS3B2A_SELF_WEIGHT_CASE = "SELF-WEIGHT — PORTAL FRAME ONLY"
PTLOSS3B2A_PRESTRESS_CASE = "PRESTRESS AFTER ANCHORAGE SET"
PTLOSS3B2A_COMBINED_CASE = "LINEAR SUPERPOSITION QA"
PTLOSS3B2A_CASES = (
    PTLOSS3B2A_SELF_WEIGHT_CASE,
    PTLOSS3B2A_PRESTRESS_CASE,
    PTLOSS3B2A_COMBINED_CASE,
)

DEFAULT_MAX_BEAM_ELEMENT_LENGTH_M = 0.50
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
        }
    name = str(getattr(value, "name", "") or "").strip()
    fc = _float(getattr(value, "fc_MPa", getattr(value, "fc_mpa", 0.0)))
    density = _float(getattr(value, "density_kg_m3", 2400.0), 2400.0)
    ec = _float(getattr(value, "effective_Ec_MPa", 0.0))
    if ec <= 0.0 and fc > 0.0:
        ec = 4700.0 * fc**0.5
    return {
        "name": name,
        "fc_mpa": fc,
        "density_kg_m3": density,
        "ec_mpa": ec,
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
        k_global = transform.T @ k_local @ transform
        dofs = _element_dofs(element)
        stiffness[np.ix_(dofs, dofs)] += k_global

        q_local_y = _float((uniform_local_y_by_element or {}).get(element_id), 0.0)
        f_local = frame_uniform_local_y_load(q_n_per_mm=q_local_y, length_mm=length)
        f_global = transform.T @ f_local
        load[dofs] += f_global
        element_cache[element_id] = {
            "length_mm": length,
            "c": c,
            "s": s,
            "k_local": k_local,
            "transform": transform,
            "f_local": f_local,
            "dofs": dofs,
            "q_local_y": q_local_y,
        }

    if issues:
        return {"status": "SOURCE BLOCKED", "issues": _dedupe(issues)}

    restrained: list[int] = []
    for node_id in fixed_node_ids or []:
        restrained.extend([3 * int(node_id), 3 * int(node_id) + 1, 3 * int(node_id) + 2])
    restrained = sorted(set(restrained))
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
        d_local = cache["transform"] @ d_global
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
    for node in nodes:
        node_id = int(node["id"])
        base = 3 * node_id
        node_rows.append(
            {
                **node,
                "u_mm": displacement[base],
                "v_mm": displacement[base + 1],
                "theta_rad": displacement[base + 2],
                "applied_fx_N": load[base],
                "applied_fy_N": load[base + 1],
                "applied_moment_Nmm": load[base + 2],
                "reaction_fx_N": reaction[base] if node_id in fixed_set else 0.0,
                "reaction_fy_N": reaction[base + 1] if node_id in fixed_set else 0.0,
                "reaction_moment_Nmm": reaction[base + 2] if node_id in fixed_set else 0.0,
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
    max_beam_element_length_m: float = DEFAULT_MAX_BEAM_ELEMENT_LENGTH_M,
) -> dict[str, Any]:
    """Resolve a piecewise-gross Crossbeam + fixed-base column frame model."""

    length = max(_float(length_m), 0.0)
    issues: list[str] = []
    notes: list[str] = []
    if length <= 0.0:
        issues.append("Crossbeam length must be positive.")

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
        ctop = _float(prop.get("Centroid from top mm"))
        height = _float(definition.get("Parameters", {}).get("height_mm"))
        section_sources[section_id] = {
            "Section ID": section_id,
            "Material": material_name,
            "E_MPa": material["ec_mpa"],
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
    if len(columns) < 2:
        issues.append("At least two columns are required for the Portal-Frame QA model.")
    column_sources: list[dict[str, Any]] = []
    seen_stations: set[float] = set()
    for row in columns:
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
                "E_MPa": _float(props.get("Ec (MPa)")),
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
    if ctop_values and max(ctop_values) - min(ctop_values) > 1.0:
        notes.append(
            "Multiple section centroid-from-top values exist. PTLOSS3B2A uses a straight idealized beam reference axis and local section eccentricity; exact centroidal rigid offsets remain future solver scope."
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
        "self_weight_uniform_N_per_mm": self_weight_uniform,
        "issues": issues,
        "notes": _dedupe(notes),
        "solver_boundary": (
            "Fixed-base gross-section linear frame only; continuous temporary-support contact/lift-off is excluded, so this model does not release stressing-stage f_cgp or final Elastic Shortening."
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
            eccentricity = _float(section.get("centroid_from_top_mm")) - dtop
            tendon_values.append(
                {
                    "station_m": station,
                    "dtop_mm": dtop,
                    "force_N": force_kn * 1000.0,
                    "eccentricity_mm": eccentricity,
                }
            )
        if not tendon_values:
            continue

        for index, (left, right) in enumerate(zip(tendon_values, tendon_values[1:]), start=1):
            dx = (right["station_m"] - left["station_m"]) * 1000.0
            dy = right["eccentricity_mm"] - left["eccentricity_mm"]
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
                    -left["eccentricity_mm"] * left["force_N"] * ux,
                ],
                dtype=float,
            )
            force_j = np.array(
                [
                    -right["force_N"] * ux,
                    -right["force_N"] * uy,
                    right["eccentricity_mm"] * right["force_N"] * ux,
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
                    "e_i (mm)": left["eccentricity_mm"],
                    "e_j (mm)": right["eccentricity_mm"],
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
    return {
        "status": "LOAD SOURCE READY" if tendon_count > 0 and not issues else "SOURCE BLOCKED",
        "ready": tendon_count > 0 and not issues,
        "tendon_count": tendon_count,
        "nodal_loads": nodal_output,
        "audit_rows": audit_rows,
        "issues": issues,
        "source": "Accepted P after Anchorage Set + adopted tendon profile",
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
        "max_equilibrium_residual_ratio": max_residual,
        "issues": _dedupe(issues),
        "fcgp_status": "LOCKED — CONTACT + STAGE STRESS EXTRACTION NOT RELEASED",
        "temporary_support_status": "EXCLUDED — PTLOSS3B2B CONTACT MILESTONE",
        "solver_boundary": (
            "PTLOSS3B2A is a fixed-base gross-section linear response QA. It does not represent the final stressing stage while continuous compression-only falsework contact is active and therefore cannot feed f_cgp or Elastic Shortening."
        ),
    }


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
