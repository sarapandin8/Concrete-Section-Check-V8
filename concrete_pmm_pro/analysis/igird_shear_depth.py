"""Developed flexural force resultants for AASHTO 5.7.2.8 I-girder dv.

Shear depth is evaluated at the physical station, using the resisting section
and available longitudinal steel. C5.7.2.8 requires kappa=2 for debonded
strand development in this calculation. No area-centroid d substitutes for de.
"""
from __future__ import annotations

from collections.abc import Mapping
import math

from concrete_pmm_pro.analysis.igird_flexure_development import (
    SectionEquilibrium, strand_stress_limit,
)
from concrete_pmm_pro.analysis.igird_combined_vt import ordinary_development_factor

RESULT_VERSION = "IGIRDER.DECKULS1.developed-composite-depth"


def developed_shear_depth(context: SectionEquilibrium, families: tuple, *,
        reference: Mapping, x_m: float, span_m: float, nu_n: float,
        precast_depth_mm: float, ordinary_settings: Mapping, bar_factors=None, bar_source_ready=True) -> dict:
    caps, transfer, trace = [], [], []
    for i, family in enumerate(families):
        element = family.element
        limit = strand_stress_limit(distance_mm=family.bonded_distance_mm(x_m),
            db_mm=family.db_mm, fpe_mpa=element.pe_eff_n / element.area_mm2,
            fps_mpa=max(float(reference["fps_MPa"][i]), 1e-6), depth_mm=precast_depth_mm,
            debonded=family.debonded, service_condition="tension")
        caps.append(limit["fpx_limit_MPa"])
        transfer.append(limit["transfer_factor"])
        trace.append({"Family": family.name, "bonded_distance_mm": family.bonded_distance_mm(x_m),
            "Count": element.count, **limit})
    ordinary = ordinary_development_factor(ordinary_settings, x_m=x_m, span_m=span_m) if context.bars else 1.0
    factors = list(bar_factors) if bar_factors is not None else [ordinary or 0.0] * len(context.bars)
    result = context.solve(nu_n, strand_caps=caps, transfer_factors=transfer, bar_factors=factors)
    forces = context.force_resultants(result, bar_factors=factors)
    lower = max(0.9 * forces["de_mm"], 0.72 * context.h)
    dv = max(forces["lever_arm_mm"], lower)
    if not math.isfinite(dv) or dv <= 0 or dv > context.h:
        raise ValueError("Developed shear depth is outside the resisting section.")
    return {"dv_mm": dv, "h_mm": context.h, "lower_bound_mm": lower,
        "c_mm": result["c_mm"], "a_mm": result["a_mm"], "Mn_Nmm": result["Mn_Nmm"],
        "Pn_N": result["Pn_N"], "residual_N": result["residual_N"],
        "fps_MPa": result["fps_MPa"], "strand_development_trace": trace,
        "ordinary_factor": ordinary, "bar_source_ready":bar_source_ready, **forces}
