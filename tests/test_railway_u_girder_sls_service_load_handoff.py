from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.core.models import LoadCase
from concrete_pmm_pro.geometry.generators import railway_u_girder
from concrete_pmm_pro.serviceability.railway_u_girder_stages import (
    railway_u_girder_service_load_governing_rows,
    railway_u_girder_service_load_handoff_dataframe,
    railway_u_girder_service_load_limit_check_dataframe,
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


def test_service_load_handoff_consumes_active_sls_cases_and_pe_final():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    load_cases = [
        LoadCase(name="SLS-mid", Pu_N=0.0, Mux_Nmm=1_000_000_000.0, load_type="SLS", active=True),
        LoadCase(name="ULS-ignore", Pu_N=0.0, Mux_Nmm=9_000_000_000.0, load_type="ULS", active=True),
        LoadCase(name="SLS-inactive", Pu_N=0.0, Mux_Nmm=2_000_000_000.0, load_type="SLS", active=False),
    ]

    df = railway_u_girder_service_load_handoff_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        load_cases=load_cases,
        station_m=5.0,
    )

    assert df["Load Case"].tolist() == ["SLS-mid"]
    row = df.iloc[0]
    assert row["Section basis"] == "Full Railway U-Girder gross reference"
    assert row["Mux (kN-m)"] == pytest.approx(1000.0)
    assert row["Pe_final (kN)"] > 0.0
    assert int(row["Effective strands"]) == 72
    assert row["Top total (MPa)"] != pytest.approx(row["Load top (MPa)"])


def test_service_load_handoff_uses_station_based_debonding_for_pe_only():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    table.loc[table["Group ID"] == "L Row 1", "Debonded strand nos"] = "1,9"
    table.loc[table["Group ID"] == "L Row 1", "Left debond m"] = 2.0
    table.loc[table["Group ID"] == "L Row 1", "Right debond m"] = 2.0
    table.loc[table["Group ID"] == "R Row 1", "Debonded strand nos"] = "1,9"
    table.loc[table["Group ID"] == "R Row 1", "Left debond m"] = 2.0
    table.loc[table["Group ID"] == "R Row 1", "Right debond m"] = 2.0
    load_cases = [LoadCase(name="SLS", Pu_N=0.0, Mux_Nmm=500_000_000.0, load_type="SLS", active=True)]

    near = railway_u_girder_service_load_handoff_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        load_cases=load_cases,
        station_m=0.5,
    )
    mid = railway_u_girder_service_load_handoff_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        load_cases=load_cases,
        station_m=5.0,
    )

    assert int(near.loc[0, "Effective strands"]) == 68
    assert int(mid.loc[0, "Effective strands"]) == 72
    assert near.loc[0, "Pe_final (kN)"] < mid.loc[0, "Pe_final (kN)"]
    assert near.loc[0, "Mux (kN-m)"] == pytest.approx(mid.loc[0, "Mux (kN-m)"])


def test_service_load_limit_and_governing_rows_are_available():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    loads = [LoadCase(name="SLS-A", Pu_N=100_000.0, Mux_Nmm=800_000_000.0, load_type="SLS", active=True)]
    service = railway_u_girder_service_load_handoff_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        load_cases=loads,
        station_m=5.0,
    )
    limits = railway_u_girder_service_load_limit_check_dataframe(service, settings=_stage_settings())
    governing = railway_u_girder_service_load_governing_rows(service)

    assert limits.loc[0, "Load Case"] == "SLS-A"
    assert limits.loc[0, "Concrete strength used (MPa)"] == pytest.approx(35.0)
    assert limits.loc[0, "Limit stage profile"]
    assert governing.loc[0, "Load Case"] == "SLS-A"
    assert governing.loc[0, "Pe_final (kN)"] > 0.0


def test_prestress_ui_mentions_sls_rail_ugirder4_service_load_handoff():
    source = Path("concrete_pmm_pro/ui/prestress_page.py").read_text(encoding="utf-8")
    module_source = Path("concrete_pmm_pro/serviceability/railway_u_girder_stages.py").read_text(encoding="utf-8")

    assert "SLS.RAIL.UGIRDER4 consumes active SLS load cases from Loads" in source
    assert "Service load handoff from Loads tab" in source
    assert "railway_u_girder_service_load_handoff_dataframe" in module_source
    assert "web-stage locked-in stresses are not transformed and summed" in source
