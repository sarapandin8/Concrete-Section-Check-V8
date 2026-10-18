"""Source-separated RC torsion reference and complete strain continuation.

The concrete law follows Bernardo et al. (2015), doi:10.1617/s11527-014-0301-z.
The embedded-steel cracking parameter follows the explicit Table 4 in
Bernardo et al. (2012), doi:10.1016/j.engstruct.2012.04.036:
fcr_steel[psi] = 3.75*sqrt(fc[psi]). This is different from the torsion-
corrected tensile concrete peak Ec*K*eps_cr used in the concrete ties.

Three profiles remain separate. The literal steel exponent has a domain
problem at 9B-0.2 <= 0. The positive-cap profile is a DECLARED continuous
extension of the printed m<=25 limit. It is not claimed as the authors'
undocumented implementation and never grants production acceptance.

Scope: homogeneous solid rectangle, closed cage, pure torsion, no prestress,
construction interface, open U substitution or concurrent N-M-V-T resistance.
N, mm, MPa, radians; compression magnitudes positive, steel tension positive.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence

import numpy as np
from scipy.optimize import brentq, least_squares, minimize_scalar

from concrete_pmm_pro.analysis.igird_reference42 import (
    RCMaterial, RectangularRC, ReferenceConvergenceError, ReferenceScopeError,
    ReferenceState, _finite, average_compression_MPa, average_tension_MPa,
)

VERSION = "IGIRDER.REFERENCE43"
PRODUCTION_VALIDATED = False
PUBLISHED_REPRODUCTION_VALIDATED = False
PSI_TO_MPA = 0.006894757293168
COMPARISON_WINDOW_START = 0.0005


class MaterialProfile(str, Enum):
    LEGACY42 = "legacy42_shared_torsion_fcr"
    SOURCE2012_STRICT = "2012_steel_cracking_parameter_strict_exponent"
    SOURCE2012_POSITIVE_CAP = "2012_steel_cracking_parameter_declared_positive_cap"


@dataclass(frozen=True)
class SteelLawTrace:
    role: str
    rho: float
    cracking_stress_MPa: float
    B: float
    exponent_denominator: float
    exponent: float
    positive_cap_extension_used: bool


def steel_cracking_stress_MPa(material: RCMaterial, profile: MaterialProfile) -> float:
    if not isinstance(profile, MaterialProfile):
        raise ValueError("Choose an explicit, supported material profile.")
    if profile is MaterialProfile.LEGACY42:
        return material.cracking_stress_MPa
    return 3.75 * math.sqrt(material.concrete_strength_MPa / PSI_TO_MPA) * PSI_TO_MPA


def steel_law_trace(section: RectangularRC, material: RCMaterial,
                    profile: MaterialProfile) -> tuple[SteelLawTrace, SteelLawTrace]:
    fcr = steel_cracking_stress_MPa(material, profile)
    result = []
    for role, rho, fy in (("longitudinal", section.rho_l, material.longitudinal_yield_MPa),
                          ("transverse", section.rho_t, material.transverse_yield_MPa)):
        B = (fcr / fy)**1.5 / rho
        denominator = 9*B - 0.2
        extension = denominator <= 0
        if extension and profile is not MaterialProfile.SOURCE2012_POSITIVE_CAP:
            raise ReferenceScopeError(f"{role}: literal steel exponent is nonpositive (9B-0.2={denominator:.8g}). The strict profile does not repair it.")
        # Inverse exponent makes the domain extension and the existing upper
        # cap explicit. No beam-specific coefficient or new fitted cap is used.
        exponent = 1 / max(1/25, denominator)
        result.append(SteelLawTrace(role, rho, fcr, B, denominator, exponent, extension))
    return tuple(result)


def _steel_stress(strain: float, E: float, fy: float, shape: SteelLawTrace) -> float:
    if strain <= 0:
        # Only small elastic compression before cracking is represented.
        # Trial iterates may leave this range; accepted states are checked below.
        return E*strain
    log_x = math.log(1.1*E/fy) + math.log(strain)
    m = shape.exponent
    return .975*E*strain*math.exp(-float(np.logaddexp(0., m*log_x))/m) + .025*E*strain


def state_from_principal_strains(section: RectangularRC, material: RCMaterial, *,
                                 surface_compression: float, surface_tension: float,
                                 strut_angle_rad: float,
                                 profile: MaterialProfile = MaterialProfile.SOURCE2012_STRICT) -> ReferenceState:
    """Use principal strains directly; allow elastic steel compression at low T.

    Mohr compatibility gives el, et without positive-strain clipping. The
    geometry quadratic follows the same published compatibility equations
    independently of the material profile.
    """
    e2 = _finite(surface_compression, "surface concrete compression", positive=True)
    e1s = _finite(surface_tension, "surface concrete tension", positive=True)
    a = _finite(strut_angle_rad, "strut angle")
    if not 0 < a < math.pi/2:
        raise ReferenceScopeError("Strut angle must be inside (0,pi/2).")
    if e2 > material.concrete_surface_limit:
        raise ReferenceScopeError("Concrete strain exceeds the declared reference limit.")
    long_shape, trans_shape = steel_law_trace(section, material, profile)
    s, c = math.sin(a), math.cos(a)
    el = .5*e1s*s*s - .5*e2*c*c
    et = .5*e1s*c*c - .5*e2*s*s
    g = e2 / ((e1s+e2)*s*s*c*c)
    b, h = section.width_mm, section.height_mm
    linear = (2+g)*(b+h)
    t = 2*g*b*h/(linear + math.sqrt(linear*linear - 4*(4+g)*g*b*h))
    ao, po = (b-t)*(h-t), 2*(b+h-2*t)
    eta = section.rho_l*material.longitudinal_yield_MPa/(section.rho_t*material.transverse_yield_MPa)
    eta_prime = min(eta, 1/eta)
    beta = min(.9,5.8/math.sqrt(material.concrete_strength_MPa))/math.sqrt(1+400*(e1s/2)/eta_prime)
    sc = average_compression_MPa(e2, material.concrete_strength_MPa, material.concrete_peak_strain, beta)
    st = average_tension_MPa(e1s, material.cracking_stress_MPa, material.cracking_strain)
    fl = _steel_stress(el, material.longitudinal_E_MPa, material.longitudinal_yield_MPa, long_shape)
    ft = _steel_stress(et, material.transverse_E_MPa, material.transverse_yield_MPa, trans_shape)
    beta_angle = math.atan2(st*s, sc*c)
    shear = (sc+st)*s*c
    r_l = section.longitudinal_area_mm2*fl/(po*t) - sc*c*c + st*s*s
    r_t = section.transverse_one_leg_area_per_spacing_mm*ft/t - shear*math.tan(a-beta_angle)
    return ReferenceState(e2, el, et, e1s, t, ao, po, a, beta, sc, st, fl, ft,
                          2*ao*t*shear, e2/(2*t*s*c),
                          max(abs(r_l),abs(r_t))/material.concrete_strength_MPa)


def _equilibrium_residual(section: RectangularRC, material: RCMaterial, state: ReferenceState) -> np.ndarray:
    """Original Eqs.22-23, expressed through direct force triangles."""
    a, t = state.strut_angle_rad, state.wall_depth_mm
    s, c = math.sin(a), math.cos(a)
    sc, st = state.concrete_compression_MPa, state.concrete_tension_MPa
    C, T = sc*t*c, st*t*s
    ba = math.atan2(T,C)
    torque = 2*state.shear_flow_area_mm2*math.hypot(C,T)*math.sin(a+ba)
    force_l = torque*state.shear_flow_perimeter_mm/(2*state.shear_flow_area_mm2)/math.tan(a+ba)
    force_t_per_length = torque/(2*state.shear_flow_area_mm2)*math.tan(a-ba)
    return np.asarray([
        (section.longitudinal_area_mm2*state.longitudinal_stress_MPa-force_l)/(state.shear_flow_perimeter_mm*t),
        (section.transverse_one_leg_area_per_spacing_mm*state.transverse_stress_MPa-force_t_per_length)/t,
    ])


def solve_state(section: RectangularRC, material: RCMaterial, surface_compression: float, *,
                profile: MaterialProfile = MaterialProfile.SOURCE2012_STRICT,
                seed: ReferenceState | None = None) -> ReferenceState:
    e2 = _finite(surface_compression, "surface concrete compression", positive=True)
    if e2 > material.concrete_surface_limit:
        raise ReferenceScopeError("Concrete strain exceeds the declared reference limit.")
    steel_law_trace(section, material, profile)  # Fail domain checks before optimization.
    start = [seed.strut_angle_rad, math.log(seed.concrete_tie_surface_strain/e2)] if seed else [math.pi/4,0.]
    lower = [1e-7,-18.]
    upper = [math.pi/2-1e-7, math.log(.1/e2)]
    start = np.clip(start, np.asarray(lower)+1e-10, np.asarray(upper)-1e-10)
    # Scale by loading stage. Scaling exclusively by fc loses relative accuracy
    # at near-zero loads and can terminate while the elastic equilibrium is wrong.
    stress_scale = material.concrete_strength_MPa*min(e2/material.concrete_peak_strain,1.)

    def evaluate(v: Sequence[float]) -> ReferenceState:
        return state_from_principal_strains(section, material, surface_compression=e2,
                                            surface_tension=math.exp(v[1])*e2,
                                            strut_angle_rad=float(v[0]), profile=profile)
    fit = least_squares(lambda v: _equilibrium_residual(section, material, evaluate(v))/stress_scale,
                        start, bounds=(lower,upper), xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=250)
    q = evaluate(fit.x)
    relative = float(max(abs(_equilibrium_residual(section,material,q)))/stress_scale)
    if not fit.success or relative > 1e-9:
        raise ReferenceConvergenceError(f"e2s={e2:.8g}: equilibrium did not converge (stage-relative residual={relative:.3g}); no point is bridged.")
    if q.longitudinal_strain < 0 and abs(q.longitudinal_stress_MPa) > material.longitudinal_yield_MPa:
        raise ReferenceScopeError("Compression yielding of longitudinal steel is outside this reference.")
    if q.transverse_strain < 0 and abs(q.transverse_stress_MPa) > material.transverse_yield_MPa:
        raise ReferenceScopeError("Compression yielding of transverse steel is outside this reference.")
    return q


@dataclass(frozen=True)
class Reference43Curve:
    section: RectangularRC
    material: RCMaterial
    profile: MaterialProfile
    steel_laws: tuple[SteelLawTrace, SteelLawTrace]
    states: tuple[ReferenceState, ...]
    interval_peak: ReferenceState
    comparison_window_peak: ReferenceState | None
    termination: str
    branch_status: str
    production_accepted: bool = False


def trace_curve(section: RectangularRC, material: RCMaterial, *,
                profile: MaterialProfile = MaterialProfile.SOURCE2012_STRICT,
                start_surface_strain: float = 1e-8, steps: int = 220) -> Reference43Curve:
    """Trace from small load to the first actual declared material strain limit.

    The post-cracking comparison window e2s>=0.0005 is retained explicitly
    from REFERENCE42; it is not promoted to a cracking criterion. A located
    material boundary is a complete endpoint even if the maximum is there.
    """
    start = _finite(start_surface_strain,"starting strain",positive=True)
    if start >= material.concrete_surface_limit or start >= COMPARISON_WINDOW_START:
        raise ValueError("The full reference interval must start below 0.0005 and the material limit.")
    if isinstance(steps,bool) or not isinstance(steps,int) or not 30 <= steps <= 3000:
        raise ValueError("Continuation requires 30..3000 integer steps.")
    laws = steel_law_trace(section,material,profile)
    extra = [COMPARISON_WINDOW_START] if COMPARISON_WINDOW_START <= material.concrete_surface_limit else []
    grid = np.unique(np.concatenate((np.geomspace(start,material.concrete_surface_limit,steps),extra)))
    points: list[ReferenceState] = []
    termination = "concrete_surface_limit"
    for e2 in grid:
        point = solve_state(section,material,float(e2),profile=profile,seed=points[-1] if points else None)
        if max(point.longitudinal_strain,point.transverse_strain) >= material.steel_strain_limit:
            if not points:
                raise ReferenceScopeError("The starting point already exceeds the steel strain limit.")
            previous = points[-1]
            def limit_residual(e: float) -> float:
                q = solve_state(section,material,e,profile=profile,seed=previous)
                return max(q.longitudinal_strain,q.transverse_strain)-material.steel_strain_limit
            bound = brentq(limit_residual,previous.concrete_surface_strain,float(e2),xtol=1e-14)
            point = solve_state(section,material,bound,profile=profile,seed=previous)
            termination = "steel_strain_limit"
            points.append(point)
            break
        points.append(point)
    if len(points)<3:
        raise ReferenceConvergenceError("No usable continuation interval was obtained.")

    def refine(index: int, window_start: float) -> ReferenceState:
        q = points[index]
        if index in (0,len(points)-1):
            return q
        fit = minimize_scalar(lambda e:-solve_state(section,material,e,profile=profile,seed=q).torque_Nmm,
                              bounds=(max(window_start, points[index-1].concrete_surface_strain),
                                      points[index+1].concrete_surface_strain),
                              method="bounded",options={"xatol":1e-12})
        if not fit.success:
            raise ReferenceConvergenceError("Peak refinement failed.")
        candidate = solve_state(section,material,float(fit.x),profile=profile,seed=q)
        if max(candidate.longitudinal_strain,candidate.transverse_strain) > material.steel_strain_limit*(1+1e-9):
            raise ReferenceScopeError("Peak refinement exceeded the located steel boundary.")
        return candidate if candidate.torque_Nmm>=q.torque_Nmm else q

    all_index = max(range(len(points)),key=lambda i:points[i].torque_Nmm)
    post = [i for i,q in enumerate(points) if q.concrete_surface_strain>=COMPARISON_WINDOW_START]
    interval_peak = refine(all_index, start)
    post_peak = refine(max(post,key=lambda i:points[i].torque_Nmm), COMPARISON_WINDOW_START) if post else None
    return Reference43Curve(section,material,profile,laws,tuple(points),interval_peak,post_peak,
                            termination,"NUMERICALLY_COMPLETE_TO_MATERIAL_LIMIT")


def state_at_tensile_strain(curve: Reference43Curve, *, mean_concrete_tension_strain: float) -> ReferenceState:
    """Locate a stated strain event; do not call it Tcr without a source criterion."""
    target = 2*_finite(mean_concrete_tension_strain,"mean concrete tensile strain",positive=True)
    hits = [q for q in curve.states
            if math.isclose(q.concrete_tie_surface_strain, target, rel_tol=1e-12, abs_tol=1e-15)]
    intervals = [(a,b) for a,b in zip(curve.states,curve.states[1:])
                 if (a.concrete_tie_surface_strain-target)*(b.concrete_tie_surface_strain-target)<0]
    if len(hits)+len(intervals)!=1:
        raise ReferenceScopeError("The requested tensile-strain event is absent or not unique on this branch.")
    if hits:
        return hits[0]
    a,b = intervals[0]
    def event(e: float) -> float:
        return solve_state(curve.section,curve.material,e,profile=curve.profile,seed=a).concrete_tie_surface_strain-target
    e2 = brentq(event,a.concrete_surface_strain,b.concrete_surface_strain,xtol=1e-14)
    return solve_state(curve.section,curve.material,e2,profile=curve.profile,seed=a)
