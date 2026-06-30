from __future__ import annotations

import math

import pandas as pd
import pytest

from concrete_pmm_pro.code_checks import (
    aashto_seismic_circular_spiral_required,
    aashto_seismic_column_spacing_limit_mm,
    aashto_seismic_confinement_length_mm,
    aashto_seismic_rectangular_ash_required_mm2,
)
from concrete_pmm_pro.geometry.generators import rectangle
from concrete_pmm_pro.ui.analysis_page import _column_pier_aashto_seismic_spacing_summary_dataframe
from concrete_pmm_pro.ui.rebar_page import (
    _aashto_lrfd_seismic_bridge_column_advisor,
    _default_column_pier_transverse_reinforcement_table,
    load_rebar_database,
)
from concrete_pmm_pro.core.analysis import AnalysisInput, AnalysisSettings
from concrete_pmm_pro.core.design_code import PROJECT_CODE_AASHTO_LRFD
from concrete_pmm_pro.core.models import ConcreteMaterial, Rebar, RebarMaterial


def test_aashto_seismic_spacing_and_confinement_length_use_si_limits() -> None:
    smax, governing = aashto_seismic_column_spacing_limit_mm(900.0)
    length, criteria = aashto_seismic_confinement_length_mm(max_member_dimension_mm=900.0, clear_height_mm=6000.0)

    assert smax == pytest.approx(101.6)
    assert governing == "4.0 in maximum"
    assert length == pytest.approx(1000.0)
    assert any(row["Criterion"] == "1/6 clear height" for row in criteria)


def test_aashto_seismic_rectangular_ash_uses_mpa_ratio_consistently() -> None:
    required, eq2, eq3 = aashto_seismic_rectangular_ash_required_mm2(
        fc_MPa=35.0,
        fyh_MPa=420.0,
        Ag_mm2=600.0 * 900.0,
        Ac_mm2=520.0 * 820.0,
        s_mm=100.0,
        hc_mm=520.0,
    )

    assert required == pytest.approx(max(eq2, eq3))
    assert required > 0.0
    assert eq3 == pytest.approx(0.12 * 100.0 * 520.0 * 35.0 / 420.0)


def test_aashto_seismic_circular_spiral_checks_511_and_564_requirements() -> None:
    asp_req, rho_req, rho_511, rho_564 = aashto_seismic_circular_spiral_required(
        fc_MPa=35.0,
        fyh_MPa=420.0,
        Ag_mm2=math.pi * 600.0**2 / 4.0,
        Ac_mm2=math.pi * 520.0**2 / 4.0,
        dc_mm=520.0,
        s_mm=100.0,
    )

    assert rho_req == pytest.approx(max(rho_511, rho_564))
    assert asp_req == pytest.approx(rho_req * 520.0 * 100.0 / 4.0)


def test_rebar_page_aashto_seismic_advisor_recommends_spacing_and_checks_area() -> None:
    rebar_db = load_rebar_database()
    table = _default_column_pier_transverse_reinforcement_table()
    table.loc[0, "Active"] = True
    table.loc[0, "Bar Size"] = "DB12"
    table.loc[0, "Diameter_mm"] = 12.0
    table.loc[0, "Legs"] = 4
    table.loc[0, "Spacing_mm"] = 100.0
    table.loc[0, "fy_MPa"] = 420.0
    settings = {
        "closed_tie_layout": "Closed ties / hoops",
        "tie_center_offset_mm": 50.0,
        "seismic_clear_height_mm": 6000.0,
    }

    result = _aashto_lrfd_seismic_bridge_column_advisor(
        section_geometry=rectangle(width_mm=600.0, height_mm=900.0),
        settings=settings,
        table=table,
        rebar_db=rebar_db,
        fc_MPa=35.0,
    )

    assert result.code_basis == "AASHTO LRFD 9th seismic bridge-column advisor"
    assert result.s_max_mm == pytest.approx(101.6)
    assert result.suggested_spacing_mm == pytest.approx(100.0)
    assert result.status in {"PASS", "FAIL", "REVIEW"}
    assert any("Required Ash" in row["Criterion"] for row in result.criteria)
    assert not any("not implemented" in note.lower() for note in result.notes)


def test_analysis_page_exposes_aashto_seismic_summary_row() -> None:
    analysis_input = AnalysisInput(
        section_geometry=rectangle(width_mm=600.0, height_mm=900.0),
        concrete_material=ConcreteMaterial(name="C35", fc_MPa=35.0, ecu=0.003),
        rebar_materials=[RebarMaterial(name="SD40", fy_MPa=420.0, Es_MPa=200000.0)],
        rebars=[Rebar(x_mm=0.0, y_mm=0.0, diameter_mm=20.0, material_name="SD40")],
        load_cases=[],
        settings=AnalysisSettings(code=PROJECT_CODE_AASHTO_LRFD),
    )
    state = {
        "column_pier_transverse_reinforcement_settings": {
            "seismic_detailing": "AASHTO LRFD seismic bridge column - manual review",
            "closed_tie_layout": "Closed ties / hoops",
            "tie_center_offset_mm": 50.0,
            "seismic_clear_height_mm": 6000.0,
        },
        "column_pier_transverse_reinforcement_table": [
            {
                "Active": True,
                "Zone": "Control",
                "x_start_m": 0.0,
                "x_end_m": 0.0,
                "Bar Size": "DB12",
                "Diameter_mm": 12.0,
                "Legs": 4.0,
                "Spacing_mm": 100.0,
                "fy_MPa": 420.0,
                "Note": "",
            }
        ],
    }

    df = _column_pier_aashto_seismic_spacing_summary_dataframe(state, analysis_input)

    assert not df.empty
    assert df.iloc[0]["Recommendation"] == "AASHTO 5.11.4 seismic confinement"
    assert "100 mm" in df.iloc[0]["Suggested spacing"]


def test_aashto_seismic_advisor_exposes_confinement_length_inputs() -> None:
    rebar_db = load_rebar_database()
    table = _default_column_pier_transverse_reinforcement_table()
    table.loc[0, "Active"] = True
    table.loc[0, "Bar Size"] = "DB12"
    table.loc[0, "Diameter_mm"] = 12.0
    table.loc[0, "Legs"] = 2
    table.loc[0, "Spacing_mm"] = 100.0
    table.loc[0, "fy_MPa"] = 390.0
    result = _aashto_lrfd_seismic_bridge_column_advisor(
        section_geometry=rectangle(width_mm=600.0, height_mm=900.0),
        settings={"closed_tie_layout": "Closed ties / hoops", "tie_center_offset_mm": 50.0, "seismic_clear_height_mm": 6000.0},
        table=table,
        rebar_db=rebar_db,
        fc_MPa=35.0,
    )

    assert result.clear_height_mm == pytest.approx(6000.0)
    assert result.one_sixth_clear_height_mm == pytest.approx(1000.0)
    assert result.max_member_dimension_mm == pytest.approx(900.0)
    assert result.confinement_min_length_mm == pytest.approx(457.2)
    assert result.confinement_length_mm == pytest.approx(1000.0)
    assert result.confinement_length_governing == "1/6 clear height"
    assert result.area_dc is not None and result.area_dc > 1.0


def test_aashto_seismic_analysis_summary_flags_clear_height_and_overall_status() -> None:
    analysis_input = AnalysisInput(
        section_geometry=rectangle(width_mm=600.0, height_mm=900.0),
        concrete_material=ConcreteMaterial(name="C35", fc_MPa=35.0, ecu=0.003),
        rebar_materials=[RebarMaterial(name="SD40", fy_MPa=420.0, Es_MPa=200000.0)],
        rebars=[Rebar(x_mm=0.0, y_mm=0.0, diameter_mm=20.0, material_name="SD40")],
        load_cases=[],
        settings=AnalysisSettings(code=PROJECT_CODE_AASHTO_LRFD),
    )
    state = {
        "column_pier_transverse_reinforcement_settings": {
            "seismic_detailing": "AASHTO LRFD seismic bridge-column advisor",
            "closed_tie_layout": "Closed ties / hoops",
            "tie_center_offset_mm": 50.0,
            "seismic_clear_height_mm": 6000.0,
        },
        "column_pier_transverse_reinforcement_table": [
            {
                "Active": True,
                "Zone": "Control",
                "x_start_m": 0.0,
                "x_end_m": 0.0,
                "Bar Size": "DB12",
                "Diameter_mm": 12.0,
                "Legs": 2.0,
                "Spacing_mm": 100.0,
                "fy_MPa": 390.0,
                "Note": "",
            }
        ],
    }

    df = _column_pier_aashto_seismic_spacing_summary_dataframe(state, analysis_input)

    assert df.iloc[0]["Clear height input"] == "6000 mm"
    assert df.iloc[0]["1/6 clear height"] == "1000 mm"
    assert df.iloc[0]["Confinement length"] == "1000 mm"
    assert df.iloc[0]["Overall seismic detailing"] == "FAIL / REVIEW"
