"""Explain stored missing capacity; never fill, suppress or recompute it."""
import math
import pandas as pd


def missing_capacity_table(frame):
    if frame is None or frame.empty: return pd.DataFrame()
    def number(v):
        try: return float(v)
        except (ValueError,TypeError): return float("nan")
    rows=[]
    for _,r in frame.iterrows():
        if math.isfinite(number(r.get("Capacity kN-m"))): continue
        strands=r.get("Strand development trace",[])
        bars=r.get("Ordinary bar development trace",[])
        strands=strands if isinstance(strands,list) else []
        bars=bars if isinstance(bars,list) else []
        zero_strands=bool(strands) and all(number(s.get("fpx_limit_MPa"))==0. for s in strands)
        zero_bars=bool(bars) and all(number(b.get("factor"))==0. for b in bars)
        axial=number(r.get("Nu AASHTO tension-positive kN",r.get("Original CSI P kN")))
        status=str(r.get("Numerical status",r.get("Status","REVIEW")))
        if status=="NO EQUILIBRIUM" and zero_strands and zero_bars and axial>0:
            reason="Axial tension is present, while every strand and ordinary bar has zero developed tensile credit at this cut. No axial-flexural equilibrium exists in the current sectional model."
            action="Verify the actual cut/bearing station and anchored bars/strand development. Review the end-region force path; do not copy an interior φMn to the cut."
        else:
            reason=str(r.get("Notes") or status)
            action="Review the stored force-reference, material and development trace for this source row."
        raw=number(r.get("Original CSI M3 kN-m",r.get("Source Mux kN-m")))
        demand=number(r.get("Demand kN-m"))
        rows.append({"x (m)":r.get("Station x (m)"),"Load case":r.get("Source OutputCase",r.get("Case")),
            "Bound":r.get("Source ItemType",""),"CSI M3 (kN-m)":raw,"CSI P (kN)":r.get("Original CSI P kN"),
            "Shift ΔM (kN-m)":demand-raw,"Design Mux (kN-m)":demand,"Capacity status":status,
            "All strand credit zero":zero_strands,"All ordinary bar credit zero":zero_bars,
            "Reason":reason,"Required action":action})
    return pd.DataFrame(rows)


def render_missing_capacity(frame):
    import streamlit as st
    table=missing_capacity_table(frame)
    if table.empty: return
    st.info("The red capacity curve stops where the stored section has no available φMn. Blue demand remains complete. This is a calculation/source condition, not a drawing defect.")
    developed=table[table["All strand credit zero"] & table["All ordinary bar credit zero"] & table["Capacity status"].eq("NO EQUILIBRIUM")]
    if not developed.empty:
        r=developed.iloc[0]
        def fmt(v,precision=4):
            try: return f"{float(v):+.{precision}f}" if math.isfinite(float(v)) else "—"
            except (TypeError,ValueError): return "—"
        st.caption(f"At x={fmt(r['x (m)'],3)} m, {r['Load case']} {r['Bound']}: CSI M3={fmt(r['CSI M3 (kN-m)'])} kN-m, "
            f"CSI P={fmt(r['CSI P (kN)'])} kN, design Mux={fmt(r['Design Mux (kN-m)'])} kN-m. "
            "All strand and ordinary-bar development credits are zero. Check the actual bearing/cut location and anchored end reinforcement.")
    with st.expander("Why φMn is missing — source / development / equilibrium",expanded=True):
        first=["x (m)","Load case","Bound","Capacity status","Reason","Required action"]
        st.dataframe(table[first+[c for c in table if c not in first]],hide_index=True,use_container_width=True)
