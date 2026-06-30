from __future__ import annotations

import pytest

from concrete_pmm_pro.geometry.generators import railway_u_girder
from concrete_pmm_pro.serviceability.railway_u_girder_stages import (
    lifting_udl_moment_kNm,
    railway_u_girder_stage_basis_set,
    railway_u_girder_staged_stress_preview_dataframe,
    railway_u_girder_web_geometry,
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
        "concrete_unit_weight_kN_m3": 24.0,
        "wet_slab_distribution_each_web": 0.5,
        "formwork_construction_load_kN_m2": 2.5,
        "lifting_point_ratio": 0.20,
        "lifting_impact_factor": 1.10,
    }


def test_railway_u_girder_web_basis_uses_one_precast_web_not_full_u():
    geom = _railway_geometry()
    web = railway_u_girder_web_geometry(geom)
    basis = railway_u_girder_stage_basis_set(geom, _stage_settings())

    assert web.name == "Railway U-Girder precast web only"
    assert basis.quantities.web_area_mm2 == pytest.approx(992_562.5)
    assert basis.quantities.slab_area_mm2 == pytest.approx(1_848_000.0)
    assert basis.web_basis.area_mm2 == pytest.approx(992_562.5)
    assert basis.full_u_basis.area_mm2 > 3.0 * basis.web_basis.area_mm2
    assert basis.quantities.web_self_weight_kN_m == pytest.approx(23.8215)
    assert basis.quantities.wet_slab_to_each_web_kN_m == pytest.approx(22.176)
    assert basis.quantities.formwork_to_each_web_kN_m == pytest.approx(5.25)


def test_two_point_lifting_moment_has_negative_overhang_and_positive_midspan():
    w = 10.0
    L = 10.0
    assert lifting_udl_moment_kNm(w, 0.0, L, 0.20) == pytest.approx(0.0)
    assert lifting_udl_moment_kNm(w, 2.0, L, 0.20) == pytest.approx(-20.0)
    assert lifting_udl_moment_kNm(w, 5.0, L, 0.20) == pytest.approx(25.0)
    assert lifting_udl_moment_kNm(w, 10.0, L, 0.20) == pytest.approx(0.0)


def test_staged_stress_preview_consumes_station_based_debonding_for_web_stage():
    geom = _railway_geometry()
    table = _default_girder_strand_layout_table(geom)
    table.loc[table["Group ID"] == "L Row 1", "Debonded strand nos"] = "1,9"
    table.loc[table["Group ID"] == "L Row 1", "Left debond m"] = 2.0
    table.loc[table["Group ID"] == "L Row 1", "Right debond m"] = 2.0
    table.loc[table["Group ID"] == "R Row 1", "Debonded strand nos"] = "1,9"
    table.loc[table["Group ID"] == "R Row 1", "Left debond m"] = 2.0
    table.loc[table["Group ID"] == "R Row 1", "Right debond m"] = 2.0

    preview = railway_u_girder_staged_stress_preview_dataframe(
        geometry=geom,
        settings=_stage_settings(),
        strand_table=table,
        span_length_m=10.0,
        stations_m=[0.5, 5.0],
    )
    transfer = preview[preview["Stage"] == "Transfer"].set_index("Station x (m)")
    service = preview[preview["Stage"] == "Service Pe reference"].set_index("Station x (m)")

    # Transfer uses one web only, so only L-row strands are counted. Two L Row 1
    # strands are ineffective inside the left sleeve and recover at midspan.
    assert int(transfer.loc[0.5, "Effective strands"]) == 34
    assert int(transfer.loc[5.0, "Effective strands"]) == 36
    assert transfer.loc[0.5, "Section basis"] == "One precast web only"
    assert transfer.loc[0.5, "Pe stage (kN)"] < transfer.loc[5.0, "Pe stage (kN)"]

    # Full-U service reference uses both webs, not the one-web filtered table.
    assert int(service.loc[5.0, "Effective strands"]) == 72
    assert service.loc[5.0, "Section basis"] == "Full Railway U-Girder gross reference"


def test_prestress_page_contains_railway_sls_stage_preview_guardrails():
    from pathlib import Path

    source = Path("concrete_pmm_pro/ui/prestress_page.py").read_text(encoding="utf-8")
    assert "Railway U-Girder staged SLS stress preview" in source
    assert "SLS.RAIL.UGIRDER1 consumes station-based debonded strand participation" in source
    assert "Transfer, lifting, and wet slab casting use one precast web only" in source
    assert "Locked-in staged stress superposition" in source
