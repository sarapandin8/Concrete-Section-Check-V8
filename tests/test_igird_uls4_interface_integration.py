import pandas as pd

from concrete_pmm_pro.analysis.igird_interface_shear import SURFACE_ROUGHENED_GIRDER_SLAB
from concrete_pmm_pro.analysis.uls_strength_routing import beam_girder_uls_strength_route
from concrete_pmm_pro.core.models import ConcreteMaterial, Point2D, SectionGeometry
from concrete_pmm_pro.ui.analysis_page import (
    _beam_uls_final_composite_preparation,
    _igird_interface_overall_status,
    _igird_interface_shear_dataframe,
)


def _geometry():
    return SectionGeometry(
        name="QA I girder",
        outer_polygon=[
            Point2D(x=-400.0, y=0.0),
            Point2D(x=400.0, y=0.0),
            Point2D(x=400.0, y=1600.0),
            Point2D(x=-400.0, y=1600.0),
        ],
    )


def _state():
    strand_table = pd.DataFrame([
        {
            "Active": True,
            "Group ID": "Bottom",
            "No. Strands": 20,
            "Area/Strand_mm2": 140.0,
            "Total Aps_mm2": 2800.0,
            "y_mm_from_bottom": 120.0,
            "Pe_transfer/strand_kN": 150.0,
            "Pe_construction/strand_kN": 140.0,
            "Pe_eff_final/strand_kN": 120.0,
            "Left debond m": 0.0,
            "Right debond m": 0.0,
        }
    ])
    return {
        "section_geometry": _geometry(),
        "concrete_material": ConcreteMaterial(name="Girder", fc_MPa=45.0, density_kg_m3=2400.0),
        "section_parameters": {
            "composite_enabled": True,
            "B1_mm": 800.0,
            "Be_mm": 2400.0,
            "Tslab_mm": 220.0,
            "deck_fc_MPa": 35.0,
            "Be_mode": "Manual",
            "Be_strength_verified": True,
        },
        "girder_strand_layout_table": strand_table,
        "rebars": [],
        "rebar_materials": [],
        "prestress_elements": [],
        "prestress_materials": [],
        "beam_girder_shear_reinforcement_table": pd.DataFrame([
            {"Active": True, "Zone": "Full span", "x_start_m": 0.0, "x_end_m": 20.0, "Bar Size": "DB12", "Diameter_mm": 12.0, "Legs": 2.0, "Spacing_mm": 150.0, "fy_MPa": 390.0, "Note": ""}
        ]),
    }


def _demand():
    return pd.DataFrame([
        {"Active": True, "Station x (m)": 0.0, "Case Name": "Strength I", "Mux": 0.0, "Vuy": 500.0, "Tu": 0.0, "Muy": 0.0, "Vux": 0.0, "Nu": 0.0, "Note": ""},
        {"Active": True, "Station x (m)": 10.0, "Case Name": "Strength I", "Mux": 3000.0, "Vuy": 0.0, "Tu": 0.0, "Muy": 0.0, "Vux": 0.0, "Nu": 0.0, "Note": ""},
        {"Active": True, "Station x (m)": 20.0, "Case Name": "Strength I", "Mux": 0.0, "Vuy": -500.0, "Tu": 0.0, "Muy": 0.0, "Vux": 0.0, "Nu": 0.0, "Note": ""},
    ])


def _route():
    return beam_girder_uls_strength_route(
        is_bridge=True,
        is_building=False,
        project_design_code="AASHTO LRFD",
        code_edition="AASHTO LRFD 9th Edition",
    )


def test_uls4_interface_check_reuses_b1_strands_and_stirrup_zones_and_passes_low_demand():
    state = _state()
    prep, composite_state, _ = _beam_uls_final_composite_preparation(state)
    assert composite_state is not None
    result, messages = _igird_interface_shear_dataframe(
        state,
        _demand(),
        prep=prep,
        composite_state=composite_state,
        settings={
            "surface_key": SURFACE_ROUGHENED_GIRDER_SLAB,
            "width_mode": "Auto — I-Girder top flange B1",
            "bvi_override_mm": None,
            "stirrups_cross_and_anchored": True,
        },
        strength_route=_route(),
    )
    assert not result.empty
    assert _igird_interface_overall_status(result) == "PASS"
    assert set(result["bvi (mm)"]) == {800.0}
    assert (result["dv interface (mm)"] > 0.0).all()
    assert (result["fy used <=60 ksi (MPa)"] <= 413.686).all()
    assert (result["Strength D/C"].fillna(0.0) <= 1.0).all()
    assert any("Pc = 0" in note for note in messages)


def test_uls4_withholds_avf_credit_and_reports_review_until_anchorage_confirmed():
    state = _state()
    prep, composite_state, _ = _beam_uls_final_composite_preparation(state)
    result, _ = _igird_interface_shear_dataframe(
        state,
        _demand(),
        prep=prep,
        composite_state=composite_state,
        settings={
            "surface_key": SURFACE_ROUGHENED_GIRDER_SLAB,
            "width_mode": "Auto — I-Girder top flange B1",
            "bvi_override_mm": None,
            "stirrups_cross_and_anchored": False,
        },
        strength_route=_route(),
    )
    assert _igird_interface_overall_status(result) == "REVIEW"
    assert (result["Avf credited (mm2/m)"] == 0.0).all()
    assert (result["Status"] == "REVIEW").all()
