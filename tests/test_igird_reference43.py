"""Independent mechanics, source-domain checks and complete endpoint behavior."""
from dataclasses import replace
import math
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import root

from concrete_pmm_pro.analysis import igird_reference42 as previous
from concrete_pmm_pro.analysis import igird_reference43 as r


@pytest.fixture
def section():
    return r.RectangularRC(254, 381, 216, 343, 1136, 1.016)


@pytest.fixture
def material():
    return r.RCMaterial(28.1, .00197, 327.6, 320)


@pytest.fixture(scope="module")
def curve():
    return r.trace_curve(r.RectangularRC(254, 381, 216, 343, 1136, 1.016),
                         r.RCMaterial(28.1, .00197, 327.6, 320), steps=75)


def test_steel_source_psi_conversion_is_distinct_from_concrete_torsion_correction(material):
    # Hand conversion: 28.1 MPa = 4075.5611291966 psi. The coefficient
    # 3.75 has psi units; applying 3.75 directly to MPa is invalid.
    strength = r.steel_cracking_stress_MPa(material, r.MaterialProfile.SOURCE2012_STRICT)
    assert strength == pytest.approx(1.650607899117297, rel=1e-11)
    assert strength != pytest.approx(material.cracking_stress_MPa)
    assert strength != pytest.approx(3.75*math.sqrt(28.1))
    assert r.steel_cracking_stress_MPa(material, r.MaterialProfile.LEGACY42) == material.cracking_stress_MPa


def test_invalid_literal_exponent_is_rejected_by_default_and_extension_is_explicit(material):
    dense = r.RectangularRC(254, 254, 216, 216, 2039, 2.391)
    with pytest.raises(r.ReferenceScopeError, match="literal steel exponent"):
        r.solve_state(dense, material, .002)
    laws = r.steel_law_trace(dense, material, r.MaterialProfile.SOURCE2012_POSITIVE_CAP)
    assert all(q.exponent == 25 for q in laws)
    assert all(q.positive_cap_extension_used for q in laws)
    assert all(q.exponent_denominator < 0 for q in laws)
    q = r.solve_state(dense, material, .002, profile=r.MaterialProfile.SOURCE2012_POSITIVE_CAP)
    assert q.torque_Nmm > 0


def test_positive_cap_is_continuous_across_zero_denominator_and_published_cap(material):
    fcr = r.steel_cracking_stress_MPa(material, r.MaterialProfile.SOURCE2012_STRICT)
    for denominator in (-1e-9, 1e-9, .039999, .040001):
        rho = (fcr / material.longitudinal_yield_MPa)**1.5 / ((denominator+.2)/9)
        s = r.RectangularRC(254,381,216,343,rho*254*381,1.016)
        law = r.steel_law_trace(s, material, r.MaterialProfile.SOURCE2012_POSITIVE_CAP)[0]
        assert law.exponent == pytest.approx(25, rel=3e-5)
        assert law.positive_cap_extension_used is (denominator < 0)


@pytest.mark.parametrize("strain", [1e-8, .0005, .001, .002, .0035])
def test_original_uncancelled_compatibility_and_force_triangles(section, material, strain):
    q = r.solve_state(section,material,strain)
    a,t,ao,po = q.strut_angle_rad,q.wall_depth_mm,q.shear_flow_area_mm2,q.shear_flow_perimeter_mm
    s,c = math.sin(a),math.cos(a)
    C = q.concrete_compression_MPa*t*c
    T = q.concrete_tension_MPa*t*s
    beta = math.atan2(T,C)
    torque = 2*ao*math.hypot(C,T)*math.sin(a+beta)
    assert q.torque_Nmm == pytest.approx(torque, rel=2e-12)
    eps_t = (ao**2*q.concrete_compression_MPa*math.sin(a+beta) /
             (po*torque*math.cos(beta)*math.tan(a)*s)-.5)*strain
    eps_l = (ao**2*q.concrete_compression_MPa*math.sin(a+beta) /
             (po*torque*math.cos(beta)/math.tan(a)*s)-.5)*strain
    assert q.longitudinal_strain == pytest.approx(eps_l, abs=1e-14)
    assert q.transverse_strain == pytest.approx(eps_t, abs=1e-14)
    assert q.concrete_tie_surface_strain == pytest.approx(2*(eps_l+eps_t)+strain, rel=2e-12)
    gamma = 2*(eps_t+strain/2)*math.tan(a)
    assert q.twist_rad_per_mm == pytest.approx(po*gamma/(2*ao), rel=2e-12)
    # Scale the force-balance tolerance with the current loading stage, not fc.
    stress_scale = material.concrete_strength_MPa*min(strain/material.concrete_peak_strain,1.)
    fl = torque*po/(2*ao)/math.tan(a+beta)
    ft = torque/(2*ao)*math.tan(a-beta)
    assert abs(section.longitudinal_area_mm2*q.longitudinal_stress_MPa-fl)/(po*t) < 1e-9*stress_scale
    assert abs(section.transverse_one_leg_area_per_spacing_mm*q.transverse_stress_MPa-ft)/t < 1e-9*stress_scale


def test_full_solution_against_independent_three_unknown_root(section, material):
    # Independent root for alpha, wall thickness and tie surface strain.
    # Uses original shear-flow compatibility, not the condensed quadratic or
    # the implementation's residual / steel-stress functions.
    e2 = .002
    def equations(v):
        a,t,e1s = v
        s,c = math.sin(a),math.cos(a)
        ao,po = (254-t)*(381-t),2*(635-2*t)
        el,et = .5*e1s*s*s-.5*e2*c*c,.5*e1s*c*c-.5*e2*s*s
        eta = section.rho_l*327.6/(section.rho_t*320)
        soft = .9/math.sqrt(1+400*.5*e1s/min(eta,1/eta))
        sc = previous.average_compression_MPa(e2,28.1,.00197,soft)
        st = previous.average_tension_MPa(e1s,material.cracking_stress_MPa,material.cracking_strain)
        def stress(e,fy,rho):
            fcr_psi = 3.75*math.sqrt(28.1/0.006894757293168)
            B = ((fcr_psi*0.006894757293168)/fy)**1.5/rho
            m = min(25,1/(9*B-.2))
            return .975*200000*e/(1+(1.1*200000*e/fy)**m)**(1/m)+.025*200000*e
        fl,ft = stress(el,327.6,section.rho_l),stress(et,320,section.rho_t)
        C,T = sc*t*c,st*t*s
        beta = math.atan2(T,C)
        torque = 2*ao*math.hypot(C,T)*math.sin(a+beta)
        return [1136*fl/(po*t)-torque/(2*ao*t)/math.tan(a+beta),
                1.016*ft/t-torque/(2*ao*t)*math.tan(a-beta),
                1000*(po/(2*ao)*(e1s+e2)*s*c-e2/(2*t*s*c))]
    fit = root(equations,[.78,55,.007])
    assert fit.success
    assert max(abs(q) for q in equations(fit.x)) < 1e-7
    q = r.solve_state(section,material,e2)
    assert [q.strut_angle_rad,q.wall_depth_mm,q.concrete_tie_surface_strain] == pytest.approx(fit.x,rel=2e-8)


@pytest.mark.parametrize("strain", [.0005,.001,.002,.0035])
def test_legacy_material_profile_reproduces_previous_fixed_strain_states(section,material,strain):
    old = previous.solve_state(section,material,strain)
    new = r.solve_state(section,material,strain,profile=r.MaterialProfile.LEGACY42)
    assert [new.torque_Nmm,new.twist_rad_per_mm,new.strut_angle_rad,new.wall_depth_mm] == pytest.approx(
        [old.torque_Nmm,old.twist_rad_per_mm,old.strut_angle_rad,old.wall_depth_mm],rel=1e-9)


def test_uncracked_steel_compression_is_elastic_and_not_clipped(section, material):
    q = r.solve_state(section,material,1e-8)
    negative = [(q.longitudinal_strain,q.longitudinal_stress_MPa,material.longitudinal_E_MPa),
                (q.transverse_strain,q.transverse_stress_MPa,material.transverse_E_MPa)]
    negative = [(e,f,E) for e,f,E in negative if e<0]
    assert negative
    for e,f,E in negative:
        assert f == pytest.approx(E*e,rel=1e-12)
        assert f < 0


def test_similarity_and_cross_section_rotation(section,material):
    q = r.solve_state(section,material,.002)
    scaled = r.RectangularRC(762,1143,648,1029,1136*9,1.016*3)
    a = r.solve_state(scaled,material,.002)
    b = r.solve_state(r.RectangularRC(381,254,343,216,1136,1.016),material,.002)
    assert a.torque_Nmm == pytest.approx(27*q.torque_Nmm,rel=1e-10)
    assert a.twist_rad_per_mm == pytest.approx(q.twist_rad_per_mm/3,rel=1e-10)
    assert b.torque_Nmm == pytest.approx(q.torque_Nmm,rel=1e-10)
    assert b.twist_rad_per_mm == pytest.approx(q.twist_rad_per_mm,rel=1e-10)


def test_full_curve_has_real_low_load_points_and_concrete_endpoint(curve):
    assert curve.states[0].concrete_surface_strain == 1e-8
    assert curve.states[0].torque_Nmm > 0
    assert curve.states[-1].concrete_surface_strain == .0035
    assert curve.termination == "concrete_surface_limit"
    assert curve.branch_status == "NUMERICALLY_COMPLETE_TO_MATERIAL_LIMIT"
    assert all(b.concrete_surface_strain>a.concrete_surface_strain for a,b in zip(curve.states,curve.states[1:]))
    assert curve.interval_peak.torque_Nmm >= max(q.torque_Nmm for q in curve.states)
    assert curve.comparison_window_peak.concrete_surface_strain >= .0005
    assert curve.production_accepted is False


def test_boundary_maximum_is_valid_and_steel_limit_is_located_exactly(section,material):
    # The prescribed lower strain limit forces a material-boundary maximum;
    # an interior-peak requirement would reject this complete curve incorrectly.
    m = replace(material,steel_strain_limit=.0015)
    c = r.trace_curve(section,m,steps=65)
    end = c.states[-1]
    assert c.termination == "steel_strain_limit"
    assert max(end.longitudinal_strain,end.transverse_strain) == pytest.approx(.0015,abs=1e-11)
    assert all(max(q.longitudinal_strain,q.transverse_strain)<.0015 for q in c.states[:-1])
    assert c.interval_peak.concrete_surface_strain == end.concrete_surface_strain
    assert c.comparison_window_peak == end


def test_limit_before_comparison_window_is_complete_without_fabricating_peak(section,material):
    c = r.trace_curve(section,replace(material,concrete_surface_limit=.0002),steps=40)
    assert c.termination == "concrete_surface_limit"
    assert c.states[-1].concrete_surface_strain == .0002
    assert c.comparison_window_peak is None
    assert all(q.concrete_surface_strain<=.0002 for q in c.states)


def test_peak_and_event_are_stable_under_grid_refinement(curve):
    fine = r.trace_curve(curve.section,curve.material,steps=145)
    assert fine.comparison_window_peak.torque_Nmm == pytest.approx(curve.comparison_window_peak.torque_Nmm,rel=1e-7)
    assert fine.comparison_window_peak.twist_rad_per_mm == pytest.approx(curve.comparison_window_peak.twist_rad_per_mm,rel=1e-5)
    event = r.state_at_tensile_strain(curve,mean_concrete_tension_strain=curve.material.cracking_strain)
    assert event.concrete_tie_surface_strain/2 == pytest.approx(curve.material.cracking_strain,rel=1e-8)
    # An event coinciding with an existing point counts once, not twice.
    point = curve.states[20]
    assert r.state_at_tensile_strain(curve,mean_concrete_tension_strain=point.concrete_tie_surface_strain/2) == point
    with pytest.raises(r.ReferenceScopeError,match="absent"):
        r.state_at_tensile_strain(curve,mean_concrete_tension_strain=.1)


def test_exact_mesh_hit_does_not_hide_a_second_strain_crossing(curve):
    # A branch can hit the target exactly at one mesh point, then cross it
    # again between other points. An exact hit must not bypass uniqueness.
    strains = [.0001,.0002,.0003,.0001]
    points = tuple(replace(q,concrete_tie_surface_strain=e) for q,e in zip(curve.states,strains))
    with pytest.raises(r.ReferenceScopeError,match="not unique"):
        r.state_at_tensile_strain(replace(curve,states=points),mean_concrete_tension_strain=.0001)


@pytest.mark.parametrize("bad", [None,True,-1,0,float("nan"),float("inf")])
def test_invalid_continuation_strain_is_rejected(section,material,bad):
    with pytest.raises(ValueError):
        r.solve_state(section,material,bad)


@pytest.mark.parametrize("bad", [None,False,"legacy42_shared_torsion_fcr", "guess"])
def test_no_unrecognized_or_silent_material_profile(section,material,bad):
    with pytest.raises(ValueError,match="profile"):
        r.solve_state(section,material,.002,profile=bad)


@pytest.mark.parametrize("bad", [True,29,3001,60.5])
def test_invalid_step_count_is_rejected(section,material,bad):
    with pytest.raises(ValueError):
        r.trace_curve(section,material,steps=bad)


def test_offline_reference_does_not_enter_design_dispatch_or_capacity_fields():
    root_dir = Path(__file__).resolve().parents[1]
    assert not any("igird_reference43" in p.read_text(encoding="utf-8") for p in (root_dir/"concrete_pmm_pro/ui").rglob("*.py"))
    assert r.PRODUCTION_VALIDATED is False
    assert r.PUBLISHED_REPRODUCTION_VALIDATED is False
    assert not ({"Tn","Vn","phi_Tn","phi_Vn","accepted_Tn"} & set(r.Reference43Curve.__dataclass_fields__))


def test_audit_retains_rejected_cases_and_unchanged_gate(tmp_path):
    from tools.run_igird_reference43 import audit, write_evidence
    summary,curves = audit(steps=55)
    expected = ["B3","B4","B5","B6","B7","B8","B9","B10","C4","C5","C6","G3","G4","G5","G7","G8"]
    assert summary["reproduction_relative_tolerance"] == .01
    assert summary["published_reproduction_status"] == "NOT_REPRODUCED"
    assert summary["production_accepted"] is False
    assert len(summary["profiles"]) == 3
    for p in summary["profiles"]:
        assert [q["specimen"] for q in p["results"]] == expected
        assert p["reference_cases"] == 16
        assert p["published_reproduction_status"] == "NOT_REPRODUCED"
        assert all(q["production_accepted"] is False for q in p["results"])
    strict = summary["profiles"][1]
    cap = summary["profiles"][2]
    assert strict["unsupported_cases"] > 0
    assert strict["numerically_solved_cases"]+strict["unsupported_cases"] == 16
    assert cap["numerically_solved_cases"] == 16
    assert cap["declared_extension_cases"] == strict["unsupported_cases"]
    # Reference improvement is real without moving the 1% gate or claiming PASS.
    assert cap["maximum_absolute_torque_theory_difference"] < .05
    assert cap["maximum_absolute_twist_theory_difference"] < .07
    assert cap["published_point_matches"] < 16
    assert all(q["maximum_stage_relative_equilibrium_residual"]<1e-9 for q in cap["results"])
    write_evidence(tmp_path,summary,curves)
    assert (tmp_path/"steel_material_trace.csv").is_file()
    assert "NaN" not in (tmp_path/"audit.json").read_text()
