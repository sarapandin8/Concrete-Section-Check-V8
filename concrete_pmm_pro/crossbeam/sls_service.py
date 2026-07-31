"""ACI 318-19 final-service concrete stress checks for Portal Frame Crossbeam.

CROSSBEAM.SLS1B consumes validated ``SLS At Service`` station contexts.  The
external FEA row is the sole source of row-coupled ``P`` and ``M3`` demand;
prestress and secondary prestress are not added again in this module.

The adopted first production route is deliberately conservative and explicit:

* service tensile behavior is checked on a Class U (uncracked) basis using
  ``ft <= 0.62 sqrt(f'c)`` from ACI 318-19 Table 24.5.2.1;
* cases identified by the engineer as prestress-plus-sustained use the
  compression limit ``0.45 f'c``;
* all other imported service cases use the total-load compression limit
  ``0.60 f'c`` from ACI 318-19 Table 24.5.4.1; and
* every physical precast segment joint must retain at least 0.70 MPa
  compression at both top and bottom fibers.  Adjacent Segment section
  properties are evaluated internally, but one governing value per fiber is
  reported for each joint.

Stress convention follows the accepted app charts: compression negative and
tension positive.  Source ``P`` is compression-positive and source ``M3`` is
sagging-positive.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

from concrete_pmm_pro.core.concrete_materials import (
    concrete_materials_by_name,
    ensure_concrete_material_library,
)
from concrete_pmm_pro.crossbeam.analysis_foundation import DATASET_SLS_SERVICE
from concrete_pmm_pro.crossbeam.section_library import canonical_section_definitions
from concrete_pmm_pro.crossbeam.sls_transfer import (
    DEFAULT_JOINT_MIN_COMPRESSION_MPA,
    _bool,
    _fiber_check,
    _fingerprint,
    _float,
    _governing_by_type,
    _governing_demand,
    _governing_joint,
    _joint_gate_required,
    _joint_summary_rows,
    _joint_case_coverage_errors,
    _jsonable_material,
    _records,
    _text,
)
from concrete_pmm_pro.crossbeam.tendon import canonical_tendon_system_rows


CROSSBEAM_SLS_SERVICE_SCHEMA = "crossbeam-sls-service-stress-v2"
CB_ANALYSIS_SLS_SERVICE_RESULT_KEY = "crossbeam_analysis_sls1b_service_result"
CB_ANALYSIS_SLS_SERVICE_SUSTAINED_CASES_KEY = "crossbeam_analysis_sls1b_sustained_cases"
CLASS_U_TENSION_COEFFICIENT = 0.62
SUSTAINED_COMPRESSION_COEFFICIENT = 0.45
TOTAL_COMPRESSION_COEFFICIENT = 0.60


def canonical_sustained_case_names(value: Any) -> list[str]:
    """Return stable unique service case names selected as sustained load."""

    if isinstance(value, str):
        source = [value]
    elif isinstance(value, Sequence):
        source = list(value)
    else:
        source = []
    names: list[str] = []
    for item in source:
        name = _text(item)
        if name and name not in names:
            names.append(name)
    return sorted(names)


def service_stress_input_fingerprint(
    *,
    foundation: Mapping[str, Any],
    section_definitions: Any,
    concrete_material: Any = None,
    concrete_materials: Any = None,
    active_concrete_material_name: str | None = None,
    deck_topping_material_name: str | None = None,
    tendon_system_rows: Any = None,
    sustained_case_names: Any = None,
    joint_min_compression_mpa: float = DEFAULT_JOINT_MIN_COMPRESSION_MPA,
) -> str:
    """Return the current final-service input hash without running the check."""

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
            "schema": CROSSBEAM_SLS_SERVICE_SCHEMA,
            "foundation": _text(foundation.get("fingerprint")),
            "definitions": canonical_section_definitions(section_definitions),
            "materials": materials,
            "tendon_system": canonical_tendon_system_rows(tendon_system_rows),
            "sustained_case_names": canonical_sustained_case_names(sustained_case_names),
            "joint_min_compression_mpa": _float(joint_min_compression_mpa),
            "service_tension_class": "Class U",
        }
    )


def calculate_crossbeam_service_stress(
    *,
    foundation: Mapping[str, Any],
    section_definitions: Any,
    concrete_material: Any = None,
    concrete_materials: Any = None,
    active_concrete_material_name: str | None = None,
    deck_topping_material_name: str | None = None,
    tendon_system_rows: Any = None,
    sustained_case_names: Any = None,
    joint_min_compression_mpa: float = DEFAULT_JOINT_MIN_COMPRESSION_MPA,
) -> dict[str, Any]:
    """Calculate final-service top/bottom stresses for every mapped context."""

    joint_limit = _float(joint_min_compression_mpa, DEFAULT_JOINT_MIN_COMPRESSION_MPA)
    selected_sustained = canonical_sustained_case_names(sustained_case_names)
    input_fingerprint = service_stress_input_fingerprint(
        foundation=foundation,
        section_definitions=section_definitions,
        concrete_material=concrete_material,
        concrete_materials=concrete_materials,
        active_concrete_material_name=active_concrete_material_name,
        deck_topping_material_name=deck_topping_material_name,
        tendon_system_rows=tendon_system_rows,
        sustained_case_names=selected_sustained,
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
            "Active Internal Tendons are present, but SLS1B has no adopted duct-void geometry. "
            "ACI 318R-19 R24.5.2.1 indicates that section properties should account for voids "
            "created by sheathing or ducts for unbonded prestressing; therefore a gross-section "
            "non-failing result is REVIEW, not PASS."
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
    service_contexts = [
        dict(row)
        for row in _records(foundation.get("mapped_rows"))
        if _text(row.get("Dataset")) == DATASET_SLS_SERVICE
    ]
    if not service_contexts:
        errors.append("No mapped SLS At Service station-force contexts are available.")
    blocked_contexts = [
        row for row in service_contexts if _text(row.get("Context status")) != "READY"
    ]
    if blocked_contexts:
        errors.append(
            f"{len(blocked_contexts)} SLS At Service context(s) are blocked by Section/Rebar source mapping."
        )

    available_cases = sorted(
        {
            _text(row.get("Case / Combination"))
            for row in service_contexts
            if _text(row.get("Case / Combination"))
        }
    )
    unknown_sustained = [name for name in selected_sustained if name not in available_cases]
    if unknown_sustained:
        warnings.append(
            "Saved sustained service case selection is not present in the current dataset: "
            + ", ".join(unknown_sustained)
            + "."
        )
    sustained_cases = [name for name in selected_sustained if name in available_cases]
    total_cases = [name for name in available_cases if name not in sustained_cases]
    basis_coverage_issues: list[str] = []
    if available_cases and not sustained_cases:
        basis_coverage_issues.append(
            "No prestress-plus-sustained service case is identified; the ACI 318-19 0.45f'c compression condition is not verified."
        )
    if available_cases and not total_cases:
        basis_coverage_issues.append(
            "No prestress-plus-total service case remains; the ACI 318-19 0.60f'c compression condition is not verified."
        )

    joint_coverage_issues = _joint_case_coverage_errors(
        foundation=foundation,
        transfer_rows=service_contexts,
    )

    result_rows: list[dict[str, Any]] = []
    for context in service_contexts:
        context_id = _text(context.get("Context ID"))
        section_id = _text(context.get("Section ID"))
        definition = definition_by_id.get(section_id)
        if definition is None:
            errors.append(f"{context_id}: Section ID {section_id or '(blank)'} is not defined.")
            continue
        material_name = _text(definition.get("Material"))
        material = material_by_name.get(material_name)
        if material is None:
            errors.append(
                f"{context_id}: concrete material '{material_name or '(blank)'}' is not available."
            )
            continue
        fc_mpa = _float(getattr(material, "fc_MPa", 0.0))
        area_mm2 = _float(context.get("Area mm2"))
        z_top_mm3 = _float(context.get("Z top mm3"))
        z_bottom_mm3 = _float(context.get("Z bottom mm3"))
        if min(fc_mpa, area_mm2, z_top_mm3, z_bottom_mm3) <= 0.0:
            errors.append(
                f"{context_id}: positive f'c, area, Ztop, and Zbottom are required."
            )
            continue

        case_name = _text(context.get("Case / Combination"))
        is_sustained = case_name in sustained_cases
        compression_coefficient = (
            SUSTAINED_COMPRESSION_COEFFICIENT
            if is_sustained
            else TOTAL_COMPRESSION_COEFFICIENT
        )
        load_condition = (
            "Prestress + sustained load" if is_sustained else "Prestress + total load"
        )

        p_kn = _float(context.get("P (kN; compression +)"))
        m3_knm = _float(context.get("M3 (kN-m; sagging +)"))
        axial_mpa = -(p_kn * 1.0e3) / area_mm2
        top_bending_mpa = -(m3_knm * 1.0e6) / z_top_mm3
        bottom_bending_mpa = +(m3_knm * 1.0e6) / z_bottom_mm3
        top_stress_mpa = axial_mpa + top_bending_mpa
        bottom_stress_mpa = axial_mpa + bottom_bending_mpa

        compression_limit_mpa = compression_coefficient * fc_mpa
        tension_limit_mpa = CLASS_U_TENSION_COEFFICIENT * math.sqrt(fc_mpa)
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
        joint_top_status = (
            "PASS"
            if not physical_joint or top_stress_mpa <= -joint_limit + 1.0e-12
            else "FAIL"
        )
        joint_bottom_status = (
            "PASS"
            if not physical_joint or bottom_stress_mpa <= -joint_limit + 1.0e-12
            else "FAIL"
        )
        result_rows.append(
            {
                **context,
                "Material": material_name,
                "f'c (MPa)": fc_mpa,
                "Service load condition": load_condition,
                "Compression coefficient": compression_coefficient,
                "Service tensile class": "Class U",
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
                "Joint minimum compression required (MPa)": (
                    joint_limit if physical_joint else None
                ),
                "Joint top compression (MPa)": -top_stress_mpa if physical_joint else None,
                "Joint bottom compression (MPa)": (
                    -bottom_stress_mpa if physical_joint else None
                ),
                "Joint top status": joint_top_status if physical_joint else "N/A",
                "Joint bottom status": joint_bottom_status if physical_joint else "N/A",
                "Joint status": (
                    "PASS"
                    if physical_joint
                    and joint_top_status == "PASS"
                    and joint_bottom_status == "PASS"
                    else "FAIL"
                    if physical_joint
                    else "N/A"
                ),
            }
        )

    errors = list(dict.fromkeys(errors))
    warnings = list(dict.fromkeys(warnings))
    if errors:
        return {
            "schema": CROSSBEAM_SLS_SERVICE_SCHEMA,
            "status": "SOURCE BLOCKED",
            "stress_status": "SOURCE BLOCKED",
            "joint_status": "SOURCE BLOCKED",
            "input_fingerprint": input_fingerprint,
            "foundation_fingerprint": _text(foundation.get("fingerprint")),
            "rows": result_rows,
            "joint_rows": [],
            "cases": sorted(
                {
                    _text(row.get("Case / Combination"))
                    for row in result_rows
                    if _text(row.get("Case / Combination"))
                }
            ),
            "errors": errors,
            "warnings": warnings,
            "joint_coverage_issues": joint_coverage_issues,
            "basis_coverage_issues": basis_coverage_issues,
            "solver_run": False,
            "code_basis": "ACI 318-19 §§24.5.2 and 24.5.4",
        }

    stress_fail = any(
        _text(row.get("Top status")) == "FAIL"
        or _text(row.get("Bottom status")) == "FAIL"
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
    basis_incomplete = bool(basis_coverage_issues)
    stress_status = (
        "FAIL"
        if stress_fail
        else "REVIEW"
        if gross_section_review or basis_incomplete
        else "PASS"
    )
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
        if gross_section_review or basis_incomplete
        else "PASS"
    )

    return {
        "schema": CROSSBEAM_SLS_SERVICE_SCHEMA,
        "status": overall_status,
        "stress_status": stress_status,
        "joint_status": joint_status,
        "input_fingerprint": input_fingerprint,
        "foundation_fingerprint": _text(foundation.get("fingerprint")),
        "rows": result_rows,
        "joint_rows": joint_rows,
        "cases": sorted(
            {
                _text(row.get("Case / Combination"))
                for row in result_rows
                if _text(row.get("Case / Combination"))
            }
        ),
        "governing": _governing_demand(result_rows),
        "governing_compression": _governing_by_type(result_rows, "Compression"),
        "governing_tension": _governing_by_type(result_rows, "Tension"),
        "governing_joint": _governing_joint(joint_rows),
        "joint_min_compression_mpa": joint_limit,
        "section_basis_status": "REVIEW" if gross_section_review else "PASS",
        "service_basis_status": "REVIEW" if basis_incomplete else "PASS",
        "active_internal_tendon_ids": active_internal_tendon_ids,
        "sustained_case_names": sustained_cases,
        "total_case_names": total_cases,
        "unknown_sustained_case_names": unknown_sustained,
        "errors": [],
        "warnings": warnings,
        "joint_coverage_issues": joint_coverage_issues,
        "basis_coverage_issues": basis_coverage_issues,
        "solver_run": True,
        "code_basis": "ACI 318-19 §§24.5.2 and 24.5.4",
        "limit_basis": {
            "compression_sustained": "0.45 f'c — prestress plus sustained load",
            "compression_total": "0.60 f'c — prestress plus total load",
            "tension": "Class U: 0.62 sqrt(f'c) — uncracked service behavior",
            "joint": (
                "Project criterion for Precast Segmental only: one governing Top stress and one governing Bottom stress "
                "are reported per physical joint; both must satisfy fjoint <= -0.70 MPa "
                "(compression magnitude >= 0.70 MPa)."
            ),
        },
        "sign_convention": (
            "Compression negative / tension positive; source P compression positive; "
            "source M3 sagging positive"
        ),
        "limitations": [
            "External FEA P and M3 are used exactly as imported from the same output row; prestress is not added again.",
            "Class U tension screening is applied conservatively to any extreme fiber in tension; precompressed-tension-zone decomposition is not available from the compact station-force contract.",
            "Class T/C cracked-section, crack-control, and deflection checks are outside SLS1B.",
            "Gross Section ID properties are used. Active Internal Tendon duct voids require adopted net-section properties before final PASS.",
            "Anchorage zones, beam-column joints, D-regions, shear, torsion, and seismic detailing remain separate checks.",
            "Physical-joint results collapse adjacent Section-ID calculations to one governing Top value and one governing Bottom value; values are not averaged.",
            "Cast-in-Place Section/Zone boundaries are monolithic and do not require the physical segment-joint compression gate.",
            "Lines on the result chart connect imported stations for visualization only; no compliance is inferred between unverified stations.",
        ],
    }


__all__ = [
    "CB_ANALYSIS_SLS_SERVICE_RESULT_KEY",
    "CB_ANALYSIS_SLS_SERVICE_SUSTAINED_CASES_KEY",
    "CLASS_U_TENSION_COEFFICIENT",
    "CROSSBEAM_SLS_SERVICE_SCHEMA",
    "SUSTAINED_COMPRESSION_COEFFICIENT",
    "TOTAL_COMPRESSION_COEFFICIENT",
    "calculate_crossbeam_service_stress",
    "canonical_sustained_case_names",
    "service_stress_input_fingerprint",
]
