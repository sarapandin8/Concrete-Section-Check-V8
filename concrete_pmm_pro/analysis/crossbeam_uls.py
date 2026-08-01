"""Station-specific ULS flexure adapter for Portal Frame Crossbeams.

``CROSSBEAM.ANALYSIS1A`` promotes the accepted Crossbeam Section/Zone,
reinforcement, tendon, effective-prestress, and ULS station-force inputs into a
solver-facing contract.  It does not mutate the generic ``load_cases`` table
and it does not add prestress force to the imported FEA demand.

Internal units remain mm, MPa, N, and N-mm.  Imported Crossbeam ``M3`` is the
sagging-positive moment in the member s-vertical plane and maps to PMM ``Mux``
because the section x-axis is transverse and the y-axis is vertical.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

from concrete_pmm_pro.analysis.capacity_check import check_uls_demands_against_rc_pmm
from concrete_pmm_pro.analysis.pmm_solver import run_pmm_solver
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
    PMM solve.
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


def _analysis_settings(state: Any) -> AnalysisSettings:
    source = _get(state, "analysis_settings")
    if isinstance(source, AnalysisSettings):
        settings = source
    elif isinstance(source, Mapping):
        settings = AnalysisSettings.model_validate(source)
    else:
        settings = AnalysisSettings()
    preset = str(_get(state, "analysis_accuracy_preset", "Standard") or "Standard")
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


def build_crossbeam_uls_flexure_preparation(state: Any) -> CrossbeamUlsPreparation:
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
    templates, zones, transverse_templates = _load_source_for_method(state, construction_method)
    templates_by_id = template_map(templates)
    transverse_by_id = transverse_template_map(transverse_templates)
    if not templates:
        errors.append("Crossbeam longitudinal reinforcement templates are missing.")
    if not zones:
        errors.append("Crossbeam reinforcement Zone assignments are missing.")

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
        payload = {"contract": contract, "demands": demand_rows, "errors": _dedupe(errors)}
        return CrossbeamUlsPreparation(
            ready=False,
            rows=(),
            errors=tuple(_dedupe(errors)),
            warnings=tuple(_dedupe(warnings)),
            info=(),
            fingerprint=_fingerprint(payload),
            demand_rows=tuple(demand_rows),
        )

    joint_stations = segment_joint_stations(segment_rows, length_m=length_m)
    settings = _analysis_settings(state)
    prepared: list[PreparedCrossbeamUlsRow] = []
    profile_rows = _get(state, CB_PROFILE_ROWS_KEY, [])

    for demand in active_demands:
        station = float(demand.get("Station s (m)") or 0.0)
        case = str(demand.get("Case Name") or "ULS")
        check_point = str(demand.get("Check Point") or "")
        tolerance = max(1.0e-7, length_m * 1.0e-9)
        at_joint = construction_method == CONSTRUCTION_METHOD_PRECAST and any(
            abs(station - joint) <= tolerance for joint in joint_stations
        )
        contexts = station_section_contexts(
            station,
            segment_rows,
            definitions,
            length_m=length_m,
        )
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
                station_m=station,
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
                rebar_rows, rebar_materials, rebar_errors, rebar_warnings = _generate_rebars(
                    geometry,
                    definition,
                    templates_by_id.get(template_id),
                    transverse_by_id.get(transverse_id),
                    allow_credit=not at_joint,
                )
                errors.extend(f"{case} at s = {station:.6f} m: {message}" for message in rebar_errors)
                row_notes = list(rebar_warnings)

                prestress_rows, prestress_materials, omitted_unbonded, ps_errors, ps_warnings = _prestress_at_station(
                    station_m=station,
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
                if len(zone_candidates) > 1 and zone:
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
                        location_type="PHYSICAL SEGMENT JOINT" if at_joint else "SEGMENT / ZONE INTERIOR",
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
        "schema": "crossbeam-analysis1a-uls-flexure-v1",
        "construction_method": construction_method,
        "contract": contract,
        "demands": demand_rows,
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
    )


def run_crossbeam_uls_flexure(preparation: CrossbeamUlsPreparation) -> dict[str, Any]:
    """Run one PMM surface per unique Crossbeam capacity source and check all demands."""

    if not preparation.ready:
        raise ValueError("Crossbeam ULS flexure preparation is not ready.")
    grouped: dict[str, list[PreparedCrossbeamUlsRow]] = defaultdict(list)
    for row in preparation.rows:
        grouped[row.capacity_signature].append(row)

    result_rows: list[dict[str, Any]] = []
    warnings: list[str] = list(preparation.warnings)
    solver_errors: list[str] = []
    for group in grouped.values():
        representative = group[0]
        try:
            pmm = run_pmm_solver(representative.analysis_input)
            warnings.extend(pmm.warnings)
        except Exception as exc:
            for row in group:
                solver_errors.append(f"{row.case_name} at s = {row.station_m:.6f} m: {exc}")
            continue

        for row in group:
            summary = check_uls_demands_against_rc_pmm(pmm, row.analysis_input.load_cases)
            warnings.extend(summary.warnings)
            result = summary.results[0] if summary.results else None
            capacity = None if result is None else result.capacity_phiMn_Nmm
            dcr = None if result is None else result.dcr
            status = "REVIEW" if result is None else str(result.status)
            if status == "PASS" and row.omitted_unbonded_tendon_count:
                status = "REVIEW"
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
                    "Rebar Zone": row.rebar_zone_id or "None at physical joint",
                    "Rebar Template": row.rebar_template_id or "None at physical joint",
                    "P kN": row.source_p_kn,
                    "V2 kN": row.source_v2_kn,
                    "T kN-m": row.source_t_knm,
                    "M3 kN-m": row.source_m3_knm,
                    "Demand": f"{row.source_m3_knm:,.3f} kN-m",
                    "Capacity": "-" if capacity is None else f"{capacity / 1_000_000.0:,.3f} kN-m",
                    "Utilization": "-" if dcr is None else f"{dcr:.3f}",
                    "Demand kN-m": row.source_m3_knm,
                    "Capacity kN-m": float("nan") if capacity is None else capacity / 1_000_000.0,
                    "Utilization value": float("nan") if dcr is None else dcr,
                    "Capacity plot sign": -1.0 if row.source_m3_knm < 0.0 else 1.0,
                    "Mn nominal kN-m": float("nan"),
                    "φ value": float("nan"),
                    "φMn kN-m": float("nan") if capacity is None else capacity / 1_000_000.0,
                    "D/C value": float("nan") if dcr is None else dcr,
                    "Bending direction": "Sagging (+M3)" if row.source_m3_knm > 0.0 else "Hogging (-M3)" if row.source_m3_knm < 0.0 else "Axial / zero M3",
                    "Tension face": "Bottom face" if row.source_m3_knm > 0.0 else "Top face" if row.source_m3_knm < 0.0 else "-",
                    "Code basis": "ACI 318-19",
                    "Strain compatibility basis": "ACI section strain compatibility",
                    "φ policy": "ACI strain-based φ from PMM engine",
                    "Solver basis": "Existing PMM section engine through Crossbeam station adapter",
                    "Material model scope": "Concrete + generated ordinary rebar layout + bonded tendon groups",
                    "Route": "Crossbeam M3 → PMM Mux",
                    "Ordinary bars credited": row.ordinary_rebar_count,
                    "Ordinary As credited mm²": row.ordinary_rebar_area_mm2,
                    "Bonded tendons credited": row.bonded_tendon_count,
                    "Bonded Aps credited mm²": row.bonded_tendon_area_mm2,
                    "Unbonded tendons omitted": row.omitted_unbonded_tendon_count,
                    "Method": "ACI strain compatibility / directional Pu-Mux slice",
                    "Notes": " | ".join(row.notes + (() if result is None else (str(result.message),))),
                }
            )

    finite = [row for row in result_rows if math.isfinite(float(row["Utilization value"]))]
    governing = max(finite, key=lambda row: float(row["Utilization value"]), default=None)
    statuses = {str(row.get("Status") or "REVIEW") for row in result_rows}
    if solver_errors or not result_rows:
        overall = "REVIEW"
    elif "FAIL" in statuses:
        overall = "FAIL"
    elif statuses == {"PASS"}:
        overall = "PASS"
    else:
        overall = "REVIEW"
    return {
        "schema": "crossbeam-analysis1a-uls-flexure-result-v1",
        "input_fingerprint": preparation.fingerprint,
        "status": overall,
        "rows": result_rows,
        "governing_row": governing,
        "warnings": _dedupe(warnings),
        "errors": _dedupe(solver_errors),
        "structural_solves": len(grouped),
        "station_checks": len(preparation.rows),
        "scope": (
            "ULS flexure station check only. V2/T are retained for audit but Shear, Torsion, combined V+T, "
            "anchorage/development, physical-joint shear transfer, D-region, and seismic detailing remain separate."
        ),
    }
