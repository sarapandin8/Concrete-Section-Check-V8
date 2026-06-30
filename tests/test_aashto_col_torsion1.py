from __future__ import annotations

import math

import pytest

from concrete_pmm_pro.code_checks import aashto_simplified_torsion_result, aashto_torsional_cracking_moment_nmm
from concrete_pmm_pro.core.analysis import AnalysisInput, AnalysisSettings
from concrete_pmm_pro.core.design_code import PROJECT_CODE_AASHTO_LRFD
from concrete_pmm_pro.core.models import ConcreteMaterial, LoadCase, PrestressElement, Rebar, RebarMaterial
from concrete_pmm_pro.geometry.generators import rectangle
from concrete_pmm_pro.ui.analysis_page import (
    _column_pier_check_decision_rows,
    _column_pier_torsion_check_dataframe,
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
        load_cases=[LoadCase(name="ULS-T", Pu_N=1_200_000.0, Mux_Nmm=0.0, Muy_Nmm=0.0, load_type="ULS")],
        settings=AnalysisSettings(code=PROJECT_CODE_AASHTO_LRFD, transverse_reinforcement="tied"),
    )


def _state(*, tu_kNm: float = 60.0, with_prestress: bool = False, open_ties: bool = False) -> dict[str, object]:
    return {
        "project_design_code": PROJECT_CODE_AASHTO_LRFD,
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "design_code": "ACI 318",  # stale widget key must not control routing
        "code_edition": "ACI 318-19",
        "column_uls_loads_table": [
            {
                "Active": True,
                "Case Name": "ULS-T",
                "Pu": -50.0 if with_prestress else 1_200.0,
                "Mux": 120.0,
                "Muy": 60.0,
                "Vux": 120.0,
                "Vuy": 80.0,
                "Tu": tu_kNm,
                "Note": "",
            }
        ],
        "column_pier_transverse_reinforcement_settings": {
            "closed_tie_layout": "Open ties - shear only review" if open_ties else "Closed ties / hoops",
            "torsion_core_basis": "Auto from section and tie offset",
            "tie_center_offset_mm": 50.0,
        },
        "column_pier_transverse_reinforcement_table": [
            {
                "Active": True,
                "Zone": "Control",
                "x_start_m": 0.0,
                "x_end_m": 1.0,
                "Bar Size": "DB16",
                "Diameter_mm": 16.0,
                "Legs": 4.0,
                "Spacing_mm": 100.0,
                "fy_MPa": 420.0,
                "Note": "",
            }
        ],
        "rebars": [
            Rebar(x_mm=-250.0, y_mm=-380.0, diameter_mm=25.0, material_name="SD40", label="B1"),
            Rebar(x_mm=250.0, y_mm=-380.0, diameter_mm=25.0, material_name="SD40", label="B2"),
            Rebar(x_mm=250.0, y_mm=380.0, diameter_mm=25.0, material_name="SD40", label="B3"),
            Rebar(x_mm=-250.0, y_mm=380.0, diameter_mm=25.0, material_name="SD40", label="B4"),
        ],
    }


def test_aashto_torsion1_helper_uses_threshold_and_phi_tn_in_si() -> None:
    result = aashto_simplified_torsion_result(
        fc_MPa=45.0,
        Acp_mm2=600.0 * 900.0,
        Pcp_mm=2.0 * (600.0 + 900.0),
        Ao_mm2=(600.0 - 100.0) * (900.0 - 100.0) * 0.85,
        ph_mm=2.0 * ((600.0 - 100.0) + (900.0 - 100.0)),
        tu_Nmm=60.0e6,
        at_mm2_per_mm=math.pi * 16.0**2 / 4.0 / 100.0,
        fy_MPa=420.0,
        spacing_mm=100.0,
    )

    assert result.phi == pytest.approx(0.90)
    assert result.theta_deg == pytest.approx(45.0)
    assert result.tcr_Nmm > 0.0
    assert result.threshold_Nmm == pytest.approx(0.25 * result.phi_tcr_Nmm)
    assert result.phi_tn_Nmm == pytest.approx(0.90 * result.tn_Nmm)
    assert "5.7.3.6.2" in result.basis


def test_aashto_torsion1_cracking_helper_converts_sqrt_fc_to_si() -> None:
    tcr = aashto_torsional_cracking_moment_nmm(fc_MPa=45.0, Acp_mm2=540_000.0, Pcp_mm=3_000.0)
    assert tcr > 0.0
    # If MPa were incorrectly inserted into a ksi-root formula directly, this
    # value would be badly distorted.  This simple range check guards the route.
    assert 0.0 < tcr / 1.0e6 < 1_000.0


def test_aashto_torsion1_dataframe_routes_to_aashto_not_aci() -> None:
    torsion_df = _column_pier_torsion_check_dataframe(_state(tu_kNm=60.0), _analysis_input())

    assert not torsion_df.empty
    assert set(torsion_df["Code basis"]) == {"AASHTO LRFD 9th Column/Pier torsion"}
    assert not torsion_df["Method"].str.contains("ACI", case=False).any()
    assert set(torsion_df["phi"]) == pytest.approx([0.90])
    assert set(torsion_df["Status"]).issubset({"PASS", "FAIL", "REVIEW", "BELOW THRESHOLD"})


def test_aashto_torsion1_open_ties_are_review_not_false_pass() -> None:
    torsion_df = _column_pier_torsion_check_dataframe(_state(tu_kNm=60.0, open_ties=True), _analysis_input())

    assert not torsion_df.empty
    assert set(torsion_df["Status"]) == {"REVIEW"}
    assert torsion_df["Notes"].str.contains("closed", case=False).any()


def test_aashto_torsion1_prestress_remains_review() -> None:
    torsion_df = _column_pier_torsion_check_dataframe(_state(tu_kNm=60.0, with_prestress=True), _analysis_input(with_prestress=True))

    assert not torsion_df.empty
    assert set(torsion_df["Status"]) == {"REVIEW"}
    assert torsion_df["Notes"].str.contains("Prestressed torsion", case=False).any()


def test_aashto_torsion1_decision_view_no_longer_says_not_implemented() -> None:
    rows = _column_pier_check_decision_rows(_state(tu_kNm=60.0), _analysis_input())
    torsion_row = next(row for row in rows if row["Check"] == "Torsion")

    assert "not implemented" not in torsion_row["Route / Scope"].lower()
    assert "AASHTO LRFD 9th Section 5.7.3.6" in torsion_row["Route / Scope"]
