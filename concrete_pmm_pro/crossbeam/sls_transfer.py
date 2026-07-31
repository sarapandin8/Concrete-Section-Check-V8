"""ACI 318-19 transfer-stage concrete stress checks for Portal Frame Crossbeam.

CROSSBEAM.SLS1A consumes the validated ``SLS At Transfer`` station contexts
assembled by :mod:`analysis_foundation`.  External FEA remains the sole source
of row-coupled ``P`` and ``M3`` demand.  The app does not add prestress force or
secondary prestress again.

Stress convention used by the result workspace follows the accepted
Beam/Girder SLS charts:

* compression is negative;
* tension is positive;
* source ``P`` is compression-positive; and
* source ``M3`` is sagging-positive.

For a Portal Frame Crossbeam, every station is treated as an ``all other
locations`` station in ACI 318-19 Tables 24.5.3.1 and 24.5.3.2.  The special
simply-supported-member end limits are therefore not used.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from typing import Any

from concrete_pmm_pro.core.concrete_materials import (
    concrete_materials_by_name,
    ensure_concrete_material_library,
)
from concrete_pmm_pro.crossbeam.analysis_foundation import (
    DATASET_SLS_TRANSFER,
)
from concrete_pmm_pro.crossbeam.prestress_loss import (
    DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
    MIN_CROSSBEAM_STRESSING_STRENGTH_RATIO,
)
from concrete_pmm_pro.crossbeam.section_library import canonical_section_definitions
from concrete_pmm_pro.crossbeam.tendon import canonical_tendon_system_rows


CROSSBEAM_SLS_TRANSFER_SCHEMA = "crossbeam-sls-transfer-stress-v2"
CB_ANALYSIS_SLS_TRANSFER_RESULT_KEY = "crossbeam_analysis_sls1a_transfer_result"
DEFAULT_JOINT_MIN_COMPRESSION_MPA = 0.70


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, float) and math.isnan(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return bool(value)


def _joint_gate_required(foundation: Mapping[str, Any]) -> bool:
    """Return whether the active construction route has physical segment joints."""

    construction_method = _text(foundation.get("construction_method"))
    if construction_method:
        return construction_method.casefold() == "precast segmental"
    # Compatibility for pre-CIP test fixtures and legacy foundations that did
    # not yet persist the construction method explicitly.
    return any(
        _text(row.get("Boundary type")) == "Physical segment joint"
        for row in _records(foundation.get("internal_boundaries"))
    )


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            rows = value.to_dict(orient="records")
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
        except Exception:
            pass
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _jsonable_material(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        try:
            payload = value.model_dump(mode="json")
            if isinstance(payload, Mapping):
                return dict(payload)
        except Exception:
            pass
    if isinstance(value, Mapping):
        return dict(value)
    return {
        "name": _text(getattr(value, "name", "")),
        "fc_MPa": _float(getattr(value, "fc_MPa", 0.0)),
        "Ec_method": _text(getattr(value, "Ec_method", "")),
        "Ec_MPa": getattr(value, "Ec_MPa", None),
    }


def _fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def transfer_stress_input_fingerprint(
    *,
    foundation: Mapping[str, Any],
    section_definitions: Any,
    concrete_material: Any = None,
    concrete_materials: Any = None,
    active_concrete_material_name: str | None = None,
    deck_topping_material_name: str | None = None,
    tendon_system_rows: Any = None,
    stressing_strength_ratio: Any = DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
    joint_min_compression_mpa: float = DEFAULT_JOINT_MIN_COMPRESSION_MPA,
) -> str:
    """Return the current input hash without running the stress check."""

    try:
        library = ensure_concrete_material_library(
            concrete_material=concrete_material,
            concrete_materials=concrete_materials,
            active_concrete_material_name=active_concrete_material_name,
            deck_topping_material_name=deck_topping_material_name,
        )
        materials = [_jsonable_material(item) for item in library.materials]
    except Exception:
        materials = [_jsonable_material(item) for item in (concrete_materials or [])]
    return _fingerprint(
        {
            "schema": CROSSBEAM_SLS_TRANSFER_SCHEMA,
            "foundation": _text(foundation.get("fingerprint")),
            "definitions": canonical_section_definitions(section_definitions),
            "materials": materials,
            "tendon_system": canonical_tendon_system_rows(tendon_system_rows),
            "stressing_strength_ratio": _float(stressing_strength_ratio),
            "joint_min_compression_mpa": _float(joint_min_compression_mpa),
        }
    )


def _fiber_check(stress_mpa: float, *, compression_limit_mpa: float, tension_limit_mpa: float) -> dict[str, Any]:
    """Return the applicable signed limit and utilization for one fiber."""

    if stress_mpa < 0.0:
        demand = "Compression"
        limit_signed = -float(compression_limit_mpa)
        utilization = abs(float(stress_mpa)) / float(compression_limit_mpa) if compression_limit_mpa > 0.0 else math.inf
    else:
        demand = "Tension"
        limit_signed = float(tension_limit_mpa)
        utilization = float(stress_mpa) / float(tension_limit_mpa) if tension_limit_mpa > 0.0 else (0.0 if stress_mpa <= 0.0 else math.inf)
    return {
        "Demand type": demand,
        "Applicable limit (MPa)": limit_signed,
        "Utilization": utilization,
        "Status": "PASS" if math.isfinite(utilization) and utilization <= 1.0 + 1.0e-12 else "FAIL",
    }


def _joint_case_coverage_errors(
    *,
    foundation: Mapping[str, Any],
    transfer_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Require at least one mapped result at every physical joint for every case.

    Analysis Foundation may expand one imported station row to both adjacent
    Section IDs internally.  The production joint gate no longer requires the
    user to provide or review separate ``s-``/``s+`` results.  One governing
    Top value and one governing Bottom value are reported per physical joint.
    """

    if not _joint_gate_required(foundation):
        return []

    boundaries = [
        dict(row)
        for row in _records(foundation.get("internal_boundaries"))
        if _text(row.get("Boundary type")) == "Physical segment joint"
    ]
    if not boundaries:
        return []
    cases = sorted({_text(row.get("Case / Combination")) for row in transfer_rows if _text(row.get("Case / Combination"))})
    tolerance = max(1.0e-7, abs(_float(foundation.get("member_length_m"))) * 1.0e-8)
    errors: list[str] = []
    for case_name in cases:
        case_rows = [row for row in transfer_rows if _text(row.get("Case / Combination")) == case_name]
        for boundary in boundaries:
            station = _float(boundary.get("Station s (m)"))
            matches = [
                row
                for row in case_rows
                if bool(row.get("Physical segment joint"))
                and abs(_float(row.get("Station s (m)")) - station) <= tolerance
            ]
            if not matches:
                errors.append(
                    f"Case {case_name}: physical joint {_text(boundary.get('Boundary ID')) or '?'} at "
                    f"s = {station:.6f} m requires one joint result with both Top and Bottom fibers."
                )
    return errors


def _joint_summary_rows(
    *,
    foundation: Mapping[str, Any],
    result_rows: Sequence[Mapping[str, Any]],
    joint_limit_mpa: float,
) -> list[dict[str, Any]]:
    """Collapse internal adjacent-face calculations to one result per joint/case.

    If adjacent Segment section properties differ, each side is still evaluated
    internally using the same row-coupled FEA force state.  The displayed Top
    and Bottom values are the numerically greatest signed stresses, meaning the
    values closest to zero or furthest into tension.  They are therefore the
    governing values for joint-opening prevention under the adopted convention
    Compression = negative and Tension = positive.
    """

    if not _joint_gate_required(foundation):
        return []

    boundaries = [
        dict(row)
        for row in _records(foundation.get("internal_boundaries"))
        if _text(row.get("Boundary type")) == "Physical segment joint"
    ]
    if not boundaries:
        return []
    cases = sorted(
        {
            _text(row.get("Case / Combination"))
            for row in result_rows
            if _text(row.get("Case / Combination"))
        }
    )
    tolerance = max(1.0e-7, abs(_float(foundation.get("member_length_m"))) * 1.0e-8)
    summaries: list[dict[str, Any]] = []
    for case_name in cases:
        for boundary in boundaries:
            station = _float(boundary.get("Station s (m)"))
            matches = [
                row
                for row in result_rows
                if _text(row.get("Case / Combination")) == case_name
                and bool(row.get("Physical segment joint"))
                and abs(_float(row.get("Station s (m)")) - station) <= tolerance
            ]
            if not matches:
                continue

            top_source = max(matches, key=lambda row: _float(row.get("Top stress (MPa)"), -math.inf))
            bottom_source = max(matches, key=lambda row: _float(row.get("Bottom stress (MPa)"), -math.inf))
            top_stress = _float(top_source.get("Top stress (MPa)"))
            bottom_stress = _float(bottom_source.get("Bottom stress (MPa)"))
            top_status = "PASS" if top_stress <= -joint_limit_mpa + 1.0e-12 else "FAIL"
            bottom_status = "PASS" if bottom_stress <= -joint_limit_mpa + 1.0e-12 else "FAIL"
            summaries.append(
                {
                    "Boundary ID": _text(boundary.get("Boundary ID")) or "Physical joint",
                    "Case / Combination": case_name,
                    "Station s (m)": station,
                    "Top stress (MPa)": top_stress,
                    "Top compression magnitude (MPa)": -top_stress,
                    "Top status": top_status,
                    "Bottom stress (MPa)": bottom_stress,
                    "Bottom compression magnitude (MPa)": -bottom_stress,
                    "Bottom status": bottom_status,
                    "Joint minimum signed stress (MPa)": -joint_limit_mpa,
                    "Joint minimum compression magnitude (MPa)": joint_limit_mpa,
                    "Joint status": "PASS" if top_status == "PASS" and bottom_status == "PASS" else "FAIL",
                    "Section IDs evaluated": " / ".join(
                        sorted({_text(row.get("Section ID")) for row in matches if _text(row.get("Section ID"))})
                    ),
                    "Internal section contexts": len(matches),
                    "Top source context": _text(top_source.get("Context ID")),
                    "Bottom source context": _text(bottom_source.get("Context ID")),
                }
            )
    return summaries


def _governing_demand(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        for fiber in ("Top", "Bottom"):
            candidates.append(
                {
                    "Fiber": fiber,
                    "Stress (MPa)": _float(row.get(f"{fiber} stress (MPa)")),
                    "Demand type": _text(row.get(f"{fiber} demand type")),
                    "Limit (MPa)": _float(row.get(f"{fiber} applicable limit (MPa)")),
                    "Utilization": _float(row.get(f"{fiber} utilization"), math.inf),
                    "Status": _text(row.get(f"{fiber} status")),
                    "Case / Combination": _text(row.get("Case / Combination")),
                    "Station s (m)": _float(row.get("Station s (m)")),
                    "Station face": _text(row.get("Station face")),
                    "Section ID": _text(row.get("Section ID")),
                    "Context ID": _text(row.get("Context ID")),
                }
            )
    if not candidates:
        return None
    return max(candidates, key=lambda item: (_float(item.get("Utilization"), -math.inf), abs(_float(item.get("Stress (MPa)")))))


def _governing_by_type(rows: Sequence[Mapping[str, Any]], demand_type: str) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        for fiber in ("Top", "Bottom"):
            if _text(row.get(f"{fiber} demand type")) != demand_type:
                continue
            candidates.append(
                {
                    "Fiber": fiber,
                    "Stress (MPa)": _float(row.get(f"{fiber} stress (MPa)")),
                    "Limit (MPa)": _float(row.get(f"{fiber} applicable limit (MPa)")),
                    "Utilization": _float(row.get(f"{fiber} utilization"), 0.0),
                    "Status": _text(row.get(f"{fiber} status")),
                    "Case / Combination": _text(row.get("Case / Combination")),
                    "Station s (m)": _float(row.get("Station s (m)")),
                    "Station face": _text(row.get("Station face")),
                    "Section ID": _text(row.get("Section ID")),
                    "Context ID": _text(row.get("Context ID")),
                }
            )
    if not candidates:
        return None
    return max(candidates, key=lambda item: (_float(item.get("Utilization"), -math.inf), abs(_float(item.get("Stress (MPa)")))))


def _governing_joint(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Return the joint/fiber closest to tension from collapsed joint rows."""

    candidates: list[dict[str, Any]] = []
    for row in rows:
        for fiber in ("Top", "Bottom"):
            stress = _float(row.get(f"{fiber} stress (MPa)"))
            candidates.append(
                {
                    "Boundary ID": _text(row.get("Boundary ID")),
                    "Fiber": fiber,
                    "Stress (MPa)": stress,
                    "Compression (MPa)": -stress,
                    "Limit (MPa)": _float(row.get("Joint minimum signed stress (MPa)")),
                    "Status": _text(row.get(f"{fiber} status")),
                    "Case / Combination": _text(row.get("Case / Combination")),
                    "Station s (m)": _float(row.get("Station s (m)")),
                }
            )
    if not candidates:
        return None
    return max(candidates, key=lambda item: (_float(item.get("Stress (MPa)"), -math.inf), -_float(item.get("Station s (m)"))))


def calculate_crossbeam_transfer_stress(
    *,
    foundation: Mapping[str, Any],
    section_definitions: Any,
    concrete_material: Any = None,
    concrete_materials: Any = None,
    active_concrete_material_name: str | None = None,
    deck_topping_material_name: str | None = None,
    tendon_system_rows: Any = None,
    stressing_strength_ratio: Any = DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO,
    joint_min_compression_mpa: float = DEFAULT_JOINT_MIN_COMPRESSION_MPA,
) -> dict[str, Any]:
    """Calculate top/bottom transfer stresses for every mapped transfer context."""

    ratio = _float(stressing_strength_ratio, DEFAULT_CROSSBEAM_STRESSING_STRENGTH_RATIO)
    joint_limit = _float(joint_min_compression_mpa, DEFAULT_JOINT_MIN_COMPRESSION_MPA)
    input_fingerprint = transfer_stress_input_fingerprint(
        foundation=foundation,
        section_definitions=section_definitions,
        concrete_material=concrete_material,
        concrete_materials=concrete_materials,
        active_concrete_material_name=active_concrete_material_name,
        deck_topping_material_name=deck_topping_material_name,
        tendon_system_rows=tendon_system_rows,
        stressing_strength_ratio=ratio,
        joint_min_compression_mpa=joint_limit,
    )
    errors: list[str] = []
    warnings: list[str] = []

    canonical_tendons = canonical_tendon_system_rows(tendon_system_rows)
    active_internal_tendon_ids = [
        _text(row.get("Tendon ID")) or "Unnamed tendon"
        for row in canonical_tendons
        if _bool(row.get("Active"), True)
        and _text(row.get("Type")).casefold() == "internal"
    ]
    gross_section_review = bool(active_internal_tendon_ids)
    if gross_section_review:
        warnings.append(
            "Active Internal Tendons are present, but SLS1A has no adopted duct-void geometry. "
            "ACI 318R-19 R24.5.2.1 indicates that section properties should account for voids "
            "created by sheathing or ducts for unbonded prestressing; therefore a gross-section "
            "non-failing result is REVIEW, not PASS."
        )

    if ratio < MIN_CROSSBEAM_STRESSING_STRENGTH_RATIO or ratio > 1.0:
        errors.append(
            "Crossbeam stressing-strength ratio f'ci/f'c must be between "
            f"{MIN_CROSSBEAM_STRESSING_STRENGTH_RATIO:.2f} and 1.00."
        )
    if joint_limit <= 0.0:
        errors.append("Physical segment-joint minimum compression must be greater than 0 MPa.")

    try:
        library = ensure_concrete_material_library(
            concrete_material=concrete_material,
            concrete_materials=concrete_materials,
            active_concrete_material_name=active_concrete_material_name,
            deck_topping_material_name=deck_topping_material_name,
        )
        material_by_name = concrete_materials_by_name(library.materials)
    except Exception as exc:
        material_by_name = {}
        errors.append(f"Concrete material library could not be resolved: {exc}")

    definitions = canonical_section_definitions(section_definitions)
    definition_by_id = {row["Section ID"]: row for row in definitions}
    transfer_contexts = [
        dict(row)
        for row in _records(foundation.get("mapped_rows"))
        if _text(row.get("Dataset")) == DATASET_SLS_TRANSFER
    ]
    if not transfer_contexts:
        errors.append("No mapped SLS At Transfer station-force contexts are available.")
    blocked_contexts = [row for row in transfer_contexts if _text(row.get("Context status")) != "READY"]
    if blocked_contexts:
        errors.append(f"{len(blocked_contexts)} SLS At Transfer context(s) are blocked by Section/Rebar source mapping.")
    joint_coverage_issues = _joint_case_coverage_errors(
        foundation=foundation, transfer_rows=transfer_contexts
    )

    result_rows: list[dict[str, Any]] = []
    for context in transfer_contexts:
        context_id = _text(context.get("Context ID"))
        section_id = _text(context.get("Section ID"))
        definition = definition_by_id.get(section_id)
        if definition is None:
            errors.append(f"{context_id}: Section ID {section_id or '(blank)'} is not defined.")
            continue
        material_name = _text(definition.get("Material"))
        material = material_by_name.get(material_name)
        if material is None:
            errors.append(f"{context_id}: concrete material '{material_name or '(blank)'}' is not available.")
            continue
        fc_mpa = _float(getattr(material, "fc_MPa", 0.0))
        fci_mpa = ratio * fc_mpa
        area_mm2 = _float(context.get("Area mm2"))
        z_top_mm3 = _float(context.get("Z top mm3"))
        z_bottom_mm3 = _float(context.get("Z bottom mm3"))
        if min(fc_mpa, fci_mpa, area_mm2, z_top_mm3, z_bottom_mm3) <= 0.0:
            errors.append(f"{context_id}: positive f'c, f'ci, area, Ztop, and Zbottom are required.")
            continue

        p_kn = _float(context.get("P (kN; compression +)"))
        m3_knm = _float(context.get("M3 (kN-m; sagging +)"))
        axial_mpa = -(p_kn * 1.0e3) / area_mm2
        top_bending_mpa = -(m3_knm * 1.0e6) / z_top_mm3
        bottom_bending_mpa = +(m3_knm * 1.0e6) / z_bottom_mm3
        top_stress_mpa = axial_mpa + top_bending_mpa
        bottom_stress_mpa = axial_mpa + bottom_bending_mpa

        compression_limit_mpa = 0.60 * fci_mpa
        tension_limit_mpa = 0.25 * math.sqrt(fci_mpa)
        top_check = _fiber_check(
            top_stress_mpa,
            compression_limit_mpa=compression_limit_mpa,
            tension_limit_mpa=tension_limit_mpa,
        )
        bottom_check = _fiber_check(
            bottom_stress_mpa,
            compression_limit_mpa=compression_limit_mpa,
            tension_limit_mpa=tension_limit_mpa,
        )

        physical_joint = bool(context.get("Physical segment joint"))
        joint_top_status = "PASS" if not physical_joint or top_stress_mpa <= -joint_limit + 1.0e-12 else "FAIL"
        joint_bottom_status = "PASS" if not physical_joint or bottom_stress_mpa <= -joint_limit + 1.0e-12 else "FAIL"
        row = {
            **context,
            "Material": material_name,
            "f'c (MPa)": fc_mpa,
            "f'ci/f'c": ratio,
            "f'ci (MPa)": fci_mpa,
            "Axial stress (MPa)": axial_mpa,
            "Top bending stress (MPa)": top_bending_mpa,
            "Bottom bending stress (MPa)": bottom_bending_mpa,
            "Top stress (MPa)": top_stress_mpa,
            "Bottom stress (MPa)": bottom_stress_mpa,
            "Compression limit magnitude (MPa)": compression_limit_mpa,
            "Compression limit (MPa)": -compression_limit_mpa,
            "Tension limit (MPa)": tension_limit_mpa,
            "Top demand type": top_check["Demand type"],
            "Top applicable limit (MPa)": top_check["Applicable limit (MPa)"],
            "Top utilization": top_check["Utilization"],
            "Top status": top_check["Status"],
            "Bottom demand type": bottom_check["Demand type"],
            "Bottom applicable limit (MPa)": bottom_check["Applicable limit (MPa)"],
            "Bottom utilization": bottom_check["Utilization"],
            "Bottom status": bottom_check["Status"],
            "Joint minimum compression required (MPa)": joint_limit if physical_joint else None,
            "Joint top compression (MPa)": -top_stress_mpa if physical_joint else None,
            "Joint bottom compression (MPa)": -bottom_stress_mpa if physical_joint else None,
            "Joint top status": joint_top_status if physical_joint else "N/A",
            "Joint bottom status": joint_bottom_status if physical_joint else "N/A",
            "Joint status": (
                "PASS"
                if physical_joint and joint_top_status == "PASS" and joint_bottom_status == "PASS"
                else "FAIL"
                if physical_joint
                else "N/A"
            ),
        }
        result_rows.append(row)

    errors = list(dict.fromkeys(errors))
    warnings = list(dict.fromkeys(warnings))
    if errors:
        return {
            "schema": CROSSBEAM_SLS_TRANSFER_SCHEMA,
            "status": "SOURCE BLOCKED",
            "stress_status": "SOURCE BLOCKED",
            "joint_status": "SOURCE BLOCKED",
            "input_fingerprint": input_fingerprint,
            "foundation_fingerprint": _text(foundation.get("fingerprint")),
            "rows": result_rows,
            "joint_rows": [],
            "cases": sorted({_text(row.get("Case / Combination")) for row in result_rows if _text(row.get("Case / Combination"))}),
            "errors": errors,
            "warnings": warnings,
            "joint_coverage_issues": joint_coverage_issues,
            "solver_run": False,
            "code_basis": "ACI 318-19 §24.5.3",
        }

    stress_fail = any(
        _text(row.get("Top status")) == "FAIL" or _text(row.get("Bottom status")) == "FAIL"
        for row in result_rows
    )
    joint_rows = _joint_summary_rows(
        foundation=foundation,
        result_rows=result_rows,
        joint_limit_mpa=joint_limit,
    )
    joint_fail = any(_text(row.get("Joint status")) == "FAIL" for row in joint_rows)
    physical_boundaries_exist = _joint_gate_required(foundation) and any(
        _text(row.get("Boundary type")) == "Physical segment joint"
        for row in _records(foundation.get("internal_boundaries"))
    )
    stress_status = "FAIL" if stress_fail else "REVIEW" if gross_section_review else "PASS"
    joint_status = (
        "FAIL"
        if joint_fail
        else "INCOMPLETE"
        if joint_coverage_issues
        else "PASS"
        if physical_boundaries_exist
        else "NOT REQUIRED"
    )
    overall_status = (
        "FAIL"
        if stress_fail or joint_fail
        else "INCOMPLETE"
        if joint_coverage_issues
        else "REVIEW"
        if gross_section_review
        else "PASS"
    )
    governing = _governing_demand(result_rows)
    governing_compression = _governing_by_type(result_rows, "Compression")
    governing_tension = _governing_by_type(result_rows, "Tension")
    governing_joint = _governing_joint(joint_rows)

    return {
        "schema": CROSSBEAM_SLS_TRANSFER_SCHEMA,
        "status": overall_status,
        "stress_status": stress_status,
        "joint_status": joint_status,
        "input_fingerprint": input_fingerprint,
        "foundation_fingerprint": _text(foundation.get("fingerprint")),
        "rows": result_rows,
        "joint_rows": joint_rows,
        "cases": sorted({_text(row.get("Case / Combination")) for row in result_rows if _text(row.get("Case / Combination"))}),
        "governing": governing,
        "governing_compression": governing_compression,
        "governing_tension": governing_tension,
        "governing_joint": governing_joint,
        "joint_min_compression_mpa": joint_limit,
        "section_basis_status": "REVIEW" if gross_section_review else "PASS",
        "active_internal_tendon_ids": active_internal_tendon_ids,
        "errors": [],
        "warnings": warnings,
        "joint_coverage_issues": joint_coverage_issues,
        "solver_run": True,
        "code_basis": "ACI 318-19 §24.5.3",
        "limit_basis": {
            "compression": "0.60 f'ci — all other locations; Portal Frame Crossbeam is not a simply supported member",
            "tension": "0.25 sqrt(f'ci) — no additional bonded reinforcement credit",
            "joint": (
                "Project criterion for Precast Segmental only: one governing Top stress and one governing Bottom stress "
                "are reported per physical joint; both must satisfy fjoint <= -0.70 MPa "
                "(compression magnitude >= 0.70 MPa)."
            ),
        },
        "sign_convention": "Compression negative / tension positive; source P compression positive; source M3 sagging positive",
        "limitations": [
            "External FEA P and M3 are used exactly as imported from the same output row; prestress is not added again.",
            "The ACI 318-19 simply-supported end exceptions are not used for this Portal Frame Crossbeam.",
            "Gross Section ID properties are used. If active Internal Tendons are present, the result remains REVIEW until adopted duct-void geometry is included in the transfer-section properties.",
            "Additional bonded reinforcement under 24.5.3.2.1 is not credited in SLS1A.",
            "Anchorage zones, beam-column joints, D-regions, shear, torsion, and seismic detailing remain separate checks.",
            "Physical-joint results collapse adjacent Section-ID calculations to one governing Top value and one governing Bottom value; values are not averaged.",
            "Cast-in-Place Section/Zone boundaries are monolithic and do not require the physical segment-joint compression gate.",
            "Lines on the result chart connect imported stations for visualization only; no compliance is inferred between unverified stations.",
        ],
    }


__all__ = [
    "CB_ANALYSIS_SLS_TRANSFER_RESULT_KEY",
    "CROSSBEAM_SLS_TRANSFER_SCHEMA",
    "DEFAULT_JOINT_MIN_COMPRESSION_MPA",
    "calculate_crossbeam_transfer_stress",
    "transfer_stress_input_fingerprint",
]
