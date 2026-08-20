import math

from concrete_pmm_pro.analysis.igird_interface_shear import (
    DEFAULT_PHI_SHEAR,
    INTERFACE_FY_CAP_MPA,
    KSI_TO_MPA,
    MIN_REINF_COEFF_MPA,
    ROUGHENED_WAIVER_STRESS_MPA,
    SURFACE_ROUGHENED_GIRDER_SLAB,
    interface_shear_demand_si,
    interface_shear_resistance_si,
    minimum_interface_reinforcement_si,
    provided_interface_reinforcement_mm2_per_m,
    source_unit_trace,
)


def test_aashto_us_constants_are_explicitly_converted_to_mpa():
    trace = source_unit_trace(SURFACE_ROUGHENED_GIRDER_SLAB)
    assert math.isclose(trace["c_internal_MPa"], 0.28 * KSI_TO_MPA, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(trace["K2_internal_MPa"], 1.8 * KSI_TO_MPA, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(INTERFACE_FY_CAP_MPA, 60.0 * KSI_TO_MPA, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(MIN_REINF_COEFF_MPA, 0.05 * KSI_TO_MPA, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(ROUGHENED_WAIVER_STRESS_MPA, 0.210 * KSI_TO_MPA, rel_tol=0.0, abs_tol=1e-12)


def test_interface_demand_si_matches_aashto_5745_dimensionally():
    result = interface_shear_demand_si(vu_kN=1000.0, bvi_mm=1000.0, dv_mm=1800.0)
    assert math.isclose(result["vui_MPa"], 1000.0 * 1000.0 / (1000.0 * 1800.0), rel_tol=1e-12)
    assert math.isclose(result["Vui_kN_per_m"], result["vui_MPa"] * 1000.0, rel_tol=1e-12)


def test_interface_resistance_honors_60_ksi_fy_cap_and_one_meter_strip():
    avf = provided_interface_reinforcement_mm2_per_m(bar_area_mm2=math.pi * 12.0**2 / 4.0, legs=2.0, spacing_mm=150.0)
    r_hi = interface_shear_resistance_si(
        bvi_mm=1000.0, fc_weaker_MPa=35.0, avf_provided_mm2_per_m=avf, fy_MPa=500.0,
        surface_key=SURFACE_ROUGHENED_GIRDER_SLAB,
    )
    r_cap = interface_shear_resistance_si(
        bvi_mm=1000.0, fc_weaker_MPa=35.0, avf_provided_mm2_per_m=avf, fy_MPa=INTERFACE_FY_CAP_MPA,
        surface_key=SURFACE_ROUGHENED_GIRDER_SLAB,
    )
    assert math.isclose(r_hi["fy_used_MPa"], INTERFACE_FY_CAP_MPA, rel_tol=1e-12)
    assert math.isclose(r_hi["Vri_N"], r_cap["Vri_N"], rel_tol=1e-12)
    assert math.isclose(r_hi["Acv_mm2_per_m"], 1_000_000.0, rel_tol=1e-12)


def test_minimum_reinforcement_equation_is_si_equivalent():
    bvi = 1000.0
    fy = 390.0
    result = minimum_interface_reinforcement_si(
        bvi_mm=bvi, fy_MPa=fy, demand_Vui_N_per_m=10_000_000.0,
        c_MPa=0.28 * KSI_TO_MPA, mu=1.0,
    )
    expected = (0.05 * KSI_TO_MPA) * (bvi * 1000.0) / fy
    assert math.isclose(result["Avf_min_eq_mm2_per_m"], expected, rel_tol=1e-12)
    assert result["Avf_min_required_mm2_per_m"] <= result["Avf_min_eq_mm2_per_m"] + 1e-9


def test_resistance_caps_are_applied():
    r = interface_shear_resistance_si(
        bvi_mm=1000.0, fc_weaker_MPa=35.0, avf_provided_mm2_per_m=1_000_000.0, fy_MPa=390.0,
        surface_key=SURFACE_ROUGHENED_GIRDER_SLAB,
    )
    assert math.isclose(r["Vni_N"], min(r["Vni_base_N"], r["Vni_cap_fc_N"], r["Vni_cap_k2_N"]), rel_tol=1e-12)
    assert math.isclose(r["Vri_N"], DEFAULT_PHI_SHEAR * r["Vni_N"], rel_tol=1e-12)



def test_full_aashto_interface_example_is_numerically_equivalent_in_us_and_si_units():
    """Protect the SI solver against accidentally treating ksi constants as MPa."""
    kip_to_n = 4448.2216152605
    inch_to_mm = 25.4

    # One identical 1.0 m interface strip expressed in both unit systems.
    bvi_mm = 1000.0
    lvi_mm = 1000.0
    dv_mm = 1800.0
    vu_kn = 1000.0
    fc_mpa = 35.0
    avf_mm2 = 1500.0
    fy_mpa = 390.0

    bvi_in = bvi_mm / inch_to_mm
    lvi_in = lvi_mm / inch_to_mm
    dv_in = dv_mm / inch_to_mm
    vu_kip = vu_kn * 1000.0 / kip_to_n
    fc_ksi = fc_mpa / KSI_TO_MPA
    avf_in2 = avf_mm2 / (inch_to_mm**2)
    fy_ksi = fy_mpa / KSI_TO_MPA
    acv_in2 = bvi_in * lvi_in

    # AASHTO 5.7.4.5 demand in US customary units.
    vui_ksi_us = vu_kip / (bvi_in * dv_in)
    vui_mpa_us_converted = vui_ksi_us * KSI_TO_MPA
    demand_si = interface_shear_demand_si(vu_kN=vu_kn, bvi_mm=bvi_mm, dv_mm=dv_mm)
    assert math.isclose(demand_si["vui_MPa"], vui_mpa_us_converted, rel_tol=2e-12, abs_tol=1e-12)

    # AASHTO 5.7.4.3 nominal resistance and caps in US customary units.
    fy_used_ksi = min(fy_ksi, 60.0)
    vni_base_kip_us = 0.28 * acv_in2 + 1.0 * (avf_in2 * fy_used_ksi)
    vni_fc_cap_kip_us = 0.30 * fc_ksi * acv_in2
    vni_k2_cap_kip_us = 1.80 * acv_in2
    vni_kip_us = min(vni_base_kip_us, vni_fc_cap_kip_us, vni_k2_cap_kip_us)
    vri_n_us_converted = DEFAULT_PHI_SHEAR * vni_kip_us * kip_to_n

    resistance_si = interface_shear_resistance_si(
        bvi_mm=bvi_mm,
        fc_weaker_MPa=fc_mpa,
        avf_provided_mm2_per_m=avf_mm2,
        fy_MPa=fy_mpa,
        surface_key=SURFACE_ROUGHENED_GIRDER_SLAB,
    )
    assert math.isclose(resistance_si["Vri_N"], vri_n_us_converted, rel_tol=2e-12, abs_tol=1e-6)
