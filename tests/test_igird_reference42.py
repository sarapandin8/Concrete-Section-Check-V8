"""Independent identities/integrals plus explicit reference-validation limits."""
from dataclasses import replace
import math
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.optimize import brentq, root

from concrete_pmm_pro.analysis import igird_reference42 as r


@pytest.fixture
def section():
    return r.RectangularRC(254, 381, 216, 343, 1136, 1.016)


@pytest.fixture
def material():
    return r.RCMaterial(28.1, .00197, 327.6, 320)


@pytest.fixture(scope="module")
def curve():
    return r.trace_postcracking(r.RectangularRC(254, 381, 216, 343, 1136, 1.016),
                              r.RCMaterial(28.1, .00197, 327.6, 320), steps=70)


@pytest.mark.parametrize("strain", [0., .00002, .000116, .0003, .002, .01])
def test_average_tension_against_independent_numerical_integral(strain):
    ec, f = .000116, 3.45
    if not strain:
        expected = 0.
    else:
        def point_stress(e):
            return f / ec * e if e <= ec else f * (ec / e)**.4
        expected = quad(point_stress, 0, strain, points=[ec] if ec < strain else None, epsabs=1e-12)[0] / strain
    assert r.average_tension_MPa(strain, f, ec) == pytest.approx(expected, rel=1e-10, abs=1e-12)


@pytest.mark.parametrize("beta", [.2, .5, .9])
@pytest.mark.parametrize("strain", [0., .00002, .0005, .0018, .0035])
def test_average_compression_against_independent_numerical_integral(beta, strain):
    fc, eo = 28.1, .002
    peak = beta * eo
    def point_stress(e):
        if e <= peak:
            return beta * fc * (2 * e / peak - (e / peak)**2)
        return beta * fc * (1 - ((e - peak) / (2 * eo - peak))**2)
    expected = quad(point_stress, 0, strain, points=[peak] if peak < strain else None, epsabs=1e-12)[0] / strain if strain else 0.
    assert r.average_compression_MPa(strain, fc, eo, beta) == pytest.approx(expected, rel=1e-11, abs=1e-12)


def test_pinned_material_profile_does_not_silently_substitute_table2(material):
    assert material.concrete_tension_E_MPa == pytest.approx(3875 * 1.45 * math.sqrt(28.1))
    assert material.cracking_stress_MPa == pytest.approx(material.concrete_tension_E_MPa * material.cracking_strain)
    assert material.cracking_stress_MPa != pytest.approx(2.22)


def test_hoop_perimeter_and_units_are_not_outer_perimeter(section):
    assert section.hoop_perimeter_mm == 1118
    assert section.rho_l == pytest.approx(1136 / (254 * 381))
    assert section.rho_t == pytest.approx(1.016 * 1118 / (254 * 381))
    assert section.rho_t != pytest.approx(1.016 * 1270 / (254 * 381))


def test_condensed_kinematics_against_original_uncancelled_equations(section, material):
    q = r.state_from_steel_strains(section, material, surface_compression=.002,
                                  longitudinal_strain=.0014, transverse_strain=.0021)
    alpha, tc, ao, po = q.strut_angle_rad, q.wall_depth_mm, q.shear_flow_area_mm2, q.shear_flow_perimeter_mm
    sc, st = q.concrete_compression_MPa, q.concrete_tension_MPa
    # Direct force triangles and original Eqs. 28, 43, 56-58, not the condensed g quadratic.
    C = sc * tc * math.cos(alpha)  # take dv=1 mm
    T = st * tc * math.sin(alpha)
    resultant = math.hypot(C, T)
    beta_angle = math.atan2(T, C)
    gamma = alpha + beta_angle
    torque = 2 * ao * resultant * math.sin(gamma)
    et = (ao**2 * sc * math.sin(gamma) / (po * torque * math.cos(beta_angle) * math.tan(alpha) * math.sin(alpha)) - .5) * .002
    el = (ao**2 * sc * math.sin(gamma) / (po * torque * math.cos(beta_angle) / math.tan(alpha) * math.sin(alpha)) - .5) * .002
    assert q.torque_Nmm == pytest.approx(torque, rel=1e-13)
    assert q.transverse_strain == pytest.approx(et, rel=1e-13)
    assert q.longitudinal_strain == pytest.approx(el, rel=1e-13)
    assert q.twist_rad_per_mm == pytest.approx(.002 / (2 * tc * math.sin(alpha) * math.cos(alpha)))
    # Eq. 59 and Mohr circle plus Bredt compatibility, independently.
    assert q.concrete_tie_surface_strain == pytest.approx(2 * (el + et) + .002)
    shear_strain = 2 * (et + .002 / 2) * math.tan(alpha)
    assert q.twist_rad_per_mm == pytest.approx(po * shear_strain / (2 * ao), rel=1e-13)


def test_nonlinear_solution_against_independent_three_variable_root(section, material):
    # Solve directly for alpha, t, e1s with force transformation and Mohr strains.
    # No call to the production residual / condensed wall-thickness formula.
    e2 = .002
    def direct(v, details=False):
        alpha, tc, e1s = v
        c, s = math.cos(alpha), math.sin(alpha)
        ao, po = (254 - tc) * (381 - tc), 2 * (254 + 381 - 2 * tc)
        el = e1s / 2 * s*s - e2 / 2 * c*c
        et = e1s / 2 * c*c - e2 / 2 * s*s
        eta = section.rho_l * 327.6 / (section.rho_t * 320)
        be = .9 / math.sqrt(1 + 400 * e1s / 2 / min(eta, 1 / eta))
        sc = r.average_compression_MPa(e2, 28.1, .00197, be)
        st = r.average_tension_MPa(e1s, material.cracking_stress_MPa, material.cracking_strain)
        fl = r.steel_tension_MPa(el, 200000, 327.6, section.rho_l, material.cracking_stress_MPa)
        ft = r.steel_tension_MPa(et, 200000, 320, section.rho_t, material.cracking_stress_MPa)
        beta_angle = math.atan2(st*s, sc*c)
        tan_beta = math.tan(beta_angle)
        F = 1.016*ft*po/(1136*fl)
        alpha_from_published_49 = math.atan(math.sqrt(F*F*tan_beta*tan_beta + F*tan_beta**4 + F + tan_beta*tan_beta) / (F*tan_beta*tan_beta+1))
        residual = [1136 * fl / (po * tc) - sc * c*c + st * s*s,
                    28.1 * (alpha-alpha_from_published_49),
                    1000 * (po / (2 * ao) * (e1s + e2) * s * c - e2 / (2 * tc * s * c))]
        return (residual, el, et) if details else residual
    fit = root(direct, [.78, 55., .007])
    assert fit.success
    independent, el, et = direct(fit.x, True)
    q = r.solve_state(section, material, e2)
    assert max(abs(v) for v in independent) < 1e-8
    assert [q.strut_angle_rad, q.wall_depth_mm] == pytest.approx(fit.x[:2], rel=1e-8)
    assert [q.longitudinal_strain, q.transverse_strain] == pytest.approx([el, et], rel=1e-8)


def test_solved_forces_satisfy_original_force_triangle_equilibrium(section, material):
    q = r.solve_state(section, material, .002)
    a, t = q.strut_angle_rad, q.wall_depth_mm
    C = q.concrete_compression_MPa * t * math.cos(a)
    T = q.concrete_tension_MPa * t * math.sin(a)
    beta_angle = math.atan2(T, C)
    gamma, gamma_prime = a+beta_angle, a-beta_angle
    predicted_long = q.torque_Nmm*q.shear_flow_perimeter_mm/(2*q.shear_flow_area_mm2)/math.tan(gamma)
    predicted_trans_per_length = q.torque_Nmm/(2*q.shear_flow_area_mm2)*math.tan(gamma_prime)
    assert section.longitudinal_area_mm2*q.longitudinal_stress_MPa == pytest.approx(predicted_long, rel=1e-9)
    assert section.transverse_one_leg_area_per_spacing_mm*q.transverse_stress_MPa == pytest.approx(predicted_trans_per_length, rel=1e-9)


def test_balanced_case_has_45_degree_struts():
    # Equal reinforcement ratios alone do not imply equal normal steel forces:
    # the printed hoop perimeter and evolving shear-flow perimeter differ.
    # Construct a genuinely balanced state with both perimeters equal here.
    m = r.RCMaterial(30., .002, 390., 390.)
    el, e2 = .0016, .002
    g = e2 / (el + e2/2)
    tc = min(np.roots([4+g, -(2+g)*650, g*250*400]))
    po = 2*(650-2*tc)
    e1s = 4*el+e2
    beta = .9 / math.sqrt(1+400*e1s/2)
    sc = r.average_compression_MPa(e2, 30, .002, beta)
    st = r.average_tension_MPa(e1s, m.cracking_stress_MPa, m.cracking_strain)
    def force_balance(rho):
        fs = r.steel_tension_MPa(el, 200000, 390, rho, m.cracking_stress_MPa)
        return rho*100000*fs/(po*tc) - (sc-st)/2
    rho = brentq(force_balance, .001, .02, xtol=1e-15)
    al = rho*100000
    s = r.RectangularRC(250, 400, 250-tc, 400-tc, al, al/po)
    q = r.solve_state(s, m, .002)
    assert s.rho_l == pytest.approx(s.rho_t)
    assert q.longitudinal_strain == pytest.approx(q.transverse_strain, rel=1e-9)
    assert q.longitudinal_strain == pytest.approx(el, rel=1e-9)
    assert q.strut_angle_rad == pytest.approx(math.pi / 4, rel=1e-10)


def test_geometrically_similar_sections_scale_torque_and_twist(section, material):
    q = r.solve_state(section, material, .002)
    lam = 3.
    scaled = r.RectangularRC(254*lam, 381*lam, 216*lam, 343*lam, 1136*lam**2, 1.016*lam)
    other = r.solve_state(scaled, material, .002)
    assert other.torque_Nmm == pytest.approx(q.torque_Nmm * lam**3, rel=1e-9)
    assert other.twist_rad_per_mm == pytest.approx(q.twist_rad_per_mm / lam, rel=1e-9)
    assert other.wall_depth_mm == pytest.approx(q.wall_depth_mm * lam, rel=1e-9)


def test_cross_section_90_degree_rotation_preserves_reference(section, material):
    q = r.solve_state(section, material, .002)
    rotated = r.RectangularRC(381, 254, 343, 216, 1136, 1.016)
    other = r.solve_state(rotated, material, .002)
    assert other.torque_Nmm == pytest.approx(q.torque_Nmm, rel=1e-11)
    assert other.twist_rad_per_mm == pytest.approx(q.twist_rad_per_mm, rel=1e-11)


def test_curve_has_no_invented_origin_no_gaps_and_refined_interior_peak(curve):
    assert curve.branch_status == "NUMERICALLY_COMPLETE"
    assert curve.states[0].concrete_surface_strain == .0005
    assert curve.states[-1].concrete_surface_strain == .0035
    assert len(curve.states) == 70
    assert max(q.equilibrium_relative_residual for q in curve.states) < 1e-9
    assert curve.postcracking_peak.torque_Nmm >= max(q.torque_Nmm for q in curve.states)
    assert curve.production_accepted is False


def test_peak_is_stable_under_continuation_refinement(curve):
    finer = r.trace_postcracking(curve.section, curve.material, steps=135)
    assert finer.postcracking_peak.torque_Nmm == pytest.approx(curve.postcracking_peak.torque_Nmm, rel=1e-7)
    assert finer.postcracking_peak.twist_rad_per_mm == pytest.approx(curve.postcracking_peak.twist_rad_per_mm, rel=1e-5)


def _synthetic(curve, values):
    points = tuple(replace(curve.states[0], concrete_surface_strain=.001*(i+1),
                           twist_rad_per_mm=(i+1)*1e-6, torque_Nmm=float(t)) for i, t in enumerate(values))
    return replace(curve, states=points, postcracking_peak=max(points, key=lambda q: q.torque_Nmm))


def _inventory(curve):
    s = curve.section
    return {"c": 2*s.area_mm2, "l": 2*s.longitudinal_area_mm2, "t": 2*s.transverse_one_leg_area_per_spacing_mm}


def test_equal_twist_assembly_does_not_sum_independent_maxima(curve):
    a, b = _synthetic(curve, [1, 5, 3]), _synthetic(curve, [4, 2, 1])
    result = r.combine_at_common_twist([a, b], [r.CellResources("c", "l", "t")]*2, _inventory(curve))
    assert result.torque_Nmm == (5., 7., 4.)
    assert result.sampled_peak_Nmm == 7.
    assert result.sampled_peak_Nmm < 5 + 4
    assert result.production_accepted is False


@pytest.mark.parametrize("resource", ["c", "l", "t"])
def test_double_counted_concrete_or_steel_is_rejected(curve, resource):
    limits = _inventory(curve)
    limits[resource] /= 2
    with pytest.raises(r.ReferenceScopeError, match="available inventory"):
        r.combine_at_common_twist([curve, curve], [r.CellResources("c", "l", "t")]*2, limits)


def test_shared_twist_does_not_extrapolate_past_first_component_end(curve):
    a = _synthetic(curve, [1, 5, 3])
    b = _synthetic(curve, [4, 2, 1])
    b = replace(b, states=tuple(replace(q, twist_rad_per_mm=q.twist_rad_per_mm + .5e-6) for q in b.states))
    b = replace(b, postcracking_peak=b.states[0])
    result = r.combine_at_common_twist([a, b], [r.CellResources("c", "l", "t")]*2, _inventory(curve))
    assert result.twist_rad_per_mm[0] == 1.5e-6
    assert result.twist_rad_per_mm[-1] == 3e-6


def test_snapback_or_incomplete_branch_cannot_be_hidden_by_sorting(curve):
    a = _synthetic(curve, [1, 5, 3])
    bad = replace(a, states=(a.states[0], replace(a.states[1], twist_rad_per_mm=.5e-6), a.states[2]))
    with pytest.raises(r.ReferenceScopeError, match="Nonmonotonic"):
        r.combine_at_common_twist([bad, a], [r.CellResources("c", "l", "t")]*2, _inventory(curve))
    with pytest.raises(r.ReferenceScopeError, match="incomplete"):
        r.combine_at_common_twist([replace(a, branch_status="INCOMPLETE_BRANCH"), a], [r.CellResources("c", "l", "t")]*2, _inventory(curve))


@pytest.mark.parametrize("bad", [True, None, float("nan"), float("inf"), -1, 0])
def test_invalid_geometry_cannot_be_defaulted(bad):
    with pytest.raises(ValueError):
        r.RectangularRC(bad, 381, 216, 343, 1136, 1.016)


def test_actual_open_u_cannot_be_presented_as_closed_reference(section):
    with pytest.raises(r.ReferenceScopeError, match="open U"):
        replace(section, closed_cage=False)


def test_unsupported_material_branch_cannot_be_silently_repaired():
    with pytest.raises(r.ReferenceScopeError, match="exponent"):
        r.steel_tension_MPa(.002, 200000, 390, .1, 2.)
    with pytest.raises(r.ReferenceScopeError, match="compressive"):
        r.steel_tension_MPa(-.001, 200000, 390, .01, 3.5)


def test_precracking_compressive_steel_region_is_not_fabricated(section, material):
    with pytest.raises(r.ReferenceConvergenceError):
        r.solve_state(section, material, 1e-7)


def test_no_hidden_production_integration_or_certified_result_fields():
    assert r.PRODUCTION_VALIDATED is False
    assert r.PUBLISHED_REPRODUCTION_VALIDATED is False
    root_dir = Path(__file__).resolve().parents[1]
    ui = root_dir / "concrete_pmm_pro/ui"
    assert not any("igird_reference42" in p.read_text(encoding="utf-8") for p in ui.rglob("*.py"))
    assert not ({"Tn", "Vn", "phi_Tn", "phi_Vn", "accepted_Tn"} & set(r.ReferenceCurve.__dataclass_fields__))


def test_published_audit_keeps_all_cases_and_an_unmatched_gate_visible():
    from tools.run_igird_reference42 import audit
    summary, curves = audit(steps=50)
    expected = ["B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                "C4", "C5", "C6", "G3", "G4", "G5", "G7", "G8"]
    assert [q["specimen"] for q in summary["results"]] == expected
    assert summary["numerically_solved_cases"] == 16
    assert len(curves) == 16
    assert summary["published_reproduction_status"] == "NOT_REPRODUCED"
    assert summary["published_point_matches"] < 16
    assert summary["production_accepted"] is False
    assert all(q["production_accepted"] is False for q in summary["results"])
    for q in summary["results"]:
        if abs(q["torque_theory_relative_difference"]) > .01 or abs(q["twist_theory_relative_difference"]) > .01:
            assert q["status"] == "REFERENCE_MISMATCH"
