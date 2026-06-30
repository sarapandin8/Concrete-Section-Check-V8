"""Report table registry for future export."""

from __future__ import annotations

from typing import Any

import pandas as pd

from concrete_pmm_pro.reporting.limitations import collect_limitations_for_report, engineering_limitations_to_dataframe
from concrete_pmm_pro.reporting.readiness import check_report_readiness, report_readiness_to_dataframe
from concrete_pmm_pro.reporting.report_models import ReportTableInfo
from concrete_pmm_pro.reporting.terminology import terminology_to_dataframe
from concrete_pmm_pro.reporting.traceability import build_result_traceability_snapshot, result_traceability_snapshot_to_dataframe
from concrete_pmm_pro.reporting.units import unit_conventions_to_dataframe
from concrete_pmm_pro.reporting.railway_u_girder_report import build_railway_u_girder_sls_report_package
from concrete_pmm_pro.reporting.generic_precast_lifting_report import build_generic_precast_lifting_report_package
from concrete_pmm_pro.reporting.railway_u_girder_release import build_railway_u_girder_release_package
from concrete_pmm_pro.reporting.railway_u_girder_final import build_railway_u_girder_final_design_check_package
from concrete_pmm_pro.reporting.column_pier_vt_report import build_column_pier_vt_report_package
from concrete_pmm_pro.analysis.railway_u_girder_uls import build_railway_u_girder_uls_framework_package
from concrete_pmm_pro.verification.column_pier_vt_benchmarks import benchmark_cases
from concrete_pmm_pro.verification.pmm_published_benchmark_inventory import (
    summarize_pmm_published_benchmark_inventory,
)


def _get(mapping: Any, key: str, default: Any = None) -> Any:
    if mapping is None:
        return default
    if hasattr(mapping, "get"):
        try:
            return mapping.get(key, default)
        except (AttributeError, TypeError, ValueError):
            return default
    return getattr(mapping, key, default)


def _has_any(session_state: Any, keys: list[str]) -> bool:
    return any(_get(session_state, key) is not None for key in keys)


def _row_count(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        return len(value)
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    for attr in ("results", "checks", "points", "stress_results"):
        values = getattr(value, attr, None)
        if values is not None:
            try:
                return len(values)
            except TypeError:
                return None
    return None


def collect_available_report_tables(session_state: Any) -> list[ReportTableInfo]:
    """Collect table availability from existing state without recalculation."""

    snapshot = build_result_traceability_snapshot(session_state)
    readiness = check_report_readiness(snapshot)
    limitations = collect_limitations_for_report(session_state, include_all=True)
    pmm_benchmark_inventory = summarize_pmm_published_benchmark_inventory()
    railway_report = build_railway_u_girder_sls_report_package(session_state)
    generic_lifting_report = build_generic_precast_lifting_report_package(session_state)
    railway_uls_report = build_railway_u_girder_uls_framework_package(session_state)
    railway_release = build_railway_u_girder_release_package(session_state)
    railway_final = build_railway_u_girder_final_design_check_package(session_state)
    column_pier_vt_report = build_column_pier_vt_report_package(session_state)

    standard_tables = [
        ReportTableInfo(
            "result_traceability_snapshot",
            "Result Traceability Snapshot",
            True,
            "build_result_traceability_snapshot",
            "Project, workflow, ULS, SLS, cracking, verification, warning, and limitation summary.",
            row_count=len(result_traceability_snapshot_to_dataframe(snapshot)),
        ),
        ReportTableInfo(
            "report_readiness",
            "Report Readiness",
            True,
            "check_report_readiness",
            "Pre-report readiness status and missing/optional items.",
            row_count=len(report_readiness_to_dataframe(readiness)),
        ),
        ReportTableInfo(
            "engineering_warnings",
            "Engineering Warnings",
            True,
            "collect_engineering_warnings",
            "Consolidated engineering warnings.",
            row_count=len(snapshot.warnings),
        ),
        ReportTableInfo(
            "engineering_limitations",
            "Engineering Limitations",
            True,
            "collect_limitations_for_report",
            "Engineering limitations and prototype/future-work disclosures.",
            row_count=len(engineering_limitations_to_dataframe(limitations)),
        ),
        ReportTableInfo(
            "unit_conventions",
            "Unit Conventions",
            True,
            "get_unit_conventions",
            "Internal, display, and future report units.",
            row_count=len(unit_conventions_to_dataframe()),
        ),
        ReportTableInfo(
            "terminology",
            "Standard Terminology",
            True,
            "get_standard_terminology",
            "Engineering term glossary for report consistency.",
            row_count=len(terminology_to_dataframe()),
        ),
        ReportTableInfo(
            "pmm_published_benchmark_inventory",
            "PMM Published Benchmark Inventory",
            True,
            "verification.pmm_published_benchmark_inventory",
            "Readiness inventory separating internal PMM evidence from published/reference benchmark gaps for prestressed and custom shapes.",
            row_count=len(pmm_benchmark_inventory.items),
            warning="Published/reference prestressed and custom-shape PMM examples are still required before final certification wording.",
        ),
    ]

    pmm_value = _get(session_state, "rc_pmm_result")
    if pmm_value is None:
        pmm_value = _get(session_state, "pmm_result")
    dc_value = _get(session_state, "rc_demand_capacity_result")
    if dc_value is None:
        dc_value = _get(session_state, "demand_capacity_summary")
    serviceability = _get(session_state, "serviceability_summary")
    crack = _get(session_state, "crack_classification_summary")
    custom_points = _get(session_state, "custom_stress_check_points")
    column_pier_vt_qa_available = snapshot.member_type == "column_pier_pmm"

    standard_tables.extend(
        [
            ReportTableInfo("pmm_summary", "PMM Summary", pmm_value is not None, "rc_pmm_result", "ULS PMM result summary.", row_count=_row_count(getattr(pmm_value, "points", None))),
            ReportTableInfo("uls_demand_capacity_result", "ULS Demand / Capacity Result", dc_value is not None, "rc_demand_capacity_result", "ULS demand/capacity prototype results.", row_count=_row_count(dc_value)),
            ReportTableInfo("pmm_slice", "PMM Slice", pmm_value is not None, "rc_pmm_result", "Selected PMM slice data when generated.", row_count=None),
            ReportTableInfo("pmm_slice_envelope", "PMM Slice Envelope", pmm_value is not None, "rc_pmm_result", "Selected PMM envelope data when generated.", row_count=None),
            ReportTableInfo("pmm_verification", "PMM Verification", _get(session_state, "pmm_verification_summary") is not None, "pmm_verification_summary", "PMM benchmark checks.", row_count=_row_count(_get(session_state, "pmm_verification_summary"))),
            ReportTableInfo("hand_check_results", "Independent Hand Checks", _get(session_state, "pmm_hand_check_summary") is not None, "pmm_hand_check_summary", "Independent PMM hand-check results.", row_count=_row_count(_get(session_state, "pmm_hand_check_summary"))),
            ReportTableInfo("sls_stress_results", "SLS Stress Results", serviceability is not None, "serviceability_summary", "Gross/transformed elastic SLS stress results.", row_count=_row_count(getattr(serviceability, "stress_results", None))),
            ReportTableInfo("sls_prestress_contribution", "SLS Prestress Contribution", bool(getattr(serviceability, "prestress_contribution", None)), "serviceability_summary", "Effective bonded prestress contribution to SLS stress.", row_count=1 if getattr(serviceability, "prestress_contribution", None) else None),
            ReportTableInfo("transformed_section_properties", "Transformed Section Properties", bool(getattr(serviceability, "transformed_section_properties", None)), "serviceability_summary", "Uncracked transformed section properties.", row_count=1 if getattr(serviceability, "transformed_section_properties", None) else None),
            ReportTableInfo("cracking_classification", "Cracking Classification", crack is not None, "crack_classification_summary", "Tension/cracking classification from SLS stress results.", row_count=_row_count(getattr(crack, "points", None))),
            ReportTableInfo("custom_stress_check_points", "Custom Stress Check Points", bool(custom_points), "custom_stress_check_points", "User-defined SLS stress check points.", row_count=_row_count(custom_points)),
            ReportTableInfo("sls_verification_results", "SLS Verification Results", _get(session_state, "sls_verification_summary") is not None, "sls_verification_summary", "SLS stress sign benchmark checks.", row_count=_row_count(_get(session_state, "sls_verification_summary"))),
            ReportTableInfo(
                "column_pier_vt_qa1_benchmarks",
                "Column/Pier V+T QA1 Benchmarks",
                column_pier_vt_qa_available,
                "verification.column_pier_vt_benchmarks",
                "Independent hand-check reference cases for the scoped Column/Pier shear-torsion interaction gate.",
                row_count=len(benchmark_cases()) if column_pier_vt_qa_available else None,
                warning="Static validation evidence only; AASHTO LRFD prestressed/general-procedure V+T, seismic detailing, and anchorage remain excluded routes.",
            ),
            ReportTableInfo("sls_visualization_selected_combo", "Selected SLS Visualization Data", _has_any(session_state, ["sls_visualization_dataframe", "sls_stress_visualization_selected_combo"]), "sls_visualization_dataframe", "Selected-combo SLS stress visualization source data.", row_count=_row_count(_get(session_state, "sls_visualization_dataframe"))),
        ]
    )
    if column_pier_vt_report.available:
        column_pier_vt_titles = {
            "column_pier_vt_report_summary": "Column/Pier V+T Report Summary",
            "column_pier_vt_report_results": "Column/Pier V+T Compact Results",
            "column_pier_vt_report_audit": "Column/Pier V+T Audit Details",
            "column_pier_vt_report_scope_guard": "Column/Pier V+T Scope Guard",
        }
        for table_key, dataframe in column_pier_vt_report.tables().items():
            standard_tables.append(
                ReportTableInfo(
                    table_key,
                    column_pier_vt_titles.get(table_key, table_key.replace("_", " ").title()),
                    not dataframe.empty,
                    "reporting.column_pier_vt_report",
                    "Column/Pier Shear + Torsion report-preview table from stored Analysis results; no solver rerun in Report / QA.",
                    row_count=len(dataframe),
                    warning="Column/Pier V+T report preview is a guarded strength-gate summary; seismic/detailing and prestressed/general-procedure V+T remain outside scope.",
                )
            )

    if railway_report.available:
        railway_table_titles = {
            "railway_u_girder_closeout_status": "Railway U-Girder Closeout Status",
            "railway_u_girder_sls_scope": "Railway U-Girder SLS Report Scope",
            "railway_u_girder_geometry_summary": "Railway U-Girder Geometry Summary",
            "railway_u_girder_material_stage_settings": "Railway U-Girder Material and Stage Settings",
            "railway_u_girder_stage_quantities": "Railway U-Girder Stage Quantities",
            "railway_u_girder_prestress_debonding_summary": "Railway U-Girder Prestress / Debonding Summary",
            "railway_u_girder_sls_stage_governing": "Railway U-Girder SLS Stage Governing Rows",
            "railway_u_girder_sls_limit_governing": "Railway U-Girder SLS Limit Governing Rows",
            "railway_u_girder_sls_final_service_governing": "Railway U-Girder Final Service Governing Rows",
            "railway_u_girder_sls_decision_summary": "Railway U-Girder SLS Decision Summary",
            "railway_u_girder_service_multifiber_summary": "Railway U-Girder Service Multi-Fiber Summary",
        }
        for table_key, dataframe in railway_report.tables().items():
            standard_tables.append(
                ReportTableInfo(
                    table_key,
                    railway_table_titles.get(table_key, table_key.replace("_", " ").title()),
                    not dataframe.empty,
                    "reporting.railway_u_girder_report",
                    "Railway U-Girder staged SLS engineering-review report table. Guarded preview only; not final code-certified.",
                    row_count=len(dataframe),
                    warning="Railway U-Girder report is engineering-review preview, not final code-certified design.",
                )
            )


    if generic_lifting_report.available:
        generic_lifting_titles = {
            "generic_precast_lifting_scope": "Generic Precast Lifting Report Scope",
            "generic_precast_lifting_settings": "Generic Precast Lifting Settings",
            "generic_precast_lifting_load_basis": "Generic Precast Lifting Load Basis",
            "generic_precast_lifting_station_stress_rows": "Generic Precast Lifting Station Stress Rows",
            "generic_precast_lifting_governing_rows": "Generic Precast Lifting Governing Rows",
            "generic_precast_lifting_closeout_guard": "Generic Precast Lifting Closeout Guard",
        }
        for table_key, dataframe in generic_lifting_report.tables().items():
            standard_tables.append(
                ReportTableInfo(
                    table_key,
                    generic_lifting_titles.get(table_key, table_key.replace("_", " ").title()),
                    not dataframe.empty,
                    "reporting.generic_precast_lifting_report",
                    "Generic precast lifting-stage engineering-review report table. Individual precast unit only; not final code-certified.",
                    row_count=len(dataframe),
                    warning="Generic precast lifting report excludes lifting insert/local hardware, transfer/development certification, and final code-certified design approval.",
                )
            )

    if railway_uls_report.available:
        railway_uls_table_titles = {
            "railway_u_girder_uls_closeout_boundary": "Railway U-Girder ULS Closeout Boundary",
            "railway_u_girder_uls_code_basis": "Railway U-Girder ULS Code Basis",
            "railway_u_girder_uls_demand_summary": "Railway U-Girder ULS Demand Summary",
            "railway_u_girder_uls_flexure_evidence": "Railway U-Girder ULS Flexure Calculation Evidence",
            "railway_u_girder_uls_shear_evidence": "Railway U-Girder ULS PSC Shear Route Evidence",
            "railway_u_girder_uls_torsion_vt_guard": "Railway U-Girder ULS Torsion / V+T Guard Evidence",
            "railway_u_girder_prestress_development_evidence": "Railway U-Girder Prestress Transfer / Development Evidence",
            "railway_u_girder_anchorage_end_zone_evidence": "Railway U-Girder Anchorage / End-Zone Evidence",
            "railway_u_girder_uls_check_matrix": "Railway U-Girder ULS Check Matrix",
            "railway_u_girder_uls_future_checks": "Railway U-Girder ULS Future Checks",
        }
        for table_key, dataframe in railway_uls_report.tables().items():
            standard_tables.append(
                ReportTableInfo(
                    table_key,
                    railway_uls_table_titles.get(table_key, table_key.replace("_", " ").title()),
                    not dataframe.empty,
                    "analysis.railway_u_girder_uls",
                    "Railway U-Girder guarded ULS strength-check framework table. Framework-ready only; not final code-certified.",
                    row_count=len(dataframe),
                    warning="Railway U-Girder ULS framework is guarded engineering-review evidence, not final code-certified design.",
                )
            )

    if railway_release.available:
        railway_release_titles = {
            "railway_u_girder_release_manifest": "Railway U-Girder Release Manifest",
            "railway_u_girder_release_readiness": "Railway U-Girder Release Readiness",
            "railway_u_girder_final_claim_guard": "Railway U-Girder Final Claim Guard",
        }
        for table_key, dataframe in railway_release.tables().items():
            standard_tables.append(
                ReportTableInfo(
                    table_key,
                    railway_release_titles.get(table_key, table_key.replace("_", " ").title()),
                    not dataframe.empty,
                    "reporting.railway_u_girder_release",
                    "Railway U-Girder engineering-review release closeout table. No new UI and not final code-certified design.",
                    row_count=len(dataframe),
                    warning="Railway U-Girder release baseline is closeout-ready for engineering review only; it is not final code-certified design.",
                )
            )


    if railway_final.available:
        railway_final_titles = {
            "railway_u_girder_final_design_check_manifest": "Railway U-Girder Final Design-Check Manifest",
            "railway_u_girder_final_prerequisite_matrix": "Railway U-Girder Final Prerequisite Matrix",
            "railway_u_girder_final_certification_boundary": "Railway U-Girder Final Certification Boundary",
            "railway_u_girder_final_handoff": "Railway U-Girder Final Handoff",
        }
        for table_key, dataframe in railway_final.tables().items():
            standard_tables.append(
                ReportTableInfo(
                    table_key,
                    railway_final_titles.get(table_key, table_key.replace("_", " ").title()),
                    not dataframe.empty,
                    "reporting.railway_u_girder_final",
                    "Railway U-Girder final software design-check evidence table. Complete for engineering-review evidence; Engineer-of-Record certification remains required.",
                    row_count=len(dataframe),
                    warning="Railway U-Girder final design-check package is not legal engineer certification and must not be claimed as Final Code-Certified Design Complete without Engineer-of-Record approval.",
                )
            )
    return standard_tables


def report_tables_to_dataframe(tables: list[ReportTableInfo]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Table Key": table.table_key,
                "Title": table.title,
                "Available": table.available,
                "Source": table.source,
                "Recommended": table.recommended_for_report,
                "Row Count": table.row_count,
                "Description": table.description,
                "Warning": table.warning or "",
            }
            for table in tables
        ],
        columns=["Table Key", "Title", "Available", "Source", "Recommended", "Row Count", "Description", "Warning"],
    )
