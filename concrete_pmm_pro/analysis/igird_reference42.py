"""Published-equation reference kernel; NOT the project's composite resistance.

Bernardo, Andrade & Nunes (2015), Materials and Structures 48:2169-2193,
doi:10.1617/s11527-014-0301-z, Eqs. 22-23, 28, 34-40, 56-63 and Table 1.
Units throughout: N, mm, MPa, radians. Compression magnitudes are positive.

Scope: solid rectangular RC, one closed transverse cage, pure torsion,
positive smeared steel strains, post-cracking branch only. No PC, construction
joint, open U, biaxial bending, shear-torsion interaction, strength factor or
production capacity is inferred from this reference problem.

The Table-1 material profile is pinned explicitly. It uses K=1.45,
Ec=3875*K*sqrt(fc), eps_cr=0.00008*K and fcr=Ec*eps_cr for continuity.
This interpretation has NOT reproduced all Table-3 published numbers; see the
benchmark audit. Do not substitute the Table-2 tensile strength silently, fit
beam-specific coefficients, or interpret numerical convergence as validation.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares, minimize_scalar

VERSION = "IGIRDER.REFERENCE42"
SOURCE_DOI = "10.1617/s11527-014-0301-z"
PRODUCTION_VALIDATED = False
PUBLISHED_REPRODUCTION_VALIDATED = False
MATERIAL_PROFILE = "2015_table1_continuous_solid_K1.45"


class ReferenceScopeError(ValueError):
    """The reference equations do not establish this requested case."""


class ReferenceConvergenceError(RuntimeError):
    """No equilibrium state was accepted at a requested continuation point."""


def _finite(value: float, name: str, *, positive: bool = False) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a finite number, not a flag.")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be a finite number.") from None
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError(f"{name} must be finite" + (" and positive." if positive else "."))
    return result


@dataclass(frozen=True)
class RectangularRC:
    width_mm: float
    height_mm: float
    hoop_width_mm: float
    hoop_height_mm: float
    longitudinal_area_mm2: float
    transverse_one_leg_area_per_spacing_mm: float
    closed_cage: bool = True

    def __post_init__(self) -> None:
        for name in ("width_mm", "height_mm", "hoop_width_mm", "hoop_height_mm",
                     "longitudinal_area_mm2", "transverse_one_leg_area_per_spacing_mm"):
            object.__setattr__(self, name, _finite(getattr(self, name), name, positive=True))
        if self.closed_cage is not True:
            raise ReferenceScopeError("This reference requires one closed cage; an open U with slab mesh is not substituted.")
        if self.hoop_width_mm >= self.width_mm or self.hoop_height_mm >= self.height_mm:
            raise ValueError("Hoop centreline dimensions must lie inside the concrete rectangle.")

    @property
    def area_mm2(self) -> float:
        return self.width_mm * self.height_mm

    @property
    def hoop_perimeter_mm(self) -> float:
        # The original 2015 section 6 and Table 2 use the hoop, not outer perimeter.
        return 2 * (self.hoop_width_mm + self.hoop_height_mm)

    @property
    def rho_l(self) -> float:
        return self.longitudinal_area_mm2 / self.area_mm2

    @property
    def rho_t(self) -> float:
        return self.transverse_one_leg_area_per_spacing_mm * self.hoop_perimeter_mm / self.area_mm2


@dataclass(frozen=True)
class RCMaterial:
    concrete_strength_MPa: float
    concrete_peak_strain: float
    longitudinal_yield_MPa: float
    transverse_yield_MPa: float
    longitudinal_E_MPa: float = 200000.0
    transverse_E_MPa: float = 200000.0
    concrete_surface_limit: float = 0.0035
    steel_strain_limit: float = 0.010

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, _finite(getattr(self, name), name, positive=True))
        if self.concrete_surface_limit > 2 * self.concrete_peak_strain:
            raise ReferenceScopeError("Concrete surface limit extends beyond the defined descending concrete law.")

    @property
    def concrete_tension_E_MPa(self) -> float:
        return 3875 * 1.45 * math.sqrt(self.concrete_strength_MPa)

    @property
    def cracking_strain(self) -> float:
        return 0.00008 * 1.45

    @property
    def cracking_stress_MPa(self) -> float:
        return self.concrete_tension_E_MPa * self.cracking_strain


def average_tension_MPa(surface_strain: float, fcr_MPa: float, eps_cr: float) -> float:
    """Exact integral of the linear / e^-0.4 tensile law (2015 Eqs. 62-63)."""
    e = _finite(surface_strain, "surface tensile strain")
    f = _finite(fcr_MPa, "cracking stress", positive=True)
    ec = _finite(eps_cr, "cracking strain", positive=True)
    if e < 0:
        raise ReferenceScopeError("Concrete tie strain cannot be negative in this law.")
    if e <= ec:
        return f * e / (2 * ec)
    k = ec / (2 * e) + ec**0.4 / (0.6 * e) * (e**0.6 - ec**0.6)
    return f * k


def average_compression_MPa(surface_strain: float, fc_MPa: float, eps0: float, beta: float) -> float:
    """Exact integral of the softened parabola (2015 Eqs. 60-61)."""
    e = _finite(surface_strain, "surface compressive strain")
    fc = _finite(fc_MPa, "concrete strength", positive=True)
    e0 = _finite(eps0, "concrete peak strain", positive=True)
    be = _finite(beta, "softening factor", positive=True)
    if e < 0 or be > 0.9 or e > 2 * e0:
        raise ReferenceScopeError("Concrete compression lies outside the defined reference law.")
    peak = be * e0
    if e <= peak:
        k = e / peak - e * e / (3 * peak * peak)
    else:
        k = 1 - peak / (3 * e) - (e - peak)**3 / (3 * e * (2 * e0 - peak)**2)
    return be * fc * k


def steel_tension_MPa(strain: float, E_MPa: float, fy_MPa: float, rho: float, fcr_MPa: float) -> float:
    """Belarbi-Hsu smeared tensile law as printed in 2015 Table 1.

    A nonpositive exponent denominator is rejected rather than repaired with
    an undocumented m=25 rule or allowed to create nonzero stress at zero strain.
    """
    e = _finite(strain, "steel strain")
    E = _finite(E_MPa, "steel modulus", positive=True)
    fy = _finite(fy_MPa, "steel yield stress", positive=True)
    density = _finite(rho, "steel ratio", positive=True)
    fcr = _finite(fcr_MPa, "cracking stress", positive=True)
    if e < 0:
        raise ReferenceScopeError("The printed tensile law does not define a compressive steel branch.")
    B = (fcr / fy)**1.5 / density
    denominator = 9 * B - 0.2
    if denominator <= 0:
        raise ReferenceScopeError("The printed steel exponent is nonpositive; no unreferenced replacement is made.")
    m = min(25.0, 1 / denominator)
    if e == 0:
        return 0.0
    # Log-domain evaluation avoids overflow for large exponents / trial strains.
    log_x = math.log(1.1 * E / fy) + math.log(e)
    log_denom = float(np.logaddexp(0.0, m * log_x)) / m
    return 0.975 * E * e * math.exp(-log_denom) + 0.025 * E * e


@dataclass(frozen=True)
class ReferenceState:
    concrete_surface_strain: float
    longitudinal_strain: float
    transverse_strain: float
    concrete_tie_surface_strain: float
    wall_depth_mm: float
    shear_flow_area_mm2: float
    shear_flow_perimeter_mm: float
    strut_angle_rad: float
    softening_factor: float
    concrete_compression_MPa: float
    concrete_tension_MPa: float
    longitudinal_stress_MPa: float
    transverse_stress_MPa: float
    torque_Nmm: float
    twist_rad_per_mm: float
    equilibrium_relative_residual: float


def state_from_steel_strains(section: RectangularRC, material: RCMaterial, *,
                            surface_compression: float, longitudinal_strain: float,
                            transverse_strain: float) -> ReferenceState:
    """Condense compatibility analytically; equilibrium remains to be solved.

    Eqs. 56-58 reduce to kl=el/e2s+1/2, kt=et/e2s+1/2,
    tan(alpha)^2=kl/kt and g=po*t/Ao=(1/2kl)+(1/2kt).
    Inserting the EXACT Ao=(b-t)(h-t) gives the smaller quadratic root:
      (4+g)t^2 - (2+g)(b+h)t + g*b*h = 0.
    The t^2 term in Ao is retained; the linear approximation printed after
    Eq. 40 is not silently treated as an equal expression.
    """
    e2 = _finite(surface_compression, "surface compression", positive=True)
    el = _finite(longitudinal_strain, "longitudinal strain")
    et = _finite(transverse_strain, "transverse strain")
    if min(el, et) < 0:
        raise ReferenceScopeError("Only the tensile-steel reference branch is implemented.")
    if e2 > material.concrete_surface_limit or max(el, et) > material.steel_strain_limit:
        raise ReferenceScopeError("State exceeds a declared reference failure strain.")
    kl, kt = el / e2 + 0.5, et / e2 + 0.5
    alpha = math.atan(math.sqrt(kl / kt))
    g = 0.5 / kl + 0.5 / kt
    b, h = section.width_mm, section.height_mm
    linear = (2 + g) * (b + h)
    discriminant = linear * linear - 4 * (4 + g) * g * b * h
    t = 2 * g * b * h / (linear + math.sqrt(discriminant))
    area, perimeter = (b - t) * (h - t), 2 * (b + h - 2 * t)
    e1s = 2 * (el + et) + e2
    eta = section.rho_l * material.longitudinal_yield_MPa / (section.rho_t * material.transverse_yield_MPa)
    eta_prime = min(eta, 1 / eta)
    beta = min(0.9, 5.8 / math.sqrt(material.concrete_strength_MPa)) / math.sqrt(1 + 400 * (e1s / 2) / eta_prime)
    sc = average_compression_MPa(e2, material.concrete_strength_MPa, material.concrete_peak_strain, beta)
    st = average_tension_MPa(e1s, material.cracking_stress_MPa, material.cracking_strain)
    fl = steel_tension_MPa(el, material.longitudinal_E_MPa, material.longitudinal_yield_MPa, section.rho_l, material.cracking_stress_MPa)
    ft = steel_tension_MPa(et, material.transverse_E_MPa, material.transverse_yield_MPa, section.rho_t, material.cracking_stress_MPa)
    c, s = math.cos(alpha), math.sin(alpha)
    beta_angle = math.atan2(st * s, sc * c)
    # Literal published Eqs. 22-23 and force triangles (gamma'=alpha-beta).
    # The transverse relation is NOT replaced with the usual membrane normal
    # stress sc*sin(alpha)^2 - st*cos(alpha)^2; the two differ when st != 0.
    r_l = section.longitudinal_area_mm2 * fl / (perimeter * t) - sc * c * c + st * s * s
    r_t = section.transverse_one_leg_area_per_spacing_mm * ft / t - (sc + st) * s * c * math.tan(alpha - beta_angle)
    return ReferenceState(e2, el, et, e1s, t, area, perimeter, alpha, beta, sc, st, fl, ft,
                          2 * area * t * (sc + st) * s * c, e2 / (2 * t * s * c),
                          max(abs(r_l), abs(r_t)) / material.concrete_strength_MPa)


def solve_state(section: RectangularRC, material: RCMaterial, surface_compression: float,
                *, seed: ReferenceState | None = None) -> ReferenceState:
    """Solve two simultaneous equilibrium equations, without clipping strains."""
    e2 = _finite(surface_compression, "surface compression", positive=True)
    if e2 > material.concrete_surface_limit:
        raise ReferenceScopeError("Requested concrete strain exceeds the declared failure strain.")
    # Bound strains by the actual failure criterion, not arbitrary log-ratio caps.
    upper = math.log(material.steel_strain_limit / e2)
    lower = math.log(1e-14 / e2)
    initial = np.log([seed.longitudinal_strain / e2, seed.transverse_strain / e2]) if seed else np.log([0.25, 0.25])
    initial = np.clip(initial, lower + 1e-10, upper - 1e-10)

    def evaluate(log_ratios: np.ndarray) -> ReferenceState:
        el, et = np.exp(log_ratios) * e2
        return state_from_steel_strains(section, material, surface_compression=e2,
                                       longitudinal_strain=float(el), transverse_strain=float(et))

    def residual(log_ratios: np.ndarray) -> np.ndarray:
        q = evaluate(log_ratios)
        c, s = math.cos(q.strut_angle_rad), math.sin(q.strut_angle_rad)
        sc, st, t = q.concrete_compression_MPa, q.concrete_tension_MPa, q.wall_depth_mm
        beta_angle = math.atan2(st * s, sc * c)
        return np.asarray([
            section.longitudinal_area_mm2 * q.longitudinal_stress_MPa / (q.shear_flow_perimeter_mm * t) - sc * c*c + st * s*s,
            section.transverse_one_leg_area_per_spacing_mm * q.transverse_stress_MPa / t - (sc+st)*s*c*math.tan(q.strut_angle_rad-beta_angle),
        ]) / material.concrete_strength_MPa

    result = least_squares(residual, initial, bounds=(lower, upper), xtol=1e-12,
                           ftol=1e-12, gtol=1e-12, max_nfev=250)
    state = evaluate(result.x)
    if not result.success or state.equilibrium_relative_residual > 1e-9:
        raise ReferenceConvergenceError(f"No accepted tensile-steel state at e2s={e2:.8g}; residual={state.equilibrium_relative_residual:.3g}. No missing point was bridged.")
    return state


@dataclass(frozen=True)
class ReferenceCurve:
    section: RectangularRC
    material: RCMaterial
    states: tuple[ReferenceState, ...]
    postcracking_peak: ReferenceState
    branch_status: str
    termination: str
    material_profile: str = MATERIAL_PROFILE
    production_accepted: bool = False


def trace_postcracking(section: RectangularRC, material: RCMaterial, *,
                       start_surface_strain: float = 0.0005, steps: int = 160) -> ReferenceCurve:
    """Follow a declared post-cracking interval; never invent the origin/Tcr.

    Only a concrete-limit-complete curve with an interior, refined peak is
    called NUMERICALLY_COMPLETE. Failure to solve is raised to the caller.
    A steel strain boundary produces an explicit incomplete curve.
    """
    start = _finite(start_surface_strain, "starting surface strain", positive=True)
    if start >= material.concrete_surface_limit:
        raise ValueError("Reference interval must extend beyond its starting strain.")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 12 or steps > 2000:
        raise ValueError("Continuation requires an integer number of steps between 12 and 2000.")
    states: list[ReferenceState] = []
    stop = "concrete_surface_limit"
    for e2 in np.geomspace(start, material.concrete_surface_limit, steps):
        try:
            point = solve_state(section, material, float(e2), seed=states[-1] if states else None)
        except ReferenceConvergenceError:
            if states and max(states[-1].longitudinal_strain, states[-1].transverse_strain) >= 0.98 * material.steel_strain_limit:
                stop = "steel_limit_bracket_not_resolved"
                break
            raise
        states.append(point)
    if len(states) < 3:
        raise ReferenceConvergenceError("No usable continuation interval was obtained.")
    index = max(range(len(states)), key=lambda i: states[i].torque_Nmm)
    peak = states[index]
    status = "NUMERICALLY_COMPLETE" if stop == "concrete_surface_limit" and 0 < index < len(states) - 1 else "INCOMPLETE_BRANCH"
    if 0 < index < len(states) - 1:
        lo, hi = states[index - 1].concrete_surface_strain, states[index + 1].concrete_surface_strain
        def negative_torque(e2: float) -> float:
            return -solve_state(section, material, e2, seed=states[index]).torque_Nmm
        refined = minimize_scalar(negative_torque, bounds=(lo, hi), method="bounded", options={"xatol": 1e-12})
        if not refined.success:
            raise ReferenceConvergenceError("Reference peak refinement did not converge.")
        peak = solve_state(section, material, float(refined.x), seed=states[index])
    return ReferenceCurve(section, material, tuple(states), peak, status, stop)


@dataclass(frozen=True)
class CellResources:
    """Supply IDs must refer to actual shared inventories, not arbitrary new IDs."""
    concrete_id: str
    longitudinal_id: str
    transverse_id: str


@dataclass(frozen=True)
class SharedTwistReference:
    twist_rad_per_mm: tuple[float, ...]
    torque_Nmm: tuple[float, ...]
    component_torques_Nmm: tuple[tuple[float, ...], ...]
    sampled_peak_Nmm: float
    resource_totals: tuple[tuple[str, float], ...]
    status: str = "IDEAL_COMMON_TWIST_REFERENCE_ONLY"
    production_accepted: bool = False


def combine_at_common_twist(curves: Sequence[ReferenceCurve], allocations: Sequence[CellResources],
                            resource_limits: Mapping[str, float]) -> SharedTwistReference:
    """Reference sum at equal twist, NOT the sum of independent peak torques.

    This is the numerical assembly rule from Bernardo (2019),
    doi:10.3390/app9132730. No actual joint law or U closure is supplied here.
    The caller must state concrete/steel inventories; allocated quantities are
    derived from each rectangle. All cells stop at the first component's end;
    no post-failure redistribution or extrapolation is implied.
    """
    if len(curves) < 2 or len(allocations) != len(curves):
        raise ValueError("At least two curves and one resource record per curve are required.")
    totals: dict[str, float] = {}
    roles: dict[str, str] = {}
    for curve, resource in zip(curves, allocations):
        if curve.branch_status != "NUMERICALLY_COMPLETE":
            raise ReferenceScopeError("An incomplete component branch cannot be used as a complete common-twist reference.")
        s = curve.section
        for role, key, quantity in (("concrete_mm2", resource.concrete_id, s.area_mm2),
                                    ("longitudinal_mm2", resource.longitudinal_id, s.longitudinal_area_mm2),
                                    ("transverse_mm2_per_mm", resource.transverse_id, s.transverse_one_leg_area_per_spacing_mm)):
            if not isinstance(key, str) or not key or key not in resource_limits:
                raise ValueError("Every allocated resource requires an explicit nonempty inventory ID and limit.")
            if key in roles and roles[key] != role:
                raise ValueError("A resource ID cannot mix concrete, longitudinal and transverse units.")
            roles[key] = role
            totals[key] = totals.get(key, 0.0) + quantity
    for key, value in totals.items():
        limit = _finite(resource_limits[key], f"inventory {key}", positive=True)
        if value > limit * (1 + 1e-12):
            raise ReferenceScopeError(f"Resource {key} is counted more than its available inventory.")
    components: list[tuple[np.ndarray, np.ndarray]] = []
    for curve in curves:
        # Include the refined peak; retain continuation order. Sorting the whole
        # curve could hide snap-back / multi-valued torque at a shared twist.
        points = sorted((*curve.states, curve.postcracking_peak), key=lambda q: q.concrete_surface_strain)
        unique: list[ReferenceState] = []
        for point in points:
            if not unique or point.concrete_surface_strain > unique[-1].concrete_surface_strain:
                unique.append(point)
        twists = np.asarray([q.twist_rad_per_mm for q in unique])
        if np.any(np.diff(twists) <= 0):
            raise ReferenceScopeError("Nonmonotonic twist requires an explicit branch choice; it is not sorted away.")
        components.append((twists, np.asarray([q.torque_Nmm for q in unique])))
    lo, hi = max(x[0] for x, _ in components), min(x[-1] for x, _ in components)
    if lo >= hi:
        raise ReferenceScopeError("Component continuation intervals do not overlap in twist.")
    grid = np.unique(np.concatenate(([lo, hi], *[x[(x >= lo) & (x <= hi)] for x, _ in components])))
    torques = tuple(tuple(float(v) for v in np.interp(grid, x, y)) for x, y in components)
    combined = np.sum(np.asarray(torques), axis=0)
    return SharedTwistReference(tuple(float(v) for v in grid), tuple(float(v) for v in combined), torques,
                                float(max(combined)), tuple(sorted(totals.items())))
