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
UI_VERSION="IGIRDER.DETAIL35"


def _editor(frame, *, prefix, **kwargs):
    from .igird_input_editor import input_editor
    edited=input_editor(frame,prefix=prefix,hide_index=True,use_container_width=True,**kwargs)
    return json.loads(edited.to_json(orient="records",double_precision=15))


def render_settings(current, *, section_params, state=None):
    from .igird_composite_inputs import effective_config, input_plan, positive
    from concrete_pmm_pro.visualization.igird_dowel_detail import (
        DIMENSION_GUIDE, dimension_label, u_dowel_detail_svg,
    )
    original=config(current)
    cfg=effective_config(current,section_params)
    # Geometry and slab mesh are normal composite inputs, independent of the
    # optional legacy joint-force screening model. No model selector is needed
    # before users can enter the reinforcement they know from their drawing.
    cfg["mode"]=original.get("mode","off")
    from concrete_pmm_pro.analysis.igird_dowel_detail35 import migrate, resolve, diameter_values, value, SCHEMA
    legacy = cfg.get("detail_schema") != SCHEMA
    cfg = migrate(cfg, section_params)
    input_names = {"row_spacing_mm":"A · U-leg centre spacing across girder",
        "hook_tail_mm":"C · Straight tail after 90° bend",
        "hook_top_depth_mm":"E · Top slab surface to OUTSIDE of hook",
        "girder_ld_available_mm":"F · Straight bonded leg below interface"}
    missing = sum(not positive(cfg.get(k)) for k in input_names)
    raw_zones = (state or {}).get("beam_girder_shear_reinforcement_table", [])
    zones = raw_zones.to_dict("records") if isinstance(raw_zones, pd.DataFrame) else raw_zones
    dbs = diameter_values(current, zones if isinstance(zones, list) else [])
    with st.expander(f"Dowel detail — {missing} missing dimensions" if missing else "Dowel detail — saved dimensions",
            expanded=False,key="igird_edit33_dowel_detail"):
        st.caption("Enter A, C, E and F once. B = slab thickness − E. D = 6.0db is the specified design bend, recalculated for each dowel zone. All dimensions are in mm.")
        if legacy:
            st.info("Earlier E meant required clear cover. Its value is preserved under Cover requirements below; the hook depth is derived only from the saved B. Earlier provided D is retained in legacy input history. The new default design bend is 6.0db.")
        figure = st.empty()
        frame = pd.DataFrame([{"Dimension":label, "Value mm":cfg.get(k)} for k,label in input_names.items()])
        frame["Value mm"] = pd.to_numeric(frame["Value mm"],errors="coerce")
        edited = _editor(frame, prefix="igird_detail35_dimensions_", disabled=["Dimension"], num_rows="fixed",
            column_config={"Dimension":st.column_config.TextColumn("Measured dimension",width="large"),
                "Value mm":st.column_config.NumberColumn("Value (mm)",min_value=0., help="E is measured from the slab top to the outside of the hook. Unknown values stay blank.")})
        for key,record in zip(input_names,edited):
            cfg[key] = value(record.get("Value mm"))
        with st.expander("Cover requirements / provided bend override", expanded=False):
            st.caption("Required minimum covers are separate from measured hook depth E. Girder cover is checked along the actual leg path, including the web.")
            keys = ("girder_clear_cover_required_mm", "slab_clear_cover_required_mm")
            cover_frame = pd.DataFrame({"Component":["Girder — side / bottom", "Slab — hook"], "Minimum clear cover mm":[cfg.get(k) for k in keys]})
            cover_frame["Minimum clear cover mm"] = pd.to_numeric(cover_frame["Minimum clear cover mm"],errors="coerce")
            covers = _editor(cover_frame, prefix="igird_detail35_covers_", disabled=["Component"], num_rows="fixed",
                column_config={"Minimum clear cover mm":st.column_config.NumberColumn("Minimum clear cover (mm)",min_value=0.)})
            for key,row in zip(keys,covers): cfg[key] = value(row.get("Minimum clear cover mm"))
            modes = ["auto_6db", "provided"]
            mode = cfg.get("bend_mode","auto_6db")
            cfg["bend_mode"] = st.selectbox("D — bend specification", modes, index=modes.index(mode) if mode in modes else 0,
                format_func=lambda v:"Automatic — 6.0db" if v=="auto_6db" else "Provided inside bend diameter", key="igird_detail35_bend_mode")
            if cfg["bend_mode"] == "provided":
                old = value(cfg.get("hook_inside_bend_mm"))
                cfg["hook_inside_bend_mm"] = st.number_input("Provided D (mm)",value=old,min_value=0.,key="igird_detail35_provided_D")
            values=["unknown","uncoated","epoxy"];old=cfg.get("coating","unknown")
            cfg["coating"]=st.selectbox("Known dowel surface (optional)",values,index=values.index(old) if old in values else 0,
                help="Use the material specification if known. Unknown stays unknown; the model cannot claim verified development from a guessed coating.")
            st.caption("Anchorage-region classification is a model check. Existing drawing evidence is retained; no manual interior/end selection is required in this input workflow.")
        cfg = resolve(cfg, slab_thickness_mm=section_params.get("Tslab_mm"), db_mm=dbs[0] if len(dbs)==1 else None)
        b = value(cfg.get("slab_ldh_available_mm"))
        st.caption(f"B = Tslab − E = {b:g} mm" if b is not None else "B = Tslab − E; enter the measured hook depth E.")
        if cfg.get("bend_mode") == "auto_6db":
            st.caption("D = 6.0db: " + (" · ".join(f"DB{d:g} → {6*d:g} mm" for d in dbs) if dbs else "dowel diameter is taken from the selected connector layout"))
            st.caption("The specified bend is still checked against the applicable code minimum. Automatic sizing does not verify fabrication, anchorage or a closed torsion cage.")
        from concrete_pmm_pro.visualization.igird_dowel_detail import detail_guide
        figure.markdown(u_dowel_detail_svg(cfg,section_params=section_params).replace("\n",""),unsafe_allow_html=True)
        with st.expander("How to measure A–F",expanded=False):
            st.dataframe(pd.DataFrame([{"Ref":ref,"Dimension":label,"Measure from / to":meaning}
                for _,ref,label,meaning in detail_guide(cfg)]),hide_index=True,use_container_width=True)
    from .igird_slab_mesh import render as render_mesh
    cfg = render_mesh(cfg, section_params, state=state)
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
            st.markdown("**Model availability / validation status**")
            st.caption("Research calculations and production acceptance have separate readiness requirements.")
            st.dataframe(pd.DataFrame(plan["pending"]),hide_index=True,use_container_width=True)
        if plan["components"]:
            st.markdown("**Saved CSiBridge component inputs**")
            st.dataframe(pd.DataFrame(plan["components"]),hide_index=True,use_container_width=True)
            st.caption("Available source tables are not recovered interface forces or accepted composite resistance.")
    # Merely viewing an empty optional detail must not create phantom inputs.
    physical=any(cfg.get(k) is not None for k in input_names)
    physical=physical or any(row.get(k) is not None for row in cfg.get('slab_transverse_mesh',{}).values()
        for k in ('Diameter_mm','Spacing_mm','Clear_cover_mm'))
    if not original and cfg.get('mode')=='off' and not physical:return {}
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
