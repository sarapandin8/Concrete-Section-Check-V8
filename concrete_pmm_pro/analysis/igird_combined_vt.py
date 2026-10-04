"""Concurrent solid I-girder V+T checks, AASHTO LRFD 9th (2020).

Source: supplied SECTION 5, printed pp. 5-75--5-78. Units: N, mm, MPa.
This module does not change standalone Shear, Torsion, or Flexure solvers.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from shapely.geometry import Point

from concrete_pmm_pro.code_checks.aashto_lrfd import aashto_alpha1, aashto_beta1
from concrete_pmm_pro.core.analysis import AnalysisInput
from concrete_pmm_pro.geometry.summary import to_shapely_polygon
from concrete_pmm_pro.analysis.strain_compatibility import (
    compression_block_polygon, projection_frame, rebar_net_force_n, steel_strain_at_point,
)
from concrete_pmm_pro.analysis.prestress_stress import prestress_stress_mpa

RESULT_VERSION = "IGIRDER.VTQA1.concurrent-vt-partial-results"
DEVELOPMENT_KEY = "igird_longitudinal_development_settings"


def development_settings(state: Mapping) -> dict:
    raw = state.get(DEVELOPMENT_KEY)
    if not isinstance(raw, Mapping):
        raw = (state.get("project_metadata") or {}).get(DEVELOPMENT_KEY, {})
    if not raw:
        legacy = state.get("igird_flexure_development_settings")
        if not isinstance(legacy, Mapping):
            legacy = (state.get("project_metadata") or {}).get("igird_flexure_development_settings", {})
        if isinstance(legacy, Mapping):
            raw = {
                "continuous_full_span_confirmed": legacy.get("bars_continuous_confirmed", False),
                "left_end_anchored_confirmed": legacy.get("left_bar_anchored", False),
                "right_end_anchored_confirmed": legacy.get("right_bar_anchored", False),
                "development_length_mm": legacy.get("bar_ld_mm", 0.0),
                "note": legacy.get("note", ""),
            }
    raw = raw if isinstance(raw, Mapping) else {}
    try:
        ld = float(raw.get("development_length_mm", 0.0))
    except (TypeError, ValueError):
        ld = 0.0
    return {
        "continuous_full_span_confirmed": bool(raw.get("continuous_full_span_confirmed", False)),
        "left_end_anchored_confirmed": bool(raw.get("left_end_anchored_confirmed", False)),
        "right_end_anchored_confirmed": bool(raw.get("right_end_anchored_confirmed", False)),
        "development_length_mm": ld if math.isfinite(ld) and ld >= 0 else 0.0,
        "note": str(raw.get("note") or ""),
    }


def ordinary_development_factor(settings: Mapping, *, x_m: float, span_m: float) -> float | None:
    """Common conservative ld for existing full-span bars; never assume anchorage.

    Engineer enters the governing verified straight-bar development length
    under 5.10.8.2.1a. Confirmed end anchorage removes that end's build-up only.
    No new torsion-only bar identity or reinforcement table is introduced.
    """
    if not bool(settings.get("continuous_full_span_confirmed")):
        return None
    if not all(math.isfinite(v) for v in [x_m, span_m]) or span_m <= 0 or not 0 <= x_m <= span_m:
        return None
    left = bool(settings.get("left_end_anchored_confirmed"))
    right = bool(settings.get("right_end_anchored_confirmed"))
    if left and right:
        return 1.0
    ld = float(settings.get("development_length_mm", 0.0))
    if not math.isfinite(ld) or ld <= 0:
        return None
    lf = 1.0 if left else min(1.0, 1000.0 * x_m / ld)
    rf = 1.0 if right else min(1.0, 1000.0 * (span_m - x_m) / ld)
    return max(0.0, min(lf, rf))


def nominal_tension_fps(
    analysis_input: AnalysisInput, *, moment_sign: float, axial_nominal_N: float,
    tension_y_mid_mm: float,
) -> dict:
    """Exact-axis nominal AASHTO equilibrium for the fps source, not a new Mn check.

    Reuses the accepted AASHTO stress block and bonded-steel constitutive
    model. Nominal axial equilibrium Pn = Nu/phi uses the phi in 5.7.3.6.3-1.
    Minimum nominal fps over tension-side groups is a conservative lower
    bound for summing developed Aps*fps; no fpu resistance is invented.
    """
    polygon = to_shapely_polygon(analysis_input.section_geometry)
    sign = -1.0 if moment_sign < 0 else 1.0
    frame = projection_frame(polygon, sign * math.pi / 2.0)
    fc = float(analysis_input.concrete_material.fc_MPa)
    ecu = float(analysis_input.concrete_material.ecu)
    block_stress = aashto_alpha1(fc) * fc
    beta = aashto_beta1(fc)
    materials = {m.name: m for m in analysis_input.rebar_materials}
    rebars = analysis_input.rebars if analysis_input.settings.include_rebars else []
    elements = analysis_input.prestress_elements if analysis_input.settings.include_prestress else []
    for bar in rebars:
        if bar.material_name not in materials:
            return {"ready": False, "note": f"Unresolved longitudinal material: {bar.material_name}."}
    if any(not e.bonded for e in elements):
        return {"ready": False, "note": "Unbonded prestress is outside this pretensioned I-Girder fps source."}

    def evaluate(c: float) -> tuple[float, list[float]]:
        region = compression_block_polygon(polygon, frame, beta * c)
        pn = block_stress * region.area
        for bar in rebars:
            mat = materials[bar.material_name]
            strain = steel_strain_at_point(bar.x_mm, bar.y_mm, frame, c, ecu)
            fs = max(-mat.fy_MPa, min(mat.fy_MPa, mat.Es_MPa * strain))
            # Same displaced-concrete policy as the accepted section engine.
            inside = region.covers(Point(bar.x_mm, bar.y_mm))
            force, _ = rebar_net_force_n(bar.area_mm2, fs, fc, inside,
                analysis_input.settings.subtract_rebar_displaced_concrete, concrete_stress_MPa=block_stress)
            pn += force
        tension_fps = []
        for element in elements:
            fpu = element.fpu_mpa
            if fpu is None or element.ep_mpa <= 0:
                raise ValueError("Nominal fps requires finite strand fpu and Ep.")
            initial = element.initial_strain
            if initial is None:
                initial = (element.initial_stress_mpa or element.pe_eff_n / element.area_mm2) / element.ep_mpa
            eps = steel_strain_at_point(element.x_mm, element.y_mm, frame, c, ecu)
            fps, _ = prestress_stress_mpa(initial - eps, element.ep_mpa, fpu,
                element.fpy_mpa, analysis_input.settings.prestress_stress_model)
            pn -= element.total_area_mm2 * fps
            on_side = element.y_mm <= tension_y_mid_mm if sign > 0 else element.y_mm >= tension_y_mid_mm
            if on_side:
                tension_fps.append(fps)
        return float(pn), tension_fps

    h = max(1.0, polygon.bounds[3] - polygon.bounds[1])
    lo, hi = h * 1e-8, h * 100.0
    try:
        flo = evaluate(lo)[0] - axial_nominal_N
        fhi = evaluate(hi)[0] - axial_nominal_N
        if not math.isfinite(flo + fhi) or flo > 0 or fhi < 0:
            return {"ready": False, "note": "Nominal axial equilibrium has no bracket; review axial-flexural scope."}
        for _ in range(90):
            mid = 0.5 * (lo + hi)
            residual = evaluate(mid)[0] - axial_nominal_N
            if abs(residual) <= max(0.1, abs(axial_nominal_N) * 1e-9):
                break
            if residual > 0:
                hi = mid
            else:
                lo = mid
        pn, fps_values = evaluate(mid)
    except (ValueError, TypeError) as exc:
        return {"ready": False, "note": str(exc)}
    if not fps_values:
        return {"ready": False, "note": "No nominal tension-side strand stress source is available."}
    if abs(pn - axial_nominal_N) > max(0.1, abs(axial_nominal_N) * 1e-9):
        return {"ready": False, "note": "Nominal axial equilibrium residual exceeds tolerance."}
    return {"ready": True, "fps_min_MPa": min(fps_values) if fps_values else 0.0,
        "c_mm": mid, "residual_N": pn - axial_nominal_N,
        "note": "fps = minimum tension-side nominal AASHTO strain-compatible strand stress; developed Aps uses the conservative fps=fpu development-length screen, not fpu resistance."}


def concurrent_vt_si(
    *, mu_Nmm: float, nu_compression_positive_N: float, vu_N: float, tu_Nmm: float,
    phi: float, fc_MPa: float, bv_mm: float, dv_mm: float, Ao_mm2: float,
    ph_mm: float, fy_MPa: float, cot_theta: float, vc_N: float,
    avs_provided: float, ats_required: float, avs_minimum: float,
    aps_fps_N: float, as_fy_N: float, lambda_duct: float = 1.0, vp_N: float = 0.0,
) -> dict:
    """5.7.3.6.1 sum and exact 5.7.3.6.3-1 concurrent longitudinal force.

    A single physical closed hoop supplies Av/s; adding 2At/s to that same
    provided hoop would count it twice. Torsion allocation is subtracted
    before any Vs relief is credited in the longitudinal equation.
    """
    positive = [phi, fc_MPa, bv_mm, dv_mm, fy_MPa, cot_theta, lambda_duct]
    if abs(tu_Nmm) > 0:
        positive += [Ao_mm2, ph_mm]
    finite = [mu_Nmm, nu_compression_positive_N, vu_N, tu_Nmm, vp_N]
    nonnegative = [vc_N, avs_provided, ats_required, avs_minimum, aps_fps_N, as_fy_N]
    if not all(math.isfinite(v) and v > 0 for v in positive):
        raise ValueError("Concurrent V+T positive source terms are invalid.")
    if not all(math.isfinite(v) for v in finite) or not all(math.isfinite(v) and v >= 0 for v in nonnegative):
        raise ValueError("Concurrent V+T actions/resistance terms must be finite.")
    vu, tu = abs(vu_N), abs(tu_Nmm)
    shear_req = max(0.0, (vu / phi - vp_N - vc_N) / (fy_MPa * dv_mm * cot_theta * lambda_duct))
    # Min shear reinforcement and concurrent torsion must both be supplied.
    required = max(shear_req, avs_minimum) + 2.0 * ats_required
    available_shear = max(0.0, avs_provided - 2.0 * ats_required)
    vs_nominal = available_shear * fy_MPa * dv_mm * cot_theta * lambda_duct
    vs_used = min(vs_nominal, vu / phi)  # 5.7.3.5 definition, amended by 5.7.3.6.3.
    shear_term = abs(vu / phi - vp_N) - 0.5 * vs_used
    torsion_term = 0.45 * ph_mm * tu / (2.0 * Ao_mm2 * phi) if tu > 0 else 0.0
    mu_term = abs(mu_Nmm) / (phi * dv_mm)
    nu_aashto = -nu_compression_positive_N
    nu_term = 0.5 * nu_aashto / phi
    diagonal_term = cot_theta * math.hypot(shear_term, torsion_term)
    rhs_raw = mu_term + nu_term + diagonal_term
    rhs = max(0.0, rhs_raw)
    resistance = aps_fps_N + as_fy_N
    veff = math.hypot(vu, 0.9 * ph_mm * tu / (2.0 * Ao_mm2)) if tu > 0 else vu
    # Additional conservative Veff compression limit; explicitly a guard,
    # not the former ACI Aoh/ph stress expression.
    strut_dc = veff / (phi * (0.25 * fc_MPa * bv_mm * dv_mm + vp_N))
    transverse_dc = required / avs_provided if avs_provided > 0 else float("inf")
    long_dc = rhs / resistance if resistance > 0 else (0.0 if rhs == 0 else float("inf"))
    return {"shear_required": shear_req, "combined_required": required,
        "provided_physical": avs_provided, "available_shear": available_shear,
        "vs_nominal_N": vs_nominal, "vs_used_N": vs_used, "shear_term_N": shear_term,
        "torsion_term_N": torsion_term, "mu_term_N": mu_term, "nu_term_N": nu_term,
        "diagonal_term_N": diagonal_term, "longitudinal_rhs_raw_N": rhs_raw,
        "longitudinal_required_N": rhs, "longitudinal_resistance_N": resistance,
        "transverse_dc": transverse_dc, "longitudinal_dc": long_dc,
        "strut_dc": strut_dc, "veff_N": veff}
