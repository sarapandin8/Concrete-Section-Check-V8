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
CROSSBEAM_SERVICE_RESULT_KEY = "crossbeam_sls1b_service_stress_result"
CROSSBEAM_SERVICE_RESULT_HASH_KEY = "crossbeam_sls1b_service_stress_input_hash"
CROSSBEAM_SLS_LOAD_TABLE_KEY = "crossbeam_sls_loads_table"
CROSSBEAM_LENGTH_KEY = "crossbeam_ui1_length_m"
CROSSBEAM_SEGMENT_ROWS_KEY = "crossbeam_ui1_segment_layout_rows"

ACI_TRANSFER_COMPRESSION_FACTOR = 0.60
ACI_TRANSFER_TENSION_FACTOR_MPA = 0.25
ACI_SERVICE_TOTAL_COMPRESSION_FACTOR = 0.60
ACI_SERVICE_CLASS_U_TENSION_FACTOR_MPA = 0.62
ACI_SERVICE_CLASS_T_TENSION_FACTOR_MPA = 1.00
PHYSICAL_JOINT_TRANSFER_MAX_TENSION_MPA = 0.0
PHYSICAL_JOINT_SERVICE_MIN_COMPRESSION_MPA = 0.70
# Backward-compatible alias retained for Final Service callers/tests that
# imported the earlier generic name.  The 0.70 MPa gate is service-only.
PHYSICAL_JOINT_MIN_COMPRESSION_MPA = PHYSICAL_JOINT_SERVICE_MIN_COMPRESSION_MPA
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
    derived_joint_rows: tuple[dict[str, Any], ...] = ()


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
    skip_pairs: set[tuple[str, float]] | None = None,
) -> list[str]:
    errors: list[str] = []
    for case in cases:
        for joint in joint_stations:
            if (case, float(joint)) in (skip_pairs or set()):
                continue
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


def _finite_station(row: Mapping[str, Any]) -> float | None:
    try:
        station = float(row.get("Station s (m)"))
    except (TypeError, ValueError):
        return None
    return station if math.isfinite(station) else None


def _interpolation_source_row(
    rows: list[dict[str, Any]],
    *,
    station_m: float,
    tolerance_m: float,
) -> dict[str, Any] | None:
    """Return one unambiguous row at an interpolation bracket station."""

    at_station = [
        row
        for row in rows
        if (value := _finite_station(row)) is not None
        and abs(value - float(station_m)) <= tolerance_m
    ]
    if not at_station:
        return None
    unlabeled = [row for row in at_station if not str(row.get("Check Point") or "").strip()]
    if len(unlabeled) == 1:
        return unlabeled[0]
    candidates = unlabeled or at_station
    first = candidates[0]
    for other in candidates[1:]:
        for key in ("P", "V2", "T", "M3"):
            try:
                delta = abs(float(other.get(key) or 0.0) - float(first.get(key) or 0.0))
            except (TypeError, ValueError):
                return None
            if delta > 1.0e-9:
                return None
    return first


def _derive_precast_joint_demands(
    active_demands: list[dict[str, Any]],
    *,
    joint_stations: list[float],
    tolerance_m: float,
    stage: str = "Transfer stage",
    stage_label: str = "Transfer",
) -> tuple[list[dict[str, Any]], list[str], set[tuple[str, float]]]:
    """Linearly interpolate missing Precast joint resultants without extrapolation.

    One derived resultant is expanded to the left and right Section faces by the
    normal preparation route.  Exact imported joint rows always remain
    authoritative, including intentionally side-labelled rows.
    """

    derived: list[dict[str, Any]] = []
    blockers: list[str] = []
    blocked_pairs: set[tuple[str, float]] = set()
    cases = sorted({str(row.get("Case Name") or "") for row in active_demands})
    for case in cases:
        case_rows = [row for row in active_demands if str(row.get("Case Name") or "") == case]
        stations = sorted(
            {
                value
                for row in case_rows
                if (value := _finite_station(row)) is not None
            }
        )
        for joint in joint_stations:
            if any(abs(value - joint) <= tolerance_m for value in stations):
                continue
            lower = [value for value in stations if value < joint - tolerance_m]
            upper = [value for value in stations if value > joint + tolerance_m]
            if not lower or not upper:
                blockers.append(
                    f"{case}: physical joint at s = {joint:.6f} m cannot be auto-interpolated because active {stage_label} rows do not bracket the joint."
                )
                blocked_pairs.add((case, float(joint)))
                continue
            s0 = max(lower)
            s1 = min(upper)
            row0 = _interpolation_source_row(case_rows, station_m=s0, tolerance_m=tolerance_m)
            row1 = _interpolation_source_row(case_rows, station_m=s1, tolerance_m=tolerance_m)
            if row0 is None or row1 is None or s1 <= s0:
                blockers.append(
                    f"{case}: physical joint at s = {joint:.6f} m cannot be auto-interpolated because a bracketing station has ambiguous duplicate {stage_label} resultants."
                )
                blocked_pairs.add((case, float(joint)))
                continue
            ratio = (joint - s0) / (s1 - s0)
            interpolated: dict[str, Any] = {
                "Active": True,
                "Station s (m)": float(joint),
                "Check Point": "AUTO JOINT INTERPOLATION",
                "Case Name": case,
                "Stage": stage,
                "Note": (
                    f"Auto-interpolated physical-joint resultant from s={s0:.6f} m and "
                    f"s={s1:.6f} m; used for both s-/s+ Section faces."
                ),
                "_auto_joint_interpolated": True,
                "_interpolation_from_m": [float(s0), float(s1)],
            }
            for key in ("P", "V2", "T", "M3"):
                value0 = float(row0.get(key) or 0.0)
                value1 = float(row1.get(key) or 0.0)
                interpolated[key] = value0 + ratio * (value1 - value0)
            derived.append(interpolated)
    return derived, _dedupe(blockers), blocked_pairs


def _build_crossbeam_stress_preparation(
    state: Any,
    *,
    stage: str,
    stage_label: str,
    schema: str,
    transfer_stage: bool,
) -> CrossbeamTransferPreparation:
    """Build validated gross-section checks for one Crossbeam SLS stage."""

    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    length_m = float(_get(state, CROSSBEAM_LENGTH_KEY, 0.0) or 0.0)
    if length_m <= 0.0:
        errors.append("Crossbeam physical length L must be positive.")

    construction_method = normalize_construction_method(
        _get(state, CB_LOSS_ES_CONSTRUCTION_METHOD_KEY, CONSTRUCTION_METHOD_PRECAST)
    )
    if transfer_stage:
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
    else:
        stressing_ratio = 1.0

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
    demand_rows = [row for row in all_sls if canonical_sls_stage(row.get("Stage")) == stage]
    validation = validate_station_force_rows(
        demand_rows,
        contract=contract,
        member_length_m=max(length_m, 0.0),
        response_type="SLS",
        rows_are_canonical=True,
        expected_sls_stage=stage,
    )
    errors.extend(validation.errors)
    warnings.extend(validation.warnings)
    active_demands = [row for row in demand_rows if bool(row.get("Active", True))]
    if not active_demands:
        errors.append(f"No active SLS {stage_label} station-force rows are available.")

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
            "schema": schema,
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
            derived_joint_rows=(),
        )

    tolerance_m = max(_STATION_TOLERANCE_MIN_M, length_m * 1.0e-9)
    derived_joint_rows: list[dict[str, Any]] = []
    interpolation_blocked_pairs: set[tuple[str, float]] = set()
    if construction_method == CONSTRUCTION_METHOD_PRECAST:
        derived_joint_rows, interpolation_errors, interpolation_blocked_pairs = _derive_precast_joint_demands(
            active_demands,
            joint_stations=joint_stations,
            tolerance_m=tolerance_m,
            stage=stage,
            stage_label=stage_label,
        )
        errors.extend(interpolation_errors)
    check_demands = active_demands + derived_joint_rows
    prepared: list[PreparedCrossbeamTransferRow] = []
    for demand in check_demands:
        station = float(demand.get("Station s (m)") or 0.0)
        case = str(demand.get("Case Name") or ("SLS-TR" if transfer_stage else "SLS-SERV"))
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
            source_notes = list(summary.warnings)
            if bool(demand.get("_auto_joint_interpolated")):
                source_notes.append(str(demand.get("Note") or "Auto-interpolated physical-joint resultant."))
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
                    notes=tuple(source_notes),
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
                skip_pairs=interpolation_blocked_pairs,
            )
        )

    if prepared:
        info.extend(
            [
                f"Prepared {len(prepared)} {stage_label} station/face concrete-stress checks.",
                f"Active imported {stage_label} rows: {len(active_demands)}.",
                "Demand mapping: P compression-positive; M3 sagging-positive; V2/T retained for row-coupled audit only.",
                f"Imported FEA {stage_label} resultants are used exactly once; prestress and secondary effects are not added again.",
            ]
        )
    if derived_joint_rows:
        warnings.append(
            f"{len(derived_joint_rows)} physical-joint resultant row(s) were linearly interpolated from active bracketing {stage_label} stations and expanded to both s-/s+ Section faces."
        )
    warnings.append(
        "Stress lines connect verified imported stations for visualization only; no compliance is inferred between unverified stations."
    )
    errors = _dedupe(errors)
    warnings = _dedupe(warnings)
    fingerprint_payload = {
        "schema": schema,
        "construction_method": construction_method,
        "stressing_strength_ratio": stressing_ratio,
        "contract": contract,
        "demands": demand_rows,
        "derived_joint_demands": derived_joint_rows,
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
        derived_joint_rows=tuple(derived_joint_rows),
    )


def build_crossbeam_transfer_stress_preparation(state: Any) -> CrossbeamTransferPreparation:
    """Build validated gross-section transfer checks from Crossbeam SLS rows."""

    return _build_crossbeam_stress_preparation(
        state,
        stage="Transfer stage",
        stage_label="At Transfer",
        # v4 invalidates stored SLS1A results created before the adopted
        # Precast Segmental Transfer joint rule was corrected from the
        # Final-Service 0.70 MPa compression gate to a zero-tension gate.
        schema="crossbeam-sls1a-transfer-preparation-v4",
        transfer_stage=True,
    )


def build_crossbeam_service_stress_preparation(state: Any) -> CrossbeamTransferPreparation:
    """Build validated gross-section final-service checks from Crossbeam SLS rows."""

    return _build_crossbeam_stress_preparation(
        state,
        stage="Final service stage",
        stage_label="At Final Service",
        schema="crossbeam-sls1b-service-preparation-v1",
        transfer_stage=False,
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
    joint_exceedance: float | None = None
    joint_margin: float | None = None
    if physical_joint:
        # Adopted Precast Segmental Transfer rule: physical joints may not
        # carry concrete tension.  With the app stress convention
        # compression < 0 and tension > 0, every s-/s+ Top/Bottom fiber must
        # satisfy signed stress <= 0.0 MPa.  This is a binary zero-limit gate,
        # so a demand/capacity ratio is intentionally not fabricated.
        signed = float(stress_mpa)
        joint_margin = PHYSICAL_JOINT_TRANSFER_MAX_TENSION_MPA - signed
        joint_exceedance = max(signed - PHYSICAL_JOINT_TRANSFER_MAX_TENSION_MPA, 0.0)
        joint_pass = signed <= PHYSICAL_JOINT_TRANSFER_MAX_TENSION_MPA + 1.0e-12
        if not joint_pass:
            criterion = "Physical-joint no tension at Transfer"
            actual = signed
            limit = PHYSICAL_JOINT_TRANSFER_MAX_TENSION_MPA
    # Keep the ACI ratio available for audit, but do not present it as the
    # utilization of a zero-tension joint gate.  A zero allowable tension has
    # no finite D/C; downstream summaries therefore show N/A when this gate
    # controls while the separate ACI compression/tension ratios remain fully
    # traceable.
    utilization = float("nan") if physical_joint and not joint_pass else general_util
    general_pass = general_util <= 1.0 + 1.0e-12
    return {
        "status": "PASS" if general_pass and joint_pass else "FAIL",
        "utilization": utilization,
        "compression_utilization": compression_util,
        "tension_utilization": tension_util,
        "aci_utilization": general_util,
        "joint_utilization": joint_util,
        "joint_no_tension_exceedance_mpa": joint_exceedance,
        "criterion": criterion,
        "actual_mpa": actual,
        "limit_mpa": limit,
        "joint_margin_mpa": joint_margin,
    }


def _required_actions(fiber_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failed = [row for row in fiber_rows if str(row.get("Status")) == "FAIL"]
    actions: list[dict[str, Any]] = []
    joint = [
        row
        for row in failed
        if math.isfinite(float(row.get("Joint no-tension margin MPa") or float("nan")))
        and float(row.get("Joint no-tension margin MPa")) < -1.0e-12
    ]
    if joint:
        governing = max(joint, key=lambda row: float(row.get("Stress MPa") or 0.0))
        actions.append(
            {
                "Priority": "High",
                "Module": "Physical joint",
                "Issue": (
                    f"No-tension Transfer joint gate fails at s={governing['Station s (m)']:.3f} m / "
                    f"{governing['Section face']} / {governing['Fiber']} / {governing['Case']}: "
                    f"signed stress {float(governing['Stress MPa']):+.3f} MPa "
                    f"({'tension' if float(governing['Stress MPa']) > 0.0 else 'compression'}), "
                    f"required <= {PHYSICAL_JOINT_TRANSFER_MAX_TENSION_MPA:+.3f} MPa."
                ),
                "Required Action": (
                    "Revise Transfer tendon force/profile, stressing sequence, support/contact stage, or joint/section geometry until both s-/s+ top and bottom fibers are non-tensile (signed stress <= 0.0 MPa)."
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
        row_utilization = max(float(top_check["aci_utilization"]), float(bottom_check["aci_utilization"]))
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
                "Top utilization": float(top_check["aci_utilization"]),
                "Bottom utilization": float(bottom_check["aci_utilization"]),
                "Governing utilization": row_utilization,
                "Top criterion": str(top_check["criterion"]),
                "Bottom criterion": str(bottom_check["criterion"]),
                "Joint Transfer tension limit MPa": (
                    PHYSICAL_JOINT_TRANSFER_MAX_TENSION_MPA if source.is_physical_joint else float("nan")
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
                    "Joint no-tension margin MPa": (
                        float(check["joint_margin_mpa"])
                        if check["joint_margin_mpa"] is not None
                        else float("nan")
                    ),
                    "Joint no-tension exceedance MPa": (
                        float(check["joint_no_tension_exceedance_mpa"])
                        if check["joint_no_tension_exceedance_mpa"] is not None
                        else float("nan")
                    ),
                    "Utilization value": float(check["utilization"]),
                    "f'ci MPa": source.fci_mpa,
                    "Compression limit MPa": -compression_limit,
                    "Tension limit MPa": tension_limit,
                }
            )

    failed_joint_candidates = [
        row
        for row in fiber_rows
        if math.isfinite(float(row.get("Joint no-tension margin MPa") or float("nan")))
        and float(row.get("Joint no-tension margin MPa")) < -1.0e-12
    ]
    # A failed zero-tension joint gate controls the engineering result even
    # though no finite D/C exists for a zero allowable tension.  Within tied
    # joint failures, report the most tensile fiber deterministically.
    governing = (
        max(failed_joint_candidates, key=lambda row: float(row.get("Stress MPa") or 0.0))
        if failed_joint_candidates
        else max(fiber_rows, key=lambda row: float(row["Utilization value"]), default=None)
    )
    compression_candidates = [row for row in fiber_rows if float(row["Compression utilization"]) > 0.0]
    tension_candidates = [row for row in fiber_rows if float(row["Tension utilization"]) > 0.0]
    joint_candidates = [
        row
        for row in fiber_rows
        if math.isfinite(float(row.get("Joint no-tension exceedance MPa") or float("nan")))
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
        key=lambda row: float(row["Joint no-tension exceedance MPa"]),
        default=None,
    )
    status = "FAIL" if any(row["Status"] == "FAIL" for row in rows) else "PASS"
    return {
        "schema": "crossbeam-sls1a-transfer-stress-result-v2",
        "input_fingerprint": preparation.fingerprint,
        "construction_method": preparation.construction_method,
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
        "code_basis": (
            "ACI 318-19 Tables 24.5.3.1 and 24.5.3.2 + project Precast physical-joint no-tension rule at Transfer"
            if preparation.construction_method == CONSTRUCTION_METHOD_PRECAST
            else "ACI 318-19 Tables 24.5.3.1 and 24.5.3.2"
        ),
        "scope": (
            "Transfer-stage gross-section extreme-fiber concrete stress only. Imported P/M3 are used once. "
            "V2/T, principal stress, shear/torsion, anchorage-zone, local D-region, transfer/development length, "
            "and ACI 318-19 24.5.3.2.1 total tensile-force reinforcement design remain separate."
        ),
    }


def _service_fiber_check(
    stress_mpa: float,
    *,
    fc_mpa: float,
    physical_joint: bool,
    section_class: str,
) -> dict[str, Any]:
    """Check one final-service gross-section fiber under ACI 318-19.

    Gross stress classifies the complete section before any Class C stress
    verification is attempted.  Table 24.5.4.1 compression limits apply only
    to Class U/T members; a Class C section instead requires a cracked
    transformed-section stress analysis under 24.5.2.3.  The project physical-
    joint minimum-compression criterion remains independent and can still FAIL
    a Class C section.
    """

    compression_limit = ACI_SERVICE_TOTAL_COMPRESSION_FACTOR * fc_mpa
    class_u_limit = ACI_SERVICE_CLASS_U_TENSION_FACTOR_MPA * math.sqrt(fc_mpa)
    class_t_limit = ACI_SERVICE_CLASS_T_TENSION_FACTOR_MPA * math.sqrt(fc_mpa)
    compression = max(-float(stress_mpa), 0.0)
    tension = max(float(stress_mpa), 0.0)
    compression_util = compression / compression_limit
    class_u_util = tension / class_u_limit
    class_t_util = tension / class_t_limit

    if section_class == "Class C":
        status = "REVIEW"
        classification = "Class C"
        criterion = "ACI Class C cracked-section route"
        actual = float(stress_mpa)
        limit = class_t_limit
    elif compression_util > 1.0 + 1.0e-12:
        status = "FAIL"
        classification = "Compression exceeds total-load limit"
        criterion = "ACI service total-load compression"
        actual = compression
        limit = compression_limit
    elif tension <= class_u_limit + 1.0e-12:
        status = "PASS"
        classification = "Class U"
        criterion = "ACI Class U tension"
        actual = tension
        limit = class_u_limit
    elif tension <= class_t_limit + 1.0e-12:
        status = "REVIEW"
        classification = "Class T"
        criterion = "ACI Class T classification"
        actual = tension
        limit = class_t_limit
    else:
        status = "REVIEW"
        classification = "Class C"
        criterion = "ACI Class C classification"
        actual = tension
        limit = class_t_limit

    joint_util: float | None = None
    joint_margin: float | None = None
    if physical_joint:
        joint_margin = compression - PHYSICAL_JOINT_MIN_COMPRESSION_MPA
        if compression > 0.0:
            joint_util = PHYSICAL_JOINT_MIN_COMPRESSION_MPA / compression
        else:
            joint_util = 1.001 + tension / PHYSICAL_JOINT_MIN_COMPRESSION_MPA
        if stress_mpa > -PHYSICAL_JOINT_MIN_COMPRESSION_MPA + 1.0e-12:
            status = "FAIL"
            criterion = "Physical-joint minimum compression"
            actual = compression
            limit = PHYSICAL_JOINT_MIN_COMPRESSION_MPA

    # Table 24.5.4.1 is not a Class C acceptance check. Keep a useful
    # classification ratio for ordering the Class C review while preserving
    # the independent project physical-joint gate.
    if section_class == "Class C":
        utilization = max(class_t_util, float(joint_util or 0.0))
    else:
        utilization = max(
            compression_util,
            class_u_util,
            float(joint_util or 0.0),
        )
    return {
        "status": status,
        "classification": classification,
        "criterion": criterion,
        "actual_mpa": actual,
        "limit_mpa": limit,
        "compression_utilization": compression_util,
        "class_u_utilization": class_u_util,
        "class_t_utilization": class_t_util,
        "joint_utilization": joint_util,
        "joint_margin_mpa": joint_margin,
        "utilization": utilization,
        "compression_limit_mpa": compression_limit,
        "class_u_limit_mpa": class_u_limit,
        "class_t_limit_mpa": class_t_limit,
        "section_class": section_class,
    }


def _service_section_class(top_stress_mpa: float, bottom_stress_mpa: float, fc_mpa: float) -> str:
    """Return the ACI gross-section service classification for one section face."""

    tension = max(float(top_stress_mpa), float(bottom_stress_mpa), 0.0)
    root_fc = math.sqrt(float(fc_mpa))
    if tension <= ACI_SERVICE_CLASS_U_TENSION_FACTOR_MPA * root_fc + 1.0e-12:
        return "Class U"
    if tension <= ACI_SERVICE_CLASS_T_TENSION_FACTOR_MPA * root_fc + 1.0e-12:
        return "Class T"
    return "Class C"


def _service_required_actions(fiber_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    failed_joints = [
        row
        for row in fiber_rows
        if math.isfinite(float(row.get("Joint compression margin MPa") or float("nan")))
        and float(row.get("Joint compression margin MPa")) < -1.0e-12
    ]
    if failed_joints:
        governing = max(failed_joints, key=lambda row: float(row.get("Utilization value") or 0.0))
        actions.append(
            {
                "Priority": "High",
                "Module": "Physical joint",
                "Issue": (
                    f"Final-service minimum compression fails at s={governing['Station s (m)']:.3f} m / "
                    f"{governing['Section face']} / {governing['Fiber']} / {governing['Case']}: "
                    f"signed stress {float(governing['Stress MPa']):+.3f} MPa "
                    f"({'tension' if float(governing['Stress MPa']) > 0.0 else 'compression'}), "
                    f"required <= {-PHYSICAL_JOINT_MIN_COMPRESSION_MPA:.3f} MPa."
                ),
                "Required Action": (
                    "Revise effective prestress, tendon profile, final service demand, or joint/section geometry until both s-/s+ top and bottom fibers remain at least 0.70 MPa in compression."
                ),
            }
        )
    compression = [
        row
        for row in fiber_rows
        if str(row.get("Section ACI class") or "") != "Class C"
        if float(row.get("Compression utilization") or 0.0) > 1.0 + 1.0e-12
    ]
    if compression:
        governing = max(compression, key=lambda row: float(row.get("Compression utilization") or 0.0))
        actions.append(
            {
                "Priority": "High",
                "Module": "ACI service compression",
                "Issue": (
                    f"Total-load compression exceeds 0.60f'c at s={governing['Station s (m)']:.3f} m / "
                    f"{governing['Fiber']} / {governing['Case']}."
                ),
                "Required Action": (
                    "Verify the imported final-service response and final effective-prestress basis, then revise prestress, eccentricity, service demand, or gross section before acceptance."
                ),
            }
        )
    class_c = [row for row in fiber_rows if str(row.get("ACI class")) == "Class C"]
    if class_c:
        governing = max(class_c, key=lambda row: float(row.get("Class U utilization") or 0.0))
        actions.append(
            {
                "Priority": "High",
                "Module": "ACI Class C service route",
                "Issue": (
                    f"Gross-section tension exceeds 1.00sqrt(f'c) at s={governing['Station s (m)']:.3f} m / "
                    f"{governing['Fiber']} / {governing['Case']}."
                ),
                "Required Action": (
                    "Complete a cracked transformed-section service-stress analysis in accordance with ACI 318-19 24.5.2.3 before final acceptance. "
                    "The current total-response FEA P/M bucket is retained for gross classification and is not reused as a fabricated cracked-section result."
                ),
            }
        )
    elif any(str(row.get("ACI class")) == "Class T" for row in fiber_rows):
        governing = max(
            (row for row in fiber_rows if str(row.get("ACI class")) == "Class T"),
            key=lambda row: float(row.get("Class U utilization") or 0.0),
        )
        actions.append(
            {
                "Priority": "Medium",
                "Module": "ACI Class T service route",
                "Issue": (
                    f"Final-service tension is Class T at s={governing['Station s (m)']:.3f} m / "
                    f"{governing['Fiber']} / {governing['Case']}."
                ),
                "Required Action": (
                    "Carry the Class T classification into the serviceability and deflection review; this gross-section stress result is not a Class U PASS."
                ),
            }
        )
    return actions


def run_crossbeam_service_stress(preparation: CrossbeamTransferPreparation) -> dict[str, Any]:
    """Calculate final-service gross-section stress and ACI classification."""

    if not preparation.ready:
        raise ValueError("Crossbeam Final Service stress preparation is not ready.")
    rows: list[dict[str, Any]] = []
    fiber_rows: list[dict[str, Any]] = []
    for source in preparation.rows:
        axial_mpa = -source.source_p_kn * 1000.0 / source.area_mm2
        top_bending_mpa = -source.source_m3_knm * 1_000_000.0 / source.z_top_mm3
        bottom_bending_mpa = source.source_m3_knm * 1_000_000.0 / source.z_bottom_mm3
        top_stress = axial_mpa + top_bending_mpa
        bottom_stress = axial_mpa + bottom_bending_mpa
        section_class = _service_section_class(top_stress, bottom_stress, source.fc_mpa)
        top_check = _service_fiber_check(
            top_stress,
            fc_mpa=source.fc_mpa,
            physical_joint=source.is_physical_joint,
            section_class=section_class,
        )
        bottom_check = _service_fiber_check(
            bottom_stress,
            fc_mpa=source.fc_mpa,
            physical_joint=source.is_physical_joint,
            section_class=section_class,
        )
        statuses = {str(top_check["status"]), str(bottom_check["status"])}
        status = "FAIL" if "FAIL" in statuses else ("REVIEW" if "REVIEW" in statuses else "PASS")
        row_utilization = max(float(top_check["utilization"]), float(bottom_check["utilization"]))
        rows.append(
            {
                "Check": "Concrete Stress At Final Service",
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
                "A mm2": source.area_mm2,
                "Ix mm4": source.ix_mm4,
                "Ztop mm3": source.z_top_mm3,
                "Zbottom mm3": source.z_bottom_mm3,
                "Axial stress MPa": axial_mpa,
                "Top bending stress MPa": top_bending_mpa,
                "Bottom bending stress MPa": bottom_bending_mpa,
                "Top stress MPa": top_stress,
                "Bottom stress MPa": bottom_stress,
                "Compression limit MPa": -float(top_check["compression_limit_mpa"]),
                "Tension limit MPa": float(top_check["class_u_limit_mpa"]),
                "Class T upper MPa": float(top_check["class_t_limit_mpa"]),
                "Section ACI class": section_class,
                "Top ACI class": str(top_check["classification"]),
                "Bottom ACI class": str(bottom_check["classification"]),
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
                    "ACI class": str(check["classification"]),
                    "Section ACI class": section_class,
                    "Criterion": str(check["criterion"]),
                    "Actual MPa": float(check["actual_mpa"]),
                    "Limit MPa": float(check["limit_mpa"]),
                    "Compression utilization": float(check["compression_utilization"]),
                    "Class U utilization": float(check["class_u_utilization"]),
                    "Class T utilization": float(check["class_t_utilization"]),
                    "Tension utilization": float(check["class_u_utilization"]),
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
                    "f'c MPa": source.fc_mpa,
                    "Compression limit MPa": -float(check["compression_limit_mpa"]),
                    "Tension limit MPa": float(check["class_u_limit_mpa"]),
                    "Class T upper MPa": float(check["class_t_limit_mpa"]),
                }
            )

    governing = max(fiber_rows, key=lambda row: float(row["Utilization value"]), default=None)
    statuses = {str(row.get("Status")) for row in fiber_rows}
    status = "FAIL" if "FAIL" in statuses else ("REVIEW" if "REVIEW" in statuses else "PASS")
    class_rank = {"Class U": 0, "Class T": 1, "Class C": 2}
    overall_class = max(
        (str(row.get("Section ACI class") or "Class U") for row in fiber_rows),
        key=lambda value: class_rank.get(value, -1),
        default="Class U",
    )
    cracked_status = "REVIEW REQUIRED" if overall_class == "Class C" else "NOT REQUIRED FOR STRESS"
    return {
        "schema": "crossbeam-sls1b-service-stress-result-v1",
        "input_fingerprint": preparation.fingerprint,
        "construction_method": preparation.construction_method,
        "status": status,
        "rows": rows,
        "fiber_rows": fiber_rows,
        "governing_row": governing,
        "overall_aci_class": overall_class,
        "gross_classification_status": "COMPLETE",
        "cracked_transformed_status": cracked_status,
        "required_actions": _service_required_actions(fiber_rows),
        "warnings": list(preparation.warnings)
        + [
            "For Class U/T, the imported Final Service bucket is checked as prestress plus total load against 0.60f'c. "
            "Class C instead requires cracked transformed-section analysis. A separate sustained-load response is required to check the ACI 318-19 0.45f'c limit where applicable."
        ],
        "errors": [],
        "station_face_checks": len(rows),
        "fiber_checks": len(fiber_rows),
        "code_basis": "ACI 318-19 Sections 24.5.2.1 through 24.5.2.3 and Table 24.5.4.1 (Class U/T only)",
        "scope": (
            "Final-service gross-section extreme-fiber concrete stress using verified external-FEA total resultants. "
            "Imported P/M3 are used once; effective prestress and secondary response are not added again. "
            "Gross stress is used only to classify Class C; Table 24.5.4.1 compression limits are not applied to Class C. "
            "Class C remains REVIEW REQUIRED until a separate cracked transformed-section result is available, and the sustained-load 0.45f'c condition remains a separate source check."
        ),
    }
