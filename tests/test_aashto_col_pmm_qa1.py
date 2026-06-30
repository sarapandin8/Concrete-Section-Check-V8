from __future__ import annotations

import math

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.pmm_solver import run_aashto_lrfd_column_pmm_solver, run_pmm_solver, run_rc_pmm_solver
from concrete_pmm_pro.analysis.result_models import pmm_result_to_display_dataframe, summarize_pmm_result
from concrete_pmm_pro.code_checks import aashto_max_phiPn, aashto_nominal_po_rc_prestressed
from concrete_pmm_pro.core.analysis import AnalysisInput, AnalysisSettings
from concrete_pmm_pro.core.design_code import PROJECT_CODE_AASHTO_LRFD
from concrete_pmm_pro.core.models import ConcreteMaterial, LoadCase, PrestressElement, Rebar, RebarMaterial
from concrete_pmm_pro.geometry.generators import rectangle
from concrete_pmm_pro.ui.analysis_page import (
    _column_pier_check_decision_rows,
    _column_pier_decision_caption_for_code,
    _column_pier_uls_decision_summary_cards,
)


def _qa_column_input(
    *,
    code: str = "AASHTO LRFD",
    with_prestress: bool = False,
    fc_mpa: float = 48.0,
    angle_steps: int = 16,
    depth_steps: int = 28,
) -> AnalysisInput:
    prestress_elements: list[PrestressElement] = []
    if with_prestress:
        prestress_elements = [
            PrestressElement(
                x_mm=-80.0,
                y_mm=-230.0,
                area_mm2=140.0,
                steel_type="strand",
                pe_eff_n=105_000.0,
                initial_stress_mpa=750.0,
                fpy_mpa=1670.0,
                fpu_mpa=1860.0,
                ep_mpa=195000.0,
                bonded=True,
                count=3,
                label="PS-L",
            ),
            PrestressElement(
                x_mm=80.0,
                y_mm=230.0,
                area_mm2=140.0,
                steel_type="strand",
                pe_eff_n=0.0,
                initial_stress_mpa=0.0,
                fpy_mpa=1670.0,
                fpu_mpa=1860.0,
                ep_mpa=195000.0,
                bonded=True,
                count=2,
                label="PS-PASSIVE",
            ),
        ]
    return AnalysisInput(
        section_geometry=rectangle(width_mm=520.0, height_mm=760.0),
        concrete_material=ConcreteMaterial(name="C48", fc_MPa=fc_mpa, ecu=0.003),
        rebar_materials=[RebarMaterial(name="SD40", fy_MPa=420.0, Es_MPa=200000.0)],
        rebars=[
            Rebar(x_mm=-210.0, y_mm=-320.0, diameter_mm=28.0, material_name="SD40", label="B1"),
            Rebar(x_mm=210.0, y_mm=-320.0, diameter_mm=28.0, material_name="SD40", label="B2"),
            Rebar(x_mm=210.0, y_mm=320.0, diameter_mm=28.0, material_name="SD40", label="B3"),
            Rebar(x_mm=-210.0, y_mm=320.0, diameter_mm=28.0, material_name="SD40", label="B4"),
        ],
        prestress_elements=prestress_elements,
        load_cases=[LoadCase(name="ULS-QA", Pu_N=1_800_000.0, Mux_Nmm=250_000_000.0, Muy_Nmm=80_000_000.0, load_type="ULS")],
        settings=AnalysisSettings(
            code=code,
            transverse_reinforcement="tied",
            neutral_axis_angle_steps=angle_steps,
            neutral_axis_depth_steps=depth_steps,
        ),
    )


def test_aashto_col_pmm_qa1_result_has_stable_si_numeric_surface() -> None:
    result = run_aashto_lrfd_column_pmm_solver(_qa_column_input())
    summary = summarize_pmm_result(result)
    display_df = pmm_result_to_display_dataframe(result)

    assert summary["point_count"] == 16 * 28
    assert summary["has_nan"] is False
    assert summary["has_inf"] is False
    assert summary["phi_min"] == pytest.approx(0.75)
    assert summary["phi_max"] <= 0.90
    assert not display_df.empty
    assert {"Pn_kN", "phiPn_kN", "Mnx_kNm", "Mny_kNm", "phiMnx_kNm", "phiMny_kNm"}.issubset(display_df.columns)
    assert pd.to_numeric(display_df["phiPn_capped_kN"], errors="coerce").notna().all()


def test_aashto_col_pmm_qa1_phi_is_applied_consistently_to_p_and_m() -> None:
    result = run_aashto_lrfd_column_pmm_solver(_qa_column_input(with_prestress=True))

    assert result.points
    assert max(point.phi for point in result.points) == pytest.approx(1.0)
    for point in result.points:
        assert point.phiPn_N == pytest.approx(point.phi * point.Pn_N)
        assert point.phiMnx_Nmm == pytest.approx(point.phi * point.Mnx_Nmm)
        assert point.phiMny_Nmm == pytest.approx(point.phi * point.Mny_Nmm)
        if point.phiPn_capped_N is not None:
            assert point.phiPn_capped_N <= max(point.phiPn_N, point.phiPn_capped_N) + 1.0e-6


def test_aashto_col_pmm_qa1_axial_cap_matches_aashto_helper() -> None:
    analysis_input = _qa_column_input(with_prestress=True)
    result = run_aashto_lrfd_column_pmm_solver(analysis_input)
    expected_po = aashto_nominal_po_rc_prestressed(
        analysis_input.concrete_material.fc_MPa,
        520.0 * 760.0,
        analysis_input.rebars,
        analysis_input.rebar_materials[0],
        analysis_input.prestress_elements,
    )
    expected_cap = aashto_max_phiPn(expected_po, transverse_reinforcement="tied", phi_compression=0.75)

    compression_points = [point for point in result.points if point.phiPn_N > 0.0]
    assert compression_points
    assert all(point.phiPn_capped_N is not None for point in compression_points)
    assert max(point.phiPn_capped_N or 0.0 for point in compression_points) <= expected_cap + 1.0e-6
    assert any(f"capped max phiPn = {expected_cap:,.1f} N" in info for info in result.info)


def test_aashto_col_pmm_qa1_route_is_not_aci_when_code_is_aashto() -> None:
    aashto_input = _qa_column_input(code="AASHTO LRFD", fc_mpa=80.0)
    aci_input = aashto_input.model_copy(update={"settings": aashto_input.settings.model_copy(update={"code": "ACI 318"})})

    routed = run_pmm_solver(aashto_input)
    explicit_aashto = run_aashto_lrfd_column_pmm_solver(aashto_input)
    explicit_aci = run_rc_pmm_solver(aci_input)

    assert [point.phi for point in routed.points] == [point.phi for point in explicit_aashto.points]
    assert any("AASHTO LRFD 9th Column/Pier PMM route" in item for item in routed.info)
    assert not any("ACI maximum axial strength cap" in item for item in routed.info)
    assert any(
        not math.isclose(a.Pn_N, b.Pn_N, rel_tol=1.0e-9, abs_tol=1.0e-3)
        for a, b in zip(explicit_aashto.points, explicit_aci.points, strict=True)
    )


def test_aashto_col_pmm_qa1_decision_view_does_not_label_guarded_checks_as_aci_routes() -> None:
    analysis_input = _qa_column_input(with_prestress=True)
    state = {
        "project_design_code": PROJECT_CODE_AASHTO_LRFD,
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "design_code": "ACI 318",  # stale legacy/widget key must not leak into decision text
        "code_edition": "ACI 318-19",
        "column_pier_uls_load_rows": [],
        "rebars": analysis_input.rebars,
    }

    rows = _column_pier_check_decision_rows(state, analysis_input)
    cards = _column_pier_uls_decision_summary_cards(rows, analysis_input, state)
    route_text = " | ".join(str(row["Route / Scope"]) for row in rows)

    assert "AASHTO LRFD 9th PMM" in route_text
    assert "AASHTO LRFD 9th Section 5.7 simplified shear route" in route_text
    assert "AASHTO LRFD 9th Section 5.7.3.6 scoped torsion gate" in route_text
    assert "AASHTO LRFD 9th Section 5.7.3.6 scoped nonprestressed V+T gate" in route_text
    assert "ACI 318 RC scoped shear gate" not in route_text
    assert cards[1]["value"] == PROJECT_CODE_AASHTO_LRFD
    assert "AASHTO PMM" in str(cards[1]["detail"])
    assert "AASHTO V+T" in str(cards[2]["detail"])


def test_aashto_col_pmm_qa1_caption_is_code_specific() -> None:
    aashto_caption = _column_pier_decision_caption_for_code("AASHTO LRFD")
    aci_caption = _column_pier_decision_caption_for_code("ACI 318")

    assert "AASHTO LRFD 9th PMM interaction" in aashto_caption
    assert "AASHTO Section 5.7 simplified shear" in aashto_caption
    assert "torsion, and combined V+T" in aashto_caption
    assert "scoped ACI RC shear" in aci_caption
