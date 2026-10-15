"""Shared analysis-only station adapter; no persisted solver cache."""
from __future__ import annotations
from dataclasses import replace
from functools import wraps
import inspect,math
from concrete_pmm_pro.analysis import igird_end_sections as ends
from concrete_pmm_pro.core.models import SectionGeometry
BASE_GEOMETRY="_igird_endsection_base_geometry"
LOCAL_X="_igird_endsection_local_x"
PROJECT_STATE="_igird_endsection_project_state"
TRACE_KEY="_igird_endsection_trace"
PROFILE_KEY="_igird_endsection_profile"
WEB_GEOMETRY="_igird_endsection_web_geometry"
TRACE_COLUMNS=["Section region","Solid fill fraction","Physical girder x (m)","Physical girder length (m)",
    "Section Acp mm2","Section Pcp mm","Section geometry version","End section acceptance","End section review","Section boundaries (m)"]

def at_station(state,x_m):
    if not ends.enabled(state): return state
    x=float(x_m)
    if state.get(LOCAL_X)==x: return state
    from concrete_pmm_pro.ui import analysis_page as ap,igird_shear_section as shear
    geometry=state.get(BASE_GEOMETRY,state.get("section_geometry"))
    if isinstance(geometry,dict): geometry=SectionGeometry.model_validate(geometry)
    if not isinstance(geometry,SectionGeometry): raise ValueError("Precast I-girder source geometry is unavailable.")
    definition=ends.profile(state,geometry,ap._beam_uls_span_length_from_state(state,is_building=False))
    local,trace=ends.section_at(geometry,definition,x)
    derived={**state,BASE_GEOMETRY:geometry,LOCAL_X:x,TRACE_KEY:trace,PROFILE_KEY:definition,
        PROJECT_STATE:state.get(PROJECT_STATE,state),WEB_GEOMETRY:local,"section_geometry":local}
    if "_igird_flexure_precast_depth_mm" in state:
        from concrete_pmm_pro.analysis.igird_composite_flexure import _composite_geometry
        params=state.get("section_parameters") or {}
        be=float(params.get("Be_effective_mm",params.get("Be_mm",0.0)))
        derived["section_geometry"]=_composite_geometry(local,be_mm=be,tslab_mm=float(params.get("Tslab_mm",0)))
    runtime=state.get(shear.RUNTIME_KEY)
    if isinstance(runtime,dict):
        key=(round(trace["Solid fill fraction"],12),tuple((p.x,p.y) for p in local.outer_polygon))
        parent=state.get("_igird_endsection_parent_runtime",runtime)
        cache=parent.setdefault("endsection_runtime",{}).setdefault(key,{})
        if "active_df" in parent: cache["active_df"]=parent["active_df"]
        derived[shear.RUNTIME_KEY]=cache
        derived["_igird_endsection_parent_runtime"]=parent
    return derived

def strand_families(state,table,*,y_min_mm,span_m,stage,settings):
    from concrete_pmm_pro.analysis.igird_flexure_development import strand_families as families
    if not ends.enabled(state): return families(table,y_min_mm=y_min_mm,span_m=span_m,stage=stage,settings=settings)
    left,right=ends.cut_ends(state.get("section_parameters") or {},span_m)
    return tuple(replace(f,left_bond_start_m=f.left_bond_start_m+left,right_bond_end_m=f.right_bond_end_m+left)
        for f in families(table,y_min_mm=y_min_mm,span_m=right-left,stage=stage,settings=settings))

def annotate(result,state,*,check_name):
    if TRACE_KEY not in state: return result
    result={**result,**state[TRACE_KEY]};cfg=state[PROFILE_KEY];reasons=[]
    if not cfg.load_reference_confirmed and result.get("Reference status") not in {"EXACT", "INTERVAL BOUND"}:
        reasons.append("Confirm imported Mux/Nu reference at the local section centroid; no automatic Nu×eccentricity conversion is applied.")
    if result["Solid fill fraction"]>0:
        if not cfg.d_region_confirmed:
            reasons.append("End block/taper sectional screening: bearing, prestress transfer, anchorage and D-region/strut-and-tie verification are required.")
        if check_name in ("Torsion","Shear + Torsion") and not cfg.hoop_confirmed:
            reasons.append("Confirm actual closed hoop shape, cover and perimeter longitudinal steel in the solid ends/tapers; the I-zone declaration alone is insufficient.")
    result["End section acceptance"]="REVIEW" if reasons else "PASS"
    if reasons:
        for key in ("Status","Overall status"):
            if result.get(key)=="PASS": result[key]="REVIEW"
        result["Notes"]=" ".join(filter(None,[str(result.get("Notes") or ""),*reasons]))
        result["End section review"]=" ".join(reasons)
    return result

def station_check(check_name):
    def decorate(fn):
        @wraps(fn)
        def wrapped(state,row,*args,**kwargs):
            try:
                local=at_station(state,row.get("Station x (m)")) if ends.enabled(state) else state
                from concrete_pmm_pro.ui.csi_reference_analysis import convert_for_check
                from concrete_pmm_pro.io.csi_force_reference import qualify_result
                converted=convert_for_check(local,row,check_name=check_name)
            except (ValueError,TypeError,KeyError) as exc:
                from concrete_pmm_pro.ui import analysis_page as ap
                return {"Check":check_name,"Status":"REVIEW","Numerical status":"SECTION UNAVAILABLE",
                    "Governing x":ap._format_beam_uls_x(row.get("Station x (m)")),"Station x (m)":row.get("Station x (m)"),"Case":row.get("Case Name"),
                    "Result version":ap._IGIRDER_COMBINED_VT_RESULT_VERSION if check_name=="Shear + Torsion" else ends.RESULT_VERSION,
                    "Station type":str(row.get("__VT station type") or "LOAD STATION"),"Section region":"UNAVAILABLE","End section acceptance":"REVIEW",
                    "φVn kN":float("nan"),"φTn kN-m":float("nan"),"Capacity kN":float("nan"),"Capacity kN-m":float("nan"),
                    "Utilization value":float("nan"),"D/C value":float("nan"),"Overall D/C value":float("nan"),"Notes":str(exc)}
            result=qualify_result(fn(local,converted,*args,**kwargs),converted,check_name=check_name)
            return annotate(result,local,check_name=check_name)
        return wrapped
    return decorate

def station_figure(frame_argument):
    """Draw saved geometry only; never rerun a solver in review."""
    def decorate(fn):
        signature=inspect.signature(fn)
        @wraps(fn)
        def wrapped(*args,**kwargs):
            fig=fn(*args,**kwargs);frame=signature.bind_partial(*args,**kwargs).arguments.get(frame_argument)
            if frame is None or frame.empty or "Section region" not in frame: return fig
            regions={}
            for _,row in frame.iterrows():
                try: x=float(str(row.get("Governing x")).replace(" m",""))
                except (ValueError,TypeError): continue
                regions[(str(row.get("Case")),round(x,6))]=str(row.get("Section region") or "UNAVAILABLE")
            for trace in fig.data:
                if trace.customdata is None or trace.x is None or not trace.hovertemplate: continue
                labels=[]
                for x,data in zip(trace.x,trace.customdata):
                    try: labels.append(regions.get((str(data[0]),round(float(x),6)),"UNAVAILABLE"))
                    except (ValueError,TypeError,IndexError): labels.append("UNAVAILABLE")
                if labels:
                    trace.text=labels
                    if "Section=%" not in trace.hovertemplate:
                        trace.hovertemplate=trace.hovertemplate.replace("<extra>","<br>Section=%{text}<extra>")
            if "Section boundaries (m)" in frame:
                values=frame["Section boundaries (m)"].dropna()
                if len(values):
                    for token in str(values.iloc[0]).split(","):
                        try:
                            x=float(token)
                            if math.isfinite(x): fig.add_vline(x=x,line_width=1,line_dash="dot",line_color="#94a3b8",layer="below")
                        except (ValueError,TypeError): continue
            fig.update_layout(meta={**dict(fig.layout.meta or {}),"station_geometry":ends.RESULT_VERSION})
            return fig
        return wrapped
    return decorate

def geometry_diagram_demands(state,demands):
    """Interpolate same-case vectors at geometric changes for diagrams only."""
    if not ends.enabled(state) or demands.empty: return demands
    import pandas as pd
    from concrete_pmm_pro.ui import analysis_page as ap
    geometry=state.get(BASE_GEOMETRY,state.get("section_geometry"))
    if isinstance(geometry,dict): geometry=SectionGeometry.model_validate(geometry)
    try: cfg=ends.profile(state,geometry,ap._beam_uls_span_length_from_state(state,is_building=False))
    except (ValueError,TypeError,KeyError): return demands
    points=set(cfg.boundaries)
    for a,b in ((cfg.left_x_m,cfg.left_x_m+cfg.left_solid_m),
            (cfg.left_x_m+cfg.left_solid_m,cfg.left_x_m+cfg.left_solid_m+cfg.left_taper_m),
            (cfg.right_x_m-cfg.right_solid_m-cfg.right_taper_m,cfg.right_x_m-cfg.right_solid_m),
            (cfg.right_x_m-cfg.right_solid_m,cfg.right_x_m)):
        points.update(a+(b-a)*f for f in (.25,.5,.75) if b>a)
    additions=[];actions=['Mux','Vuy','Tu','Muy','Vux','Nu']
    for case,group in demands.groupby('Case Name',sort=False):
        group=group.copy();group['Station x (m)']=pd.to_numeric(group['Station x (m)'])
        if any(len(same[actions].drop_duplicates())>1 for _,same in group.groupby('Station x (m)')): continue
        group=group.drop_duplicates('Station x (m)').sort_values('Station x (m)')
        for x in sorted(points):
            if group['Station x (m)'].sub(x).abs().lt(1e-8).any(): continue
            left=group[group['Station x (m)']<x];right=group[group['Station x (m)']>x]
            if left.empty or right.empty: continue
            a,b=left.iloc[-1],right.iloc[0];fraction=(x-float(a['Station x (m)']))/(float(b['Station x (m)'])-float(a['Station x (m)']))
            try:
                values={key:float(a[key])+(float(b[key])-float(a[key]))*fraction for key in actions}
                if not all(math.isfinite(v) for v in values.values()): continue
            except (ValueError,TypeError,KeyError): continue
            additions.append({**a.to_dict(),**values,'Station x (m)':x,'Case Name':case,
                'Note':'Same-case force interpolation for end/taper capacity diagram only; no new physical design station.',
                '__Geometry sample':True,'__Source row':'','__Shared CSI endpoint':False})
    return pd.concat([demands,pd.DataFrame(additions)],ignore_index=True).sort_values(['Case Name','Station x (m)'],kind='stable') if additions else demands
