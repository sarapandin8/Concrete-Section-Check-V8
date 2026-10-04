"""Inputs and stored calculation trace for AASHTO developed I-Girder flexure."""
from __future__ import annotations

import pandas as pd
import streamlit as st
import math

from concrete_pmm_pro.analysis.igird_flexure_development import SETTINGS_KEY, development_settings

WIDGET_PREFIX = "igird_flexdep_"


def render_failure_summary(frame: pd.DataFrame | None, *, stage: str) -> None:
    """Read stored station failures; no solve or demand alteration on reruns."""
    if frame is None or frame.empty or "Numerical status" not in frame:
        return
    failures = frame[frame["Numerical status"].isin(["FAIL", "NO EQUILIBRIUM"])].copy()
    if failures.empty:
        return
    descriptions = []
    for _,row in failures.head(5).iterrows():
        x = float(row["Station x (m)"])
        nu = float(row["Nu kN"])
        raw = float(row["Nu input kN"])
        capacity = float(row.get("φMn kN-m", float("nan")))
        demand = float(row["Demand kN-m"])
        detail = (f"φMn={capacity:,.3f} < |Mu|={abs(demand):,.3f} kN-m" if math.isfinite(capacity)
            else "NO EQUILIBRIUM; φMn unavailable")
        strand = row.get("Strand development trace") or []
        bars = row.get("Ordinary bar development trace") or []
        if strand and all(float(t.get("fpx_limit_MPa",-1))==0 for t in strand) and all(float(t.get("factor",-1))==0 for t in bars):
            detail += "; no developed strand / ordinary-bar force at this cut end"
        descriptions.append(f"x={x:.3f} m: Nu input={raw:+.3f} kN → solver Nu={nu:+.3f} kN ({row.get('Nu action','—')}); {detail}.")
    st.error(f"{stage}: {len(failures)} failing section station(s) under the entered development / anchorage assumptions.\n\n" + "\n\n".join(descriptions))
    st.caption("Physical cut-end force transfer requires the real FEA force reference and end anchorage / D-region detailing. A beam-theory section result alone does not certify the end region; failed endpoints remain visible.")


def render_inputs() -> None:
    current = development_settings(st.session_state)
    st.caption("AASHTO LRFD 9th (2020): available φMn includes strand transfer/development and ordinary-bar end development. Nu remains included.")
    with st.expander("Flexure development / physical beam ends — AASHTO 5.9.4.3", expanded=False):
        st.caption("Station x is the Loads coordinate. Enter measured distances from its 0/L endpoints to the cut ends if the Loads axis starts/ends at bearings. Zero credits no extension. Sleeve lengths are measured from the cut ends.")
        cols = st.columns(2)
        with cols[0]:
            left = st.number_input("Cut end before x=0 (m)", min_value=0.0,
                value=current["left_extension_m"], step=0.05, key=WIDGET_PREFIX + "left_extension_m")
        with cols[1]:
            right = st.number_input("Cut end beyond x=L (m)", min_value=0.0,
                value=current["right_extension_m"], step=0.05, key=WIDGET_PREFIX + "right_extension_m")
        labels = {"unknown": "Unclassified service tension — conservative κ=2.0",
            "tension": "Service tension exists — required κ=2.0",
            "no_tension_confirmed": "No service tension in precompressed tensile zone — engineer confirmed"}
        modes = list(labels)
        condition = st.selectbox("Debonded-strand service condition (5.9.4.3.3F)", modes,
            index=modes.index(current["debonded_service_condition"]), format_func=labels.get,
            key=WIDGET_PREFIX + "service_condition")
        st.caption("The no-tension declaration allows the bonded-strand depth branch κ=1.6 (>609.6 mm) or 1.0 (≤609.6 mm). Pretensioned debonded strands are not external/unbonded post-tensioned tendons.")
        continuous = st.checkbox("Ordinary longitudinal bars: full-span continuity / cutoff lengths verified from drawing",
            value=current["bars_continuous_confirmed"], key=WIDGET_PREFIX + "bar_continuity")
        cols = st.columns(2)
        with cols[0]:
            left_anchor = st.checkbox("Left end: full ordinary-bar strength has verified anchorage",
                value=current["left_bar_anchored"], key=WIDGET_PREFIX + "left_bar_anchor")
        with cols[1]:
            right_anchor = st.checkbox("Right end: full ordinary-bar strength has verified anchorage",
                value=current["right_bar_anchored"], key=WIDGET_PREFIX + "right_bar_anchor")
        ld = st.number_input("Verified governing straight-bar ld (mm); 0 = conservative automatic ld",
            min_value=0.0, value=current["bar_ld_mm"], step=50.0, key=WIDGET_PREFIX + "bar_ld_mm",
            help="AASHTO 5.10.8.2.1: automatic normal-weight ld uses location/coating product 1.7, no confinement/excess reduction, and ≥304.8 mm. Enter a verified length covering every active girder/deck bar layer for other material/geometry scopes.")
        note = st.text_input("Development / anchorage calculation and drawing reference",
            value=current["note"], key=WIDGET_PREFIX + "note")
        settings = {"left_extension_m": left, "right_extension_m": right,
            "debonded_service_condition": condition, "bars_continuous_confirmed": continuous,
            "left_bar_anchored": left_anchor, "right_bar_anchored": right_anchor,
            "bar_ld_mm": ld, "note": note}
        st.session_state[SETTINGS_KEY] = settings
        metadata = dict(st.session_state.get("project_metadata") or {})
        metadata[SETTINGS_KEY] = settings
        st.session_state["project_metadata"] = metadata
        st.caption("Automatic ordinary-bar scope: normal-weight f'c≤10 ksi, fy≤75 ksi and bars≤No.11. No partial straight-bar credit below 12 in; hooked/mechanical anchorage requires confirmation. The single Longitudinal Rebar table remains the steel source.")
    if not continuous:
        st.warning("Ordinary-bar layout is treated as full-span straight bars for the numerical curve. Confirm actual continuity/cutoffs and anchorage before a flexure PASS; current numerical PASS rows remain REVIEW.")
    materials = st.session_state.get("rebar_materials", []) or []
    names = {m.get("name") if isinstance(m, dict) else m.name for m in materials}
    rebars = st.session_state.get("rebars", []) or []
    missing = sorted({(b.get("material_name") if isinstance(b, dict) else b.material_name) or "(unnamed)"
        for b in rebars if (b.get("material_name") if isinstance(b, dict) else b.material_name) not in names})
    if missing:
        st.warning("Ordinary-bar material definition missing: " + ", ".join(missing) +
            ". The numerical curve uses the existing solver fallback; fy/Es is shown in Calculation trace. Define matching materials in Materials before a flexure PASS.")


def render_trace(frame: pd.DataFrame | None, *, stage: str) -> None:
    with st.expander(f"Calculation trace / Equations — {stage} flexure", expanded=False):
        st.markdown("**AASHTO LRFD 9th Edition (2020), 5.9.4.3.1–3 and 5.5.4.2.** The displayed values come from the stored Calculate result.")
        st.latex(r"l_t=60d_b,\qquad l_d=\kappa\left(f_{ps}-\frac{2}{3}f_{pe}\right)d_b\quad\text{(ksi, in.)}")
        st.latex(r"l_d\ [\mathrm{mm}]=\kappa\,\frac{f_{ps}-\frac{2}{3}f_{pe}}{6.894757293}\,d_b\ [\mathrm{mm}]\quad\text{(stresses in MPa)}")
        st.latex(r"f_{px}=\begin{cases}0 & l_{px}=0\ \text{or sleeve}\\ f_{pe}l_{px}/l_t & 0<l_{px}<l_t\\ f_{pe}+\dfrac{l_{px}-l_t}{l_d-l_t}(f_{ps}-f_{pe}) & l_t\le l_{px}<l_d\\ f_{ps} & l_{px}\ge l_d\end{cases}")
        st.latex(r"f_{ps,used}=\min(f_{ps,compatible},f_{px}),\quad T_{ps}=\sum A_{ps}f_{ps,used}")
        st.latex(r"\phi\left(C_c+\sum F_s-\sum T_{ps}\right)=N_u,\quad M_r=\phi M_n")
        st.caption("Compression-positive signed Fs includes displaced-concrete subtraction. Moments use the gross strength-section centroid shown below; map FEA Nu/Mux to this same reference. Effective initial prestress is reduced through lt and applied once inside strand strain; it is not added again as external Nu.")
        st.latex(r"\phi=0.75+0.25\,\frac{\varepsilon_t-0.002}{0.005-0.002},\qquad 0.75\le\phi\le1.00\quad\text{(bonded PSC)}")
        st.caption("εt is net tensile strain excluding initial effective prestress. φ=1.00 applies to tension-controlled bonded PSC. Pretensioned sleeves do not make the whole member an unbonded post-tensioned member.")
        definitions = [
            ("db", "Nominal strand diameter", "mm"),
            ("lpx", "Shortest available bond distance to the left/right bond start; sleeve length and cut-end extensions included", "mm"),
            ("lt", "Transfer length to develop effective prestress fpe", "mm"),
            ("ld", "Bond length to develop reference fps at nominal resistance", "mm"),
            ("fpe", "Stage effective prestress Pe per strand / strand area", "MPa"),
            ("fps, reference", "Fully developed section strand stress at the same Nu/sign and current material law", "MPa"),
            ("fpx / fps used", "Code stress limit / actual stress used after the developed equilibrium solve", "MPa"),
            ("κ", "1.6 for precast depth>24 in; 1.0 for≤24 in; 2.0 for debonded service tension (also conservative unknown condition)", "—"),
            ("Nu", "Original external factored axial demand; positive compression", "kN"),
        ]
        st.dataframe(pd.DataFrame(definitions, columns=["Variable", "Meaning", "Unit"]), hide_index=True, use_container_width=True)
        if frame is None or frame.empty or "Strand development trace" not in frame:
            st.info("Calculate this stage to populate the stored equilibrium and strand-group audit.")
            return
        labels = [f"{r.get('Case', '-')} · x={r.get('Governing x', '-')}" for _, r in frame.iterrows()]
        util = pd.to_numeric(frame.get("Utilization value"), errors="coerce")
        default = int(util.argmax()) if util.notna().any() else 0
        position = st.selectbox("Stored station", list(range(len(frame))), index=default,
            format_func=lambda i: labels[i], key=WIDGET_PREFIX + "trace_" + stage.replace(" ", "_"))
        row = frame.iloc[position]
        st.caption("Source Muy/M2 and Source Vux/V3 are reference values. This flexure route checks signed primary-axis Mux/M3 with Nu.")
        st.caption("Nu input is the preserved Loads value. Nu kN is the compression-positive value used in equilibrium; CSI input uses Nu = −P. AASHTO tension-positive Nu is the opposite of solver Nu.")
        fields = ["Source sheet", "Source Excel row", "Source ItemType", "Source row set", "Source coupling", "Source Mux kN-m", "Source Vuy kN", "Source Tu kN-m", "Source Muy kN-m", "Source Vux kN", "Source Nu kN", "Nu input kN", "Nu input convention", "Nu conversion factor", "Nu action", "Nu kN", "Nu AASHTO tension-positive kN", "Mn nominal kN-m", "φ value", "φMn kN-m", "Neutral axis c mm",
            "Stress block a mm", "α1", "β1", "Net tensile strain", "Strain condition", "Cc kN",
            "Ordinary steel force kN", "Strand force kN", "φPn kN", "Force residual N",
            "Moment reference y mm", "Full-development reference φMn kN-m", "Development source status", "Minimum flexure gate"]
        st.dataframe(pd.DataFrame([{"Quantity": k, "Stored value": str(row.get(k, "—"))} for k in fields]),
            hide_index=True, use_container_width=True)
        st.caption(str(row.get("Notes", "")))
        trace = row.get("Strand development trace")
        if isinstance(trace, list):
            st.markdown("**Strand families — actual stress and force used**")
            st.dataframe(pd.DataFrame(trace), hide_index=True, use_container_width=True)
        bars = row.get("Ordinary bar development trace")
        if isinstance(bars, list) and bars:
            st.markdown("**Ordinary longitudinal bars — 5.10.8.2.1**")
            st.latex(r"l_{db}=2.4d_b\frac{f_y}{\sqrt{f'_c}}\quad\text{(ksi, in.)},\quad l_{d,auto}=\max(12\ \mathrm{in.},1.7l_{db})")
            st.caption("For straight-bar partial force, 5.10.8.2.1c permits excess-reinforcement reduction; the 12-in minimum is retained. Below 12 in, no ordinary steel strength is credited unless full end anchorage is confirmed. Automatic development uses precast f'c for girder bars and actual bar diameter/deck f'c for smeared deck layers.")
            st.dataframe(pd.DataFrame(bars), hide_index=True, use_container_width=True)
        st.caption("Available φMn includes the development limits. The full-development reference is an audit comparator and does not feed D/C. Debonding detailing, minimum flexural reinforcement, composite interface action, and biaxial demand remain their respective checks.")
