from __future__ import annotations

import pandas as pd

from concrete_pmm_pro.analysis.uls_strength_routing import beam_girder_uls_strength_route
from concrete_pmm_pro.core.models import ConcreteMaterial, Point2D, Rebar, RebarMaterial, SectionGeometry
from concrete_pmm_pro.ui.analysis_page import (
    _beam_uls_combined_vt_check_dataframe,
    _beam_uls_torsion_check_dataframe,
)


def _below_threshold_state() -> dict:
    geometry = SectionGeometry(
        outer_polygon=[
            Point2D(x=0.0, y=0.0),
            Point2D(x=400.0, y=0.0),
            Point2D(x=400.0, y=900.0),
            Point2D(x=0.0, y=900.0),
        ]
    )
    return {
        "section_geometry": geometry,
        "concrete_material": ConcreteMaterial(name="C40", fc_MPa=40.0),
        "rebars": [Rebar(x_mm=60.0 + i * 20.0, y_mm=80.0, diameter_mm=25.0, material_name="SD40") for i in range(12)],
        "rebar_materials": [RebarMaterial(name="SD40", fy_MPa=400.0, Es_MPa=200000.0)],
        "prestress_elements": [],
        "section_has_ordinary_rebar": True,
        "beam_girder_shear_reinforcement_table": [
            {
                "Active": True,
                "Zone": "Support",
                "x_start_m": 0.0,
                "x_end_m": 10.0,
                "Bar Size": "DB12",
                "Diameter_mm": 12.0,
                "Legs": 2,
                "Spacing_mm": 200.0,
                "fy_MPa": 400.0,
                "Note": "provided",
            }
        ],
    }


def _below_threshold_demand() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Active": True,
                "Station x (m)": 4.0,
                "Case Name": "Strength I",
                "Mux": 100.0,
                "Vuy": 20.0,
                "Tu": 20.0,
                "Muy": 0.0,
                "Vux": 0.0,
                "Nu": 0.0,
                "Note": "",
            }
        ]
    )


def test_torsion_below_threshold_does_not_require_longitudinal_al_layout() -> None:
    route = beam_girder_uls_strength_route(is_bridge=True, is_building=False, code_edition="AASHTO LRFD")

    torsion = _beam_uls_torsion_check_dataframe(_below_threshold_state(), _below_threshold_demand(), strength_route=route).iloc[0]

    assert torsion["Status"] == "BELOW THRESHOLD"
    assert torsion["Threshold status"] == "BELOW THRESHOLD"
    assert torsion["Longitudinal status"] == "NOT REQUIRED"
    assert float(torsion["Al req mm2"]) == 0.0
    assert "Longitudinal torsion Al is not required" in torsion["Notes"]


def test_combined_vt_below_threshold_torsion_does_not_return_data_required_for_missing_al() -> None:
    route = beam_girder_uls_strength_route(is_bridge=True, is_building=False, code_edition="AASHTO LRFD")

    vt = _beam_uls_combined_vt_check_dataframe(_below_threshold_state(), _below_threshold_demand(), strength_route=route).iloc[0]

    assert vt["Status"] == "PASS"
    assert vt["Longitudinal status"] == "NOT REQUIRED"
    assert float(vt["Al V+T req mm2"]) == 0.0
    assert "source torsion row is below threshold" in vt["Notes"]
