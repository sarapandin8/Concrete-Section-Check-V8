from pathlib import Path

import pytest

from concrete_pmm_pro.core.models import LoadCase
from concrete_pmm_pro.geometry.generators import railway_u_girder
from concrete_pmm_pro.serviceability.railway_u_girder_stages import (
    railway_u_girder_final_service_accumulation_dataframe,
    railway_u_girder_final_service_limit_check_dataframe,
    railway_u_girder_sls_decision_summary_dataframe,
    railway_u_girder_staged_stress_limit_check_dataframe,
    railway_u_girder_staged_stress_preview_dataframe,
)
from concrete_pmm_pro.ui.prestress_page import _default_girder_strand_layout_table


def _railway_geometry():
    return railway_u_girder(
        width_mm=5500,
        depth_mm=1600,
        top_wall_width_mm=600,
        bottom_side_width_mm=650,
        haunch_x_mm=300,
        haunch_y_mm=300,
        h1_step_height_mm=670,
        h2_bottom_opening_mm=305,
        h3_floor_side_thickness_mm=395,
        h4_floor_center_thickness_mm=450,
    )


def _stage_settings():
    return {
        "web_fc_MPa": 45.0,
        "web_fci_MPa": 36.0,
        "slab_fc_MPa": 35.0,
        "concrete_unit_weight_kN_m3": 24.0,
        "wet_slab_distribution_each_web": 0.5,
        "formwork_construction_load_kN_m2": 2.5,
        "lifting_point_ratio": 0.20,
        "lifting_impact_factor": 1.10,
    }


def _stage_limits():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    stress_df = railway_u_girder_staged_stress_preview_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        stations_m=[0.5, 5.0, 9.5],
    )
    return railway_u_girder_staged_stress_limit_check_dataframe(stress_df, settings=_stage_settings())


def test_railway_u_girder_sls_decision_summary_reports_four_check_stages():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    loads = [LoadCase(name="SLS-final", Pu_N=0.0, Mux_Nmm=700_000_000.0, load_type="SLS", active=True)]
    final_df = railway_u_girder_final_service_accumulation_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        load_cases=loads,
        station_m=5.0,
    )
    final_limits = railway_u_girder_final_service_limit_check_dataframe(final_df, settings=_stage_settings())

    summary = railway_u_girder_sls_decision_summary_dataframe(
        stage_limit_df=_stage_limits(),
        final_service_limit_df=final_limits,
        active_sls_count=1,
    )

    assert list(summary["Check stage"]) == ["Transfer", "Lifting", "Wet slab casting", "Final service"]
    assert set(summary["Decision"]).issubset({"Preview PASS", "REVIEW"})
    assert summary["Max utilization"].notna().all()
    assert "Final staged service accumulation" in summary.loc[summary["Check stage"] == "Final service", "Governing source"].iloc[0]
    assert "engineering review" in summary.loc[0, "Review action"] or summary.loc[0, "Decision"] == "REVIEW"


def test_railway_u_girder_sls_decision_summary_flags_missing_sls_loads():
    summary = railway_u_girder_sls_decision_summary_dataframe(
        stage_limit_df=_stage_limits(),
        final_service_limit_df=None,
        active_sls_count=0,
    )

    final = summary[summary["Check stage"] == "Final service"].iloc[0]
    assert final["Decision"] == "REVIEW"
    assert final["Governing x / case"] == "No active SLS load case"
    assert "Add/activate SLS load cases" in final["Review action"]


def test_railway_u_girder_sls_decision_summary_turns_fail_into_review():
    stage_limits = _stage_limits()
    stage_limits.loc[stage_limits["Stage"] == "Transfer", "Overall status"] = "FAIL"
    summary = railway_u_girder_sls_decision_summary_dataframe(
        stage_limit_df=stage_limits,
        final_service_limit_df=None,
        active_sls_count=0,
    )

    transfer = summary[summary["Check stage"] == "Transfer"].iloc[0]
    assert transfer["Decision"] == "REVIEW"
    assert "exceeds" in transfer["Review action"]


def test_prestress_ui_mentions_sls_rail_ugirder6_decision_summary():
    source = Path("concrete_pmm_pro/ui/prestress_page.py").read_text(encoding="utf-8")
    module_source = Path("concrete_pmm_pro/serviceability/railway_u_girder_stages.py").read_text(encoding="utf-8")

    assert "SLS.RAIL.UGIRDER6" in source
    assert "Railway U-Girder SLS decision summary" in source
    assert "railway_u_girder_sls_decision_summary_dataframe" in module_source
