from __future__ import annotations

import pytest

from concrete_pmm_pro.geometry.generators import railway_u_girder
from concrete_pmm_pro.serviceability.railway_u_girder_stages import (
    railway_u_girder_stage_limit_governing_rows,
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


def test_railway_u_girder_stage_limit_preview_assigns_strength_by_stage():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    stress_df = railway_u_girder_staged_stress_preview_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        stations_m=[0.5, 5.0],
    )

    limits = railway_u_girder_staged_stress_limit_check_dataframe(stress_df, settings=_stage_settings())
    by_stage = limits.groupby("Stage")["Concrete strength used (MPa)"].first().to_dict()

    assert by_stage["Transfer"] == pytest.approx(36.0)
    assert by_stage["Lifting"] == pytest.approx(36.0)
    assert by_stage["Wet slab casting"] == pytest.approx(45.0)
    assert by_stage["Service Pe reference"] == pytest.approx(35.0)
    assert set(limits["Overall status"].unique()).issubset({"PASS", "FAIL", "NOT_CHECKED"})
    assert "Transfer / Release" in set(limits["Limit stage profile"])
    assert "Deck casting / Pre-composite" in set(limits["Limit stage profile"])
    assert "Final service / Composite" in set(limits["Limit stage profile"])


def test_railway_u_girder_stage_limit_governing_rows_are_compact_per_stage():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    stress_df = railway_u_girder_staged_stress_preview_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        stations_m=[0.5, 5.0],
    )
    limits = railway_u_girder_staged_stress_limit_check_dataframe(stress_df, settings=_stage_settings())
    governing = railway_u_girder_stage_limit_governing_rows(limits)

    assert list(governing["Stage"]) == ["Transfer", "Lifting", "Wet slab casting", "Service Pe reference"]
    assert governing["Max utilization"].notna().all()


def test_prestress_ui_mentions_sls_rail_ugirder2_limit_checks():
    from pathlib import Path

    source = Path("concrete_pmm_pro/ui/prestress_page.py").read_text(encoding="utf-8")
    assert "SLS.RAIL.UGIRDER2 consumes station-based debonded strand participation" in source
    assert "Stage stress-limit preview" in source
    assert "Stage stress-limit rows are editable preview checks" in source
