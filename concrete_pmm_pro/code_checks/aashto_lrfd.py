"""AASHTO LRFD Section 5 concrete strength helpers.

The helpers in this module keep the AASHTO LRFD 9th Edition concrete PMM
route auditable in Concrete Section Pro.  AASHTO Section 5 equations and
limits are expressed in kips, inches, and ksi; the app's solver internals stay
in mm, MPa, N, and N-mm.  Where strength-dependent thresholds are written in
ksi, these helpers convert the SI input to ksi before applying the code rule.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from concrete_pmm_pro.core.aashto_units import aashto_sqrt_fc_stress_mpa, inch_to_mm, ksi_to_mpa, mpa_to_ksi
from concrete_pmm_pro.core.models import PrestressElement, Rebar, RebarMaterial

AASHTO_ECU_STRENGTH = 0.003
AASHTO_COMPRESSION_CONTROLLED_PHI = 0.75
AASHTO_TENSION_CONTROLLED_RC_PHI = 0.90
AASHTO_TENSION_CONTROLLED_BONDED_PRESTRESS_PHI = 1.00
AASHTO_TENSION_CONTROLLED_UNBONDED_PRESTRESS_PHI = 0.90
AASHTO_SHEAR_PHI = 0.90
AASHTO_SHEAR_PHI_PRESTRESSED_DEBONDED = 0.85
AASHTO_SHEAR_SIMPLIFIED_BETA = 2.0
AASHTO_SHEAR_SIMPLIFIED_THETA_DEG = 45.0
AASHTO_SHEAR_MAX_FC_MPA = 103.42135939752542  # 15 ksi
AASHTO_SHEAR_TRANSVERSE_FY_MAX_MPA = 689.4757293168361  # 100 ksi
AASHTO_TORSION_TRANSVERSE_FY_MAX_MPA = ksi_to_mpa(75.0)  # 5.7.2.7, torsion / other elements

AASHTO_SEISMIC_HOOK_FYH_MAX_MPA = 517.106797
AASHTO_SEISMIC_SPACING_MAX_MM = 101.6  # 4 in
AASHTO_SEISMIC_CONFINEMENT_MIN_LENGTH_MM = 457.2  # 18 in


@dataclass(frozen=True)
class AashtoGeneralShearParameters:
    """AASHTO LRFD 5.7.3.4.2 General Procedure beta/theta trace."""

    epsilon_s_raw: float
    epsilon_s_used: float
    beta: float
    theta_deg: float
    has_minimum_transverse_reinforcement: bool
    sxe_mm: float | None
    sxe_in: float | None
    basis: str
    notes: tuple[str, ...] = ()


def aashto_prestressed_shear_phi(*, has_unbonded_or_debonded_strands: bool) -> tuple[float, str]:
    """Return AASHTO LRFD 5.5.4.2 shear/torsion resistance factor for PSC.

    Normal-weight prestressed concrete with bonded strands/tendons uses 0.90.
    If unbonded or debonded strands/tendons are present, the Section 5 branch
    uses 0.85.  The caller owns the project/member classification.
    """

    if has_unbonded_or_debonded_strands:
        return (
            AASHTO_SHEAR_PHI_PRESTRESSED_DEBONDED,
            "AASHTO LRFD 5.5.4.2: prestressed shear/torsion with unbonded or debonded strands/tendons; phi = 0.85",
        )
    return (
        AASHTO_SHEAR_PHI,
        "AASHTO LRFD 5.5.4.2: prestressed shear/torsion with bonded strands/tendons; phi = 0.90",
    )


def aashto_torsion_transverse_design_fy_mpa(fy_input_MPa: float) -> tuple[float, str]:
    """Return design fy for nonprestressed transverse torsion reinforcement.

    AASHTO LRFD 5.7.2.7 permits higher transverse grades for specified
    flexural-shear-only cases, but torsion is outside that exception.  For the
    active prestressed I-Girder torsion route, nonprestressed transverse steel
    with specified yield strength above 60 ksi is therefore limited to the
    stress corresponding to 0.0035 strain and not more than 75 ksi.  With the
    app's elastic-perfectly-plastic reinforcing-steel basis, the controlling
    explicit code cap is 75 ksi.
    """

    fy = float(fy_input_MPa)
    if not math.isfinite(fy) or fy <= 0.0:
        raise ValueError("fy_input_MPa must be positive and finite.")
    design = min(fy, AASHTO_TORSION_TRANSVERSE_FY_MAX_MPA)
    if design < fy - 1.0e-9:
        return (
            design,
            f"AASHTO LRFD 5.7.2.7 torsion branch: transverse design fy limited from {fy:.1f} MPa to 75 ksi ({design:.1f} MPa).",
        )
    return design, "AASHTO LRFD 5.7.2.7 torsion branch: entered transverse fy is within the applicable design limit."


def aashto_general_shear_parameters(
    *,
    epsilon_s: float,
    has_minimum_transverse_reinforcement: bool,
    sxe_mm: float | None = None,
) -> AashtoGeneralShearParameters:
    """Evaluate AASHTO LRFD 5.7.3.4.2 Eqs. 1-3.

    Concrete Section Pro adopts the explicitly permitted negative-strain route
    in Article 5.7.3.4.2: a calculated negative epsilon_s is taken as zero.
    The upper bound is 0.006.  For sections below minimum transverse
    reinforcement, ``sxe`` is dimensional in the source equation (inches), so
    this helper converts the SI input before Eq. 5.7.3.4.2-2.
    """

    eps_raw = float(epsilon_s)
    if not math.isfinite(eps_raw):
        raise ValueError("epsilon_s must be finite.")
    notes: list[str] = []
    if eps_raw < 0.0:
        eps_used = 0.0
        notes.append("Negative epsilon_s taken as zero per the permitted Article 5.7.3.4.2 branch.")
    else:
        eps_used = min(eps_raw, 0.006)
        if eps_raw > 0.006:
            notes.append("epsilon_s limited to 0.006 per Article 5.7.3.4.2.")

    denominator = 1.0 + 750.0 * eps_used
    if denominator <= 0.0:
        raise ValueError("General Procedure epsilon_s produces an invalid beta denominator.")

    sxe_in: float | None = None
    sxe_value_mm: float | None = None
    if has_minimum_transverse_reinforcement:
        beta = 4.8 / denominator
        basis = "AASHTO LRFD 5.7.3.4.2-1 / -3 (section contains at least minimum transverse reinforcement)"
    else:
        if sxe_mm is None or not math.isfinite(float(sxe_mm)) or float(sxe_mm) <= 0.0:
            raise ValueError("sxe_mm is required when the section has less than minimum transverse reinforcement.")
        sxe_value_mm = float(sxe_mm)
        sxe_in = sxe_value_mm / 25.4
        sxe_in_limited = min(max(sxe_in, 12.0), 80.0)
        if abs(sxe_in_limited - sxe_in) > 1.0e-12:
            notes.append(f"sxe limited from {sxe_in:.3f} in to {sxe_in_limited:.3f} in (12-80 in code limits).")
            sxe_in = sxe_in_limited
            sxe_value_mm = sxe_in * 25.4
        beta = (4.8 / denominator) * (51.0 / (39.0 + sxe_in))
        basis = "AASHTO LRFD 5.7.3.4.2-2 / -3 (section contains less than minimum transverse reinforcement)"

    theta_deg = 29.0 + 3500.0 * eps_used
    return AashtoGeneralShearParameters(
        epsilon_s_raw=eps_raw,
        epsilon_s_used=eps_used,
        beta=beta,
        theta_deg=theta_deg,
        has_minimum_transverse_reinforcement=bool(has_minimum_transverse_reinforcement),
        sxe_mm=sxe_value_mm,
        sxe_in=sxe_in,
        basis=basis,
        notes=tuple(notes),
    )


def aashto_pretensioned_transfer_length_mm(db_mm: float) -> float:
    """Return 60db transfer length permitted by AASHTO LRFD 5.9.4.3.1/3.2."""

    if not math.isfinite(float(db_mm)) or float(db_mm) <= 0.0:
        raise ValueError("db_mm must be positive and finite.")
    return 60.0 * float(db_mm)


def aashto_pretensioned_strand_development_length_mm(
    *,
    fps_MPa: float,
    fpe_MPa: float,
    db_mm: float,
    member_depth_mm: float,
    debonded_conservative: bool = False,
) -> tuple[float, float, str]:
    """Return AASHTO LRFD 5.9.4.3.2-1 strand development length in mm.

    The source equation is calibrated in ksi and inches, therefore this helper
    explicitly converts the SI stresses and diameter before evaluating it.
    ``debonded_conservative=True`` applies kappa=2.0, the Article 5.9.4.3.3F
    branch, as a conservative screen when the project has not supplied the
    service-tension classification needed to use a smaller kappa.
    """

    values = [fps_MPa, fpe_MPa, db_mm, member_depth_mm]
    if not all(math.isfinite(float(v)) and float(v) > 0.0 for v in values):
        raise ValueError("fps_MPa, fpe_MPa, db_mm, and member_depth_mm must be positive finite values.")
    if float(fps_MPa) <= float(fpe_MPa):
        raise ValueError("fps_MPa must exceed fpe_MPa for development-length evaluation.")

    depth_in = float(member_depth_mm) / 25.4
    if debonded_conservative:
        kappa = 2.0
        kappa_basis = "kappa=2.0 conservative debonded-strand screen (5.9.4.3.3F)"
    elif depth_in <= 24.0 + 1.0e-12:
        kappa = 1.0
        kappa_basis = "kappa=1.0 for pretensioned member depth <= 24 in"
    else:
        kappa = 1.6
        kappa_basis = "kappa=1.6 for pretensioned member depth > 24 in"

    fps_ksi = mpa_to_ksi(float(fps_MPa))
    fpe_ksi = mpa_to_ksi(float(fpe_MPa))
    db_in = float(db_mm) / 25.4
    ld_in = kappa * (fps_ksi - (2.0 / 3.0) * fpe_ksi) * db_in
    if not math.isfinite(ld_in) or ld_in <= 0.0:
        raise ValueError("AASHTO development-length equation produced a nonpositive length.")
    return inch_to_mm(ld_in), kappa, kappa_basis


def aashto_pretensioned_transfer_fpo_factor(*, bonded_distance_mm: float, db_mm: float) -> float:
    """Linear fpo build-up from bond commencement through the 60db transfer length."""

    if not math.isfinite(float(bonded_distance_mm)) or float(bonded_distance_mm) < 0.0:
        raise ValueError("bonded_distance_mm must be finite and nonnegative.")
    transfer = aashto_pretensioned_transfer_length_mm(float(db_mm))
    return min(max(float(bonded_distance_mm) / transfer, 0.0), 1.0)


def aashto_development_area_factor(*, bonded_distance_mm: float, development_length_mm: float) -> float:
    """Proportional Aps/As development factor for Article 5.7.3.4.2 strain input."""

    if not math.isfinite(float(bonded_distance_mm)) or float(bonded_distance_mm) < 0.0:
        raise ValueError("bonded_distance_mm must be finite and nonnegative.")
    if not math.isfinite(float(development_length_mm)) or float(development_length_mm) <= 0.0:
        raise ValueError("development_length_mm must be positive and finite.")
    return min(max(float(bonded_distance_mm) / float(development_length_mm), 0.0), 1.0)


@dataclass(frozen=True)
class AashtoSeismicConfinementResult:
    status: str
    section_type: str
    s_max_mm: float | None
    suggested_spacing_mm: float | None
    governing_limit: str
    confinement_length_mm: float | None
    spacing_dc: float
    area_dc: float
    provided_transverse_area_mm2: float | None
    required_transverse_area_mm2: float | None
    required_transverse_area_y_mm2: float | None
    provided_rho: float | None
    required_rho: float | None
    core_width_mm: float | None
    core_depth_mm: float | None
    core_area_mm2: float | None
    criteria: tuple[dict[str, object], ...]
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    basis: str = "AASHTO LRFD 9th Article 5.11.4.1.4/5.11.4.1.5"


def aashto_seismic_column_spacing_limit_mm(min_member_dimension_mm: float) -> tuple[float, str]:
    """Return AASHTO LRFD 5.11.4.1.5 confinement spacing limit in mm."""

    if not math.isfinite(float(min_member_dimension_mm)) or float(min_member_dimension_mm) <= 0.0:
        raise ValueError("min_member_dimension_mm must be positive and finite.")
    quarter_dim = 0.25 * float(min_member_dimension_mm)
    four_in = inch_to_mm(4.0)
    if quarter_dim <= four_in:
        return quarter_dim, "0.25 x minimum member dimension"
    return four_in, "4.0 in maximum"


def aashto_seismic_confinement_length_mm(
    *,
    max_member_dimension_mm: float,
    clear_height_mm: float | None = None,
) -> tuple[float, tuple[dict[str, object], ...]]:
    """Return AASHTO LRFD 5.11.4.1.5 plastic-hinge confinement length in mm."""

    if not math.isfinite(float(max_member_dimension_mm)) or float(max_member_dimension_mm) <= 0.0:
        raise ValueError("max_member_dimension_mm must be positive and finite.")
    criteria: list[dict[str, object]] = [
        {"Criterion": "Maximum cross-sectional dimension", "Limit (mm)": float(max_member_dimension_mm), "Basis": "AASHTO LRFD 5.11.4.1.5"},
        {"Criterion": "18.0 in", "Limit (mm)": inch_to_mm(18.0), "Basis": "AASHTO LRFD 5.11.4.1.5"},
    ]
    values = [float(max_member_dimension_mm), inch_to_mm(18.0)]
    if clear_height_mm is not None and math.isfinite(float(clear_height_mm)) and float(clear_height_mm) > 0.0:
        one_sixth = float(clear_height_mm) / 6.0
        criteria.append({"Criterion": "1/6 clear height", "Limit (mm)": one_sixth, "Basis": "AASHTO LRFD 5.11.4.1.5"})
        values.append(one_sixth)
    return max(values), tuple(criteria)


def aashto_seismic_rectangular_ash_required_mm2(
    *,
    fc_MPa: float,
    fyh_MPa: float,
    Ag_mm2: float,
    Ac_mm2: float,
    s_mm: float,
    hc_mm: float,
) -> tuple[float, float, float]:
    """Return required rectangular hoop ``Ash`` by AASHTO 5.11.4.1.4 in SI.

    The AASHTO equations use ksi for both ``fc`` and ``fyh``; the ratio is
    dimensionless, so the app may use MPa/MPa after keeping the same unit in
    numerator and denominator.  ``s`` and ``hc`` are supplied in mm, giving
    ``Ash`` in mm².
    """

    values = [fc_MPa, fyh_MPa, Ag_mm2, Ac_mm2, s_mm, hc_mm]
    if not all(math.isfinite(float(v)) and float(v) > 0.0 for v in values):
        raise ValueError("fc_MPa, fyh_MPa, Ag_mm2, Ac_mm2, s_mm, and hc_mm must be positive finite values.")
    ag_ac = float(Ag_mm2) / float(Ac_mm2)
    eq2 = 0.30 * float(s_mm) * float(hc_mm) * float(fc_MPa) / float(fyh_MPa) * max(0.0, ag_ac - 1.0)
    eq3 = 0.12 * float(s_mm) * float(hc_mm) * float(fc_MPa) / float(fyh_MPa)
    return max(eq2, eq3), eq2, eq3


def aashto_seismic_circular_spiral_required(
    *,
    fc_MPa: float,
    fyh_MPa: float,
    Ag_mm2: float,
    Ac_mm2: float,
    dc_mm: float,
    s_mm: float,
) -> tuple[float, float, float, float]:
    """Return circular spiral/hoop confinement requirement in SI.

    Returns ``(Asp_required_mm2, rho_required, rho_5_11_4_1_4, rho_5_6_4_6)``.
    Article 5.11.4.1.4 gives ``rho >= 0.12 fc/fyh`` and references Article
    5.6.4.6, which gives the familiar ``0.45(Ag/Ac - 1)fc/fyh`` minimum when
    it controls.  The controlling ratio is converted to ``Asp`` from
    ``rho = 4Asp/(dc*s)``.
    """

    values = [fc_MPa, fyh_MPa, Ag_mm2, Ac_mm2, dc_mm, s_mm]
    if not all(math.isfinite(float(v)) and float(v) > 0.0 for v in values):
        raise ValueError("fc_MPa, fyh_MPa, Ag_mm2, Ac_mm2, dc_mm, and s_mm must be positive finite values.")
    rho_511 = 0.12 * float(fc_MPa) / float(fyh_MPa)
    rho_564 = 0.45 * max(0.0, float(Ag_mm2) / float(Ac_mm2) - 1.0) * float(fc_MPa) / float(fyh_MPa)
    rho_req = max(rho_511, rho_564)
    asp_req = rho_req * float(dc_mm) * float(s_mm) / 4.0
    return asp_req, rho_req, rho_511, rho_564


@dataclass(frozen=True)
class AashtoPhiResult:
    phi: float
    strain_condition: str
    eps_cl: float
    eps_tl: float
    tension_phi: float
    basis: str


def aashto_alpha1(fc_MPa: float) -> float:
    """Return AASHTO LRFD rectangular stress-block alpha1 for ``fc_MPa``.

    AASHTO Section 5 defines the strength breakpoints in ksi.  The input is
    converted to ksi before applying the 10 ksi threshold and reduction rate.
    """

    if fc_MPa <= 0:
        raise ValueError("fc_MPa must be positive.")
    fc_ksi = mpa_to_ksi(fc_MPa)
    if fc_ksi <= 10.0:
        return 0.85
    return max(0.75, 0.85 - 0.02 * (fc_ksi - 10.0))


def aashto_beta1(fc_MPa: float) -> float:
    """Return AASHTO LRFD rectangular stress-block beta1 for ``fc_MPa``.

    AASHTO Section 5 defines the strength breakpoints in ksi.  The input is
    converted to ksi before applying the 4 ksi threshold and reduction rate.
    """

    if fc_MPa <= 0:
        raise ValueError("fc_MPa must be positive.")
    fc_ksi = mpa_to_ksi(fc_MPa)
    if fc_ksi <= 4.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_ksi - 4.0))


def _linear_interpolate(value: float, x0: float, y0: float, x1: float, y1: float) -> float:
    if x1 == x0:
        return y0
    ratio = (value - x0) / (x1 - x0)
    return y0 + ratio * (y1 - y0)


def aashto_compression_controlled_strain_limit(
    fy_MPa: float | None = None,
    Es_MPa: float = 200000.0,
    *,
    prestressed_reinforcement: bool = False,
) -> float:
    """Return AASHTO compression-controlled net tensile strain limit.

    Prestressing reinforcement uses 0.002.  Nonprestressed reinforcement uses
    the AASHTO ksi breakpoints for 60 ksi and 100 ksi bars.
    """

    if prestressed_reinforcement:
        return 0.002
    fy = float(fy_MPa if fy_MPa is not None else 420.0)
    Es = float(Es_MPa)
    if fy <= 0:
        raise ValueError("fy_MPa must be positive.")
    if Es <= 0:
        raise ValueError("Es_MPa must be positive.")
    fy_ksi = mpa_to_ksi(fy)
    if fy_ksi <= 60.0:
        return min(fy / Es, 0.002)
    if fy_ksi >= 100.0:
        return 0.004
    return _linear_interpolate(fy_ksi, 60.0, 0.002, 100.0, 0.004)


def aashto_tension_controlled_strain_limit(
    fy_MPa: float | None = None,
    *,
    prestressed_reinforcement: bool = False,
) -> float:
    """Return AASHTO tension-controlled net tensile strain limit."""

    if prestressed_reinforcement:
        return 0.005
    fy = float(fy_MPa if fy_MPa is not None else 420.0)
    if fy <= 0:
        raise ValueError("fy_MPa must be positive.")
    fy_ksi = mpa_to_ksi(fy)
    if fy_ksi <= 75.0:
        return 0.005
    if fy_ksi >= 100.0:
        return 0.008
    return _linear_interpolate(fy_ksi, 75.0, 0.005, 100.0, 0.008)


def aashto_phi_and_strain_condition(
    eps_t: float | None,
    *,
    fy_MPa: float | None = None,
    Es_MPa: float = 200000.0,
    prestressed_member: bool = False,
    prestressed_reinforcement_controls: bool = False,
    unbonded_prestress_controls: bool = False,
) -> AashtoPhiResult:
    """Return AASHTO LRFD φ and strain classification for axial-flexure.

    The interpolation lower bound is 0.75.  The upper bound is 0.90 for
    nonprestressed reinforced concrete, 1.00 for bonded prestressed concrete,
    and 0.90 for unbonded/debonded prestressing when explicitly controlling.
    """

    is_ps_basis = bool(prestressed_member or prestressed_reinforcement_controls or unbonded_prestress_controls)
    eps_cl = aashto_compression_controlled_strain_limit(fy_MPa, Es_MPa, prestressed_reinforcement=is_ps_basis)
    eps_tl = aashto_tension_controlled_strain_limit(fy_MPa, prestressed_reinforcement=is_ps_basis)
    if unbonded_prestress_controls:
        tension_phi = AASHTO_TENSION_CONTROLLED_UNBONDED_PRESTRESS_PHI
        basis = "AASHTO LRFD 5.5.4.2 unbonded/debonded prestressed transition"
    elif is_ps_basis:
        tension_phi = AASHTO_TENSION_CONTROLLED_BONDED_PRESTRESS_PHI
        basis = "AASHTO LRFD 5.5.4.2 bonded prestressed transition"
    else:
        tension_phi = AASHTO_TENSION_CONTROLLED_RC_PHI
        basis = "AASHTO LRFD 5.5.4.2 nonprestressed RC transition"

    eps = 0.0 if eps_t is None else max(0.0, float(eps_t))
    if eps <= eps_cl:
        return AashtoPhiResult(AASHTO_COMPRESSION_CONTROLLED_PHI, "compression-controlled", eps_cl, eps_tl, tension_phi, basis)
    if eps >= eps_tl:
        return AashtoPhiResult(tension_phi, "tension-controlled", eps_cl, eps_tl, tension_phi, basis)
    ratio = (eps - eps_cl) / (eps_tl - eps_cl)
    phi = AASHTO_COMPRESSION_CONTROLLED_PHI + ratio * (tension_phi - AASHTO_COMPRESSION_CONTROLLED_PHI)
    return AashtoPhiResult(phi, "transition", eps_cl, eps_tl, tension_phi, basis)


def _rebar_yield_strength_mpa(rebar: Rebar, default_material: RebarMaterial) -> float:
    return float(getattr(rebar, "fy_MPa", None) or getattr(rebar, "fy_mpa", None) or default_material.fy_MPa)


def _prestress_axial_strength_reference_mpa(element: PrestressElement) -> float:
    if element.fpy_mpa is not None:
        return float(element.fpy_mpa)
    if element.fpu_mpa is not None:
        return 0.90 * float(element.fpu_mpa)
    raise ValueError("Prestress element is missing both fpy_mpa and fpu_mpa.")


def aashto_nominal_po_rc_prestressed(
    fc_MPa: float,
    Ag_mm2: float,
    rebars: list[Rebar],
    rebar_material_default: RebarMaterial | None = None,
    prestress_elements: list[PrestressElement] | None = None,
) -> float:
    """Return AASHTO-style nominal concentric axial resistance in N.

    This SI helper follows the AASHTO compression-member stress coefficient
    ``kc`` basis through ``aashto_alpha1`` and subtracts modeled steel area from
    the concrete term to avoid double counting.  It uses fpy/proof stress for
    prestressing steel when available, otherwise 0.90 fpu as a conservative
    material reference.
    """

    if fc_MPa <= 0:
        raise ValueError("fc_MPa must be positive.")
    if Ag_mm2 <= 0:
        raise ValueError("Ag_mm2 must be positive.")
    default_material = rebar_material_default or RebarMaterial(name="Default", fy_MPa=390.0, Es_MPa=200000.0)
    prestress_items = prestress_elements or []
    Ast_mm2 = sum(rebar.area_mm2 for rebar in rebars)
    Aps_mm2 = sum(element.area_mm2 * element.count for element in prestress_items)
    concrete_area_mm2 = Ag_mm2 - Ast_mm2 - Aps_mm2
    if concrete_area_mm2 < 0:
        raise ValueError("Ag_mm2 minus total rebar and prestress steel area must not be negative.")

    steel_force_N = sum(_rebar_yield_strength_mpa(rebar, default_material) * rebar.area_mm2 for rebar in rebars)
    prestress_force_N = sum(_prestress_axial_strength_reference_mpa(element) * element.area_mm2 * element.count for element in prestress_items)
    return aashto_alpha1(fc_MPa) * fc_MPa * concrete_area_mm2 + steel_force_N + prestress_force_N


def aashto_column_axial_cap_factor(transverse_reinforcement: str) -> float:
    if transverse_reinforcement == "spiral":
        return 0.85
    if transverse_reinforcement == "tied":
        return 0.80
    raise ValueError("transverse_reinforcement must be tied or spiral.")


def aashto_max_phiPn(
    Po_N: float,
    *,
    transverse_reinforcement: str,
    phi_compression: float = AASHTO_COMPRESSION_CONTROLLED_PHI,
) -> float:
    """Return factored axial-resistance cap for compression members in N."""

    if Po_N < 0:
        raise ValueError("Po_N must not be negative.")
    if phi_compression <= 0:
        raise ValueError("phi_compression must be positive.")
    return aashto_column_axial_cap_factor(transverse_reinforcement) * phi_compression * Po_N



@dataclass(frozen=True)
class AashtoTorsionResult:
    phi: float
    theta_deg: float
    cot_theta: float
    lambda_concrete: float
    lambda_duct: float
    tcr_Nmm: float
    phi_tcr_Nmm: float
    threshold_Nmm: float
    threshold_status: str
    tn_Nmm: float
    phi_tn_Nmm: float
    tu_over_phi_tn: float
    at_provided_mm2_per_mm: float
    at_required_mm2_per_mm: float
    at_dc: float
    al_required_mm2: float
    s_max_mm: float
    spacing_dc: float
    method: str
    basis: str


@dataclass(frozen=True)
class AashtoPrestressedTorsionGeneralResult:
    """AASHTO LRFD 5.7 prestressed solid-section torsion trace.

    This helper owns only the torsion threshold, solid-section Veff term, and
    transverse torsional resistance.  The concurrent longitudinal resistance
    equation of Article 5.7.3.6.3 is intentionally outside this result and must
    be checked by the combined V+T workflow.
    """

    phi: float
    fpc_MPa: float
    k_factor: float
    k_max: float
    tcr_Nmm: float
    phi_tcr_Nmm: float
    threshold_Nmm: float
    threshold_status: str
    veff_N: float
    theta_deg: float
    cot_theta: float
    tn_Nmm: float
    phi_tn_Nmm: float
    strength_dc: float
    at_required_mm2_per_mm: float
    method: str
    basis: str


def aashto_prestressed_torsion_general_result(
    *,
    fc_MPa: float,
    Acp_mm2: float,
    Pcp_mm: float,
    Ao_mm2: float,
    ph_mm: float,
    tu_Nmm: float,
    vu_N: float,
    at_mm2_per_mm: float,
    fy_MPa: float,
    theta_deg: float,
    phi: float,
    fpc_MPa: float = 0.0,
    lambda_concrete: float = 1.0,
    lambda_duct: float = 1.0,
    k_max: float = 2.0,
) -> AashtoPrestressedTorsionGeneralResult:
    """Evaluate AASHTO LRFD 5.7 prestressed solid-section torsion in SI.

    Code basis:
    - 5.7.2.1-3: torsion is investigated when |Tu| > 0.25 phi Tcr.
    - 5.7.2.1-4/-6: solid-section Tcr including prestress factor K.
    - 5.7.3.4.2-5: solid-section Veff used by the General Procedure strain.
    - 5.7.3.6.2-1: Tn = 2 Ao (At/s) fy cot(theta) lambda_duct.

    The caller supplies theta from Article 5.7.3.4 after replacing Vu with
    Veff in the longitudinal-strain calculation.  Longitudinal resistance per
    5.7.3.6.3-1 is deliberately not certified here.
    """

    positive = [fc_MPa, Acp_mm2, Pcp_mm, Ao_mm2, ph_mm, fy_MPa, phi, lambda_concrete, lambda_duct, k_max]
    if not all(math.isfinite(float(v)) and float(v) > 0.0 for v in positive):
        raise ValueError('fc, Acp, Pcp, Ao, ph, fy, phi, lambda_concrete, lambda_duct, and k_max must be positive finite values.')
    if float(k_max) > 2.0 + 1.0e-12:
        raise ValueError('k_max must not exceed the AASHTO upper limit of 2.0.')
    if not math.isfinite(float(at_mm2_per_mm)) or float(at_mm2_per_mm) < 0.0:
        raise ValueError('at_mm2_per_mm must be finite and nonnegative.')
    if not all(math.isfinite(float(v)) for v in [tu_Nmm, vu_N, theta_deg, fpc_MPa]):
        raise ValueError('tu_Nmm, vu_N, theta_deg, and fpc_MPa must be finite.')

    theta = math.radians(float(theta_deg))
    tan_theta = math.tan(theta)
    if abs(tan_theta) <= 1.0e-12:
        raise ValueError('theta_deg must have nonzero tangent.')
    cot_theta = 1.0 / tan_theta

    tcr = aashto_torsional_cracking_moment_nmm(
        fc_MPa=float(fc_MPa),
        Acp_mm2=float(Acp_mm2),
        Pcp_mm=float(Pcp_mm),
        shape='solid',
        lambda_concrete=float(lambda_concrete),
        fpc_MPa=float(fpc_MPa),
        k_max=float(k_max),
    )
    phi_tcr = float(phi) * tcr
    threshold = 0.25 * phi_tcr
    threshold_status = 'BELOW THRESHOLD' if abs(float(tu_Nmm)) <= threshold + 1.0e-9 else 'DESIGN REQUIRED'

    torsion_equiv_N = 0.9 * float(ph_mm) * abs(float(tu_Nmm)) / (2.0 * float(Ao_mm2))
    veff = math.hypot(abs(float(vu_N)), torsion_equiv_N)
    tn = 2.0 * float(Ao_mm2) * float(at_mm2_per_mm) * float(fy_MPa) * cot_theta * float(lambda_duct)
    phi_tn = float(phi) * tn
    dc = abs(float(tu_Nmm)) / phi_tn if phi_tn > 0.0 else float('inf')
    at_req = abs(float(tu_Nmm)) / (float(phi) * 2.0 * float(Ao_mm2) * float(fy_MPa) * cot_theta * float(lambda_duct))

    # Recompute K explicitly for the audit result; the Tcr helper uses the same
    # SI-safe source conversion.
    base_stress = aashto_sqrt_fc_stress_mpa(0.126 * float(lambda_concrete), float(fc_MPa))
    if base_stress <= 0.0:
        raise ValueError("AASHTO torsion K base stress must be positive.")
    k_radicand = 1.0 + float(fpc_MPa) / base_stress
    if k_radicand < 0.0:
        raise ValueError("AASHTO torsion K is undefined because 1 + fpc/(0.126 lambda sqrt(fc)) is negative.")
    k = min(float(k_max), math.sqrt(k_radicand))

    return AashtoPrestressedTorsionGeneralResult(
        phi=float(phi),
        fpc_MPa=float(fpc_MPa),
        k_factor=float(k),
        k_max=float(k_max),
        tcr_Nmm=float(tcr),
        phi_tcr_Nmm=float(phi_tcr),
        threshold_Nmm=float(threshold),
        threshold_status=threshold_status,
        veff_N=float(veff),
        theta_deg=float(theta_deg),
        cot_theta=float(cot_theta),
        tn_Nmm=float(tn),
        phi_tn_Nmm=float(phi_tn),
        strength_dc=float(dc),
        at_required_mm2_per_mm=float(at_req),
        method='AASHTO LRFD 5.7 prestressed solid-section torsion with General Procedure theta',
        basis='5.7.2.1-3/-4/-6; 5.7.3.4.2-5; 5.7.3.6.2-1; longitudinal 5.7.3.6.3-1 checked separately',
    )


@dataclass(frozen=True)
class AashtoCombinedShearTorsionResult:
    phi: float
    theta_deg: float
    cot_theta: float
    vu_N: float
    tu_Nmm: float
    shear_required_mm2_per_mm: float
    torsion_required_mm2_per_mm: float
    minimum_transverse_mm2_per_mm: float
    combined_transverse_required_mm2_per_mm: float
    governing_transverse_required_mm2_per_mm: float
    provided_av_plus_2at_mm2_per_mm: float
    transverse_dc: float
    shear_strength_dc: float
    torsion_strength_dc: float
    source_strength_dc: float
    al_required_mm2: float
    method: str
    basis: str


def aashto_combined_shear_torsion_result(
    *,
    vu_N: float,
    tu_Nmm: float,
    phi: float,
    vc_N: float,
    phi_vn_N: float,
    phi_tn_Nmm: float,
    bv_mm: float,
    dv_mm: float,
    Ao_mm2: float,
    ph_mm: float,
    fy_MPa: float,
    avs_provided_mm2_per_mm: float,
    at_provided_mm2_per_mm: float,
    avs_minimum_mm2_per_mm: float,
    theta_deg: float = AASHTO_SHEAR_SIMPLIFIED_THETA_DEG,
) -> AashtoCombinedShearTorsionResult:
    """Return AASHTO LRFD Section 5.7.3.6 scoped V+T result in SI.

    Scope: nonprestressed Column/Pier B-region review using the validated
    AASHTO.COL.SHEAR1 and AASHTO.COL.TORSION1 source routes.  Article
    5.7.3.6.1 requires transverse reinforcement for concurrent V+T to be at
    least the sum of shear reinforcement and torsion reinforcement.  Concrete
    Section Pro stores ``Av/s`` as the active shear leg area per spacing and
    ``At/s`` as one closed torsion leg per spacing for solid members; therefore
    the display gate uses ``Av/s + 2At/s`` to compare the available closed-tie
    source against the combined transverse demand.

    This helper intentionally does not implement prestressed V+T, general
    procedure beta/theta iteration, multi-cell torsion certification, or final
    hook/anchorage/lap-splice detailing.
    """

    values = [phi, vc_N, phi_vn_N, phi_tn_Nmm, bv_mm, dv_mm, Ao_mm2, ph_mm, fy_MPa]
    if not all(math.isfinite(float(v)) and float(v) > 0.0 for v in values):
        raise ValueError("phi, Vc, phiVn, phiTn, bv, dv, Ao, ph, and fy must be positive finite values.")
    if not all(math.isfinite(float(v)) and float(v) >= 0.0 for v in [vu_N, tu_Nmm, avs_provided_mm2_per_mm, at_provided_mm2_per_mm, avs_minimum_mm2_per_mm]):
        raise ValueError("Vu, Tu, provided Av/s, provided At/s, and minimum Av/s must be finite nonnegative values.")
    theta = math.radians(float(theta_deg))
    tan_theta = math.tan(theta)
    if abs(tan_theta) <= 1.0e-12:
        raise ValueError("theta_deg must have nonzero tangent.")
    cot_theta = 1.0 / tan_theta

    shear_required = max(0.0, (abs(float(vu_N)) / float(phi) - float(vc_N)) / (float(fy_MPa) * float(dv_mm) * cot_theta))
    torsion_required = abs(float(tu_Nmm)) / (float(phi) * 2.0 * float(Ao_mm2) * float(fy_MPa) * cot_theta)
    combined_required = shear_required + 2.0 * torsion_required
    governing_required = max(combined_required, float(avs_minimum_mm2_per_mm))
    provided_total = float(avs_provided_mm2_per_mm) + 2.0 * float(at_provided_mm2_per_mm)
    transverse_dc = governing_required / provided_total if provided_total > 0.0 else float("inf")
    shear_dc = abs(float(vu_N)) / float(phi_vn_N) if float(phi_vn_N) > 0.0 else float("inf")
    torsion_dc = abs(float(tu_Nmm)) / float(phi_tn_Nmm) if float(phi_tn_Nmm) > 0.0 else float("inf")
    al_required = torsion_required * float(ph_mm) * cot_theta * cot_theta
    return AashtoCombinedShearTorsionResult(
        phi=float(phi),
        theta_deg=float(theta_deg),
        cot_theta=cot_theta,
        vu_N=abs(float(vu_N)),
        tu_Nmm=abs(float(tu_Nmm)),
        shear_required_mm2_per_mm=shear_required,
        torsion_required_mm2_per_mm=torsion_required,
        minimum_transverse_mm2_per_mm=float(avs_minimum_mm2_per_mm),
        combined_transverse_required_mm2_per_mm=combined_required,
        governing_transverse_required_mm2_per_mm=governing_required,
        provided_av_plus_2at_mm2_per_mm=provided_total,
        transverse_dc=transverse_dc,
        shear_strength_dc=shear_dc,
        torsion_strength_dc=torsion_dc,
        source_strength_dc=max(shear_dc, torsion_dc),
        al_required_mm2=al_required,
        method="AASHTO LRFD 5.7.3.6 combined shear + torsion transverse sum, theta=45 deg",
        basis="Article 5.7.3.6.1 transverse reinforcement sum; Article 5.7.3.6.2 torsional resistance; Article 5.7.3.6.3 longitudinal torsion reinforcement preview",
    )


def aashto_torsional_cracking_moment_nmm(
    *,
    fc_MPa: float,
    Acp_mm2: float,
    Pcp_mm: float,
    Ao_mm2: float | None = None,
    be_mm: float | None = None,
    shape: str = "solid",
    lambda_concrete: float = 1.0,
    fpc_MPa: float = 0.0,
    k_max: float = 2.0,
) -> float:
    """Return AASHTO LRFD Article 5.7.2.1 torsional cracking moment in N-mm.

    AASHTO writes the expressions with ``f'c`` in ksi and dimensions in inches.
    This helper keeps the app in SI by converting the ``0.126*K*lambda*sqrt(fc)``
    stress term to MPa before multiplying by SI geometry.  ``fpc`` is optional;
    the current Column/Pier torsion route uses ``fpc=0`` for nonprestressed
    members and keeps prestressed torsion in REVIEW.
    """

    if fc_MPa <= 0 or Acp_mm2 <= 0 or Pcp_mm <= 0 or lambda_concrete <= 0 or k_max <= 0:
        raise ValueError("fc_MPa, Acp_mm2, Pcp_mm, lambda_concrete, and k_max must be positive.")
    if float(k_max) > 2.0 + 1.0e-12:
        raise ValueError("k_max must not exceed 2.0.")
    base_stress = aashto_sqrt_fc_stress_mpa(0.126 * float(lambda_concrete), float(fc_MPa))
    if base_stress <= 0.0:
        raise ValueError("AASHTO torsion K base stress must be positive.")
    fpc = float(fpc_MPa)
    if not math.isfinite(fpc):
        raise ValueError("fpc_MPa must be finite.")
    k_radicand = 1.0 + fpc / base_stress
    if k_radicand < 0.0:
        raise ValueError("AASHTO torsion K is undefined because 1 + fpc/(0.126 lambda sqrt(fc)) is negative.")
    k = min(float(k_max), math.sqrt(k_radicand))
    cracking_stress = aashto_sqrt_fc_stress_mpa(0.126 * k * float(lambda_concrete), float(fc_MPa))
    shape_norm = str(shape or "solid").strip().lower()
    if shape_norm == "hollow":
        ao = float(Ao_mm2) if Ao_mm2 is not None else float("nan")
        be = float(be_mm) if be_mm is not None else float("nan")
        if not all(math.isfinite(value) and value > 0.0 for value in [ao, be]):
            raise ValueError("Ao_mm2 and be_mm must be positive for hollow torsion cracking moment.")
        return cracking_stress * 2.0 * ao * be
    return cracking_stress * float(Acp_mm2) * float(Acp_mm2) / float(Pcp_mm)


def aashto_simplified_torsion_result(
    *,
    fc_MPa: float,
    Acp_mm2: float,
    Pcp_mm: float,
    Ao_mm2: float,
    ph_mm: float,
    tu_Nmm: float,
    at_mm2_per_mm: float,
    fy_MPa: float,
    spacing_mm: float,
    shape: str = "solid",
    be_mm: float | None = None,
    lambda_concrete: float = 1.0,
    lambda_duct: float = 1.0,
    theta_deg: float = AASHTO_SHEAR_SIMPLIFIED_THETA_DEG,
    phi: float = AASHTO_SHEAR_PHI,
) -> AashtoTorsionResult:
    """Return AASHTO LRFD Section 5.7 closed-transverse torsion result in SI.

    Scope: nonprestressed B-region Column/Pier torsion using the same simplified
    ``theta=45 deg`` route as AASHTO.COL.SHEAR1.  Combined shear + torsion
    interaction, prestressed torsion contribution, multi-cell hollow torsion,
    and seismic overstrength torsion remain separate guarded milestones.
    """

    values = [fc_MPa, Acp_mm2, Pcp_mm, Ao_mm2, ph_mm, fy_MPa, spacing_mm, phi, lambda_concrete, lambda_duct]
    if not all(math.isfinite(float(v)) and float(v) > 0.0 for v in values):
        raise ValueError("fc, Acp, Pcp, Ao, ph, fy, spacing, phi, lambda_concrete, and lambda_duct must be positive.")
    if not math.isfinite(float(at_mm2_per_mm)) or float(at_mm2_per_mm) < 0.0:
        raise ValueError("at_mm2_per_mm must be finite and nonnegative.")
    theta = math.radians(float(theta_deg))
    tan_theta = math.tan(theta)
    if abs(tan_theta) <= 1.0e-12:
        raise ValueError("theta_deg must have nonzero tangent.")
    cot_theta = 1.0 / tan_theta

    shape_norm = "hollow" if str(shape or "solid").strip().lower() == "hollow" else "solid"
    be = float(be_mm) if be_mm is not None and math.isfinite(float(be_mm)) and float(be_mm) > 0.0 else float(Acp_mm2) / float(Pcp_mm)
    tcr = aashto_torsional_cracking_moment_nmm(
        fc_MPa=float(fc_MPa),
        Acp_mm2=float(Acp_mm2),
        Pcp_mm=float(Pcp_mm),
        Ao_mm2=float(Ao_mm2),
        be_mm=be,
        shape=shape_norm,
        lambda_concrete=float(lambda_concrete),
    )
    phi_tcr = float(phi) * tcr
    threshold = 0.25 * phi_tcr
    threshold_status = "BELOW THRESHOLD" if abs(float(tu_Nmm)) <= threshold + 1.0e-9 else "DESIGN REQUIRED"

    tn = 2.0 * float(Ao_mm2) * float(at_mm2_per_mm) * float(fy_MPa) * cot_theta * float(lambda_duct)
    phi_tn = float(phi) * tn
    dc = abs(float(tu_Nmm)) / phi_tn if phi_tn > 0.0 else float("inf")
    at_req = abs(float(tu_Nmm)) / (float(phi) * 2.0 * float(Ao_mm2) * float(fy_MPa) * cot_theta * float(lambda_duct))
    at_dc = at_req / float(at_mm2_per_mm) if float(at_mm2_per_mm) > 0.0 else float("inf")
    # Article 5.7.3.6.3 box-section torsion-only relationship.  For solid
    # members the full combined longitudinal force equation is a future V+T
    # milestone; this value remains a transparent torsion-only Al preview.
    al_req = tn * float(ph_mm) / (2.0 * float(Ao_mm2) * float(fy_MPa)) if tn > 0.0 else 0.0
    smax = min(float(ph_mm) / 8.0, 12.0 * 25.4)
    spacing_dc = float(spacing_mm) / smax if smax > 0.0 else float("inf")
    return AashtoTorsionResult(
        phi=float(phi),
        theta_deg=float(theta_deg),
        cot_theta=cot_theta,
        lambda_concrete=float(lambda_concrete),
        lambda_duct=float(lambda_duct),
        tcr_Nmm=tcr,
        phi_tcr_Nmm=phi_tcr,
        threshold_Nmm=threshold,
        threshold_status=threshold_status,
        tn_Nmm=tn,
        phi_tn_Nmm=phi_tn,
        tu_over_phi_tn=dc,
        at_provided_mm2_per_mm=float(at_mm2_per_mm),
        at_required_mm2_per_mm=at_req,
        at_dc=at_dc,
        al_required_mm2=al_req,
        s_max_mm=smax,
        spacing_dc=spacing_dc,
        method="AASHTO LRFD 5.7.3.6 closed-transverse torsion, theta=45 deg",
        basis="Article 5.7.2.1 threshold Tu > 0.25phiTcr; Article 5.7.3.6.2 Tn=2AoAtfy cot(theta)/s; Article 5.7.3.6.3 Al torsion preview",
    )


@dataclass(frozen=True)
class AashtoShearResult:
    phi: float
    beta: float
    theta_deg: float
    alpha_deg: float
    lambda_concrete: float
    vc_N: float
    vs_N: float
    vp_N: float
    vn_uncapped_N: float
    vn_limit_N: float
    vn_N: float
    phi_vn_N: float
    vu_over_phi_vn: float
    avs_provided_mm2_per_mm: float
    avs_required_mm2_per_mm: float
    avs_dc: float
    s_max_mm: float
    spacing_dc: float
    shear_stress_mpa: float
    shear_stress_ratio_to_fc: float
    method: str
    basis: str


def aashto_min_transverse_avs_mm2_per_mm(fc_MPa: float, bv_mm: float, fy_MPa: float, *, lambda_concrete: float = 1.0) -> float:
    """Return AASHTO LRFD Article 5.7.2.5 minimum transverse Av/s in mm²/mm.

    The AASHTO expression is written with ``f'c`` in ksi and yields an area
    ratio after multiplication by ``bv / fy``.  The helper evaluates the
    ``0.0316*lambda*sqrt(f'c)`` stress term in MPa before multiplying by SI
    ``bv`` and dividing by SI ``fy``.
    """

    if fc_MPa <= 0 or bv_mm <= 0 or fy_MPa <= 0:
        raise ValueError("fc_MPa, bv_mm, and fy_MPa must be positive.")
    stress_mpa = aashto_sqrt_fc_stress_mpa(0.0316 * float(lambda_concrete), float(fc_MPa))
    return stress_mpa * float(bv_mm) / float(fy_MPa)


def aashto_shear_smax_mm(fc_MPa: float, bv_mm: float, dv_mm: float, vu_N: float) -> tuple[float, float, str]:
    """Return AASHTO LRFD Article 5.7.2.6 maximum transverse spacing.

    The spacing branch is based on ``vu/f'c``.  Because both stresses are in
    MPa in the app, the 0.125 threshold is dimensionless and can be applied
    directly after computing ``vu = Vu/(bv*dv)``.
    """

    if fc_MPa <= 0 or bv_mm <= 0 or dv_mm <= 0:
        raise ValueError("fc_MPa, bv_mm, and dv_mm must be positive.")
    vu_mpa = abs(float(vu_N)) / (float(bv_mm) * float(dv_mm))
    ratio = vu_mpa / float(fc_MPa)
    if ratio < 0.125:
        return min(0.8 * float(dv_mm), 24.0 * 25.4), ratio, "vu < 0.125 fc: smax = min(0.8dv, 24 in)"
    return min(0.4 * float(dv_mm), 12.0 * 25.4), ratio, "vu >= 0.125 fc: smax = min(0.4dv, 12 in)"


def aashto_simplified_shear_result(
    *,
    fc_MPa: float,
    bv_mm: float,
    dv_mm: float,
    vu_N: float,
    avs_mm2_per_mm: float,
    fy_MPa: float,
    vp_N: float = 0.0,
    lambda_concrete: float = 1.0,
    alpha_deg: float = 90.0,
    phi: float = AASHTO_SHEAR_PHI,
) -> AashtoShearResult:
    """Return AASHTO LRFD Section 5.7 simplified sectional shear result in SI.

    Scope: nonprestressed B-regions using Method 1 parameters ``beta=2.0`` and
    ``theta=45 deg``.  Prestress component ``Vp`` is accepted for transparent
    traceability, but Column/Pier UI keeps active-prestress rows in REVIEW until
    the general procedure/PSC milestone is validated.
    """

    values = [fc_MPa, bv_mm, dv_mm, fy_MPa, phi, lambda_concrete]
    if not all(math.isfinite(float(v)) and float(v) > 0.0 for v in values):
        raise ValueError("fc_MPa, bv_mm, dv_mm, fy_MPa, phi, and lambda_concrete must be positive finite values.")
    if not math.isfinite(float(avs_mm2_per_mm)) or float(avs_mm2_per_mm) < 0.0:
        raise ValueError("avs_mm2_per_mm must be finite and nonnegative.")
    fc_ksi = mpa_to_ksi(float(fc_MPa))
    if fc_ksi > 15.0 + 1.0e-9:
        raise ValueError("AASHTO LRFD Article 5.7 shear fc limit is 15 ksi for Article 5.7.3.")

    beta = AASHTO_SHEAR_SIMPLIFIED_BETA
    theta_deg = AASHTO_SHEAR_SIMPLIFIED_THETA_DEG
    theta = math.radians(theta_deg)
    alpha = math.radians(float(alpha_deg))
    if abs(math.sin(alpha)) <= 1.0e-12:
        raise ValueError("alpha_deg must define a transverse reinforcement angle with nonzero sine.")

    vc_stress_mpa = aashto_sqrt_fc_stress_mpa(0.0316 * beta * float(lambda_concrete), float(fc_MPa))
    vc_N = vc_stress_mpa * float(bv_mm) * float(dv_mm)
    vs_N = float(avs_mm2_per_mm) * float(fy_MPa) * float(dv_mm) * (1.0 / math.tan(theta) + 1.0 / math.tan(alpha)) * math.sin(alpha)
    vn_uncapped_N = max(0.0, vc_N + vs_N + float(vp_N))
    vn_limit_N = 0.25 * float(fc_MPa) * float(bv_mm) * float(dv_mm) + float(vp_N)
    vn_N = min(vn_uncapped_N, vn_limit_N)
    phi_vn_N = float(phi) * vn_N
    vu_over_phi_vn = abs(float(vu_N)) / phi_vn_N if phi_vn_N > 0.0 else float("nan")
    avs_required = aashto_min_transverse_avs_mm2_per_mm(float(fc_MPa), float(bv_mm), float(fy_MPa), lambda_concrete=float(lambda_concrete))
    avs_dc = avs_required / float(avs_mm2_per_mm) if float(avs_mm2_per_mm) > 0.0 else float("inf")
    s_max_mm, stress_ratio, spacing_basis = aashto_shear_smax_mm(float(fc_MPa), float(bv_mm), float(dv_mm), float(vu_N))
    shear_stress_mpa = abs(float(vu_N)) / (float(bv_mm) * float(dv_mm))
    return AashtoShearResult(
        phi=float(phi),
        beta=beta,
        theta_deg=theta_deg,
        alpha_deg=float(alpha_deg),
        lambda_concrete=float(lambda_concrete),
        vc_N=vc_N,
        vs_N=vs_N,
        vp_N=float(vp_N),
        vn_uncapped_N=vn_uncapped_N,
        vn_limit_N=vn_limit_N,
        vn_N=vn_N,
        phi_vn_N=phi_vn_N,
        vu_over_phi_vn=vu_over_phi_vn,
        avs_provided_mm2_per_mm=float(avs_mm2_per_mm),
        avs_required_mm2_per_mm=avs_required,
        avs_dc=avs_dc,
        s_max_mm=s_max_mm,
        spacing_dc=float("nan"),
        shear_stress_mpa=shear_stress_mpa,
        shear_stress_ratio_to_fc=stress_ratio,
        method="AASHTO LRFD 5.7.3 simplified sectional shear (beta=2.0, theta=45 deg)",
        basis=f"Article 5.7.3.3 Vn=min(Vc+Vs+Vp,0.25fc*bv*dv+Vp); Article 5.7.2.6 {spacing_basis}",
    )
