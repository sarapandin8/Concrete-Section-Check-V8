"""Analysis-only research adapter. No diagnostic result feeds design acceptance.

Existing geometry/materials/ordinary-bar development/dowel zoning are reused.
The central rectangular cell is an explicit HYPOTHESIS; the existing I-hoop
outline and slab Be are never replaced by this path in any production engine.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import math

import pandas as pd
import streamlit as st
from shapely.geometry import box

from concrete_pmm_pro.analysis import igird_coupled_resistance as engine
from concrete_pmm_pro.analysis import igird_dowel_joint as joint
from concrete_pmm_pro.analysis.igird_interface_connectors import at_station, STIRRUPS
from concrete_pmm_pro.analysis.igird_interface_shear import surface_preset

KEY = "igird_coupled34_settings"
STATE_COLUMNS = ["Girder", "Case", "Station x (m)", "qx_kN_per_m", "qy_kN_per_m", "n_kN_per_m", "mx_kNm_per_m", "mz_kNm_per_m", "Source"]


def settings(state):
    raw = (state.get("project_metadata") or {}).get(KEY, {})
    return deepcopy(dict(raw)) if isinstance(raw,Mapping) else {}


def fingerprint(state, rows, *, route):
    from . import analysis_page as ap
    from concrete_pmm_pro.io import csi_component_sources
    payload = {"version":engine.VERSION,"settings":settings(state),
        "dowel_detail":joint.config(ap._igird_interface_shear_settings_from_state(state)),
        "section":ap._beam_uls_final_composite_flexure_hash(state,rows,strength_route=route),
        "interface":ap._igird_interface_shear_hash(state,ap._igird_interface_source_dataframe(rows),
            settings=ap._igird_interface_shear_settings_from_state(state),strength_route=route),
        "components":csi_component_sources.fingerprint(csi_component_sources.saved(state))}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()


def render_inputs(state, *, prefix="flexure"):
    cfg = settings(state)
    with st.expander("Composite V–T — research model inputs",expanded=False):
        st.warning("Research model only. Full composite design acceptance requires compatible cracking/slip behaviour and independent structural validation; this version cannot issue production Tn or V–T PASS.")
        cfg["enabled"] = st.toggle("Include coupled composite model in Calculate", value=bool(cfg.get("enabled",False)),key=f"igird_coupled34_{prefix}_enabled")
        if cfg["enabled"]:
            st.caption("Reuses the girder, assigned slab, materials, U-detail, dowel zones and developed ordinary bars. Slab longitudinal bars are not transverse closing bars. Prestress is omitted from the research longitudinal reserve.")
            from .igird_input_editor import input_editor
            names = {"closure_db_mm":"Transverse slab closing bar diameter (mm)",
                     "closure_spacing_mm":"Closing bar spacing along girder (mm)",
                     "lap_available_mm":"Actual U-to-girder-hoop straight overlap (mm)"}
            frame = pd.DataFrame({"Detail":list(names.values()),"Value":[cfg.get(k) for k in names]})
            frame["Value"] = pd.to_numeric(frame["Value"],errors="coerce")
            edited = input_editor(frame,prefix=f"igird_coupled34_{prefix}_detail_",hide_index=True,
                use_container_width=True,disabled=["Detail"],column_config={"Value":st.column_config.NumberColumn("Provided",min_value=0.)})
            for k,v in zip(names,edited["Value"]): cfg[k] = float(v) if pd.notna(v) and math.isfinite(float(v)) else None
            routes = ["unverified", "90-degree tension hooks", "continuous closed unit with verified 135-degree torsion anchorage"]
            current = cfg.get("closure_detail","unverified")
            cfg["closure_detail"] = st.selectbox("Actual closed-path detail",routes,index=routes.index(current) if current in routes else 0,key=f"igird_coupled34_{prefix}_closure")
            cfg["drawing_reference"] = st.text_input("Cage / lap drawing reference",value=str(cfg.get("drawing_reference") or ""),key=f"igird_coupled34_{prefix}_drawing")
            st.caption("This selector records the actual detail for review; it cannot validate the research model or enable production acceptance. The candidate cell width is U-leg spacing, not slab Be.")
            with st.expander("Advanced — concurrent interface states",expanded=False):
                st.caption("Optional for model V–T at actual actions. One exact girder / app case / station and verified free-body source per row. mz is the background moment of longitudinal interface tractions; unknown values remain blank. The model separately adds its signed torsional-flow couple. Never copy Girder Tu into mx or mz.")
                rows = cfg.get("action_rows",[])
                f = pd.DataFrame(rows if isinstance(rows,list) else [],columns=STATE_COLUMNS)
                for c in STATE_COLUMNS[2:8]: f[c] = pd.to_numeric(f[c],errors="coerce")
                edited = input_editor(f,prefix=f"igird_coupled34_{prefix}_actions_",num_rows="dynamic",hide_index=True,use_container_width=True)
                cfg["action_rows"] = json.loads(edited.to_json(orient="records",double_precision=15))
    metadata = dict(state.get("project_metadata") or {}); metadata[KEY] = cfg; state["project_metadata"] = metadata


def _positive(raw, name):
    n = joint.number(raw.get(name))
    labels={"row_spacing_mm":"U-leg centre spacing A (mm)","slab_ldh_available_mm":"interface-to-hook dimension B (mm)",
        "closure_db_mm":"transverse slab closing-bar diameter (mm)","closure_spacing_mm":"closing-bar spacing along girder (mm)",
        "cover_required_mm":"required clear cover E (mm)","Diameter_mm":"bar diameter (mm)","Spacing_mm":"bar spacing (mm)",
        "fy_MPa":"bar yield strength (MPa)","deck_long_rebar_fy_MPa":"slab reinforcement yield-strength basis (MPa)"}
    if not math.isfinite(n) or n <= 0: raise ValueError("Provide " + labels.get(name,name) + "; no default physical detail is assumed.")
    return n


def weakest_girder_zone(zones, x):
    """Do not let table order choose the stronger side of a spacing change."""
    covered=[]
    intervals=[]
    for raw in zones:
        if not raw.get("Active",True): continue
        a,b=joint.number(raw.get("x_start_m")),joint.number(raw.get("x_end_m"))
        if not math.isfinite(a+b) or a<0 or b<=a: raise ValueError("Define valid girder transverse-zone ranges.")
        intervals.append((a,b))
        if a-1e-9<=x<=b+1e-9:
            db,fy,s=[_positive(raw,k) for k in ("Diameter_mm","fy_MPa","Spacing_mm")]
            if joint.number(raw.get("Legs"))!=2: raise ValueError("Research girder cage requires exactly two physical legs at this station.")
            covered.append((math.pi*db*db/4*min(fy,75*6.894757293)/s,raw))
    intervals.sort()
    if any(b[0]<a[1]-1e-9 for a,b in zip(intervals,intervals[1:])): raise ValueError("Girder transverse zones overlap; supplies cannot be added.")
    if not covered: raise ValueError("No girder transverse zone covers this physical station.")
    return min(covered,key=lambda item:item[0])[1]


def _context(state, row, *, cfg, interface, route):
    """No calls from rendering. Numeric hypotheses remain separate from detail gates."""
    from . import analysis_page as ap, igird_station_section
    from concrete_pmm_pro.analysis.igird_flexure_development import SectionEquilibrium, ordinary_bar_limits, development_settings
    from concrete_pmm_pro.geometry.summary import to_shapely_polygon
    x = float(row["Station x (m)"])
    local = igird_station_section.at_station(state,x)
    params = dict(ap._beam_uls_get_state_value(local,"section_parameters",{}) or {})
    prep, composite, messages = ap._beam_uls_final_composite_preparation(local)
    if composite is None: raise ValueError("; ".join(messages) or "Composite section geometry unavailable.")
    if ap._igird_interface_density_basis(local)[0]: raise ValueError("Research adapter supports normal-weight concrete only.")
    def material_value(material,key):
        return material.get(key) if isinstance(material,Mapping) else getattr(material,key,None)
    girder_material=ap._beam_uls_get_state_value(local,"concrete_material")
    deck_name=str(ap._beam_uls_get_state_value(local,"deck_topping_material_name","") or "")
    materials=ap._beam_uls_get_state_value(local,"concrete_materials",[]) or []
    decks=[m for m in materials if deck_name and material_value(m,"name")==deck_name]
    densities=[joint.number(material_value(girder_material,"density_kg_m3"))]+[
        joint.number(material_value(m,"density_kg_m3")) for m in decks]
    if len(decks)!=1 or any(not math.isfinite(d) or d<2200 for d in densities):
        raise ValueError("Known normal-weight girder and assigned slab material densities are required.")
    fc = min(float(prep.deck_fc_MPa),float(prep.girder_fc_MPa))
    if not 0 < fc <= 68.9475729: raise ValueError("Composite torsion concrete is outside the <=10 ksi research scope.")
    zone = weakest_girder_zone(ap._beam_uls_shear_reinforcement_dataframe_from_state(local).to_dict("records"),x)
    connector = at_station(interface,x_m=x,girder_zone=zone)
    if zone is None or not connector["ready"]: raise ValueError(connector.get("reason") or "No girder transverse zone covers station.")
    if interface.get("connector_source") == STIRRUPS: raise ValueError("Select explicit U-dowel reinforcement; girder stirrups are not silently copied into a second supply.")
    dz = connector["zone"]
    if joint.number(zone.get("Legs")) != 2 or joint.number(dz.get("Legs")) != 2:
        raise ValueError("The central-cell research adapter supports exactly two physical legs in each series segment.")
    from concrete_pmm_pro.analysis.igird_dowel_detail35 import resolve
    detail = resolve(joint.config(interface), slab_thickness_mm=float(prep.deck_thickness_mm), db_mm=dz.get("Diameter_mm"))
    a = _positive(detail,"row_spacing_mm"); B = _positive(detail,"slab_ldh_available_mm")
    db = _positive(dz,"Diameter_mm"); db_g = _positive(zone,"Diameter_mm")
    close_db = _positive(cfg,"closure_db_mm"); close_s = _positive(cfg,"closure_spacing_mm")
    cover = _positive(detail,"cover_required_mm")
    geom = ap._beam_uls_get_state_value(local,"section_geometry")
    if isinstance(geom,Mapping): geom = ap.SectionGeometry.model_validate(geom)
    poly = to_shapely_polygon(geom)
    xmin,ymin,xmax,ymax = poly.bounds
    width,basis = ap._igird_interface_bvi_mm(local,interface)
    centre = .5*(xmin+xmax)
    yb = ymin+cover+.5*db_g; yt = ymax+B-.5*db
    H = yt-yb
    if H <= 0 or not 0 < a < width: raise ValueError("Candidate cell height/leg spacing does not fit contact geometry.")
    # Rectangular CENTRAL path only. This is not the accepted I-hoop outline.
    # The prototype refuses a centreline crossing the exterior or a void.
    cage = box(centre-a/2,yb,centre+a/2,min(ymax,yt))
    if not poly.covers(cage): raise ValueError("Candidate central cell crosses the girder exterior/void. Verify the physical cage path.")
    full = to_shapely_polygon(prep.geometry)
    if not full.covers(box(centre-a/2,yb,centre+a/2,yt)):
        raise ValueError("Candidate central cell is outside the girder/slab polygon.")
    inp,notes = ap._beam_uls_flexure_analysis_input_for_station(composite,row=row,strength_route=route,
        capacity_direction=1.,prestress_force_stage="final")
    if inp is None: raise ValueError("; ".join(notes))
    context = SectionEquilibrium(inp,1.)
    if context.unresolved_bar_materials: raise ValueError("Unresolved ordinary-bar material; no fallback strength credit.")
    span = ap._beam_uls_span_length_from_state(state,is_building=False)
    dev = development_settings(state)
    factors,trace = ordinary_bar_limits(context,x_m=x,span_m=span,settings=dev,params=params,girder_fc_mpa=float(prep.girder_fc_MPa))
    # The weaker half-section governs the scalar longitudinal reserve. The
    # SAME reserve also carries held M/N in the coupled solve. No separate
    # torsion steel is added; prestress is conservatively omitted in this adapter.
    middle = .5*(yb+yt)
    upper = lower = 0.
    for bar,factor in zip(context.bars,factors):
        material = context.materials[bar.material_name]
        force = bar.area_mm2*material.fy_MPa*factor
        if bar.y_mm >= middle: upper += force
        else: lower += force
    long_N = min(upper,lower)
    depths = ap._beam_uls_effective_shear_depth_values_mm(composite,inp,mux_kNm=1.,strength_route=route,row=row)
    dv = joint.number(depths.get("dv_mm"))
    if not math.isfinite(dv) or dv <= 0: raise ValueError("Actual composite effective depth is unavailable.")
    # HYPOTHETICAL narrow cell: neither Be nor the girder Ao/ph are enlarged.
    ao, ph = a*H, 2.*(a+H)
    bw = float(params.get("T2_mm",0.))
    teff = min(a/2.,bw/2.,float(prep.deck_thickness_mm)/2.)
    if teff <= 0: raise ValueError("Candidate wall thickness cannot be resolved.")
    surface = surface_preset(interface.get("surface_key"))
    const = surface.constants_si(lightweight=False)
    fy_d = min(_positive(dz,"fy_MPa"),60.*6.894757293)
    fy_g = min(_positive(zone,"fy_MPa"),75.*6.894757293)
    # No separate arbitrary fy input: closing-bar steel uses the LOWER known
    # dowel/slab-longitudinal yield stress, stated in the hypothesis trace.
    slab_fy=[joint.number(params.get(k)) for k in ("deck_long_rebar_fy_MPa","deck_long_rebar_top_fy_MPa","deck_long_rebar_bottom_fy_MPa")]
    slab_fy=[v for v in slab_fy if math.isfinite(v) and v>0]
    if not slab_fy: raise ValueError("Slab reinforcement yield-strength basis is unavailable.")
    fy_c = min(fy_d,*slab_fy)
    area = lambda d: math.pi*d*d/4.
    cell = engine.Cell(ao,ph,dv,width,a,area(db_g)*fy_g/_positive(zone,"Spacing_mm"),
        area(db)*fy_d/_positive(dz,"Spacing_mm"),area(close_db)*fy_c/close_s,long_N,
        .25*fc*teff*.5,surface.mu,.85*fc,min(const["K1"]*fc,const["K2_MPa"]))
    # Structural detailing is reported separately and cannot turn numerical
    # optimization into validation. Existing 90-degree hook checks are reused.
    geometry_context={"fc_slab_MPa":float(prep.deck_fc_MPa),"fc_girder_MPa":float(prep.girder_fc_MPa),
        "slab_thickness_mm":float(prep.deck_thickness_mm),"girder_depth_mm":ymax-ymin,
        "girder_polygon":[list(p) for p in poly.exterior.coords],"girder_holes":[[list(p) for p in h.coords] for h in poly.interiors],
        "contact_center_x_mm":centre,"contact_top_y_mm":ymax,"normal_weight":True}
    anchor = joint.anchorage(detail,dz,geometry_context)
    issues=[]
    if anchor.get("status") != "DIMENSION CHECKS MET": issues.append("U-dowel anchorage dimensions / geometric fit require review.")
    if cfg.get("closure_detail") != "continuous closed unit with verified 135-degree torsion anchorage": issues.append("Actual full closed path / 135-degree torsion anchorage is unverified; 90-degree tension hooks are insufficient evidence.")
    if not str(cfg.get("drawing_reference") or "").strip(): issues.append("Provide the cage / lap drawing reference.")
    lap = joint.number(cfg.get("lap_available_mm"))
    requirement = joint.development_requirements(db_mm=db,fy_MPa=fy_d,fc_slab_MPa=float(prep.deck_fc_MPa),fc_girder_MPa=float(prep.girder_fc_MPa),coating=detail.get("coating"))
    girder_req = joint.development_requirements(db_mm=db_g,fy_MPa=fy_g,fc_slab_MPa=float(prep.deck_fc_MPa),fc_girder_MPa=float(prep.girder_fc_MPa),coating=detail.get("coating"))
    lap_required = 1.3*max(requirement["straight_required_mm"],girder_req["straight_required_mm"])
    if not math.isfinite(lap) or lap < lap_required: issues.append(f"Verify actual splice overlap >= {lap_required:.1f} mm; F alone is not an actual overlap measurement.")
    if math.isfinite(lap) and lap > joint.number(detail.get("girder_ld_available_mm"))+1e-7: issues.append("Entered lap exceeds the available straight U leg F.")
    if not interface.get("connectors_cross_and_anchored"): issues.append("Crossing and anchorage on both sides is unconfirmed.")
    if not dev.get("bars_continuous_confirmed") or any(not t.get("continuity_confirmed",True) for t in trace): issues.append("Developed ordinary / slab longitudinal continuity needs drawing verification.")
    if long_N <= 0: issues.append("No developed ordinary longitudinal tension reserve in at least one half-section.")
    issues.append("Candidate central rectangular path is not the existing I-hoop path; verify transfer between the actual cages and slab closure.")
    from concrete_pmm_pro.io.csi_force_reference import geometry_origin
    return cell,{"hypothesis":"Central rectangular closed path — not a drawing-derived full composite cage", "x_m":x,
        "resistance_origin":geometry_origin(prep.geometry,includes_deck=True),
        "width_basis":basis,"H_mm":H,"Ao_mm2":ao,"ph_mm":ph,"teff_mm":teff,"diagonal_cap_assumption":"0.25 fc teff sin(45)cos(45); not MCFT calibrated",
        "girder_single_leg_N_per_mm":cell.girder_leg_N_per_mm,"dowel_single_leg_N_per_mm":cell.dowel_leg_N_per_mm,
        "closing_bar_fy_MPa":fy_c,"longitudinal_upper_N":upper,"longitudinal_lower_N":lower,"prestress_credit_N":0.,
        "lap_required_mm":lap_required,"anchorage":anchor,"detail_issues":issues,"ordinary_bar_trace":trace}


def calculate(state, rows, *, route):
    """Explicit Calculate only. No inferred interface action vector or PASS."""
    from . import analysis_page as ap
    from .igird_combined_vt import concurrent_source_allowed
    from concrete_pmm_pro.io.girder_csi_import import source_info
    from concrete_pmm_pro.io.csi_force_reference import prepare_analysis_frame, translate_row, trace_columns, SNAPSHOT_KEY
    cfg = settings(state)
    result={"version":engine.VERSION,"enabled":bool(cfg.get("enabled")),"rows":[],"traces":[],
            "production_status":"UNVALIDATED — REVIEW","accepted_phiTn_Nmm":None,"accepted_VT_factor":None}
    if not result["enabled"]: return result
    result["fingerprint"] = fingerprint(state,rows,route=route)
    interface=ap._igird_interface_shear_settings_from_state(state)
    cache={}
    prepared=prepare_analysis_frame(rows)
    for _,row in prepared.iterrows():
        x = joint.number(row.get("Station x (m)")); info=source_info(row) or {}
        source_member=" / ".join(str(info.get(k) or "") for k in ("bridge_object","girder")).strip(" / ")
        name=str(row.get("Girder") or source_member or state.get("igird_active_member") or "")
        case=str(row.get("Case Name") or "")
        rec={"Girder":name,"Case":case,"Load case":info.get("case",case),"Bound":info.get("step",""),"x (m)":x,"Status":"MODEL BLOCKED","Model Tn (kN-m)":None,"Model V–T factor":None,"Production":"WITHHELD"}
        if not math.isfinite(x):
            rec["Reason"]="Invalid source station.";result["rows"].append(rec);continue
        if x not in cache:
            try:
                cell,trace = _context(state,row,cfg=cfg,interface=interface,route=route)
                nominal=engine.nominal_torsion(cell)
                fine=engine.nominal_torsion(cell,cells=64)
                trace.update(nominal=nominal,refined_nominal=fine)
                coarse=nominal.get("model_Tn_Nmm");refined=fine.get("model_Tn_Nmm")
                trace["mesh_relative_change"] = abs(refined-coarse)/max(1.,abs(refined)) if coarse is not None and refined is not None else None
                cache[x]=(cell,trace)
                result["traces"].append(trace)
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                cache[x]=(None,{"reason":str(exc)})
        cell,trace = cache[x]
        if cell is None:
            rec["Reason"]=trace["reason"];result["rows"].append(rec);continue
        nominal=trace["nominal"]
        if nominal.get("model_Tn_Nmm") is not None: rec["Model Tn (kN-m)"]=nominal["model_Tn_Nmm"]/1.e6
        rec["Status"]="HYPOTHESIS ONLY"; rec["Reason"]="; ".join(trace["detail_issues"])
        rec["Contact refinement Δ"] = trace["mesh_relative_change"]
        if not concurrent_source_allowed(info):
            rec["V–T source"]="BLOCKED — no verified concurrent section vector"
        else:
            action = matching_action(cfg.get("action_rows",[]),member=name,case=case,x=x)
            if action is None: rec["V–T source"]="BLOCKED — exact member/case/station interface free-body missing or ambiguous"
            elif SNAPSHOT_KEY not in info:
                rec["V–T source"]="BLOCKED — immutable CSI force-origin snapshot missing"
            elif info[SNAPSHOT_KEY].get("force_kind")!="GIRDER_COMPOSITE":
                rec["V–T source"]="BLOCKED — full-system demand requires Girder/composite forces, not Beam-only output"
            else:
                translated=translate_row(row,origin=trace["resistance_origin"])
                ref=trace_columns(translated)
                # Preserve all original loads and independently transport every
                # actual concurrent vector to the composite resistance centroid.
                values=[joint.number(translated.get(k)) for k in ("Vuy","Tu","Mux","Nu","Muy","Vux")]
                if not all(math.isfinite(v) for v in values) or max(abs(values[4]),abs(values[5]))>1.e-9:
                    rec["V–T source"]="BLOCKED — finite primary actions and zero secondary M2/V3 required by this uniaxial research route"
                elif trace["mesh_relative_change"] is None or trace["mesh_relative_change"]>.02:
                    rec["V–T source"]="BLOCKED — contact refinement did not converge within 2%"
                else:
                    V,T,M,N,_,_=values
                    act=engine.Actions(V*1000.,T*1.e6,M*1.e6,N*1000.,
                        action["qx_kN_per_m"],action["qy_kN_per_m"],action["n_kN_per_m"],
                        action["mx_kNm_per_m"]*1000.,action["mz_kNm_per_m"]*1000.)
                    coupled=engine.solve(cell,act,nominal=False)
                    rec["Model V–T factor"]=coupled.get("capacity_factor")
                    rec["V–T source"]="CONCURRENT — hypothesis model only"
                    result["traces"].append({"Girder":name,"Case":case,"x_m":x,"reference":ref,"coupled":coupled})
        result["rows"].append(rec)
    return result


def matching_action(rows, *, member, case, x):
    matches=[]
    for raw in rows if isinstance(rows,list) else []:
        if not isinstance(raw,Mapping): continue
        if str(raw.get("Girder") or "") != member or str(raw.get("Case") or "") != case: continue
        if abs(joint.number(raw.get("Station x (m)"))-x)>1e-8: continue
        if any(not math.isfinite(joint.number(raw.get(k))) for k in STATE_COLUMNS[2:8]): continue
        if not str(raw.get("Source") or "").strip(): continue
        matches.append({**raw,**{k:float(raw[k]) for k in STATE_COLUMNS[2:8]}})
    return matches[0] if len(matches)==1 else None


def render_result(state, rows, stored, *, route, inputs=False):
    """Stored read-only research view; never writes to engineering result owners."""
    st.markdown("##### Composite V–T — coupled resistance / validation")
    st.warning("Production acceptance: WITHHELD. COUPLED34 can calculate an idealized nominal Tn and coupled model load factor; strain/slip compatibility and independent structural validation are incomplete.")
    if inputs: render_inputs(state,prefix="combined")
    cfg=settings(state)
    if not cfg.get("enabled"):
        st.caption("Research model is available. Enable it under composite / dowel inputs and use the existing Calculate command; normal Loads upload is unchanged.")
    elif not stored or stored.get("fingerprint")!=fingerprint(state,rows,route=route):
        st.info("Composite research results are missing or stale. Use the main Calculate command. Existing sectional results remain separate.")
    else:
        frame=pd.DataFrame(stored.get("rows",[]))
        if not frame.empty:
            numeric=pd.to_numeric(frame["Model Tn (kN-m)"],errors="coerce")
            stations=frame.loc[numeric.notna(),"x (m)"].nunique()
            st.caption(f"{stations} station(s) have a numeric HYPOTHETICAL model Tn. This is pure torsion at V=M=N=external joint loads=0; it is not resistance available at the actual M/N or a production φTn.")
            columns=[c for c in ("x (m)","Status","Model Tn (kN-m)","Reason") if c in frame]
            st.dataframe(frame[columns].drop_duplicates(),hide_index=True,use_container_width=True)
            with st.expander("Concurrent V–T states / source readiness",expanded=False):
                columns=[c for c in ("x (m)","Load case","Bound","Model V–T factor","V–T source","Case") if c in frame]
                st.dataframe(frame[columns],hide_index=True,use_container_width=True)
        with st.expander("Coupled model witness / numerical checks",expanded=False):
            st.json(stored.get("traces",[]))
    with st.expander("Structural validation — acceptance gates",expanded=False):
        st.dataframe(pd.DataFrame(engine.validation_table()),hide_index=True,use_container_width=True)
        st.caption("Model assumptions: 45° cracked truss; Vc=0; cohesion=0; central closed-cell hypothesis; shared ordinary longitudinal reserve, no prestress credit; inscribed friction cone. A numerical optimizer verifies equilibrium and shared capacity bounds, not actual structural performance.")
