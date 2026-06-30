from __future__ import annotations

import math

import pytest

from concrete_pmm_pro.analysis.pmm_solver import run_aashto_lrfd_column_pmm_solver, run_pmm_solver, run_rc_pmm_solver
from concrete_pmm_pro.code_checks import (
    AASHTO_ECU_STRENGTH,
    aashto_alpha1,
    aashto_beta1,
    aashto_compression_controlled_strain_limit,
    aashto_phi_and_strain_condition,
    aashto_tension_controlled_strain_limit,
)
from concrete_pmm_pro.core.aashto_units import ksi_to_mpa
from concrete_pmm_pro.core.analysis import AnalysisInput, AnalysisSettings
from concrete_pmm_pro.core.models import ConcreteMaterial, LoadCase, PrestressElement, Rebar, RebarMaterial
from concrete_pmm_pro.geometry.generators import rectangle


def _column_input(*, code: str = "AASHTO LRFD", with_prestress: bool = False, fc_mpa: float = 70.0) -> AnalysisInput:
    prestress = []
    if with_prestress:
        prestress = [
            PrestressElement(
                x_mm=0,
                y_mm=-210,
                area_mm2=140.0,
                steel_type="strand",
                pe_eff_n=120_000.0,
                initial_stress_mpa=900.0,
                fpy_mpa=1670.0,
                fpu_mpa=1860.0,
                ep_mpa=195000.0,
                bonded=True,
                count=4,
                label="PS-BONDED",
            )
        ]
    return AnalysisInput(
        section_geometry=rectangle(width_mm=450.0, height_mm=650.0),
        concrete_material=ConcreteMaterial(name="C", fc_MPa=fc_mpa, ecu=0.003, beta1=None),
        rebar_materials=[RebarMaterial(name="SD40", fy_MPa=420.0, Es_MPa=200000.0)],
        rebars=[
            Rebar(x_mm=-170.0, y_mm=-270.0, diameter_mm=25.0, material_name="SD40", label="B1"),
            Rebar(x_mm=170.0, y_mm=-270.0, diameter_mm=25.0, material_name="SD40", label="B2"),
            Rebar(x_mm=170.0, y_mm=270.0, diameter_mm=25.0, material_name="SD40", label="B3"),
            Rebar(x_mm=-170.0, y_mm=270.0, diameter_mm=25.0, material_name="SD40", label="B4"),
        ],
        prestress_elements=prestress,
        load_cases=[LoadCase(name="ULS-1", Pu_N=1_000_000.0, Mux_Nmm=120_000_000.0, Muy_Nmm=40_000_000.0, load_type="ULS")],
        settings=AnalysisSettings(code=code, neutral_axis_angle_steps=12, neutral_axis_depth_steps=20),
    )


def test_aashto_alpha1_beta1_use_ksi_breakpoints_from_si_input() -> None:
    assert aashto_alpha1(ksi_to_mpa(10.0)) == pytest.approx(0.85)
    assert aashto_alpha1(ksi_to_mpa(15.0)) == pytest.approx(0.75)
    assert aashto_beta1(ksi_to_mpa(4.0)) == pytest.approx(0.85)
    assert aashto_beta1(ksi_to_mpa(8.0)) == pytest.approx(0.65)


def test_aashto_strain_limits_match_lrfd_transition_basis() -> None:
    # 60 ksi reinforcement is capped at 0.002 compression-controlled strain.
    assert aashto_compression_controlled_strain_limit(ksi_to_mpa(60.0), 200000.0) == pytest.approx(0.002)
    assert aashto_compression_controlled_strain_limit(prestressed_reinforcement=True) == pytest.approx(0.002)
    assert aashto_tension_controlled_strain_limit(ksi_to_mpa(75.0)) == pytest.approx(0.005)
    assert aashto_tension_controlled_strain_limit(ksi_to_mpa(100.0)) == pytest.approx(0.008)
    assert aashto_tension_controlled_strain_limit(prestressed_reinforcement=True) == pytest.approx(0.005)


def test_aashto_phi_transition_nonprestressed_and_bonded_prestressed() -> None:
    rc = aashto_phi_and_strain_condition(0.006, fy_MPa=420.0, Es_MPa=200000.0, prestressed_member=False)
    ps = aashto_phi_and_strain_condition(0.006, fy_MPa=1670.0, Es_MPa=195000.0, prestressed_member=True)
    assert rc.phi == pytest.approx(0.90)
    assert ps.phi == pytest.approx(1.00)
    assert aashto_phi_and_strain_condition(0.0, fy_MPa=420.0, Es_MPa=200000.0).phi == pytest.approx(0.75)


def test_run_pmm_solver_routes_aashto_code_to_aashto_engine() -> None:
    aashto_result = run_pmm_solver(_column_input(code="AASHTO LRFD"))
    aci_result = run_pmm_solver(_column_input(code="ACI 318"))

    assert any("AASHTO LRFD 9th Column/Pier PMM route" in item for item in aashto_result.info)
    assert any("ACI maximum axial strength cap" in item for item in aci_result.info)
    assert min(point.phi for point in aashto_result.points) >= 0.75
    assert max(point.phi for point in aashto_result.points) <= 0.90
    assert min(point.phi for point in aci_result.points) < 0.75


def test_aashto_bonded_prestress_pmm_uses_prestressed_phi_and_si_stress_block() -> None:
    analysis_input = _column_input(with_prestress=True)
    result = run_aashto_lrfd_column_pmm_solver(analysis_input)

    assert result.points
    assert max(point.phi for point in result.points) == pytest.approx(1.0)
    assert any(point.active_prestress_count == 4 for point in result.points)
    assert any("alpha1/beta1 evaluated from fc in ksi then applied in SI" in item for item in result.info)
    assert any("AASHTO nominal Po" in item for item in result.info)
    assert all(point.phiPn_capped_N is not None for point in result.points)


def test_aashto_and_aci_routes_are_not_identical_for_high_strength_concrete() -> None:
    analysis_input = _column_input(code="AASHTO LRFD", fc_mpa=80.0)
    aashto = run_aashto_lrfd_column_pmm_solver(analysis_input)
    aci = run_rc_pmm_solver(analysis_input.model_copy(update={"settings": analysis_input.settings.model_copy(update={"code": "ACI 318"})}))

    assert len(aashto.points) == len(aci.points)
    assert any(
        not math.isclose(a.Pn_N, b.Pn_N, rel_tol=1e-6, abs_tol=1e-6)
        for a, b in zip(aashto.points, aci.points, strict=True)
    )
