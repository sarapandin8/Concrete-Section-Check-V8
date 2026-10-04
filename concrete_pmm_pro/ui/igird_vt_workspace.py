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
    st.caption("Section basis: precast I-girder for V/T geometry. Deck strength is credited in Final-Composite flexure separately.")
    if ap._beam_uls_shear_depth_settings_from_state(state).get("dv_mm") is None:
        st.caption("Auto shear depth: dv=0.72h under 5.7.2.8, conservatively. A verified force-weighted de/dv may be entered in Sections → Rebar.")
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
    if check_name == "Shear":
        frame = ap._beam_uls_shear_design_rows_for_governing(frame)
        components = {"Strength": "Strength D/C value", "Detailing": "Detailing D/C value"}
    elif check_name == "Torsion":
        components = {"Transverse": "D/C value", "Detailing": "Detailing D/C value"}
        if investigation:
            frame = frame.copy()
            demand = pd.to_numeric(frame.get("Abs demand kN-m"), errors="coerce")
            threshold = pd.to_numeric(frame.get("Threshold kN-m"), errors="coerce")
            frame["Investigation ratio"] = demand / threshold.where(threshold > 0)
            components = {"Investigation": "Investigation ratio"}
    else:
        components = {"Veff limit": "Stress D/C value", "Transverse": "Transverse D/C value",
            "Longitudinal": "Longitudinal D/C value", "Spacing": "Spacing D/C"}
    envelope = utilization_envelope(frame, components)
    subtitle = "investigation threshold — not torsion strength" if investigation else "maximum available D/C from original case/check pairs"
    fig = ap._make_beam_uls_demand_figure(active_df, column="Tu" if check_name == "Torsion" else "Vuy",
        title=f"{check_name} — {'investigation' if investigation else 'utilization'}<br><sup>{code_label} · {subtitle}</sup>",
        y_label="Investigation ratio" if investigation else "Demand / capacity, D/C")
    fig.data = ()
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


def render_strength_chart(active_df, frame, *, check_name, code_label, state, boundary=None, critical=None):
    import streamlit as st
    from concrete_pmm_pro.ui import analysis_page as ap
    if frame is None or frame.empty:
        st.info("Calculate this check to display its stored results.")
        return
    span = ap._beam_uls_span_length_from_state(state, is_building=False)
    view = st.radio("Chart view", ["Overview — utilization", "Selected case — demand / capacity"],
        horizontal=True, key=f"igird_vt_{check_name}_chart_view")
    investigation = check_name == "Torsion" and not pd.to_numeric(frame.get("φTn kN-m"),errors="coerce").notna().any()
    if view == "Overview — utilization":
        fig = make_overview_figure(active_df,frame,check_name=check_name,code_label=code_label,span_m=span,investigation=investigation)
        st.caption("Blue: maximum original D/C at each station. Red: limit 1.0. Strength and demand always come from the same case. Connecting lines are visual interpolation.")
        if any(math.isinf(_v) for _v in utilization_envelope(frame,
                {"D/C": "D/C value"} if check_name == "Torsion" else {"Strength": "Strength D/C value", "Detailing": "Detailing D/C value"}).get("D/C", [])):
            st.caption("An infinite ratio is labelled ∞ and drawn at the top of the chart; it has no finite plotted magnitude.")
        if investigation:
            st.caption("φTn is unavailable. This view shows |Tu|/(0.25φTcr); a ratio above 1 means torsion design is required, not that a φTn strength check has failed.")
    else:
        cases = frame["Case"].dropna().drop_duplicates().tolist()
        gov = ap._beam_uls_governing_shear_row(frame) if check_name == "Shear" else ap._beam_uls_governing_torsion_row(frame)
        default = cases.index(gov["Case"]) if gov and gov.get("Case") in cases else 0
        case = st.selectbox("Case for diagram", cases, index=default, key=f"igird_vt_{check_name}_diagram_case")
        demands = active_df.loc[active_df["Case Name"].eq(case)]
        checked = frame.loc[frame["Case"].eq(case)]
        def pick(source):
            return source.loc[source["Case"].eq(case)] if source is not None and not source.empty else None
        if check_name == "Shear":
            fig = ap._make_beam_uls_shear_capacity_figure(demands,checked,code_label=code_label,
                boundary_capacity_df=pick(boundary),critical_section_df=pick(critical),compact_csi_legend=True)
            fig.data = tuple(t for t in fig.data if t.name not in {"φVc","Critical x"})
        else:
            fig = ap._make_beam_uls_torsion_capacity_figure(demands,checked,code_label=code_label,boundary_capacity_df=pick(boundary))
            have_tn = pd.to_numeric(checked.get("φTn kN-m"),errors="coerce").notna().any()
            hide = {"±φTcr","±0.25φTcr"} if have_tn else {"±φTcr"}
            fig.data = tuple(t for t in fig.data if t.name not in hide)
        for trace in fig.data:
            if str(trace.name).startswith("Gov."):
                trace.showlegend = False
        fig.update_xaxes(range=[0.0,span])
        st.caption(str(case) + ". Blue: original signed demand. Red: ±φVn or ±φTn for this case; the negative branch mirrors the resistance magnitude. Purple, if shown: investigation threshold.")
    ap._render_beam_uls_browser_plotly_figure(fig,interactive=True)
    st.caption("Incomplete input checks remain REVIEW. CSI Max/Min rows are numerical screening; final coupled acceptance needs verified concurrent actions.")


def render_combined_chart(frame, *, code_label):
    import streamlit as st
    from concrete_pmm_pro.ui import analysis_page as ap
    # Stored rows supply the domain context; no importer or solver runs.
    active = pd.DataFrame({"Case Name":frame["Case"],"Station x (m)":frame["Governing x"].astype(str).str.replace(" m","",regex=False).astype(float),
        "Vuy":pd.to_numeric(frame.get("Vu kN"),errors="coerce")})
    span = ap._beam_uls_span_length_from_state(st.session_state,is_building=False)
    ap._render_beam_uls_browser_plotly_figure(make_overview_figure(active,frame,check_name="Shear + Torsion",
        code_label=code_label,span_m=span),interactive=True)
    partial = int(frame.get("Calculation status",pd.Series(index=frame.index,dtype=object)).eq("PARTIAL").sum())
    st.caption(f"Blue: largest available original Veff/transverse/longitudinal/spacing D/C at each station. Red: limit 1.0. Partial rows: {partial}. Missing sub-checks are not a completed overall check.")
    if frame[[c for c in ["Stress D/C value", "Transverse D/C value", "Longitudinal D/C value", "Spacing D/C"] if c in frame]].apply(lambda c: pd.to_numeric(c, errors="coerce").map(math.isinf)).any().any():
        st.caption("An infinite ratio is labelled ∞ and drawn at the top of the chart; it has no finite plotted magnitude.")
    with st.expander("Combined components / individual cases",expanded=False):
        ap._render_beam_uls_browser_plotly_figure(ap._make_beam_uls_combined_vt_utilization_figure(frame,code_label=code_label),interactive=True)
