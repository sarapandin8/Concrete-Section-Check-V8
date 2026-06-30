from __future__ import annotations

import pandas as pd
import pytest

from concrete_pmm_pro.geometry.generators import railway_u_girder
from concrete_pmm_pro.serviceability.railway_u_girder_stages import (
    railway_u_girder_locked_in_governing_rows,
    railway_u_girder_locked_in_stress_accumulation_dataframe,
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


def test_locked_in_accumulation_separates_web_locked_rows_from_full_u_handoff():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    locked = railway_u_girder_locked_in_stress_accumulation_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        stations_m=[0.5, 5.0],
    )

    assert list(locked["Accumulation step"].unique()) == [
        "1 Transfer locked-in web stress",
        "2 Wet slab casting locked-in web stress",
        "3 Final Pe handoff on full U-section",
    ]
    transfer = locked[locked["Accumulation step"] == "1 Transfer locked-in web stress"]
    wet = locked[locked["Accumulation step"] == "2 Wet slab casting locked-in web stress"]
    final = locked[locked["Accumulation step"] == "3 Final Pe handoff on full U-section"]

    assert set(transfer["Section basis"]) == {"One precast web only"}
    assert set(wet["Section basis"]) == {"One precast web only"}
    assert set(final["Section basis"]) == {"Full Railway U-Girder gross reference"}
    assert wet["Cumulative top (MPa)"].notna().all()
    assert wet["Cumulative bottom (MPa)"].notna().all()
    assert final["Cumulative top (MPa)"].isna().all()
    assert final["Carry-over basis"].str.contains("not summed with web-locked", case=False).all()


def test_locked_in_accumulation_uses_debonded_station_participation():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    table.loc[table["Group ID"] == "L Row 1", "Debonded strand nos"] = "1,9"
    table.loc[table["Group ID"] == "L Row 1", "Left debond m"] = 2.0
    table.loc[table["Group ID"] == "L Row 1", "Right debond m"] = 2.0
    table.loc[table["Group ID"] == "R Row 1", "Debonded strand nos"] = "1,9"
    table.loc[table["Group ID"] == "R Row 1", "Left debond m"] = 2.0
    table.loc[table["Group ID"] == "R Row 1", "Right debond m"] = 2.0

    locked = railway_u_girder_locked_in_stress_accumulation_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        stations_m=[0.5, 5.0],
    )
    transfer = locked[locked["Accumulation step"] == "1 Transfer locked-in web stress"].set_index("Station x (m)")
    final = locked[locked["Accumulation step"] == "3 Final Pe handoff on full U-section"].set_index("Station x (m)")

    # Web-stage handoff uses one side only, so L Row 1 loses two effective
    # strands inside the sleeve and recovers at midspan.
    assert int(transfer.loc[0.5, "Effective strands"]) == 34
    assert int(transfer.loc[5.0, "Effective strands"]) == 36
    # Full-U handoff uses both symmetric webs.
    assert int(final.loc[0.5, "Effective strands"]) == 68
    assert int(final.loc[5.0, "Effective strands"]) == 72


def test_locked_in_governing_rows_are_compact():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    locked = railway_u_girder_locked_in_stress_accumulation_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        stations_m=[0.5, 5.0],
    )
    governing = railway_u_girder_locked_in_governing_rows(locked)

    assert list(governing["Accumulation step"]) == [
        "1 Transfer locked-in web stress",
        "2 Wet slab casting locked-in web stress",
        "3 Final Pe handoff on full U-section",
    ]
    assert governing["Governing compression (MPa)"].notna().all()
    assert governing["Governing tension (MPa)"].notna().all()


def test_prestress_ui_mentions_sls_rail_ugirder3_locked_in_handoff():
    from pathlib import Path

    source = Path("concrete_pmm_pro/ui/prestress_page.py").read_text(encoding="utf-8")
    assert "SLS.RAIL.UGIRDER3 adds a locked-in staged stress accumulation handoff" in source
    assert "Locked-in staged stress accumulation preview" in source
    assert "not algebraically summed with web-locked fibers" in source
