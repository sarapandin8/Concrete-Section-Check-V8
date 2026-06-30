from __future__ import annotations

import math

import pytest

from concrete_pmm_pro.code_checks import aashto_combined_shear_torsion_result
from concrete_pmm_pro.core.analysis import AnalysisInput, AnalysisSettings
from concrete_pmm_pro.core.design_code import PROJECT_CODE_AASHTO_LRFD
from concrete_pmm_pro.core.models import ConcreteMaterial, LoadCase, Rebar, RebarMaterial
from concrete_pmm_pro.geometry.generators import rectangle
from concrete_pmm_pro.ui.analysis_page import (
    _column_pier_check_decision_rows,
    _column_pier_combined_vt_check_dataframe,
    _column_pier_combined_vt_controlling_cause,
    _column_pier_combined_vt_governing_tie_info,
    _column_pier_combined_vt_screen_dataframe,
)


def _analysis_input() -> AnalysisInput:
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
        prestress_elements=[],
        load_cases=[LoadCase(name="ULS-VT", Pu_N=1_200_000.0, Mux_Nmm=0.0, Muy_Nmm=0.0, load_type="ULS")],
        settings=AnalysisSettings(code=PROJECT_CODE_AASHTO_LRFD, transverse_reinforcement="tied"),
    )


def _state(*, tu_kNm: float = 50.0, spacing_mm: float = 100.0) -> dict[str, object]:
    return {
        "project_design_code": PROJECT_CODE_AASHTO_LRFD,
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "design_code": "ACI 318",  # stale widget key must not control routing
        "code_edition": "ACI 318-19",
        "column_uls_loads_table": [
            {
                "Active": True,
                "Case Name": "ULS-VT",
                "Pu": 1_200.0,
                "Mux": 120.0,
                "Muy": 60.0,
                "Vux": 80.0,
                "Vuy": 50.0,
                "Tu": tu_kNm,
                "Note": "AASHTO.COL.VT1 regression",
            }
        ],
        "column_pier_transverse_reinforcement_settings": {
            "closed_tie_layout": "Closed ties / hoops",
            "torsion_core_basis": "Auto from section and tie offset",
            "tie_center_offset_mm": 50.0,
        },
        "column_pier_transverse_reinforcement_table": [
            {
                "Active": True,
                "Zone": "Control section",
                "x_start_m": 0.0,
                "x_end_m": 1.0,
                "Bar Size": "DB16",
                "Diameter_mm": 16.0,
                "Legs": 4.0,
                "Spacing_mm": spacing_mm,
                "fy_MPa": 420.0,
                "Note": "closed control section hoop",
            }
        ],
        "rebars": _analysis_input().rebars,
    }


def test_aashto_vt1_helper_combines_source_demands_in_si() -> None:
    vt = aashto_combined_shear_torsion_result(
        vu_N=80_000.0,
        tu_Nmm=50.0e6,
        phi=0.90,
        vc_N=250_000.0,
        phi_vn_N=500_000.0,
        phi_tn_Nmm=70.0e6,
        bv_mm=600.0,
        dv_mm=320.0,
        Ao_mm2=127_500.0,
        ph_mm=1_600.0,
        fy_MPa=420.0,
        avs_provided_mm2_per_mm=8.0,
        at_provided_mm2_per_mm=2.0,
        avs_minimum_mm2_per_mm=0.5,
    )

    assert vt.phi == pytest.approx(0.90)
    assert vt.theta_deg == pytest.approx(45.0)
    assert vt.torsion_required_mm2_per_mm > 0.0
    assert vt.combined_transverse_required_mm2_per_mm == pytest.approx(
        vt.shear_required_mm2_per_mm + 2.0 * vt.torsion_required_mm2_per_mm
    )
    assert vt.provided_av_plus_2at_mm2_per_mm == pytest.approx(12.0)
    assert "5.7.3.6.1" in vt.basis


def test_aashto_vt1_dataframe_routes_to_aashto_not_aci() -> None:
    vt_df = _column_pier_combined_vt_check_dataframe(_state(), _analysis_input())

    active = vt_df[vt_df["Status"].astype(str) != "NOT APPLICABLE"]
    assert not active.empty
    assert active["Code basis"].eq("AASHTO LRFD 9th Column/Pier V+T").all()
    assert not active["Notes"].str.contains("ACI 318", case=False, na=False).any()
    assert active["Interaction form"].str.contains("AASHTO 5.7.3.6.1", regex=False).all()
    assert set(active["Status"]).issubset({"PASS", "FAIL", "REVIEW", "DATA REQUIRED"})
    assert active["Provided Av+2At per s mm2/mm"].astype(float).gt(0.0).all()


def test_aashto_vt1_directional_mapping_uses_vux_and_vuy_independently() -> None:
    state = _state(spacing_mm=300.0)
    state["column_uls_loads_table"][0]["Vux"] = 20.0
    state["column_uls_loads_table"][0]["Vuy"] = 400.0
    vt_df = _column_pier_combined_vt_check_dataframe(state, _analysis_input())
    active = vt_df[vt_df["Status"].astype(str) != "NOT APPLICABLE"]
    by_direction = {row["Direction"]: row for _, row in active.iterrows()}

    assert by_direction["Vux"]["Vu kN"] == pytest.approx(20.0)
    assert by_direction["Vuy"]["Vu kN"] == pytest.approx(400.0)
    assert float(by_direction["Vuy"]["Stress D/C value"]) > float(by_direction["Vux"]["Stress D/C value"])
    assert float(by_direction["Vuy"]["Overall D/C value"]) > float(by_direction["Vux"]["Overall D/C value"])




def test_aashto_vt2_asymmetric_vu_tu_demands_change_dc_and_governing_row() -> None:
    state = _state(spacing_mm=300.0)
    state["column_uls_loads_table"] = [
        {
            "Active": True,
            "Case Name": "ULS-A",
            "Pu": 1_200.0,
            "Mux": 120.0,
            "Muy": 60.0,
            "Vux": 20.0,
            "Vuy": 800.0,
            "Tu": 50.0,
            "Note": "asymmetric lower torsion",
        },
        {
            "Active": True,
            "Case Name": "ULS-B",
            "Pu": 1_200.0,
            "Mux": 120.0,
            "Muy": 60.0,
            "Vux": 800.0,
            "Vuy": 20.0,
            "Tu": 120.0,
            "Note": "asymmetric higher torsion",
        },
    ]

    vt_df = _column_pier_combined_vt_check_dataframe(state, _analysis_input())
    active = vt_df[vt_df["Status"].astype(str) != "NOT APPLICABLE"]
    by_key = {(row["Case"], row["Direction"]): row for _, row in active.iterrows()}

    assert float(by_key[("ULS-A", "Vuy")]["Overall D/C value"]) > float(by_key[("ULS-A", "Vux")]["Overall D/C value"])
    assert float(by_key[("ULS-B", "Vux")]["Overall D/C value"]) > float(by_key[("ULS-B", "Vuy")]["Overall D/C value"])
    assert float(by_key[("ULS-B", "Vux")]["Overall D/C value"]) > float(by_key[("ULS-A", "Vuy")]["Overall D/C value"])

    tie_info = _column_pier_combined_vt_governing_tie_info(vt_df)
    assert tie_info["count"] == 1
    assert tie_info["rows"] == ["ULS-B / Vux"]


def test_aashto_vt2_controlling_cause_reports_torsion_source_failure() -> None:
    vt_df = _column_pier_combined_vt_check_dataframe(_state(spacing_mm=100.0, tu_kNm=50.0), _analysis_input())

    cause = _column_pier_combined_vt_controlling_cause(vt_df)

    assert cause.startswith("Controlling cause:")
    assert "source torsion strength" in cause


def test_aashto_vt2_seismic_scope_guard_is_warning_not_failure_alert() -> None:
    source = __import__("pathlib").Path("concrete_pmm_pro/ui/analysis_page.py").read_text()
    warning_snippet = (
        "st.warning(\n"
        "            \"Seismic confinement/detailing review remains separate: this V+T gate uses the Control section transverse row only \""
    )
    error_snippet = (
        "st.error(\n"
        "            \"Seismic confinement/detailing review remains separate: this V+T gate uses the Control section transverse row only \""
    )

    assert warning_snippet in source
    assert error_snippet not in source

def test_aashto_vt1_governing_tie_info_reports_tied_rows_for_summary_card() -> None:
    state = _state()
    state["column_uls_loads_table"] = [
        {
            "Active": True,
            "Case Name": "ULS-01",
            "Pu": 1_200.0,
            "Mux": 120.0,
            "Muy": 60.0,
            "Vux": 50.0,
            "Vuy": 50.0,
            "Tu": 50.0,
            "Note": "tie row 1",
        },
        {
            "Active": True,
            "Case Name": "ULS-02",
            "Pu": 1_200.0,
            "Mux": 120.0,
            "Muy": 60.0,
            "Vux": 50.0,
            "Vuy": 50.0,
            "Tu": 50.0,
            "Note": "tie row 2",
        },
    ]
    vt_df = _column_pier_combined_vt_check_dataframe(state, _analysis_input())
    tie_info = _column_pier_combined_vt_governing_tie_info(vt_df)

    assert tie_info["count"] == 4
    assert "Tied governing rows: 4" in str(tie_info["label"])
    assert "ULS-01 / Vux" in tie_info["rows"]
    assert "ULS-02 / Vuy" in tie_info["rows"]


def test_aashto_vt1_screen_dataframe_keeps_method_details_out_of_main_table() -> None:
    vt_df = _column_pier_combined_vt_check_dataframe(_state(), _analysis_input())
    screen = _column_pier_combined_vt_screen_dataframe(vt_df)

    assert list(screen.columns) == ["Status", "Case", "Dir", "Vu", "Tu", "Stress", "Transv.", "Long. Al", "Source", "D/C"]
    assert "Interaction form" not in screen.columns
    assert screen["D/C"].ne("-").all()


def test_aashto_vt1_decision_view_no_longer_says_not_implemented() -> None:
    rows = _column_pier_check_decision_rows(_state(), _analysis_input())
    vt_row = next(row for row in rows if row["Check"] == "Shear + Torsion")

    assert "not implemented" not in vt_row["Route / Scope"].lower()
    assert "AASHTO LRFD 9th Section 5.7.3.6" in vt_row["Route / Scope"]


def test_aashto_vt1_threshold_row_uses_source_shear_gate() -> None:
    vt_df = _column_pier_combined_vt_check_dataframe(_state(tu_kNm=0.01), _analysis_input())
    active = vt_df[vt_df["Status"].astype(str) != "NOT APPLICABLE"]

    assert not active.empty
    assert active["Source torsion status"].eq("BELOW THRESHOLD").all()
    assert active["Interaction form"].eq("torsion below threshold").all()
