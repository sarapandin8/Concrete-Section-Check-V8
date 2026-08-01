"""Transfer-stage concrete stress checks for Portal Frame Crossbeams.

``CROSSBEAM.SLS1A`` consumes the selected, row-coupled ``SLS At Transfer``
resultants imported from the external FEA model.  Those resultants already
contain the transfer-age prestress response, self-weight, support/contact
response, and secondary prestress effects applicable to the declared stage;
this adapter therefore uses P and M3 exactly once and never adds Pe again.

Internal units are mm, MPa, N, and N-mm.  Imported P is compression-positive,
M3 is sagging-positive, and displayed concrete stress is compression-negative
and tension-positive.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

from concrete_pmm_pro.core.concrete_materials import concrete_materials_by_name
from concrete_pmm_pro.core.models import ConcreteMaterial
from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_PRECAST,
    DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
    MIN_CROSSBEAM_STRESSING_STRENGTH_RATIO,
    canonical_column_stage_rows,
    normalize_construction_method,
)
from concrete_pmm_pro.crossbeam.prestress_loss import (
    CB_LOSS_ES_COLUMN_ROWS_KEY,
    CB_LOSS_ES_CONSTRUCTION_METHOD_KEY,
    CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY,
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
    canonical_sls_stage,
    canonical_station_force_contract,
    normalize_station_force_rows,
    validate_station_force_rows,
)
from concrete_pmm_pro.crossbeam.tendon import segment_joint_stations, station_section_contexts
from concrete_pmm_pro.geometry.summary import summarize_geometry


CROSSBEAM_TRANSFER_RESULT_KEY = "crossbeam_sls1a_transfer_stress_result"
CROSSBEAM_TRANSFER_RESULT_HASH_KEY = "crossbeam_sls1a_transfer_stress_input_hash"
CROSSBEAM_SLS_LOAD_TABLE_KEY = "crossbeam_sls_loads_table"
CROSSBEAM_LENGTH_KEY = "crossbeam_ui1_length_m"
CROSSBEAM_SEGMENT_ROWS_KEY = "crossbeam_ui1_segment_layout_rows"

ACI_TRANSFER_COMPRESSION_FACTOR = 0.60
ACI_TRANSFER_TENSION_FACTOR_MPA = 0.25
PHYSICAL_JOINT_MIN_COMPRESSION_MPA = 0.70
_STATION_TOLERANCE_MIN_M = 1.0e-7


@dataclass(frozen=True)
class PreparedCrossbeamTransferRow:
    station_m: float
    check_point: str
    case_name: str
    section_face: str
    location_type: str
    segment_id: str
    section_id: str
    material_name: str
    source_p_kn: float
    source_v2_kn: float
    source_t_knm: float
    source_m3_knm: float
    fc_mpa: float
    fci_mpa: float
    area_mm2: float
    ix_mm4: float
    z_top_mm3: float
    z_bottom_mm3: float
    is_physical_joint: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrossbeamTransferPreparation:
    ready: bool
    rows: tuple[PreparedCrossbeamTransferRow, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    info: tuple[str, ...]
    fingerprint: str
    demand_rows: tuple[dict[str, Any], ...]
    member_length_m: float
    construction_method: str
    stressing_strength_ratio: float
    joint_stations_m: tuple[float, ...]
    column_rows: tuple[dict[str, Any], ...]


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
    return list(dict.fromkeys(str(item).strip() for item in messages if str(item).strip()))


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


def _explicit_side(check_point: str) -> str | None:
    text = str(check_point or "").strip().casefold().replace("−", "-")
    if "left" in text or "s-" in text:
        return "left"
    if "right" in text or "s+" in text:
        return "right"
    return None


def _face_label(context: Mapping[str, Any], *, at_joint: bool, multiple: bool) -> str:
    face = str(context.get("Station face") or "")
    if at_joint:
        if face == "Right end":
            return "LEFT LIMIT (s-)"
        if face == "Left end":
            return "RIGHT LIMIT (s+)"
        return "JOINT LIMIT"
    if multiple:
        if face == "Right end":
            return "ZONE LEFT LIMIT (s-)"
        if face == "Left end":
            return "ZONE RIGHT LIMIT (s+)"
    return "INTERIOR"


def _select_contexts(
    contexts: list[dict[str, Any]],
    *,
    check_point: str,
    at_joint: bool,
) -> list[dict[str, Any]]:
    side = _explicit_side(check_point)
    if side:
        desired = "Right end" if side == "left" else "Left end"
        selected = [item for item in contexts if str(item.get("Station face") or "") == desired]
        if selected:
            return selected
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in contexts:
        key = (
            str(item.get("Segment") or ""),
            str(item.get("Section ID") or ""),
            str(item.get("Station face") or ""),
        )
        unique.setdefault(key, item)
    if not at_joint and len(unique) > 1:
        # If a monolithic zone boundary repeats the same Section ID, one gross
        # section check is sufficient.  Different Section IDs remain two-sided.
        by_section: dict[str, dict[str, Any]] = {}
        for item in unique.values():
            by_section.setdefault(str(item.get("Section ID") or ""), item)
        if len(by_section) == 1:
            return [next(iter(by_section.values()))]
    return list(unique.values())


def _joint_coverage_errors(
    prepared: list[PreparedCrossbeamTransferRow],
    *,
    cases: list[str],
    joint_stations: list[float],
    tolerance_m: float,
) -> list[str]:
    errors: list[str] = []
    for case in cases:
        for joint in joint_stations:
            rows = [
                row
                for row in prepared
                if row.case_name == case
                and abs(float(row.station_m) - float(joint)) <= tolerance_m
                and row.is_physical_joint
            ]
            faces = {row.section_face for row in rows}
            missing = [face for face in ("LEFT LIMIT (s-)", "RIGHT LIMIT (s+)") if face not in faces]
            if missing:
                errors.append(
                    f"{case}: physical joint at s = {joint:.6f} m must be checked on both s-/s+ faces; "
                    f"missing {', '.join(missing)}. Import one unlabeled joint row or explicit Left/Right rows."
                )
    return errors


def build_crossbeam_transfer_stress_preparation(state: Any) -> CrossbeamTransferPreparation:
    """Build validated gross-section transfer checks from Crossbeam SLS rows."""

    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    length_m = float(_get(state, CROSSBEAM_LENGTH_KEY, 0.0) or 0.0)
    if length_m <= 0.0:
        errors.append("Crossbeam physical length L must be positive.")

    construction_method = normalize_construction_method(
        _get(state, CB_LOSS_ES_CONSTRUCTION_METHOD_KEY, CONSTRUCTION_METHOD_PRECAST)
    )
    try:
        stressing_ratio = float(
            _get(
                state,
                CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY,
                DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
            )
        )
    except (TypeError, ValueError):
        stressing_ratio = float("nan")
    if not math.isfinite(stressing_ratio) or not (
        MIN_CROSSBEAM_STRESSING_STRENGTH_RATIO <= stressing_ratio <= 1.0
    ):
        errors.append(
            "Crossbeam stressing-strength ratio f'ci/f'c must be between "
            f"{MIN_CROSSBEAM_STRESSING_STRENGTH_RATIO:.2f} and 1.00."
        )

    contract = canonical_station_force_contract(
        _get(state, CB_STATION_FORCE_CONTRACT_KEY, {}),
        effective_prestress_link=_get(state, CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY, {}),
    )
    all_sls = normalize_station_force_rows(
        _records(_get(state, CROSSBEAM_SLS_LOAD_TABLE_KEY, [])),
        contract=contract,
        response_type="SLS",
        rows_are_canonical=True,
    )
    demand_rows = [
        row for row in all_sls if canonical_sls_stage(row.get("Stage")) == "Transfer stage"
    ]
    validation = validate_station_force_rows(
        demand_rows,
        contract=contract,
        member_length_m=max(length_m, 0.0),
        response_type="SLS",
        rows_are_canonical=True,
        expected_sls_stage="Transfer stage",
    )
    errors.extend(validation.errors)
    warnings.extend(validation.warnings)
    active_demands = [row for row in demand_rows if bool(row.get("Active", True))]
    if not active_demands:
        errors.append("No active SLS At Transfer station-force rows are available.")

    segment_rows = _records(_get(state, CROSSBEAM_SEGMENT_ROWS_KEY, []))
    definitions = canonical_section_definitions(_get(state, CB_SECLIB_DEFINITIONS_KEY, []))
    definitions_by_id = definition_map(definitions)
    materials_by_name = _material_library(state)
    if not segment_rows:
        errors.append("Crossbeam Segment / Zone Layout is missing.")
    if not definitions:
        errors.append("Crossbeam Section Library is missing.")
    if not materials_by_name:
        errors.append("Concrete material library is missing.")

    joint_stations = (
        segment_joint_stations(segment_rows, length_m=max(length_m, 0.1))
        if construction_method == CONSTRUCTION_METHOD_PRECAST and segment_rows
        else []
    )
    column_rows = canonical_column_stage_rows(
        _get(state, CB_LOSS_ES_COLUMN_ROWS_KEY, []), length_m=max(length_m, 0.0)
    )
    if errors:
        payload = {
            "schema": "crossbeam-sls1a-transfer-preparation-v1",
            "contract": contract,
            "demands": demand_rows,
            "errors": _dedupe(errors),
        }
        return CrossbeamTransferPreparation(
            ready=False,
            rows=(),
            errors=tuple(_dedupe(errors)),
            warnings=tuple(_dedupe(warnings)),
            info=(),
            fingerprint=_fingerprint(payload),
            demand_rows=tuple(demand_rows),
            member_length_m=length_m,
            construction_method=construction_method,
            stressing_strength_ratio=stressing_ratio,
            joint_stations_m=tuple(joint_stations),
            column_rows=tuple(column_rows),
        )

    tolerance_m = max(_STATION_TOLERANCE_MIN_M, length_m * 1.0e-9)
    prepared: list[PreparedCrossbeamTransferRow] = []
    for demand in active_demands:
        station = float(demand.get("Station s (m)") or 0.0)
        case = str(demand.get("Case Name") or "SLS-TR")
        check_point = str(demand.get("Check Point") or "")
        at_joint = construction_method == CONSTRUCTION_METHOD_PRECAST and any(
            abs(station - joint) <= tolerance_m for joint in joint_stations
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
        multiple = len(contexts) > 1
        for context in contexts:
            section_id = str(context.get("Section ID") or "")
            segment_id = str(context.get("Segment") or "")
            definition = definitions_by_id.get(section_id)
            if definition is None:
                errors.append(
                    f"{case} at s = {station:.6f} m: Section ID {section_id or '(blank)'} is unavailable."
                )
                continue
            material_name = str(definition.get("Material") or "")
            concrete = materials_by_name.get(material_name)
            if concrete is None:
                errors.append(
                    f"{case} at s = {station:.6f} m: concrete material {material_name or '(blank)'} is unavailable."
                )
                continue
            try:
                geometry = build_geometry_for_definition(definition)
                summary = summarize_geometry(geometry)
            except Exception as exc:
                errors.append(f"{case} at s = {station:.6f} m: unable to build {section_id}: {exc}")
                continue
            if (
                summary.area_mm2 <= 0.0
                or summary.ix_nmm4 is None
                or summary.ix_nmm4 <= 0.0
                or summary.z_top_mm3 is None
                or summary.z_top_mm3 <= 0.0
                or summary.z_bottom_mm3 is None
                or summary.z_bottom_mm3 <= 0.0
            ):
                errors.append(f"{case} at s = {station:.6f} m: Section ID {section_id} gross A/I/Z properties are invalid.")
                continue
            fci_mpa = float(concrete.fc_MPa) * stressing_ratio
            if fci_mpa <= 0.0:
                errors.append(f"{case} at s = {station:.6f} m: Section ID {section_id} f'ci is not positive.")
                continue
            prepared.append(
                PreparedCrossbeamTransferRow(
                    station_m=station,
                    check_point=check_point,
                    case_name=case,
                    section_face=_face_label(context, at_joint=at_joint, multiple=multiple),
                    location_type=(
                        "PHYSICAL SEGMENT JOINT"
                        if at_joint
                        else "SECTION / ZONE LIMIT"
                        if multiple
                        else "SEGMENT / ZONE INTERIOR"
                    ),
                    segment_id=segment_id,
                    section_id=section_id,
                    material_name=material_name,
                    source_p_kn=float(demand.get("P") or 0.0),
                    source_v2_kn=float(demand.get("V2") or 0.0),
                    source_t_knm=float(demand.get("T") or 0.0),
                    source_m3_knm=float(demand.get("M3") or 0.0),
                    fc_mpa=float(concrete.fc_MPa),
                    fci_mpa=fci_mpa,
                    area_mm2=float(summary.area_mm2),
                    ix_mm4=float(summary.ix_nmm4),
                    z_top_mm3=float(summary.z_top_mm3),
                    z_bottom_mm3=float(summary.z_bottom_mm3),
                    is_physical_joint=at_joint,
                    notes=tuple(summary.warnings),
                )
            )

    if construction_method == CONSTRUCTION_METHOD_PRECAST:
        cases = sorted({str(row.get("Case Name") or "") for row in active_demands})
        errors.extend(
            _joint_coverage_errors(
                prepared,
                cases=cases,
                joint_stations=joint_stations,
                tolerance_m=tolerance_m,
            )
        )

    if prepared:
        info.extend(
            [
                f"Prepared {len(prepared)} Transfer station/face concrete-stress checks.",
                f"Active imported Transfer rows: {len(active_demands)}.",
                "Demand mapping: P compression-positive; M3 sagging-positive; V2/T retained for row-coupled audit only.",
                "Imported FEA Transfer resultants are used exactly once; prestress and secondary effects are not added again.",
            ]
        )
    warnings.append(
        "Stress lines connect verified imported stations for visualization only; no compliance is inferred between unverified stations."
    )
    errors = _dedupe(errors)
    warnings = _dedupe(warnings)
    fingerprint_payload = {
        "schema": "crossbeam-sls1a-transfer-preparation-v1",
        "construction_method": construction_method,
        "stressing_strength_ratio": stressing_ratio,
        "contract": contract,
        "demands": demand_rows,
        "sections": definitions,
        "materials": [material.model_dump(mode="json") for material in materials_by_name.values()],
        "prepared_faces": [
            [row.station_m, row.case_name, row.section_face, row.section_id, row.fci_mpa]
            for row in prepared
        ],
        "joint_stations": joint_stations,
        "columns": column_rows,
    }
    return CrossbeamTransferPreparation(
        ready=bool(prepared) and not errors,
        rows=tuple(prepared),
        errors=tuple(errors),
        warnings=tuple(warnings),
        info=tuple(_dedupe(info)),
        fingerprint=_fingerprint(fingerprint_payload),
        demand_rows=tuple(demand_rows),
        member_length_m=length_m,
        construction_method=construction_method,
        stressing_strength_ratio=stressing_ratio,
        joint_stations_m=tuple(joint_stations),
        column_rows=tuple(column_rows),
    )


def _fiber_check(
    stress_mpa: float,
    *,
    compression_limit_mpa: float,
    tension_limit_mpa: float,
    physical_joint: bool,
) -> dict[str, Any]:
    compression_util = max(-float(stress_mpa), 0.0) / compression_limit_mpa
    tension_util = max(float(stress_mpa), 0.0) / tension_limit_mpa
    general_util = max(compression_util, tension_util)
    if compression_util >= tension_util:
        criterion = "ACI transfer compression"
        actual = max(-float(stress_mpa), 0.0)
        limit = compression_limit_mpa
    else:
        criterion = "ACI transfer tension"
        actual = max(float(stress_mpa), 0.0)
        limit = tension_limit_mpa
    joint_pass = True
    joint_util: float | None = None
    if physical_joint:
        compression_available = max(-float(stress_mpa), 0.0)
        joint_pass = float(stress_mpa) <= -PHYSICAL_JOINT_MIN_COMPRESSION_MPA + 1.0e-12
        if compression_available > 0.0:
            joint_util = PHYSICAL_JOINT_MIN_COMPRESSION_MPA / compression_available
        else:
            joint_util = 1.001 + max(float(stress_mpa), 0.0) / PHYSICAL_JOINT_MIN_COMPRESSION_MPA
        if joint_util >= general_util:
            criterion = "Physical-joint minimum compression"
            actual = compression_available
            limit = PHYSICAL_JOINT_MIN_COMPRESSION_MPA
    utilization = max(general_util, joint_util or 0.0)
    general_pass = general_util <= 1.0 + 1.0e-12
    return {
        "status": "PASS" if general_pass and joint_pass else "FAIL",
        "utilization": utilization,
        "compression_utilization": compression_util,
        "tension_utilization": tension_util,
        "joint_utilization": joint_util,
        "criterion": criterion,
        "actual_mpa": actual,
        "limit_mpa": limit,
        "joint_margin_mpa": (-float(stress_mpa) - PHYSICAL_JOINT_MIN_COMPRESSION_MPA) if physical_joint else None,
    }


def _required_actions(fiber_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failed = [row for row in fiber_rows if str(row.get("Status")) == "FAIL"]
    actions: list[dict[str, Any]] = []
    joint = [
        row
        for row in failed
        if math.isfinite(float(row.get("Joint compression margin MPa") or float("nan")))
        and float(row.get("Joint compression margin MPa")) < -1.0e-12
    ]
    if joint:
        governing = max(joint, key=lambda row: float(row.get("Utilization value") or 0.0))
        actions.append(
            {
                "Priority": "High",
                "Module": "Physical joint",
                "Issue": (
                    f"Minimum compression fails at s={governing['Station s (m)']:.3f} m / "
                    f"{governing['Section face']} / {governing['Fiber']} / {governing['Case']}."
                ),
                "Required Action": (
                    "Revise Transfer tendon force/profile, stressing sequence, support/contact stage, or joint/section geometry until both s-/s+ top and bottom fibers remain at least 0.70 MPa in compression."
                ),
            }
        )
    compression = [
        row for row in failed if float(row.get("Compression utilization") or 0.0) > 1.0 + 1.0e-12
    ]
    if compression:
        governing = max(compression, key=lambda row: float(row.get("Utilization value") or 0.0))
        actions.append(
            {
                "Priority": "High",
                "Module": "ACI transfer compression",
                "Issue": (
                    f"Compression exceeds 0.60f'ci at s={governing['Station s (m)']:.3f} m / "
                    f"{governing['Fiber']} / {governing['Case']}."
                ),
                "Required Action": (
                    "Verify the imported Transfer response and f'ci source, then revise initial prestress, eccentricity, stressing/support sequence, or gross section before acceptance."
                ),
            }
        )
    tension = [
        row for row in failed if float(row.get("Tension utilization") or 0.0) > 1.0 + 1.0e-12
    ]
    if tension:
        governing = max(tension, key=lambda row: float(row.get("Utilization value") or 0.0))
        actions.append(
            {
                "Priority": "High",
                "Module": "ACI transfer tension",
                "Issue": (
                    f"Tension exceeds 0.25sqrt(f'ci) at s={governing['Station s (m)']:.3f} m / "
                    f"{governing['Fiber']} / {governing['Case']}."
                ),
                "Required Action": (
                    "Revise Transfer tendon force/profile, stressing/support sequence, or section geometry. ACI 318-19 24.5.3.2.1 bonded-reinforcement relief is not credited by SLS1A and requires a separate total tensile-force design check."
                ),
            }
        )
    return actions


def run_crossbeam_transfer_stress(preparation: CrossbeamTransferPreparation) -> dict[str, Any]:
    """Calculate top/bottom gross-section stresses and ACI/joint checks."""

    if not preparation.ready:
        raise ValueError("Crossbeam Transfer stress preparation is not ready.")
    rows: list[dict[str, Any]] = []
    fiber_rows: list[dict[str, Any]] = []
    for source in preparation.rows:
        axial_mpa = -source.source_p_kn * 1000.0 / source.area_mm2
        top_bending_mpa = -source.source_m3_knm * 1_000_000.0 / source.z_top_mm3
        bottom_bending_mpa = source.source_m3_knm * 1_000_000.0 / source.z_bottom_mm3
        top_stress = axial_mpa + top_bending_mpa
        bottom_stress = axial_mpa + bottom_bending_mpa
        compression_limit = ACI_TRANSFER_COMPRESSION_FACTOR * source.fci_mpa
        tension_limit = ACI_TRANSFER_TENSION_FACTOR_MPA * math.sqrt(source.fci_mpa)
        top_check = _fiber_check(
            top_stress,
            compression_limit_mpa=compression_limit,
            tension_limit_mpa=tension_limit,
            physical_joint=source.is_physical_joint,
        )
        bottom_check = _fiber_check(
            bottom_stress,
            compression_limit_mpa=compression_limit,
            tension_limit_mpa=tension_limit,
            physical_joint=source.is_physical_joint,
        )
        status = "PASS" if top_check["status"] == bottom_check["status"] == "PASS" else "FAIL"
        row_utilization = max(float(top_check["utilization"]), float(bottom_check["utilization"]))
        rows.append(
            {
                "Check": "Concrete Stress At Transfer",
                "Status": status,
                "Station s (m)": source.station_m,
                "Check Point": source.check_point,
                "Case": source.case_name,
                "Section face": source.section_face,
                "Location type": source.location_type,
                "Segment": source.segment_id,
                "Section ID": source.section_id,
                "Material": source.material_name,
                "P kN": source.source_p_kn,
                "V2 kN": source.source_v2_kn,
                "T kN-m": source.source_t_knm,
                "M3 kN-m": source.source_m3_knm,
                "f'c MPa": source.fc_mpa,
                "f'ci MPa": source.fci_mpa,
                "A mm2": source.area_mm2,
                "Ix mm4": source.ix_mm4,
                "Ztop mm3": source.z_top_mm3,
                "Zbottom mm3": source.z_bottom_mm3,
                "Axial stress MPa": axial_mpa,
                "Top bending stress MPa": top_bending_mpa,
                "Bottom bending stress MPa": bottom_bending_mpa,
                "Top stress MPa": top_stress,
                "Bottom stress MPa": bottom_stress,
                "Compression limit MPa": -compression_limit,
                "Tension limit MPa": tension_limit,
                "Top utilization": float(top_check["utilization"]),
                "Bottom utilization": float(bottom_check["utilization"]),
                "Governing utilization": row_utilization,
                "Top criterion": str(top_check["criterion"]),
                "Bottom criterion": str(bottom_check["criterion"]),
                "Joint minimum compression MPa": (
                    -PHYSICAL_JOINT_MIN_COMPRESSION_MPA if source.is_physical_joint else float("nan")
                ),
                "Top joint margin MPa": (
                    float(top_check["joint_margin_mpa"])
                    if top_check["joint_margin_mpa"] is not None
                    else float("nan")
                ),
                "Bottom joint margin MPa": (
                    float(bottom_check["joint_margin_mpa"])
                    if bottom_check["joint_margin_mpa"] is not None
                    else float("nan")
                ),
                "Notes": " | ".join(source.notes),
            }
        )
        for fiber, stress, check in (
            ("Top", top_stress, top_check),
            ("Bottom", bottom_stress, bottom_check),
        ):
            fiber_rows.append(
                {
                    "Status": str(check["status"]),
                    "Station s (m)": source.station_m,
                    "Check Point": source.check_point,
                    "Case": source.case_name,
                    "Section face": source.section_face,
                    "Location type": source.location_type,
                    "Section ID": source.section_id,
                    "Fiber": fiber,
                    "Stress MPa": stress,
                    "Criterion": str(check["criterion"]),
                    "Actual MPa": float(check["actual_mpa"]),
                    "Limit MPa": float(check["limit_mpa"]),
                    "Compression utilization": float(check["compression_utilization"]),
                    "Tension utilization": float(check["tension_utilization"]),
                    "Joint utilization": (
                        float(check["joint_utilization"])
                        if check["joint_utilization"] is not None
                        else float("nan")
                    ),
                    "Joint compression margin MPa": (
                        float(check["joint_margin_mpa"])
                        if check["joint_margin_mpa"] is not None
                        else float("nan")
                    ),
                    "Utilization value": float(check["utilization"]),
                    "f'ci MPa": source.fci_mpa,
                    "Compression limit MPa": -compression_limit,
                    "Tension limit MPa": tension_limit,
                }
            )

    governing = max(fiber_rows, key=lambda row: float(row["Utilization value"]), default=None)
    compression_candidates = [row for row in fiber_rows if float(row["Compression utilization"]) > 0.0]
    tension_candidates = [row for row in fiber_rows if float(row["Tension utilization"]) > 0.0]
    joint_candidates = [
        row for row in fiber_rows if math.isfinite(float(row.get("Joint utilization") or float("nan")))
    ]
    governing_compression = max(
        compression_candidates,
        key=lambda row: float(row["Compression utilization"]),
        default=None,
    )
    governing_tension = max(
        tension_candidates,
        key=lambda row: float(row["Tension utilization"]),
        default=None,
    )
    governing_joint = max(
        joint_candidates,
        key=lambda row: float(row["Joint utilization"]),
        default=None,
    )
    status = "FAIL" if any(row["Status"] == "FAIL" for row in rows) else "PASS"
    return {
        "schema": "crossbeam-sls1a-transfer-stress-result-v1",
        "input_fingerprint": preparation.fingerprint,
        "status": status,
        "rows": rows,
        "fiber_rows": fiber_rows,
        "governing_row": governing,
        "governing_compression": governing_compression,
        "governing_tension": governing_tension,
        "governing_joint": governing_joint,
        "required_actions": _required_actions(fiber_rows),
        "warnings": list(preparation.warnings),
        "errors": [],
        "station_face_checks": len(rows),
        "fiber_checks": len(fiber_rows),
        "code_basis": "ACI 318-19 Tables 24.5.3.1 and 24.5.3.2",
        "scope": (
            "Transfer-stage gross-section extreme-fiber concrete stress only. Imported P/M3 are used once. "
            "V2/T, principal stress, shear/torsion, anchorage-zone, local D-region, transfer/development length, "
            "and ACI 318-19 24.5.3.2.1 total tensile-force reinforcement design remain separate."
        ),
    }
