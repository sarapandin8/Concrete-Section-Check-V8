"""Developed I-girder flexure, AASHTO LRFD 9th Edition (2020).

5.9.4.3.1--3 supplies strand stress limits, NOT an area or moment multiplier.
Full-development fps is obtained from a reference nominal section equilibrium
at the same external Nu and bending direction. The available strand stress is
then limited in a second equilibrium solve. The reference includes every strand
family: a sleeve boundary cannot change another family's development length.

The shared PMM engine/material laws and other workflows are not modified.
Internal units: N, mm, MPa; compression-positive external Nu and steel forces.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping

from shapely.geometry import Point, box

from concrete_pmm_pro.analysis.prestress_stress import prestress_stress_mpa
from concrete_pmm_pro.code_checks.aashto_lrfd import (
    aashto_alpha1, aashto_beta1, aashto_phi_and_strain_condition,
    aashto_pretensioned_strand_development_length_mm,
)
from concrete_pmm_pro.core.analysis import AnalysisInput
from concrete_pmm_pro.core.models import PrestressElement, RebarMaterial
from concrete_pmm_pro.geometry.summary import to_shapely_polygon
from concrete_pmm_pro.serviceability.girder_prestress_station import (
    active_girder_strand_rows, debonded_strand_numbers_for_row,
)

RESULT_VERSION = "IGIRDER.FLEXDEP1.aashto-developed-flexure.CSI-sign1"
SETTINGS_KEY = "igird_flexure_development_settings"
MPA_PER_KSI = 6.894757293168


class DevelopedEquilibriumError(ValueError):
    def __init__(self, message: str, strand_trace: list, bar_trace: list):
        super().__init__(message)
        self.strand_trace = strand_trace
        self.bar_trace = bar_trace


def development_settings(state: Mapping) -> dict:
    raw = state.get(SETTINGS_KEY)
    if not isinstance(raw, Mapping):
        raw = (state.get("project_metadata") or {}).get(SETTINGS_KEY, {})
    raw = raw if isinstance(raw, Mapping) else {}
    result = dict(raw)
    for key in ("left_extension_m", "right_extension_m", "bar_ld_mm"):
        try:
            value = float(raw.get(key, 0.0))
        except (ValueError, TypeError):
            value = 0.0
        result[key] = value if math.isfinite(value) and value >= 0 else 0.0
    for key in ("bars_continuous_confirmed", "left_bar_anchored", "right_bar_anchored"):
        result[key] = bool(raw.get(key, False))
    mode = str(raw.get("debonded_service_condition", "unknown"))
    result["debonded_service_condition"] = mode if mode in ("unknown", "tension", "no_tension_confirmed") else "unknown"
    result["note"] = str(raw.get("note") or "")
    return result


@dataclass(frozen=True)
class StrandFamily:
    name: str
    element: PrestressElement
    db_mm: float
    debonded: bool
    left_bond_start_m: float
    right_bond_end_m: float

    def bonded_distance_mm(self, x_m: float) -> float:
        return 1000.0 * max(0.0, min(x_m - self.left_bond_start_m, self.right_bond_end_m - x_m))


def strand_families(table, *, y_min_mm: float, span_m: float, stage: str, settings: Mapping) -> tuple[StrandFamily, ...]:
    if not math.isfinite(span_m) or span_m <= 0:
        raise ValueError("Physical station span must be positive and finite.")
    left_end = -float(settings.get("left_extension_m", 0.0))
    right_end = span_m + float(settings.get("right_extension_m", 0.0))
    force_key = "Pe_construction/strand_kN" if stage == "construction" else "Pe_eff_final/strand_kN"
    families = []
    for row in active_girder_strand_rows(table):
        count = int(round(float(row["No. Strands"])))
        if count <= 0:
            continue
        name = str(row.get("Group ID") or "Strand row")
        area = float(row["Area/Strand_mm2"])
        pe = float(row[force_key]) * 1000.0
        y = float(row["y_mm_from_bottom"]) + y_min_mm
        token = re.search(r"\d+(?:\.\d+)?", str(row.get("Strand Size") or ""))
        if token is None:
            raise ValueError(f"{name}: nominal strand diameter is missing; select a strand size in Prestress.")
        db = float(token.group())
        if not all(math.isfinite(v) and v > 0 for v in (area, pe, db)) or not math.isfinite(y):
            raise ValueError(f"{name}: invalid area, stage effective force, diameter, or elevation.")
        fpe = pe / area
        if fpe >= 1670.0:
            raise ValueError(f"{name}: effective stress must be below adopted strand proof stress 1670 MPa.")
        selected = debonded_strand_numbers_for_row(row)
        for debonded, n in ((False, count - len(selected)), (True, len(selected))):
            if n <= 0:
                continue
            l = float(row.get("Left debond m") or 0.0) if debonded else 0.0
            r = float(row.get("Right debond m") or 0.0) if debonded else 0.0
            if not all(math.isfinite(v) and v >= 0 for v in (l, r)) or left_end + l >= right_end - r:
                raise ValueError(f"{name}: sleeve lengths leave no bonded strand length.")
            label = f"{name} · {'debonded' if debonded else 'fully bonded'}"
            element = PrestressElement(x_mm=0.0, y_mm=y, area_mm2=area, count=n,
                diameter_mm=db, fpy_mpa=1670.0, fpu_mpa=1860.0, ep_mpa=195000.0,
                pe_eff_n=pe, initial_stress_mpa=fpe, initial_strain=fpe / 195000.0,
                bonded=True, label=label, material_name="Girder strand layout")
            families.append(StrandFamily(label, element, db, debonded, left_end + l, right_end - r))
    if not families:
        raise ValueError("No active dedicated I-Girder strand families are defined.")
    return tuple(families)


def strand_stress_limit(*, distance_mm: float, db_mm: float, fpe_mpa: float,
                        fps_mpa: float, depth_mm: float, debonded: bool,
                        service_condition: str = "unknown") -> dict:
    """Exact SI conversion of 5.9.4.3.2-1--3; zero at bond commencement.

    kappa=2 is required for a debonded strand with service tension; unknown
    service classification conservatively selects the same longer length.
    """
    values = (distance_mm, db_mm, fpe_mpa, fps_mpa, depth_mm)
    if not all(math.isfinite(v) for v in values) or distance_mm < 0 or min(values[1:]) <= 0:
        raise ValueError("Strand development inputs must be finite with positive diameter, stress and depth.")
    lt = 60.0 * db_mm
    # fps<=fpe can occur at a compression-side row; no flexural stress increase
    # is claimed there. Use fpe for the conservative development-length source.
    ld, kappa, basis = aashto_pretensioned_strand_development_length_mm(
        fps_MPa=max(fps_mpa, fpe_mpa + 1e-6), fpe_MPa=fpe_mpa, db_mm=db_mm,
        member_depth_mm=depth_mm,
        debonded_conservative=debonded and service_condition != "no_tension_confirmed")
    if distance_mm <= 0:
        cap, branch = 0.0, "BOND START / SLEEVE"
    elif distance_mm < lt:
        cap, branch = min(fps_mpa, fpe_mpa * distance_mm / lt), "TRANSFER"
    elif distance_mm < ld and ld > lt and fps_mpa > fpe_mpa:
        cap = fpe_mpa + (distance_mm - lt) / (ld - lt) * (fps_mpa - fpe_mpa)
        branch = "FLEXURAL DEVELOPMENT"
    else:
        cap, branch = fps_mpa, "FULLY DEVELOPED"
    return {"fpx_limit_MPa": max(0.0, cap), "lt_mm": lt, "ld_mm": ld,
            "kappa": kappa, "kappa_basis": basis, "branch": branch,
            "transfer_factor": min(1.0, distance_mm / lt)}


class SectionEquilibrium:
    """Fixed-axis section response with independent steel stress limits."""
    def __init__(self, ai: AnalysisInput, sign: float):
        self.ai = ai
        self.sign = 1.0 if sign >= 0 else -1.0
        self.polygon = to_shapely_polygon(ai.section_geometry)
        if not self.polygon.is_valid or self.polygon.is_empty:
            raise ValueError("Invalid I-Girder strength geometry.")
        self.xmin, self.ymin, self.xmax, self.ymax = self.polygon.bounds
        self.h = self.ymax - self.ymin
        self.yref = self.polygon.centroid.y
        self.fc = float(ai.concrete_material.fc_MPa)
        self.ecu = float(ai.concrete_material.ecu)
        if not 0 < self.ecu <= 0.003:
            raise ValueError("AASHTO 5.6.2.1 unconfined I-Girder ecu must be positive and <=0.003.")
        if not 0 < self.fc <= 15.0 * MPA_PER_KSI:
            raise ValueError("Strand development route is limited to normal-weight concrete f'c <= 15 ksi.")
        self.alpha = aashto_alpha1(self.fc)
        self.beta = aashto_beta1(self.fc)
        self.materials = {m.name: m for m in ai.rebar_materials}
        self.default = ai.rebar_materials[0] if ai.rebar_materials else RebarMaterial(name="Default", fy_MPa=390, Es_MPa=200000)
        self.bars = list(ai.rebars) if ai.settings.include_rebars else []
        self.unresolved_bar_materials = sorted({bar.material_name or "(unnamed)"
            for bar in self.bars if bar.material_name not in self.materials})
        self.elements = list(ai.prestress_elements) if ai.settings.include_prestress else []
        if any(not e.bonded or e.fpu_mpa is None for e in self.elements):
            raise ValueError("The developed I-Girder route requires bonded pretensioned strand with valid fpu.")

    def strain(self, y: float, c: float) -> float:
        d = self.ymax - y if self.sign > 0 else y - self.ymin
        return self.ecu * (1.0 - d / c)

    def evaluate(self, c: float, *, strand_caps=None, transfer_factors=None, bar_factors=None) -> dict:
        if c <= 0 or not math.isfinite(c):
            raise ValueError("Neutral-axis depth must be positive and finite.")
        a = self.beta * c
        region = self.polygon.intersection(box(self.xmin - 1, self.ymax - a, self.xmax + 1, self.ymax + 1)
            if self.sign > 0 else box(self.xmin - 1, self.ymin - 1, self.xmax + 1, self.ymin + a))
        cc = self.alpha * self.fc * region.area
        pn = cc
        mn = cc * (region.centroid.y - self.yref) if cc > 0 else 0.0
        mny = cc * (region.centroid.x - self.polygon.centroid.x) if cc > 0 else 0.0
        rebar_force = ps_force = 0.0
        eps_t = 0.0
        control_fy, control_es = 390.0, 200000.0
        for i, bar in enumerate(self.bars):
            mat = self.materials.get(bar.material_name, self.default)
            eps = self.strain(bar.y_mm, c)
            fs = max(-mat.fy_MPa, min(mat.fy_MPa, mat.Es_MPa * eps))
            factor = 1.0 if bar_factors is None else bar_factors[i]
            # Both compression and tension credit use the longer conservative
            # tension ld; missing anchorage never receives full end strength.
            fs = max(-mat.fy_MPa * factor, min(mat.fy_MPa * factor, fs))
            displaced = self.alpha * self.fc if self.ai.settings.subtract_rebar_displaced_concrete and region.covers(Point(bar.x_mm, bar.y_mm)) else 0.0
            force = bar.area_mm2 * (fs - displaced)
            pn += force
            mn += force * (bar.y_mm - self.yref)
            mny += force * (bar.x_mm - self.polygon.centroid.x)
            rebar_force += force
            if fs < 0 and -eps > eps_t:
                eps_t, control_fy, control_es = -eps, mat.fy_MPa, mat.Es_MPa
        fps_values = []
        for i, e in enumerate(self.elements):
            eps = self.strain(e.y_mm, c)
            initial = e.initial_strain if e.initial_strain is not None else (e.initial_stress_mpa or e.pe_eff_n / e.area_mm2) / e.ep_mpa
            tf = 1.0 if transfer_factors is None else transfer_factors[i]
            fps, _ = prestress_stress_mpa(initial * tf - eps, e.ep_mpa, e.fpu_mpa,
                e.fpy_mpa, self.ai.settings.prestress_stress_model)
            if strand_caps is not None:
                fps = min(fps, strand_caps[i])
            force = -e.total_area_mm2 * fps
            pn += force
            mn += force * (e.y_mm - self.yref)
            mny += force * (e.x_mm - self.polygon.centroid.x)
            ps_force += force
            fps_values.append(fps)
            # No tensile-strain credit for an unanchored zero-force family.
            if fps > 1e-9 and -eps > eps_t:
                eps_t, control_fy, control_es = -eps, e.fpy_mpa or e.fpu_mpa, e.ep_mpa
        phi_result = aashto_phi_and_strain_condition(eps_t, fy_MPa=control_fy, Es_MPa=control_es,
            prestressed_member=bool(self.elements))
        phi = phi_result.phi
        return {"c_mm": c, "a_mm": a, "alpha1": self.alpha, "beta1": self.beta,
            "Pn_N": pn, "Mn_Nmm": self.sign * mn, "phi": phi,
            "phiPn_N": phi * pn, "phiMn_Nmm": self.sign * phi * mn,
            "eps_t": eps_t, "strain_condition": phi_result.strain_condition,
            "Cc_N": cc, "As_force_N": rebar_force, "Aps_force_N": ps_force,
            "fps_MPa": fps_values, "y_reference_mm": self.yref,
            "phi_basis": phi_result.basis, "Mny_Nmm": mny}

    def solve(self, nu_n: float, **limits) -> dict:
        """Bracket every sampled branch; require phi*Pn=Nu, select directional M.

        Factored axial load is held fixed also in the transition phi zone.
        Both Pn and Mn receive the SAME phi, per C5.5.4.2.
        """
        if not math.isfinite(nu_n):
            raise ValueError("External Nu must be finite.")
        tolerance = max(0.02, abs(nu_n) * 1e-9)
        # No tensile steel and zero applied axial force has an exact zero
        # strength boundary, not an artificially closed moment diagram.
        if abs(nu_n) <= tolerance and limits.get("strand_caps") is not None and not any(limits["strand_caps"]) and not any(limits.get("bar_factors") or []):
            z = self.evaluate(self.h * 1e-10, **limits)
            z.update(Pn_N=0.0, Mn_Nmm=0.0, phiPn_N=0.0, phiMn_Nmm=0.0,
                     Cc_N=0.0, As_force_N=0.0, Aps_force_N=0.0, residual_N=0.0)
            return z
        samples = [self.h * 10.0 ** (-8.0 + 10.0 * i / 64.0) for i in range(65)]
        roots = []
        previous = self.evaluate(samples[0], **limits)
        for c in samples[1:]:
            current = self.evaluate(c, **limits)
            flo, fhi = previous["phiPn_N"] - nu_n, current["phiPn_N"] - nu_n
            if abs(flo) <= tolerance:
                roots.append(previous)
            if flo * fhi < 0:
                lo, hi = previous["c_mm"], c
                for _ in range(90):
                    mid = self.evaluate(0.5 * (lo + hi), **limits)
                    fm = mid["phiPn_N"] - nu_n
                    if abs(fm) <= tolerance:
                        break
                    if flo * fm <= 0:
                        hi = mid["c_mm"]
                    else:
                        lo, flo = mid["c_mm"], fm
                if abs(mid["phiPn_N"] - nu_n) <= tolerance:
                    roots.append(mid)
            previous = current
        if abs(previous["phiPn_N"] - nu_n) <= tolerance:
            roots.append(previous)
        roots = [r for r in roots if r["phiMn_Nmm"] >= -1e-4]
        if not roots:
            raise ValueError("No directional axial-flexural equilibrium with available developed steel; section cannot resist the applied Nu in this scope.")
        result = max(roots, key=lambda r: r["phiMn_Nmm"])
        result["residual_N"] = result["phiPn_N"] - nu_n
        return result


def ordinary_bar_limits(context: SectionEquilibrium, *, x_m: float, span_m: float,
                        settings: Mapping, params: Mapping, girder_fc_mpa: float) -> tuple[list[float], list[dict]]:
    """Conservative 5.10.8.2.1 bar credit, using existing longitudinal bars.

    Automatic ld uses location/coating product 1.7 and no confinement/excess
    reduction (lambda_rc=lambda_er=1, normal-weight lambda=1). The drawing
    confirmation is a separate gate. Shorter verified ld/anchorage may be entered.
    The 12-in minimum also applies to partial straight-bar strength credit.
    """
    factors, trace = [], []
    left = x_m + float(settings.get("left_extension_m", 0))
    right = span_m + float(settings.get("right_extension_m", 0)) - x_m
    distance = 1000.0 * max(0.0, min(float("inf") if settings.get("left_bar_anchored") else left,
        float("inf") if settings.get("right_bar_anchored") else right))
    for bar in context.bars:
        mat = context.materials.get(bar.material_name, context.default)
        db = bar.diameter_mm
        fc = girder_fc_mpa
        if bar.material_name == "Composite deck longitudinal rebar":
            prefix = "top" if str(bar.label).startswith("Top") else "bottom"
            db = float(params.get(f"deck_long_rebar_{prefix}_diameter_mm", 0.0))
            fc = float(params.get("deck_fc_MPa", 0.0))
        ld = float(settings.get("bar_ld_mm", 0.0))
        if ld > 0:
            if ld < 304.8:
                raise ValueError("Verified straight-bar ld cannot be below the AASHTO 12-in minimum.")
            basis = "Engineer-entered governing ld, 5.10.8.2.1a; confirm every included layer"
        else:
            if db <= 0 or db > 35.8 or mat.fy_MPa > 75 * MPA_PER_KSI or not 0 < fc <= 10 * MPA_PER_KSI:
                raise ValueError("Automatic ordinary-bar ld is outside its normal-weight <=10 ksi, <=No.11, fy<=75 ksi scope; enter a verified governing ld.")
            ld = max(304.8, 2.4 * db * (mat.fy_MPa / MPA_PER_KSI) / math.sqrt(fc / MPA_PER_KSI) * 1.7)
            basis = "5.10.8.2.1a--c: location/coating=1.7; confinement=excess=density=1"
        factor = 0.0 if distance < 304.8 else min(1.0, distance / ld)
        factors.append(factor)
        trace.append({"Bar": bar.label or bar.material_name, "db_mm": db, "fy_MPa": mat.fy_MPa,
            "material_name": bar.material_name, "Es_MPa": mat.Es_MPa,
            "material_source": "Project material" if bar.material_name in context.materials else
                f"Existing solver fallback: {mat.name}; resolve missing project material before PASS",
            "bonded_distance_mm": distance if math.isfinite(distance) else None, "ld_full_yield_mm": ld,
            "stress_limit_MPa": factor * mat.fy_MPa, "factor": factor, "basis": basis})
    return factors, trace


def solve_developed_station(context: SectionEquilibrium, families: tuple[StrandFamily, ...], *,
        reference: Mapping, x_m: float, span_m: float, nu_n: float,
        precast_depth_mm: float, girder_fc_mpa: float, settings: Mapping, params: Mapping) -> dict:
    caps, transfer, traces = [], [], []
    for i, family in enumerate(families):
        e = family.element
        fpe = e.pe_eff_n / e.area_mm2
        fps = float(reference["fps_MPa"][i])
        # A zero reference stress implies no tensile credit; it still has a
        # positive conservative ld audit source at effective prestress.
        limit = strand_stress_limit(distance_mm=family.bonded_distance_mm(x_m), db_mm=family.db_mm,
            fpe_mpa=fpe, fps_mpa=max(fps, 1e-6), depth_mm=precast_depth_mm,
            debonded=family.debonded, service_condition=str(settings.get("debonded_service_condition", "unknown")))
        caps.append(limit["fpx_limit_MPa"])
        transfer.append(limit["transfer_factor"])
        traces.append({"Family": family.name, "Count": e.count, "Aps_mm2": e.total_area_mm2,
            "bond_start_left_m": family.left_bond_start_m, "bond_end_right_m": family.right_bond_end_m,
            "bonded_distance_mm": family.bonded_distance_mm(x_m), "db_mm": family.db_mm,
            "fpe_MPa": fpe, "fps_reference_MPa": fps, **limit})
    bar_factors, bar_trace = ordinary_bar_limits(context, x_m=x_m, span_m=span_m,
        settings=settings, params=params, girder_fc_mpa=girder_fc_mpa)
    try:
        result = context.solve(nu_n, strand_caps=caps, transfer_factors=transfer, bar_factors=bar_factors)
    except ValueError as exc:
        raise DevelopedEquilibriumError(str(exc), traces, bar_trace) from exc
    for i, trace in enumerate(traces):
        trace["fps_used_MPa"] = result["fps_MPa"][i]
        trace["Tps_kN"] = context.elements[i].total_area_mm2 * result["fps_MPa"][i] / 1000.0
    result.update(strand_trace=traces, bar_trace=bar_trace,
        reference_Mn_kNm=reference["Mn_Nmm"] / 1e6, reference_phiMn_kNm=reference["phiMn_Nmm"] / 1e6,
        reference_c_mm=reference["c_mm"],
        source_status="PASS" if not context.bars or settings.get("bars_continuous_confirmed") else "REVIEW",
        source_note="Ordinary-bar full-span continuity/cutoff and entered anchorage/ld require drawing confirmation." if context.bars and not settings.get("bars_continuous_confirmed") else "Current bar continuity declaration recorded; strand development limits included.")
    if context.unresolved_bar_materials:
        result["source_status"] = "REVIEW"
        result["source_note"] += " Missing ordinary-bar material definitions: " + ", ".join(context.unresolved_bar_materials) + "; existing fallback fy/Es is shown in the bar trace and cannot authorize PASS."
    if abs(result["Mny_Nmm"]) > max(1.0, abs(result["Mn_Nmm"]) * 1e-6):
        result["source_status"] = "REVIEW"
        result["source_note"] += " Unsymmetric section response produces secondary bending; a biaxial solution is required."
    return result
