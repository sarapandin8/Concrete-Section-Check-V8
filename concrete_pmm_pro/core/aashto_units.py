"""AASHTO LRFD imperial-to-SI conversion helpers.

AASHTO LRFD Section 5 is written in kips, inches, and ksi while Concrete
Section Pro keeps all solver internals in SI engineering units:
mm, MPa (= N/mm^2), N, and N-mm.

Do not substitute MPa directly into equations written for ksi.  Route AASHTO
coefficient expressions through these helpers or explicitly document the SI
coefficient derivation in the code basis note.
"""

from __future__ import annotations

import math

KSI_TO_MPA = 6.894757293168361
MPA_TO_KSI = 1.0 / KSI_TO_MPA
KIP_TO_N = 4448.2216152605
N_TO_KIP = 1.0 / KIP_TO_N
IN_TO_MM = 25.4
MM_TO_IN = 1.0 / IN_TO_MM
FT_TO_MM = 304.8
MM_TO_FT = 1.0 / FT_TO_MM


def ksi_to_mpa(value_ksi: float) -> float:
    """Convert stress from ksi to MPa."""

    return float(value_ksi) * KSI_TO_MPA


def mpa_to_ksi(value_mpa: float) -> float:
    """Convert stress from MPa to ksi."""

    return float(value_mpa) * MPA_TO_KSI


def kip_to_n(value_kip: float) -> float:
    """Convert force from kip to N."""

    return float(value_kip) * KIP_TO_N


def n_to_kip(value_n: float) -> float:
    """Convert force from N to kip."""

    return float(value_n) * N_TO_KIP


def inch_to_mm(value_in: float) -> float:
    """Convert length from inch to mm."""

    return float(value_in) * IN_TO_MM


def mm_to_inch(value_mm: float) -> float:
    """Convert length from mm to inch."""

    return float(value_mm) * MM_TO_IN


def in2_to_mm2(value_in2: float) -> float:
    """Convert area from in^2 to mm^2."""

    return float(value_in2) * IN_TO_MM**2


def mm2_to_in2(value_mm2: float) -> float:
    """Convert area from mm^2 to in^2."""

    return float(value_mm2) * MM_TO_IN**2


def kip_in_to_n_mm(value_kip_in: float) -> float:
    """Convert moment from kip-in to N-mm."""

    return float(value_kip_in) * KIP_TO_N * IN_TO_MM


def n_mm_to_kip_in(value_n_mm: float) -> float:
    """Convert moment from N-mm to kip-in."""

    return float(value_n_mm) * N_TO_KIP * MM_TO_IN


def kip_ft_to_n_mm(value_kip_ft: float) -> float:
    """Convert moment from kip-ft to N-mm."""

    return float(value_kip_ft) * KIP_TO_N * FT_TO_MM


def n_mm_to_kip_ft(value_n_mm: float) -> float:
    """Convert moment from N-mm to kip-ft."""

    return float(value_n_mm) * N_TO_KIP * MM_TO_FT


def aashto_sqrt_fc_stress_mpa(coefficient_ksi: float, fc_mpa: float) -> float:
    """Return ``coefficient * sqrt(f'c)`` stress in MPa for AASHTO ksi equations.

    Many AASHTO concrete equations are expressed as a numeric coefficient times
    ``sqrt(f'c)`` with ``f'c`` in ksi and the resulting stress in ksi.  Concrete
    Section Pro stores ``f'c`` in MPa.  This helper converts ``f'c`` to ksi,
    evaluates the AASHTO expression in ksi, then converts the result back to MPa.
    """

    fc_ksi = mpa_to_ksi(fc_mpa)
    if fc_ksi < 0.0:
        raise ValueError("fc_mpa must be nonnegative.")
    return ksi_to_mpa(float(coefficient_ksi) * math.sqrt(fc_ksi))


def si_coefficient_for_aashto_sqrt_fc_stress(coefficient_ksi: float) -> float:
    """Return SI coefficient for ``C * sqrt(f'c_MPa)`` equivalent stress.

    This is provided only for documented derivations.  Prefer
    ``aashto_sqrt_fc_stress_mpa`` in solver code so the imperial basis remains
    visible and auditable.
    """

    return float(coefficient_ksi) * math.sqrt(KSI_TO_MPA)
