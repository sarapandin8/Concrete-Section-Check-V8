"""Station-specific ACI 318-19 ULS shear checks for Portal Frame Crossbeams.

``CROSSBEAM.ANALYSIS2B`` consumes the accepted canonical Crossbeam ULS
station-force rows and the same Section/Rebar/Tendon sources used by the
Crossbeam flexure adapter.  In addition to ordinary beam stations, it generates
conservative support checks at each available beam-side Column Face and at h/2
measured outward from that face.  Exact one-sided source rows are required at
faces; h/2 resultants may be row-coupled interpolations on the same beam side.
The support-footprint D-region itself is omitted from the sectional route.  A
row located exactly at a Precast physical segment joint remains a separate
interface/joint-shear REVIEW item.

The production PASS route is intentionally narrow and source-complete:

* ACI 318-19 22.5.6.2 approximate ``Vc`` for prestressed flexural members,
  including the ``Aps fse >= 0.4(Aps fpu + As fy)`` applicability gate.
* ACI 318-19 22.5.8.5.3 provided transverse-reinforcement strength.
* ACI 318-19 22.5.1.2 diagonal-compression / section-size limit.
* ACI 318-19 9.6.3.2 and Table 9.6.3.4 minimum shear reinforcement.
* ACI 318-19 Table 9.7.6.2.2 maximum spacing along the member and across
  the beam width.
* ACI 318-19 Table 21.2.1 shear strength-reduction factor ``phi = 0.75``.

Internal units remain mm, MPa, N, and N-mm.  Imported resultants are used once:
``P`` is compression positive, ``V2`` is upward positive, ``T`` is right-hand
positive about increasing station, and ``M3`` is sagging positive.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Any

from shapely.geometry import LineString, Point

from concrete_pmm_pro.analysis.crossbeam_uls import (
    CROSSBEAM_LENGTH_KEY,
    CROSSBEAM_SEGMENT_ROWS_KEY,
    CROSSBEAM_ULS_LOAD_TABLE_KEY,
    _context_face,
    _dedupe,
    _fingerprint,
    _generate_rebars,
    _get,
    _load_source_for_method,
    _material_library,
    _records,
    _select_contexts,
    _zones_for_context,
)
from concrete_pmm_pro.core.models import ConcreteMaterial, Rebar, RebarMaterial, SectionGeometry
from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_PRECAST,
    column_support_footprint_rows,
    normalize_construction_method,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.project_geometry import (
    CROSSBEAM_COLUMN_ROWS_KEY,
    crossbeam_project_geometry_audit,
)
from concrete_pmm_pro.crossbeam.rebar import template_map
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_DEFINITIONS_KEY,
    build_geometry_for_definition,
    canonical_section_definitions,
    definition_map,
)
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY,
    CB_STATION_FORCE_CONTRACT_KEY,
    canonical_effective_prestress_link,
    canonical_station_force_contract,
    normalize_station_force_rows,
    validate_station_force_rows,
)
from concrete_pmm_pro.crossbeam.tendon import (
    TENDON_BOND_STATE_BONDED,
    canonical_tendon_system_rows,
    segment_joint_stations,
    station_section_contexts,
    tendon_positions_at_station,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import (
    CB_PROFILE_ROWS_KEY,
    CB_TENDON_SYSTEM_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.transverse import (
    build_transverse_cage_geometry,
    canonical_transverse_templates,
    transverse_bar_area_mm2,
    transverse_template_map,
)
from concrete_pmm_pro.geometry.summary import to_shapely_polygon


CROSSBEAM_ULS_SHEAR_RESULT_KEY = "crossbeam_analysis2_uls_shear_result"
CROSSBEAM_ULS_SHEAR_RESULT_HASH_KEY = "crossbeam_analysis2_uls_shear_input_hash"

_ACI_SHEAR_PHI = 0.75
_ACI_NORMALWEIGHT_LAMBDA = 1.0
_ACI_SHEAR_FYT_MAX_MPA = 420.0
_ACI_VC_SQRT_FC_LIMIT_MPA_SQRT = 8.3
_DEMAND_TOLERANCE_KN = 1.0e-9
_MOMENT_TOLERANCE_KNM = 1.0e-9


@dataclass(frozen=True)
class CrossbeamShearPrestressGroup:
    tendon_id: str
    bond_state: str
    x_mm: float
    y_mm: float
    area_mm2: float
    fse_mpa: float
    fpu_mpa: float

    @property
    def effective_force_n(self) -> float:
        return self.area_mm2 * self.fse_mpa

    @property
    def ultimate_force_n(self) -> float:
        return self.area_mm2 * self.fpu_mpa


@dataclass(frozen=True)
class PreparedCrossbeamShearRow:
    station_m: float
    check_point: str
    case_name: str
    section_face: str
    location_type: str
    segment_id: str
    section_id: str
    rebar_zone_id: str
    rebar_template_id: str
    transverse_template_id: str
    source_p_kn: float
    source_v2_kn: float
    source_t_knm: float
    source_m3_knm: float
    geometry: SectionGeometry
    definition: dict[str, Any]
    concrete: ConcreteMaterial
    rebars: tuple[Rebar, ...]
    rebar_materials: tuple[RebarMaterial, ...]
    prestress_groups: tuple[CrossbeamShearPrestressGroup, ...]
    transverse_template: dict[str, Any] | None
    source_signature: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrossbeamShearPreparation:
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


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _material_width_at_y(geometry: SectionGeometry, y_mm: float) -> float:
    polygon = to_shapely_polygon(geometry)
    min_x, _min_y, max_x, _max_y = polygon.bounds
    span = max(float(max_x) - float(min_x), 1.0)
    line = LineString([(float(min_x) - span, float(y_mm)), (float(max_x) + span, float(y_mm))])
    intersection = polygon.intersection(line)

    def _length(item: Any) -> float:
        if item is None or getattr(item, "is_empty", True):
            return 0.0
        if getattr(item, "geom_type", "") in {"LineString", "LinearRing"}:
            return float(item.length)
        if hasattr(item, "geoms"):
            return sum(_length(part) for part in item.geoms)
        return 0.0

    return _length(intersection)


def _web_width_mm(geometry: SectionGeometry) -> tuple[float | None, str]:
    """Return conservative total web width for vertical one-way shear.

    The generated section polygon is sampled through the central 25–75 percent
    of its depth.  The minimum positive total material width is used as ``bw``.
    For a hollow section this is the sum of the active web thicknesses; for a
    solid section it is the minimum central material width.
    """

    try:
        polygon = to_shapely_polygon(geometry)
        min_x, min_y, max_x, max_y = polygon.bounds
    except Exception:
        return None, "bw unavailable: section polygon could not be read."
    height = float(max_y) - float(min_y)
    width = float(max_x) - float(min_x)
    if height <= 0.0 or width <= 0.0:
        return None, "bw unavailable: invalid section bounds."
    candidates: list[float] = []
    for ratio in (0.25, 0.33, 0.40, 0.50, 0.60, 0.67, 0.75):
        value = _material_width_at_y(geometry, float(min_y) + ratio * height)
        if math.isfinite(value) and value > 1.0:
            candidates.append(value)
    if not candidates:
        return None, "bw unavailable: no positive central material width was found."
    return min(candidates), "bw = minimum central total material width from the generated section polygon."


def _rebar_fy_map(materials: tuple[RebarMaterial, ...]) -> dict[str, float]:
    return {str(item.name): float(item.fy_MPa) for item in materials}


def _tendon_groups_at_station(
    *,
    station_m: float,
    member_length_m: float,
    geometry: SectionGeometry,
    tendon_rows: list[dict[str, Any]],
    profile_rows: Any,
    fse_mpa: float,
) -> tuple[list[CrossbeamShearPrestressGroup], list[str], list[str]]:
    positions = {
        str(row.get("Tendon ID") or ""): row
        for row in tendon_positions_at_station(
            profile_rows,
            tendon_rows,
            station_m=station_m,
            length_m=member_length_m,
            active_only=True,
        )
    }
    polygon = to_shapely_polygon(geometry)
    y_top = float(polygon.bounds[3])
    groups: list[CrossbeamShearPrestressGroup] = []
    errors: list[str] = []
    warnings: list[str] = []
    for tendon in tendon_rows:
        if not bool(tendon.get("Active", True)):
            continue
        tendon_id = str(tendon.get("Tendon ID") or "Unnamed tendon")
        position = positions.get(tendon_id)
        if position is None:
            errors.append(f"{tendon_id}: Tendon Profile does not cover s = {station_m:.6f} m.")
            continue
        strands = int(_finite_float(tendon.get("Strands"), 0.0))
        area_per_strand = _finite_float(tendon.get("Aps/strand mm²"), 0.0)
        area = float(strands) * area_per_strand
        fpu = _finite_float(tendon.get("fpu MPa"), 0.0)
        if area <= 0.0 or fpu <= 0.0 or fse_mpa <= 0.0:
            errors.append(f"{tendon_id}: Aps, fpu, and effective stress must be positive for the prestressed shear route.")
            continue
        x_mm = _finite_float(position.get("x lateral (mm)"), 0.0)
        y_mm = y_top - _finite_float(position.get("dtop (mm)"), 0.0)
        bond_state = str(tendon.get("Bond state") or "").strip()
        if bond_state == TENDON_BOND_STATE_BONDED and not polygon.covers(Point(x_mm, y_mm)):
            errors.append(f"{tendon_id}: bonded tendon center is outside the concrete polygon at s = {station_m:.6f} m.")
            continue
        if bond_state != TENDON_BOND_STATE_BONDED and not polygon.envelope.covers(Point(x_mm, y_mm)):
            warnings.append(
                f"{tendon_id}: external/unbonded tendon center lies outside the section envelope at s = {station_m:.6f} m; verify dp geometry."
            )
        groups.append(
            CrossbeamShearPrestressGroup(
                tendon_id=tendon_id,
                bond_state=bond_state,
                x_mm=x_mm,
                y_mm=y_mm,
                area_mm2=area,
                fse_mpa=float(fse_mpa),
                fpu_mpa=fpu,
            )
        )
    return groups, _dedupe(errors), _dedupe(warnings)


def _physical_joint_row(
    *,
    station: float,
    check_point: str,
    case: str,
    demand: Mapping[str, Any],
    contexts: list[dict[str, Any]],
    definitions_by_id: Mapping[str, dict[str, Any]],
    materials_by_name: Mapping[str, ConcreteMaterial],
) -> tuple[PreparedCrossbeamShearRow | None, list[str]]:
    errors: list[str] = []
    first = contexts[0] if contexts else {}
    section_ids = list(dict.fromkeys(str(item.get("Section ID") or "") for item in contexts if str(item.get("Section ID") or "")))
    section_id = " / ".join(section_ids) or str(first.get("Section ID") or "")
    definition = definitions_by_id.get(str(first.get("Section ID") or ""))
    if definition is None:
        return None, [f"{case} at s = {station:.6f} m: adjacent physical-joint Section ID is unavailable."]
    material_name = str(definition.get("Material") or "")
    concrete = materials_by_name.get(material_name)
    if concrete is None:
        return None, [f"{case} at s = {station:.6f} m: concrete material {material_name or '(blank)'} is unavailable."]
    try:
        geometry = build_geometry_for_definition(definition)
    except Exception as exc:
        return None, [f"{case} at s = {station:.6f} m: unable to build adjacent physical-joint section: {exc}"]
    signature = _fingerprint(
        {
            "station": station,
            "case": case,
            "joint_sections": section_ids,
            "demand": dict(demand),
            "schema": "crossbeam-analysis2-physical-joint-guard-v1",
        }
    )
    return (
        PreparedCrossbeamShearRow(
            station_m=station,
            check_point=check_point,
            case_name=case,
            section_face="PHYSICAL JOINT",
            location_type="PHYSICAL SEGMENT JOINT",
            segment_id=" / ".join(str(item.get("Segment") or "") for item in contexts if str(item.get("Segment") or "")),
            section_id=section_id,
            rebar_zone_id="",
            rebar_template_id="",
            transverse_template_id="",
            source_p_kn=_finite_float(demand.get("P")),
            source_v2_kn=_finite_float(demand.get("V2")),
            source_t_knm=_finite_float(demand.get("T")),
            source_m3_knm=_finite_float(demand.get("M3")),
            geometry=geometry,
            definition=dict(definition),
            concrete=concrete,
            rebars=(),
            rebar_materials=(),
            prestress_groups=(),
            transverse_template=None,
            source_signature=signature,
            notes=(
                "Exact Precast physical segment joint: ACI beam one-way shear is not used to certify interface/joint shear transfer.",
            ),
        ),
        errors,
    )


def _station_inside_support_interior(
    station_m: float,
    support_footprints: list[dict[str, Any]],
    *,
    tolerance: float,
) -> bool:
    """Return True only for the open interior of an applied support footprint."""

    for footprint in support_footprints:
        left = _finite_float(footprint.get("s_left (m)"), float("nan"))
        right = _finite_float(footprint.get("s_right (m)"), float("nan"))
        if math.isfinite(left) and math.isfinite(right) and left + tolerance < station_m < right - tolerance:
            return True
    return False


def _rows_at_unique_station(
    rows: list[dict[str, Any]],
    *,
    station_m: float,
    side: str,
    tolerance: float,
) -> tuple[dict[str, Any] | None, str | None]:
    candidates = [
        row for row in rows
        if abs(_finite_float(row.get("Station s (m)"), float("nan")) - station_m) <= tolerance
    ]
    if not candidates:
        return None, None
    explicit = [
        row for row in candidates
        if side in str(row.get("Check Point") or "").strip().casefold()
    ]
    if explicit:
        candidates = explicit
    reference = candidates[0]
    fields = ("P", "V2", "T", "M3")
    for other in candidates[1:]:
        if any(
            abs(_finite_float(other.get(field), 0.0) - _finite_float(reference.get(field), 0.0)) > 1.0e-8
            for field in fields
        ):
            return None, (
                f"multiple non-identical station-force rows exist at s = {station_m:.6f} m; "
                f"label an explicit {side.title()} Check Point or keep one row-coupled source state."
            )
    return dict(reference), None


def _interpolate_support_demand(
    *,
    case_rows: list[dict[str, Any]],
    target_m: float,
    support_face_m: float,
    side: str,
    support_footprints: list[dict[str, Any]],
    tolerance: float,
    exact_required: bool,
) -> tuple[dict[str, Any] | None, str | None, str]:
    """Return one row-coupled demand vector at a support check station.

    Column-face checks require an exact one-sided source row because shear may
    jump through the support/joint region.  The h/2 check may use linear
    interpolation, but both bracket rows must lie on the same beam side and
    outside all support-footprint interiors.
    """

    exact, exact_error = _rows_at_unique_station(
        case_rows,
        station_m=target_m,
        side=side,
        tolerance=tolerance,
    )
    if exact_error:
        return None, exact_error, ""
    if exact is not None:
        return exact, None, f"Exact imported row at s = {target_m:.6f} m."
    if exact_required:
        return None, (
            f"an exact one-sided station-force row is required at the {side} Column Face "
            f"s = {target_m:.6f} m; interpolation across a support reaction is not permitted."
        ), ""

    eligible: list[dict[str, Any]] = []
    for row in case_rows:
        station = _finite_float(row.get("Station s (m)"), float("nan"))
        if not math.isfinite(station):
            continue
        if side == "left" and station > support_face_m + tolerance:
            continue
        if side == "right" and station < support_face_m - tolerance:
            continue
        if _station_inside_support_interior(station, support_footprints, tolerance=tolerance):
            continue
        eligible.append(row)

    station_groups: dict[float, list[dict[str, Any]]] = {}
    for row in eligible:
        station = _finite_float(row.get("Station s (m)"), float("nan"))
        station_groups.setdefault(round(station, 9), []).append(row)
    unique_rows: list[dict[str, Any]] = []
    for key in sorted(station_groups):
        station = float(key)
        selected, ambiguity = _rows_at_unique_station(
            station_groups[key],
            station_m=station,
            side=side,
            tolerance=tolerance,
        )
        if ambiguity:
            return None, ambiguity, ""
        if selected is not None:
            unique_rows.append(selected)

    lower = [row for row in unique_rows if _finite_float(row.get("Station s (m)"), float("nan")) < target_m - tolerance]
    upper = [row for row in unique_rows if _finite_float(row.get("Station s (m)"), float("nan")) > target_m + tolerance]
    if not lower or not upper:
        return None, (
            f"the ACI h/2 station s = {target_m:.6f} m is not bracketed by two active rows "
            f"on the {side} beam side of the support."
        ), ""
    lo = max(lower, key=lambda row: _finite_float(row.get("Station s (m)"), -1.0e99))
    hi = min(upper, key=lambda row: _finite_float(row.get("Station s (m)"), 1.0e99))
    x0 = _finite_float(lo.get("Station s (m)"), float("nan"))
    x1 = _finite_float(hi.get("Station s (m)"), float("nan"))
    if not math.isfinite(x0) or not math.isfinite(x1) or x1 <= x0 + tolerance:
        return None, f"invalid interpolation bracket for s = {target_m:.6f} m.", ""
    ratio = (target_m - x0) / (x1 - x0)
    derived = {
        "Active": True,
        "Station s (m)": target_m,
        "Case Name": str(lo.get("Case Name") or hi.get("Case Name") or "ULS"),
        "P": _finite_float(lo.get("P")) + ratio * (_finite_float(hi.get("P")) - _finite_float(lo.get("P"))),
        "V2": _finite_float(lo.get("V2")) + ratio * (_finite_float(hi.get("V2")) - _finite_float(lo.get("V2"))),
        "T": _finite_float(lo.get("T")) + ratio * (_finite_float(hi.get("T")) - _finite_float(lo.get("T"))),
        "M3": _finite_float(lo.get("M3")) + ratio * (_finite_float(hi.get("M3")) - _finite_float(lo.get("M3"))),
    }
    return derived, None, f"Row-coupled linear interpolation from s = {x0:.6f} and {x1:.6f} m."


def _support_side_section_depth(
    *,
    face_m: float,
    side: str,
    segment_rows: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    member_length_m: float,
) -> tuple[float | None, float, str | None]:
    tolerance = max(1.0e-7, member_length_m * 1.0e-9)
    probe_offset = max(1.0e-6, member_length_m * 1.0e-8)
    probe = face_m - probe_offset if side == "left" else face_m + probe_offset
    probe = min(max(probe, 0.0), member_length_m)
    if side == "left" and face_m <= tolerance:
        return None, probe, None
    if side == "right" and face_m >= member_length_m - tolerance:
        return None, probe, None
    contexts = station_section_contexts(
        probe,
        segment_rows,
        definitions,
        length_m=member_length_m,
    )
    section_ids = list(dict.fromkeys(str(item.get("Section ID") or "") for item in contexts if str(item.get("Section ID") or "")))
    if not section_ids:
        return None, probe, f"no beam-side Section ID is assigned adjacent to the {side} Column Face at s = {face_m:.6f} m."
    if len(section_ids) > 1:
        return None, probe, (
            f"more than one beam-side Section ID is active adjacent to the {side} Column Face at s = {face_m:.6f} m: "
            + ", ".join(section_ids)
            + "."
        )
    definition = definition_map(definitions).get(section_ids[0])
    if definition is None:
        return None, probe, f"Section ID {section_ids[0]} is unavailable at the {side} Column Face."
    try:
        polygon = to_shapely_polygon(build_geometry_for_definition(definition))
        h_mm = float(polygon.bounds[3]) - float(polygon.bounds[1])
    except Exception as exc:
        return None, probe, f"unable to determine beam depth at the {side} Column Face: {exc}"
    if not math.isfinite(h_mm) or h_mm <= 0.0:
        return None, probe, f"beam depth h is invalid at the {side} Column Face."
    return h_mm, probe, None


def _derived_support_check_demands(
    *,
    active_demands: list[dict[str, Any]],
    support_footprints: list[dict[str, Any]],
    segment_rows: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    member_length_m: float,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Generate conservative Column Face and ACI h/2 station-force rows."""

    tolerance = max(1.0e-7, member_length_m * 1.0e-9)
    case_groups: dict[str, list[dict[str, Any]]] = {}
    for row in active_demands:
        case_groups.setdefault(str(row.get("Case Name") or "ULS"), []).append(row)

    output: list[dict[str, Any]] = []
    errors: list[str] = []
    info: list[str] = []
    seen: set[tuple[str, str, str, str]] = set()
    for case_name, case_rows in case_groups.items():
        for footprint in support_footprints:
            support_id = str(footprint.get("Column") or "Column / Support")
            left = _finite_float(footprint.get("s_left (m)"), float("nan"))
            right = _finite_float(footprint.get("s_right (m)"), float("nan"))
            if not math.isfinite(left) or not math.isfinite(right) or right <= left + tolerance:
                errors.append(f"{support_id}: invalid support-footprint limits for ULS Shear.")
                continue
            for side, face in (("left", left), ("right", right)):
                h_mm, context_station, depth_error = _support_side_section_depth(
                    face_m=face,
                    side=side,
                    segment_rows=segment_rows,
                    definitions=definitions,
                    member_length_m=member_length_m,
                )
                if depth_error:
                    errors.append(f"{case_name} · {support_id}: {depth_error}")
                    continue
                if h_mm is None:
                    continue
                side_label = "L" if side == "left" else "R"
                face_source, face_error, face_note = _interpolate_support_demand(
                    case_rows=case_rows,
                    target_m=face,
                    support_face_m=face,
                    side=side,
                    support_footprints=support_footprints,
                    tolerance=tolerance,
                    exact_required=True,
                )
                if face_error or face_source is None:
                    errors.append(f"{case_name} · {support_id}-{side_label}: {face_error}")
                    continue
                face_key = (case_name, support_id, side, "COLUMN FACE")
                if face_key not in seen:
                    seen.add(face_key)
                    row = dict(face_source)
                    row.update(
                        {
                            "Active": True,
                            "Station s (m)": face,
                            "Check Point": f"{support_id}-{side_label} Face",
                            "Case Name": case_name,
                            "Note": face_note,
                            "__Derived support check": True,
                            "__Location type": "COLUMN FACE",
                            "__Context station s (m)": context_station,
                            "__Support ID": support_id,
                            "__Support side": side.upper(),
                        }
                    )
                    output.append(row)

                offset_m = h_mm / 2000.0
                critical = face - offset_m if side == "left" else face + offset_m
                if critical < -tolerance or critical > member_length_m + tolerance:
                    info.append(
                        f"{case_name} · {support_id}-{side_label}: ACI h/2 station lies outside the modeled member; the Column Face check remains active."
                    )
                    continue
                critical = min(max(critical, 0.0), member_length_m)
                if _station_inside_support_interior(critical, support_footprints, tolerance=tolerance):
                    errors.append(
                        f"{case_name} · {support_id}-{side_label}: ACI h/2 station s = {critical:.6f} m lies inside a support footprint."
                    )
                    continue
                critical_source, critical_error, critical_note = _interpolate_support_demand(
                    case_rows=case_rows,
                    target_m=critical,
                    support_face_m=face,
                    side=side,
                    support_footprints=support_footprints,
                    tolerance=tolerance,
                    exact_required=False,
                )
                if critical_error or critical_source is None:
                    errors.append(f"{case_name} · {support_id}-{side_label}: {critical_error}")
                    continue
                critical_key = (case_name, support_id, side, "ACI h/2 CRITICAL SECTION")
                if critical_key not in seen:
                    seen.add(critical_key)
                    row = dict(critical_source)
                    row.update(
                        {
                            "Active": True,
                            "Station s (m)": critical,
                            "Check Point": f"{support_id}-{side_label} h/2",
                            "Case Name": case_name,
                            "Note": critical_note,
                            "__Derived support check": True,
                            "__Location type": "ACI h/2 CRITICAL SECTION",
                            "__Context station s (m)": critical,
                            "__Support ID": support_id,
                            "__Support side": side.upper(),
                        }
                    )
                    output.append(row)
    output.sort(key=lambda row: (str(row.get("Case Name") or ""), _finite_float(row.get("Station s (m)"))))
    return output, _dedupe(errors), _dedupe(info)


def build_crossbeam_uls_shear_preparation(state: Any) -> CrossbeamShearPreparation:
    """Build source-complete station rows for the Crossbeam ACI shear check."""

    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    member_length_m = _finite_float(_get(state, CROSSBEAM_LENGTH_KEY, 0.0), 0.0)
    if member_length_m <= 0.0:
        errors.append("Crossbeam physical length L must be positive.")

    effective_link = canonical_effective_prestress_link(
        _get(state, CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY, {})
    )
    contract = canonical_station_force_contract(
        _get(state, CB_STATION_FORCE_CONTRACT_KEY, {}),
        effective_prestress_link=effective_link,
    )
    raw_uls = _records(_get(state, CROSSBEAM_ULS_LOAD_TABLE_KEY, []))
    demand_rows = normalize_station_force_rows(
        raw_uls,
        contract=contract,
        response_type="ULS",
        rows_are_canonical=True,
    )
    validation = validate_station_force_rows(
        demand_rows,
        contract=contract,
        member_length_m=max(member_length_m, 0.0),
        response_type="ULS",
        rows_are_canonical=True,
    )
    errors.extend(validation.errors)
    warnings.extend(validation.warnings)
    active_demands = [row for row in demand_rows if bool(row.get("Active", True))]
    if not active_demands:
        errors.append("No active Crossbeam ULS station-force rows are available for Shear.")

    segment_rows = _records(_get(state, CROSSBEAM_SEGMENT_ROWS_KEY, []))
    definitions = canonical_section_definitions(_get(state, CB_SECLIB_DEFINITIONS_KEY, []))
    definitions_by_id = definition_map(definitions)
    if not segment_rows:
        errors.append("Crossbeam Segment / Zone Layout is missing.")
    if not definitions:
        errors.append("Crossbeam Section Library is missing.")

    construction_method = normalize_construction_method(
        _get(state, CB_LOSS_ES_CONSTRUCTION_METHOD_KEY, CONSTRUCTION_METHOD_PRECAST)
    )
    if construction_method == CONSTRUCTION_METHOD_PRECAST:
        geometry_audit = crossbeam_project_geometry_audit(state)
        errors.extend(
            str(issue.get("Detail") or "")
            for issue in geometry_audit.get("issues", [])
            if bool(issue.get("Blocks rebar solver")) and str(issue.get("Detail") or "").strip()
        )

    longitudinal_templates, zones, transverse_templates = _load_source_for_method(state, construction_method)
    longitudinal_by_id = template_map(longitudinal_templates)
    transverse_by_id = transverse_template_map(transverse_templates)
    if not longitudinal_templates:
        errors.append("Crossbeam longitudinal reinforcement templates are missing.")
    if not zones:
        errors.append("Crossbeam reinforcement Zone assignments are missing.")
    if not transverse_templates:
        errors.append("Crossbeam transverse reinforcement templates are missing.")

    materials_by_name = _material_library(state)
    if not materials_by_name:
        errors.append("Concrete material library is missing.")

    column_rows = _records(_get(state, CROSSBEAM_COLUMN_ROWS_KEY, []))
    if not column_rows:
        errors.append("Applied Column / Support Layout is missing; support D-regions cannot be identified for ULS Shear.")
    support_footprints = column_support_footprint_rows(
        column_rows,
        segment_rows,
        length_m=max(member_length_m, 0.0),
    ) if column_rows and segment_rows and member_length_m > 0.0 else []
    for footprint in support_footprints:
        if str(footprint.get("Status") or "") != "COMPATIBLE":
            errors.append(
                f"{footprint.get('Column') or 'Column / Support'}: support-footprint source is not compatible — "
                f"{footprint.get('Issue') or 'review the applied Column / Support Layout.'}"
            )

    tendon_rows = canonical_tendon_system_rows(_get(state, CB_TENDON_SYSTEM_ROWS_KEY, []))
    active_tendons = [row for row in tendon_rows if bool(row.get("Active", True))]
    if not active_tendons:
        errors.append("Crossbeam prestressed shear route requires at least one active Tendon System row.")
    if active_tendons and not bool(effective_link.get("ready")):
        errors.append("Effective Prestress source is not CURRENT/CLOSED for Crossbeam ULS Shear.")
    fse_mpa = _finite_float(effective_link.get("average_effective_stress_mpa"), 0.0)
    if active_tendons and fse_mpa <= 0.0:
        errors.append("Average effective prestress fse must be positive for ACI 318-19 22.5.6.")

    if errors:
        payload = {
            "schema": "crossbeam-analysis2b-shear-blocked-v1",
            "contract": contract,
            "demands": demand_rows,
            "errors": _dedupe(errors),
        }
        return CrossbeamShearPreparation(
            ready=False,
            rows=(),
            errors=tuple(_dedupe(errors)),
            warnings=tuple(_dedupe(warnings)),
            info=(),
            fingerprint=_fingerprint(payload),
            demand_rows=tuple(demand_rows),
            derived_support_rows=(),
            support_footprints=tuple(support_footprints),
            member_length_m=member_length_m,
        )

    derived_support_rows, support_errors, support_info = _derived_support_check_demands(
        active_demands=active_demands,
        support_footprints=support_footprints,
        segment_rows=segment_rows,
        definitions=definitions,
        member_length_m=member_length_m,
    )
    errors.extend(support_errors)
    info.extend(support_info)
    if errors:
        payload = {
            "schema": "crossbeam-analysis2b-support-check-source-blocked-v1",
            "contract": contract,
            "demands": demand_rows,
            "derived_support_rows": derived_support_rows,
            "support_footprints": support_footprints,
            "errors": _dedupe(errors),
        }
        return CrossbeamShearPreparation(
            ready=False,
            rows=(),
            errors=tuple(_dedupe(errors)),
            warnings=tuple(_dedupe(warnings)),
            info=tuple(_dedupe(info)),
            fingerprint=_fingerprint(payload),
            demand_rows=tuple(demand_rows),
            derived_support_rows=tuple(derived_support_rows),
            support_footprints=tuple(support_footprints),
            member_length_m=member_length_m,
        )

    joint_stations = segment_joint_stations(segment_rows, length_m=member_length_m)
    profile_rows = _get(state, CB_PROFILE_ROWS_KEY, [])
    prepared: list[PreparedCrossbeamShearRow] = []
    tolerance = max(1.0e-7, member_length_m * 1.0e-9)
    derived_station_keys = {
        (str(row.get("Case Name") or "ULS"), round(_finite_float(row.get("Station s (m)")), 9))
        for row in derived_support_rows
    }
    omitted_support_rows = 0

    for demand in [*active_demands, *derived_support_rows]:
        station = _finite_float(demand.get("Station s (m)"), 0.0)
        case = str(demand.get("Case Name") or "ULS")
        check_point = str(demand.get("Check Point") or "")
        is_derived_support = bool(demand.get("__Derived support check"))
        if not is_derived_support and (case, round(station, 9)) in derived_station_keys:
            continue
        location_override = str(demand.get("__Location type") or "").strip()
        context_station = _finite_float(demand.get("__Context station s (m)"), station)
        at_joint = construction_method == CONSTRUCTION_METHOD_PRECAST and any(
            abs(station - joint) <= tolerance for joint in joint_stations
        )
        support_hits = [
            footprint
            for footprint in support_footprints
            if _finite_float(footprint.get("s_left (m)"), float("nan")) - tolerance
            <= station
            <= _finite_float(footprint.get("s_right (m)"), float("nan")) + tolerance
        ]
        if support_hits and not is_derived_support:
            omitted_support_rows += 1
            continue

        contexts = station_section_contexts(
            context_station,
            segment_rows,
            definitions,
            length_m=member_length_m,
        )
        contexts = _select_contexts(contexts, check_point=check_point, at_joint=at_joint)
        if not contexts:
            errors.append(f"{case} at s = {station:.6f} m: no active Section ID is assigned.")
            continue

        if at_joint:
            joint_row, joint_errors = _physical_joint_row(
                station=station,
                check_point=check_point,
                case=case,
                demand=demand,
                contexts=contexts,
                definitions_by_id=definitions_by_id,
                materials_by_name=materials_by_name,
            )
            errors.extend(joint_errors)
            if joint_row is not None:
                prepared.append(joint_row)
            continue

        for context in contexts:
            section_id = str(context.get("Section ID") or "")
            segment_id = str(context.get("Segment") or "")
            definition = definitions_by_id.get(section_id)
            if definition is None:
                errors.append(f"{case} at s = {station:.6f} m: Section ID {section_id or '(blank)'} is unavailable.")
                continue
            material_name = str(definition.get("Material") or "")
            concrete = materials_by_name.get(material_name)
            if concrete is None:
                errors.append(f"{case} at s = {station:.6f} m: concrete material {material_name or '(blank)'} is unavailable.")
                continue
            try:
                geometry = build_geometry_for_definition(definition)
            except Exception as exc:
                errors.append(f"{case} at s = {station:.6f} m: unable to build {section_id}: {exc}")
                continue

            zone_candidates = _zones_for_context(
                zones,
                station_m=context_station,
                segment_id=segment_id,
                check_point=check_point,
                length_m=member_length_m,
            )
            if not zone_candidates:
                errors.append(f"{case} at s = {station:.6f} m: no reinforcement Zone covers {segment_id}.")
                continue

            tendon_groups, tendon_errors, tendon_warnings = _tendon_groups_at_station(
                station_m=station,
                member_length_m=member_length_m,
                geometry=geometry,
                tendon_rows=tendon_rows,
                profile_rows=profile_rows,
                fse_mpa=fse_mpa,
            )
            errors.extend(f"{case} at s = {station:.6f} m: {message}" for message in tendon_errors)

            for zone in zone_candidates:
                longitudinal_id = str(zone.get("Longitudinal template") or zone.get("Rebar template") or "")
                transverse_id = str(zone.get("Transverse template") or "")
                transverse_template = transverse_by_id.get(transverse_id)
                if transverse_template is None:
                    errors.append(
                        f"{case} at s = {station:.6f} m: Transverse template {transverse_id or '(blank)'} is unavailable."
                    )
                    continue
                rebar_rows, rebar_materials, rebar_errors, rebar_warnings = _generate_rebars(
                    geometry,
                    definition,
                    longitudinal_by_id.get(longitudinal_id),
                    transverse_template,
                    allow_credit=True,
                )
                errors.extend(f"{case} at s = {station:.6f} m: {message}" for message in rebar_errors)
                row_notes = list(tendon_warnings) + list(rebar_warnings)
                if is_derived_support and str(demand.get("Note") or "").strip():
                    row_notes.append(str(demand.get("Note") or ""))
                face = _context_face(context, at_joint=False)
                if location_override:
                    face = str(check_point or location_override).upper()
                elif len(zone_candidates) > 1:
                    face = f"{face} / {str(zone.get('Zone ID') or 'ZONE LIMIT')}"
                source_signature = _fingerprint(
                    {
                        "schema": "crossbeam-analysis2b-shear-row-v1",
                        "station": station,
                        "context_station": context_station,
                        "case": case,
                        "face": face,
                        "location_type": location_override or "SEGMENT / ZONE INTERIOR",
                        "section": definition,
                        "zone": zone,
                        "transverse": transverse_template,
                        "rebars": [bar.model_dump(mode="json", exclude={"id"}) for bar in rebar_rows],
                        "rebar_materials": [item.model_dump(mode="json") for item in rebar_materials],
                        "prestress": [group.__dict__ for group in tendon_groups],
                        "demand": dict(demand),
                    }
                )
                prepared.append(
                    PreparedCrossbeamShearRow(
                        station_m=station,
                        check_point=check_point,
                        case_name=case,
                        section_face=face,
                        location_type=location_override or "SEGMENT / ZONE INTERIOR",
                        segment_id=segment_id,
                        section_id=section_id,
                        rebar_zone_id=str(zone.get("Zone ID") or ""),
                        rebar_template_id=longitudinal_id,
                        transverse_template_id=transverse_id,
                        source_p_kn=_finite_float(demand.get("P")),
                        source_v2_kn=_finite_float(demand.get("V2")),
                        source_t_knm=_finite_float(demand.get("T")),
                        source_m3_knm=_finite_float(demand.get("M3")),
                        geometry=geometry,
                        definition=dict(definition),
                        concrete=concrete,
                        rebars=tuple(rebar_rows),
                        rebar_materials=tuple(rebar_materials),
                        prestress_groups=tuple(tendon_groups),
                        transverse_template=dict(transverse_template),
                        source_signature=source_signature,
                        notes=tuple(_dedupe(row_notes)),
                    )
                )

    errors = _dedupe(errors)
    warnings = _dedupe(warnings)
    if prepared:
        support_check_count = sum(
            row.location_type in {"COLUMN FACE", "ACI h/2 CRITICAL SECTION"}
            for row in prepared
        )
        info.extend(
            [
                f"Prepared Crossbeam ULS Shear station checks: {len(prepared)}.",
                f"Conservative support checks generated: {support_check_count} Column Face / ACI h/2 row(s).",
                f"Active imported ULS rows: {len(active_demands)}.",
                f"Imported rows omitted inside support footprints or replaced by exact support checks: {omitted_support_rows}.",
                "Demand mapping: V2 → Vu; P/T/M3 remain row-coupled source values.",
                "ACI 318-19 9.4.3 is implemented conservatively by checking both the beam-side Column Face and h/2 from that face where the station lies within the modeled member.",
                "ACI 318-19 prestressed shear uses the current Effective Prestress source; imported resultants are not modified.",
            ]
        )
    fingerprint = _fingerprint(
        {
            "schema": "crossbeam-analysis2b-aci-prestressed-shear-v1",
            "construction_method": construction_method,
            "contract": contract,
            "demands": demand_rows,
            "derived_support_rows": derived_support_rows,
            "support_footprints": support_footprints,
            "row_signatures": [row.source_signature for row in prepared],
        }
    )
    return CrossbeamShearPreparation(
        ready=bool(prepared) and not errors,
        rows=tuple(prepared),
        errors=tuple(errors),
        warnings=tuple(warnings),
        info=tuple(_dedupe(info)),
        fingerprint=fingerprint,
        demand_rows=tuple(demand_rows),
        derived_support_rows=tuple(derived_support_rows),
        support_footprints=tuple(support_footprints),
        member_length_m=member_length_m,
    )


def _direction_signs(row: PreparedCrossbeamShearRow) -> tuple[tuple[float, str], ...]:
    if row.source_m3_knm > _MOMENT_TOLERANCE_KNM:
        return ((1.0, "Sagging (+M3)"),)
    if row.source_m3_knm < -_MOMENT_TOLERANCE_KNM:
        return ((-1.0, "Hogging (-M3)"),)
    return ((1.0, "Zero M3 — sagging trial"), (-1.0, "Zero M3 — hogging trial"))


def _direction_geometry(
    row: PreparedCrossbeamShearRow,
    direction_sign: float,
) -> dict[str, Any]:
    polygon = to_shapely_polygon(row.geometry)
    _min_x, min_y, _max_x, max_y = polygon.bounds
    h_mm = float(max_y) - float(min_y)
    centroid_y = float(polygon.centroid.y)
    bottom_tension = direction_sign > 0.0
    tension_bars = [
        bar
        for bar in row.rebars
        if (float(bar.y_mm) <= centroid_y + 1.0e-9 if bottom_tension else float(bar.y_mm) >= centroid_y - 1.0e-9)
    ]
    fy_by_name = _rebar_fy_map(row.rebar_materials)
    missing_materials = sorted(
        {str(bar.material_name) for bar in tension_bars if str(bar.material_name) not in fy_by_name}
    )
    if missing_materials:
        raise ValueError(
            "Longitudinal reinforcement material source is unavailable for: "
            + ", ".join(missing_materials)
        )
    rebar_terms = [
        (float(bar.y_mm), float(bar.area_mm2), float(fy_by_name[str(bar.material_name)]))
        for bar in tension_bars
    ]
    tension_prestress_groups = [
        group
        for group in row.prestress_groups
        if group.area_mm2 > 0.0
        and (float(group.y_mm) <= centroid_y + 1.0e-9 if bottom_tension else float(group.y_mm) >= centroid_y - 1.0e-9)
    ]
    prestress_terms = [
        (float(group.y_mm), float(group.area_mm2))
        for group in tension_prestress_groups
    ]
    combined_area = sum(area for _y, area, _fy in rebar_terms) + sum(area for _y, area in prestress_terms)
    if combined_area <= 0.0:
        raise ValueError("No prestressed or nonprestressed longitudinal tension reinforcement is available to calculate d.")
    combined_y = (
        sum(y * area for y, area, _fy in rebar_terms)
        + sum(y * area for y, area in prestress_terms)
    ) / combined_area
    d_raw = float(max_y) - combined_y if bottom_tension else combined_y - float(min_y)
    d_mm = max(d_raw, 0.80 * h_mm)

    aps = sum(area for _y, area in prestress_terms)
    if aps <= 0.0:
        raise ValueError("No active prestress area is available to calculate dp and ACI 22.5.6 applicability.")
    ps_y = sum(y * area for y, area in prestress_terms) / aps
    dp_mm = float(max_y) - ps_y if bottom_tension else ps_y - float(min_y)
    asfy_n = sum(area * fy for _y, area, fy in rebar_terms)
    aps_fse_n = sum(group.effective_force_n for group in tension_prestress_groups)
    aps_fpu_n = sum(group.ultimate_force_n for group in tension_prestress_groups)
    denominator = aps_fpu_n + asfy_n
    prestress_ratio = aps_fse_n / denominator if denominator > 0.0 else float("nan")
    return {
        "h_mm": h_mm,
        "d_raw_mm": d_raw,
        "d_mm": d_mm,
        "dp_mm": dp_mm,
        "As_mm2": sum(area for _y, area, _fy in rebar_terms),
        "Asfy_N": asfy_n,
        "Aps_mm2": aps,
        "Aps_fse_N": aps_fse_n,
        "Aps_fpu_N": aps_fpu_n,
        "prestress_ratio": prestress_ratio,
        "tension_face": "Bottom face" if bottom_tension else "Top face",
    }


def _aci_prestressed_vc_n(
    *,
    sqrt_fc_mpa_sqrt: float,
    bw_mm: float,
    d_mm: float,
    dp_mm: float,
    vu_n: float,
    mu_nmm: float,
) -> dict[str, float]:
    sqrt_fc = float(sqrt_fc_mpa_sqrt)
    base = 0.05 * _ACI_NORMALWEIGHT_LAMBDA * sqrt_fc
    ratio_term = float("inf")
    if abs(mu_nmm) > 1.0e-9:
        ratio_term = 4.8 * abs(vu_n) * float(dp_mm) / abs(mu_nmm)
    vc_a = (base + ratio_term) * bw_mm * d_mm
    vc_b = (base + 4.8) * bw_mm * d_mm
    vc_c = 0.42 * _ACI_NORMALWEIGHT_LAMBDA * sqrt_fc * bw_mm * d_mm
    raw = min(vc_a, vc_b, vc_c)
    lower = 0.17 * _ACI_NORMALWEIGHT_LAMBDA * sqrt_fc * bw_mm * d_mm
    vc = max(raw, lower)
    return {
        "Vc_N": vc,
        "Vc_a_N": vc_a,
        "Vc_b_N": vc_b,
        "Vc_c_N": vc_c,
        "Vc_lower_N": lower,
        "sqrt_fc_for_Vc": sqrt_fc,
    }


def _transverse_values(row: PreparedCrossbeamShearRow) -> dict[str, Any]:
    template = canonical_transverse_templates([dict(row.transverse_template or {})])[0] if row.transverse_template else None
    if template is None:
        return {
            "credit": False,
            "Av_per_s": 0.0,
            "spacing_mm": float("nan"),
            "fyt_input_mpa": float("nan"),
            "fyt_design_mpa": float("nan"),
            "effective_legs": 0,
            "across_spacing_mm": float("nan"),
            "cage_errors": ("No active transverse template.",),
            "cage_warnings": (),
            "stirrup": "-",
        }
    area = transverse_bar_area_mm2(template.get("Bar size"))
    spacing = _finite_float(template.get("Spacing mm"), float("nan"))
    legs = max(int(round(_finite_float(template.get("Effective legs"), 0.0))), 0)
    fyt_input = _finite_float(template.get("fy MPa"), float("nan"))
    fyt_design = min(fyt_input, _ACI_SHEAR_FYT_MAX_MPA) if math.isfinite(fyt_input) else float("nan")
    credit = bool(template.get("Credit inside segment", True)) and area > 0.0 and spacing > 0.0 and legs > 0
    av_per_s = area * legs / spacing if credit else 0.0
    cages = build_transverse_cage_geometry(row.geometry, row.definition, template)
    across_candidates: list[float] = []
    for path in cages.closed_loops:
        width = max(float(path.envelope[1]) - float(path.envelope[0]), 0.0)
        if path.effective_legs > 1 and width > 0.0:
            across_candidates.append(width / float(path.effective_legs - 1))
    across_spacing = max(across_candidates) if across_candidates else float("nan")
    return {
        "credit": credit,
        "Av_per_s": av_per_s,
        "spacing_mm": spacing,
        "fyt_input_mpa": fyt_input,
        "fyt_design_mpa": fyt_design,
        "effective_legs": legs,
        "across_spacing_mm": across_spacing,
        "cage_errors": tuple(cages.errors),
        "cage_warnings": tuple(cages.warnings),
        "stirrup": f"{template.get('Bar size') or '-'} × {legs} legs @ {spacing:.0f} mm",
    }


def _spacing_limits_mm(*, h_mm: float, vs_required_n: float, fc_mpa: float, bw_mm: float, d_mm: float) -> tuple[float, float, str]:
    threshold = 0.33 * math.sqrt(fc_mpa) * bw_mm * d_mm
    if vs_required_n <= threshold + 1.0e-9:
        return min(0.75 * h_mm, 600.0), min(1.50 * h_mm, 600.0), "ACI Table 9.7.6.2.2 — required Vs ≤ 0.33√f'c bw d"
    return min(0.375 * h_mm, 300.0), min(0.75 * h_mm, 300.0), "ACI Table 9.7.6.2.2 — required Vs > 0.33√f'c bw d"


def _minimum_av_per_s(
    *,
    fc_mpa: float,
    bw_mm: float,
    fyt_mpa: float,
    d_mm: float,
    aps_fpu_n: float,
    prestress_dominant: bool,
) -> tuple[float, str, float, float]:
    base = max(0.062 * math.sqrt(fc_mpa) * bw_mm / fyt_mpa, 0.35 * bw_mm / fyt_mpa)
    prestress_specific = (
        aps_fpu_n / (80.0 * fyt_mpa * d_mm) * math.sqrt(d_mm / bw_mm)
        if d_mm > 0.0 and bw_mm > 0.0
        else float("nan")
    )
    if prestress_dominant and math.isfinite(prestress_specific):
        return min(base, prestress_specific), "ACI 318-19 Table 9.6.3.4(c)-(e), prestress-dominant lesser-of gate", base, prestress_specific
    return base, "ACI 318-19 Table 9.6.3.4(a)-(b)", base, prestress_specific


def _direction_result(row: PreparedCrossbeamShearRow, direction_sign: float, direction_label: str) -> dict[str, Any]:
    notes = list(row.notes)
    fc = float(row.concrete.fc_MPa)
    bw_mm, bw_note = _web_width_mm(row.geometry)
    notes.append(bw_note)
    if bw_mm is None or bw_mm <= 0.0 or fc <= 0.0:
        raise ValueError("Section bw or f'c is unavailable for the shear check.")
    geom = _direction_geometry(row, direction_sign)
    prestress_ratio = float(geom["prestress_ratio"])
    prestress_dominant = math.isfinite(prestress_ratio) and prestress_ratio >= 0.40 - 1.0e-12
    if not prestress_dominant:
        return {
            "Status": "REVIEW",
            "Strength status": "REVIEW",
            "Detailing status": "REVIEW",
            "Direction": direction_label,
            "Tension face": geom["tension_face"],
            "Notes": (
                "ACI 318-19 22.5.6.2 approximate prestressed Vc is not applicable because "
                f"Aps fse / (Aps fpu + As fy) = {prestress_ratio:.3f} < 0.400. "
                "The refined Vci/Vcw route needs additional dead-load/service stress decomposition and is outside ANALYSIS2."
            ),
            **geom,
            "bw_mm": bw_mm,
        }

    vu_n = abs(row.source_v2_kn) * 1000.0
    mu_nmm = abs(row.source_m3_knm) * 1_000_000.0
    transverse = _transverse_values(row)
    fyt = float(transverse["fyt_design_mpa"])
    if not math.isfinite(fyt) or fyt <= 0.0:
        raise ValueError("Transverse reinforcement fyt is unavailable.")
    av_per_s = float(transverse["Av_per_s"])
    av_required, av_basis, av_base, av_ps = _minimum_av_per_s(
        fc_mpa=fc,
        bw_mm=bw_mm,
        fyt_mpa=fyt,
        d_mm=float(geom["d_mm"]),
        aps_fpu_n=float(geom["Aps_fpu_N"]),
        prestress_dominant=True,
    )
    minimum_web_reinforcement_provided = (
        av_per_s + 1.0e-12 >= av_required
        and not transverse["cage_errors"]
    )
    sqrt_fc_actual = math.sqrt(fc)
    sqrt_fc_for_vc = (
        sqrt_fc_actual
        if minimum_web_reinforcement_provided
        else min(sqrt_fc_actual, _ACI_VC_SQRT_FC_LIMIT_MPA_SQRT)
    )
    vc = _aci_prestressed_vc_n(
        sqrt_fc_mpa_sqrt=sqrt_fc_for_vc,
        bw_mm=bw_mm,
        d_mm=float(geom["d_mm"]),
        dp_mm=float(geom["dp_mm"]),
        vu_n=vu_n,
        mu_nmm=mu_nmm,
    )
    vs_n = av_per_s * fyt * float(geom["d_mm"])
    vn_uncapped_n = float(vc["Vc_N"]) + max(vs_n, 0.0)
    vs_max_n = 0.66 * math.sqrt(fc) * bw_mm * float(geom["d_mm"])
    vn_limit_n = float(vc["Vc_N"]) + vs_max_n
    vn_n = min(vn_uncapped_n, vn_limit_n)
    phi_vn_n = _ACI_SHEAR_PHI * vn_n
    strength_dc = vu_n / phi_vn_n if phi_vn_n > 0.0 else float("nan")
    strength_status = "PASS" if math.isfinite(strength_dc) and strength_dc <= 1.0 + 1.0e-9 else "FAIL"
    section_limit_dc = vu_n / (_ACI_SHEAR_PHI * vn_limit_n) if vn_limit_n > 0.0 else float("nan")
    section_limit_status = "PASS" if math.isfinite(section_limit_dc) and section_limit_dc <= 1.0 + 1.0e-9 else "FAIL"

    shear_reinforcement_required = vu_n > 0.50 * _ACI_SHEAR_PHI * float(vc["Vc_N"]) + 1.0e-9
    vs_required_n = max(vu_n / _ACI_SHEAR_PHI - float(vc["Vc_N"]), 0.0)
    along_smax, across_smax, spacing_basis = _spacing_limits_mm(
        h_mm=float(geom["h_mm"]),
        vs_required_n=vs_required_n,
        fc_mpa=fc,
        bw_mm=bw_mm,
        d_mm=float(geom["d_mm"]),
    )
    av_dc = av_required / av_per_s if av_per_s > 0.0 else float("inf")
    along_dc = float(transverse["spacing_mm"]) / along_smax if along_smax > 0.0 else float("nan")
    across_spacing = float(transverse["across_spacing_mm"])
    across_dc = across_spacing / across_smax if math.isfinite(across_spacing) and across_smax > 0.0 else float("nan")

    if not shear_reinforcement_required:
        detailing_status = "NOT REQUIRED"
        detailing_dc = 0.0
        notes.append("Vu ≤ 0.5φVc; ACI 318-19 9.6.3.2 does not require Av,min at this station.")
    else:
        finite_detailing = [av_dc, along_dc, across_dc]
        if not bool(transverse["credit"]) or av_per_s <= 0.0:
            detailing_status = "FAIL"
            detailing_dc = float("inf")
            notes.append("Shear reinforcement is required, but the assigned transverse template provides no sectional Av/s credit.")
        elif transverse["cage_errors"] or not all(math.isfinite(value) for value in finite_detailing):
            detailing_status = "REVIEW"
            detailing_dc = max((value for value in finite_detailing if math.isfinite(value)), default=float("nan"))
        else:
            detailing_dc = max(finite_detailing)
            detailing_status = "PASS" if detailing_dc <= 1.0 + 1.0e-9 else "FAIL"
    if transverse["fyt_input_mpa"] > _ACI_SHEAR_FYT_MAX_MPA + 1.0e-9:
        notes.append(
            f"Transverse fy = {transverse['fyt_input_mpa']:.1f} MPa is capped at 420 MPa for ACI shear design per Table 20.2.2.4(a)."
        )
    if sqrt_fc_actual > _ACI_VC_SQRT_FC_LIMIT_MPA_SQRT + 1.0e-12:
        if minimum_web_reinforcement_provided:
            notes.append(
                "ACI 318-19 22.5.3.2 permits the full √f'c value for Vc because provided Av/s satisfies Table 9.6.3.4 minimum web reinforcement."
            )
        else:
            notes.append(
                "ACI 318-19 22.5.3.1 caps √f'c at 8.3 MPa^0.5 for Vc because Table 9.6.3.4 minimum web reinforcement is not provided."
            )
    notes.extend(str(message) for message in transverse["cage_errors"])
    notes.extend(str(message) for message in transverse["cage_warnings"])
    notes.append("Prestress vertical component Vp is not added; Table 22.5.6.2 is used and imported FEA demand remains unchanged.")
    if section_limit_status == "FAIL" or strength_status == "FAIL" or detailing_status == "FAIL":
        status = "FAIL"
    elif detailing_status == "REVIEW" or row.source_p_kn < -1.0e-9:
        status = "REVIEW"
    else:
        status = "PASS"
    if row.source_p_kn < -1.0e-9:
        notes.append("Imported P is axial tension; ACI 22.5.1.8 requires engineering judgment, so PASS is downgraded to REVIEW.")
    finite_dcs = [value for value in (strength_dc, detailing_dc, section_limit_dc) if math.isfinite(value)]
    governing_dc = max(finite_dcs) if finite_dcs else float("nan")
    return {
        "Status": status,
        "Strength status": strength_status,
        "Detailing status": detailing_status,
        "Section limit status": section_limit_status,
        "Direction": direction_label,
        "Tension face": geom["tension_face"],
        "bw_mm": bw_mm,
        **geom,
        **vc,
        "Vs_N": vs_n,
        "Vn_N": vn_n,
        "Vn_uncapped_N": vn_uncapped_n,
        "Vn_limit_N": vn_limit_n,
        "phiVn_N": phi_vn_n,
        "strength_dc": strength_dc,
        "section_limit_dc": section_limit_dc,
        "governing_dc": governing_dc,
        "shear_reinforcement_required": shear_reinforcement_required,
        "Vs_required_N": vs_required_n,
        "Av_per_s": av_per_s,
        "Av_required_per_s": av_required,
        "Av_base_per_s": av_base,
        "Av_prestress_specific_per_s": av_ps,
        "minimum_web_reinforcement_provided": minimum_web_reinforcement_provided,
        "Av_dc": av_dc,
        "along_spacing_mm": transverse["spacing_mm"],
        "along_smax_mm": along_smax,
        "along_dc": along_dc,
        "across_spacing_mm": across_spacing,
        "across_smax_mm": across_smax,
        "across_dc": across_dc,
        "detailing_dc": detailing_dc,
        "fyt_input_mpa": transverse["fyt_input_mpa"],
        "fyt_design_mpa": fyt,
        "effective_legs": transverse["effective_legs"],
        "stirrup": transverse["stirrup"],
        "av_basis": av_basis,
        "spacing_basis": spacing_basis,
        "Notes": " | ".join(_dedupe([str(item) for item in notes if str(item).strip()])),
    }


def _governing_direction(row: PreparedCrossbeamShearRow) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    for sign, label in _direction_signs(row):
        try:
            candidates.append(_direction_result(row, sign, label))
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    if not candidates:
        raise ValueError("; ".join(errors) or "No shear direction could be evaluated.")

    def _rank(item: Mapping[str, Any]) -> tuple[int, float, float]:
        status = str(item.get("Status") or "REVIEW")
        status_rank = 2 if status == "FAIL" else (1 if status == "REVIEW" else 0)
        dc = _finite_float(item.get("governing_dc"), float("nan"))
        phi_vn = _finite_float(item.get("phiVn_N"), float("nan"))
        return status_rank, dc if math.isfinite(dc) else -1.0, -phi_vn if math.isfinite(phi_vn) else 0.0

    governing = max(candidates, key=_rank)
    if len(candidates) > 1:
        note = "Zero M3: both sagging and hogging reinforcement-depth trials were evaluated; the governing lower-capacity / higher-D/C direction is reported."
        governing["Notes"] = f"{governing.get('Notes') or ''} | {note}".strip(" |")
    return governing


def _joint_result_row(row: PreparedCrossbeamShearRow) -> dict[str, Any]:
    return {
        "Check": "Shear",
        "Status": "REVIEW",
        "Strength status": "NOT CHECKED",
        "Detailing status": "NOT CHECKED",
        "Section limit status": "NOT CHECKED",
        "Station type": "PHYSICAL SEGMENT JOINT",
        "Governing x": f"{row.station_m:.3f} m",
        "Station s (m)": row.station_m,
        "Check Point": row.check_point,
        "Case": row.case_name,
        "Section face": row.section_face,
        "Location type": row.location_type,
        "Segment": row.segment_id,
        "Section ID": row.section_id,
        "Rebar Zone": "Not applicable at physical joint",
        "Transverse Template": "No joint-shear credit",
        "P kN": row.source_p_kn,
        "V2 kN": row.source_v2_kn,
        "T kN-m": row.source_t_knm,
        "M3 kN-m": row.source_m3_knm,
        "Demand": f"{row.source_v2_kn:,.3f} kN",
        "Capacity": "Joint shear transfer not checked",
        "Utilization": "-",
        "Demand kN": row.source_v2_kn,
        "Abs demand kN": abs(row.source_v2_kn),
        "φVn kN": float("nan"),
        "φVc kN": float("nan"),
        "φVs kN": float("nan"),
        "D/C value": float("nan"),
        "Strength D/C value": float("nan"),
        "Detailing D/C value": float("nan"),
        "Governing D/C value": float("nan"),
        "Code basis": "ACI 318-19 beam shear not applicable to exact physical interface",
        "Method": "Physical-joint scope guard",
        "Notes": (
            "Physical segment-joint shear transfer, keys/interface friction, compression, local reinforcement, and D-region behavior require a separate project check. "
            "This row cannot produce PASS in the sectional beam-shear module."
        ),
    }


def run_crossbeam_uls_shear(preparation: CrossbeamShearPreparation) -> dict[str, Any]:
    """Evaluate ACI 318-19 prestressed one-way shear for prepared rows."""

    if not preparation.ready:
        raise ValueError("Crossbeam ULS Shear preparation is not ready.")
    result_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = list(preparation.warnings)
    for row in preparation.rows:
        if row.location_type == "PHYSICAL SEGMENT JOINT":
            result_rows.append(_joint_result_row(row))
            continue
        try:
            result = _governing_direction(row)
        except Exception as exc:
            errors.append(f"{row.case_name} at s = {row.station_m:.6f} m: {exc}")
            continue

        status = str(result.get("Status") or "REVIEW")
        phi_vn_n = _finite_float(result.get("phiVn_N"), float("nan"))
        strength_dc = _finite_float(result.get("strength_dc"), float("nan"))
        detailing_dc = _finite_float(result.get("detailing_dc"), float("nan"))
        governing_dc = _finite_float(result.get("governing_dc"), float("nan"))
        utilization_parts: list[str] = []
        if math.isfinite(strength_dc):
            utilization_parts.append(f"Strength D/C {strength_dc:.3f}")
        if math.isfinite(detailing_dc) and str(result.get("Detailing status")) not in {"NOT REQUIRED"}:
            utilization_parts.append(f"Detailing D/C {detailing_dc:.3f}")
        elif math.isinf(detailing_dc):
            utilization_parts.append("Detailing D/C ∞")
        utilization = "; ".join(utilization_parts) or "-"
        result_rows.append(
            {
                "Check": "Shear",
                "Status": status,
                "Strength status": result.get("Strength status", "REVIEW"),
                "Detailing status": result.get("Detailing status", "REVIEW"),
                "Section limit status": result.get("Section limit status", "REVIEW"),
                "Station type": (
                    row.location_type
                    if row.location_type in {"COLUMN FACE", "ACI h/2 CRITICAL SECTION"}
                    else "LOAD STATION"
                ),
                "Governing x": f"{row.station_m:.3f} m",
                "Station s (m)": row.station_m,
                "Check Point": row.check_point,
                "Case": row.case_name,
                "Section face": row.section_face,
                "Location type": row.location_type,
                "Segment": row.segment_id,
                "Section ID": row.section_id,
                "Rebar Zone": row.rebar_zone_id,
                "Rebar Template": row.rebar_template_id,
                "Transverse Template": row.transverse_template_id,
                "P kN": row.source_p_kn,
                "V2 kN": row.source_v2_kn,
                "T kN-m": row.source_t_knm,
                "M3 kN-m": row.source_m3_knm,
                "Demand": f"{row.source_v2_kn:,.3f} kN",
                "Capacity": "-" if not math.isfinite(phi_vn_n) else f"φVn = {phi_vn_n / 1000.0:,.3f} kN",
                "Utilization": utilization,
                "Demand kN": row.source_v2_kn,
                "Abs demand kN": abs(row.source_v2_kn),
                "φVn kN": phi_vn_n / 1000.0 if math.isfinite(phi_vn_n) else float("nan"),
                "φVc kN": _finite_float(result.get("Vc_N"), float("nan")) * _ACI_SHEAR_PHI / 1000.0,
                "φVs kN": _finite_float(result.get("Vs_N"), float("nan")) * _ACI_SHEAR_PHI / 1000.0,
                "Vc kN": _finite_float(result.get("Vc_N"), float("nan")) / 1000.0,
                "Vs kN": _finite_float(result.get("Vs_N"), float("nan")) / 1000.0,
                "Vn kN": _finite_float(result.get("Vn_N"), float("nan")) / 1000.0,
                "Vn uncapped kN": _finite_float(result.get("Vn_uncapped_N"), float("nan")) / 1000.0,
                "Vn limit kN": _finite_float(result.get("Vn_limit_N"), float("nan")) / 1000.0,
                "φVn limit kN": _finite_float(result.get("Vn_limit_N"), float("nan")) * _ACI_SHEAR_PHI / 1000.0,
                "D/C value": strength_dc,
                "Strength D/C value": strength_dc,
                "Detailing D/C value": detailing_dc,
                "Governing D/C value": governing_dc,
                "Section limit D/C": result.get("section_limit_dc", float("nan")),
                "Zone": row.rebar_zone_id,
                "Stirrup": result.get("stirrup", "-"),
                "Av/s mm2/mm": result.get("Av_per_s", float("nan")),
                "Av/s mm2/m": _finite_float(result.get("Av_per_s"), float("nan")) * 1000.0,
                "Av/s required mm2/mm": result.get("Av_required_per_s", float("nan")),
                "Av/s required mm2/m": _finite_float(result.get("Av_required_per_s"), float("nan")) * 1000.0,
                "Av/s min D/C": result.get("Av_dc", float("nan")),
                "s max mm": result.get("along_smax_mm", float("nan")),
                "Spacing D/C": result.get("along_dc", float("nan")),
                "Across leg spacing mm": result.get("across_spacing_mm", float("nan")),
                "Across s max mm": result.get("across_smax_mm", float("nan")),
                "Across spacing D/C": result.get("across_dc", float("nan")),
                "Detailing basis": f"{result.get('av_basis', '-')} | {result.get('spacing_basis', '-')}",
                "bw mm": result.get("bw_mm", float("nan")),
                "h mm": result.get("h_mm", float("nan")),
                "d raw mm": result.get("d_raw_mm", float("nan")),
                "d mm": result.get("d_mm", float("nan")),
                "dp mm": result.get("dp_mm", float("nan")),
                "Tension face": result.get("Tension face", "-"),
                "Bending direction": result.get("Direction", "-"),
                "Aps mm2": result.get("Aps_mm2", float("nan")),
                "As tension mm2": result.get("As_mm2", float("nan")),
                "Aps fse kN": _finite_float(result.get("Aps_fse_N"), float("nan")) / 1000.0,
                "Aps fpu kN": _finite_float(result.get("Aps_fpu_N"), float("nan")) / 1000.0,
                "As fy kN": _finite_float(result.get("Asfy_N"), float("nan")) / 1000.0,
                "Prestress ratio": result.get("prestress_ratio", float("nan")),
                "fyt input MPa": result.get("fyt_input_mpa", float("nan")),
                "fyt design MPa": result.get("fyt_design_mpa", float("nan")),
                "Vc(a) kN": _finite_float(result.get("Vc_a_N"), float("nan")) / 1000.0,
                "Vc(b) kN": _finite_float(result.get("Vc_b_N"), float("nan")) / 1000.0,
                "Vc(c) kN": _finite_float(result.get("Vc_c_N"), float("nan")) / 1000.0,
                "Vc lower kN": _finite_float(result.get("Vc_lower_N"), float("nan")) / 1000.0,
                "√f'c actual": math.sqrt(float(row.concrete.fc_MPa)),
                "√f'c used for Vc": result.get("sqrt_fc_for_Vc", float("nan")),
                "φ": _ACI_SHEAR_PHI,
                "Code basis": "ACI 318-19 22.5.6.2, 22.5.8.5.3, 22.5.1.2, 9.6.3, 9.7.6.2.2, 21.2.1",
                "φ policy": "ACI 318-19 Table 21.2.1 shear φ = 0.75",
                "Method": "ACI prestressed approximate Vc + provided transverse reinforcement",
                "Notes": result.get("Notes", ""),
            }
        )

    statuses = {str(item.get("Status") or "REVIEW") for item in result_rows}
    if errors or not result_rows:
        overall = "REVIEW"
    elif "FAIL" in statuses:
        overall = "FAIL"
    elif statuses == {"PASS"}:
        overall = "PASS"
    else:
        overall = "REVIEW"

    def _governing_rank(item: Mapping[str, Any]) -> tuple[int, float]:
        item_status = str(item.get("Status") or "REVIEW")
        status_rank = 2 if item_status == "FAIL" else (1 if item_status == "REVIEW" else 0)
        dc = _finite_float(item.get("Governing D/C value"), float("nan"))
        if math.isinf(dc):
            dc = 1.0e99
        return status_rank, dc if math.isfinite(dc) else -1.0

    governing = max(result_rows, key=_governing_rank, default=None)
    return {
        "schema": "crossbeam-analysis2b-aci-prestressed-shear-result-v1",
        "input_fingerprint": preparation.fingerprint,
        "status": overall,
        "rows": result_rows,
        "governing_row": governing,
        "warnings": _dedupe(warnings),
        "errors": _dedupe(errors),
        "station_checks": len(preparation.rows),
        "support_checks": sum(
            str(item.get("Location type") or "") in {"COLUMN FACE", "ACI h/2 CRITICAL SECTION"}
            for item in result_rows
        ),
        "support_footprints": [dict(item) for item in preparation.support_footprints],
        "derived_support_rows": [dict(item) for item in preparation.derived_support_rows],
        "scope": (
            "ULS sectional one-way shear only. ACI 318-19 9.4.3 is applied conservatively by checking both each available beam-side "
            "Column Face and the h/2 critical section measured outward from that face; the more severe result governs. "
            "The beam-column joint/support-footprint D-region itself remains outside this sectional check and does not reduce a completed "
            "sectional PASS to REVIEW. Exact Precast physical-joint shear transfer, post-tensioning anchorage/end zones, hanger reinforcement, "
            "anchorage/development, torsion, combined V+T, fatigue, and seismic detailing remain separate. "
            "The ACI 22.5.6.2 PASS route requires fully transferred effective prestress and the prestress-dominance applicability gate; "
            "refined Vci/Vcw is not synthesized from incomplete load-stage sources."
        ),
    }
