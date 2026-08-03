"""Direct ACI 318-19 uniaxial P-M3 strength solver for Portal Frame Crossbeams.

This module is deliberately workflow-scoped.  It does not modify the generic
biaxial PMM surface used by Column/Pier/Wall/Pylon or other member workflows.

The Crossbeam route has one flexural demand axis only (M3 -> section Mx).  The
solver therefore fixes the neutral-axis orientation exactly, evaluates ACI
strain compatibility at a trial neutral-axis depth ``c``, and solves
``phi*Pn(c) = Pu`` by bracketed bisection.  No angular PMM interpolation or
neutral-axis depth grid controls the production answer.

Internal units: mm, MPa (= N/mm2), N, N-mm.  Compression is positive.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from concrete_pmm_pro.analysis.pmm_solver import (
    _clamp,
    _has_active_prestress,
    _initial_prestress_strain,
    _prestress_phi_yield_reference_mpa,
    _rebar_material_for,
    passive_prestress_steel_stress_mpa,
)
from concrete_pmm_pro.analysis.prestress_stress import prestress_stress_mpa, prestress_total_tensile_strain
from concrete_pmm_pro.analysis.strain_compatibility import (
    compression_block_polygon,
    is_point_inside_compression_block,
    projection_frame,
    rebar_net_force_n,
    steel_strain_at_point,
)
from concrete_pmm_pro.code_checks import (
    aci_beta1,
    aci_max_phiPn,
    aci_phi_and_strain_condition,
    nominal_po_rc_prestressed,
)
from concrete_pmm_pro.core.analysis import AnalysisInput
from concrete_pmm_pro.core.models import PrestressElement, RebarMaterial
from concrete_pmm_pro.geometry.summary import to_shapely_polygon


@dataclass(frozen=True)
class CrossbeamUniaxialState:
    moment_sign: float
    theta_rad: float
    c_mm: float
    beta1: float
    a_mm: float
    Pn_N: float
    Mnx_Nmm: float
    phi: float
    phiPn_N: float
    phiMn_Nmm: float
    eps_t: float | None
    strain_condition: str
    concrete_area_mm2: float
    concrete_force_N: float
    ordinary_rebar_force_N: float
    prestress_force_N: float
    rebar_inside_compression_count: int
    rebar_displaced_concrete_subtracted_N: float
    prestress_reached_fpu_cap_count: int
    prestress_compression_reversal_count: int
    max_prestress_stress_MPa: float
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrossbeamUniaxialResult:
    status: str
    message: str
    state: CrossbeamUniaxialState | None
    target_Pu_N: float
    force_residual_N: float | None
    force_residual_ratio: float | None
    iterations: int
    bracket_count: int
    max_phiPn_N: float | None
    axial_dcr: float | None
    warnings: tuple[str, ...] = ()

    @property
    def capacity_phiMn_Nmm(self) -> float | None:
        return None if self.state is None else float(self.state.phiMn_Nmm)

    @property
    def nominal_Mn_Nmm(self) -> float | None:
        return None if self.state is None else abs(float(self.state.Mnx_Nmm))

    @property
    def phi(self) -> float | None:
        return None if self.state is None else float(self.state.phi)


def _dedupe(messages: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item).strip() for item in messages if str(item).strip()))


def _moment_theta(moment_sign: float) -> float:
    # y is positive upward.  Top compression produces positive Mnx (sagging),
    # while bottom compression produces negative Mnx (hogging).
    return 0.5 * math.pi if float(moment_sign) >= 0.0 else 1.5 * math.pi


def _bonded_prestress(analysis_input: AnalysisInput) -> list[PrestressElement]:
    if not analysis_input.settings.include_prestress:
        return []
    return [element for element in analysis_input.prestress_elements if element.bonded]


def _maximum_factored_axial_capacity_N(analysis_input: AnalysisInput) -> float | None:
    """Return the ACI maximum compression strength used for separate axial D/C."""

    polygon = to_shapely_polygon(analysis_input.section_geometry)
    rebars = list(analysis_input.rebars) if analysis_input.settings.include_rebars else []
    prestress = _bonded_prestress(analysis_input)
    default_rebar = (
        analysis_input.rebar_materials[0]
        if analysis_input.rebar_materials
        else RebarMaterial(name="Default", fy_MPa=390.0, Es_MPa=200000.0)
    )
    try:
        po_n = nominal_po_rc_prestressed(
            analysis_input.concrete_material.fc_MPa,
            float(polygon.area),
            rebars,
            default_rebar,
            prestress,
        )
        transverse = analysis_input.settings.transverse_reinforcement
        phi_compression = 0.75 if transverse == "spiral" else 0.65
        return aci_max_phiPn(po_n, phi_compression, transverse)
    except (TypeError, ValueError):
        return None



def crossbeam_uniaxial_axial_dcr(analysis_input: AnalysisInput, *, Pu_N: float) -> float | None:
    """Return the ACI compression axial D/C independently of bending direction."""

    target = float(Pu_N)
    if not math.isfinite(target) or target < 0.0:
        return None
    capacity = _maximum_factored_axial_capacity_N(analysis_input)
    if capacity is None or capacity <= 0.0:
        return None
    return target / capacity

def evaluate_crossbeam_uniaxial_state(
    analysis_input: AnalysisInput,
    *,
    c_mm: float,
    moment_sign: float,
) -> CrossbeamUniaxialState:
    """Evaluate one exact-axis ACI strain-compatible section state."""

    if not math.isfinite(float(c_mm)) or float(c_mm) <= 0.0:
        raise ValueError("Neutral-axis depth c_mm must be finite and positive.")
    sign = -1.0 if float(moment_sign) < 0.0 else 1.0
    theta = _moment_theta(sign)
    settings = analysis_input.settings
    concrete = analysis_input.concrete_material
    polygon = to_shapely_polygon(analysis_input.section_geometry)
    centroid = polygon.centroid
    x_ref = float(centroid.x)
    y_ref = float(centroid.y)
    frame = projection_frame(polygon, theta)

    fc_mpa = float(concrete.fc_MPa)
    ecu = float(concrete.ecu)
    beta1 = float(concrete.beta1) if concrete.beta1 is not None else aci_beta1(fc_mpa)
    a_mm = beta1 * float(c_mm)
    compression_region = compression_block_polygon(polygon, frame, a_mm)
    concrete_area = max(0.0, float(compression_region.area))
    concrete_stress = 0.85 * fc_mpa
    concrete_force = concrete_stress * concrete_area
    if concrete_area > 0.0:
        concrete_centroid = compression_region.centroid
        mnx = concrete_force * (float(concrete_centroid.y) - y_ref)
    else:
        mnx = 0.0
    pn = concrete_force

    eps_t: float | None = None
    eps_t_fy = 420.0
    eps_t_es = 200000.0
    ordinary_rebar_force = 0.0
    rebar_inside_count = 0
    displaced_concrete_n = 0.0
    rebars = list(analysis_input.rebars) if settings.include_rebars else []
    for rebar in rebars:
        material = _rebar_material_for(rebar, analysis_input.rebar_materials)
        eps_s = steel_strain_at_point(rebar.x_mm, rebar.y_mm, frame, float(c_mm), ecu)
        fs = _clamp(material.Es_MPa * eps_s, -material.fy_MPa, material.fy_MPa)
        inside = is_point_inside_compression_block(rebar.x_mm, rebar.y_mm, compression_region)
        force, metadata = rebar_net_force_n(
            rebar.area_mm2,
            fs,
            fc_mpa,
            inside,
            settings.subtract_rebar_displaced_concrete,
            concrete_stress_MPa=concrete_stress,
        )
        if inside:
            rebar_inside_count += 1
        displaced_concrete_n += rebar.area_mm2 * float(metadata["concrete_stress_subtracted_MPa"])
        ordinary_rebar_force += force
        pn += force
        mnx += force * (rebar.y_mm - y_ref)
        if eps_s < 0.0:
            tensile = -eps_s
            if eps_t is None or tensile > eps_t:
                eps_t = tensile
                eps_t_fy = float(material.fy_MPa)
                eps_t_es = float(material.Es_MPa)

    warnings: list[str] = []
    prestress_force = 0.0
    reached_fpu_count = 0
    compression_reversal_count = 0
    max_prestress_stress = 0.0
    for element in _bonded_prestress(analysis_input):
        eps_section = steel_strain_at_point(element.x_mm, element.y_mm, frame, float(c_mm), ecu)
        if _has_active_prestress(element):
            if element.fpu_mpa is None:
                warnings.append(f"{element.label or element.id}: missing fpu; active prestress force omitted.")
                continue
            initial = _initial_prestress_strain(element, warnings)
            total_tensile = prestress_total_tensile_strain(initial, eps_section)
            fps, stress_warnings = prestress_stress_mpa(
                total_tensile,
                element.ep_mpa,
                element.fpu_mpa,
                element.fpy_mpa,
                settings.prestress_stress_model,
            )
            for warning in stress_warnings:
                if "fpu cap" in warning:
                    reached_fpu_count += element.count
                elif "compression reversal" in warning:
                    compression_reversal_count += element.count
                else:
                    warnings.append(f"{element.label or element.id}: {warning}")
            max_prestress_stress = max(max_prestress_stress, float(fps))
            force = -element.total_area_mm2 * float(fps)
        else:
            fs_passive = passive_prestress_steel_stress_mpa(element, eps_section)
            max_prestress_stress = max(max_prestress_stress, abs(float(fs_passive)))
            force = element.total_area_mm2 * float(fs_passive)
        prestress_force += force
        pn += force
        mnx += force * (element.y_mm - y_ref)
        if eps_section < 0.0:
            tensile = -eps_section
            if eps_t is None or tensile > eps_t:
                eps_t = tensile
                eps_t_fy = _prestress_phi_yield_reference_mpa(element)
                eps_t_es = float(element.ep_mpa)

    if settings.use_phi_factor:
        phi, strain_condition = aci_phi_and_strain_condition(
            eps_t,
            eps_t_fy,
            eps_t_es,
            settings.transverse_reinforcement,
        )
    else:
        phi = 1.0
        strain_condition = "phi-not-applied"

    phi_pn = phi * pn
    phi_mn_signed = phi * mnx
    # Capacity is reported as a positive magnitude in the requested direction.
    directional_phi_mn = sign * phi_mn_signed
    if directional_phi_mn < 0.0 and abs(directional_phi_mn) <= 1.0e-6:
        directional_phi_mn = 0.0

    return CrossbeamUniaxialState(
        moment_sign=sign,
        theta_rad=theta,
        c_mm=float(c_mm),
        beta1=beta1,
        a_mm=a_mm,
        Pn_N=pn,
        Mnx_Nmm=mnx,
        phi=phi,
        phiPn_N=phi_pn,
        phiMn_Nmm=directional_phi_mn,
        eps_t=eps_t,
        strain_condition=strain_condition,
        concrete_area_mm2=concrete_area,
        concrete_force_N=concrete_force,
        ordinary_rebar_force_N=ordinary_rebar_force,
        prestress_force_N=prestress_force,
        rebar_inside_compression_count=rebar_inside_count,
        rebar_displaced_concrete_subtracted_N=displaced_concrete_n,
        prestress_reached_fpu_cap_count=reached_fpu_count,
        prestress_compression_reversal_count=compression_reversal_count,
        max_prestress_stress_MPa=max_prestress_stress,
        warnings=_dedupe(warnings),
    )


def _logspace(start: float, stop: float, count: int) -> list[float]:
    if count <= 1 or stop <= start:
        return [float(start)]
    log_start = math.log(float(start))
    log_stop = math.log(float(stop))
    return [math.exp(log_start + (log_stop - log_start) * index / (count - 1)) for index in range(count)]


def _bisect_root(
    analysis_input: AnalysisInput,
    *,
    target_pu_n: float,
    moment_sign: float,
    c_left: float,
    c_right: float,
    force_tolerance_n: float,
    max_iterations: int,
) -> tuple[CrossbeamUniaxialState, int]:
    left = evaluate_crossbeam_uniaxial_state(analysis_input, c_mm=c_left, moment_sign=moment_sign)
    right = evaluate_crossbeam_uniaxial_state(analysis_input, c_mm=c_right, moment_sign=moment_sign)
    f_left = left.phiPn_N - target_pu_n
    f_right = right.phiPn_N - target_pu_n
    if abs(f_left) <= force_tolerance_n:
        return left, 0
    if abs(f_right) <= force_tolerance_n:
        return right, 0
    if f_left * f_right > 0.0:
        raise ValueError("Root bracket does not contain a sign change.")

    best = left if abs(f_left) < abs(f_right) else right
    for iteration in range(1, max_iterations + 1):
        # Bisection is slower than a pure secant method but preserves a strict
        # force-equilibrium bracket through phi-transition regions.
        middle_c = 0.5 * (c_left + c_right)
        middle = evaluate_crossbeam_uniaxial_state(analysis_input, c_mm=middle_c, moment_sign=moment_sign)
        f_middle = middle.phiPn_N - target_pu_n
        if abs(f_middle) < abs(best.phiPn_N - target_pu_n):
            best = middle
        if abs(f_middle) <= force_tolerance_n:
            return middle, iteration
        if abs(c_right - c_left) <= max(1.0e-9, 1.0e-10 * max(abs(middle_c), 1.0)):
            return best, iteration
        if f_left * f_middle <= 0.0:
            c_right = middle_c
            right = middle
            f_right = f_middle
        else:
            c_left = middle_c
            left = middle
            f_left = f_middle
    return best, max_iterations


def solve_crossbeam_uniaxial_flexure(
    analysis_input: AnalysisInput,
    *,
    Pu_N: float,
    moment_sign: float,
    force_tolerance_ratio: float = 1.0e-8,
    max_iterations: int = 120,
) -> CrossbeamUniaxialResult:
    """Solve factored ACI uniaxial capacity at the supplied factored axial force.

    The target equation is ``phi*Pn(c) = Pu``.  All sign-change roots in a wide
    adaptive ``c`` range are solved; the root providing the greatest positive
    directional ``phi*Mn`` is adopted.  This avoids silently selecting a lower
    branch if a phi transition creates more than one numerical crossing.
    """

    target = float(Pu_N)
    if not math.isfinite(target):
        return CrossbeamUniaxialResult(
            status="NOT CHECKED",
            message="Pu must be finite.",
            state=None,
            target_Pu_N=target,
            force_residual_N=None,
            force_residual_ratio=None,
            iterations=0,
            bracket_count=0,
            max_phiPn_N=None,
            axial_dcr=None,
        )

    polygon = to_shapely_polygon(analysis_input.section_geometry)
    frame = projection_frame(polygon, _moment_theta(moment_sign))
    depth = max(frame.projected_depth_mm, 1.0)
    c_min = max(1.0e-3, 1.0e-6 * depth)
    c_max = 10.0 * depth
    force_scale = max(abs(target), 1.0e6)
    force_tolerance = max(1.0, float(force_tolerance_ratio) * force_scale)

    warnings: list[str] = []
    samples: list[CrossbeamUniaxialState] = []
    brackets: list[tuple[float, float]] = []
    for _extension in range(5):
        c_values = _logspace(c_min, c_max, 121)
        samples = [
            evaluate_crossbeam_uniaxial_state(analysis_input, c_mm=value, moment_sign=moment_sign)
            for value in c_values
        ]
        brackets = []
        for left, right in zip(samples[:-1], samples[1:]):
            f_left = left.phiPn_N - target
            f_right = right.phiPn_N - target
            if abs(f_left) <= force_tolerance:
                brackets.append((left.c_mm, left.c_mm))
            elif f_left * f_right < 0.0 or abs(f_right) <= force_tolerance:
                brackets.append((left.c_mm, right.c_mm))
        if brackets or max(state.phiPn_N for state in samples) >= target:
            break
        c_max *= 5.0

    roots: list[tuple[CrossbeamUniaxialState, int]] = []
    seen: set[tuple[int, int]] = set()
    for left_c, right_c in brackets:
        key = (round(left_c * 1.0e6), round(right_c * 1.0e6))
        if key in seen:
            continue
        seen.add(key)
        if abs(right_c - left_c) <= 1.0e-12:
            roots.append((evaluate_crossbeam_uniaxial_state(analysis_input, c_mm=left_c, moment_sign=moment_sign), 0))
        else:
            roots.append(
                _bisect_root(
                    analysis_input,
                    target_pu_n=target,
                    moment_sign=moment_sign,
                    c_left=left_c,
                    c_right=right_c,
                    force_tolerance_n=force_tolerance,
                    max_iterations=max_iterations,
                )
            )

    if not roots:
        nearest = min(samples, key=lambda state: abs(state.phiPn_N - target)) if samples else None
        max_phi_pn_sample = max((state.phiPn_N for state in samples), default=None)
        residual = None if nearest is None else nearest.phiPn_N - target
        residual_ratio = None if residual is None else abs(residual) / force_scale
        max_axial = _maximum_factored_axial_capacity_N(analysis_input)
        axial_dcr = target / max_axial if max_axial and max_axial > 0.0 and target >= 0.0 else None
        return CrossbeamUniaxialResult(
            status="OUT OF RANGE",
            message="Direct uniaxial solver could not bracket phi*Pn = Pu within the adaptive neutral-axis range.",
            state=None,
            target_Pu_N=target,
            force_residual_N=residual,
            force_residual_ratio=residual_ratio,
            iterations=0,
            bracket_count=0,
            max_phiPn_N=max_axial if max_axial is not None else max_phi_pn_sample,
            axial_dcr=axial_dcr,
            warnings=_dedupe(warnings),
        )

    positive_roots = [item for item in roots if item[0].phiMn_Nmm > 0.0]
    candidates = positive_roots or roots
    state, iterations = max(candidates, key=lambda item: item[0].phiMn_Nmm)
    residual = state.phiPn_N - target
    residual_ratio = abs(residual) / force_scale
    warnings.extend(state.warnings)
    if state.prestress_compression_reversal_count:
        warnings.append(
            "Active prestress compression reversal occurred at the governing direct-solver state; "
            "the current tensile-only tendon material model clamps negative total tensile strain to zero."
        )
    if state.phiMn_Nmm <= 0.0:
        status = "NOT CHECKED"
        message = "A positive directional flexural capacity was not obtained for the requested M3 direction."
    elif abs(residual) > force_tolerance:
        status = "REVIEW"
        message = "Direct uniaxial force equilibrium did not meet the production residual tolerance."
    else:
        status = "PASS"
        message = "Direct ACI uniaxial strain compatibility solved phi*Pn = Pu on the exact M3 bending axis."

    max_axial = _maximum_factored_axial_capacity_N(analysis_input)
    axial_dcr = target / max_axial if max_axial and max_axial > 0.0 and target >= 0.0 else None
    return CrossbeamUniaxialResult(
        status=status,
        message=message,
        state=state,
        target_Pu_N=target,
        force_residual_N=residual,
        force_residual_ratio=residual_ratio,
        iterations=iterations,
        bracket_count=len(brackets),
        max_phiPn_N=max_axial,
        axial_dcr=axial_dcr,
        warnings=_dedupe(warnings),
    )
