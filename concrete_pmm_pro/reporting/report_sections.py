"""Report section planning helpers."""

from __future__ import annotations

import pandas as pd

from concrete_pmm_pro.reporting.limitations import EngineeringLimitation
from concrete_pmm_pro.reporting.readiness import ReportReadinessSummary
from concrete_pmm_pro.reporting.report_models import ReportSection
from concrete_pmm_pro.reporting.traceability import ReportFigureInfo, ResultTraceabilitySnapshot


def _available_figure_keys(figures: list[ReportFigureInfo]) -> set[str]:
    return {figure.figure_key for figure in figures if figure.available}


def _limitation_keys(limitations: list[EngineeringLimitation], risk_levels: set[str] | None = None) -> list[str]:
    return [item.key for item in limitations if risk_levels is None or item.risk_level in risk_levels]


def default_report_section_plan(
    snapshot: ResultTraceabilitySnapshot,
    readiness_summary: ReportReadinessSummary,
    figures: list[ReportFigureInfo],
    limitations: list[EngineeringLimitation],
) -> list[ReportSection]:
    figure_keys = _available_figure_keys(figures)
    high_limitation_keys = _limitation_keys(limitations, {"HIGH", "CRITICAL"})
    uls_available = bool(getattr(snapshot, "uls_result_available", False) or snapshot.pmm_result_available)
    pmm_status = "AVAILABLE" if snapshot.pmm_result_available else ("NOT_APPLICABLE" if uls_available else "MISSING")
    dc_status = "AVAILABLE" if snapshot.dc_result_available else ("PARTIAL" if uls_available else "MISSING")
    sls_status = "AVAILABLE" if snapshot.sls_result_available else "MISSING"
    crack_status = "AVAILABLE" if snapshot.crack_classification_available else ("PARTIAL" if snapshot.sls_result_available else "MISSING")
    beam_summary = None
    if snapshot.member_type == "beam_girder":
        beam_summary = "Beam/Girder workflow includes guarded ULS/SLS preview checks; final code-certified design and excluded detailing checks remain outside current report scope."
    scope_limitation_keys: list[str] = []
    if snapshot.member_type == "beam_girder":
        scope_limitation_keys.append("beam_girder_shear_torsion")
        scope_limitation_keys.append("railway_u_girder_sls_report_scope")
    elif snapshot.member_type == "column_pier_pmm":
        scope_limitation_keys.append("column_pier_vt_scope")
    column_pier_vt_status = "AVAILABLE" if snapshot.member_type == "column_pier_pmm" else "NOT_APPLICABLE"
    verification_table_keys = ["pmm_verification", "hand_check_results", "sls_verification_results", "pmm_published_benchmark_inventory"]
    verification_available = any([snapshot.pmm_verification_status, snapshot.hand_check_status, snapshot.sls_verification_status])
    if snapshot.member_type == "column_pier_pmm":
        verification_table_keys.append("column_pier_vt_qa1_benchmarks")
        verification_available = True

    return [
        ReportSection("executive_summary", "Executive Summary", summary=f"Report readiness: {readiness_summary.overall_status}.", table_keys=["result_traceability_snapshot", "report_readiness"], limitation_keys=high_limitation_keys),
        ReportSection("project_metadata", "Project / Analysis Metadata", table_keys=["result_traceability_snapshot"]),
        ReportSection("analysis_mode_scope", "Analysis Mode and Scope", summary=beam_summary or "Current analysis workflow metadata is summarized.", limitation_keys=scope_limitation_keys),
        ReportSection("geometry_materials", "Section Geometry and Materials", status="AVAILABLE" if snapshot.section_available and snapshot.materials_available else "PARTIAL", figure_keys=["section_geometry_layout"] if "section_geometry_layout" in figure_keys else [], table_keys=["result_traceability_snapshot"]),
        ReportSection("reinforcement_prestress", "Reinforcement and Prestress Layout", status="AVAILABLE" if snapshot.rebar_count or snapshot.prestress_count else "PARTIAL", table_keys=["custom_stress_check_points"], figure_keys=["custom_stress_points_layout"] if "custom_stress_points_layout" in figure_keys else []),
        ReportSection("uls_pmm_strength", "ULS PMM Strength Check", status=pmm_status, table_keys=["pmm_summary"], figure_keys=[key for key in ["pmm_interaction_surface", "pmm_mux_muy_slice"] if key in figure_keys], limitation_keys=["neutral_axis_sweep_resolution", "prestress_axial_cap"]),
        ReportSection("uls_dc_summary", "ULS Demand / Capacity Summary", status=dc_status, table_keys=["uls_demand_capacity_result", "pmm_slice", "pmm_slice_envelope"], figure_keys=["pmm_slice_envelope"] if "pmm_slice_envelope" in figure_keys else [], limitation_keys=["dc_directional_slice_envelope", "convex_hull_slice_envelope"]),
        ReportSection(
            "column_pier_vt_strength_gate",
            "Column/Pier Shear + Torsion Strength Gate",
            status=column_pier_vt_status,
            summary="Stored Column/Pier V+T report preview mirrors the Analysis Shear + Torsion page: strength gate, controlling cause, compact results, audit detail, and amber seismic scope guard.",
            table_keys=[
                "column_pier_vt_report_summary",
                "column_pier_vt_report_results",
                "column_pier_vt_report_audit",
                "column_pier_vt_report_scope_guard",
            ],
            limitation_keys=["column_pier_vt_scope"],
        ),
        ReportSection("sls_stress_check", "SLS Stress Check", status=sls_status, table_keys=["sls_stress_results", "sls_prestress_contribution", "transformed_section_properties"], figure_keys=[key for key in ["sls_section_stress_points", "sls_stress_bar_diagram", "transformed_section_preview"] if key in figure_keys], limitation_keys=["ixy_coupling_sls", "cracked_section_sls", "unbonded_prestress"]),
        ReportSection(
            "generic_precast_lifting_stage_report",
            "Generic Precast Lifting Stage Stress Check",
            status="AVAILABLE" if snapshot.member_type == "beam_girder" else "NOT_APPLICABLE",
            summary="Generic non-Railway precast girder lifting report section when the active preset is I-girder, box beam, plank girder, or voided plank girder; engineering-review only.",
            table_keys=[
                "generic_precast_lifting_scope",
                "generic_precast_lifting_settings",
                "generic_precast_lifting_load_basis",
                "generic_precast_lifting_station_stress_rows",
                "generic_precast_lifting_governing_rows",
                "generic_precast_lifting_closeout_guard",
            ],
            limitation_keys=["beam_girder_shear_torsion"],
        ),
        ReportSection(
            "railway_u_girder_sls_engineering_review",
            "Railway U-Girder SLS Engineering Review",
            status="AVAILABLE" if snapshot.member_type == "beam_girder" else "NOT_APPLICABLE",
            summary="Railway U-Girder staged SLS report-ready section when the active preset is Railway U-Girder; guarded engineering-review only, not final code-certified.",
            table_keys=[
                "railway_u_girder_sls_scope",
                "railway_u_girder_geometry_summary",
                "railway_u_girder_material_stage_settings",
                "railway_u_girder_stage_quantities",
                "railway_u_girder_prestress_debonding_summary",
                "railway_u_girder_sls_stage_governing",
                "railway_u_girder_sls_limit_governing",
                "railway_u_girder_sls_final_service_governing",
                "railway_u_girder_sls_decision_summary",
                "railway_u_girder_service_multifiber_summary",
            ],
            limitation_keys=["railway_u_girder_sls_report_scope", "beam_girder_shear_torsion"],
        ),
        ReportSection("cracking_classification", "No-Tension / Decompression / Cracking Classification", status=crack_status, table_keys=["cracking_classification"], figure_keys=["cracking_classification_overlay"] if "cracking_classification_overlay" in figure_keys else [], limitation_keys=["cracked_section_sls", "crack_width_check"]),
        ReportSection("sls_visualization", "SLS Stress Visualization", status="AVAILABLE" if snapshot.sls_result_available else "MISSING", table_keys=["sls_visualization_selected_combo"], figure_keys=[key for key in ["sls_section_stress_points", "sls_stress_bar_diagram"] if key in figure_keys]),
        ReportSection("verification", "Verification and Benchmark Checks", status="AVAILABLE" if verification_available else "PARTIAL", table_keys=verification_table_keys),
        ReportSection("warnings_limitations", "Engineering Warnings and Limitations", table_keys=["engineering_warnings", "engineering_limitations"], limitation_keys=[item.key for item in limitations], warnings=list(snapshot.warnings)),
        ReportSection("units_terminology", "Unit Conventions and Terminology", table_keys=["unit_conventions", "terminology"]),
        ReportSection("appendices_raw_tables", "Appendices / Raw Tables", status="PARTIAL", table_keys=["result_traceability_snapshot", "report_readiness", "engineering_limitations"]),
    ]


def report_sections_to_dataframe(sections: list[ReportSection]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Section ID": section.section_id,
                "Title": section.title,
                "Level": section.level,
                "Include": section.include,
                "Status": section.status,
                "Summary": section.summary or "",
                "Tables": ", ".join(section.table_keys),
                "Figures": ", ".join(section.figure_keys),
                "Limitations": ", ".join(section.limitation_keys),
                "Warnings": "\n".join(section.warnings),
            }
            for section in sections
        ],
        columns=["Section ID", "Title", "Level", "Include", "Status", "Summary", "Tables", "Figures", "Limitations", "Warnings"],
    )
