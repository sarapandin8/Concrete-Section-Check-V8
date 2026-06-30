from __future__ import annotations

import math

import pytest

from concrete_pmm_pro.code_checks import aashto_min_transverse_avs_mm2_per_mm, aashto_simplified_shear_result
from concrete_pmm_pro.core.analysis import AnalysisInput, AnalysisSettings
from concrete_pmm_pro.core.design_code import PROJECT_CODE_AASHTO_LRFD
from concrete_pmm_pro.core.models import ConcreteMaterial, LoadCase, PrestressElement, Rebar, RebarMaterial
from concrete_pmm_pro.geometry.generators import rectangle
from concrete_pmm_pro.ui.analysis_page import (
    _column_pier_check_decision_rows,
    _column_pier_decision_caption_for_code,
    _column_pier_shear_check_dataframe,
    _column_pier_uls_decision_summary_cards,
)


def _analysis_input(*, with_prestress: bool = False) -> AnalysisInput:
    prestress = []
    if with_prestress:
        prestress = [
            PrestressElement(
                x_mm=0.0,
                y_mm=-250.0,
                area_mm2=140.0,
                steel_type="strand",
                pe_eff_n=125_000.0,
                initial_stress_mpa=800.0,
                fpy_mpa=1670.0,
                fpu_mpa=1860.0,
                ep_mpa=195000.0,
                bonded=True,
                count=2,
                label="PS",
            )
        ]
    return AnalysisInput(
        section_geometry=rectangle(width_mm=600.0, height_mm=900.0),
        concrete_material=ConcreteMaterial(name="C45", fc_MPa=45.0, ecu=0.003),
        rebar_materials=[RebarMaterial(name="SD40", fy_MPa=420.0, Es_MPa=200000.0)],
        rebars=[
            Rebar(x_mm=-250.0, y_mm=-380.0, diameter_mm=25.0, material_name="SD40", label="B1"),
            Rebar(x_mm=250.0, y_mm=-380.0, diameter_mm=25.0, material_name="SD40", label="B2"),
            Rebar(x_mm=250.0, y_mm=380.0, diameter_mm=25.0, material_name="SD40", label="B3"),
            Rebar(x_mm=-250.0, y_mm=380.0, diameter_mm=25.0, material_name="SD40", label="B4"),
        ],
        prestress_elements=prestress,
        load_cases=[LoadCase(name="ULS-S", Pu_N=1_200_000.0, Mux_Nmm=0.0, Muy_Nmm=0.0, load_type="ULS")],
        settings=AnalysisSettings(code=PROJECT_CODE_AASHTO_LRFD, transverse_reinforcement="tied"),
    )


def _state(*, with_prestress: bool = False, high_demand: bool = False) -> dict[str, object]:
    return {
        "project_design_code": PROJECT_CODE_AASHTO_LRFD,
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "design_code": "ACI 318",  # stale widget key must not control routing
        "code_edition": "ACI 318-19",
        "column_uls_loads_table": [
            {
                "Active": True,
                "Case Name": "ULS-S",
                "Pu": -50.0 if with_prestress else 1_200.0,
                "Mux": 0.0,
                "Muy": 0.0,
                "Vux": 2_800.0 if high_demand else 280.0,
                "Vuy": 180.0,
                "Tu": 0.0,
                "Note": "",
            }
        ],
        "column_pier_transverse_reinforcement_table": [
            {
                "Active": True,
                "Zone": "Control",
                "x_start_m": 0.0,
                "x_end_m": 1.0,
                "Bar Size": "DB12",
                "Diameter_mm": 12.0,
                "Legs": 4.0,
                "Spacing_mm": 150.0,
                "fy_MPa": 420.0,
                "Note": "",
            }
        ],
    }


def test_aashto_shear1_helper_uses_si_safe_sqrt_fc_and_nominal_cap() -> None:
    result = aashto_simplified_shear_result(
        fc_MPa=45.0,
        bv_mm=600.0,
        dv_mm=720.0,
        vu_N=280_000.0,
        avs_mm2_per_mm=math.pi * 12.0**2 / 4.0 * 4.0 / 150.0,
        fy_MPa=420.0,
    )

    assert result.phi == pytest.approx(0.90)
    assert result.beta == pytest.approx(2.0)
    assert result.theta_deg == pytest.approx(45.0)
    assert result.phi_vn_N == pytest.approx(0.90 * result.vn_N)
    assert result.vn_N <= result.vn_limit_N + 1.0e-6
    assert result.avs_required_mm2_per_mm == pytest.approx(aashto_min_transverse_avs_mm2_per_mm(45.0, 600.0, 420.0))
    assert "5.7.3.3" in result.basis


def test_aashto_shear1_column_pier_dataframe_routes_to_aashto_and_passes_nonprestressed_case() -> None:
    shear_df = _column_pier_shear_check_dataframe(_state(), _analysis_input())

    assert not shear_df.empty
    assert set(shear_df["Code basis"]) == {"AASHTO LRFD 9th Column/Pier shear"}
    assert set(shear_df["Status"]) == {"PASS"}
    assert shear_df["phi"].tolist() == pytest.approx([0.90, 0.90])
    assert shear_df["beta"].tolist() == pytest.approx([2.0, 2.0])
    assert shear_df["theta deg"].tolist() == pytest.approx([45.0, 45.0])
    assert not shear_df["Method"].str.contains("ACI", case=False).any()


def test_aashto_shear1_high_demand_fails_strength_or_detailing_gate() -> None:
    shear_df = _column_pier_shear_check_dataframe(_state(high_demand=True), _analysis_input())

    assert "FAIL" in set(shear_df["Status"])
    assert shear_df["Governing D/C value"].max() > 1.0


def test_aashto_shear1_prestressed_or_axial_tension_row_is_review_not_false_pass() -> None:
    shear_df = _column_pier_shear_check_dataframe(_state(with_prestress=True), _analysis_input(with_prestress=True))

    assert not shear_df.empty
    assert set(shear_df["Status"]) == {"REVIEW"}
    assert shear_df["Notes"].str.contains("general procedure/PSC", case=False).any()


def test_aashto_shear1_decision_view_exposes_aashto_shear_route() -> None:
    analysis_input = _analysis_input()
    state = _state()

    rows = _column_pier_check_decision_rows(state, analysis_input)
    cards = _column_pier_uls_decision_summary_cards(rows, analysis_input, state)
    shear_row = next(row for row in rows if row["Check"] == "Shear")

    assert shear_row["Status"] == "PASS"
    assert "AASHTO LRFD 9th Section 5.7 simplified shear route" in shear_row["Route / Scope"]
    assert "not implemented" not in shear_row["Route / Scope"]
    assert "AASHTO Section 5.7 simplified shear" in _column_pier_decision_caption_for_code(PROJECT_CODE_AASHTO_LRFD)
    assert cards[1]["value"] == PROJECT_CODE_AASHTO_LRFD
