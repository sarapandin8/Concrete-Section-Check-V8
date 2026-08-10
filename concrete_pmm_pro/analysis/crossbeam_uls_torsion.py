"""Station-specific ACI 318-19 ULS torsion checks for Portal Frame Crossbeams.

``CROSSBEAM.ANALYSIS3`` reuses the accepted Crossbeam ULS station-source and
support-station contract from ``crossbeam_uls_shear``.  It evaluates imported
row-coupled ``T`` once, generates conservative Column Face and prestressed
``h/2`` checks, omits support-footprint interiors, and keeps exact Precast
physical segment joints as separate torsional-transfer review locations.

The implemented ACI 318-19 route includes:

* 22.7.1 and 22.7.4 threshold torsion ``phi*Tth`` for solid and hollow
  prestressed sections.
* 22.7.6 transverse and longitudinal space-truss torsional strength.
* 22.7.6.1.1 ``Ao = 0.85 Aoh`` and 22.7.6.1.2 prestress-dependent ``theta``.
* 22.7.7 combined shear/torsion cross-sectional stress limit.
* 9.6.4 minimum transverse and longitudinal torsional reinforcement.
* 9.7.5 longitudinal perimeter spacing/diameter/corner-coverage review.
* 9.7.6.3 closed-cage and transverse spacing/detailing checks.
* Table 21.2.1 torsion strength-reduction factor ``phi = 0.75``.

This milestone is the standalone torsion station check.  The additive
``Av/s + 2At/s`` design and the flexure-plus-longitudinal-torsion adoption are
reported here as source/detailing gates but remain the owner of the later
Combined Shear + Torsion milestone.  PT anchorage/end-zone design, physical
segment-joint torsion transfer, development/anchorage, fatigue, seismic
requirements, and warping torsion remain separate.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
import hashlib
import json
import math
from typing import Any

from shapely.geometry import LineString, Point, Polygon

from concrete_pmm_pro.analysis.crossbeam_uls_shear import (
    CrossbeamShearPreparation,
    PreparedCrossbeamShearRow,
    _governing_direction,
    build_crossbeam_uls_shear_preparation,
)
from concrete_pmm_pro.core.models import Rebar
from concrete_pmm_pro.crossbeam.transverse import (
    transverse_bar_area_mm2,
    transverse_torsion_cage_record,
    transverse_unique_steel_record,
)
from concrete_pmm_pro.geometry.summary import to_shapely_polygon


CROSSBEAM_ULS_TORSION_RESULT_KEY = "crossbeam_analysis3_uls_torsion_result"
CROSSBEAM_ULS_TORSION_RESULT_HASH_KEY = "crossbeam_analysis3_uls_torsion_input_hash"

_ACI_TORSION_PHI = 0.75
_ACI_NORMALWEIGHT_LAMBDA = 1.0
_ACI_TORSION_SQRT_FC_LIMIT = 8.3
_ACI_TORSION_FY_MAX_MPA = 420.0


@dataclass(frozen=True)
class CrossbeamTorsionPreparation:
    ready: bool
    rows: tuple[PreparedCrossbeamShearRow, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    info: tuple[str, ...]
    fingerprint: str
    demand_rows: tuple[dict[str, Any], ...]
    derived_support_rows: tuple[dict[str, Any], ...]
    support_footprints: tuple[dict[str, Any], ...]
    member_length_m: float
    excluded_end_zone_rows: tuple[dict[str, Any], ...] = ()
    pt_end_zone_settings: Mapping[str, Any] | None = None


def _finite(value: Any, default: float = float("nan")) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _dedupe(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(str(message).strip() for message in messages if str(message).strip()))


def _fingerprint(payload: Any) -> str:
    def _hashable(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, bool)):
            return value
        if isinstance(value, float):
            return round(value, 9) if math.isfinite(value) else str(value)
        if isinstance(value, Mapping):
            return {str(key): _hashable(value[key]) for key in sorted(value, key=str)}
        if isinstance(value, (list, tuple)):
            return [_hashable(item) for item in value]
        if hasattr(value, "model_dump"):
            return _hashable(value.model_dump(mode="json"))
        return repr(value)

    text = json.dumps(_hashable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_crossbeam_uls_torsion_preparation(state: Any) -> CrossbeamTorsionPreparation:
    """Build the Crossbeam torsion source contract from the accepted shear adapter.

    Shear and torsion intentionally share row-coupled station demands, exact /
    one-sided support recovery, Section/Rebar/Tendon ownership, and physical
    segment-joint semantics.  Torsion receives its own fingerprint and result
    cache so selecting or calculating one ULS check cannot mutate the other.
    """

    shear: CrossbeamShearPreparation = build_crossbeam_uls_shear_preparation(state)
    errors = [
        str(message)
        .replace("ULS Shear", "ULS Torsion")
        .replace("for Shear", "for Torsion")
        .replace("shear route", "torsion route")
        for message in shear.errors
    ]
    warnings = [
        str(message)
        .replace("ULS Shear", "ULS Torsion")
        .replace("for Shear", "for Torsion")
        for message in shear.warnings
    ]
    payload = {
        "schema": "crossbeam-analysis3-torsion-preparation-v1",
        "shared_station_fingerprint": shear.fingerprint,
        "rows": [row.source_signature for row in shear.rows],
        "formula_route": "ACI318-19-22.7-standalone-torsion-v2",
    }
    return CrossbeamTorsionPreparation(
        ready=bool(shear.ready),
        rows=tuple(shear.rows),
        errors=tuple(_dedupe(errors)),
        warnings=tuple(_dedupe(warnings)),
        info=tuple(shear.info),
        fingerprint=_fingerprint(payload),
        demand_rows=tuple(shear.demand_rows),
        derived_support_rows=tuple(shear.derived_support_rows),
        support_footprints=tuple(shear.support_footprints),
        member_length_m=float(shear.member_length_m),
        excluded_end_zone_rows=tuple(shear.excluded_end_zone_rows),
        pt_end_zone_settings=dict(shear.pt_end_zone_settings or {}),
    )


def _outer_metrics(row: PreparedCrossbeamShearRow) -> dict[str, Any]:
    concrete_polygon = to_shapely_polygon(row.geometry)
    outer_polygon = Polygon([(float(point.x), float(point.y)) for point in row.geometry.outer_polygon])
    if not concrete_polygon.is_valid or concrete_polygon.is_empty or concrete_polygon.area <= 0.0:
        raise ValueError("generated concrete polygon is invalid for torsion geometry")
    if not outer_polygon.is_valid or outer_polygon.is_empty or outer_polygon.area <= 0.0:
        raise ValueError("outside concrete perimeter is invalid for torsion geometry")
    return {
        "Ag_mm2": float(concrete_polygon.area),
        "Acp_mm2": float(outer_polygon.area),
        "pcp_mm": float(outer_polygon.exterior.length),
        "is_hollow": bool(row.geometry.holes),
        "concrete_polygon": concrete_polygon,
        "outer_polygon": outer_polygon,
    }


def _equivalent_hoop_geometry(row: PreparedCrossbeamShearRow) -> dict[str, Any]:
    template = row.transverse_template
    if not isinstance(template, Mapping):
        return {
            "ready": False,
            "errors": ["No active transverse template is assigned at this station."],
        }
    if not bool(template.get("Credit inside segment", True)):
        return {
            "ready": False,
            "errors": ["Assigned transverse template is detailing-only and receives no sectional torsion credit."],
        }
    cage_source = transverse_torsion_cage_record(template)
    if not bool(cage_source.get("Adopted")):
        return {
            "ready": False,
            "errors": [
                "Outer torsion-cage source is not ready: "
                + str(cage_source.get("Note") or cage_source.get("Status") or "LAYOUT REQUIRED")
            ],
            "source_status": str(cage_source.get("Status") or "LAYOUT REQUIRED"),
        }

    metrics = _outer_metrics(row)
    outer_polygon: Polygon = metrics["outer_polygon"]
    concrete_polygon = metrics["concrete_polygon"]
    offset = _finite(cage_source.get("Center offset mm"), 0.0)
    bar_size = str(cage_source.get("Bar") or "")
    spacing = _finite(cage_source.get("Spacing mm"), 0.0)
    fyt_input = _finite(template.get("fy MPa"), 0.0)
    if offset <= 0.0 or spacing <= 0.0 or fyt_input <= 0.0:
        return {
            "ready": False,
            "errors": ["User-defined torsion-cage center offset, spacing, and fyt must be positive."],
        }

    inset = outer_polygon.buffer(-offset, join_style=2)
    if inset.is_empty:
        return {
            "ready": False,
            "errors": ["User-defined outer torsion cage is empty at the assigned center offset."],
        }
    if hasattr(inset, "geoms"):
        inset = max(inset.geoms, key=lambda geometry: float(geometry.area))
    if not isinstance(inset, Polygon) or not inset.is_valid or inset.area <= 0.0:
        return {
            "ready": False,
            "errors": ["User-defined outer torsion-cage geometry is invalid."],
        }
    hoop_line = LineString(inset.exterior.coords)
    bar_area = transverse_bar_area_mm2(bar_size)
    bar_diameter = math.sqrt(4.0 * bar_area / math.pi)
    steel_envelope = hoop_line.buffer(0.5 * bar_diameter, cap_style=1, join_style=1)
    errors: list[str] = []
    warnings: list[str] = []
    if not concrete_polygon.buffer(1.0e-7).covers(steel_envelope):
        errors.append("User-defined outer closed-cage bar envelope leaves the concrete or enters the section void.")

    aoh = float(inset.area)
    ph = float(inset.exterior.length)
    ao = 0.85 * aoh
    hollow_wall_clearance = float("nan")
    hollow_clearance_required = float("nan")
    hollow_clearance_dc = float("nan")
    if bool(metrics["is_hollow"]):
        hole_polygons = [Polygon([(float(point.x), float(point.y)) for point in hole]) for hole in row.geometry.holes]
        valid_holes = [hole for hole in hole_polygons if hole.is_valid and not hole.is_empty]
        if valid_holes:
            hollow_wall_clearance = min(float(hoop_line.distance(hole.exterior)) for hole in valid_holes)
            hollow_clearance_required = 0.5 * aoh / ph if ph > 0.0 else float("nan")
            if math.isfinite(hollow_clearance_required) and hollow_clearance_required > 0.0:
                hollow_clearance_dc = hollow_clearance_required / max(hollow_wall_clearance, 1.0e-12)
                if hollow_clearance_dc > 1.0 + 1.0e-9:
                    errors.append(
                        "Hollow-section torsion cage is too close to the inside face for ACI 9.7.6.3.4."
                    )
        else:
            warnings.append("Hollow-section inside-face clearance could not be verified from the active void geometry.")

    cage_continuity_review = False
    warnings.append(
        "Aoh and ph are evaluated from the engineer-defined outer closed torsion-cage centerline. "
        "Development, anchorage, lap/closure detailing, and physical-joint transfer remain separate checks."
    )

    return {
        "ready": not errors,
        "errors": errors,
        "warnings": warnings,
        "cage_continuity_review": cage_continuity_review,
        "Ag_mm2": metrics["Ag_mm2"],
        "Acp_mm2": metrics["Acp_mm2"],
        "pcp_mm": metrics["pcp_mm"],
        "is_hollow": metrics["is_hollow"],
        "Aoh_mm2": aoh,
        "Ao_mm2": ao,
        "ph_mm": ph,
        "offset_mm": offset,
        "At_mm2": bar_area,
        "spacing_mm": spacing,
        "fyt_input_mpa": fyt_input,
        "fyt_design_mpa": min(fyt_input, _ACI_TORSION_FY_MAX_MPA),
        "bar_size": bar_size,
        "bar_diameter_mm": bar_diameter,
        "cage_source_status": str(cage_source.get("Status") or ""),
        "cage_relationship": str(cage_source.get("Relationship") or ""),
        "cage_closure": str(cage_source.get("Closure") or ""),
        "hollow_clearance_mm": hollow_wall_clearance,
        "hollow_clearance_required_mm": hollow_clearance_required,
        "hollow_clearance_dc": hollow_clearance_dc,
        "cage_polygon": inset,
        "cage_line": hoop_line,
        "bt_mm": float(inset.bounds[2] - inset.bounds[0]),
    }


def _rebar_fy(row: PreparedCrossbeamShearRow, bar: Rebar) -> float | None:
    material_name = str(bar.material_name)
    for material in row.rebar_materials:
        if str(material.name) == material_name:
            return min(float(material.fy_MPa), _ACI_TORSION_FY_MAX_MPA)
    return None


def _outer_longitudinal_review(
    row: PreparedCrossbeamShearRow,
    *,
    spacing_transverse_mm: float,
    al_required_mm2: float,
    cage_polygon: Polygon,
    cage_line: LineString,
) -> dict[str, Any]:
    outer_bars = [bar for bar in row.rebars if str(bar.label or "").startswith("Outer:")]
    if not outer_bars:
        return {
            "status": "LAYOUT REQUIRED",
            "provided_mm2": 0.0,
            "capacity_N": 0.0,
            "area_dc": float("inf") if al_required_mm2 > 0.0 else 0.0,
            "max_perimeter_spacing_mm": float("nan"),
            "spacing_dc": float("inf"),
            "diameter_dc": float("inf"),
            "corner_coverage": 0,
            "notes": "No active Outer longitudinal bars are available for torsion Al credit.",
        }

    fy_values: list[float] = []
    capacity_n = 0.0
    provided_area = 0.0
    min_diameter = float("inf")
    for bar in outer_bars:
        fy = _rebar_fy(row, bar)
        if fy is None:
            continue
        area = float(bar.area_mm2)
        provided_area += area
        capacity_n += area * fy
        fy_values.append(fy)
        min_diameter = min(min_diameter, float(bar.diameter_mm))
    if provided_area <= 0.0 or capacity_n <= 0.0:
        return {
            "status": "LAYOUT REQUIRED",
            "provided_mm2": provided_area,
            "capacity_N": capacity_n,
            "area_dc": float("inf"),
            "max_perimeter_spacing_mm": float("nan"),
            "spacing_dc": float("inf"),
            "diameter_dc": float("inf"),
            "corner_coverage": 0,
            "notes": "Outer longitudinal bars do not have a valid rebar-material source.",
        }

    perimeter = cage_line
    outside_cage = [
        bar for bar in outer_bars
        if not cage_polygon.buffer(1.0e-7).covers(Point(float(bar.x_mm), float(bar.y_mm)))
    ]
    projected = sorted(float(perimeter.project(Point(float(bar.x_mm), float(bar.y_mm)))) for bar in outer_bars)
    perimeter_length = float(perimeter.length)
    gaps: list[float] = []
    if len(projected) >= 2 and perimeter_length > 0.0:
        gaps.extend(projected[index + 1] - projected[index] for index in range(len(projected) - 1))
        gaps.append(perimeter_length - projected[-1] + projected[0])
    max_spacing = max(gaps) if gaps else float("inf")
    spacing_dc = max_spacing / 300.0 if math.isfinite(max_spacing) else float("inf")

    min_x, min_y, max_x, max_y = cage_polygon.bounds
    cx = 0.5 * (min_x + max_x)
    cy = 0.5 * (min_y + max_y)
    quadrants = {
        (float(bar.x_mm) >= cx, float(bar.y_mm) >= cy)
        for bar in outer_bars
    }
    corner_coverage = len(quadrants)
    diameter_required = max(0.042 * spacing_transverse_mm, 10.0)
    diameter_dc = diameter_required / max(min_diameter, 1.0e-12)
    area_dc = al_required_mm2 / provided_area if provided_area > 0.0 else float("inf")
    association_dc = float("inf") if outside_cage else 0.0
    status = "PASS" if max(area_dc, spacing_dc, diameter_dc, 4.0 / max(corner_coverage, 1), association_dc) <= 1.0 + 1.0e-9 else "FAIL"
    notes = (
        f"Al credit uses {len(outer_bars)} active Outer longitudinal bar(s) associated with the verified cage; "
        f"max spacing measured along the actual cage perimeter = {max_spacing:.1f} mm, "
        f"quadrant/corner coverage = {corner_coverage}/4, and outside-cage bar centers = {len(outside_cage)}."
    )
    return {
        "status": status,
        "provided_mm2": provided_area,
        "capacity_N": capacity_n,
        "area_dc": area_dc,
        "max_perimeter_spacing_mm": max_spacing,
        "spacing_dc": spacing_dc,
        "diameter_required_mm": diameter_required,
        "min_diameter_mm": min_diameter,
        "diameter_dc": diameter_dc,
        "corner_coverage": corner_coverage,
        "outside_cage_count": len(outside_cage),
        "association_dc": association_dc,
        "fy_min_mpa": min(fy_values),
        "notes": notes,
    }


def _prestress_terms(row: PreparedCrossbeamShearRow) -> dict[str, float]:
    aps_fse = sum(group.area_mm2 * group.fse_mpa for group in row.prestress_groups)
    aps_fpu = sum(group.area_mm2 * group.fpu_mpa for group in row.prestress_groups)
    aps = sum(group.area_mm2 for group in row.prestress_groups)
    as_fy = 0.0
    as_area = 0.0
    for bar in row.rebars:
        fy = _rebar_fy(row, bar)
        if fy is None:
            continue
        as_area += float(bar.area_mm2)
        as_fy += float(bar.area_mm2) * fy
    denominator = aps_fpu + as_fy
    ratio = aps_fse / denominator if denominator > 0.0 else float("nan")
    return {
        "Aps_mm2": aps,
        "Aps_fse_N": aps_fse,
        "Aps_fpu_N": aps_fpu,
        "As_mm2": as_area,
        "As_fy_N": as_fy,
        "prestress_ratio": ratio,
    }


def _torsion_thresholds(
    *,
    fc_mpa: float,
    ag_mm2: float,
    acp_mm2: float,
    pcp_mm: float,
    fpc_mpa: float,
    is_hollow: bool,
) -> dict[str, float]:
    sqrt_fc_actual = math.sqrt(fc_mpa)
    sqrt_fc_used = min(sqrt_fc_actual, _ACI_TORSION_SQRT_FC_LIMIT)
    prestress_factor = math.sqrt(max(1.0 + fpc_mpa / (0.33 * _ACI_NORMALWEIGHT_LAMBDA * sqrt_fc_used), 0.0))
    threshold_area = ag_mm2 if is_hollow else acp_mm2
    tth_nmm = (
        0.083
        * _ACI_NORMALWEIGHT_LAMBDA
        * sqrt_fc_used
        * threshold_area
        * threshold_area
        / pcp_mm
        * prestress_factor
    )
    tcr_nmm = (
        0.33
        * _ACI_NORMALWEIGHT_LAMBDA
        * sqrt_fc_used
        * acp_mm2
        * acp_mm2
        / pcp_mm
        * prestress_factor
    )
    return {
        "sqrt_fc_actual": sqrt_fc_actual,
        "sqrt_fc_used": sqrt_fc_used,
        "prestress_factor": prestress_factor,
        "Tth_Nmm": tth_nmm,
        "phiTth_Nmm": _ACI_TORSION_PHI * tth_nmm,
        "Tcr_Nmm": tcr_nmm,
        "phiTcr_Nmm": _ACI_TORSION_PHI * tcr_nmm,
    }


def _minimum_transverse_per_s(*, fc_mpa: float, bw_mm: float, fyt_mpa: float) -> float:
    return max(0.062 * math.sqrt(fc_mpa) * bw_mm / fyt_mpa, 0.35 * bw_mm / fyt_mpa)


def _minimum_longitudinal_area(
    *,
    fc_mpa: float,
    acp_mm2: float,
    fy_mpa: float,
    at_per_s: float,
    ph_mm: float,
    bw_mm: float,
    fyt_mpa: float,
) -> tuple[float, float, float]:
    first = 0.42 * math.sqrt(fc_mpa) * acp_mm2 / fy_mpa - at_per_s * ph_mm * fyt_mpa / fy_mpa
    second = (
        0.42 * math.sqrt(fc_mpa) * acp_mm2 / fy_mpa
        - (0.175 * bw_mm / fyt_mpa) * ph_mm * fyt_mpa / fy_mpa
    )
    return max(min(first, second), 0.0), first, second


def _physical_joint_result(row: PreparedCrossbeamShearRow) -> dict[str, Any]:
    return {
        "Check": "Torsion",
        "Status": "REVIEW",
        "Strength status": "NOT CHECKED",
        "Threshold status": "NOT CHECKED",
        "Transverse status": "NOT CHECKED",
        "Longitudinal status": "NOT CHECKED",
        "Detailing status": "NOT CHECKED",
        "Section limit status": "NOT CHECKED",
        "Station s (m)": row.station_m,
        "Check Point": row.check_point,
        "Case": row.case_name,
        "Location type": "PHYSICAL SEGMENT JOINT",
        "Section ID": row.section_id,
        "Rebar Zone": "Not applicable at physical joint",
        "Transverse Template": "No joint-torsion credit",
        "P kN": row.source_p_kn,
        "V2 kN": row.source_v2_kn,
        "T kN-m": row.source_t_knm,
        "M3 kN-m": row.source_m3_knm,
        "Demand source": row.demand_source,
        "Generated support check": row.generated_support_check,
        "Requested location type": row.requested_location_type,
        "Generated joint side check": row.generated_joint_side_check,
        "Joint side": row.joint_side,
        "Joint station s (m)": row.joint_station_m,
        "Source station 1 (m)": row.source_station_1_m,
        "Source station 2 (m)": row.source_station_2_m,
        "Source ratio": row.source_ratio,
        "Extrapolation ratio": row.extrapolation_ratio,
        "Demand kN-m": row.source_t_knm,
        "Abs demand kN-m": abs(row.source_t_knm),
        "phiTn kN-m": float("nan"),
        "phiTth kN-m": float("nan"),
        "Strength D/C value": float("nan"),
        "Governing D/C value": float("nan"),
        "Method": "Physical-joint torsion-transfer scope guard",
        "Notes": (
            "Physical segment-joint torsional transfer, joint compression/friction, shear keys, local reinforcement, "
            "and tendon continuity require a separate project check. This row cannot produce PASS in the sectional torsion module."
        ),
    }


def _base_result_fields(row: PreparedCrossbeamShearRow) -> dict[str, Any]:
    return {
        "Check": "Torsion",
        "Station s (m)": row.station_m,
        "Check Point": row.check_point,
        "Case": row.case_name,
        "Location type": row.location_type,
        "Section face": row.section_face,
        "Segment": row.segment_id,
        "Section ID": row.section_id,
        "Rebar Zone": row.rebar_zone_id,
        "Transverse Template": row.transverse_template_id,
        "P kN": row.source_p_kn,
        "V2 kN": row.source_v2_kn,
        "T kN-m": row.source_t_knm,
        "M3 kN-m": row.source_m3_knm,
        "Demand source": row.demand_source,
        "Generated support check": row.generated_support_check,
        "Requested location type": row.requested_location_type,
        "Generated joint side check": row.generated_joint_side_check,
        "Joint side": row.joint_side,
        "Joint station s (m)": row.joint_station_m,
        "Source station 1 (m)": row.source_station_1_m,
        "Source station 2 (m)": row.source_station_2_m,
        "Source ratio": row.source_ratio,
        "Extrapolation ratio": row.extrapolation_ratio,
        "Demand kN-m": row.source_t_knm,
        "Abs demand kN-m": abs(row.source_t_knm),
        "Effective prestress mode": (
            "UNIFORM_AVERAGE_OVERRIDE"
            if any(
                group.effective_prestress_mode == "UNIFORM_AVERAGE_OVERRIDE"
                for group in row.prestress_groups
            )
            else "STATION_DEPENDENT"
        ),
        "Local fse min MPa": min((group.fse_mpa for group in row.prestress_groups), default=float("nan")),
        "Local fse max MPa": max((group.fse_mpa for group in row.prestress_groups), default=float("nan")),
        "Local fse source": "; ".join(
            f"{group.tendon_id}: {group.fse_mpa:.3f} MPa"
            for group in row.prestress_groups
        ),
    }


def _hollow_wall_thickness_mm(row: PreparedCrossbeamShearRow) -> float:
    parameters = dict(row.definition.get("Parameters") or {})
    values = [
        _finite(parameters.get("t_top_mm")),
        _finite(parameters.get("t_bottom_mm")),
        _finite(parameters.get("t_left_mm")),
        _finite(parameters.get("t_right_mm")),
    ]
    positive = [value for value in values if math.isfinite(value) and value > 0.0]
    return min(positive) if positive else float("nan")


def _threshold_context(row: PreparedCrossbeamShearRow) -> dict[str, Any]:
    metrics = _outer_metrics(row)
    ag = float(metrics["Ag_mm2"])
    acp = float(metrics["Acp_mm2"])
    pcp = float(metrics["pcp_mm"])
    fc = float(row.concrete.fc_MPa)
    prestress = _prestress_terms(row)
    fpc = float(prestress["Aps_fse_N"]) / ag if ag > 0.0 else 0.0
    # ACI R22.7.4 permits small longitudinal voids with Ag/Acp >= 0.95 to be
    # ignored for the threshold screen.  The actual hollow geometry is still
    # retained for strength/detailing and the 22.7.7 section-size check.
    ag_acp_ratio = ag / acp if acp > 0.0 else float("nan")
    hollow_for_threshold = bool(metrics["is_hollow"]) and not (
        math.isfinite(ag_acp_ratio) and ag_acp_ratio >= 0.95 - 1.0e-12
    )
    thresholds = _torsion_thresholds(
        fc_mpa=fc,
        ag_mm2=ag,
        acp_mm2=acp,
        pcp_mm=pcp,
        fpc_mpa=fpc,
        is_hollow=hollow_for_threshold,
    )
    return {
        **metrics,
        **prestress,
        **thresholds,
        "fc_mpa": fc,
        "fpc_mpa": fpc,
        "Ag/Acp": ag_acp_ratio,
        "hollow_for_threshold": hollow_for_threshold,
    }


def _below_threshold_result(
    row: PreparedCrossbeamShearRow,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    tu_nmm = abs(float(row.source_t_knm)) * 1.0e6
    phi_tth = float(context["phiTth_Nmm"])
    threshold_dc = tu_nmm / phi_tth if phi_tth > 0.0 else float("nan")
    informational_phi_tn = float("nan")
    informational_tn_transverse = float("nan")
    informational_tn_longitudinal = float("nan")
    try:
        probe_demand_knm = max(phi_tth / 1.0e6 * 1.01, abs(float(row.source_t_knm)), 1.0e-6)
        probe_result = _torsion_result_for_row(replace(row, source_t_knm=probe_demand_knm))
        informational_phi_tn = _finite(probe_result.get("phiTn kN-m"), float("nan"))
        informational_tn_transverse = _finite(probe_result.get("Tn transverse kN-m"), float("nan"))
        informational_tn_longitudinal = _finite(probe_result.get("Tn longitudinal kN-m"), float("nan"))
    except Exception:
        pass
    note = (
        "Tu < phi*Tth; ACI 318-19 22.7.1.1 permits torsional effects to be neglected at this station. "
        "Any reported phi*Tn is informational capacity of the provided cage/Outer-Al and does not change the threshold decision."
    )
    return {
        **_base_result_fields(row),
        "Status": "BELOW THRESHOLD",
        "Strength status": "NOT REQUIRED",
        "Threshold status": "BELOW THRESHOLD",
        "Transverse status": "NOT REQUIRED",
        "Longitudinal status": "NOT REQUIRED",
        "Detailing status": "NOT REQUIRED",
        "Section limit status": "NOT REQUIRED",
        "phiTn kN-m": informational_phi_tn,
        "Tn transverse kN-m": informational_tn_transverse,
        "Tn longitudinal kN-m": informational_tn_longitudinal,
        "phiTth kN-m": phi_tth / 1.0e6,
        "phiTcr kN-m": float(context["phiTcr_Nmm"]) / 1.0e6,
        "Threshold D/C value": threshold_dc,
        "Strength D/C value": float("nan"),
        "Transverse D/C value": float("nan"),
        "Minimum transverse D/C value": float("nan"),
        "Longitudinal D/C value": float("nan"),
        "Detailing D/C value": float("nan"),
        "Section limit D/C value": float("nan"),
        "Governing D/C value": threshold_dc,
        "Ag mm2": float(context["Ag_mm2"]),
        "Acp mm2": float(context["Acp_mm2"]),
        "pcp mm": float(context["pcp_mm"]),
        "fpc MPa": float(context["fpc_mpa"]),
        "sqrt fc actual": float(context["sqrt_fc_actual"]),
        "sqrt fc used": float(context["sqrt_fc_used"]),
        "Prestress factor": float(context["prestress_factor"]),
        "Aps fse kN": float(context["Aps_fse_N"]) / 1000.0,
        "Aps fpu kN": float(context["Aps_fpu_N"]) / 1000.0,
        "As fy kN": float(context["As_fy_N"]) / 1000.0,
        "Ag/Acp": float(context["Ag/Acp"]),
        "Hollow threshold route": bool(context["hollow_for_threshold"]),
        "phi": _ACI_TORSION_PHI,
        "Method": "ACI 318-19 22.7.1/22.7.4 threshold torsion screen",
        "Notes": note,
    }


def _layout_required_result(
    row: PreparedCrossbeamShearRow,
    context: Mapping[str, Any],
    geometry: Mapping[str, Any],
) -> dict[str, Any]:
    phi_tth = float(context["phiTth_Nmm"])
    tu_nmm = abs(float(row.source_t_knm)) * 1.0e6
    return {
        **_base_result_fields(row),
        "Status": "LAYOUT REQUIRED",
        "Strength status": "NOT CHECKED",
        "Threshold status": "DESIGN REQUIRED",
        "Transverse status": "LAYOUT REQUIRED",
        "Longitudinal status": "NOT CHECKED",
        "Detailing status": "LAYOUT REQUIRED",
        "Section limit status": "NOT CHECKED",
        "phiTn kN-m": float("nan"),
        "phiTth kN-m": phi_tth / 1.0e6,
        "phiTcr kN-m": float(context["phiTcr_Nmm"]) / 1.0e6,
        "Threshold D/C value": tu_nmm / phi_tth if phi_tth > 0.0 else float("nan"),
        "Strength D/C value": float("nan"),
        "Governing D/C value": float("inf"),
        "Ag mm2": float(context["Ag_mm2"]),
        "Acp mm2": float(context["Acp_mm2"]),
        "pcp mm": float(context["pcp_mm"]),
        "fpc MPa": float(context["fpc_mpa"]),
        "phi": _ACI_TORSION_PHI,
        "Method": "ACI 318-19 torsion reinforcement-layout source gate",
        "Notes": " | ".join(
            _dedupe([*list(geometry.get("errors") or []), *list(geometry.get("warnings") or [])])
        ),
    }


def _torsion_result_for_row(row: PreparedCrossbeamShearRow) -> dict[str, Any]:
    tu_nmm = abs(float(row.source_t_knm)) * 1.0e6
    context = _threshold_context(row)
    phi_tth = float(context["phiTth_Nmm"])
    if tu_nmm < phi_tth - 1.0e-6:
        return _below_threshold_result(row, context)

    geometry = _equivalent_hoop_geometry(row)
    if not bool(geometry.get("ready")):
        return _layout_required_result(row, context, geometry)

    ag = float(context["Ag_mm2"])
    acp = float(context["Acp_mm2"])
    pcp = float(context["pcp_mm"])
    fc = float(context["fc_mpa"])
    fpc = float(context["fpc_mpa"])
    aoh = float(geometry["Aoh_mm2"])
    ao = float(geometry["Ao_mm2"])
    ph = float(geometry["ph_mm"])
    at = float(geometry["At_mm2"])
    spacing = float(geometry["spacing_mm"])
    fyt = float(geometry["fyt_design_mpa"])
    at_per_s = at / spacing

    # The concurrent flexural tension-side reinforcement source from the
    # accepted Shear adapter is used for the ACI 22.7.6.1.2 theta gate and for
    # the mandatory 22.7.7 shear/torsion section-size check.
    shear = _governing_direction(row)
    bw = float(shear["bw_mm"])
    d = float(shear["d_mm"])
    prestress_ratio = _finite(shear.get("prestress_ratio"), float("nan"))
    theta_deg = 37.5 if math.isfinite(prestress_ratio) and prestress_ratio >= 0.4 - 1.0e-12 else 45.0
    theta = math.radians(theta_deg)
    cot_theta = 1.0 / math.tan(theta)
    tan_theta = math.tan(theta)

    fy_candidates = [
        _rebar_fy(row, bar)
        for bar in row.rebars
        if str(bar.label or "").startswith("Outer:")
    ]
    fy_candidates = [float(value) for value in fy_candidates if value is not None and value > 0.0]
    fy = min(fy_candidates) if fy_candidates else min(_ACI_TORSION_FY_MAX_MPA, 390.0)

    at_req = tu_nmm / (_ACI_TORSION_PHI * 2.0 * ao * fyt * cot_theta) if tu_nmm > 0.0 else 0.0
    al_strength_req = tu_nmm * ph / (_ACI_TORSION_PHI * 2.0 * ao * fy * tan_theta) if tu_nmm > 0.0 else 0.0
    al_min, al_min_a, al_min_b = _minimum_longitudinal_area(
        fc_mpa=fc,
        acp_mm2=acp,
        fy_mpa=fy,
        at_per_s=at_per_s,
        ph_mm=ph,
        bw_mm=bw,
        fyt_mpa=fyt,
    )
    al_required = max(al_strength_req, al_min)
    longitudinal = _outer_longitudinal_review(
        row,
        spacing_transverse_mm=spacing,
        al_required_mm2=al_required,
        cage_polygon=geometry["cage_polygon"],
        cage_line=geometry["cage_line"],
    )

    tn_transverse = 2.0 * ao * at_per_s * fyt * cot_theta
    tn_longitudinal = (
        2.0 * ao * float(longitudinal["capacity_N"]) / ph * tan_theta
        if ph > 0.0
        else 0.0
    )
    tn = min(tn_transverse, tn_longitudinal) if tn_longitudinal > 0.0 else 0.0
    phi_tn = _ACI_TORSION_PHI * tn
    strength_dc = tu_nmm / phi_tn if phi_tn > 0.0 else float("inf")
    transverse_dc = at_req / at_per_s if at_per_s > 0.0 else float("inf")

    # Use unique physical vertical legs.  A verified additional outer cage
    # contributes two new side legs; a shared cage is already included in the
    # base Av source and is never counted a second time.
    steel = transverse_unique_steel_record(row.transverse_template or {})
    base_av_per_s = float(steel["Base Av/s mm²/mm"])
    additional_cage_av_per_s = float(steel["Additional cage shear legs/s mm²/mm"])
    combined_transverse_provided = float(steel["Combined unique provided/s mm²/mm"])
    combined_transverse_min = _minimum_transverse_per_s(
        fc_mpa=fc,
        bw_mm=bw,
        fyt_mpa=fyt,
    )
    minimum_transverse_dc = (
        combined_transverse_min / combined_transverse_provided
        if combined_transverse_provided > 0.0
        else float("inf")
    )
    spacing_max = min(ph / 8.0, 300.0)
    spacing_dc = spacing / spacing_max if spacing_max > 0.0 else float("inf")
    hollow_clearance_dc = _finite(geometry.get("hollow_clearance_dc"), 0.0)
    corner_coverage = int(longitudinal["corner_coverage"])
    corner_dc = 0.0 if corner_coverage >= 4 else 4.0 / max(corner_coverage, 1)
    detailing_dc = max(
        spacing_dc,
        hollow_clearance_dc,
        float(longitudinal["spacing_dc"]),
        float(longitudinal["diameter_dc"]),
        float(longitudinal.get("association_dc", 0.0)),
        corner_dc,
    )

    # ACI 22.7.7.2 local-wall substitution for hollow sections.  Where the
    # available section definition has unequal wall thicknesses, the minimum
    # wall thickness is paired conservatively with the full shear term.
    vu_n = abs(float(row.source_v2_kn)) * 1000.0
    vc_n = _finite(shear.get("Vc_N"), float("nan"))
    shear_stress = vu_n / (bw * d) if bw > 0.0 and d > 0.0 else float("nan")
    torsion_stress_base = tu_nmm * ph / (1.7 * aoh * aoh)
    wall_thickness = _hollow_wall_thickness_mm(row) if bool(geometry["is_hollow"]) else float("nan")
    equivalent_wall = aoh / ph if ph > 0.0 else float("nan")
    if (
        bool(geometry["is_hollow"])
        and math.isfinite(wall_thickness)
        and math.isfinite(equivalent_wall)
        and wall_thickness < equivalent_wall - 1.0e-9
    ):
        torsion_stress = tu_nmm / (1.7 * aoh * wall_thickness)
        hollow_stress_basis = "ACI 22.7.7.2 local minimum wall thickness"
    else:
        torsion_stress = torsion_stress_base
        hollow_stress_basis = "ACI 22.7.7.1 Aoh/ph wall basis"

    if math.isfinite(vc_n) and bw > 0.0 and d > 0.0:
        rhs = _ACI_TORSION_PHI * (vc_n / (bw * d) + 0.66 * math.sqrt(fc))
        lhs = (
            shear_stress + torsion_stress
            if bool(geometry["is_hollow"])
            else math.sqrt(shear_stress * shear_stress + torsion_stress * torsion_stress)
        )
        section_limit_dc = lhs / rhs if rhs > 0.0 else float("inf")
        section_limit_status = "PASS" if section_limit_dc <= 1.0 + 1.0e-9 else "FAIL"
    else:
        lhs = float("nan")
        rhs = float("nan")
        section_limit_dc = float("nan")
        section_limit_status = "REVIEW"

    strength_status = "PASS" if strength_dc <= 1.0 + 1.0e-9 else "FAIL"
    transverse_status = "PASS" if max(transverse_dc, minimum_transverse_dc) <= 1.0 + 1.0e-9 else "FAIL"
    longitudinal_status = str(longitudinal["status"])
    detailing_status = "PASS" if detailing_dc <= 1.0 + 1.0e-9 else "FAIL"
    gates = [strength_status, transverse_status, longitudinal_status, detailing_status, section_limit_status]
    if "FAIL" in gates:
        status = "FAIL"
    elif "LAYOUT REQUIRED" in gates:
        status = "LAYOUT REQUIRED"
    elif "REVIEW" in gates or bool(geometry.get("cage_continuity_review")) or row.source_p_kn < -1.0e-9:
        status = "REVIEW"
    else:
        status = "PASS"

    finite_dcs = [
        value
        for value in (
            strength_dc,
            transverse_dc,
            minimum_transverse_dc,
            float(longitudinal["area_dc"]),
            detailing_dc,
            section_limit_dc,
        )
        if math.isfinite(value)
    ]
    governing_dc = max(finite_dcs) if finite_dcs else float("nan")
    notes = [
        "Imported P/V2/T/M3 remain row-coupled; effective prestress is used only in fpc/theta and is not added to Tu.",
        str(longitudinal["notes"]),
        "Tu is treated as imported equilibrium demand; compatibility-torsion redistribution to phi*Tcr is not applied automatically.",
        "Standalone Al credit does not complete ACI 9.5.4.4 flexure-plus-torsion longitudinal interaction; the later Combined V+T milestone owns that final adoption.",
        "The Combined V+T workspace owns allocation of the unique physical transverse-steel pool to concurrent shear and torsion demands.",
        *list(geometry.get("warnings") or []),
    ]
    if section_limit_status == "REVIEW":
        notes.append("ACI 22.7.7 section-size check is REVIEW because the accepted Vc source is unavailable for this row.")
    if row.source_p_kn < -1.0e-9:
        notes.append("Imported P is axial tension; final torsion acceptance requires engineering review.")

    return {
        **_base_result_fields(row),
        "Status": status,
        "Strength status": strength_status,
        "Threshold status": "DESIGN REQUIRED",
        "Transverse status": transverse_status,
        "Longitudinal status": longitudinal_status,
        "Detailing status": detailing_status,
        "Section limit status": section_limit_status,
        "phiTn kN-m": phi_tn / 1.0e6 if phi_tn > 0.0 else float("nan"),
        "Tn transverse kN-m": tn_transverse / 1.0e6,
        "Tn longitudinal kN-m": tn_longitudinal / 1.0e6,
        "phiTth kN-m": phi_tth / 1.0e6,
        "phiTcr kN-m": float(context["phiTcr_Nmm"]) / 1.0e6,
        "Threshold D/C value": tu_nmm / phi_tth if phi_tth > 0.0 else float("nan"),
        "Strength D/C value": strength_dc,
        "Transverse D/C value": transverse_dc,
        "Minimum transverse D/C value": minimum_transverse_dc,
        "Longitudinal D/C value": float(longitudinal["area_dc"]),
        "Detailing D/C value": detailing_dc,
        "Section limit D/C value": section_limit_dc,
        "Governing D/C value": governing_dc,
        "Ag mm2": ag,
        "Acp mm2": acp,
        "pcp mm": pcp,
        "Aoh mm2": aoh,
        "Ao mm2": ao,
        "ph mm": ph,
        "bt mm": float(geometry.get("bt_mm", float("nan"))),
        "Hoop offset mm": float(geometry["offset_mm"]),
        "Torsion cage relationship": str(geometry.get("cage_relationship") or ""),
        "Torsion cage source status": str(geometry.get("cage_source_status") or ""),
        "Torsion cage closure": str(geometry.get("cage_closure") or ""),
        "At mm2": at,
        "At/s mm2/mm": at_per_s,
        "At/s required mm2/mm": at_req,
        "Base Av/s mm2/mm": base_av_per_s,
        "Additional cage Av/s mm2/mm": additional_cage_av_per_s,
        "Unique transverse provided/s mm2/mm": combined_transverse_provided,
        "Outer side legs/s provided mm2/mm": 2.0 * at_per_s,
        "(Av+2At)/s provided mm2/mm": combined_transverse_provided,
        "(Av+2At)/s min mm2/mm": combined_transverse_min,
        "Al strength required mm2": al_strength_req,
        "Al minimum mm2": al_min,
        "Al minimum (a) mm2": al_min_a,
        "Al minimum (b) mm2": al_min_b,
        "Al required mm2": al_required,
        "Al provided mm2": float(longitudinal["provided_mm2"]),
        "Longitudinal fy MPa": float(longitudinal.get("fy_min_mpa", fy)),
        "Outer bars outside cage": int(longitudinal.get("outside_cage_count", 0)),
        "Cage association D/C": float(longitudinal.get("association_dc", 0.0)),
        "Outer bar max spacing mm": float(longitudinal["max_perimeter_spacing_mm"]),
        "Outer bar spacing D/C": float(longitudinal["spacing_dc"]),
        "Outer bar min diameter mm": float(longitudinal["min_diameter_mm"]),
        "Outer bar diameter required mm": float(longitudinal["diameter_required_mm"]),
        "Outer bar diameter D/C": float(longitudinal["diameter_dc"]),
        "Corner coverage": corner_coverage,
        "Corner coverage D/C": corner_dc,
        "Torsion stirrup spacing mm": spacing,
        "Torsion stirrup s max mm": spacing_max,
        "Torsion stirrup spacing D/C": spacing_dc,
        "Hollow inside clearance mm": geometry.get("hollow_clearance_mm", float("nan")),
        "Hollow clearance required mm": geometry.get("hollow_clearance_required_mm", float("nan")),
        "Hollow clearance D/C": hollow_clearance_dc,
        "Hollow cage continuity review": bool(geometry.get("cage_continuity_review")),
        "Hollow wall thickness mm": wall_thickness,
        "Aoh/ph mm": equivalent_wall,
        "Hollow stress basis": hollow_stress_basis,
        "bw mm": bw,
        "d mm": d,
        "Vc kN": vc_n / 1000.0 if math.isfinite(vc_n) else float("nan"),
        "Shear stress MPa": shear_stress,
        "Torsion stress MPa": torsion_stress,
        "Section limit lhs MPa": lhs,
        "Section limit rhs MPa": rhs,
        "fpc MPa": fpc,
        "sqrt fc actual": float(context["sqrt_fc_actual"]),
        "sqrt fc used": float(context["sqrt_fc_used"]),
        "Prestress factor": float(context["prestress_factor"]),
        "Aps fse kN": _finite(shear.get("Aps_fse_N"), 0.0) / 1000.0,
        "Aps fpu kN": _finite(shear.get("Aps_fpu_N"), 0.0) / 1000.0,
        "As fy kN": _finite(shear.get("Asfy_N"), 0.0) / 1000.0,
        "Prestress ratio": prestress_ratio,
        "Ag/Acp": float(context["Ag/Acp"]),
        "Hollow threshold route": bool(context["hollow_for_threshold"]),
        "theta deg": theta_deg,
        "cot theta": cot_theta,
        "phi": _ACI_TORSION_PHI,
        "Method": "ACI 318-19 22.7 standalone torsion component check",
        "Notes": " | ".join(_dedupe(notes)),
    }

def _rank(row: Mapping[str, Any]) -> tuple[int, float, float]:
    status = str(row.get("Status") or "REVIEW")
    priority = {
        "FAIL": 6,
        "LAYOUT REQUIRED": 5,
        "REVIEW": 4,
        "PASS": 3,
        "DESIGN REQUIRED": 2,
        "BELOW THRESHOLD": 1,
        "NO DEMAND": 0,
    }.get(status, 4)
    dc = _finite(row.get("Governing D/C value"), -1.0)
    demand = _finite(row.get("Abs demand kN-m"), 0.0)
    return priority, dc if math.isfinite(dc) else -1.0, demand


def run_crossbeam_uls_torsion(preparation: CrossbeamTorsionPreparation) -> dict[str, Any]:
    """Evaluate the standalone ACI 318-19 Crossbeam torsion station route."""

    if not preparation.ready:
        raise ValueError("Crossbeam ULS Torsion preparation is not ready.")
    is_precast = any(
        "SEGMENT" in str(getattr(row, "location_type", "") or "").upper()
        for row in preparation.rows
    )
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    # Some legacy Rebar Template summary fields can be intentionally blank
    # even though the adopted detailed longitudinal bar layout is available
    # and is the actual source used by the torsion solver.  Preserve the
    # warning, but word it so the UI does not contradict a valid calculated
    # Aℓ-provided value reported from the detailed station source.
    detailed_longitudinal_templates = {
        str(row.rebar_template_id or "").strip()
        for row in preparation.rows
        if str(row.rebar_template_id or "").strip() and bool(row.rebars)
    }
    warnings: list[str] = []
    quantity_warning_suffix = "actual provided reinforcement quantities are not defined yet."
    for raw_warning in preparation.warnings:
        message = str(raw_warning)
        template_id = message.split(":", 1)[0].strip() if ":" in message else ""
        if message.endswith(quantity_warning_suffix) and template_id in detailed_longitudinal_templates:
            warnings.append(
                f"{template_id}: summary Rebar Template quantity fields are unset; standalone torsion uses the adopted detailed longitudinal bar layout for provided Aℓ, as reported in the station audit."
            )
        else:
            warnings.append(message)
    for row in preparation.rows:
        if row.location_type == "PHYSICAL SEGMENT JOINT":
            rows.append(_physical_joint_result(row))
            continue
        try:
            result = _torsion_result_for_row(row)
            if (
                str(result.get("Status") or "") in {"PASS", "BELOW THRESHOLD"}
                and str(result.get("Effective prestress mode") or "") == "UNIFORM_AVERAGE_OVERRIDE"
            ):
                result["Status"] = "REVIEW"
                result["Notes"] = (
                    f"{result.get('Notes') or ''} | Uniform-average Effective Prestress override is active; "
                    "refresh the tendon/station profile before production acceptance."
                ).strip(" |")
            rows.append(result)
        except Exception as exc:
            errors.append(f"{row.case_name} at s = {row.station_m:.6f} m: {exc}")

    joint_side_rows = [row for row in rows if bool(row.get("Generated joint side check"))]
    # One-sided physical-joint rows are useful capacity audit evidence, but
    # they are not standalone sectional decision stations.  Keep them out of
    # PASS/FAIL counts and governing ranking so a joint-side Aℓ shortfall can
    # never masquerade as the governing member-sectional torsion result.  The
    # physical-joint transfer gate remains REVIEW and is closed separately.
    sectional_rows = [
        row
        for row in rows
        if str(row.get("Location type")) != "PHYSICAL SEGMENT JOINT"
        and not bool(row.get("Generated joint side check"))
    ]
    joint_rows = [row for row in rows if str(row.get("Location type")) == "PHYSICAL SEGMENT JOINT"]
    joint_review_stations = sorted(
        {
            round(_finite(row.get("Joint station s (m)"), float("nan")), 9)
            for row in joint_side_rows
            if math.isfinite(_finite(row.get("Joint station s (m)"), float("nan")))
        }
    )
    design_rows = [row for row in sectional_rows if str(row.get("Threshold status")) == "DESIGN REQUIRED"]
    below_rows = [row for row in sectional_rows if str(row.get("Threshold status")) == "BELOW THRESHOLD"]
    generated_support = [row for row in rows if bool(row.get("Generated support check"))]
    support_joint_reviews = [row for row in generated_support if str(row.get("Location type")) == "PHYSICAL SEGMENT JOINT"]
    support_sectional = [row for row in generated_support if str(row.get("Location type")) != "PHYSICAL SEGMENT JOINT"]

    sectional_governing = max(sectional_rows, key=_rank) if sectional_rows else None
    # Overall decision ownership is the sectional route plus explicit
    # physical-joint REVIEW guards.  Computed one-sided joint capacities are
    # audit-only and therefore excluded from governing ranking.
    overall_decision_rows = [row for row in rows if not bool(row.get("Generated joint side check"))]
    overall_governing = max(overall_decision_rows, key=_rank) if overall_decision_rows else None
    if errors:
        sectional_status = "REVIEW"
    elif any(str(row.get("Status")) == "FAIL" for row in sectional_rows):
        sectional_status = "FAIL"
    elif any(str(row.get("Status")) in {"LAYOUT REQUIRED", "REVIEW"} for row in sectional_rows):
        sectional_status = "REVIEW"
    elif design_rows:
        sectional_status = "PASS"
    else:
        sectional_status = "BELOW THRESHOLD"
    combined_review_required = bool(design_rows)
    if sectional_status == "FAIL":
        overall_status = "FAIL"
    elif errors or joint_rows or joint_review_stations or sectional_status == "REVIEW" or combined_review_required:
        overall_status = "REVIEW"
    else:
        overall_status = sectional_status

    return {
        "status": overall_status,
        "sectional_status": sectional_status,
        "rows": rows,
        "governing_row": overall_governing,
        "sectional_governing_row": sectional_governing,
        "station_checks": len(rows),
        "sectional_checks": len(sectional_rows),
        "design_required_checks": len(design_rows),
        "below_threshold_checks": len(below_rows),
        "joint_review_count": len(joint_review_stations) if joint_review_stations else len(joint_rows),
        "joint_review_stations_m": joint_review_stations,
        "joint_side_rows": joint_side_rows,
        "generated_joint_side_checks": len(joint_side_rows),
        "generated_support_checks": len(generated_support),
        "support_checks": len(support_sectional),
        "support_joint_reviews": len(support_joint_reviews),
        "combined_review_required": combined_review_required,
        "errors": _dedupe(errors),
        "warnings": _dedupe(warnings),
        "fingerprint": preparation.fingerprint,
        "support_footprints": [dict(item) for item in preparation.support_footprints],
        "member_length_m": float(preparation.member_length_m),
        "excluded_pt_end_zone_rows": [],
        "pt_end_zone_settings": dict(preparation.pt_end_zone_settings or {}),
        "scope": (
            "ACI 318-19 standalone sectional torsion: threshold, transverse and longitudinal torsion strength, minimum reinforcement, "
            "closed-cage/perimeter detailing, and the 22.7.7 section-size stress limit. Column Face and prestressed h/2 checks are both evaluated conservatively. "
            + (
                "Physical segment-joint torsion transfer, compatibility-torsion redistribution, additive shear-plus-torsion reinforcement adoption, "
                "and ACI 9.5.4.4 flexure-plus-Al interaction remain separate completion gates. They do not downgrade a standalone sectional FAIL; "
                "when standalone sectional torsion otherwise passes but torsion design is required, overall Crossbeam ULS adoption remains REVIEW/INCOMPLETE until Combined V+T and physical-joint transfer reviews close. "
                if is_precast
                else "Cast-in-Place Zone boundaries are monolithic property boundaries, so physical segment-joint torsion transfer is NOT APPLICABLE. "
                "Compatibility-torsion redistribution, additive shear-plus-torsion reinforcement adoption, and ACI 9.5.4.4 flexure-plus-Al interaction remain separate sectional/design checks where applicable. "
            )
            + "Anchorage/development, PT end zones, fatigue, seismic detailing, and warping torsion remain separate."
        ),
    }
