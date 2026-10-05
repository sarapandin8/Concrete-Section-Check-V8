"""I-Girder ULS7 adapter and stored-result presentation.

Analysis owns calculations; these trace/definition functions only format
already computed rows and are safe for Result Summary / Report-QA.
"""
from __future__ import annotations
import math
from collections.abc import Mapping
import pandas as pd

from concrete_pmm_pro.analysis.igird_combined_vt import (
    RESULT_VERSION, concurrent_vt_si, development_settings,
    nominal_tension_fps, ordinary_development_factor,
)
from concrete_pmm_pro.code_checks.aashto_lrfd import (
    aashto_general_shear_parameters, aashto_min_transverse_avs_mm2_per_mm,
    aashto_prestressed_shear_phi, aashto_torsion_transverse_design_fy_mpa, aashto_shear_transverse_design_fy_mpa,
)
from concrete_pmm_pro.ui import igird_shear_section
from concrete_pmm_pro.core.aashto_units import aashto_sqrt_fc_stress_mpa, ksi_to_mpa


def _number(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def check_dataframe(state, active_df, *, strength_route) -> pd.DataFrame:
    from concrete_pmm_pro.ui import analysis_page as ap
    if active_df.empty:
        return pd.DataFrame()
    if igird_shear_section.RUNTIME_KEY not in state:
        state = {**state, igird_shear_section.RUNTIME_KEY: {"active_df": active_df}}
    # Keep every physical concurrent row (including both support faces).
    # Supplemental critical rows are only interpolated when each case has
    # unambiguous action vectors at every source x; no separate envelopes.
    prepared = ap._beam_uls_combined_vt_demand_rows(active_df, state, strength_route=strength_route)
    ambiguous_cases = set()
    for case, group in active_df.groupby("Case Name", sort=False):
        for _, same_x in group.groupby("Station x (m)", sort=False):
            if len(same_x[["Mux", "Nu", "Vuy", "Tu"]].drop_duplicates()) > 1:
                ambiguous_cases.add(str(case))
    nominal_cache = {}
    rows = []
    for i, source in prepared.iterrows():
        kind = str(source.get("__VT station type") or "LOAD STATION")
        if kind == "DIAGRAM BOUNDARY":
            continue  # Never fabricate engineering checks outside imported physical rows.
        if kind == "CRITICAL SHEAR SECTION" and str(source.get("Case Name")) in ambiguous_cases:
            continue
        mux = _number(source.get("Mux"))
        faces = ["bottom", "top"] if math.isfinite(mux) and abs(mux) <= 1e-9 else ["top" if mux < 0 else "bottom"]
        for face in faces:
            rows.append(_check_row(state, source.to_dict(), strength_route=strength_route,
                face=face, source_index=i, nominal_cache=nominal_cache,
                ambiguous_case=str(source.get("Case Name")) in ambiguous_cases))
    from concrete_pmm_pro.io.girder_csi_import import apply_source_gate
    return apply_source_gate(pd.DataFrame(rows), active_df)


def _check_row(state, row, *, strength_route, face, source_index, nominal_cache, ambiguous_case):
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.analysis.girder_axial_convention import axial_trace
    x, mu, _raw_nu, vu, tu = [_number(row.get(k)) for k in ["Station x (m)", "Mux", "Nu", "Vuy", "Tu"]]
    nu_trace = axial_trace(row, state)
    nu = nu_trace["Nu kN"]
    span = ap._beam_uls_span_length_from_state(state, is_building=False)
    side = ap._beam_uls_member_end_side(x, span)
    result = {"Check": "Shear + Torsion", "Status": "REVIEW", "Station type": str(row.get("__VT station type") or "LOAD STATION"),
        "Governing x": ap._format_beam_uls_x(x), "Case": str(row.get("Case Name") or "-"),
        "Source row": source_index, "Support side": side or "-", "Tension face": face.upper(),
        "Mu kN-m": mu, **nu_trace, "Nu app kN": nu, "Nu AASHTO kN": -nu, "Vu kN": vu, "Tu kN-m": tu,
        "Shape": "SOLID", "Result version": RESULT_VERSION,
        "Code basis": "AASHTO LRFD 9th Ed. 5.7.3.4.2; 5.7.3.6.1; 5.7.3.6.3-1",
        "Stress status": "REVIEW", "Transverse status": "REVIEW", "Longitudinal status": "REVIEW",
        "Overall D/C value": float("nan"), "Development status": "REVIEW"}
    notes = []
    def blocked(note, *, status="REVIEW"):
        known_failure = any(result.get(key) == "FAIL" for key in ("Stress status", "Transverse status", "Detailing status"))
        partial = any(math.isfinite(_number(result.get(key))) for key in ("Stress D/C value", "Transverse D/C value"))
        failures = []
        for label, key, dc_key in (("Compression/Veff", "Stress status", "Stress D/C value"),
                ("Transverse reinforcement", "Transverse status", "Transverse D/C value"),
                ("Transverse detailing", "Detailing status", "Spacing D/C")):
            if result.get(key) == "FAIL":
                dc = _number(result.get(dc_key))
                failures.append(label + (f" D/C={dc:.3f}" if math.isfinite(dc) else " fails"))
        return {**result, "Status": "FAIL" if known_failure else status,
            "Calculation status": "PARTIAL" if partial else "SOURCE REQUIRED",
            "Longitudinal status": "DATA REQUIRED", "Overall D/C value": float("nan"),
            "Failure reason": "; ".join(failures),
            "Review reason": "; ".join([*notes, note]), "Notes": "; ".join([*notes, note])}
    if not all(math.isfinite(v) for v in [x, mu, nu, vu, tu, span]) or span <= 0 or not 0 <= x <= span:
        return blocked("Concurrent Mu, Nu, Vu, Tu and physical station must all be finite within the member.")
    if max(abs(mu), abs(nu), abs(vu), abs(tu)) <= 1e-9:
        return {**result, "Status": "NO DEMAND", "Stress status": "NOT REQUIRED", "Transverse status": "NOT REQUIRED",
            "Longitudinal status": "NOT REQUIRED", "Development status": "NOT REQUIRED", "Notes": "Zero concurrent actions."}
    result.update({"M2 reference kN-m": row.get("Muy"), "V3 reference kN": row.get("Vux"),
        "Section basis": "PRECAST I-GIRDER", "Reference action policy": "M2 and V3 retained as reference only"})
    if ambiguous_case:
        notes.append("Multiple concurrent action vectors at the same case/x: all physical rows checked; supplemental dv interpolation is withheld.")
    torsion = ap._beam_uls_igird_torsion_result_for_row(state, row, strength_route=strength_route) if abs(tu) > 1e-9 else {}
    threshold = str(torsion.get("Threshold status") or ("BELOW THRESHOLD" if abs(tu) <= 1e-9 else ""))
    result.update({"Threshold status": threshold, "Threshold kN-m": torsion.get("Threshold kN-m", float("nan"))})
    if not threshold:
        return blocked("Torsion threshold source unavailable: " + str(torsion.get("Notes") or ""))
    needs_t = threshold == "DESIGN REQUIRED"
    if abs(mu) <= 1e-9 and face == "top" and not needs_t:
        return {**result, "Status": "NOT APPLICABLE", "Notes": "At zero Mu below the torsion threshold, the default bottom flexural tension chord owns the shear-only longitudinal check."}
    zone = ap._beam_uls_active_shear_zone_for_station(state, x, require_coverage=True)
    result["Coverage status"] = "PASS" if zone is not None else "REQUIRED"
    if zone is None:
        return blocked("No physical transverse zone covers this station.", status="DATA REQUIRED")
    result["Zone"] = str(zone.get("Zone") or "-")
    if needs_t:
        source = ap._beam_uls_igird_torsion_zone_source(state, x_m=x)
        result["Coverage status"] = "PASS" if source.get("ready") else "REQUIRED"
        if not source.get("ready"):
            return blocked(str(source.get("reason") or "Torsion-qualified closed hoop with 135° hook and finite auto ph required."), status="DATA REQUIRED")
    inp, messages = igird_shear_section.analysis_input_for_station(state, row=row,
        strength_route=strength_route, capacity_direction=-1.0 if face == "top" else 1.0)
    if inp is None:
        return blocked("; ".join(messages))
    prepared = igird_shear_section.prepared_section(state)
    fc = min(prepared["web_fc_MPa"], ksi_to_mpa(10.0 if needs_t else 15.0))
    if inp.concrete_material.density_kg_m3 < 2200.0:
        return blocked("Lightweight concrete requires a verified lambda/source branch; the ULS7 normal-weight route does not infer lambda.")
    bv = _number(ap._beam_uls_web_width_mm(prepared["web_geometry"])[0])
    # This sign only selects the physical tension half/depth; the real Mu
    # remains unchanged in epsilon and in the longitudinal force equation.
    depths = ap._beam_uls_effective_shear_depth_values_mm(state, inp,
        mux_kNm=-abs(mu or 1.0) if face == "top" else abs(mu or 1.0), strength_route=strength_route, row=row)
    result.update(igird_shear_section.trace_columns(depths))
    dv, d = _number(depths.get("dv_mm")), _number(depths.get("d_mm"))
    bar_area, legs, spacing, fy_input = [ap._beam_uls_stirrup_area_mm2(zone), _number(zone.get("Legs")), _number(zone.get("Spacing_mm")), _number(zone.get("fy_MPa"))]
    if not all(math.isfinite(v) and v > 0 for v in [fc, bv, dv, bar_area, legs, spacing, fy_input]):
        return blocked("Transverse geometry, spacing, material or effective depth is incomplete.", status="DATA REQUIRED")
    if needs_t and legs < 2:
        return blocked("Solid closed hoop needs at least two physical effective shear legs.", status="DATA REQUIRED")
    fy, fy_note = (aashto_torsion_transverse_design_fy_mpa if needs_t else aashto_shear_transverse_design_fy_mpa)(fy_input)
    phi, phi_note = aashto_prestressed_shear_phi(has_unbonded_or_debonded_strands=ap._beam_uls_igird_has_debonded_strands(state))
    provided = bar_area * legs / spacing
    avmin = aashto_min_transverse_avs_mm2_per_mm(fc, bv, fy, lambda_concrete=1.0)
    result.update({"f'c MPa": fc, "bw mm": bv, "d mm": d, "dv mm": dv, "φ": phi,
        "dv basis": depths.get("dv_note"),
        "φ policy": phi_note, "fy input MPa": fy_input, "fy MPa": fy, "fy policy": fy_note,
        "Spacing mm": spacing, "Provided transverse mm2/mm": provided, "Minimum transverse req mm2/mm": avmin})
    from concrete_pmm_pro.analysis.igird_crack_spacing import crack_spacing_source
    has_minimum = provided >= avmin - 1e-12
    crack = crack_spacing_source(state,dv_mm=dv) if not has_minimum else {'ready':False}
    if not has_minimum and not crack['ready']:
        result.update({"Transverse status": "FAIL", "Detailing status": "FAIL"})
        return blocked("Below 5.7.2.5 minimum. sx/ag source for the below-minimum General Procedure is not owned; no theta is fabricated.", status="FAIL")
    ao, ph = _number(torsion.get("Ao mm2")), _number(torsion.get("ph mm"))
    if needs_t and not all(math.isfinite(v) and v > 0 for v in [ao, ph]):
        return blocked("AASHTO solid shear-flow Ao / derived hoop ph is unavailable.", status="DATA REQUIRED")
    veff = math.hypot(abs(vu)*1000.0, 0.9*ph*abs(tu)*1e6/(2*ao)) if needs_t else abs(vu)*1000.0
    # This compression guard is independent of the longitudinal material/fps
    # source. Retain it even if a later longitudinal input is unavailable.
    strut_dc = veff / (phi * 0.25 * fc * bv * dv)
    detail = ap._beam_uls_shear_detailing_guard(strength_route=strength_route, fc_MPa=fc,
        bw_mm=bv, d_eff_mm=d, dv_mm=dv, spacing_mm=spacing, avs_mm2_per_mm=provided,
        fy_MPa=fy, vu_N=veff, phi=phi)
    result.update({"Stress D/C value": strut_dc, "Stress status": "PASS" if strut_dc <= 1+1e-9 else "FAIL",
        "Veff kN": veff/1000.0, "Ao mm2": ao, "ph mm": ph,
        "Detailing status": detail.get("Detailing status"), "Spacing D/C": detail.get("Spacing D/C"),
        "s max mm": detail.get("s max mm")})
    dev_settings = development_settings(state)
    dev_factor = ordinary_development_factor(dev_settings, x_m=x, span_m=span) if inp.rebars else 1.0
    result.update({"Ordinary development factor": dev_factor if dev_factor is not None else float("nan"),
        "Ordinary ld mm": dev_settings["development_length_mm"],
        "Development status": "PASS" if dev_factor is not None else "REVIEW"})
    if dev_factor is None and any(not b.material_name.startswith("Composite deck longitudinal rebar") for b in inp.rebars):
        notes.append("Ordinary bar continuity/development is unconfirmed; zero ordinary strength/stiffness credit, final PASS withheld.")
    from concrete_pmm_pro.analysis.igird_deck_development import station_bar_factors, negative_composite_ready
    factors, bars_ready, deck_trace = station_bar_factors(state, inp.rebars, inp.rebar_materials,
        x_m=x, span_m=span, girder_factor=dev_factor)
    result['Development status'] = 'PASS' if bars_ready else 'REVIEW'
    result['Deck development trace'] = deck_trace
    eps_inp = inp.model_copy(update={"rebars":[b.model_copy(update={"diameter_mm":b.diameter_mm*math.sqrt(f)})
        for b,f in zip(inp.rebars,factors) if f > 0]})
    eps = ap._beam_uls_igird_general_shear_epsilon(state, analysis_input=eps_inp, x_m=x,
        span_length_m=span, tension_face=face, mux_kNm=mu, vu_kN=vu,
        nu_compression_positive_kN=nu, dv_mm=dv, effective_shear_kN=veff/1000.0 if needs_t else None,
        ordinary_development_applied=True)
    if not eps.get("ready"):
        return blocked("General Procedure source: " + str(eps.get("note") or ""))
    params = aashto_general_shear_parameters(epsilon_s=float(eps["epsilon_s_raw"]),
        has_minimum_transverse_reinforcement=has_minimum,sxe_mm=crack.get('sxe mm'))
    if crack['ready']:
        result.update({k:v for k,v in crack.items() if k != 'ready'})
        notes.append(crack['note'])
    theta, cot = params.theta_deg, 1.0/math.tan(math.radians(params.theta_deg))
    vc = aashto_sqrt_fc_stress_mpa(0.0316 * params.beta, fc) * bv * dv
    at_req = abs(tu)*1e6/(phi*2*ao*fy*cot) if needs_t else 0.0
    partial_values = concurrent_vt_si(mu_Nmm=mu*1e6, nu_compression_positive_N=nu*1000,
        vu_N=vu*1000, tu_Nmm=tu*1e6 if needs_t else 0.0, phi=phi, fc_MPa=fc,
        bv_mm=bv, dv_mm=dv, Ao_mm2=ao, ph_mm=ph, fy_MPa=fy, cot_theta=cot, vc_N=vc,
        avs_provided=provided, ats_required=at_req, avs_minimum=avmin, aps_fps_N=0.0, as_fy_N=0.0)
    result.update({"Transverse D/C value": partial_values["transverse_dc"],
        "Transverse status": "PASS" if partial_values["transverse_dc"] <= 1+1e-9 else "FAIL",
        "Vc kN": vc/1000.0, "Vs allocated kN": partial_values["vs_nominal_N"]/1000.0,
        "Vs used kN": partial_values["vs_used_N"]/1000.0, "β": params.beta, "θ deg": theta, "θ cot": cot,
        "εs raw": eps["epsilon_s_raw"], "εs used": params.epsilon_s_used,
        "εs numerator N": eps.get("numerator_N"), "εs denominator N": eps.get("denominator_N"),
        "Av shear req mm2/mm": partial_values["shear_required"], "At torsion req mm2/mm": at_req,
        "Governing transverse req mm2/mm": partial_values["combined_required"],
        "Combined transverse req mm2/mm": partial_values["combined_required"],
        "Av available for shear mm2/mm": partial_values["available_shear"]})
    _, ymin, _, ymax = ap._beam_uls_section_bounds(inp.section_geometry)
    ymid = 0.5*(ymin+ymax)
    mats = {m.name: m for m in inp.rebar_materials}
    raw_as, as_force, developed_as = 0.0, 0.0, 0.0
    for b, factor in zip(inp.rebars,factors):
        if (face == "bottom" and b.y_mm > ymid) or (face == "top" and b.y_mm < ymid):
            continue
        raw_as += b.area_mm2
        if b.material_name not in mats:
            return blocked(f"Longitudinal material {b.material_name} is unresolved.")
        as_force += b.area_mm2 * mats[b.material_name].fy_MPa * factor
        developed_as += b.area_mm2 * factor
    aps_dev = _number(eps.get("Aps_developed_mm2"))
    fps_trace = {"ready": True, "fps_min_MPa": 0.0, "c_mm": float("nan"), "residual_N": 0.0}
    if aps_dev > 0:
        nominal_inp = inp
        if nominal_inp is None:
            return blocked("Nominal fps analysis input is unavailable.")
        # The concurrent route owns developed precast ordinary bars only.
        # Optional deck bars remain a separate Flexure source: no unverified
        # deck-bar development is credited to the nominal fps equilibrium.
        nominal_inp = nominal_inp.model_copy(update={"rebars": eps_inp.rebars})
        key = ap._beam_uls_flexure_capacity_state_key(nominal_inp, strength_route=strength_route,
            demand_kNm=-1.0 if face == "top" else 1.0, capacity_direction=-1.0 if face == "top" else 1.0,
            solver_engine="uls7_nominal_fps") + face
        if key not in nominal_cache:
            nominal_cache[key] = nominal_tension_fps(nominal_inp, moment_sign=-1.0 if face == "top" else 1.0,
                axial_nominal_N=nu*1000.0/phi, tension_y_mid_mm=ymid)
        fps_trace = nominal_cache[key]
        if not fps_trace.get("ready"):
            return blocked("Nominal fps source: " + str(fps_trace.get("note") or ""))
    fps = _number(fps_trace["fps_min_MPa"])
    aps_force = aps_dev * fps
    values = concurrent_vt_si(mu_Nmm=mu*1e6, nu_compression_positive_N=nu*1000,
        vu_N=vu*1000, tu_Nmm=tu*1e6 if needs_t else 0.0, phi=phi, fc_MPa=fc,
        bv_mm=bv, dv_mm=dv, Ao_mm2=ao, ph_mm=ph, fy_MPa=fy, cot_theta=cot, vc_N=vc,
        avs_provided=provided, ats_required=at_req, avs_minimum=avmin,
        aps_fps_N=aps_force, as_fy_N=as_force)
    detail = ap._beam_uls_shear_detailing_guard(strength_route=strength_route, fc_MPa=fc,
        bw_mm=bv, d_eff_mm=d, dv_mm=dv, spacing_mm=spacing, avs_mm2_per_mm=provided,
        fy_MPa=fy, vu_N=veff, phi=phi)
    config = ap._beam_uls_igird_torsion_settings(state)
    corner = bool(config.get("corner_longitudinal_reinforcement_confirmed"))
    perimeter = bool(config.get("longitudinal_perimeter_distribution_confirmed"))
    # Inheritance from Article 5.7.3.5, pretensioned/debonded tensile steel.
    ps_dominance = aps_force > as_force if raw_as > 0 or aps_dev > 0 else False
    long_pass = values["longitudinal_dc"] <= 1 + 1e-9 and ps_dominance
    result.update({"Stress status": "PASS" if values["strut_dc"] <= 1+1e-9 else "FAIL",
        "Transverse status": "PASS" if values["transverse_dc"] <= 1+1e-9 else "FAIL",
        "Longitudinal status": "PASS" if long_pass else "FAIL",
        "Detailing status": str(detail.get("Detailing status") or "REVIEW"),
        "Corner longitudinal status": "CONFIRMED" if corner else ("REQUIRED" if needs_t else "NOT REQUIRED"),
        "Perimeter longitudinal status": "CONFIRMED" if perimeter else ("REQUIRED" if needs_t else "NOT REQUIRED"),
        "Prestress dominance status": "PASS" if ps_dominance else "FAIL",
        "Stress D/C value": values["strut_dc"], "Transverse D/C value": values["transverse_dc"],
        "Longitudinal D/C value": values["longitudinal_dc"],
        "Overall D/C value": max(values["strut_dc"],values["transverse_dc"],values["longitudinal_dc"],_number(detail.get("Detailing D/C value"))),
        "Vc kN": vc/1000, "Vs allocated kN": values["vs_nominal_N"]/1000,
        "Vs used kN": values["vs_used_N"]/1000, "Vp kN": 0.0, "Veff kN": veff/1000,
        "β": params.beta, "θ deg": theta, "θ cot": cot,
        "εs raw": float(eps["epsilon_s_raw"]), "εs used": params.epsilon_s_used,
        "εs numerator N": eps.get("numerator_N"), "εs denominator N": eps.get("denominator_N"),
        "General Procedure branch": params.basis,
        "Av shear req mm2/mm": values["shear_required"], "At torsion req mm2/mm": at_req,
        "Combined transverse req mm2/mm": values["combined_required"],
        "Governing transverse req mm2/mm": values["combined_required"],
        "Av available for shear mm2/mm": values["available_shear"], "Ao mm2": ao, "ph mm": ph,
        "As raw tension mm2": raw_as, "As developed tension mm2": developed_as,
        "As fy kN": as_force/1000, "Aps fps kN": aps_force/1000,
        "Aps raw tension mm2": eps.get("Aps_raw_mm2"), "Aps developed tension mm2": aps_dev,
        "Aps development factor min": eps.get("min_development_factor"),
        "fpo transfer factor min": eps.get("min_transfer_factor"), "fpo full MPa": eps.get("fpo_full_MPa"),
        "fps nominal min MPa": fps, "fps c mm": fps_trace["c_mm"], "fps equilibrium residual N": fps_trace["residual_N"],
        "Longitudinal required kN": values["longitudinal_required_N"]/1000,
        "Longitudinal RHS raw kN": values["longitudinal_rhs_raw_N"]/1000,
        "Longitudinal resistance kN": values["longitudinal_resistance_N"]/1000,
        "Mu term kN": values["mu_term_N"]/1000, "Nu term kN": values["nu_term_N"]/1000,
        "Shear term kN": values["shear_term_N"]/1000, "Torsion term kN": values["torsion_term_N"]/1000,
        "Diagonal term kN": values["diagonal_term_N"]/1000,
        "Spacing D/C": detail.get("Spacing D/C"), "s max mm": detail.get("s max mm"),
        "Interaction form": "Veff / compression limit (conservative guard)",
        "Capacity": f"Long. R = {values['longitudinal_resistance_N']/1000:,.2f} kN",
        "Demand": f"Long. F = {values['longitudinal_required_N']/1000:,.2f} kN"})
    failures = [result[k] for k in ["Stress status","Transverse status","Longitudinal status","Detailing status"]]
    review = not bars_ready or bool(notes) or (needs_t and (not corner or not perimeter)) or (mu < -1e-9 and not negative_composite_ready(state.get("section_parameters") or {})) or depths.get("Depth source status") != "PASS" or depths.get("Composite action status") not in {"PASS", "NOT APPLICABLE"}
    result["Status"] = "FAIL" if "FAIL" in failures or depths.get("Composite action status") == "FAIL" else ("REVIEW" if review else "PASS")
    from concrete_pmm_pro.analysis.igird_shear_support import station_region
    region = station_region(state,x_m=x,span_m=span,h_mm=depths.get('h mm',prepared['precast_depth_mm']))
    result.update(region)
    result['Scope note'] = region['Support region note']
    result["Calculation status"] = "COMPLETE"
    if not bars_ready:
        result["Longitudinal status"] = "REVIEW" if long_pass else "FAIL"
    if mu < -1e-9 and not negative_composite_ready(state.get("section_parameters") or {}):
        notes.append("Top tension-side force checked; negative composite flexure certification remains separate and is outside the accepted positive route.")
    if not ps_dominance:
        notes.append("5.7.3.5 pretensioned condition fails: developed Aps*fps must exceed developed As*fy on the checked tension side, independently of force D/C.")
    if needs_t and not corner:
        notes.append("At least one bar/tendon at every hoop corner is not confirmed.")
    if needs_t and not perimeter:
        notes.append("Longitudinal distribution around the physical hoop perimeter is not confirmed.")
    result["Review reason"] = "; ".join(notes)
    result["Failure reason"] = ", ".join(k.replace(" status", "") for k in
        ["Stress status", "Transverse status", "Longitudinal status", "Detailing status", "Prestress dominance status"] if result.get(k) == "FAIL")
    notes.extend(["Concurrent physical row retained; support faces remain eligible. At Mu=0 both tension halves are checked.",
        "One physical closed-hoop Av/s is counted once against max(Av/s shear requirement, Av/s minimum)+2At/s torsion requirement.",
        "Vs relief uses residual hoop area after torsion allocation and is capped at Vu/phi per 5.7.3.5.",
        "Straight pretensioned strands: Vp=0, lambda_duct=1. No tendon slope or duct is inferred.",
        "Nominal fps equilibrium uses the same station-developed girder/deck longitudinal bars as the strain and force checks.",
        "Veff compression cap is an additional conservative guard; no ACI Aoh/ph stress shortcut is used.",
        str(eps.get("note") or ""),str(fps_trace.get("note") or ""),str(dev_settings.get("note") or ""), str(depths.get("Depth note") or "")])
    result["Notes"] = "; ".join(n for n in notes if n)
    return result


def calculation_trace(row: Mapping | None) -> pd.DataFrame:
    if not row or row.get("Result version") != RESULT_VERSION:
        return pd.DataFrame()
    def n(key):
        v = _number(row.get(key))
        return f"{v:,.6g}" if math.isfinite(v) else "source unavailable"
    rows = [
        ("Concurrent actions", "Mu, Nu, Vu, Tu from one physical row/case", f"Mu={n('Mu kN-m')} kN-m; Nu(app)={n('Nu app kN')} kN; Vu={n('Vu kN')} kN; Tu={n('Tu kN-m')} kN-m", "Same row; Nu(AASHTO)=-Nu(app)", "5.7.3.6.1 / 5.7.3.6.3"),
        ("General Procedure", "Veff=sqrt[Vu²+(0.9phTu/(2Ao))²] → εs → β, θ", f"Veff={n('Veff kN')} kN; εs raw={n('εs raw')}; adopted={n('εs used')}; β={n('β')}; θ={n('θ deg')} deg", str(row.get('General Procedure branch') or '-'), "5.7.3.4.2-1/-3/-4/-5"),
        ("Physical transverse sum", "Required=max(Av/s shear, Av/s minimum)+2At/s torsion ≤ Av/s physical", f"max({n('Av shear req mm2/mm')},{n('Minimum transverse req mm2/mm')})+2×{n('At torsion req mm2/mm')}={n('Governing transverse req mm2/mm')} mm²/mm; provided={n('Provided transverse mm2/mm')}", f"D/C={n('Transverse D/C value')} · {row.get('Transverse status','-')}", "5.7.3.6.1 / 5.7.2.5"),
        ("Vs relief", "Av/s available=max(0, Av/s physical−2At/s required); Vs_used=min(Vs allocated, |Vu|/φ)", f"Available={n('Av available for shear mm2/mm')} mm²/mm; Vs allocated={n('Vs allocated kN')} kN; Vs used={n('Vs used kN')} kN", "One hoop counted once", "5.7.3.3-4 / 5.7.3.5"),
        ("Nominal fps source", "Pn(c)=Nu(app)/φ; fps=min tension-side nominal strand stresses", f"c={n('fps c mm')} mm; residual={n('fps equilibrium residual N')} N; fps={n('fps nominal min MPa')} MPa", "AASHTO block + bonded-strand strain compatibility", "5.6.2 / 5.7.3.6.3-1"),
        ("Longitudinal resistance", "R=Aps_developed fps+ΣAs_developed fy", f"{n('Aps fps kN')}+{n('As fy kN')}={n('Longitudinal resistance kN')} kN", f"Ordinary development={n('Ordinary development factor')}; Aps development={n('Aps development factor min')}", "5.7.3.5 / 5.9.4.3.2 / 5.10.8.2.1a"),
        ("Longitudinal demand", "F=|Mu|/(φdv)+0.5Nu(AASHTO)/φ+cotθ sqrt[(|Vu/φ−Vp|−0.5Vs)²+(0.45phTu/(2Aoφ))²]", f"{n('Mu term kN')}+({n('Nu term kN')})+{n('θ cot')}×hypot({n('Shear term kN')},{n('Torsion term kN')})={n('Longitudinal RHS raw kN')} kN; adopted={n('Longitudinal required kN')}", f"F/R={n('Longitudinal D/C value')} · {row.get('Longitudinal status','-')}", "5.7.3.6.3-1"),
        ("Pretensioned steel condition", "Aps_developed fps > ΣAs_developed fy", f"{n('Aps fps kN')} > {n('As fy kN')} kN", str(row.get('Prestress dominance status') or '-'), "5.7.3.5"),
        ("Coverage and detailing", "Physical zone; closed hoop/hooks; s≤smax; corner and perimeter longitudinal confirmation", f"Zone={row.get('Zone','-')}; s={n('Spacing mm')} mm; smax={n('s max mm')} mm", f"Coverage={row.get('Coverage status','-')}; detailing={row.get('Detailing status','-')}; corner={row.get('Corner longitudinal status','-')}", "5.7.2.5/.6 / 5.7.3.6.3"),
    ]
    return pd.DataFrame(rows, columns=["Step","Equation / route","Substitution / units","Result / branch","Code basis"])


def variable_definitions() -> pd.DataFrame:
    return pd.DataFrame([
        ("Mu, Nu, Vu, Tu","Concurrent imported actions. Nu input follows the declared source convention; Nu(app) is compression-positive after conversion.","kN-m, kN, kN, kN-m"),
        ("Veff","Torsion-modified shear used in longitudinal strain; actual Vu remains in Eq. 5.7.3.6.3-1.","kN"),
        ("Av/s physical, At/s","Av/s = effective shear legs×bar area/spacing; At/s = one closed hoop leg/spacing. The same hoop is counted once.","mm²/mm"),
        ("Ao, ph","Ao is AASHTO shear-flow enclosed area; ph is the actual derived closed-hoop centerline perimeter.","mm², mm"),
        ("Vs used","Shear resistance of the remaining transverse allocation after torsion; capped at Vu/phi.","kN"),
        ("Aps fps, As fy","Developed tension-side strand force plus developed ordinary bar yield force from the single existing rebar source.","kN"),
        ("fps","Minimum tension-side nominal strain-compatible strand stress; conservative group sum bound, distinct from fpo and fpu.","MPa"),
        ("ld","Verified governing straight ordinary-bar development length; no presumed anchorage or continuity.","mm"),
        ("φ, β, θ","Accepted bonded/debonded resistance factor; General Procedure concrete factor and diagonal compression angle.","-, -, deg"),
    ],columns=["Variable","Engineering meaning","Unit"])


def render_development_inputs(*, expanded: bool = False) -> None:
    import streamlit as st
    from concrete_pmm_pro.analysis.igird_combined_vt import DEVELOPMENT_KEY
    if str(st.session_state.get("section_preset_key") or "") != "parametric_i_girder":
        return
    current = development_settings(st.session_state)
    with st.expander("Longitudinal development — V/T", expanded=expanded):
        st.caption("The existing Longitudinal Rebar table is the ordinary-bar source. These confirmations govern bar development credit in Shear, Torsion and Combined V+T.")
        continuous = st.checkbox("All active ordinary bars are continuous over the full physical member",
            value=current["continuous_full_span_confirmed"], key="igird_vt_bars_continuous")
        cols = st.columns(2)
        with cols[0]:
            left = st.checkbox("Left physical end x=0: full bar strength is verified",
                value=current["left_end_anchored_confirmed"], key="igird_vt_bars_left_anchor")
        with cols[1]:
            right = st.checkbox("Right physical end x=L: full bar strength is verified",
                value=current["right_end_anchored_confirmed"], key="igird_vt_bars_right_anchor")
        ld = st.number_input("Verified governing straight-bar development length ld (mm)",
            min_value=0.0, value=current["development_length_mm"], step=50.0, key="igird_vt_bars_ld",
            help="Enter the largest required straight-bar development length, at least 304.8 mm under 5.10.8.2.1a. End anchorage must justify full strength at the model's physical cut-end coordinates; it removes that end's build-up only.")
        note = st.text_input("Development / anchorage drawing or calculation reference", value=current["note"], key="igird_vt_bars_development_note")
        st.caption("These end confirmations apply to x=0/L. Anchorage at an inset bearing alone does not establish full bar strength at the physical beam end.")
        settings = {"continuous_full_span_confirmed": continuous, "left_end_anchored_confirmed": left,
            "right_end_anchored_confirmed": right, "development_length_mm": ld, "note": note}
        # Metadata persists through the existing project JSON route; no schema change.
        st.session_state[DEVELOPMENT_KEY] = settings
        metadata = dict(st.session_state.get("project_metadata") or {})
        metadata[DEVELOPMENT_KEY] = settings
        st.session_state["project_metadata"] = metadata
        if not continuous or (not (left and right) and ld < 304.8):
            st.warning("Development is unconfirmed. Combined V+T will withhold final PASS and will not assume ordinary bar strength or stiffness.")
        else:
            st.caption("Straight unanchored ends receive zero strength below 304.8 mm bonded length, then min(available length/ld, 1). Cut-off bars or mixed anchorage require separate review; each end declaration must justify the actual x=0/L cut-end station.")


def render_workspace(df: pd.DataFrame | None, *, code_label: str, member_name: str = "") -> None:
    import streamlit as st
    from concrete_pmm_pro.ui import analysis_page as ap
    if df is None or df.empty:
        st.info("No concurrent V+T check rows are available. Calculate Shear + Torsion for the current imported ULS actions.")
        return
    gov = ap._beam_uls_governing_combined_vt_row(df)
    if not gov:
        st.info("No active concurrent actions require a check.")
        return
    status = str(gov.get("Status") or "REVIEW")
    def value(key, unit=""):
        v = _number(gov.get(key))
        if math.isinf(v):
            return "∞"
        return f"{v:,.3f}{(' '+unit) if unit else ''}" if math.isfinite(v) else "SOURCE REQUIRED"
    cards = [
        {"title":"Concurrent V+T","value":status,"detail":f"{gov.get('Case','-')} @ x={gov.get('Governing x','-')} · {gov.get('Tension face','-')} tension side", "status":"danger" if status == "FAIL" else ("ready" if status == "PASS" else "warning"),"strong":True},
        {"title":"Transverse sum","value":value("Transverse D/C value"),"detail":"One physical hoop counted once · AASHTO 5.7.3.6.1","status":"danger" if gov.get('Transverse status') == 'FAIL' else 'info'},
        {"title":"Longitudinal force","value":value("Longitudinal D/C value"),"detail":f"F {value('Longitudinal required kN','kN')} / R {value('Longitudinal resistance kN','kN')}","status":"danger" if gov.get('Longitudinal status') == 'FAIL' else 'info'},
        {"title":"General Procedure","value":f"θ {value('θ deg','deg')}","detail":f"β {value('β')} · Veff {value('Veff kN','kN')}","status":"info"},
        {"title":"Development","value":str(gov.get('Development status','REVIEW')),"detail":f"As factor {value('Ordinary development factor')} · Aps factor {value('Aps development factor min')}","status":"info" if gov.get('Development status') == 'PASS' else 'warning'},
    ]
    ap._render_analysis_summary_strip(cards[:3], columns=3)
    dc_columns = [c for c in ("Stress D/C value", "Transverse D/C value", "Longitudinal D/C value") if c in df]
    finite_rows = df[dc_columns].apply(lambda column: pd.to_numeric(column, errors="coerce").map(lambda v: pd.notna(v) and math.isfinite(float(v)))).any(axis=1) if dc_columns else pd.Series(False, index=df.index)
    st.caption(f"Calculation completed: {len(df)} concurrent check rows; {int(finite_rows.sum())} rows with finite D/C. Original source rows and acceptance gates are retained.")
    st.dataframe(pd.DataFrame([{ 'Section basis':gov.get('Section basis','SOURCE REQUIRED'),
        'Composite action':gov.get('Composite action status','REVIEW'), 'Source vectors':gov.get('Source coupling','USER TABLE — VERIFY'),
        'h (mm)':gov.get('h mm'), 'dv (mm)':gov.get('dv mm'), 'Region':gov.get('Support region','REVIEW')}]),
        use_container_width=True,hide_index=True)
    readiness = source_readiness_dataframe(df)
    if not readiness.empty:
        with st.expander("Required inputs / source review", expanded=False):
            st.dataframe(readiness, use_container_width=True, hide_index=True)
    if ap._beam_uls_combined_vt_has_finite_utilization(df):
        from concrete_pmm_pro.ui.igird_vt_workspace import render_combined_chart
        render_combined_chart(df, code_label=code_label, member_name=member_name)
    else:
        st.info("Calculation completed, but no finite D/C can be drawn yet. Complete the required inputs listed above, then press Calculate Shear + Torsion again.")
    missing = df.loc[df["Status"].isin(["REVIEW","DATA REQUIRED"]) | df.get("Calculation status",pd.Series(index=df.index,dtype=object)).eq("PARTIAL")]
    uncovered = df.loc[df.get("Coverage status",pd.Series(index=df.index,dtype=object)).eq("REQUIRED")]
    if not uncovered.empty:
        st.warning(f"Transverse coverage is incomplete at {len(uncovered)} check row(s), even if another covered station governs a strength failure.")
    if not missing.empty:
        st.warning(f"{len(missing)} check row(s) still require source/development review. A passing numerical row does not certify the member while any required row is unresolved.")
    if status == "FAIL":
        st.error("Concurrent V+T fails: " + str(gov.get("Failure reason") or gov.get("Review reason") or "governing strength/detailing gate") + ". Review the stored governing equations before accepting the section.")
    elif status == "PASS":
        st.success("Current concurrent V+T sectional rows and their development/detailing gates pass. Bearing/D-region, slab and other separate scope checks are not certified by this status.")
    else:
        st.warning("Concurrent V+T needs review. " + str(gov.get("Review reason") or "Complete the sources and confirmations before final sectional acceptance."))
    compact = [c for c in ["Governing x","Case","Section basis","Composite action status","Source coupling","Support region","Support region status","h mm","dv mm","Tension face","Status","Calculation status","Transverse status","Longitudinal status",
        "Coverage status","Development status","Detailing status","Corner longitudinal status","Perimeter longitudinal status","Prestress dominance status",
        "Transverse D/C value","Longitudinal required kN","Longitudinal resistance kN","Longitudinal D/C value","Review reason"] if c in df]
    with st.expander("Station results / source status", expanded=False):
        st.dataframe(df[compact],use_container_width=True,hide_index=True)
    with st.expander("Calculation trace / Equations — governing concurrent V+T station",expanded=False):
        st.dataframe(calculation_trace(gov),use_container_width=True,hide_index=True)
    with st.expander("Variable definitions / Engineering terms",expanded=False):
        st.dataframe(variable_definitions(),use_container_width=True,hide_index=True)
    with st.expander("Concurrent V+T — detailed engineering audit",expanded=False):
        st.dataframe(df,use_container_width=True,hide_index=True)
    st.caption("Scope: uniaxial solid pretensioned I-Girder sectional V+T with concurrent imported actions. Nominal fps uses the calculated composite section; composite-action acceptance is shown separately; ordinary bars remain the same physical source used by Flexure. Vp=0 and λduct=1 for straight pretensioned strands. Negative composite requires defined developed deck layers; biaxial shear/flexure, fatigue, bearing/D-regions, hook/lap execution and shop-drawing verification remain separate. Missing continuity/development confirmation withholds PASS.")


def source_readiness_dataframe(df: pd.DataFrame | None) -> pd.DataFrame:
    """Summarize stored blocking reasons and actionable input locations without solving."""
    columns = ["Required source / review", "Check rows", "Stations", "Input location", "Required action"]
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)
    partial = df.get("Calculation status", pd.Series(index=df.index, dtype=object)).eq("PARTIAL")
    unresolved = df.loc[df["Status"].isin(["DATA REQUIRED", "REVIEW"]) | partial].copy(deep=True)
    groups = {}
    for _, row in unresolved.iterrows():
        reason = str(row.get("Review reason") or "").strip()
        # Early-return rows append their actual blocking gate after advisory
        # notes. Keep each gate separate; never convert missing strength to zero.
        reasons = [r.strip() for r in reason.split(";") if r.strip()]
        if not reasons:
            reasons = [str(row.get("Source coupling") or "Review the stored equation/source trace.")]
        for issue in dict.fromkeys(reasons):
            if pd.notna(row.get("Source ItemType")) and issue.startswith(("Muy requires biaxial review", "Vux requires biaxial review")):
                # Native M2/V3 are retained reference values in this workflow,
                # not missing primary V/T inputs. Original advisory notes stay
                # unchanged in the compact and detailed engineering audit.
                continue
            group = groups.setdefault(issue, {"count":0, "stations":set()})
            group["count"] += 1
            group["stations"].add(str(row.get("Governing x") or "-"))
    rows = []
    for issue, group in groups.items():
        lower = issue.lower()
        location, action = "Analysis → Calculation trace / Equations", "Review this stored source/check and correct the model before recalculating."
        if "transverse zone" in lower or "closed hoop" in lower or "closed torsion loop" in lower or "135°" in lower or "torsion" in lower and "zone" in lower:
            location = "Sections → Rebar → Transverse Rebar"
            action = "Check zone ranges and actual cage details; confirm Use for Torsion, Closed Loop and 135° Hook for applicable zones."
        elif "material" in lower and ("unresolved" in lower or "unavailable" in lower):
            location = "Analysis → Complete missing longitudinal materials"
            action = "Enter verified fy and Es for the referenced steel grade here, or assign the bars to an existing defined material in Sections."
        elif "ordinary" in lower and ("continu" in lower or "development" in lower) or "anchorage" in lower:
            location = "Analysis → Longitudinal development — Shear + Torsion"
            action = "Verify bar continuity, end anchorage and governing ld; enter only confirmations supported by the actual cage and calculation."
        elif "corner" in lower or "perimeter" in lower:
            location = "Sections → Rebar → Transverse Rebar"
            action = "Verify and confirm the actual corner bars/strands and longitudinal perimeter distribution."
        elif "concurren" in lower or "envelope" in lower:
            location = "Loads → Final ULS"
            action = "Use corresponding concurrent FEA action rows for final coupled acceptance; Max/Min bounds retain numerical screening only."
        stations = sorted(group["stations"], key=lambda s: _number(s.replace(" m", "")))
        station_text = ", ".join(stations[:6]) + (f" … ({len(stations)} positions)" if len(stations) > 6 else "")
        rows.append({"Required source / review":issue, "Check rows":group["count"], "Stations":station_text,
            "Input location":location, "Required action":action})
    return pd.DataFrame(rows, columns=columns)
