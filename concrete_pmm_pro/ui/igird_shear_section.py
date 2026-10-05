"""Analysis-only Final-Composite section adapter for I-girder V/T strain.

Deck concrete participates in the flexural resultants/de/dv. Web shear
properties and the qualified closed torsion hoop remain precast properties.
The per-Calculate dictionary is ephemeral, never a project result cache.
"""
from __future__ import annotations

from collections.abc import Mapping
import math

from concrete_pmm_pro.analysis.igird_flexure_development import (
    SectionEquilibrium, development_settings as flexure_settings, strand_families,
)
from concrete_pmm_pro.analysis.igird_combined_vt import development_settings
from concrete_pmm_pro.analysis.igird_shear_depth import RESULT_VERSION, developed_shear_depth

RUNTIME_KEY = "_igird_shearcomp_runtime"
DEPTH_COLUMNS = ["Section basis", "Depth source status", "Composite action status", "h mm",
    "Precast h mm", "Compression f'c MPa", "de mm", "C-T lever arm mm", "dv lower bound mm",
    "y C mm", "y T mm", "C kN", "T kN", "Depth Mn kN-m", "Depth c mm",
    "Depth force residual N", "Depth moment residual N-mm", "dv basis", "Depth note"]


def _runtime(state):
    value = state.get(RUNTIME_KEY)
    return value if isinstance(value, dict) else {}


def geometry_signature(state):
    """Canonical physical coordinates; ignore names and vertex ordering."""
    raw = state.get("section_geometry")
    raw = raw.model_dump() if hasattr(raw, "model_dump") else raw
    if not isinstance(raw, Mapping):
        return None
    def ring(points):
        coords = [(round(float(p["x"]), 6), round(float(p["y"]), 6)) for p in points]
        if len(coords) > 1 and coords[-1] == coords[0]:
            coords.pop()
        if not coords:
            return ()
        forward = [tuple(coords[i:] + coords[:i]) for i in range(len(coords))]
        reverse = list(reversed(coords))
        return min(forward + [tuple(reverse[i:] + reverse[:i]) for i in range(len(reverse))])
    return {"outer": ring(raw.get("outer_polygon") or []),
        "holes": sorted(ring(hole) for hole in raw.get("holes") or [])}


def prepared_section(state):
    from concrete_pmm_pro.ui import analysis_page as ap
    cache = _runtime(state)
    if "section" in cache:
        return cache["section"]
    params = state.get("section_parameters") or {}
    composite = bool(params.get("composite_enabled"))
    analysis_state, notes = state, []
    if composite:
        prep, analysis_state, notes = ap._beam_uls_final_composite_preparation(state)
        if analysis_state is None:
            result = {"ready": False, "notes": notes, "basis": "FINAL COMPOSITE", "composite": True}
            cache["section"] = result
            return result
        # V/T owns the existing precast longitudinal bars and their governing
        # development declaration. Optional deck-bar development is not owned.
        analysis_state = dict(analysis_state)
        analysis_state["rebars"] = list(state.get("rebars") or [])
        notes.append("Effective deck concrete participates in de/dv; deck longitudinal bars receive no V/T credit.")
    geometry = ap._beam_uls_get_state_value(state, "section_geometry")
    concrete = ap._beam_uls_get_state_value(state, "concrete_material")
    try:
        if isinstance(geometry, Mapping):
            geometry = ap.SectionGeometry.model_validate(geometry)
        if isinstance(concrete, Mapping):
            concrete = ap.ConcreteMaterial.model_validate(concrete)
        if not isinstance(geometry, ap.SectionGeometry) or not isinstance(concrete, ap.ConcreteMaterial):
            raise ValueError("Section geometry and concrete material are required for shear depth.")
        _, ymin, _, ymax = ap._beam_uls_section_bounds(geometry)
    except (ValueError, TypeError, AttributeError) as exc:
        result = {"ready": False, "notes": [*notes, str(exc)], "composite": composite,
            "basis": "FINAL COMPOSITE" if composite else "PRECAST I-GIRDER"}
        cache["section"] = result
        return result
    result = {"ready": True, "state": analysis_state, "web_geometry": geometry,
        "web_fc_MPa": float(concrete.fc_MPa), "precast_depth_mm": ymax - ymin,
        "ymin_mm": ymin, "composite": composite,
        "basis": "FINAL COMPOSITE" if composite else "PRECAST I-GIRDER", "notes": notes}
    cache["section"] = result
    return result


def analysis_input_for_station(state, *, row, strength_route, capacity_direction=None):
    from concrete_pmm_pro.ui import analysis_page as ap
    prepared = prepared_section(state)
    if not prepared["ready"]:
        return None, list(prepared["notes"])
    return ap._beam_uls_flexure_analysis_input_for_station(prepared["state"], row=row,
        strength_route=strength_route, capacity_direction=capacity_direction, prestress_force_stage="final")


def composite_action_gate(state, *, strength_route):
    """Read current acceptance inputs/results; never run interface analysis."""
    from concrete_pmm_pro.ui import analysis_page as ap
    cache = _runtime(state)
    if "composite_gate" in cache:
        return cache["composite_gate"]
    prepared = prepared_section(state)
    if not prepared.get("composite"):
        return "NOT APPLICABLE", []
    if not prepared["ready"]:
        return "REVIEW", list(prepared["notes"])
    params = state.get("section_parameters") or {}
    notes = []
    if not bool(params.get("Be_strength_verified", False)):
        notes.append("Composite effective width Be is not confirmed for strength.")
    source = cache.get("active_df")
    if source is None:
        source = ap._active_beam_uls_demand_dataframe_from_session(state)
    supported = ap._igird_interface_source_dataframe(source)
    signature = ap._igird_interface_shear_hash(state, supported,
        settings=ap._igird_interface_shear_settings_from_state(state), strength_route=strength_route)
    entry = ap._beam_uls_manual_cache(state).get(ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME)
    interface = "PENDING"
    if isinstance(entry, dict):
        if entry.get("input_hash") == signature and entry.get("result_version") == ap._IGIRDER_INTERFACE_SHEAR_RESULT_VERSION:
            interface = ap._igird_interface_overall_status(ap._beam_uls_cached_dataframe(entry, "interface_shear_df"))
        else:
            interface = "STALE"
    if interface != "PASS":
        notes.append(f"Final-Composite action requires a current PASS in Interface Shear (current: {interface}).")
    result = ("PASS" if not notes else ("FAIL" if interface == "FAIL" else "REVIEW"), notes)
    cache["composite_gate"] = result
    return result


def depth_values(state, *, row, strength_route, capacity_direction=None):
    from concrete_pmm_pro.ui import analysis_page as ap
    cache = _runtime(state)
    prepared = prepared_section(state)
    sign = -1.0 if float(capacity_direction if capacity_direction is not None else (row.get("Mux") or 1.0)) < 0 else 1.0
    x = float(row["Station x (m)"])
    nu = ap.girder_axial_demand_kN(row, state) * 1000.0
    span = ap._beam_uls_span_length_from_state(state, is_building=False)
    common = {"dv_mm": float("nan"), "d_mm": float("nan"), "tension_face": "top" if sign < 0 else "bottom",
        "Section basis": prepared["basis"], "Depth source status": "REVIEW"}
    if not prepared["ready"]:
        return {**common, "dv_note": "; ".join(prepared["notes"])}
    key = ("depth", sign, x, nu)
    if key in cache:
        return cache[key]
    try:
        if not all(math.isfinite(v) for v in (x, nu, span)) or not 0 <= x <= span or span <= 0:
            raise ValueError("Physical station / span / external Nu is invalid for dv.")
        context_key = ("context", sign)
        if context_key not in cache:
            ai, notes = analysis_input_for_station(state, row={**row, "Station x (m)": span / 2.0},
                strength_route=strength_route, capacity_direction=sign)
            if ai is None:
                raise ValueError("; ".join(notes))
            if not ai.settings.include_prestress:
                raise ValueError("The prestressed General Procedure requires the prestressing-steel system to be enabled.")
            settings = flexure_settings(state)
            # Stations are the physical strand cut ends. Do not silently add
            # fictitious bonded extensions from a flexure-only setting.
            settings = {**settings, "left_extension_m": 0.0, "right_extension_m": 0.0}
            families = strand_families(state.get("girder_strand_layout_table"), y_min_mm=prepared["ymin_mm"],
                span_m=span, stage="final", settings=settings)
            known = {m.name for m in ai.rebar_materials}
            missing = sorted({b.material_name for b in ai.rebars if b.material_name not in known})
            ordinary = development_settings(state)
            bars = [b for b in ai.rebars if b.material_name in known]
            ai = ai.model_copy(update={"prestress_elements": [f.element for f in families], "rebars": bars})
            context = SectionEquilibrium(ai, sign)
            cache[context_key] = context, families, ordinary, missing
        context, families, ordinary, missing = cache[context_key]
        reference_key = ("reference", sign, nu)
        if reference_key not in cache:
            confirmed = not context.bars or bool(ordinary.get("continuous_full_span_confirmed"))
            cache[reference_key] = context.solve(nu, bar_factors=[1.0 if confirmed else 0.0] * len(context.bars))
        values = developed_shear_depth(context, families, reference=cache[reference_key],
            x_m=x, span_m=span, nu_n=nu, precast_depth_mm=prepared["precast_depth_mm"], ordinary_settings=ordinary)
        source_ready = not missing and values["ordinary_factor"] is not None
        notes = list(prepared["notes"])
        if missing:
            notes.append("Unresolved longitudinal material excluded from depth strength: " + ", ".join(missing))
        if values["ordinary_factor"] is None:
            notes.append("Unconfirmed ordinary-bar development receives zero strength credit in dv.")
        gate, gate_notes = composite_action_gate(state, strength_route=strength_route)
        notes.extend(gate_notes)
        if sign < 0 and prepared.get("composite"):
            source_ready = False
            notes.append("Negative composite flexure remains outside the certified positive-composite route; this depth is audit-only.")
        if abs(values["force_balance_N"]) > 1e-4 or abs(values["moment_balance_Nmm"]) > max(1e-3, abs(values["Mn_Nmm"]) * 1e-9):
            raise ValueError("The C/T resultants do not reproduce the solved section force/moment equilibrium.")
        dv = values["dv_mm"]
        manual = ap._beam_uls_shear_depth_settings_from_state(state).get("dv_mm")
        dv_note = "AASHTO 5.7.2.8: dv=max(C/T lever arm, 0.9de, 0.72h), using station-developed forces; debonded strand kappa=2."
        if manual is not None:
            if not values["lower_bound_mm"] <= float(manual) <= dv + 1e-6:
                raise ValueError("Manual dv must lie between the code lower bound and the calculated developed C/T-based dv. Clear the override to use Auto.")
            dv = float(manual)
            dv_note += " Conservative manual dv within the verified bounds is used."
        result = {**common, "dv_mm": dv, "d_mm": values["de_mm"], "h_mm": values["h_mm"],
            "d_note": "de uses developed Aps*fps and As*fy force weights, measured from the compression face.",
            "dv_note": dv_note, "Depth source status": "PASS" if source_ready else "REVIEW",
            "Composite action status": gate, "h mm": values["h_mm"], "Precast h mm": prepared["precast_depth_mm"],
            "Compression f'c MPa": context.fc, "de mm": values["de_mm"],
            "C-T lever arm mm": values["lever_arm_mm"], "dv lower bound mm": values["lower_bound_mm"],
            "y C mm": values["y_C_mm"], "y T mm": values["y_T_mm"],
            "C kN": values["C_N"] / 1000, "T kN": values["T_N"] / 1000,
            "Depth Mn kN-m": values["Mn_Nmm"] / 1e6, "Depth c mm": values["c_mm"],
            "Depth force residual N": values["force_balance_N"], "Depth moment residual N-mm": values["moment_balance_Nmm"],
            "dv basis": dv_note, "Depth note": "; ".join(notes), "force_trace": values}
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        result = {**common, "Composite action status": "REVIEW" if prepared.get("composite") else "NOT APPLICABLE",
            "dv_note": str(exc), "dv basis": "AASHTO 5.7.2.8 — depth source unavailable", "Depth note": str(exc)}
    cache[key] = result
    return result


def trace_columns(values):
    return {key: values.get(key, float("nan") if key.endswith((" mm", " kN", " MPa", " N", " N-mm", "kN-m")) else "-")
        for key in DEPTH_COLUMNS}
