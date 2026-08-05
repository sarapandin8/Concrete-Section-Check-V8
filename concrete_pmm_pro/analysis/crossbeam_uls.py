"""Production ULS flexure route for Portal Frame Prestressed Crossbeams.

The adapter rebuilds the active Section, material, ordinary reinforcement,
bonded tendon geometry, effective prestress, and row-coupled ULS demand at
every imported or generated check station.  Crossbeam flexural strength is
solved directly on the exact P-M3 axis using ACI 318-19 strain compatibility
and an adaptive ``phi*Pn(c) = Pu`` root; the generic biaxial PMM surface used
by other member workflows is not called or modified.

For Precast Segmental construction, ordinary longitudinal reinforcement
receives strength credit only in fully developed Segment interiors.  Physical
joints and conservative straight-bar development zones use bonded-tendon
continuity without ordinary-rebar flexural credit.  Cast-in-Place zones retain
monolithic reinforcement behavior.

Internal units remain mm, MPa, N, and N-mm. Imported Crossbeam ``M3`` is the
sagging-positive moment in the member s-vertical plane and maps to section
``Mx`` because the section x-axis is transverse and y is vertical.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any

from concrete_pmm_pro.analysis.crossbeam_flexure_uniaxial import (
    crossbeam_uniaxial_axial_dcr,
    solve_crossbeam_uniaxial_flexure,
)
from concrete_pmm_pro.analysis.runtime import accuracy_preset_resolution
from concrete_pmm_pro.core.analysis import AnalysisInput, AnalysisSettings
from concrete_pmm_pro.core.concrete_materials import concrete_materials_by_name
from concrete_pmm_pro.core.design_code import PROJECT_CODE_ACI318
from concrete_pmm_pro.core.models import (
    ConcreteMaterial,
    LoadCase,
    PrestressElement,
    PrestressSteelMaterial,
    Rebar,
    RebarMaterial,
)
from concrete_pmm_pro.crossbeam.cip_rebar_templates import (
    CIP_RB_TEMPLATE_ROWS_KEY,
    CIP_RB_ZONE_ROWS_KEY,
    CIP_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    CONSTRUCTION_METHOD_PRECAST,
    normalize_construction_method,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.project_geometry import crossbeam_project_geometry_audit
from concrete_pmm_pro.crossbeam.rebar import (
    cage_relative_longitudinal_center_offset_mm,
    canonical_rebar_templates,
    canonical_rebar_zones,
    rebar_diameter_mm,
    template_map,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
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
    TENDON_BOND_STATE_UNBONDED,
    canonical_tendon_system_rows,
    segment_joint_stations,
    station_section_contexts,
    tendon_positions_at_station,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import (
    CB_PROFILE_ROWS_KEY,
    CB_TENDON_SYSTEM_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.uls_rebar_source import build_crossbeam_uls_rebar_source_contract
from concrete_pmm_pro.crossbeam.uls_station_geometry import (
    canonical_pt_end_zone_settings,
    end_zone_exclusion_record,
    generate_support_check_demands,
    interior_location_type,
    pt_end_zone_side,
    station_inside_support_interior,
    support_footprints_from_state,
)
from concrete_pmm_pro.crossbeam.transverse import (
    build_transverse_cage_geometry,
    canonical_transverse_templates,
    place_longitudinal_bars_relative_to_cages,
    transverse_bar_diameter_mm,
    transverse_template_map,
)
from concrete_pmm_pro.geometry.rebar_layout import (
    PerimeterRebarLayoutResult,
    generate_inner_face_rebar_layout,
    generate_perimeter_rebar_layout,
)
from concrete_pmm_pro.geometry.summary import to_shapely_polygon


CROSSBEAM_ULS_RESULT_KEY = "crossbeam_analysis1a_uls_flexure_result"
CROSSBEAM_ULS_RESULT_HASH_KEY = "crossbeam_analysis1a_uls_flexure_input_hash"
CROSSBEAM_ULS_LOAD_TABLE_KEY = "crossbeam_uls_loads_table"
CROSSBEAM_LENGTH_KEY = "crossbeam_ui1_length_m"
CROSSBEAM_SEGMENT_ROWS_KEY = "crossbeam_ui1_segment_layout_rows"
_ZERO_M3_TOLERANCE_KNM = 1.0e-9


@dataclass(frozen=True)
class PreparedCrossbeamUlsRow:
    station_m: float
    check_point: str
    case_name: str
    section_face: str
    location_type: str
    segment_id: str
    section_id: str
    rebar_zone_id: str
    rebar_template_id: str
    source_p_kn: float
    source_v2_kn: float
    source_t_knm: float
    source_m3_knm: float
    ordinary_rebar_count: int
    ordinary_rebar_area_mm2: float
    bonded_tendon_count: int
    bonded_tendon_area_mm2: float
    omitted_unbonded_tendon_count: int
    development_length_m: float
    distance_to_nearest_segment_end_m: float
    rebar_credit_status: str
    development_region: str
    demand_source: str
    source_station_1_m: float | None
    source_station_2_m: float | None
    source_ratio: float | None
    extrapolation_ratio: float | None
    analysis_input: AnalysisInput
    capacity_signature: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrossbeamUlsPreparation:
    ready: bool
    rows: tuple[PreparedCrossbeamUlsRow, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    info: tuple[str, ...]
    fingerprint: str
    demand_rows: tuple[dict[str, Any], ...]
    derived_support_rows: tuple[dict[str, Any], ...] = ()
    support_footprints: tuple[dict[str, Any], ...] = ()
    excluded_end_zone_rows: tuple[dict[str, Any], ...] = ()
    pt_end_zone_settings: Mapping[str, Any] = field(default_factory=dict)
    member_length_m: float = 0.0


@dataclass(frozen=True)
class ZeroMomentDirectionReference:
    sign: float
    station_m: float
    source_m3_knm: float


def _get(state: Any, key: str, default: Any = None) -> Any:
    if hasattr(state, "get"):
        return state.get(key, default)
    return getattr(state, key, default)


def _records(value: Any) -> list[dict[str, Any]]:
    if hasattr(value, "to_dict"):
        try:
            return [dict(row) for row in value.to_dict(orient="records")]
        except Exception:
            return []
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _dedupe(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(str(message).strip() for message in messages if str(message).strip()))


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


def _fingerprint(value: Any) -> str:
    payload = json.dumps(_hashable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _without_runtime_ids(value: Any) -> Any:
    """Remove generated model UUIDs from a solver-capacity fingerprint.

    Rebar and prestress Pydantic models create UUIDs when they are rebuilt.
    Those identifiers are not engineering inputs; retaining them would make a
    Streamlit rerun look stale even when Section/Rebar/Tendon sources did not
    change, and it would prevent identical station capacities from sharing one
    direct section solve.
    """

    if isinstance(value, Mapping):
        return {
            str(key): _without_runtime_ids(item)
            for key, item in value.items()
            if str(key) != "id"
        }
    if isinstance(value, (list, tuple)):
        return [_without_runtime_ids(item) for item in value]
    return value


def _nearest_nonzero_m3_reference(
    row: PreparedCrossbeamUlsRow,
    rows: tuple[PreparedCrossbeamUlsRow, ...],
) -> ZeroMomentDirectionReference | None:
    """Resolve a zero-M3 bending side from the same Load Case only.

    A zero moment has no mathematical direction, but section capacity at the
    same Pu still exists.  The nearest nonzero station in the same imported
    Load Case provides only the sign used to select the direct-solver bending direction; its
    moment magnitude is never substituted into demand. Generated joint or
    development-boundary checks must not displace a nearer imported station as
    the direction source.
    """

    candidates = [
        candidate
        for candidate in rows
        if candidate.case_name == row.case_name
        and abs(float(candidate.source_m3_knm)) > _ZERO_M3_TOLERANCE_KNM
    ]
    if not candidates:
        return None
    imported_candidates = [candidate for candidate in candidates if candidate.demand_source == "IMPORTED"]
    if imported_candidates:
        candidates = imported_candidates
    reference = min(
        candidates,
        key=lambda candidate: (
            abs(float(candidate.station_m) - float(row.station_m)),
            float(candidate.station_m),
            str(candidate.check_point),
            str(candidate.section_face),
        ),
    )
    source_m3 = float(reference.source_m3_knm)
    return ZeroMomentDirectionReference(
        sign=-1.0 if source_m3 < 0.0 else 1.0,
        station_m=float(reference.station_m),
        source_m3_knm=source_m3,
    )


def _analysis_settings(state: Any) -> AnalysisSettings:
    source = _get(state, "analysis_settings")
    if isinstance(source, AnalysisSettings):
        settings = source
    elif isinstance(source, Mapping):
        settings = AnalysisSettings.model_validate(source)
    else:
        settings = AnalysisSettings()
    preset = str(_get(state, "crossbeam_flexure_accuracy_preset", "High Accuracy") or "High Accuracy")
    try:
        resolution = accuracy_preset_resolution(preset)
    except Exception:
        resolution = {
            "neutral_axis_angle_steps": settings.neutral_axis_angle_steps,
            "neutral_axis_depth_steps": settings.neutral_axis_depth_steps,
        }
    return settings.model_copy(
        update={
            "code": PROJECT_CODE_ACI318,
            "strength_load_type": "ULS",
            "include_rebars": True,
            "include_prestress": True,
            "use_phi_factor": True,
            "compression_positive": True,
            "neutral_axis_angle_steps": int(resolution["neutral_axis_angle_steps"]),
            "neutral_axis_depth_steps": int(resolution["neutral_axis_depth_steps"]),
        }
    )


_ACI_DEV_FC_MAX_MPA = 70.0
_DEV_EXTRAPOLATION_LIMIT_RATIO = 1.0


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return float(default)
    return numeric if math.isfinite(numeric) else float(default)


def _segment_bounds(context: Mapping[str, Any]) -> tuple[float, float]:
    start = _finite_float(context.get("s_start_m"), 0.0)
    end = _finite_float(context.get("s_end_m"), start)
    return (min(start, end), max(start, end))


def _aci_conservative_development_length_mm(
    longitudinal: Mapping[str, Any] | None,
    *,
    fc_mpa: float,
) -> float:
    """Return a conservative straight-bar tension development length.

    Portal Frame Precast Segmental uses ACI 318-19 Table 25.4.2.3 ``Other
    cases`` without confinement credit.  All bars are conservatively treated
    with the top-cast factor psi_t=1.3; uncoated normalweight reinforcement is
    assumed from the current project inputs.  The result is the maximum of the
    active outer/inner bar systems and 300 mm.  This gate controls *strength
    credit only*; it does not replace final bar anchorage detailing.
    """

    if not longitudinal or not bool(longitudinal.get("Active", True)):
        return 0.0
    if not bool(longitudinal.get("Credit inside segment", True)):
        return 0.0
    fy = max(_finite_float(longitudinal.get("fy MPa"), 390.0), 1.0)
    if fy <= 420.0 + 1.0e-9:
        psi_g = 1.0
    elif fy <= 550.0 + 1.0e-9:
        psi_g = 1.15
    else:
        psi_g = 1.30
    psi_t = 1.30
    psi_e = 1.0
    lambda_factor = 1.0
    sqrt_fc = math.sqrt(max(min(float(fc_mpa), _ACI_DEV_FC_MAX_MPA), 1.0e-9))
    candidates: list[float] = []
    for enabled_key, size_key in (
        ("Outer face bars", "Outer bar size"),
        ("Inner face bars", "Inner bar size"),
    ):
        if not bool(longitudinal.get(enabled_key)):
            continue
        db = rebar_diameter_mm(str(longitudinal.get(size_key) or "DB16"))
        # Table 25.4.2.3: No.19 and smaller use 1.4 for "Other cases";
        # larger bars use 1.1.  A 20 mm custom/metric bar is conservatively
        # classified in the larger-bar column.
        denominator = 1.4 if db <= 19.1 + 1.0e-9 else 1.1
        ld = fy * psi_t * psi_e * psi_g * db / (denominator * lambda_factor * sqrt_fc)
        candidates.append(max(300.0, ld))
    return max(candidates, default=0.0)


def _development_credit_context(
    *,
    construction_method: str,
    station_m: float,
    context: Mapping[str, Any],
    longitudinal: Mapping[str, Any] | None,
    concrete: ConcreteMaterial,
    at_joint: bool,
) -> tuple[bool, float, float, str, str]:
    """Return binary ordinary-rebar flexural credit for one section context."""

    if construction_method != CONSTRUCTION_METHOD_PRECAST:
        return True, 0.0, float("inf"), "FULL CREDIT", "CIP / monolithic zone"
    start, end = _segment_bounds(context)
    distance = max(0.0, min(float(station_m) - start, end - float(station_m)))
    ld_m = _aci_conservative_development_length_mm(longitudinal, fc_mpa=concrete.fc_MPa) / 1000.0
    tolerance = max(1.0e-7, max(end - start, 1.0) * 1.0e-9)
    if at_joint:
        return False, ld_m, 0.0, "NO CREDIT", "PHYSICAL JOINT"
    if ld_m <= tolerance:
        return True, 0.0, distance, "FULL CREDIT", "NO ACTIVE STRENGTH-CREDIT BAR SYSTEM"
    if end - start <= 2.0 * ld_m + tolerance:
        return False, ld_m, distance, "NO CREDIT", "SEGMENT SHORTER THAN TWO DEVELOPMENT LENGTHS"
    if distance <= ld_m + tolerance:
        region = "LEFT DEVELOPMENT ZONE" if abs(float(station_m) - start) <= abs(end - float(station_m)) else "RIGHT DEVELOPMENT ZONE"
        return False, ld_m, distance, "NO CREDIT", region
    return True, ld_m, distance, "FULL CREDIT", "FULLY DEVELOPED INTERIOR"


def _unique_demand_at_station(
    rows: list[dict[str, Any]],
    *,
    station_m: float,
    tolerance: float,
) -> tuple[dict[str, Any] | None, str | None]:
    candidates = [
        row for row in rows
        if abs(_finite_float(row.get("Station s (m)"), float("nan")) - station_m) <= tolerance
    ]
    if not candidates:
        return None, None
    reference = dict(candidates[0])
    for other in candidates[1:]:
        if any(abs(_finite_float(other.get(field)) - _finite_float(reference.get(field))) > 1.0e-8 for field in ("P", "V2", "T", "M3")):
            return None, f"multiple non-identical row-coupled demands exist at s = {station_m:.6f} m."
    return reference, None


def _recover_demand_within_segment(
    *,
    case_rows: list[dict[str, Any]],
    target_m: float,
    segment_start_m: float,
    segment_end_m: float,
    tolerance: float,
    allow_exact_unlabelled: bool = True,
) -> tuple[dict[str, Any] | None, str | None, str]:
    """Recover P/V2/T/M3 with one common ratio and no cross-joint mixing."""

    if allow_exact_unlabelled:
        exact, error = _unique_demand_at_station(case_rows, station_m=target_m, tolerance=tolerance)
        if error:
            return None, error, ""
        if exact is not None:
            exact.update({
                "__Demand source": "EXACT",
                "__Source station 1 (m)": target_m,
                "__Source station 2 (m)": target_m,
                "__Source ratio": 0.0,
                "__Extrapolation ratio": 0.0,
            })
            return exact, None, f"Exact row-coupled source at s = {target_m:.6f} m."

    lower_bound = min(segment_start_m, segment_end_m)
    upper_bound = max(segment_start_m, segment_end_m)
    eligible = [
        dict(row) for row in case_rows
        if lower_bound - tolerance <= _finite_float(row.get("Station s (m)"), float("nan")) <= upper_bound + tolerance
        and abs(_finite_float(row.get("Station s (m)"), float("nan")) - target_m) > tolerance
    ]
    by_station: dict[float, list[dict[str, Any]]] = {}
    for row in eligible:
        x = _finite_float(row.get("Station s (m)"), float("nan"))
        if math.isfinite(x):
            by_station.setdefault(round(x, 9), []).append(row)
    unique: list[dict[str, Any]] = []
    for key in sorted(by_station):
        selected, error = _unique_demand_at_station(by_station[key], station_m=float(key), tolerance=tolerance)
        if error:
            return None, error, ""
        if selected is not None:
            unique.append(selected)
    if len(unique) < 2:
        return None, "at least two row-coupled source stations are required inside the adjacent Segment.", ""

    below = [row for row in unique if _finite_float(row.get("Station s (m)")) < target_m - tolerance]
    above = [row for row in unique if _finite_float(row.get("Station s (m)")) > target_m + tolerance]
    method = "INTERPOLATED"
    if below and above:
        lo = max(below, key=lambda row: _finite_float(row.get("Station s (m)")))
        hi = min(above, key=lambda row: _finite_float(row.get("Station s (m)")))
    elif not below:
        lo, hi = unique[0], unique[1]
        method = "EXTRAPOLATED"
    else:
        lo, hi = unique[-2], unique[-1]
        method = "EXTRAPOLATED"
    x0 = _finite_float(lo.get("Station s (m)"), float("nan"))
    x1 = _finite_float(hi.get("Station s (m)"), float("nan"))
    if not math.isfinite(x0) or not math.isfinite(x1) or x1 <= x0 + tolerance:
        return None, "invalid one-sided source bracket.", ""
    ratio = (target_m - x0) / (x1 - x0)
    extrapolation = 0.0
    if method == "EXTRAPOLATED":
        extrapolation = min(abs(target_m - x0), abs(target_m - x1)) / (x1 - x0)
        if extrapolation > _DEV_EXTRAPOLATION_LIMIT_RATIO + 1.0e-12:
            return None, (
                f"one-sided extrapolation requires {100.0 * extrapolation:.1f}% of source spacing, "
                f"exceeding the {100.0 * _DEV_EXTRAPOLATION_LIMIT_RATIO:.0f}% limit."
            ), ""
    derived = {
        "Active": True,
        "Station s (m)": target_m,
        "Case Name": str(lo.get("Case Name") or hi.get("Case Name") or "ULS"),
        "P": _finite_float(lo.get("P")) + ratio * (_finite_float(hi.get("P")) - _finite_float(lo.get("P"))),
        "V2": _finite_float(lo.get("V2")) + ratio * (_finite_float(hi.get("V2")) - _finite_float(lo.get("V2"))),
        "T": _finite_float(lo.get("T")) + ratio * (_finite_float(hi.get("T")) - _finite_float(lo.get("T"))),
        "M3": _finite_float(lo.get("M3")) + ratio * (_finite_float(hi.get("M3")) - _finite_float(lo.get("M3"))),
        "__Demand source": method,
        "__Source station 1 (m)": x0,
        "__Source station 2 (m)": x1,
        "__Source ratio": ratio,
        "__Extrapolation ratio": extrapolation,
    }
    note = (
        f"Row-coupled {method.lower()} source from s = {x0:.6f} and {x1:.6f} m "
        f"(r = {ratio:.6f})."
    )
    return derived, None, note


def _derived_crossbeam_flexure_demands(
    *,
    active_demands: list[dict[str, Any]],
    segment_rows: list[dict[str, Any]],
    definitions_by_id: Mapping[str, Mapping[str, Any]],
    material_by_name: Mapping[str, ConcreteMaterial],
    zones: list[dict[str, Any]],
    templates_by_id: Mapping[str, Mapping[str, Any]],
    member_length_m: float,
    construction_method: str,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Generate physical-joint sides and development-boundary demand checks."""

    if construction_method != CONSTRUCTION_METHOD_PRECAST:
        return [], [], []
    tolerance = max(1.0e-7, member_length_m * 1.0e-9)
    ordered = sorted(
        [dict(row) for row in segment_rows],
        key=lambda row: _finite_float(row.get("s_start (m)", row.get("x_start_m")), float("inf")),
    )
    cases: dict[str, list[dict[str, Any]]] = {}
    for row in active_demands:
        cases.setdefault(str(row.get("Case Name") or "ULS"), []).append(row)
    output: list[dict[str, Any]] = []
    errors: list[str] = []
    info: list[str] = []

    # Exact one-sided physical-joint checks.  Flexural P/M are ordinarily
    # continuous, so an exact unlabelled row may serve both faces; otherwise
    # each face is recovered only from rows owned by its adjacent Segment.
    for index in range(len(ordered) - 1):
        left = ordered[index]
        right = ordered[index + 1]
        joint = _finite_float(left.get("s_end (m)", left.get("x_end_m")), float("nan"))
        right_start = _finite_float(right.get("s_start (m)", right.get("x_start_m")), float("nan"))
        if not math.isfinite(joint) or not math.isfinite(right_start) or abs(joint - right_start) > tolerance:
            continue
        joint_id = f"J{index + 1}"
        for case_name, case_rows in cases.items():
            exact, exact_error = _unique_demand_at_station(case_rows, station_m=joint, tolerance=tolerance)
            if exact_error:
                errors.append(f"{case_name} · {joint_id}: {exact_error}")
                continue
            shared_source: dict[str, Any] | None = None
            shared_error: str | None = None
            shared_note = ""
            if exact is not None:
                shared_source = dict(exact)
                shared_source.update({
                    "__Demand source": "EXACT SHARED JOINT",
                    "__Source station 1 (m)": joint,
                    "__Source station 2 (m)": joint,
                    "__Source ratio": 0.0,
                    "__Extrapolation ratio": 0.0,
                })
                shared_note = f"Exact row-coupled physical-joint source at s = {joint:.6f} m."
            else:
                # P and M3 are global member resultants and remain continuous
                # across an internal construction joint unless an explicit
                # concentrated member action is present.  Recover one shared
                # row-coupled FEA state from the nearest bracketing stations;
                # the left/right capacities remain independently one-sided.
                shared_source, shared_error, shared_note = _recover_demand_within_segment(
                    case_rows=case_rows,
                    target_m=joint,
                    segment_start_m=0.0,
                    segment_end_m=member_length_m,
                    tolerance=tolerance,
                    allow_exact_unlabelled=False,
                )
                if shared_source is not None:
                    shared_source["__Demand source"] = f"SHARED JOINT {shared_source.get('__Demand source') or 'RECOVERED'}"
                    shared_note = (
                        f"Shared row-coupled member-force source at the physical joint; "
                        f"left/right section capacities remain one-sided. {shared_note}"
                    )
            if shared_error or shared_source is None:
                errors.append(f"{case_name} · {joint_id}: {shared_error}")
                continue
            for side_label, segment in (("L", left), ("R", right)):
                source = dict(shared_source)
                note = shared_note
                source.update({
                    "Active": True,
                    "Station s (m)": joint,
                    "Check Point": f"{joint_id}-{side_label}",
                    "Case Name": case_name,
                    "Note": note,
                    "__Derived flexure check": True,
                    "__Flexure check type": "PHYSICAL JOINT SIDE",
                    "__Joint side": side_label,
                    "__Segment override": str(segment.get("Segment") or ""),
                })
                output.append(source)

    # ACI conservative binary development gate transition checks.
    for segment in ordered:
        segment_id = str(segment.get("Segment") or "")
        start = _finite_float(segment.get("s_start (m)", segment.get("x_start_m")), float("nan"))
        end = _finite_float(segment.get("s_end (m)", segment.get("x_end_m")), float("nan"))
        section_id = str(segment.get("Section ID") or "")
        definition = definitions_by_id.get(section_id)
        if definition is None or not math.isfinite(start) or not math.isfinite(end) or end <= start + tolerance:
            continue
        material = material_by_name.get(str(definition.get("Material") or ""))
        if material is None:
            continue
        zone_candidates = [
            zone for zone in zones
            if str(zone.get("Segment") or "") == segment_id
        ]
        if not zone_candidates:
            continue
        zone = zone_candidates[0]
        template_id = str(zone.get("Longitudinal template") or zone.get("Rebar template") or "")
        ld_m = _aci_conservative_development_length_mm(
            templates_by_id.get(template_id),
            fc_mpa=material.fc_MPa,
        ) / 1000.0
        if ld_m <= tolerance:
            continue
        targets: list[tuple[str, float]] = []
        if start + ld_m < end - tolerance:
            targets.append(("L", start + ld_m))
        if end - ld_m > start + tolerance and abs((end - ld_m) - (start + ld_m)) > tolerance:
            targets.append(("R", end - ld_m))
        for side_label, target in targets:
            for case_name, case_rows in cases.items():
                source, error, note = _recover_demand_within_segment(
                    case_rows=case_rows,
                    target_m=target,
                    segment_start_m=start,
                    segment_end_m=end,
                    tolerance=tolerance,
                )
                if error or source is None:
                    errors.append(f"{case_name} · {segment_id}-{side_label} development boundary: {error}")
                    continue
                source.update({
                    "Active": True,
                    "Station s (m)": target,
                    "Check Point": f"{segment_id}-{side_label} ld",
                    "Case Name": case_name,
                    "Note": note,
                    "__Derived flexure check": True,
                    "__Flexure check type": "DEVELOPMENT BOUNDARY",
                    "__Segment override": segment_id,
                })
                output.append(source)
    output.sort(key=lambda row: (str(row.get("Case Name") or ""), _finite_float(row.get("Station s (m)")), str(row.get("Check Point") or "")))
    info.append(f"Generated {sum(str(row.get('__Flexure check type')) == 'PHYSICAL JOINT SIDE' for row in output)} physical-joint side check(s).")
    info.append(f"Generated {sum(str(row.get('__Flexure check type')) == 'DEVELOPMENT BOUNDARY' for row in output)} development-boundary check(s).")
    return output, _dedupe(errors), _dedupe(info)


def _material_library(state: Any) -> dict[str, ConcreteMaterial]:
    materials: list[ConcreteMaterial] = []
    for raw in list(_get(state, "concrete_materials", []) or []):
        try:
            materials.append(raw if isinstance(raw, ConcreteMaterial) else ConcreteMaterial.model_validate(raw))
        except Exception:
            continue
    primary = _get(state, "concrete_material")
    try:
        if primary is not None:
            item = primary if isinstance(primary, ConcreteMaterial) else ConcreteMaterial.model_validate(primary)
            if item.name not in {material.name for material in materials}:
                materials.append(item)
    except Exception:
        pass
    return concrete_materials_by_name(materials)


def _load_source_for_method(state: Any, construction_method: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if construction_method == CONSTRUCTION_METHOD_CIP:
        return (
            canonical_rebar_templates(_records(_get(state, CIP_RB_TEMPLATE_ROWS_KEY, []))),
            canonical_rebar_zones(_records(_get(state, CIP_RB_ZONE_ROWS_KEY, []))),
            canonical_transverse_templates(_records(_get(state, CIP_TR_TEMPLATE_ROWS_KEY, []))),
        )
    return (
        canonical_rebar_templates(_records(_get(state, CB_RB_TEMPLATE_ROWS_KEY, []))),
        canonical_rebar_zones(_records(_get(state, CB_RB_ZONE_ROWS_KEY, []))),
        canonical_transverse_templates(_records(_get(state, CB_TR_TEMPLATE_ROWS_KEY, []))),
    )


def _result_rebars(result: PerimeterRebarLayoutResult, *, layer: str) -> list[Rebar]:
    if result.table.empty:
        return []
    rows: list[Rebar] = []
    for source in result.table.to_dict(orient="records"):
        try:
            rows.append(
                Rebar(
                    x_mm=float(source["x_mm"]),
                    y_mm=float(source["y_mm"]),
                    diameter_mm=float(source["Diameter_mm"]),
                    material_name=str(source.get("Material") or "SD40"),
                    label=f"{layer}: {source.get('Label') or ''}",
                )
            )
        except Exception:
            continue
    return rows


def _generate_rebars(
    geometry: Any,
    definition: Mapping[str, Any],
    longitudinal: Mapping[str, Any] | None,
    transverse: Mapping[str, Any] | None,
    *,
    allow_credit: bool,
) -> tuple[list[Rebar], list[RebarMaterial], list[str], list[str]]:
    if not allow_credit or not longitudinal:
        return [], [], [], []
    errors: list[str] = []
    warnings: list[str] = []
    if not bool(longitudinal.get("Active", True)):
        return [], [], ["Assigned longitudinal template is inactive."], []
    if not bool(longitudinal.get("Credit inside segment", True)):
        return [], [], [], ["Assigned longitudinal template is local/detailing-only and receives no ULS flexure credit."]
    if not transverse:
        return [], [], ["Assigned transverse template is unavailable; cage-relative longitudinal coordinates cannot be built."], []
    cages = build_transverse_cage_geometry(geometry, definition, transverse)
    errors.extend(str(item) for item in cages.errors)
    warnings.extend(str(item) for item in cages.warnings)
    transverse_diameter = transverse_bar_diameter_mm(transverse.get("Bar size"))
    transverse_offset = float(transverse.get("Center offset mm") or 50.0)
    material = str(longitudinal.get("Rebar material") or "SD40")
    rebars: list[Rebar] = []

    if bool(longitudinal.get("Outer face bars")):
        bar_size = str(longitudinal.get("Outer bar size") or "DB16")
        diameter = rebar_diameter_mm(bar_size)
        offset = cage_relative_longitudinal_center_offset_mm(transverse_offset, transverse_diameter, diameter)
        outer_result = generate_perimeter_rebar_layout(
            geometry,
            bar_size=bar_size,
            diameter_mm=diameter,
            material=material,
            edge_offset_mm=offset,
            target_spacing_mm=float(longitudinal.get("Outer target spacing mm") or 150.0),
            min_bars=4,
            exact_bar_count=(
                int(longitudinal.get("Outer exact bar count") or 0)
                if str(longitudinal.get("Outer layout method")) == "By exact bar count"
                else None
            ),
            label_prefix="O",
        )
        errors.extend(str(item) for item in outer_result.errors)
        warnings.extend(str(item) for item in outer_result.warnings)
        if outer_result.ok:
            rebars.extend(place_longitudinal_bars_relative_to_cages(cages, _result_rebars(outer_result, layer="Outer")).rebars)

    role = str(definition.get("Section role") or "Solid")
    if role == "Hollow" and bool(longitudinal.get("Inner face bars")):
        bar_size = str(longitudinal.get("Inner bar size") or "DB16")
        diameter = rebar_diameter_mm(bar_size)
        offset = cage_relative_longitudinal_center_offset_mm(transverse_offset, transverse_diameter, diameter)
        inner_result = generate_inner_face_rebar_layout(
            geometry,
            hole_index=0,
            bar_size=bar_size,
            diameter_mm=diameter,
            material=material,
            edge_offset_mm=offset,
            target_spacing_mm=float(longitudinal.get("Inner target spacing mm") or 150.0),
            min_bars=4,
            exact_bar_count=(
                int(longitudinal.get("Inner exact bar count") or 0)
                if str(longitudinal.get("Inner layout method")) == "By exact bar count"
                else None
            ),
            label_prefix="I",
        )
        errors.extend(str(item) for item in inner_result.errors)
        warnings.extend(str(item) for item in inner_result.warnings)
        if inner_result.ok:
            rebars.extend(place_longitudinal_bars_relative_to_cages(cages, _result_rebars(inner_result, layer="Inner")).rebars)

    fy = float(longitudinal.get("fy MPa") or 390.0)
    rebar_materials = [RebarMaterial(name=material, fy_MPa=fy, Es_MPa=200000.0)] if rebars else []
    return list(rebars), rebar_materials, _dedupe(errors), _dedupe(warnings)


def _explicit_side(check_point: str) -> str | None:
    text = str(check_point or "").strip().casefold().replace("−", "-")
    if "left" in text or "s-" in text:
        return "left"
    if "right" in text or "s+" in text:
        return "right"
    return None


def _context_face(context: Mapping[str, Any], *, at_joint: bool) -> str:
    face = str(context.get("Station face") or "")
    if not at_joint:
        return "INTERIOR"
    if face == "Right end":
        return "LEFT LIMIT (s-)"
    if face == "Left end":
        return "RIGHT LIMIT (s+)"
    return "JOINT LIMIT"


def _select_contexts(contexts: list[dict[str, Any]], *, check_point: str, at_joint: bool) -> list[dict[str, Any]]:
    side = _explicit_side(check_point)
    if at_joint and side:
        desired = "Right end" if side == "left" else "Left end"
        selected = [item for item in contexts if str(item.get("Station face")) == desired]
        if selected:
            return selected
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in contexts:
        key = (str(item.get("Section ID") or ""), _context_face(item, at_joint=at_joint))
        unique.setdefault(key, item)
    if at_joint and len({str(item.get("Section ID") or "") for item in unique.values()}) == 1:
        return [next(iter(unique.values()))]
    return list(unique.values())


def _zones_for_context(
    zones: list[dict[str, Any]],
    *,
    station_m: float,
    segment_id: str,
    check_point: str,
    length_m: float,
) -> list[dict[str, Any]]:
    tolerance = max(1.0e-7, length_m * 1.0e-9)
    candidates = [
        row
        for row in zones
        if str(row.get("Segment") or "") == segment_id
        and float(row.get("s_start_m") or 0.0) - tolerance <= station_m
        <= float(row.get("s_end_m") or 0.0) + tolerance
    ]
    side = _explicit_side(check_point)
    if len(candidates) > 1 and side == "left":
        return [min(candidates, key=lambda row: float(row.get("s_end_m") or 0.0))]
    if len(candidates) > 1 and side == "right":
        return [max(candidates, key=lambda row: float(row.get("s_start_m") or 0.0))]
    unique: dict[str, dict[str, Any]] = {}
    for row in candidates:
        unique.setdefault(str(row.get("Longitudinal template") or row.get("Rebar template") or ""), row)
    return list(unique.values())


def _prestress_at_station(
    *,
    station_m: float,
    length_m: float,
    geometry: Any,
    system_rows: list[dict[str, Any]],
    profile_rows: Any,
    fpe_mpa: float,
) -> tuple[list[PrestressElement], list[PrestressSteelMaterial], int, list[str], list[str]]:
    positions = {
        str(row.get("Tendon ID") or ""): row
        for row in tendon_positions_at_station(
            profile_rows,
            system_rows,
            station_m=station_m,
            length_m=length_m,
            active_only=True,
        )
    }
    polygon = to_shapely_polygon(geometry)
    y_top = float(polygon.bounds[3])
    elements: list[PrestressElement] = []
    materials: dict[str, PrestressSteelMaterial] = {}
    errors: list[str] = []
    warnings: list[str] = []
    omitted_unbonded = 0
    for tendon in system_rows:
        if not bool(tendon.get("Active", True)):
            continue
        tendon_id = str(tendon.get("Tendon ID") or "")
        bond_state = str(tendon.get("Bond state") or "")
        if bond_state == TENDON_BOND_STATE_UNBONDED:
            omitted_unbonded += 1
            continue
        if bond_state != TENDON_BOND_STATE_BONDED:
            errors.append(f"{tendon_id or 'Unnamed tendon'}: final bond system is not specified for ULS section-strain compatibility.")
            continue
        position = positions.get(tendon_id)
        if position is None:
            errors.append(f"{tendon_id}: Tendon Profile does not cover s = {station_m:.6f} m.")
            continue
        x_mm = float(position.get("x lateral (mm)") or 0.0)
        y_mm = y_top - float(position.get("dtop (mm)") or 0.0)
        from shapely.geometry import Point

        if not polygon.covers(Point(x_mm, y_mm)):
            errors.append(f"{tendon_id}: tendon center is outside Section ID geometry at s = {station_m:.6f} m.")
            continue
        strands = int(tendon.get("Strands") or 0)
        aps_per_strand = float(tendon.get("Aps/strand mm²") or 0.0)
        area = strands * aps_per_strand
        fpu = float(tendon.get("fpu MPa") or 0.0)
        if area <= 0.0 or fpu <= 0.0 or fpe_mpa <= 0.0:
            errors.append(f"{tendon_id}: Aps, fpu, and effective stress must be positive.")
            continue
        if fpe_mpa >= fpu:
            errors.append(
                f"{tendon_id}: adopted average effective stress {fpe_mpa:,.3f} MPa "
                f"must be lower than fpu = {fpu:,.3f} MPa."
            )
            continue
        ep = 195000.0
        fpy = 0.90 * fpu
        material_name = f"Crossbeam PT {fpu:g}"
        materials.setdefault(
            material_name,
            PrestressSteelMaterial(
                name=material_name,
                steel_type="strand",
                fpy_MPa=fpy,
                fpu_MPa=fpu,
                Ep_MPa=ep,
                relaxation_class="low-relaxation",
                source="Crossbeam Tendon System",
            ),
        )
        elements.append(
            PrestressElement(
                x_mm=x_mm,
                y_mm=y_mm,
                area_mm2=area,
                steel_type="tendon_group",
                material_name=material_name,
                fpy_mpa=fpy,
                fpu_mpa=fpu,
                ep_mpa=ep,
                pe_eff_n=area * fpe_mpa,
                bonded=True,
                count=1,
                initial_stress_mpa=fpe_mpa,
                initial_strain=fpe_mpa / ep,
                label=tendon_id,
            )
        )
    if omitted_unbonded:
        warnings.append(
            f"{omitted_unbonded} permanently unbonded/external tendon(s) are excluded from the current section-strain flexure route; PASS is downgraded to REVIEW."
        )
    return elements, list(materials.values()), omitted_unbonded, _dedupe(errors), _dedupe(warnings)


def build_crossbeam_uls_flexure_preparation(
    state: Any,
    *,
    station_rows_are_pre_routed: bool = False,
) -> CrossbeamUlsPreparation:
    """Return validated station-specific AnalysisInput rows for Crossbeam ULS flexure."""

    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    length_m = float(_get(state, CROSSBEAM_LENGTH_KEY, 0.0) or 0.0)
    if length_m <= 0.0:
        errors.append("Crossbeam physical length L must be positive.")

    contract = canonical_station_force_contract(
        _get(state, CB_STATION_FORCE_CONTRACT_KEY, {}),
        effective_prestress_link=_get(state, CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY, {}),
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
        member_length_m=max(length_m, 0.0),
        response_type="ULS",
        rows_are_canonical=True,
    )
    errors.extend(validation.errors)
    warnings.extend(validation.warnings)
    active_demands = [row for row in demand_rows if bool(row.get("Active", True))]

    segment_rows = _records(_get(state, CROSSBEAM_SEGMENT_ROWS_KEY, []))
    definitions = canonical_section_definitions(_get(state, CB_SECLIB_DEFINITIONS_KEY, []))
    definition_by_id = definition_map(definitions)
    if not segment_rows:
        errors.append("Crossbeam Segment / Zone Layout is missing.")
    if not definitions:
        errors.append("Crossbeam Section Library is missing.")

    construction_method = normalize_construction_method(
        _get(state, CB_LOSS_ES_CONSTRUCTION_METHOD_KEY, CONSTRUCTION_METHOD_PRECAST)
    )
    support_footprints, support_geometry_errors = support_footprints_from_state(
        state,
        member_length_m=max(length_m, 0.0),
        segment_rows=segment_rows,
    )
    errors.extend(support_geometry_errors)
    for footprint in support_footprints:
        if str(footprint.get("Status") or "") != "COMPATIBLE":
            errors.append(
                f"{footprint.get('Column') or 'Column / Support'}: support-footprint source is not compatible — "
                f"{footprint.get('Issue') or 'review the applied Column / Support Layout.'}"
            )
    pt_end_zone = canonical_pt_end_zone_settings(
        state,
        member_length_m=max(length_m, 0.0),
        segment_rows=segment_rows,
        definitions=definitions,
    )
    errors.extend(pt_end_zone.errors)
    info.extend(pt_end_zone.notes)
    if construction_method == CONSTRUCTION_METHOD_PRECAST:
        geometry_audit = crossbeam_project_geometry_audit(state)
        errors.extend(
            str(issue.get("Detail") or "")
            for issue in geometry_audit.get("issues", [])
            if bool(issue.get("Blocks rebar solver"))
            and str(issue.get("Detail") or "").strip()
        )
    rebar_source = build_crossbeam_uls_rebar_source_contract(state)
    templates = [dict(row) for row in rebar_source.longitudinal_templates]
    zones = [dict(row) for row in rebar_source.zone_assignments]
    transverse_templates = [dict(row) for row in rebar_source.transverse_templates]
    templates_by_id = template_map(templates)
    transverse_by_id = transverse_template_map(transverse_templates)
    errors.extend(
        f"ULS reinforcement source blocked: {message}"
        for message in rebar_source.errors
    )
    warnings.extend(rebar_source.warnings)
    info.extend(rebar_source.info)

    material_by_name = _material_library(state)
    if not material_by_name:
        errors.append("Concrete material library is missing.")

    tendon_system = canonical_tendon_system_rows(_get(state, CB_TENDON_SYSTEM_ROWS_KEY, []))
    active_tendons = [row for row in tendon_system if bool(row.get("Active", True))]
    effective_link = canonical_effective_prestress_link(
        _get(state, CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY, {})
    )
    if active_tendons and not bool(effective_link.get("ready")):
        errors.append("Effective Prestress source is not CURRENT/CLOSED for Crossbeam ULS tendon strain compatibility.")
    fpe_mpa = float(effective_link.get("average_effective_stress_mpa") or 0.0)
    if active_tendons and fpe_mpa <= 0.0:
        errors.append("Average effective prestress fpe must be positive before bonded tendons can receive ULS flexure credit.")

    if errors:
        payload = {"contract": contract, "demands": demand_rows, "rebar_source_fingerprint": rebar_source.fingerprint, "errors": _dedupe(errors)}
        return CrossbeamUlsPreparation(
            ready=False,
            rows=(),
            errors=tuple(_dedupe(errors)),
            warnings=tuple(_dedupe(warnings)),
            info=(),
            fingerprint=_fingerprint(payload),
            demand_rows=tuple(demand_rows),
            support_footprints=tuple(support_footprints),
            pt_end_zone_settings=pt_end_zone.as_dict(),
            member_length_m=length_m,
        )

    if station_rows_are_pre_routed:
        # Combined V+T supplies the already accepted Shear/Torsion station set
        # (imported, Column Face, and prestressed h/2 rows).  Re-generating
        # support or development rows here would duplicate stations and can
        # demand source points that were intentionally excluded by the shared
        # station-eligibility route.
        support_demands: list[dict[str, Any]] = []
        derived_demands: list[dict[str, Any]] = []
        info.append(
            "Flexure section inputs use the pre-routed combined V+T station set; "
            "no additional support, physical-joint, or development-boundary rows were generated."
        )
    else:
        support_demands, support_errors, support_info = generate_support_check_demands(
            active_demands=active_demands,
            support_footprints=support_footprints,
            segment_rows=segment_rows,
            definitions=definitions,
            member_length_m=length_m,
            include_h2=False,
        )
        errors.extend(support_errors)
        info.extend(support_info)

        derived_demands, derived_errors, derived_info = _derived_crossbeam_flexure_demands(
            active_demands=active_demands,
            segment_rows=segment_rows,
            definitions_by_id=definition_by_id,
            material_by_name=material_by_name,
            zones=zones,
            templates_by_id=templates_by_id,
            member_length_m=length_m,
            construction_method=construction_method,
        )
        warnings.extend(f"Flexure generated-check source review: {message}" for message in derived_errors)
        info.extend(derived_info)
    if errors:
        payload = {
            "schema": "crossbeam-analysis4c6b-flexure-station-routing-blocked-v1",
            "station_rows_are_pre_routed": station_rows_are_pre_routed,
            "contract": contract,
            "demands": demand_rows,
            "support_demands": support_demands,
            "support_footprints": support_footprints,
            "pt_end_zone": pt_end_zone.as_dict(),
            "errors": _dedupe(errors),
        }
        return CrossbeamUlsPreparation(
            ready=False,
            rows=(),
            errors=tuple(_dedupe(errors)),
            warnings=tuple(_dedupe(warnings)),
            info=tuple(_dedupe(info)),
            fingerprint=_fingerprint(payload),
            demand_rows=tuple(demand_rows),
            derived_support_rows=tuple(support_demands),
            support_footprints=tuple(support_footprints),
            pt_end_zone_settings=pt_end_zone.as_dict(),
            member_length_m=length_m,
        )
    joint_stations = segment_joint_stations(segment_rows, length_m=length_m)
    derived_joint_keys = {
        (str(row.get("Case Name") or "ULS"), round(_finite_float(row.get("Station s (m)")), 9))
        for row in derived_demands
        if str(row.get("__Flexure check type") or "") == "PHYSICAL JOINT SIDE"
    }
    settings = _analysis_settings(state)
    prepared: list[PreparedCrossbeamUlsRow] = []
    excluded_end_zone_rows: list[dict[str, Any]] = []
    profile_rows = _get(state, CB_PROFILE_ROWS_KEY, [])
    tolerance = max(1.0e-7, length_m * 1.0e-9)
    support_station_keys = {
        (str(row.get("Case Name") or "ULS"), round(_finite_float(row.get("Station s (m)")), 9))
        for row in support_demands
    }

    for demand in [*active_demands, *support_demands, *derived_demands]:
        station = float(demand.get("Station s (m)") or 0.0)
        case = str(demand.get("Case Name") or "ULS")
        check_point = str(demand.get("Check Point") or "")
        is_derived = bool(demand.get("__Derived flexure check"))
        is_derived_support = bool(demand.get("__Derived support check"))
        is_joint_side = str(demand.get("__Flexure check type") or "") == "PHYSICAL JOINT SIDE"
        is_physical_joint_station = (
            construction_method == CONSTRUCTION_METHOD_PRECAST
            and any(abs(station - joint) <= tolerance for joint in joint_stations)
        )
        if (not is_derived and not is_derived_support) and (case, round(station, 9)) in support_station_keys:
            continue
        if (
            station_inside_support_interior(station, support_footprints, tolerance=tolerance)
            and not is_joint_side
            and not is_physical_joint_station
        ):
            continue
        end_side = pt_end_zone_side(station, pt_end_zone, tolerance=tolerance)
        if end_side and not is_joint_side:
            excluded_end_zone_rows.append(
                end_zone_exclusion_record(
                    demand,
                    side=end_side,
                    source_kind="GENERATED SUPPORT" if is_derived_support else "IMPORTED",
                )
            )
            continue
        if (not is_derived) and (case, round(station, 9)) in derived_joint_keys and any(
            abs(station - joint) <= tolerance for joint in joint_stations
        ):
            # The generated J-L/J-R rows own the exact physical-joint check.
            continue
        at_joint = is_physical_joint_station
        context_station = _finite_float(demand.get("__Context station s (m)"), station)
        contexts = station_section_contexts(
            context_station,
            segment_rows,
            definitions,
            length_m=length_m,
        )
        segment_override = str(demand.get("__Segment override") or "").strip()
        if segment_override:
            contexts = [
                context for context in contexts
                if str(context.get("Segment") or "").strip() == segment_override
            ]
        contexts = _select_contexts(contexts, check_point=check_point, at_joint=at_joint)
        if not contexts:
            errors.append(f"{case} at s = {station:.6f} m: no active Section ID is assigned.")
            continue

        for context in contexts:
            section_id = str(context.get("Section ID") or "")
            segment_id = str(context.get("Segment") or "")
            definition = definition_by_id.get(section_id)
            if definition is None:
                errors.append(f"{case} at s = {station:.6f} m: Section ID {section_id or '(blank)'} is unavailable.")
                continue
            material_name = str(definition.get("Material") or "")
            concrete = material_by_name.get(material_name)
            if concrete is None:
                errors.append(f"{case} at s = {station:.6f} m: concrete material {material_name or '(blank)'} is unavailable.")
                continue
            try:
                geometry = build_geometry_for_definition(definition)
            except Exception as exc:
                errors.append(f"{case} at s = {station:.6f} m: unable to build {section_id}: {exc}")
                continue

            zone_candidates = [] if at_joint else _zones_for_context(
                zones,
                station_m=context_station,
                segment_id=segment_id,
                check_point=check_point,
                length_m=length_m,
            )
            if not at_joint and not zone_candidates:
                errors.append(f"{case} at s = {station:.6f} m: no reinforcement Zone covers {segment_id}.")
                continue
            if at_joint:
                zone_candidates = [{}]

            for zone in zone_candidates:
                template_id = str(zone.get("Longitudinal template") or zone.get("Rebar template") or "")
                transverse_id = str(zone.get("Transverse template") or "")
                longitudinal_source = templates_by_id.get(template_id)
                allow_rebar_credit, development_length_m, distance_to_end_m, rebar_credit_status, development_region = _development_credit_context(
                    construction_method=construction_method,
                    station_m=station,
                    context=context,
                    longitudinal=longitudinal_source,
                    concrete=concrete,
                    at_joint=at_joint,
                )
                rebar_rows, rebar_materials, rebar_errors, rebar_warnings = _generate_rebars(
                    geometry,
                    definition,
                    longitudinal_source,
                    transverse_by_id.get(transverse_id),
                    allow_credit=allow_rebar_credit,
                )
                errors.extend(f"{case} at s = {station:.6f} m: {message}" for message in rebar_errors)
                row_notes = list(rebar_warnings)
                if construction_method == CONSTRUCTION_METHOD_PRECAST:
                    row_notes.append(
                        f"Ordinary rebar flexural credit: {rebar_credit_status}; {development_region}; "
                        f"ACI conservative ld = {development_length_m:.3f} m; nearest Segment end = {distance_to_end_m:.3f} m."
                    )

                prestress_rows, prestress_materials, omitted_unbonded, ps_errors, ps_warnings = _prestress_at_station(
                    station_m=context_station if is_derived_support else station,
                    length_m=length_m,
                    geometry=geometry,
                    system_rows=tendon_system,
                    profile_rows=profile_rows,
                    fpe_mpa=fpe_mpa,
                )
                errors.extend(f"{case} at s = {station:.6f} m: {message}" for message in ps_errors)
                row_notes.extend(ps_warnings)
                if not rebar_rows and not prestress_rows:
                    errors.append(
                        f"{case} at s = {station:.6f} m: no ordinary rebar or bonded tendon is available for ULS flexure capacity."
                    )
                    continue

                face = _context_face(context, at_joint=at_joint)
                location_override = str(demand.get("__Location type") or "").strip()
                if location_override:
                    face = str(check_point or location_override).upper()
                elif len(zone_candidates) > 1 and zone:
                    face = f"{face} / {str(zone.get('Zone ID') or 'ZONE LIMIT')}"
                load = LoadCase(
                    name=f"{case} @ s={station:.6f} m · {face}",
                    Pu_N=float(demand.get("P") or 0.0) * 1000.0,
                    Mux_Nmm=float(demand.get("M3") or 0.0) * 1_000_000.0,
                    Muy_Nmm=0.0,
                    load_type="ULS",
                    active=True,
                    note=(
                        "Crossbeam adapter: P compression positive; M3 sagging positive maps to Mux. "
                        "V2 and T remain row-coupled traceability demands and are not used by this Flexure milestone."
                    ),
                )
                analysis_input = AnalysisInput(
                    section_geometry=geometry,
                    concrete_material=concrete,
                    rebar_materials=rebar_materials,
                    prestress_materials=prestress_materials,
                    rebars=rebar_rows,
                    prestress_elements=prestress_rows,
                    load_cases=[load],
                    settings=settings,
                )
                capacity_payload = analysis_input.model_dump(mode="json")
                capacity_payload.pop("load_cases", None)
                capacity_payload = _without_runtime_ids(capacity_payload)
                prepared.append(
                    PreparedCrossbeamUlsRow(
                        station_m=station,
                        check_point=check_point,
                        case_name=case,
                        section_face=face,
                        location_type=(
                            location_override
                            if location_override
                            else "PHYSICAL SEGMENT JOINT"
                            if at_joint
                            else "DEVELOPMENT BOUNDARY"
                            if str(demand.get("__Flexure check type") or "") == "DEVELOPMENT BOUNDARY"
                            else "DEVELOPMENT ZONE"
                            if rebar_credit_status == "NO CREDIT" and construction_method == CONSTRUCTION_METHOD_PRECAST
                            else interior_location_type(construction_method)
                        ),
                        segment_id=segment_id,
                        section_id=section_id,
                        rebar_zone_id=str(zone.get("Zone ID") or ""),
                        rebar_template_id=template_id,
                        source_p_kn=float(demand.get("P") or 0.0),
                        source_v2_kn=float(demand.get("V2") or 0.0),
                        source_t_knm=float(demand.get("T") or 0.0),
                        source_m3_knm=float(demand.get("M3") or 0.0),
                        ordinary_rebar_count=len(rebar_rows),
                        ordinary_rebar_area_mm2=sum(bar.area_mm2 for bar in rebar_rows),
                        bonded_tendon_count=len(prestress_rows),
                        bonded_tendon_area_mm2=sum(item.total_area_mm2 for item in prestress_rows),
                        omitted_unbonded_tendon_count=omitted_unbonded,
                        development_length_m=development_length_m,
                        distance_to_nearest_segment_end_m=distance_to_end_m,
                        rebar_credit_status=rebar_credit_status,
                        development_region=development_region,
                        demand_source=str(demand.get("__Demand source") or "IMPORTED"),
                        source_station_1_m=(
                            None if demand.get("__Source station 1 (m)") is None else _finite_float(demand.get("__Source station 1 (m)"))
                        ),
                        source_station_2_m=(
                            None if demand.get("__Source station 2 (m)") is None else _finite_float(demand.get("__Source station 2 (m)"))
                        ),
                        source_ratio=(None if demand.get("__Source ratio") is None else _finite_float(demand.get("__Source ratio"))),
                        extrapolation_ratio=(
                            None if demand.get("__Extrapolation ratio") is None else _finite_float(demand.get("__Extrapolation ratio"))
                        ),
                        analysis_input=analysis_input,
                        capacity_signature=_fingerprint(capacity_payload),
                        notes=tuple(_dedupe(row_notes)),
                    )
                )

    errors = _dedupe(errors)
    warnings = _dedupe(warnings)
    if prepared:
        info.extend(
            [
                f"Prepared Crossbeam ULS station checks: {len(prepared)}.",
                f"Active imported ULS rows: {len(active_demands)}.",
                "Demand mapping: P → Pu; M3 → Mux; V2/T retained for row-coupled audit only.",
                "Imported FEA resultants are used directly; Pe or secondary prestress is not added to demand again.",
            ]
        )
    fingerprint_payload = {
        "schema": "crossbeam-analysis4-direct-uniaxial-development-gate-v1",
        "construction_method": construction_method,
        "contract": contract,
        "demands": demand_rows,
        "support_demands": support_demands,
        "support_footprints": support_footprints,
        "pt_end_zone": pt_end_zone.as_dict(),
        "excluded_end_zone_rows": excluded_end_zone_rows,
        "rebar_source_fingerprint": rebar_source.fingerprint,
        "capacity_signatures": [row.capacity_signature for row in prepared],
        "source_faces": [
            [row.station_m, row.case_name, row.section_face, row.section_id, row.rebar_zone_id]
            for row in prepared
        ],
    }
    return CrossbeamUlsPreparation(
        ready=bool(prepared) and not errors,
        rows=tuple(prepared),
        errors=tuple(errors),
        warnings=tuple(warnings),
        info=tuple(_dedupe(info)),
        fingerprint=_fingerprint(fingerprint_payload),
        demand_rows=tuple(demand_rows),
        derived_support_rows=tuple(support_demands),
        support_footprints=tuple(support_footprints),
        excluded_end_zone_rows=tuple(excluded_end_zone_rows),
        pt_end_zone_settings=pt_end_zone.as_dict(),
        member_length_m=length_m,
    )


def run_crossbeam_uls_flexure(preparation: CrossbeamUlsPreparation) -> dict[str, Any]:
    """Run the direct exact-axis ACI P-M3 solver for every Crossbeam check row."""

    if not preparation.ready:
        raise ValueError("Crossbeam ULS flexure preparation is not ready.")

    result_rows: list[dict[str, Any]] = []
    warnings: list[str] = list(preparation.warnings)
    solver_errors: list[str] = []
    solved: dict[tuple[str, float, float], Any] = {}

    for row in preparation.rows:
        zero_m3 = abs(float(row.source_m3_knm)) <= _ZERO_M3_TOLERANCE_KNM
        direction_reference = _nearest_nonzero_m3_reference(row, preparation.rows) if zero_m3 else None
        if zero_m3 and direction_reference is None:
            solver = None
            capacity = None
            nominal_mn = None
            phi_value = None
            dcr = None
            axial_dcr = crossbeam_uniaxial_axial_dcr(
                row.analysis_input,
                Pu_N=float(row.analysis_input.load_cases[0].Pu_N),
            )
            status = "REVIEW"
            result_message = (
                "M3 is zero and no nonzero M3 row exists in the same Load Case; "
                "the direct-solver bending direction is intentionally not guessed."
            )
            capacity_sign = 1.0
            bending_direction = "Unresolved — zero M3"
            tension_face = "-"
            direction_source = "Unavailable — no nonzero M3 row in the same Load Case"
            residual_n = None
            residual_ratio = None
            c_mm = None
            a_mm = None
            eps_t = None
            strain_condition = "-"
            iterations = 0
            bracket_count = 0
        else:
            capacity_sign = (
                direction_reference.sign
                if zero_m3 and direction_reference is not None
                else (-1.0 if row.source_m3_knm < 0.0 else 1.0)
            )
            pu_n = float(row.analysis_input.load_cases[0].Pu_N)
            cache_key = (row.capacity_signature, round(pu_n, 3), capacity_sign)
            solver = solved.get(cache_key)
            if solver is None:
                try:
                    solver = solve_crossbeam_uniaxial_flexure(
                        row.analysis_input,
                        Pu_N=pu_n,
                        moment_sign=capacity_sign,
                    )
                    solved[cache_key] = solver
                except Exception as exc:
                    solver_errors.append(f"{row.case_name} at s = {row.station_m:.6f} m: {exc}")
                    solver = None
            if solver is None or solver.state is None:
                capacity = None
                nominal_mn = None
                phi_value = None
                dcr = None
                axial_dcr = None if solver is None else solver.axial_dcr
                status = "REVIEW"
                result_message = "Direct uniaxial flexure solution is unavailable." if solver is None else solver.message
                residual_n = None if solver is None else solver.force_residual_N
                residual_ratio = None if solver is None else solver.force_residual_ratio
                c_mm = None
                a_mm = None
                eps_t = None
                strain_condition = "-"
                iterations = 0 if solver is None else solver.iterations
                bracket_count = 0 if solver is None else solver.bracket_count
            else:
                warnings.extend(solver.warnings)
                capacity = solver.capacity_phiMn_Nmm
                nominal_mn = solver.nominal_Mn_Nmm
                phi_value = solver.phi
                dcr = (
                    0.0
                    if zero_m3 and capacity is not None and capacity > 0.0
                    else abs(float(row.source_m3_knm) * 1_000_000.0) / float(capacity)
                    if capacity is not None and capacity > 0.0
                    else None
                )
                axial_dcr = solver.axial_dcr
                if solver.status not in {"PASS"}:
                    status = "REVIEW"
                elif dcr is None:
                    status = "REVIEW"
                elif dcr > 1.0 + 1.0e-12 or (axial_dcr is not None and axial_dcr > 1.0 + 1.0e-12):
                    status = "FAIL"
                else:
                    status = "PASS"
                if solver.state.prestress_compression_reversal_count:
                    status = "REVIEW" if status == "PASS" else status
                result_message = solver.message
                residual_n = solver.force_residual_N
                residual_ratio = solver.force_residual_ratio
                c_mm = solver.state.c_mm
                a_mm = solver.state.a_mm
                eps_t = solver.state.eps_t
                strain_condition = solver.state.strain_condition
                iterations = solver.iterations
                bracket_count = solver.bracket_count

            if status == "PASS" and row.omitted_unbonded_tendon_count:
                status = "REVIEW"
            if zero_m3 and direction_reference is not None:
                bending_direction = "Sagging reference (+M3)" if direction_reference.sign > 0.0 else "Hogging reference (-M3)"
                tension_face = "Bottom face" if direction_reference.sign > 0.0 else "Top face"
                direction_source = (
                    f"Same-case nearest nonzero: s = {direction_reference.station_m:.3f} m; "
                    f"M3 = {direction_reference.source_m3_knm:+,.3f} kN-m"
                )
                result_message = (
                    f"{result_message} Zero-M3 capacity uses the bending sign from "
                    f"s = {direction_reference.station_m:.3f} m; flexural D/C = 0.000."
                )
            else:
                bending_direction = "Sagging (+M3)" if capacity_sign > 0.0 else "Hogging (-M3)"
                tension_face = "Bottom face" if capacity_sign > 0.0 else "Top face"
                direction_source = "Current nonzero M3 row"

        result_rows.append(
            {
                "Check": "Flexure",
                "Status": status,
                "Governing x": f"{row.station_m:.3f} m",
                "Station s (m)": row.station_m,
                "Check Point": row.check_point,
                "Case": row.case_name,
                "Section face": row.section_face,
                "Location type": row.location_type,
                "Segment": row.segment_id,
                "Section ID": row.section_id,
                "Rebar Zone": row.rebar_zone_id or "None / joint-development gate",
                "Rebar Template": row.rebar_template_id or "None at physical joint",
                "P kN": row.source_p_kn,
                "V2 kN": row.source_v2_kn,
                "T kN-m": row.source_t_knm,
                "M3 kN-m": row.source_m3_knm,
                "Demand": f"{row.source_m3_knm:,.3f} kN-m",
                "Capacity": "-" if capacity is None else f"{capacity / 1_000_000.0:,.3f} kN-m",
                "φMn at Pu": "-" if capacity is None else f"{capacity / 1_000_000.0:,.3f} kN-m",
                "Utilization": "-" if dcr is None else f"{dcr:.3f}",
                "Flexural D/C": "-" if dcr is None else f"{dcr:.3f}",
                "Axial D/C": "-" if axial_dcr is None else f"{axial_dcr:.3f}",
                "Demand kN-m": row.source_m3_knm,
                "Capacity kN-m": float("nan") if capacity is None else capacity / 1_000_000.0,
                "Utilization value": float("nan") if dcr is None else dcr,
                "Axial D/C value": float("nan") if axial_dcr is None else axial_dcr,
                "Capacity plot sign": capacity_sign,
                "Mn nominal kN-m": float("nan") if nominal_mn is None else nominal_mn / 1_000_000.0,
                "φ value": float("nan") if phi_value is None else phi_value,
                "φMn kN-m": float("nan") if capacity is None else capacity / 1_000_000.0,
                "D/C value": float("nan") if dcr is None else dcr,
                "Neutral axis c mm": float("nan") if c_mm is None else c_mm,
                "Stress block a mm": float("nan") if a_mm is None else a_mm,
                "Net tensile strain": float("nan") if eps_t is None else eps_t,
                "Strain condition": strain_condition,
                "Force residual N": float("nan") if residual_n is None else residual_n,
                "Force residual ratio": float("nan") if residual_ratio is None else residual_ratio,
                "Root iterations": iterations,
                "Root brackets": bracket_count,
                "Bending direction": bending_direction,
                "Tension face": tension_face,
                "Direction reference": direction_source,
                "Code basis": "ACI 318-19",
                "Strain compatibility basis": "Direct exact-axis ACI section strain compatibility",
                "φ policy": "ACI strain-based φ solved concurrently with phiPn = Pu",
                "Solver basis": "Crossbeam-scoped direct uniaxial P-M3 adaptive root solver",
                "Material model scope": "Concrete + eligible ordinary rebar + bonded tendon groups",
                "Route": "Crossbeam P + M3 → exact Mx axis",
                "Ordinary rebar credit": row.rebar_credit_status,
                "Development region": row.development_region,
                "ACI conservative ld m": row.development_length_m,
                "Distance to nearest Segment end m": row.distance_to_nearest_segment_end_m,
                "Ordinary bars credited": row.ordinary_rebar_count,
                "Ordinary As credited mm²": row.ordinary_rebar_area_mm2,
                "Bonded tendons credited": row.bonded_tendon_count,
                "Bonded Aps credited mm²": row.bonded_tendon_area_mm2,
                "Unbonded tendons omitted": row.omitted_unbonded_tendon_count,
                "Demand source": row.demand_source,
                "Source station 1 m": row.source_station_1_m,
                "Source station 2 m": row.source_station_2_m,
                "Source ratio": row.source_ratio,
                "Extrapolation ratio": row.extrapolation_ratio,
                "Method": "Direct ACI 318-19 uniaxial strain compatibility / adaptive phiPn root / 25.4 development gate",
                "Notes": " | ".join(row.notes + ((result_message,) if result_message else ())),
            }
        )

    finite = [row for row in result_rows if math.isfinite(float(row["Utilization value"]))]
    governing = max(finite, key=lambda item: float(item["Utilization value"]), default=None)
    statuses = {str(row.get("Status") or "REVIEW") for row in result_rows}
    missing_generated = any(str(message).startswith("Flexure generated-check source review:") for message in warnings)
    if solver_errors or not result_rows:
        overall = "REVIEW"
    elif "FAIL" in statuses:
        overall = "FAIL"
    elif statuses == {"PASS"} and not missing_generated:
        overall = "PASS"
    else:
        overall = "REVIEW"
    joint_rows = [row for row in result_rows if str(row.get("Location type")) == "PHYSICAL SEGMENT JOINT"]
    development_rows = [row for row in result_rows if str(row.get("Location type")) in {"DEVELOPMENT ZONE", "DEVELOPMENT BOUNDARY"}]
    return {
        "schema": "crossbeam-analysis4-direct-uniaxial-development-gate-v1",
        "input_fingerprint": preparation.fingerprint,
        "status": overall,
        "rows": result_rows,
        "governing_row": governing,
        "warnings": _dedupe(warnings),
        "errors": _dedupe(solver_errors),
        "structural_solves": len(solved),
        "station_checks": len(preparation.rows),
        "generated_support_checks": sum(row.location_type == "COLUMN FACE" for row in preparation.rows),
        "support_footprints": [dict(item) for item in preparation.support_footprints],
        "excluded_pt_end_zone_rows": [dict(item) for item in preparation.excluded_end_zone_rows],
        "pt_end_zone_settings": dict(preparation.pt_end_zone_settings),
        "member_length_m": float(preparation.member_length_m),
        "physical_joint_side_checks": len(joint_rows),
        "development_zone_checks": len(development_rows),
        "solver_route": "DIRECT UNIAXIAL P-M3",
        "accuracy_preset_dependency": "NONE — production result is independent of PMM angle/depth presets",
        "scope": (
            "ULS Crossbeam P-M3 flexure using direct ACI 318-19 strain compatibility. For Precast Segmental, ordinary "
            "longitudinal reinforcement receives strength credit only in fully developed Segment interiors; physical joints "
            "and conservative ACI 25.4 straight-bar development zones use bonded-tendon continuity without ordinary-rebar credit. "
            "Shear, Torsion, combined V+T, joint shear/torsion transfer, PT anchorage/end-zone D-regions, fatigue, and seismic detailing remain separate. "
            "Ordinary B-region governing excludes the adopted PT end-zone lengths and support-footprint interiors."
        ),
    }

