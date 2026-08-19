from __future__ import annotations

from pathlib import Path

import pytest

import concrete_pmm_pro.ui.analysis_page as analysis_page
from concrete_pmm_pro.analysis.pmm_solver import run_rc_pmm_solver
from concrete_pmm_pro.analysis.uls_strength_routing import beam_girder_uls_strength_route
from concrete_pmm_pro.core.analysis import AnalysisInput, AnalysisSettings
from concrete_pmm_pro.core.models import ConcreteMaterial, LoadCase, PrestressElement, Rebar, RebarMaterial
from concrete_pmm_pro.geometry.generators import rectangle

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")


def _prestressed_bridge_input() -> AnalysisInput:
    return AnalysisInput(
        section_geometry=rectangle(width_mm=500.0, height_mm=1000.0),
        concrete_material=ConcreteMaterial(name="C45", fc_MPa=45.0, ecu=0.003, beta1=0.80),
        rebar_materials=[RebarMaterial(name="SD40", fy_MPa=400.0, Es_MPa=200000.0)],
        rebars=[
            Rebar(x_mm=-180.0, y_mm=-420.0, diameter_mm=20.0, material_name="SD40"),
            Rebar(x_mm=180.0, y_mm=-420.0, diameter_mm=20.0, material_name="SD40"),
        ],
        prestress_elements=[
            PrestressElement(
                x_mm=0.0,
                y_mm=-400.0,
                area_mm2=140.0,
                steel_type="strand",
                fpy_mpa=1670.0,
                fpu_mpa=1860.0,
                ep_mpa=195000.0,
                pe_eff_n=140000.0,
                initial_stress_mpa=1000.0,
                bonded=True,
                count=8,
            )
        ],
        load_cases=[LoadCase(name="AUTO-CONSTRUCTION-ULS", Pu_N=0.0, Mux_Nmm=500_000_000.0, Muy_Nmm=0.0, load_type="ULS")],
        settings=AnalysisSettings(
            code="AASHTO LRFD 9th Edition",
            neutral_axis_angle_steps=12,
            neutral_axis_depth_steps=10,
            include_rebars=True,
            include_prestress=True,
            use_phi_factor=True,
        ),
    )


def test_igird_uls2p_nominal_capacity_reuses_same_pmm_cloud_with_equivalent_result() -> None:
    analysis_input = _prestressed_bridge_input()
    pmm = run_rc_pmm_solver(analysis_input)

    fast_nominal, fast_messages = analysis_page._beam_uls_nominal_flexure_capacity_from_pmm(
        pmm,
        analysis_input.load_cases,
    )
    legacy_nominal, _ = analysis_page._beam_uls_nominal_flexure_capacity_for_input(analysis_input)

    assert fast_nominal is not None and fast_nominal > 0.0
    assert legacy_nominal is not None and legacy_nominal > 0.0
    assert fast_nominal == pytest.approx(legacy_nominal, rel=1e-10, abs=1e-6)
    assert any("no duplicate neutral-axis sweep" in message for message in fast_messages)


def test_igird_uls2p_capacity_state_runs_rc_pmm_solver_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_input = _prestressed_bridge_input()
    route = beam_girder_uls_strength_route(
        is_bridge=True,
        is_building=False,
        project_design_code="AASHTO LRFD",
        code_edition="9th Edition",
    )
    calls = 0
    real_solver = analysis_page.run_rc_pmm_solver

    def counted_solver(value: AnalysisInput):
        nonlocal calls
        calls += 1
        return real_solver(value)

    monkeypatch.setattr(analysis_page, "run_rc_pmm_solver", counted_solver)
    solved = analysis_page._beam_uls_solve_flexure_capacity_state(analysis_input, strength_route=route)

    assert solved["state"] == "ok"
    assert calls == 1
    assert float(solved["nominal_capacity_nmm"]) > 0.0
    assert float(solved["routed_capacity_nmm"]) > 0.0


def test_igird_uls2p_construction_chart_uses_browser_plotly_not_kaleido_static_export() -> None:
    assert 'IGIRDER.ULS2P.flexure-performance-optimization' in ANALYSIS_SOURCE
    assert "def _render_beam_uls_browser_plotly_figure" in ANALYSIS_SOURCE
    assert '"staticPlot": True' in ANALYSIS_SOURCE
    construction_block = ANALYSIS_SOURCE.split('st.markdown("#### Construction Flexure — automatic noncomposite demand")', 1)[1]
    construction_block = construction_block.split("if active_df.empty:", 1)[0]
    assert "_render_beam_uls_browser_plotly_figure(" in construction_block
    assert "_render_beam_uls_static_plotly_figure(" not in construction_block
