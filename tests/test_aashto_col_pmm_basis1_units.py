import math

from concrete_pmm_pro.core.aashto_units import (
    KIP_TO_N,
    KSI_TO_MPA,
    aashto_sqrt_fc_stress_mpa,
    in2_to_mm2,
    inch_to_mm,
    kip_ft_to_n_mm,
    kip_in_to_n_mm,
    ksi_to_mpa,
    mpa_to_ksi,
    n_mm_to_kip_ft,
    n_mm_to_kip_in,
    si_coefficient_for_aashto_sqrt_fc_stress,
)


def test_basic_aashto_unit_roundtrips():
    assert math.isclose(ksi_to_mpa(1.0), KSI_TO_MPA, rel_tol=1.0e-12)
    assert math.isclose(mpa_to_ksi(KSI_TO_MPA), 1.0, rel_tol=1.0e-12)
    assert math.isclose(inch_to_mm(1.0), 25.4, rel_tol=1.0e-12)
    assert math.isclose(in2_to_mm2(1.0), 25.4 * 25.4, rel_tol=1.0e-12)


def test_aashto_sqrt_fc_stress_helper_evaluates_in_ksi_then_returns_mpa():
    fc_mpa = 34.473786465841805  # 5 ksi
    coefficient = 0.24
    expected = coefficient * math.sqrt(5.0) * KSI_TO_MPA
    assert math.isclose(aashto_sqrt_fc_stress_mpa(coefficient, fc_mpa), expected, rel_tol=1.0e-12)


def test_documented_si_sqrt_fc_coefficient_matches_explicit_ksi_route():
    fc_mpa = 45.0
    coefficient_ksi = 0.24
    explicit = aashto_sqrt_fc_stress_mpa(coefficient_ksi, fc_mpa)
    derived = si_coefficient_for_aashto_sqrt_fc_stress(coefficient_ksi) * math.sqrt(fc_mpa)
    assert math.isclose(explicit, derived, rel_tol=1.0e-12)


def test_moment_conversion_roundtrips_for_solver_internal_n_mm():
    one_kip_in = KIP_TO_N * 25.4
    assert math.isclose(kip_in_to_n_mm(1.0), one_kip_in, rel_tol=1.0e-12)
    assert math.isclose(n_mm_to_kip_in(one_kip_in), 1.0, rel_tol=1.0e-12)

    value_kip_ft = 123.45
    assert math.isclose(n_mm_to_kip_ft(kip_ft_to_n_mm(value_kip_ft)), value_kip_ft, rel_tol=1.0e-12)
