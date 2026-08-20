"""AASHTO LRFD 9th Ed. girder/slab interface-shear checks in native SI units.

IGIRDER.ULS4 keeps the source equations traceable to AASHTO 5.7.4 while the
application itself remains N-mm-MPa.  US-customary source constants are
converted once at the module boundary; no ksi-valued magic numbers are used in
SI equilibrium calculations.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

KSI_TO_MPA = 6.894757293168361
INTERFACE_FY_CAP_KSI = 60.0
INTERFACE_FY_CAP_MPA = INTERFACE_FY_CAP_KSI * KSI_TO_MPA
MIN_REINF_COEFF_KSI = 0.05
MIN_REINF_COEFF_MPA = MIN_REINF_COEFF_KSI * KSI_TO_MPA
ROUGHENED_WAIVER_STRESS_KSI = 0.210
ROUGHENED_WAIVER_STRESS_MPA = ROUGHENED_WAIVER_STRESS_KSI * KSI_TO_MPA
DEFAULT_PHI_SHEAR = 0.90
DESIGN_STRIP_LENGTH_MM = 1000.0

SURFACE_ROUGHENED_GIRDER_SLAB = "roughened_girder_slab"
SURFACE_CLEAN_NOT_ROUGHENED = "clean_not_roughened"


@dataclass(frozen=True)
class InterfaceSurfacePreset:
    key: str
    label: str
    c_source_ksi: float
    mu: float
    k1: float
    k2_source_ksi_normal: float
    k2_source_ksi_lightweight: float | None = None
    roughness_note: str = ""

    def constants_si(self, *, lightweight: bool = False) -> dict[str, float]:
        k2_ksi = (
            self.k2_source_ksi_lightweight
            if lightweight and self.k2_source_ksi_lightweight is not None
            else self.k2_source_ksi_normal
        )
        return {
            "c_MPa": self.c_source_ksi * KSI_TO_MPA,
            "mu": self.mu,
            "K1": self.k1,
            "K2_MPa": k2_ksi * KSI_TO_MPA,
            "c_source_ksi": self.c_source_ksi,
            "K2_source_ksi": k2_ksi,
        }


SURFACE_PRESETS: dict[str, InterfaceSurfacePreset] = {
    SURFACE_ROUGHENED_GIRDER_SLAB: InterfaceSurfacePreset(
        key=SURFACE_ROUGHENED_GIRDER_SLAB,
        label="CIP slab on clean girder · intentionally roughened 6.35 mm (0.25 in)",
        c_source_ksi=0.28,
        mu=1.0,
        k1=0.30,
        k2_source_ksi_normal=1.80,
        k2_source_ksi_lightweight=1.30,
        roughness_note="AASHTO 5.7.4.4 special girder/slab surface; 0.25 in roughness = 6.35 mm.",
    ),
    SURFACE_CLEAN_NOT_ROUGHENED: InterfaceSurfacePreset(
        key=SURFACE_CLEAN_NOT_ROUGHENED,
        label="Clean concrete interface · not intentionally roughened",
        c_source_ksi=0.075,
        mu=0.60,
        k1=0.20,
        k2_source_ksi_normal=0.80,
        roughness_note="AASHTO 5.7.4.4 clean, free-of-laitance interface without intentional roughening.",
    ),
}


def surface_preset(key: str | None) -> InterfaceSurfacePreset:
    return SURFACE_PRESETS.get(str(key or ""), SURFACE_PRESETS[SURFACE_ROUGHENED_GIRDER_SLAB])


def provided_interface_reinforcement_mm2_per_m(*, bar_area_mm2: float, legs: float, spacing_mm: float) -> float:
    if not all(math.isfinite(v) and v > 0.0 for v in (bar_area_mm2, legs, spacing_mm)):
        return float("nan")
    return float(bar_area_mm2) * float(legs) * DESIGN_STRIP_LENGTH_MM / float(spacing_mm)


def interface_shear_demand_si(*, vu_kN: float, bvi_mm: float, dv_mm: float) -> dict[str, float]:
    """AASHTO 5.7.4.5 demand using N-mm-MPa.

    vui = Vu1/(bvi*dv).  A one-metre design strip is used for force comparison.
    """
    if not (math.isfinite(vu_kN) and math.isfinite(bvi_mm) and bvi_mm > 0.0 and math.isfinite(dv_mm) and dv_mm > 0.0):
        return {"vui_MPa": float("nan"), "Vui_kN_per_m": float("nan"), "Vui_N": float("nan")}
    vu_n = abs(float(vu_kN)) * 1000.0
    vui = vu_n / (float(bvi_mm) * float(dv_mm))
    acv = float(bvi_mm) * DESIGN_STRIP_LENGTH_MM
    vui_n = vui * acv
    return {"vui_MPa": vui, "Vui_kN_per_m": vui_n / 1000.0, "Vui_N": vui_n}


def interface_shear_resistance_si(
    *,
    bvi_mm: float,
    fc_weaker_MPa: float,
    avf_provided_mm2_per_m: float,
    fy_MPa: float,
    surface_key: str = SURFACE_ROUGHENED_GIRDER_SLAB,
    lightweight: bool = False,
    phi: float = DEFAULT_PHI_SHEAR,
    pc_N_per_m: float = 0.0,
) -> dict[str, float | str]:
    """Return AASHTO 5.7.4.3 resistance for a 1000-mm interface strip."""
    if not all(math.isfinite(v) and v > 0.0 for v in (bvi_mm, fc_weaker_MPa, phi)):
        raise ValueError("bvi_mm, fc_weaker_MPa, and phi must be positive finite values")
    avf = max(0.0, float(avf_provided_mm2_per_m)) if math.isfinite(avf_provided_mm2_per_m) else 0.0
    fy_eff = min(max(0.0, float(fy_MPa)) if math.isfinite(fy_MPa) else 0.0, INTERFACE_FY_CAP_MPA)
    pc = max(0.0, float(pc_N_per_m)) if math.isfinite(pc_N_per_m) else 0.0
    preset = surface_preset(surface_key)
    const = preset.constants_si(lightweight=lightweight)
    acv = float(bvi_mm) * DESIGN_STRIP_LENGTH_MM
    base = float(const["c_MPa"]) * acv + float(const["mu"]) * (avf * fy_eff + pc)
    cap_fc = float(const["K1"]) * float(fc_weaker_MPa) * acv
    cap_k2 = float(const["K2_MPa"]) * acv
    nominal = min(base, cap_fc, cap_k2)
    factored = float(phi) * nominal
    governing = "Eq. 5.7.4.3-3"
    if nominal == cap_fc and cap_fc <= base + 1.0e-6 and cap_fc <= cap_k2 + 1.0e-6:
        governing = "Eq. 5.7.4.3-4 K1 f'c cap"
    elif nominal == cap_k2 and cap_k2 <= base + 1.0e-6 and cap_k2 <= cap_fc + 1.0e-6:
        governing = "Eq. 5.7.4.3-5 K2 cap"
    return {
        "Acv_mm2_per_m": acv,
        "fy_used_MPa": fy_eff,
        "fy_cap_MPa": INTERFACE_FY_CAP_MPA,
        "c_MPa": float(const["c_MPa"]),
        "mu": float(const["mu"]),
        "K1": float(const["K1"]),
        "K2_MPa": float(const["K2_MPa"]),
        "c_source_ksi": float(const["c_source_ksi"]),
        "K2_source_ksi": float(const["K2_source_ksi"]),
        "Vni_base_N": base,
        "Vni_cap_fc_N": cap_fc,
        "Vni_cap_k2_N": cap_k2,
        "Vni_N": nominal,
        "Vri_N": factored,
        "vri_MPa": factored / acv,
        "Vri_kN_per_m": factored / 1000.0,
        "governing_resistance": governing,
        "surface_label": preset.label,
    }


def minimum_interface_reinforcement_si(
    *,
    bvi_mm: float,
    fy_MPa: float,
    demand_Vui_N_per_m: float,
    c_MPa: float,
    mu: float,
    phi: float = DEFAULT_PHI_SHEAR,
    pc_N_per_m: float = 0.0,
) -> dict[str, float]:
    """AASHTO 5.7.4.2 minimum Avf for a 1000-mm design strip.

    The minimum need not exceed the amount required to resist 1.33 Vui/phi by
    Eq. 5.7.4.3-3.  The special roughened girder/slab waiver is *not* silently
    applied here; callers may report its eligibility separately.
    """
    if not all(math.isfinite(v) and v > 0.0 for v in (bvi_mm, fy_MPa, phi)):
        return {"Avf_min_eq_mm2_per_m": float("nan"), "Avf_min_1p33_mm2_per_m": float("nan"), "Avf_min_required_mm2_per_m": float("nan")}
    fy_eff = min(float(fy_MPa), INTERFACE_FY_CAP_MPA)
    acv = float(bvi_mm) * DESIGN_STRIP_LENGTH_MM
    avf_eq = MIN_REINF_COEFF_MPA * acv / fy_eff
    target_nominal = 1.33 * max(0.0, float(demand_Vui_N_per_m)) / float(phi)
    cohesion = max(0.0, float(c_MPa)) * acv
    pc = max(0.0, float(pc_N_per_m))
    if mu <= 0.0:
        avf_133 = 0.0 if target_nominal <= cohesion else float("inf")
    else:
        avf_133 = max(0.0, ((target_nominal - cohesion) / float(mu) - pc) / fy_eff)
    required = min(avf_eq, avf_133)
    return {
        "Avf_min_eq_mm2_per_m": avf_eq,
        "Avf_min_1p33_mm2_per_m": avf_133,
        "Avf_min_required_mm2_per_m": required,
    }


def source_unit_trace(surface_key: str, *, lightweight: bool = False) -> dict[str, float]:
    preset = surface_preset(surface_key)
    const = preset.constants_si(lightweight=lightweight)
    return {
        "ksi_to_MPa": KSI_TO_MPA,
        "c_source_ksi": float(const["c_source_ksi"]),
        "c_internal_MPa": float(const["c_MPa"]),
        "K2_source_ksi": float(const["K2_source_ksi"]),
        "K2_internal_MPa": float(const["K2_MPa"]),
        "fy_cap_source_ksi": INTERFACE_FY_CAP_KSI,
        "fy_cap_internal_MPa": INTERFACE_FY_CAP_MPA,
        "min_reinf_coeff_source_ksi": MIN_REINF_COEFF_KSI,
        "min_reinf_coeff_internal_MPa": MIN_REINF_COEFF_MPA,
        "roughened_waiver_source_ksi": ROUGHENED_WAIVER_STRESS_KSI,
        "roughened_waiver_internal_MPa": ROUGHENED_WAIVER_STRESS_MPA,
    }
