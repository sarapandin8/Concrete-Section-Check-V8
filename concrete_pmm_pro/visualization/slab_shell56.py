"""One truthful deck-plan map: element maxima, no corner/case averaging."""
from __future__ import annotations

from html import escape
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import sample_colorscale

from concrete_pmm_pro.analysis.slab_shell56 import GROUPS
from concrete_pmm_pro.analysis.slab_code57 import FLEXURE_VIEW, MINIMUM_VIEW, REFERENCE_VIEWS
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability

VIEWS = ["Overall section", *GROUPS, "Concrete compression", "One-way shear", FLEXURE_VIEW, MINIMUM_VIEW]
ALL_CASES = "All imported ULS cases"
SAFE = "#176b9b"
LIMIT = "#f4c95d"
FAIL = "#c93535"
UNKNOWN = "#cbd2dc"


def view_column(view):
    if view in REFERENCE_VIEWS:
        return REFERENCE_VIEWS[view]
    if view == "Overall section":
        return "Field D/C"
    if view == "Concrete compression":
        return "Concrete D/C"
    if view == "One-way shear":
        return "Shear D/C"
    return view+" D/C"


def element_envelope(result, *, view="Overall section", case=ALL_CASES):
    rows = result["rows"]
    if case != ALL_CASES:
        rows = rows.loc[rows["OutputCase"] == case]
    if rows.empty:
        return pd.DataFrame()
    column = view_column(view)
    working = rows.copy(deep=False).assign(_dc=rows[column])
    step_cols = [c for c in ("OutputCase", "StepType", "StepNum") if c in rows]
    expected = len(rows[step_cols].drop_duplicates())*4
    sizes = rows.groupby("AreaElem").size()
    # Known failures outrank unresolved records; unresolved records outrank
    # apparently passing ones. A numeric maximum cannot hide a missing check.
    review = working[column].isna()
    if view == "Overall section":
        review |= working["Status"].eq("REVIEW")
    working = working.assign(_priority=np.where(working[column]>1+1e-8, 2, np.where(review, 1, 0)), _review=review)
    working = working.sort_values(["_priority", "_dc"], ascending=[False,False], na_position="last")
    selected = working.drop_duplicates("AreaElem").set_index("AreaElem")
    selected["Map incomplete"] = sizes.reindex(selected.index).lt(expected)
    selected["Map unresolved"] = selected["_review"] | selected["Map incomplete"]
    selected["Map D/C"] = selected[column]
    selected.loc[selected["Map unresolved"] & selected["Map D/C"].le(1+1e-8), "Map D/C"] = np.nan
    return selected


def _color_scale(maximum):
    # Logarithmic numerical mapping keeps both D/C=1 and large peaks legible.
    # The colorbar shows the actual D/C values; values are never clipped.
    top = math.log1p(max(1.05, maximum))
    limit = math.log(2)/top
    colors = [[0, SAFE], [max(0,limit*.65), "#68a9bb"],
        [limit, LIMIT], [min(1,limit+1e-8), FAIL], [1,"#7b1825"]]
    return top, colors


def plan_figure(result, *, view="Overall section", case=ALL_CASES):
    selected = element_envelope(result, view=view, case=case)
    elements = result["geometry"].elements
    if not elements:
        raise ValueError("No slab geometry to plot")
    finite = selected["Map D/C"].dropna() if not selected.empty else pd.Series(dtype=float)
    maximum = max(1.05,float(finite.max())) if len(finite) else 1.05
    top, colors = _color_scale(maximum)
    # Binned SVG fills have a bounded trace count even for thousands of mesh
    # elements. Hover points retain exact unrounded governing values.
    bins = {i: [] for i in range(32)}
    unavailable = []
    centres, hovers, values = [], [], []
    for elem, points in elements.items():
        row = selected.loc[elem] if elem in selected.index else None
        value = float(row["Map D/C"]) if row is not None else math.nan
        polygon = np.vstack((points[:,:2], points[0,:2], [[np.nan,np.nan]]))
        if math.isfinite(value):
            z = math.log1p(max(value,0))
            bucket = (min(15,int(z/math.log(2)*16)) if value<=1 else
                      16+min(15,int((z-math.log(2))/(top-math.log(2))*16)))
            bins[bucket].append(polygon)
        else:
            unavailable.append(polygon)
        if row is not None:
            centres.append(points[:,:2].mean(axis=0))
            detail = f"{escape(elem)} · {escape(str(row['OutputCase']))} / {escape(str(row['StepType']))}"
            detail += f"<br>Corner {escape(str(row['Joint']))}: X={row['X (m)']:.3f}, Y={row['Y (m)']:.3f} m"
            detail += f"<br>D/C = {row[view_column(view)]:.3f}" if pd.notna(row[view_column(view)]) else "<br>D/C unavailable: scope / source coverage requires review"
            if view in REFERENCE_VIEWS:
                detail += "<br>"+escape(str(row['Code reference reason']))
                detail += "<br>Independent reference; coupled field results retained"
            else:
                detail += "<br>Controlling field check: "+escape(str(row.get('Controlling check','')))
            if view in GROUPS:
                detail += f"<br>As required = {row[view+' As required (mm²/m)']:.1f} mm²/m"
            if row["Map incomplete"]:
                detail += "<br>Incomplete corner/case coverage"
            hovers.append(detail)
            values.append(value)
    fig = go.Figure()
    for index, polygons in bins.items():
        if not polygons:
            continue
        xy = np.concatenate(polygons)
        centre = ((index+.5)/16*math.log(2) if index<16 else
                  math.log(2)+(index-16+.5)/16*(top-math.log(2)))
        color = sample_colorscale(colors,[centre/top])[0]
        fig.add_trace(go.Scatter(x=xy[:,0],y=xy[:,1],mode="lines",fill="toself",fillcolor=color,
            line={"width":.2,"color":"rgba(255,255,255,.22)"},hoverinfo="skip",showlegend=False,
            name="Element envelope",connectgaps=False))
    if unavailable:
        xy = np.concatenate(unavailable)
        fig.add_trace(go.Scatter(x=xy[:,0],y=xy[:,1],mode="lines",fill="toself",fillcolor=UNKNOWN,
            line={"width":.2,"color":"#ffffff"},hoverinfo="skip",name="Review / missing",showlegend=False))
        fig.add_trace(go.Scatter(x=[None],y=[None],mode="markers",marker={"symbol":"square","size":11,"color":UNKNOWN},
            name="Review / missing",hoverinfo="skip"))
    if centres:
        centres = np.array(centres)
        fig.add_trace(go.Scatter(x=centres[:,0],y=centres[:,1],mode="markers",marker={"size":9,"opacity":0},
            text=hovers,hovertemplate="%{text}<extra></extra>",showlegend=False,name="Source details"))
    ticks = [v for v in (0,.5,1,2,5,10,20,50,100) if v<=maximum]
    if maximum>ticks[-1]*1.1:
        ticks.append(maximum)
    if len(finite):
        fig.add_trace(go.Scatter(x=[None,None],y=[None,None],mode="markers",showlegend=False,hoverinfo="skip",name="D/C scale",
            marker={"color":[0,top],"cmin":0,"cmax":top,"colorscale":colors,"showscale":True,
                "colorbar":{"title":{"text":"D/C"},"tickvals":np.log1p(ticks),
                    "ticktext":[f"{v:.2f}" if v==maximum else f"{v:g}" for v in ticks],"thickness":15,"len":.85}}))
    # Plot the true governing corner, not an averaged element centre.
    known = selected.loc[selected["Map D/C"].notna()] if not selected.empty else selected
    if not known.empty:
        governor = known.loc[known["Map D/C"].idxmax()]
        fig.add_trace(go.Scatter(x=[governor["X (m)"]],y=[governor["Y (m)"]],mode="markers",
            marker={"symbol":"diamond-open","size":13,"color":"#111827","line":{"width":2}},
            name=f"Gov. D/C {governor['Map D/C']:.3f}",cliponaxis=False,
            hovertemplate=f"Governing corner · D/C {governor['Map D/C']:.3f}<extra></extra>"))
    xy = np.concatenate([p[:,:2] for p in elements.values()])
    low, high = xy.min(axis=0), xy.max(axis=0)
    pad = np.maximum((high-low)*.035,.05)
    title = escape(view)+" · "+escape("all cases" if case==ALL_CASES else case)
    fig.update_layout(template="plotly_white",height=575,title={"text":title,"x":.5,"xanchor":"center"},
        margin={"l":66,"r":90,"t":58,"b":82},font={"family":"Arial, sans-serif","size":13},
        meta={"slab_version":"SLAB.REVIEW57","aggregation":"maximum source corner per element; no averaging"},
        legend={"orientation":"h","x":.5,"xanchor":"center","y":-.15,"yanchor":"top"},
        hovermode="closest",xaxis={"title":"Global X (m)","range":[low[0]-pad[0],high[0]+pad[0]],"constrain":"domain","showgrid":False,"zeroline":False},
        yaxis={"title":"Global Y (m)","range":[low[1]-pad[1],high[1]+pad[1]],"scaleanchor":"x","scaleratio":1,
            "constrain":"domain","showgrid":False,"zeroline":False},uirevision=f"SLAB56:{view}:{case}")
    return apply_global_plot_readability(fig)
