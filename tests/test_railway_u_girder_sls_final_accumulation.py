from pathlib import Path

import pytest

from concrete_pmm_pro.core.models import LoadCase
from concrete_pmm_pro.geometry.generators import railway_u_girder
from concrete_pmm_pro.serviceability.railway_u_girder_stages import (
    railway_u_girder_final_service_accumulation_dataframe,
    railway_u_girder_final_service_governing_rows,
    railway_u_girder_final_service_limit_check_dataframe,
    railway_u_girder_service_load_handoff_dataframe,
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


def test_final_service_accumulation_adds_locked_web_stress_and_final_pe_increment():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    loads = [LoadCase(name="SLS-final", Pu_N=0.0, Mux_Nmm=900_000_000.0, load_type="SLS", active=True)]

    final_df = railway_u_girder_final_service_accumulation_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        load_cases=loads,
        station_m=5.0,
    )
    service_df = railway_u_girder_service_load_handoff_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        load_cases=loads,
        station_m=5.0,
    )

    assert final_df["Load Case"].tolist() == ["SLS-final"]
    row = final_df.iloc[0]
    assert row["Section basis"] == "Locked web fibers + full Railway U-Girder incremental service"
    assert row["Locked top (MPa)"] != pytest.approx(0.0)
    assert row["Locked bottom (MPa)"] != pytest.approx(0.0)
    assert row["Pe_final increment (kN)"] < 0.0  # final losses reduce construction Pe
    assert row["Final top (MPa)"] == pytest.approx(
        row["Locked top (MPa)"] + row["Service load top (MPa)"] + row["Final Pe increment top (MPa)"]
    )
    assert row["Final top (MPa)"] != pytest.approx(service_df.loc[0, "Top total (MPa)"])
    assert "additional service actions" in row["Preview note"]


def test_final_service_accumulation_respects_station_based_debonding():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    table.loc[table["Group ID"] == "L Row 1", "Debonded strand nos"] = "1,9"
    table.loc[table["Group ID"] == "L Row 1", "Left debond m"] = 2.0
    table.loc[table["Group ID"] == "L Row 1", "Right debond m"] = 2.0
    table.loc[table["Group ID"] == "R Row 1", "Debonded strand nos"] = "1,9"
    table.loc[table["Group ID"] == "R Row 1", "Left debond m"] = 2.0
    table.loc[table["Group ID"] == "R Row 1", "Right debond m"] = 2.0
    loads = [LoadCase(name="SLS", Pu_N=0.0, Mux_Nmm=500_000_000.0, load_type="SLS", active=True)]

    near = railway_u_girder_final_service_accumulation_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        load_cases=loads,
        station_m=0.5,
    )
    mid = railway_u_girder_final_service_accumulation_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        load_cases=loads,
        station_m=5.0,
    )

    assert int(near.loc[0, "Effective strands"]) == 68
    assert int(mid.loc[0, "Effective strands"]) == 72
    assert near.loc[0, "Pe_final increment (kN)"] != pytest.approx(mid.loc[0, "Pe_final increment (kN)"])


def test_final_service_limit_and_governing_rows_are_available():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    loads = [LoadCase(name="SLS-A", Pu_N=100_000.0, Mux_Nmm=800_000_000.0, load_type="SLS", active=True)]
    final_df = railway_u_girder_final_service_accumulation_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        load_cases=loads,
        station_m=5.0,
    )
    limits = railway_u_girder_final_service_limit_check_dataframe(final_df, settings=_stage_settings())
    governing = railway_u_girder_final_service_governing_rows(final_df)

    assert limits.loc[0, "Load Case"] == "SLS-A"
    assert limits.loc[0, "Concrete strength used (MPa)"] == pytest.approx(35.0)
    assert limits.loc[0, "Limit stage profile"]
    assert governing.loc[0, "Load Case"] == "SLS-A"
    assert governing.loc[0, "Final top (MPa)"] == pytest.approx(final_df.loc[0, "Final top (MPa)"])


def test_prestress_ui_mentions_sls_rail_ugirder5_final_accumulation():
    source = Path("concrete_pmm_pro/ui/prestress_page.py").read_text(encoding="utf-8")
    module_source = Path("concrete_pmm_pro/serviceability/railway_u_girder_stages.py").read_text(encoding="utf-8")

    assert "SLS.RAIL.UGIRDER5" in source
    assert "Final staged service accumulation preview" in source
    assert "railway_u_girder_final_service_accumulation_dataframe" in module_source
    assert "Loads tab values are treated as additional service actions" in module_source
