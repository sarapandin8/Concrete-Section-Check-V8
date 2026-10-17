"""One Final Flexure command; read-only member, case and chart review.

FLEXURE31 changes orchestration and presentation only. Section and interface
checks keep their own accepted engines, hashes, statuses and summary owners.
No endpoint load correction, strength waiver or result persistence is added.
"""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY, save_active
from concrete_pmm_pro.ui import igird_member_results as members
from concrete_pmm_pro.ui.igird_case_review import AUTO_CASE, controlling_result, ratio_text
from concrete_pmm_pro.ui.result_table_display import result_table_for_display

VERSION = "IGIRDER.FLEXURE31"
CACHE_KEY = "igird_flexure31_runtime_results"
DEMAND = "Demand / capacity"
UTILIZATION = "Utilization"
SOURCE = "CSI source M3"
INTERFACE = "Interface shear"
POLICY_KEY = "igird_flexure_review_policy"
WHOLE = "Whole member — include cut ends"
SEPARATE = "Span section — review cut ends separately"


def zero_L_are_cut_ends(state, *, length):
    """Never exclude a bearing station when the girder extends beyond 0/L."""
    from concrete_pmm_pro.analysis.igird_flexure_development import development_settings
    from concrete_pmm_pro.analysis.igird_end_sections import cut_ends
    settings = development_settings(state)
    if settings["left_extension_m"] > 1e-7 or settings["right_extension_m"] > 1e-7:
        return False
    try:
        left, right = cut_ends(state.get("section_parameters") or {}, length)
    except (TypeError, ValueError):
        return False
    return abs(left) <= 1e-7 and abs(right - length) <= 1e-7


def assessment_frames(frame, *, length, separate_ends=False):
    """Review scope only. All original calculated rows remain in the bundle."""
    if frame is None or frame.empty:
        empty = pd.DataFrame() if frame is None else frame.copy()
        return empty, empty.copy()
    xs = pd.to_numeric(frame["Station x (m)"], errors="coerce")
    ends = xs.abs().le(1e-7) | xs.sub(length).abs().le(1e-7)
    return (frame.loc[~ends].copy() if separate_ends else frame.copy(), frame.loc[ends].copy())


def fingerprints(state, rows, *, route):
    from . import analysis_page as ap
    settings = ap._igird_interface_shear_settings_from_state(state)
    return {
        "section": members.result_hash(state, rows, check_name="Flexure", route=route),
        "interface": ap._igird_interface_shear_hash(state,
            ap._igird_interface_source_dataframe(rows), settings=settings, strength_route=route),
    }


def calculate_bundle(state, rows, *, route):
    """Called only by Calculate Flexure. Neither chart nor report calls here."""
    from . import analysis_page as ap
    section = members.calculate_member(state, rows, check_name="Flexure", route=route)
    if section.get("error"):
        return {"section": section, "interface": {"interface_status": "NOT CALCULATED"}}
    prep, composite, _ = ap._beam_uls_final_composite_preparation(state)
    settings = ap._igird_interface_shear_settings_from_state(state)
    source = ap._igird_interface_source_dataframe(rows)
    frame, notes = ap._igird_interface_shear_dataframe(state, source, prep=prep,
        composite_state=composite, settings=settings, strength_route=route)
    width, basis = ap._igird_interface_bvi_mm(state, settings)
    lightweight, density_note = ap._igird_interface_density_basis(state)
    surface = ap.IGIRD_INTERFACE_SURFACE_PRESETS[settings["surface_key"]]
    from .igird_coupled_model import calculate as calculate_coupled_model
    coupled = (calculate_coupled_model(state,rows,route=route) if state.get('igird_cover38_legacy_inputs',False) else
        {'enabled':False,'status':'ARCHIVED LEGACY MODEL — DISABLED','accepted_phiTn_Nmm':None,'accepted_VT_factor':None})
    from .igird_station36 import calculate as calculate_station_review
    station_review=calculate_station_review(state,rows,route=route)
    from .igird_joint37 import calculate as calculate_joint_transfer
    joint_transfer=calculate_joint_transfer(state,rows,route=route,station=station_review)
    return {"section": section, "coupled_research":coupled, "station36_research":station_review, "joint37_research":joint_transfer, "interface": {
        "interface_shear_df": frame, "interface_shear_messages": list(notes),
        "interface_status": ap._igird_interface_overall_status(frame),
        "surface_key": surface.key, "surface_label": surface.label,
        "bvi_mm": width, "bvi_basis": basis, "lightweight_basis": lightweight,
        "density_basis_note": density_note,
        "result_version": ap._IGIRDER_INTERFACE_SHEAR_RESULT_VERSION}}


def decision(frame):
    """Separate unavailable resistance from actual exceedances; keep raw FAIL."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return {"status": "NOT CALCULATED", "exceeded": 0, "unavailable": 0,
                "review": 0, "ratio": float("nan")}
    cap = pd.to_numeric(frame.get("Capacity kN-m", pd.Series(index=frame.index, dtype=float)), errors="coerce")
    dc = pd.to_numeric(frame.get("Utilization value", pd.Series(index=frame.index, dtype=float)), errors="coerce")
    available = cap.map(lambda v: pd.notna(v) and math.isfinite(float(v)))
    statuses = frame.get("Status", pd.Series("REVIEW", index=frame.index)).astype(str)
    numerical = frame.get("Numerical status", statuses).astype(str)
    failed = statuses.isin(["FAIL", "NO EQUILIBRIUM"]) | numerical.isin(["FAIL", "NO EQUILIBRIUM"])
    status = "FAIL" if failed.any() else "PASS" if statuses.eq("PASS").all() else "REVIEW"
    ratios = dc[available & dc.notna()]
    return {"status": status, "exceeded": int((available & dc.gt(1 + 1e-9)).sum()),
        "unavailable": int((~available).sum()), "review": int((~statuses.isin(["PASS", "FAIL"])).sum()),
        "ratio": float(ratios.max()) if not ratios.empty else float("nan")}


def summary_row(name, bundle, *, state_label="CURRENT", length=None, separate_ends=False):
    section = bundle.get("section", {}) if bundle else {}
    frame = section.get("flexure_preview_df")
    assessed, ends = assessment_frames(frame, length=length, separate_ends=separate_ends) if length is not None else (frame, pd.DataFrame())
    check = decision(assessed)
    interface = bundle.get("interface", {}) if bundle else {}
    gate = str(interface.get("interface_status", "NOT CALCULATED"))
    if section.get("error"):
        overall = "INCOMPLETE"
    elif check["status"] == "FAIL" or gate == "FAIL":
        overall = "FAIL"
    elif check["status"] == "PASS" and gate == "PASS" and section.get("Be_strength_verified") and not (separate_ends and not ends.empty):
        overall = "PASS"
    else:
        overall = "REVIEW" if bundle else state_label
    return {"Girder": name, "Result state": state_label, "Overall": overall,
        "Section": check["status"], "Cut ends": "SEPARATE REVIEW" if separate_ends and not ends.empty else "INCLUDED",
        "Interface": gate, "Max available D/C": ratio_text(check["ratio"]),
        "Strength exceeded": check["exceeded"], "Resistance unavailable": check["unavailable"],
        "Rows requiring review": check["review"]}


def endpoint_reference_table(frame, *, length):
    """Audit stored transported actions, including rows without equilibrium."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    xs = pd.to_numeric(frame["Station x (m)"], errors="coerce")
    mask = xs.abs().le(1e-7) | xs.sub(length).abs().le(1e-7)
    records = []
    for _, row in frame.loc[mask].iterrows():
        raw = row.get("Original CSI M3 kN-m", row.get("Source Mux kN-m", float("nan")))
        target = row.get("Demand kN-m", float("nan"))
        raw, target = pd.to_numeric(pd.Series([raw, target]), errors="coerce")
        records.append({"x (m)": row["Station x (m)"],
            "Load case": row.get("Source OutputCase", row.get("Case", "—")),
            "Bound": row.get("Source ItemType", "—"), "Face": row.get("Source LocType", "—"),
            "CSI M3 (kN-m)": raw, "CSI P (kN)": row.get("Original CSI P kN", row.get("Source Nu kN")),
            "Reference shift ΔM (kN-m)": target - raw, "Design Mux (kN-m)": target,
            "Reference status": row.get("Reference status", "No CSI reference snapshot"),
            "Capacity status": row.get("Numerical status", row.get("Status")),
            "Source row": row.get("Source Excel row", "—")})
    return pd.DataFrame(records)


def _store(state, cache, name, bundle, hashes, *, design_member):
    from . import analysis_page as ap
    cache[name] = {"hashes": hashes, "bundle": bundle, "version": VERSION}
    # Existing Report / QA and Result Summary retain the stage-owned caches.
    collection = dict(state.get(members.CACHE_KEY, {}))
    entry = dict(collection.get(name, {}))
    entry["Flexure"] = {"input_hash": hashes["section"], "result": bundle["section"]}
    collection[name] = entry
    state[members.CACHE_KEY] = collection
    if name == design_member and not bundle["section"].get("error"):
        ap._beam_uls_store_manual_result(state, "Flexure — Final Composite",
            input_hash=hashes["section"], result={**bundle["section"], "runtime_only": True})
        ap._beam_uls_store_manual_result(state, ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME,
            input_hash=hashes["interface"], result={**bundle["interface"], "runtime_only": True})


def _current_bundle(state, cache, name, hashes, *, design_member):
    """Read only; a legacy section result alone cannot close the interface gate."""
    from . import analysis_page as ap
    entry = cache.get(name, {})
    if entry.get("version") == VERSION and entry.get("hashes") == hashes:
        return entry["bundle"]
    section = members.current_result(state.get(members.CACHE_KEY, {}), name, "Flexure", hashes["section"])
    if section is None and name == design_member:
        section = ap._beam_uls_current_cached_result(state, "Flexure — Final Composite", hashes["section"])
    if section is None:
        return None
    interface = None
    if name == design_member:
        interface = ap._beam_uls_current_cached_result(state, ap._IGIRDER_INTERFACE_SHEAR_CHECK_NAME, hashes["interface"])
    return {"section": section, "interface": interface or {"interface_status": "NOT CALCULATED"}}


def _focus(fig, focus, *, length):
    """Change only viewport; padding keeps end markers inside exported charts."""
    width = min(length / 2, max(2., length * .15))
    left, right = (0., width) if focus == "Left end" else (length - width, length) if focus == "Right end" else (0., length)
    pad = (right - left) * .012
    fig.update_xaxes(range=[left - pad, right + pad])
    fig.update_layout(meta={**dict(fig.layout.meta or {}), "flexure31_focus": focus})
    return fig


def _render_charts(state, rows, bundle, *, member, route, code_label, length, separate_ends=False):
    from . import analysis_page as ap, igird_maxmin_charts as mm
    frame = bundle["section"]["flexure_preview_df"]
    assessment, _ = assessment_frames(frame, length=length, separate_ends=separate_ends)
    control = controlling_result(assessment, "Flexure")
    cases = rows["Case Name"].astype(str).drop_duplicates().tolist()
    families, choices = mm.review_choices(rows, cases)
    options = [AUTO_CASE, *choices]
    key = "igird_flexure31_case"
    if state.get(key) not in options:
        state[key] = AUTO_CASE
    columns = st.columns([2.2, 1.2, 1.2])
    with columns[0]:
        choice = st.selectbox("Load case", options, key=key,
            format_func=lambda v: mm.choice_label(v, families))
    controlling_case = str((control["row"] or {}).get("Case", cases[0] if cases else ""))
    family = (mm.family_for_case(families, controlling_case) if choice == AUTO_CASE else
              next((f for f in families if f.option == choice), None))
    case = controlling_case if choice == AUTO_CASE else choice
    with columns[1]:
        bound = st.radio("CSI bound", ["Max", "Min", "Both"], horizontal=True,
            key="igird_flexure31_bound") if family else None
    with columns[2]:
        focus = st.selectbox("View range", ["Full member", "Left end", "Right end"], key="igird_flexure31_focus")
    view = st.radio("Result view", [DEMAND, UTILIZATION, SOURCE, INTERFACE], horizontal=True,
        key="igird_flexure31_view")
    if family:
        steps = ["Max", "Min"] if bound == "Both" else [bound]
        selected_cases = tuple(c for step in steps for c in family.groups[step])
        checked = mm.select_cases(frame, selected_cases)
        selected_rows = mm.select_cases(rows, selected_cases, column="Case Name")
    else:
        selected_rows = rows.loc[rows["Case Name"].astype(str).eq(case)].copy()
        checked = frame.loc[frame["Case"].astype(str).eq(case)].copy()
        steps, selected_cases = [], (case,)
    if view == INTERFACE:
        interface = bundle["interface"].get("interface_shear_df")
        selected = mm.select_cases(interface, selected_cases) if isinstance(interface, pd.DataFrame) else None
        if selected is None or selected.empty:
            st.info("Interface shear is not available for this selection. Use Calculate Flexure to run both checks.")
        else:
            fig = ap._igird_interface_figure(selected, code_label=code_label, member_length_m=length)
            members.titled_figure(fig, member)
            ap._render_beam_uls_browser_plotly_figure(_focus(fig, focus, length=length),
                interactive=True, key="flexure31_interface")
            st.caption("Interface stress envelope is for display. Acceptance uses every original check row; dowel anchorage and zone coverage remain required.")
    elif view == SOURCE:
        st.info("Original CSI M3 at the imported CSI origin. Design capacity is shown in Demand / capacity at the strength-section centroid. No endpoint moment is forced to zero.")
        source_groups = [(step, mm.select_cases(rows, family.groups[step], column="Case Name")) for step in steps] if family else [("Source", selected_rows)]
        for step, source in source_groups:
            if source.empty:
                st.warning(f"{step}: no source rows. No values are taken from the other bound.")
                continue
            fig = ap._polish_igird_uls_flexure_legend(ap._make_beam_uls_demand_figure(source,
                column="Mux", title=f"Original CSI M3 — {step}", y_label="CSI M3 (kN-m)",
                member_length_m=length, source_context_df=rows))
            for trace in fig.data:
                trace.name = str(trace.name).replace("Mux", "M3")
            members.titled_figure(fig, member)
            fig.update_layout(meta={**dict(fig.layout.meta or {}), "flexure31_reference": "ORIGINAL CSI"})
            ap._render_beam_uls_browser_plotly_figure(_focus(fig, focus, length=length),
                interactive=True, key="flexure31_source_" + step)
    else:
        st.caption("Design Mux and φMn use the same strength-section centroid. Transport includes axial-force eccentricity; CSI source M3 can be zero while design Mux is nonzero.")
        if family:
            figures = mm.make_bound_figures(state, {"rows": rows, "result": bundle["section"],
                "control_frame": assessment, "scope_label": "Span scope; cut ends separate" if separate_ends else "All LCs"},
                family=family, member=member, check_name="Flexure", code_label=code_label,
                view=mm.UTILIZATION_VIEW if view == UTILIZATION else mm.DEMAND_VIEW)
            for step in steps:
                fig = figures.get(step)
                if fig is None:
                    st.warning(f"{step}: no stored results for this source family.")
                    continue
                ap._render_beam_uls_browser_plotly_figure(_focus(fig, focus, length=length),
                    interactive=True, key="flexure31_design_" + step)
        elif view == DEMAND:
            fig = members.make_member_flexure_figure(state, selected_rows, checked,
                member=member, code_label=code_label, case_name=case, source_context_df=rows)
            if separate_ends:
                fig.data = tuple(t for t in fig.data if str(t.name) != "Governing flexure check")
            ap._render_beam_uls_browser_plotly_figure(_focus(fig, focus, length=length), interactive=True, key="flexure31_design")
        else:
            from .igird_vt_workspace import make_overview_figure
            fig = make_overview_figure(selected_rows, checked, check_name="Flexure", code_label=code_label,
                span_m=length)
            members.titled_figure(fig, member, case_name=case)
            ap._render_beam_uls_browser_plotly_figure(_focus(fig, focus, length=length), interactive=True, key="flexure31_utilization")
        if checked.empty:
            st.warning("No calculated stations for this selection.")
        else:
            unavailable = decision(checked)["unavailable"]
            if unavailable:
                st.warning(f"{unavailable} source row(s) have unavailable φMn. Grey × and shaded segments show missing resistance, not zero capacity. Review end/reference evidence below.")
                from .igird_flexure_gap_review import render_missing_capacity
                render_missing_capacity(checked)
        if separate_ends:
            st.caption("Curves retain original stored end values and gaps. The control marker and span summary exclude exact 0/L cut ends; those sections remain a separate review, not PASS.")
    return checked


def render_stored_scope_review(state):
    """Read-only scope disclosure for Result Summary / Report; never calculates."""
    from . import analysis_page as ap
    if state.get("section_preset_key") != "parametric_i_girder":
        return
    policy = (state.get("project_metadata", {}) or {}).get(POLICY_KEY, {})
    if policy.get("end_treatment") != "separate_review":
        return
    length = ap._beam_uls_span_length_from_state(state, is_building=False)
    if not zero_L_are_cut_ends(state, length=length):
        st.warning("Saved Flexure cut-end scope is not applicable: Loads 0/L do not coincide with physical cut ends. Whole-member checks remain in force.")
        return
    st.info("Flexure scope: physical cut ends 0/L are reported separately from span section assessment. End-region / anchorage acceptance remains REVIEW. The global dashboard retains original whole-member check statuses.")
    from .igird_uls_report import current_check_packages
    packages = current_check_packages(state, "Flexure")
    rows = []
    for name, package in packages.items():
        assessed, ends = assessment_frames(package["result"]["flexure_preview_df"], length=length, separate_ends=True)
        scope = decision(assessed)
        rows.append({"Girder": name, "Span section": scope["status"],
            "Span D/C": ratio_text(scope["ratio"]), "Cut-end rows reported separately": len(ends),
            "End-region acceptance": "REVIEW"})
    if rows:
        st.dataframe(result_table_for_display(pd.DataFrame(rows)), hide_index=True, use_container_width=True)


def render_workspace(active_rows, *, route, code_label):
    from . import analysis_page as ap, igird_dowel_joint as joint_ui
    from concrete_pmm_pro.analysis.igird_dowel_joint import config, MODE
    save_active(st.session_state)
    rows_by_member = members.member_inputs(st.session_state)
    design = st.session_state.get(ACTIVE_KEY)
    if not rows_by_member and not active_rows.empty:
        design = str(design or "Design girder")
        rows_by_member = {design: active_rows}
    if not rows_by_member:
        st.info("Import Final ULS girder loads in Loads before calculating Flexure.")
        return
    names = list(rows_by_member)
    length = ap._beam_uls_span_length_from_state(st.session_state, is_building=False)
    st.markdown("#### Final Composite Flexure")
    st.caption("One calculation runs section flexure and girder–deck interface shear. Review one girder and load case at a time; changes to the view do not run calculations.")
    st.caption("Composite reinforcement: transverse slab bars outside; longitudinal positions calculated inside. Full composite Vn / Tn / V–T resistance remains under structural validation; local model results do not constitute design acceptance.")
    if st.toggle("Edit composite / dowel inputs", key="igird_flexure31_edit_inputs", value=False):
        ap._igird_render_interface_shear_settings(st.session_state)
        # The current six-action review is included automatically. Archived
        # model choices and unknown interface-force entries are not required
        # in the primary physical-input workflow.
        from . import igird_station36 as station_review,igird_joint37 as joint_review
        metadata=dict(st.session_state.get("project_metadata") or {})
        metadata[station_review.KEY]={**station_review.settings(st.session_state),"enabled":True}
        metadata[joint_review.KEY]={**joint_review.settings(st.session_state),"enabled":True}
        st.session_state["project_metadata"]=metadata
        with st.expander("Advanced — legacy research tools",expanded=False):
            if st.toggle("Show legacy research inputs",value=False,key="igird_cover38_legacy_inputs"):
                from .igird_coupled_model import render_inputs
                render_inputs(st.session_state)
                st.caption("Archived idealization. Manual interface actions are not required for the current local six-action review; unknown values must remain blank.")
    else:
        settings = ap._igird_interface_shear_settings_from_state(st.session_state)
        zones = settings.get("dowel_zones", [])
        st.caption(f"Shared section and reinforcement model · {len(names)} girder(s) · {len(zones)} saved dowel zone(s). Edit composite / dowel inputs to review interface reinforcement and anchorage.")
    metadata = dict(st.session_state.get("project_metadata", {}) or {})
    policy = metadata.get(POLICY_KEY, {})
    scope_key = "igird_flexure31_end_scope"
    if scope_key not in st.session_state:
        st.session_state[scope_key] = SEPARATE if policy.get("end_treatment") == "separate_review" else WHOLE
    can_separate = zero_L_are_cut_ends(st.session_state, length=length)
    if not can_separate:
        st.session_state[scope_key] = WHOLE
        st.warning("Cut-end separation is unavailable: Loads 0/L do not coincide with physical cut ends. Bearing sections remain in the whole-member check.")
    command_cols = st.columns([2., 1.5, 1.15])
    with command_cols[0]:
        end_scope = st.selectbox("Section assessment", [WHOLE, SEPARATE], key=scope_key,
            index=[WHOLE, SEPARATE].index(st.session_state[scope_key]),
            disabled=not can_separate,
            help="Only exact physical Loads endpoints 0/L can be separated. All loads and calculated rows stay unchanged; anchorage/end-region review remains open and overall PASS is withheld.")
    separate_ends = end_scope == SEPARATE
    if separate_ends or policy:
        metadata[POLICY_KEY] = {"end_treatment": "separate_review" if separate_ends else "include",
            "basis": "Physical cut ends 0/L reported separately from sectional span flexure; no end-region strength certification or force correction."}
        st.session_state["project_metadata"] = metadata
    if separate_ends:
        st.info(f"Span D/C excludes only cut ends x=0 / {length:.3f} m. End-region / anchorage: SEPARATE REVIEW. Near-support stations remain included.")
    hashes = {n: fingerprints(st.session_state, rows, route=route) for n, rows in rows_by_member.items()}
    cache = dict(st.session_state.get(CACHE_KEY, {}))
    with command_cols[1]:
        scope = st.selectbox("Calculation scope", ["All imported girders", "Design member only"], key="igird_flexure31_scope")
    with command_cols[2]:
        st.caption("Section + interface")
        run = st.button("Calculate Flexure", type="primary", key="igird_flexure31_calculate", use_container_width=True)
    if run:
        targets = names if scope == "All imported girders" else [design] if design in names else []
        if not targets:
            st.warning("Select the design member in Loads.")
        for name in targets:
            with st.spinner("Calculating flexure + interface: " + name):
                bundle = calculate_bundle(st.session_state, rows_by_member[name], route=route)
            _store(st.session_state, cache, name, bundle, hashes[name], design_member=design)
        st.session_state[CACHE_KEY] = cache
        settings = ap._igird_interface_shear_settings_from_state(st.session_state)
        if design in targets and config(settings).get("mode") == MODE:
            joint_hash = hashes[design]["interface"]
            result = ap._igird_dowel_joint_review(st.session_state, settings, code_label=code_label)
            st.session_state[joint_ui.CACHE_KEY] = {"fingerprint": joint_ui.result_fingerprint(
                settings, fingerprint=joint_hash, state=st.session_state), "result": result}
        st.rerun()
    current = {n: _current_bundle(st.session_state, cache, n, hashes[n], design_member=design) for n in names}
    summaries = [summary_row(n, current[n], length=length, separate_ends=separate_ends, state_label="CURRENT" if current[n] else
        "STALE" if n in cache else "NOT CALCULATED") for n in names]
    summary = pd.DataFrame(summaries)
    compact = summary[["Girder", "Overall", "Section", "Cut ends", "Interface", "Max available D/C"]].rename(
        columns={"Max available D/C": "Max D/C"})
    st.dataframe(result_table_for_display(compact), hide_index=True, use_container_width=True)
    st.caption("All active load cases govern the selected section scope. Unavailable resistance and numerical exceedances are counted separately. Cut-end separation is a recorded scope choice; original solver statuses and overall end-region review remain.")
    key = "igird_flexure31_member"
    if st.session_state.get(key) not in names:
        st.session_state[key] = design if design in names else names[0]
    name = st.selectbox("Girder to review", names, key=key)
    bundle = current[name]
    if bundle is None:
        st.info("No current results for this girder. Use Calculate Flexure; stale results are not drawn.")
        return
    section = bundle["section"]
    if section.get("error"):
        st.error(section["error"])
        return
    frame = section.get("flexure_preview_df")
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        st.warning("No calculated flexure rows. Check the section and active Loads.")
        return
    status = next(row for row in summaries if row["Girder"] == name)
    ap._render_analysis_summary_strip([
        {"title": "Final Composite", "value": status["Overall"], "detail": "Section + interface + current source/detailing gates", "status": "danger" if status["Overall"] == "FAIL" else "ready" if status["Overall"] == "PASS" else "warning", "strong": True},
        {"title": "Span section" if separate_ends else "Section flexure", "value": status["Section"], "detail": f"{status['Strength exceeded']} strength exceeded · {status['Resistance unavailable']} resistance unavailable" + (" · cut ends: SEPARATE REVIEW" if separate_ends else ""), "status": "danger" if status["Section"] == "FAIL" else "warning"},
        {"title": "Available section D/C", "value": status["Max available D/C"], "detail": "Unavailable φMn is excluded from this numerical ratio, but remains a blocking gate", "status": "info"},
        {"title": "Interface shear", "value": status["Interface"], "detail": "AASHTO 5.7.4 · included in Calculate Flexure", "status": "danger" if status["Interface"] == "FAIL" else "ready" if status["Interface"] == "PASS" else "warning"}], columns=4)
    checked = _render_charts(st.session_state, rows_by_member[name], bundle, member=name,
        route=route, code_label=code_label, length=length, separate_ends=separate_ends)
    with st.expander("Issues / end-region review — all load cases", expanded=False):
        from .igird_flexure_development import render_failure_summary
        render_failure_summary(frame, stage="Final Composite · " + name)
        st.caption("End cut failures are not waived by a small moment or by a pin/roller label. Verify the actual bearing station, force origin and end-region load transfer. No blanket exclusion or endpoint zeroing is applied.")
    with st.expander("End moments — CSI source / design reference", expanded=False):
        supports = st.session_state.get("igird_shear_support_settings", {}) or {}
        if supports.get("locations_confirmed"):
            left, right = float(supports.get("left_offset_m", 0)), length - float(supports.get("right_offset_m", 0))
            st.caption(f"Saved support reference ({supports.get('offset_reference', 'unspecified')}): x={left:.3f}, {right:.3f} m. Physical Loads ends: x=0, {length:.3f} m. This view does not relocate supports or loads.")
        st.dataframe(result_table_for_display(endpoint_reference_table(frame, length=length)), hide_index=True, use_container_width=True)
        st.caption("M_O = M_C + (C − O) × F. Design Mux may contain P × vertical eccentricity even if original CSI M3 = 0. Source P uses the CSI sign. A nonzero original M3 still requires checking CSI restraints, section location and force transfer.")
    from .igird_flexure_development import render_trace
    render_trace(checked, stage="Final Composite · " + name)
    with st.expander("Stored section / interface rows and calculation notes", expanded=False):
        st.dataframe(result_table_for_display(summary), hide_index=True, use_container_width=True)
        st.dataframe(result_table_for_display(frame), hide_index=True, use_container_width=True)
        interface = bundle["interface"].get("interface_shear_df")
        if isinstance(interface, pd.DataFrame):
            st.dataframe(result_table_for_display(interface), hide_index=True, use_container_width=True)
        for message in [*section.get("flexure_preview_messages", []), *bundle["interface"].get("interface_shear_messages", [])]:
            st.caption(str(message))
    if name == design:
        settings = ap._igird_interface_shear_settings_from_state(st.session_state)
        if config(settings).get("mode") == MODE:
            with st.expander("Optional U-dowel joint review — design member", expanded=False):
                joint_ui.render_analysis(settings, fingerprint=hashes[name]["interface"],
                    calculate=None, render_cards=ap._render_analysis_summary_strip,
                    state=st.session_state, allow_calculate=False)
    from .igird_coupled_model import render_result as render_coupled_result
    with st.expander("Advanced — archived composite model results",expanded=False):
        render_coupled_result(st.session_state,rows_by_member[name],bundle.get("coupled_research"),route=route)
    from .igird_station36 import render_result as render_station_result
    render_station_result(st.session_state,rows_by_member[name],bundle.get("station36_research"),route=route,joint_review=bundle.get("joint37_research"))
    from .igird_joint37 import render_result as render_joint_transfer
    render_joint_transfer(st.session_state,rows_by_member[name],bundle.get("joint37_research"),route=route,station=bundle.get("station36_research"))
    st.caption("Session results only. Project JSON saves inputs; calculate after loading. Result Summary / Report use the design member selected in Loads: " + str(design) + ".")
