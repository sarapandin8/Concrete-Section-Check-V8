"""Stored-result V/T overview and one place to complete missing inputs.

The overview ranks each original case's D/C. It never pairs an envelope of
Vu/Tu with an unrelated envelope of resistance. No solver is called here.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
import pandas as pd
import plotly.graph_objects as go


def missing_bar_materials(state: Mapping) -> list[str]:
    def get(item, key):
        return item.get(key) if isinstance(item, Mapping) else getattr(item, key, None)
    known = {str(get(m, "name")) for m in state.get("rebar_materials", []) or []}
    return sorted({str(get(b, "material_name")) for b in state.get("rebars", []) or []} - known)


def render_support_geometry(state, *, span_m):
    import streamlit as st
    from concrete_pmm_pro.analysis.igird_shear_support import SETTINGS_KEY, support_settings, support_basis
    settings = support_settings(state)
    with st.expander("Bearing locations / shear section basis", expanded=False):
        st.caption("Offsets are measured from each physical beam end. Bearing length is along the beam; 0 means unknown. These inputs do not change the strand cut ends or imported loads.")
        confirmed = st.checkbox("Bearing locations are defined", value=settings["locations_confirmed"],
            key="igird_support_widget_confirmed")
        labels = {"Bearing centerline": "centerline", "Internal bearing face": "inside_face"}
        reference = st.selectbox("Bearing offset reference", list(labels),
            index=0 if settings["offset_reference"] != "inside_face" else 1,
            key="igird_support_widget_reference")
        values = {}
        for col, side in zip(st.columns(2), ("left", "right")):
            with col:
                values[f"{side}_offset_m"] = st.number_input(f"{side.title()} bearing offset from beam end (m)",
                    min_value=0.0, value=float(settings[f"{side}_offset_m"] or 0.0), step=0.05,
                    key=f"igird_support_widget_{side}_offset")
                values[f"{side}_bearing_length_mm"] = st.number_input(f"{side.title()} bearing length along beam (mm; 0 = unknown)",
                    min_value=0.0, value=float(settings[f"{side}_bearing_length_mm"] or 0.0), step=50.0,
                    key=f"igird_support_widget_{side}_length")
        note = st.text_input("Bearing drawing / coordinate reference", value=settings["note"], key="igird_support_widget_note")
        values.update({"locations_confirmed": confirmed, "offset_reference": labels[reference], "note": note})
        state[SETTINGS_KEY] = values
        state["project_metadata"] = {**(state.get("project_metadata") or {}), SETTINGS_KEY: values}
        st.markdown("The composite compression section uses the lower deck/girder f'c conservatively. Final-Composite acceptance requires confirmed effective width and a current Interface Shear PASS. "
            "AASHTO 5.7.3.2 locates an eligible critical section dv from the internal support face. This release retains every original force row, including end overhangs; reaction compression, concentrated loads and end-region detailing are not inferred.")
    basis = support_basis(state, span_m=span_m)
    if basis["supports"]:
        coords = []
        for support in basis["supports"]:
            cl, face = support["centerline_x_m"], support["inside_face_x_m"]
            coords.append(f'{support["side"]}: CL ' + (f'x={cl:.3f} m' if cl is not None else 'unknown') +
                ', inside face ' + (f'x={face:.3f} m' if face is not None else 'unknown'))
        st.caption("Bearings — " + "; ".join(coords) + ". Physical beam/strand ends remain x=0/L.")
    if basis["status"] == "INVALID":
        st.warning(basis["note"])
    elif basis["status"] != "FACES KNOWN":
        st.caption(basis["note"] + " No face+dv marker is assigned until the faces are known.")


def render_input_checks(state, *, check_name: str) -> None:
    import streamlit as st
    from concrete_pmm_pro.core.models import RebarMaterial
    from concrete_pmm_pro.analysis.igird_combined_vt import development_settings, ordinary_development_factor
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.ui.igird_combined_vt import render_development_inputs
    missing = missing_bar_materials(state)
    dev = development_settings(state)
    span = ap._beam_uls_span_length_from_state(state, is_building=False)
    development_ready = not state.get("rebars") or ordinary_development_factor(dev, x_m=span/2, span_m=span) is not None
    composite = bool((state.get("section_parameters") or {}).get("composite_enabled"))
    st.caption("Final-Composite: deck concrete participates in the flexural C/T resultants and shear depth. Web width and web concrete strength remain the precast girder properties."
        if composite else "Section basis: precast I-girder; composite deck action is disabled.")
    st.caption("Auto dv=max(C/T lever arm, 0.9de, 0.72h), with station strand/bar development. Torsion Ao/ph and the closed hoop remain the qualified precast section.")
    if composite:
        from concrete_pmm_pro.ui import igird_shear_section
        route = ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
        gate, gate_notes = igird_shear_section.composite_action_gate(state,strength_route=route)
        if gate != "PASS":
            st.info("Final-Composite action: " + gate + ". " + " ".join(gate_notes) +
                " Calculate Interface Shear in Flexure → Final — Composite, then recalculate this check.")
    render_support_geometry(state, span_m=span)
    with st.expander('ULS Final scope / completion checklist',expanded=False):
        params = state.get('section_parameters') or {}
        st.dataframe(pd.DataFrame([
            ['Concurrent vectors','Envelope retains REVIEW; declared Static/step or Correspondence vectors accepted with recorded basis','Loads → multi-file import'],
            ['Composite action','Effective width and current Interface Shear PASS required','Sections + Flexure → Final Composite'],
            ['Deck longitudinal reinforcement','Top/bottom grade, diameter, spacing, cover and independent cutoff/development feed Final ULS','Sections → Composite Deck Longitudinal Reinforcement'],
            ['Composite torsion','Resistance uses the physical girder closed hoop. Deck torsional force-flow and slab checks are not certified','Separate slab/connection design'],
            ['Bearing / D-region','Physical coordinates and region audit only; bearing/nodal/STM design requires reaction and end details','Bearing editor + separate end-region design'],
            ['Below minimum reinforcement','Confirmed ag and verified sx enable numerical Eq.-2 audit; minimum detailing can still FAIL','Sections → General shear crack spacing'],
            ['Other checks','Biaxial, fatigue, slab transverse design and hook/lap execution remain separate; sectional PASS is not complete bridge approval','Project design / drawing review'],
        ],columns=['Check','Acceptance / scope','Input or action']),use_container_width=True,hide_index=True)

    if missing:
        st.warning("Longitudinal material missing: " + ", ".join(missing) + ". Define its verified properties below; choosing a hoop does not define the longitudinal steel material.")
        with st.expander("Complete missing longitudinal materials", expanded=True):
            for name in missing:
                cols = st.columns([2.5, 1.0])
                with cols[0]:
                    fy = st.number_input(f"Verified fy for {name} (MPa)", min_value=0.0, max_value=1000.0,
                        value=0.0, step=10.0, key=f"igird_vt_define_{name}_fy",
                        help="Enter the specified yield strength from the actual steel material. No fy is inferred from the grade name.")
                    es = st.number_input(f"Es for {name} (MPa)", min_value=1.0, value=200000.0,
                        step=1000.0, key=f"igird_vt_define_{name}_es")
                with cols[1]:
                    if st.button(f"Define {name}", key=f"igird_vt_define_{name}", disabled=fy <= 0.0):
                        state["rebar_materials"] = [*list(state.get("rebar_materials") or []),
                            RebarMaterial(name=name, fy_MPa=float(fy), Es_MPa=float(es))]
                        st.rerun()
    if state.get("rebars"):
        render_development_inputs(expanded=not development_ready)
    if check_name == "Shear + Torsion":
        st.caption("Calculate Shear + Torsion also refreshes Shear and Torsion. Completed sub-checks remain visible when another input is missing.")


def utilization_envelope(frame: pd.DataFrame, components: Mapping[str, str]) -> pd.DataFrame:
    """Maximum of original row ratios; retain source identity and missingness."""
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = frame.copy(deep=True)
    data["__x"] = pd.to_numeric(data["Governing x"].astype(str).str.replace(" m", "", regex=False), errors="coerce")
    output = []
    for x, group in data.loc[data["__x"].notna()].groupby("__x", sort=True):
        candidates, missing_rows = [], 0
        for _, row in group.iterrows():
            row_values = []
            for label, column in components.items():
                try:
                    v = float(row.get(column))
                except (TypeError, ValueError):
                    continue
                if not math.isnan(v) and v >= 0:
                    row_values.append((v, label))
            if row_values:
                v, label = max(row_values)
                candidates.append((v, label, str(row.get("Case") or "-"), str(row.get("Status") or "-")))
            else:
                missing_rows += 1
        if candidates:
            v, label, case, status = max(candidates)
        else:
            v, label, case, status = float("nan"), "Source required", "-", "REVIEW"
        output.append({"x_m": float(x), "D/C": v, "Component": label, "Case": case,
            "Status": status, "Missing rows": missing_rows, "Check rows": len(group)})
    return pd.DataFrame(output)


def make_overview_figure(active_df, frame, *, check_name, code_label, span_m, investigation=False):
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.ui.igird_case_review import eligible_rows, component_values
    frame = eligible_rows(frame, check_name)
    if check_name == "Torsion" and investigation:
        demand = pd.to_numeric(frame.get("Abs demand kN-m"), errors="coerce")
        threshold = pd.to_numeric(frame.get("Threshold kN-m"), errors="coerce")
        frame["Investigation ratio"] = demand / threshold.where(threshold > 0)
        components = {"Investigation": "Investigation ratio"}
    else:
        components = {}
        for index, (label, values) in enumerate(component_values(frame, check_name)):
            column = f"__review_component_{index}"
            frame[column] = values
            components[label] = column
    envelope = utilization_envelope(frame, components)
    subtitle = "investigation threshold — not torsion strength" if investigation else "maximum available D/C from original case/check pairs"
    title = f"{check_name} — {'investigation' if investigation else 'utilization'}<br><sup>{code_label} · {subtitle}</sup>"
    fig = ap._make_beam_uls_demand_figure(active_df, column="Tu" if check_name == "Torsion" else "Vuy",
        title=title,
        y_label="Investigation ratio" if investigation else "Demand / capacity, D/C")
    fig.data = ()
    # The demand template note refers to a single demand case; an overview
    # displays checked case/component ratios instead.
    fig.update_layout(title_text=title, annotations=[])
    if not envelope.empty:
        finite = [v for v in envelope["D/C"] if math.isfinite(v)]
        ceiling = max([1.0, *finite])*1.16
        ys = [ceiling if math.isinf(v) else v for v in envelope["D/C"]]
        customs = [[r["Case"],r["Component"],"∞" if math.isinf(r["D/C"]) else f"{r['D/C']:.3f}",
            r["Status"],r["Missing rows"]] for _,r in envelope.iterrows()]
        fig.add_trace(go.Scatter(x=envelope["x_m"].tolist(),y=ys,mode="lines+markers",
            name="Investigation" if investigation else "Max D/C",connectgaps=False,
            line={"color":"#1f77b4","width":2.6},marker={"size":5},customdata=customs,
            hovertemplate="x=%{x:.3f} m<br>Ratio=%{customdata[2]}<br>%{customdata[1]} · %{customdata[3]}<br>%{customdata[0]}<br>Rows without a numeric check: %{customdata[4]}<extra></extra>"))
        known = envelope.loc[envelope["D/C"].notna()]
        if not known.empty:
            gov = known.loc[known["D/C"].idxmax()]
            y = ceiling if math.isinf(gov["D/C"]) else gov["D/C"]
            label = "∞" if math.isinf(gov["D/C"]) else f"{gov['D/C']:.3f}"
            fig.add_trace(go.Scatter(x=[gov["x_m"]],y=[y],mode="markers+text",showlegend=False,
                name="Governing",text=[f"Gov. {label}"],textposition="top left" if gov["x_m"] > .7*span_m else "top right",
                marker={"size":10,"symbol":"diamond","color":"#0f172a"},
                customdata=[[gov["Case"],gov["Component"]]],
                hovertemplate="x=%{x:.3f} m<br>%{customdata[1]}<br>%{customdata[0]}<extra></extra>"))
        fig.update_yaxes(range=[0,ceiling*1.08])
    fig.add_trace(go.Scatter(x=[0.0,span_m],y=[1.0,1.0],mode="lines",name="Limit = 1.0",
        line=dict(ap._BEAM_ULS_CHECK_LINE_STYLE),hovertemplate="Limit = 1.0<extra></extra>"))
    fig.update_xaxes(range=[0.0,span_m])
    return fig


def render_strength_chart(active_df, frame, *, check_name, code_label, state, boundary=None, critical=None, diagram=None, key_prefix="", member_name="", selected_case=None, source_context_df=None):
    import streamlit as st
    from concrete_pmm_pro.ui import analysis_page as ap
    if frame is None or frame.empty:
        st.info("Calculate this check to display its stored results.")
        return
    span = ap._beam_uls_span_length_from_state(state, is_building=False)
    view = st.radio("Chart view", ["Overview — utilization", "Selected case — demand / capacity"],
        horizontal=True, key=f"{key_prefix}igird_vt_{check_name}_chart_view")
    from concrete_pmm_pro.ui.igird_case_review import controlling_result
    investigation = check_name == "Torsion" and controlling_result(frame,check_name)['basis'] == 'INVESTIGATION ONLY'
    if view == "Overview — utilization":
        fig = make_overview_figure(active_df,frame,check_name=check_name,code_label=code_label,span_m=span,investigation=investigation)
        st.caption("Blue: maximum original D/C at each station. Red: limit 1.0. Strength and demand always come from the same case. Connecting lines are visual interpolation.")
        if any(trace.name == 'Max D/C' and any(row[2] == '∞' for row in trace.customdata)
                for trace in fig.data):
            st.caption("An infinite ratio is labelled ∞ and drawn at the top of the chart; it has no finite plotted magnitude.")
        if investigation:
            st.caption("φTn is unavailable. This view shows |Tu|/(0.25φTcr); a ratio above 1 means torsion design is required, not that a φTn strength check has failed.")
    else:
        cases = frame["Case"].dropna().drop_duplicates().tolist()
        gov = ap._beam_uls_governing_shear_row(frame) if check_name == "Shear" else ap._beam_uls_governing_torsion_row(frame)
        default = cases.index(gov["Case"]) if gov and gov.get("Case") in cases else 0
        case = selected_case if selected_case in cases else st.selectbox("Case for diagram", cases, index=default, key=f"{key_prefix}igird_vt_{check_name}_diagram_case")
        demands = active_df.loc[active_df["Case Name"].eq(case)]
        checked = frame.loc[frame["Case"].eq(case)]
        def pick(source):
            return source.loc[source["Case"].eq(case)] if source is not None and not source.empty else None
        selected_diagram = pick(diagram)
        if check_name == "Shear":
            fig = ap._make_beam_uls_shear_capacity_figure(demands,checked,code_label=code_label,
                boundary_capacity_df=pick(boundary),critical_section_df=pick(critical),compact_csi_legend=True,
                member_length_m=span,source_context_df=source_context_df if source_context_df is not None else active_df,diagram_capacity_df=selected_diagram)
            fig.data = tuple(t for t in fig.data if t.name not in {"φVc","Critical x"})
        else:
            fig = ap._make_beam_uls_torsion_capacity_figure(demands,checked,code_label=code_label,
                boundary_capacity_df=pick(boundary),diagram_capacity_df=selected_diagram,
                member_length_m=span,source_context_df=source_context_df if source_context_df is not None else active_df)
            capacity_source = selected_diagram if selected_diagram is not None and not selected_diagram.empty else checked
            have_tn = pd.to_numeric(capacity_source.get("φTn kN-m"),errors="coerce").notna().any()
            hide = {"±φTcr","±0.25φTcr"} if have_tn else {"±φTcr"}
            fig.data = tuple(t for t in fig.data if t.name not in hide)
        for trace in fig.data:
            if str(trace.name).startswith("Gov."):
                trace.showlegend = False
        fig.update_xaxes(range=[0.0,span])
        st.caption(str(case) + ". Blue: original signed demand. Red: ±φVn or ±φTn for this case; the negative branch mirrors the resistance magnitude. Purple, if shown: investigation threshold.")
        shared = (fig.layout.meta or {}).get("shared_csi_endpoints", [])
        if shared:
            st.caption("Shared physical endpoints at x=0/L use the unique original Excel row from the same girder, case and Max/Min family. They are diagram points only; hover shows the originating row. Stored import and design checks are unchanged.")
        if check_name == "Torsion" and diagram is not None and not diagram.empty:
            st.caption("φTn is also evaluated for the diagram where Tu is below 0.25φTcr or zero, using the actual station actions and qualified reinforcement. The original threshold/design decisions are unchanged; no end resistance is copied from an interior station.")
            with st.expander("Torsion diagram capacity — station / source / θ trace",expanded=False):
                columns = [column for column in ("Governing x","Case","Demand kN-m","φTn kN-m",
                    "Threshold status","Source decision status","Diagram evaluation status","εs raw","θ deg",
                    "Ao mm2","At/s mm2/mm","fy MPa","φ","Diagram source case","Diagram source sheet",
                    "Diagram source row","Diagram source type","Notes") if column in selected_diagram]
                st.dataframe(selected_diagram[columns],hide_index=True,use_container_width=True)
        if check_name == "Shear" and diagram is not None and not diagram.empty:
            st.caption("φVn at shared physical endpoints uses their actual Excel forces. Zero-force synthetic boundary capacities are not used in this case diagram. The original support/critical-section design decisions are unchanged.")
        missing = (fig.layout.meta or {}).get("unavailable_capacity", [])
        if missing:
            st.caption("Grey × at the chart foot marks unavailable resistance, not zero capacity. Hover for the missing station source.")
            with st.expander("Missing capacity at plotted stations",expanded=False):
                st.dataframe(pd.DataFrame([{"x (m)":row["x_m"],"Quantity":row["quantity"],
                    "Case": "; ".join(row["cases"]),"Reason":row["reason"]} for row in missing]),
                    hide_index=True,use_container_width=True)
    if member_name:
        from concrete_pmm_pro.ui.igird_member_results import titled_figure
        fig = titled_figure(fig, member_name,case_name=selected_case)
    ap._render_beam_uls_browser_plotly_figure(fig,interactive=True)
    st.caption("Incomplete input checks remain REVIEW. CSI Max/Min rows are numerical screening; final coupled acceptance needs verified concurrent actions.")


def render_combined_chart(frame, *, code_label, member_name="", selected_case=None):
    import streamlit as st
    from concrete_pmm_pro.ui import analysis_page as ap
    # Stored rows supply the domain context; no importer or solver runs.
    active = pd.DataFrame({"Case Name":frame["Case"],"Station x (m)":frame["Governing x"].astype(str).str.replace(" m","",regex=False).astype(float),
        "Vuy":pd.to_numeric(frame.get("Vu kN"),errors="coerce")})
    span = ap._beam_uls_span_length_from_state(st.session_state,is_building=False)
    fig = make_overview_figure(active,frame,check_name="Shear + Torsion",code_label=code_label,span_m=span)
    if member_name:
        from concrete_pmm_pro.ui.igird_member_results import titled_figure
        fig = titled_figure(fig,member_name,case_name=selected_case)
    ap._render_beam_uls_browser_plotly_figure(fig,interactive=True)
    partial = int(frame.get("Calculation status",pd.Series(index=frame.index,dtype=object)).eq("PARTIAL").sum())
    st.caption(f"Blue: largest available original Veff/transverse/longitudinal/spacing D/C at each station. Red: limit 1.0. Partial rows: {partial}. Missing sub-checks are not a completed overall check.")
    if any(trace.name == 'Max D/C' and any(row[2] == '∞' for row in trace.customdata) for trace in fig.data):
        st.caption("An infinite ratio is labelled ∞ and drawn at the top of the chart; it has no finite plotted magnitude.")
    with st.expander("Combined components / individual cases",expanded=False):
        components = ap._make_beam_uls_combined_vt_utilization_figure(frame,code_label=code_label,member_length_m=span)
        if member_name:
            components = titled_figure(components,member_name,case_name=selected_case)
        ap._render_beam_uls_browser_plotly_figure(components,interactive=True)
        st.caption("The x-axis covers the physical span. Component D/C values are plotted only at evaluated design stations; support boundaries and unavailable source terms are not assigned a numeric D/C.")
