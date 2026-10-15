"""Explicit Analysis controls and read-only runtime review for U-dowel joints."""
from __future__ import annotations
import hashlib
import json
import math
import pandas as pd
import streamlit as st
from concrete_pmm_pro.analysis.igird_dowel_joint import (
    ACTION_COLUMNS, DIMENSIONS, KEY, MODE, SCOPE, VERSION, config, number,
)

CACHE_KEY="igird_joint29_mechanism_review"
UI_VERSION="IGIRDER.INPUT30"


def _editor(frame, *, prefix, **kwargs):
    signature=hashlib.sha256(frame.to_json(orient="records").encode()).hexdigest()[:12]
    edited=st.data_editor(frame,key=prefix+signature,hide_index=True,use_container_width=True,**kwargs)
    return json.loads(edited.to_json(orient="records",double_precision=15))


def render_settings(current, *, section_params, state=None):
    from .igird_composite_inputs import effective_config, input_plan, positive
    from concrete_pmm_pro.visualization.igird_dowel_detail import (
        DIMENSION_GUIDE, dimension_label, u_dowel_detail_svg,
    )
    original=config(current)
    if original.get("mode")!=MODE:
        with st.expander("Additional U-dowel assessment",expanded=False):
            selected=st.selectbox("U-dowel joint assessment",["off",MODE],index=0,
                format_func=lambda v:"Not assessed" if v=="off" else "Cracked interface — equilibrium screening")
        if selected=="off":
            return {KEY:{**original,"mode":"off"}} if original else {}
    cfg=effective_config(current,section_params)
    cfg["mode"]=MODE
    missing=sum(not positive(cfg.get(k)) for k in DIMENSIONS)
    with st.expander(f"Dowel detail — {missing} missing dimensions" if missing else "Dowel detail — saved dimensions",expanded=False):
        st.caption("Section dimensions, concrete strengths, slab reinforcement, bar sizes, fy and spacings are reused. "
            "Enter only the measured dowel dimensions below; saved values do not need re-entry.")
        figure=st.empty()
        st.caption("Match A–F in the drawing to the inputs below. Not entered means unknown. "
            "A is across the girder, not the longitudinal dowel spacing. All dimensions are in mm.")
        dims=[{"Dimension":dimension_label(k),"Value mm":cfg.get(k)} for k in DIMENSIONS]
        frame=pd.DataFrame(dims)
        frame["Value mm"]=pd.to_numeric(frame["Value mm"],errors="coerce")
        edited=_editor(frame,prefix="input30_dimensions_",disabled=["Dimension"],num_rows="fixed",
            column_config={"Dimension":st.column_config.TextColumn("Dimension A–F",width="large"),
                "Value mm":st.column_config.NumberColumn("Value (mm)",min_value=0.,
                    help="Provided dimensions from the detail, matched to A–F above. E is required clear cover. Unknown values stay blank.")})
        for key,record in zip(DIMENSIONS,edited):
            value=number(record.get("Value mm"));cfg[key]=value if math.isfinite(value) and value>0 else None
        # Render after reading the editor, into its earlier placeholder: labels
        # show the current edit on this rerun, without a calculation or refresh.
        # st.html uses an HTML-only sanitizer which removes SVG. This drawing
        # contains fixed SVG markup and numeric labels only; flatten linebreaks
        # so Markdown cannot interpret parts of the drawing as separate blocks.
        figure.markdown(u_dowel_detail_svg(cfg,section_params=section_params).replace("\n",""),
            unsafe_allow_html=True)
        with st.expander("How to measure A–F",expanded=False):
            st.dataframe(pd.DataFrame([{"Ref":ref,"Dimension":label,"Measure from / to":meaning}
                for _,ref,label,meaning in DIMENSION_GUIDE]),hide_index=True,use_container_width=True)
        cols=st.columns(2)
        for col,key,label,values in [
            (cols[0],"coating","Dowel surface",["unknown","uncoated","epoxy"]),
            (cols[1],"anchorage_region","Anchorage region",["unknown","interior","discontinuous_end"])]:
            old=cfg.get(key,"unknown")
            with col:cfg[key]=st.selectbox(label,values,index=values.index(old) if old in values else 0)
        st.caption("Cover starts from the existing slab cover and remains editable. Use the dimensions in the actual dowel detail. "
            "The schematic does not establish geometric fit or anchorage; required development lengths remain in the calculation review.")
    with st.expander("Joint forces / advanced",expanded=False):
        selected=st.selectbox("Joint assessment model",["off",MODE],index=int(cfg.get("mode")==MODE),
            format_func=lambda v:"Not assessed" if v=="off" else "Cracked interface — equilibrium screening")
        cfg["mode"]=selected
        raw=cfg.get("action_rows",[])
        st.caption(f"{len(raw) if isinstance(raw,list) else 0} joint force states saved. "
            "Existing Loads stay in Loads. Beam/Slab source tables from the same uploader are retained as inputs; "
            "this release does not yet recover interface reactions from them.")
        if st.toggle("Edit joint forces manually",value=False,key="input30_edit_joint_forces"):
            st.caption("Use a simultaneous free-body / FE interface state per row. qx/qy: longitudinal/transverse shear; "
                "n>0: opening; mx: roll about interface centre. Girder Tu is not interface mx. Unknown forces stay blank.")
            frame=pd.DataFrame(raw if isinstance(raw,list) else [],columns=ACTION_COLUMNS)
            for col in ACTION_COLUMNS[1:6]:frame[col]=pd.to_numeric(frame[col],errors="coerce")
            cfg["action_rows"]=_editor(frame,prefix="joint29_actions_",num_rows="dynamic",
                column_config={"Case":st.column_config.TextColumn("Joint action state"),
                    "Station x (m)":st.column_config.NumberColumn("Station x (m)"),
                    "qx_kN_per_m":st.column_config.NumberColumn("qx (kN/m)"),
                    "qy_kN_per_m":st.column_config.NumberColumn("qy (kN/m)"),
                    "n_kN_per_m":st.column_config.NumberColumn("Opening n (kN/m)"),
                    "mx_kNm_per_m":st.column_config.NumberColumn("Roll mx (kN-m/m)"),
                    "Source":st.column_config.TextColumn("Free-body / interface force source")})
        st.caption("The 90° hook is assessed as tension-tie anchorage. The I-girder closed torsion hoop remains a separate reinforcement path.")
    plan=input_plan({**current,KEY:cfg},params=section_params,state=state)
    if plan["missing"]:
        groups=list(dict.fromkeys(row["Where"] for row in plan["missing"]))
        st.caption("Still needed: "+" · ".join(groups)+". See Inputs reused / still missing for the exact fields.")
    with st.expander("Inputs reused / still missing",expanded=False):
        st.dataframe(pd.DataFrame(plan["reused"]),hide_index=True,use_container_width=True)
        if plan["missing"]:
            st.markdown("**Still needed — enter once**")
            st.dataframe(pd.DataFrame(plan["missing"]),hide_index=True,use_container_width=True)
        if plan["pending"]:
            st.markdown("**Calculation steps still in development**")
            st.caption("These are app development steps, not additional forces the normal workflow asks you to enter.")
            st.dataframe(pd.DataFrame(plan["pending"]),hide_index=True,use_container_width=True)
        if plan["components"]:
            st.markdown("**Saved CSiBridge component inputs**")
            st.dataframe(pd.DataFrame(plan["components"]),hide_index=True,use_container_width=True)
            st.caption("Available source tables are not recovered interface forces or accepted composite resistance.")
    return {KEY:cfg}


def result_fingerprint(settings, *, fingerprint, state=None):
    from concrete_pmm_pro.io import csi_component_sources
    source_hash=csi_component_sources.fingerprint(csi_component_sources.saved(state or {}))
    return hashlib.sha256((UI_VERSION+VERSION+str(fingerprint)+source_hash+json.dumps(config(settings),sort_keys=True,default=str)).encode()).hexdigest()


def render_analysis(settings, *, fingerprint, calculate, render_cards=None, state=None, allow_calculate=True):
    if config(settings).get("mode")!=MODE:return
    st.markdown("##### U-dowel joint — opening, roll and interface shear")
    st.warning(SCOPE)
    st.caption("Enter the dowel detail once; use Calculate to review anchorage and any saved joint force states. "
        "A complete form or feasible joint mechanism does not establish Girder Tn or composite V–T resistance.")
    expected=result_fingerprint(settings, fingerprint=fingerprint, state=state)
    if allow_calculate and st.button("Calculate U-dowel Joint",key="calculate_joint29",type="primary"):
        result=calculate()
        st.session_state[CACHE_KEY]={"fingerprint":expected,"result":result}
    saved=st.session_state.get(CACHE_KEY,{})
    if saved.get("fingerprint")!=expected:
        st.info("U-dowel joint is not calculated for the current inputs. " +
            ("Press Calculate U-dowel Joint." if allow_calculate else "Use the main Calculate Flexure command."));return
    result=saved["result"]
    rows=result["rows"]
    finite=[r for r in rows if math.isfinite(number(r.get("Mechanism D/C")))]
    governing=max(finite,key=lambda r:number(r["Mechanism D/C"])) if finite else None
    anchorage_bad=any(r.get("Anchorage")=="FAIL" for r in rows)
    anchorage_ready=bool(rows) and all(r.get("Anchorage")=="DIMENSION CHECKS MET" for r in rows)
    if callable(render_cards):
        render_cards([
            {"title":"Composite design scope","value":"REVIEW","detail":"Joint mechanism screening; no composite V–T acceptance","status":"warning","strong":True},
            {"title":"Governing mechanism D/C","value":f"{governing['Mechanism D/C']:.3f}" if governing else "INPUTS REQUIRED",
             "detail":f"{governing['Case']} @ x={governing['Station x (m)']:.3f} m" if governing else "Supply joint actions and measured anchorage / zoning",
             "status":"danger" if governing and governing['Mechanism D/C']>1 else "info"},
            {"title":"Anchorage dimensions","value":"INSUFFICIENT" if anchorage_bad else ("DIMENSIONS MET" if anchorage_ready else "REVIEW"),
             "detail":"Length, tail, bend and geometric-fit checks; splitting/confinement remains separate",
             "status":"danger" if anchorage_bad else "warning"},
        ],columns=3)
    if result["requirements"]:
        with st.expander("Required development lengths / detail checks",expanded=False):
            st.dataframe(pd.DataFrame(result["requirements"]),hide_index=True,use_container_width=True)
    if result["missing_actions"]:
        st.info("REVIEW — no interface action states supplied. Girder Tu has not been substituted. Enter the measured anchorage dimensions and independent dowel ranges to complete the inputs.")
    if result["rows"]:
        frame=pd.DataFrame(result["rows"])
        st.dataframe(frame,hide_index=True,use_container_width=True)
        st.download_button("Download U-dowel joint review CSV",frame.to_csv(index=False).encode("utf-8-sig"),
            file_name="igird_joint29_mechanism_review.csv",mime="text/csv",key="joint29_csv")
    with st.expander("Calculation trace / Equations — U-dowel joint",expanded=False):
        st.latex(r"\sum_i T_i-\sum_j C_j=\lambda n,\qquad \sum_i y_iT_i-\sum_j y_jC_j=\lambda m_x")
        st.latex(r"\sum_j S_j=\lambda\sqrt{q_x^2+q_y^2},\qquad 0\le S_j\le\mu C_j,\qquad\sum_j S_j\le\mu\sum_iT_i")
        st.caption("T: tie tension; C: compression contact; S: friction; y: transverse offset from interface centre. "
            "Each is integrated over a 1-m longitudinal strip. Displayed forces in the detailed witness correspond to the radial limit lambda, not automatically to lambda=1. "
            "Tie cap=0.90 Avf fy/2 per row (fy≤60 ksi); contact cap=0.70×0.85fc; interface concrete caps=0.90 min(K1fc,K2). "
            "Assumed static admissibility does not establish slip/opening compatibility or local slab/anchorage-zone strength.")
        st.latex(r"\ell_{dh}=\max\left[8d_b,152.4,38d_b\frac{f_y/6.894757}{60\sqrt{f'_{c,s}/6.894757}}\lambda_{cw}\right]\ {\rm mm}")
        st.latex(r"\ell_d=\max\left[304.8,2.4d_b\frac{f_y/6.894757}{\sqrt{f'_{c,g}/6.894757}}\lambda_{cf}\right]\ {\rm mm}")
        st.caption("fy/fc in MPa; db in mm. AASHTO 2020 5.10.8.2.4a / 5.10.8.2.1a. No confinement or excess-steel reductions. "
            "Uncoated factors=1; epoxy hook=1.2 and conservative vertical straight-bar factor=1.5. "
            "This route excludes lightweight concrete, fc>10 ksi, fy>75 ksi, discontinuous-end hook confinement and bundled bars. "
            "For direct transverse torsion reinforcement, 5.10.8.2.6d requires full continuity and 135° standard hooks around longitudinal reinforcement.")
        st.json(result)
