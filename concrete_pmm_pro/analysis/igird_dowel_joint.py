"""U-dowel anchorage and a statically admissible cracked-joint mechanism.

This is a separate mechanism screening model, NOT composite girder resistance.
It assumes two symmetric developed tension ties, compression-only concrete
contact and Coulomb friction. It does not establish strain compatibility,
slab bending, splitting, dowel bending/shear or a closed torsion cage. Its
results must not feed production ULS acceptance, Summary or Report/QA.
"""
from __future__ import annotations

from copy import deepcopy
import math
from collections.abc import Mapping

from .igird_interface_shear import INTERFACE_FY_CAP_MPA, KSI_TO_MPA, SURFACE_PRESETS, surface_preset

VERSION = "IGIRDER.JOINT29.DETAIL35"
MODE = "cracked_equilibrium"
KEY = "dowel_connection"
ACTION_COLUMNS = ["Case", "Station x (m)", "qx_kN_per_m", "qy_kN_per_m",
                  "n_kN_per_m", "mx_kNm_per_m", "Source"]
DIMENSIONS = {
    "row_spacing_mm": "Transverse distance between the two leg centres (mm)",
    "slab_ldh_available_mm": "Slab: interface to outside of hook bend, ldh available (mm)",
    "hook_tail_mm": "Slab: straight tail beyond the bend (mm)",
    "hook_inside_bend_mm": "Slab: inside bend diameter (mm)",
    "cover_required_mm": "Project required clear cover at the hook / bar (mm)",
    "girder_ld_available_mm": "Girder: straight bonded leg below interface, excluding U-bend (mm)",
}
SCOPE = ("REVIEW — U-dowel joint mechanism only. Full composite V–T, slab bending, "
         "local splitting/confinement, slip/opening compatibility and D-regions remain separate. "
         "No enlargement of Ao/ph or production torsional-resistance credit.")


def number(value):
    try:
        return float(value) if not isinstance(value, bool) else float("nan")
    except (ValueError, TypeError):
        return float("nan")


def config(settings):
    raw = settings.get(KEY, {}) if isinstance(settings, Mapping) else {}
    return deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}


def development_requirements(*, db_mm, fy_MPa, fc_slab_MPa, fc_girder_MPa, coating):
    """AASHTO 2020 5.10.8.2.4a / 5.10.8.2.1a; no beneficial modifiers.

    Vertical, individual bars; normal-weight fc <=10 ksi and fy <=75 ksi.
    Conservative general tension hook: 12db tail and general bend diameter.
    No confinement, excess-steel or bottom U-return development credit.
    """
    db, fy, fs, fg = map(number, (db_mm, fy_MPa, fc_slab_MPa, fc_girder_MPa))
    if not all(math.isfinite(v) and v > 0 for v in (db, fy, fs, fg)):
        raise ValueError("Positive bar diameter, fy and both concrete strengths are required.")
    if db > 35.8 or fy > 75 * KSI_TO_MPA or max(fs, fg) > 10 * KSI_TO_MPA:
        raise ValueError("This anchorage route is limited to db ≤35.8 mm, fy ≤75 ksi and normal-weight fc ≤10 ksi; additional code detailing is not implemented.")
    if coating not in {"uncoated", "epoxy"}:
        raise ValueError("Specify whether the dowel is uncoated or epoxy coated.")
    fy_ksi = fy / KSI_TO_MPA
    hook_factor = 1.2 if coating == "epoxy" else 1.
    # Worst epoxy cover/spacing factor; no beneficial confinement reduction.
    straight_factor = 1.5 if coating == "epoxy" else 1.
    return {
        "hook_required_mm": max(8*db, 6*25.4,
            38*db*(fy_ksi/60)/math.sqrt(fs/KSI_TO_MPA)*hook_factor),
        "straight_required_mm": max(12*25.4,
            2.4*db*fy_ksi/math.sqrt(fg/KSI_TO_MPA)*straight_factor),
        "tail_required_mm": 12*db,
        "bend_required_mm": (6 if db <= 25.4 else 8)*db,
        "hook_coating_factor": hook_factor,
        "straight_coating_factor": straight_factor,
        "basis": "AASHTO 2020 5.10.8.2.4a, 5.10.8.2.1a, 5.10.2.1 and Table 5.10.2.3-1; vertical individual bars, lambda_rc=lambda_er=1; bottom return ignored",
    }


def anchorage(cfg, zone, context):
    """Return measurable checks; the old anchorage declaration is not proof."""
    from .igird_dowel_detail35 import resolve, covers
    cfg = resolve(cfg, slab_thickness_mm=context.get("slab_thickness_mm"), db_mm=zone.get("Diameter_mm"))
    result = {"ready": False, "status": "REVIEW", "checks": {}, "reasons": []}
    try:
        if context.get("normal_weight") is not True:
            raise ValueError("A known normal-weight concrete basis is required for this anchorage route.")
        req = development_requirements(db_mm=zone.get("Diameter_mm"), fy_MPa=zone.get("fy_MPa"),
            fc_slab_MPa=context.get("fc_slab_MPa"), fc_girder_MPa=context.get("fc_girder_MPa"),
            coating=cfg.get("coating"))
        result.update(req)
    except ValueError as exc:
        result["reasons"].append(str(exc)); return result
    if cfg.get("anchorage_region") != "interior":
        result["reasons"].append("Only an interior anchorage region is implemented; unknown or discontinuous-end hook confinement needs separate detailing.")
    checks = result["checks"]
    for key, limit in (("slab_ldh_available_mm", req["hook_required_mm"]),
                       ("hook_tail_mm", req["tail_required_mm"]),
                       ("hook_inside_bend_mm", req["bend_required_mm"]),
                       ("girder_ld_available_mm", req["straight_required_mm"])):
        available = number(cfg.get(key))
        if not math.isfinite(available) or available <= 0:
            result["reasons"].append("Enter " + DIMENSIONS[key]); continue
        checks[key] = {"available_mm": available, "required_mm": limit,
                       "dc": limit/available, "adequate": available+1e-8 >= limit}
    cover, slab_cover = map(number, covers(cfg))
    result["resolved_detail"] = {k:cfg.get(k) for k in ("detail_schema", "bend_mode", "hook_top_depth_mm", "slab_ldh_available_mm", "hook_inside_bend_mm")}
    result["cover_basis"] = {"girder_required_mm":cover, "slab_required_mm":slab_cover}
    ts, h = number(context.get("slab_thickness_mm")), number(context.get("girder_depth_mm"))
    top, bottom = number(cfg.get("slab_ldh_available_mm")), number(cfg.get("girder_ld_available_mm"))
    db = number(zone.get("Diameter_mm"))
    if not math.isfinite(cover) or cover <= 0 or not all(math.isfinite(v) and v>0 for v in (ts, h)):
        result["reasons"].append("Known slab/girder depths and required clear cover are needed to check anchorage fit.")
    else:
        if math.isfinite(top) and top>0 and math.isfinite(slab_cover) and slab_cover>0:
            checks["slab_hook_cover"] = {"available_mm": ts-top, "required_mm": slab_cover,
                "dc": slab_cover/(ts-top) if ts>top else None, "adequate": ts-top+1e-8>=slab_cover}
        elif not math.isfinite(slab_cover) or slab_cover<=0:
            result["reasons"].append("Provide the required slab clear cover separately from the measured hook depth E.")
        if math.isfinite(bottom) and bottom>0:
            # Available straight length ends before the return bend, never on it.
            limit = h-cover-db/2
            checks["girder_leg_fit"] = {"available_mm": limit, "required_mm": bottom,
                "dc": bottom/limit if limit>0 else None, "adequate": bottom<=limit+1e-8}
    # The straight leg must actually remain in concrete, including the narrow
    # web. The construction interface is not a free cover face. All other
    # concrete boundaries retain the required side/bottom cover.
    if math.isfinite(bottom) and bottom>0 and math.isfinite(cover) and cover>0:
        try:
            from shapely.geometry import Polygon, LineString
            polygon=Polygon(context.get("girder_polygon",[]),holes=context.get("girder_holes",[]))
            if polygon.is_empty or not polygon.is_valid:raise ValueError("Local girder polygon is unavailable or invalid.")
            centre=number(context.get("contact_center_x_mm"));top_y=number(context.get("contact_top_y_mm"))
            a=number(cfg.get("row_spacing_mm"))
            if not all(math.isfinite(v) for v in (centre,top_y,a)) or a<=0:
                raise ValueError("Actual U-leg centre spacing and interface location are needed to check the bonded leg path.")
            xmin,_,xmax,_=polygon.bounds
            interface=LineString([(xmin-1,top_y),(xmax+1,top_y)])
            free_edges=polygon.boundary.difference(interface)
            lines=[LineString([(centre+sign*a/2,top_y),(centre+sign*a/2,top_y-bottom)]) for sign in (-1,1)]
            available=min(line.distance(free_edges) if polygon.covers(line) else 0. for line in lines)
            required=cover+db/2
            checks["bonded_leg_concrete_cover"]={"available_mm":available,"required_mm":required,
                "dc":required/available if available>0 else None,"adequate":available+1e-7>=required}
        except (ValueError,TypeError) as exc:
            result["reasons"].append(str(exc))
    failed = [k for k,v in checks.items() if not v["adequate"]]
    result["reasons"].extend("Insufficient " + k for k in failed)
    if failed: result["status"] = "FAIL"
    elif not result["reasons"] and len(checks)==7:
        result.update(ready=True, status="DIMENSION CHECKS MET")
    return result


def solve_mechanism(*, width_mm, leg_spacing_mm, avf_mm2_per_m, fy_MPa,
                    fc_weaker_MPa, surface_key, qx_kN_per_m, qy_kN_per_m,
                    n_kN_per_m, mx_kNm_per_m, cells=64):
    """Radial load factor for one joint action vector per metre of member.

    t_i: developed tie forces, c_j: compression-only contact, s_j: friction.
    sum(t)-sum(c)=lambda*n; sum(y*t)-sum(y*c)=lambda*mx;
    sum(s)=lambda*hypot(qx,qy); 0<=s_j<=mu*c_j and concrete shear caps.
    The SAME tie forces supply opening/roll equilibrium and friction clamping.
    No cohesion, externally assumed Pc, bar bending/shear or kinematic fit.
    """
    vals = list(map(number, (width_mm, leg_spacing_mm, avf_mm2_per_m, fy_MPa,
                            fc_weaker_MPa,qx_kN_per_m,qy_kN_per_m,n_kN_per_m,mx_kNm_per_m)))
    b,a,avf,fy,fc,qx,qy,n,m = vals
    if not all(math.isfinite(v) for v in vals) or not all(v>0 for v in vals[:5]):
        raise ValueError("Complete finite joint actions and positive geometry/material/steel data are required.")
    if a>=b or not isinstance(cells,int) or isinstance(cells,bool) or not 8<=cells<=512:
        raise ValueError("The symmetric leg rows must lie inside contact width; use 8–512 contact strips.")
    if surface_key not in SURFACE_PRESETS:
        raise ValueError("Specify a supported interface surface condition.")
    from scipy.optimize import linprog
    import numpy as np
    mu = surface_preset(surface_key).mu
    const = surface_preset(surface_key).constants_si(lightweight=False)
    dx = b/cells
    y = np.linspace(-b/2+dx/2,b/2-dx/2,cells)
    tie_cap = .90*avf*min(fy,INTERFACE_FY_CAP_MPA)/2/1000
    contact_cap = .70*.85*fc*dx  # kN in a 1000-mm design strip; no area enhancement
    shear_cap = .90*min(const["K1"]*fc,const["K2_MPa"])*dx
    shear = math.hypot(qx,qy)
    if max(abs(n),abs(m),shear)<=1e-12:
        return {"ready":True,"capacity_factor":None,"utilization":0.,"mechanism":"ZERO ACTIONS",
                "tie_capacity_each_kN_per_m":tie_cap,"cohesion_MPa":0.,"equilibrium_residual":0.,
                "tie_forces_kN_per_m":[0.,0.],"contact_kN_per_m":0.,"friction_kN_per_m":0.}
    # Variables: 2 ties, cells contact forces, cells friction forces, lambda.
    size = 3+2*cells
    obj = np.zeros(size); obj[-1] = -1.
    eq = np.zeros((3,size))
    eq[0,:2]=1.;eq[0,2:2+cells]=-1.;eq[0,-1]=-n
    eq[1,:2]=[-a/b,a/b];eq[1,2:2+cells]=-y/(b/2);eq[1,-1]=-m*1000/(b/2)
    eq[2,2+cells:-1]=1.;eq[2,-1]=-shear
    ub = np.zeros((cells+1,size))
    for j in range(cells):ub[j,2+j]=-mu;ub[j,2+cells+j]=1.
    # Pc=0 basis: external normal compression cannot silently become friction
    # credit. Opening/roll still consumes the same developed tie capacities.
    ub[-1,:2]=-mu;ub[-1,2+cells:-1]=1.
    bounds = [(0.,tie_cap)]*2+[(0.,contact_cap)]*cells+[(0.,shear_cap)]*cells+[(0.,None)]
    fit = linprog(obj,A_ub=ub,b_ub=np.zeros(cells+1),A_eq=eq,b_eq=np.zeros(3),bounds=bounds,method="highs")
    if not fit.success or fit.status!=0 or fit.x is None:
        return {"ready":False,"reason":"Joint equilibrium solver did not return a verified optimum: "+str(fit.message)}
    v = fit.x
    residual = float(np.max(np.abs(eq@v)))
    violation = max(float(np.max(ub@v)), max(-float(z) for z in v),
        max(float(z)-upper for z,(_,upper) in zip(v,bounds) if upper is not None))
    scale = max(1.,float(np.max(np.abs(v))),abs(float(v[-1])*n),abs(float(v[-1])*m*1000/(b/2)))
    if not np.all(np.isfinite(v)) or max(residual,violation)>1e-7*scale:
        return {"ready":False,"reason":"Joint equilibrium / yield constraints exceed the numerical acceptance tolerance."}
    lam = max(0.,float(v[-1]))
    dc = 1/lam if lam>1e-12 else None
    t,c,s = v[:2],v[2:2+cells],v[2+cells:-1]
    return {"ready":True,"capacity_factor":lam,"utilization":dc,
        "mechanism":"WITHIN IDEALIZED MECHANISM" if lam>=1-1e-7 else "EXCEEDS IDEALIZED MECHANISM",
        "tie_capacity_each_kN_per_m":tie_cap,"tie_forces_kN_per_m":t.tolist(),
        "contact_kN_per_m":float(c.sum()),"friction_kN_per_m":float(s.sum()),
        "normal_reconstructed_kN_per_m":float(t.sum()-c.sum()),
        "roll_reconstructed_kNm_per_m":float(np.dot([-a/2,a/2],t)-np.dot(y,c))/1000,
        "active_contact_width_mm":float((c>1e-8).sum()*dx),
        "max_contact_MPa":float(c.max()/dx),"cohesion_MPa":0.,
        "equilibrium_residual":residual,"yield_constraint_violation":max(0.,violation),
        "contact_cells":cells,"contact_y_mm":y.tolist(),"contact_forces_kN_per_m":c.tolist(),
        "friction_forces_kN_per_m":s.tolist(),
        "basis":"Equilibrium screening model; phi_tie=0.90, phi_contact=0.70, nominal contact cap=0.85fc without bearing-area enhancement, phi_interface=0.90; c=0; no external normal-compression friction credit (Pc=0); normal opening n>0; moments at interface centre; all actions scaled together",
    }


def evaluate(cfg, zone, context, actions, *, declared_anchored):
    """All outcomes retain REVIEW for composite design, including zero actions."""
    out = {"status":"REVIEW","scope":SCOPE,"anchorage":{},"mechanism":{},"reasons":[]}
    if not zone:
        out["reasons"].append("No complete dowel zone covers this station; no I-stirrup fallback.");return out
    from .igird_dowel_detail35 import resolve
    cfg = resolve(cfg, slab_thickness_mm=context.get("slab_thickness_mm"), db_mm=zone.get("Diameter_mm"))
    anch = anchorage(cfg,zone,context);out["anchorage"]=anch
    out["reasons"].extend(anch["reasons"])
    if not declared_anchored:out["reasons"].append("The existing connector anchorage declaration is unresolved.")
    if number(zone.get("Legs"))!=2:out["reasons"].append("This joint model requires one symmetric U-dowel with exactly two crossing legs per set.")
    a,b,db = map(number,(cfg.get("row_spacing_mm"),context.get("width_mm"),zone.get("Diameter_mm")))
    cover = number(cfg.get("cover_required_mm"))
    if not all(math.isfinite(v) and v>0 for v in (a,b,db,cover)) or a+db+2*cover>b+1e-8:
        out["reasons"].append("Enter actual transverse leg spacing within the contact width and required clear cover; the 220-mm hook dimension is not a lever arm.")
    for name in ACTION_COLUMNS:
        value=actions.get(name)
        if name in {"Case","Source"}:
            if value is None or str(value).strip().lower() in {"","nan","none"}:
                out["reasons"].append("Enter the joint-action "+name+"; Girder Tu is not an interface-action source.")
        elif not math.isfinite(number(value)):
            out["reasons"].append("Missing "+name+"; unknown joint actions are not zero.")
    x = number(actions.get("Station x (m)"))
    start,end=number(context.get("start_m")),number(context.get("end_m"))
    if not all(math.isfinite(v) for v in (start,end,x)) or end<=start or not start-1e-9<=x<=end+1e-9:
        out["reasons"].append("A joint station inside the known physical member domain is required.")
    if out["reasons"]:return out
    try:
        mechanism=solve_mechanism(width_mm=b,leg_spacing_mm=a,avf_mm2_per_m=zone["Avf_mm2_per_m"],
            fy_MPa=zone["fy_MPa"],fc_weaker_MPa=min(context["fc_slab_MPa"],context["fc_girder_MPa"]),
            surface_key=context["surface_key"],**{name:actions[name] for name in ACTION_COLUMNS[2:6]})
        out["mechanism"]=mechanism
        if not mechanism["ready"]:out["reasons"].append(mechanism["reason"])
    except (ValueError,ImportError) as exc:
        out["reasons"].append(str(exc))
    return out


def build_review(settings, *, context_for_station, base_context, girder_zones):
    """Calculate only when explicitly called from Analysis; inputs remain read-only.

    Anchorage requirement rows do not assert longitudinal coverage. Exact zone
    boundaries produce separate candidate results, never a sum or a guessed
    selection based on Avf alone (different bars can govern development).
    """
    from .igird_interface_connectors import at_station, INDEPENDENT_DOWELS, LINKED_DOWELS
    cfg=config(settings)
    requirements=[]
    source=settings.get("connector_source")
    zones=cfg_zones=settings.get("dowel_zones",[]) if source==INDEPENDENT_DOWELS else girder_zones
    if not isinstance(zones,list): zones=[]
    for raw in zones:
        if not isinstance(raw,Mapping): continue
        r={"Dowel zone":str(raw.get("Zone") or "-"),"db mm":raw.get("Diameter_mm"),
           "fy MPa":raw.get("fy_MPa"),"Scope":"Length requirements only; no coverage/anchorage acceptance"}
        try:
            if base_context.get("normal_weight") is not True:raise ValueError("Known normal-weight basis required")
            if cfg.get("coating") not in {"uncoated","epoxy"}:
                for coating in ("uncoated","epoxy"):
                    req=development_requirements(db_mm=raw.get("Diameter_mm"),fy_MPa=raw.get("fy_MPa"),
                        fc_slab_MPa=base_context.get("fc_slab_MPa"),fc_girder_MPa=base_context.get("fc_girder_MPa"),coating=coating)
                    r["Slab ldh "+coating+" mm"]=req["hook_required_mm"]
                    r["Girder ld "+coating+" mm"]=req["straight_required_mm"]
                r.update({"Tail required mm":req["tail_required_mm"],"Bend required mm":req["bend_required_mm"]})
                raise ValueError("Coating is unknown: alternatives shown only; no steel credit.")
            req=development_requirements(db_mm=raw.get("Diameter_mm"),fy_MPa=raw.get("fy_MPa"),
                fc_slab_MPa=base_context.get("fc_slab_MPa"),fc_girder_MPa=base_context.get("fc_girder_MPa"),coating=cfg.get("coating"))
            r.update({"Slab ldh required mm":req["hook_required_mm"],"Girder ld required mm":req["straight_required_mm"],
                      "Tail required mm":req["tail_required_mm"],"Bend required mm":req["bend_required_mm"]})
            from .igird_dowel_detail35 import resolve
            detail = resolve(cfg, slab_thickness_mm=base_context.get("slab_thickness_mm"), db_mm=raw.get("Diameter_mm"))
            r.update({"B provided mm":detail.get("slab_ldh_available_mm"), "D specified mm":detail.get("hook_inside_bend_mm"),
                      "Bend source":detail.get("bend_mode", "Legacy provided dimension")})
        except ValueError as exc:r["Reason"]=str(exc)
        requirements.append(r)
    rows=[];traces=[]
    action_rows=cfg.get("action_rows",[])
    if not isinstance(action_rows,list): action_rows=[]
    for action in action_rows:
        if not isinstance(action,Mapping):
            rows.append({"Status":"REVIEW","Reason":"Invalid joint-action record"});continue
        x=number(action.get("Station x (m)"))
        try:
            context=dict(context_for_station(x))
        except (ValueError,TypeError,KeyError) as exc:
            rows.append({"Case":action.get("Case"),"Station x (m)":action.get("Station x (m)"),"Status":"REVIEW","Reason":str(exc)});continue
        girder_zone=context.pop("girder_zone",None)
        selected=at_station(settings,x_m=x,girder_zone=girder_zone)
        candidates=[selected]
        if source==INDEPENDENT_DOWELS and selected["ready"]:
            candidates=[at_station({**settings,"dowel_zones":[z]},x_m=x) for z in cfg_zones
                if isinstance(z,Mapping) and z.get("Active",True) and
                number(z.get("x_start_m"))-1e-9<=x<=number(z.get("x_end_m"))+1e-9]
        if source not in {INDEPENDENT_DOWELS,LINKED_DOWELS}:
            candidates=[{"ready":False,"zone":None,"reason":"Choose an explicit U-dowel source for this mechanism."}]
        for selected in candidates:
            out=evaluate(cfg,selected["zone"],context,action,
                declared_anchored=bool(settings.get("connectors_cross_and_anchored",False)))
            if not selected["ready"]:out["reasons"].append(selected["reason"])
            anchor,m=out["anchorage"],out["mechanism"]
            checks=anchor.get("checks",{})
            dc=[v["dc"] for v in checks.values() if v.get("dc") is not None]
            rows.append({"Case":action.get("Case"),"Station x (m)":action.get("Station x (m)"),
                "Status":"REVIEW","Mechanism":m.get("mechanism","INPUTS REQUIRED"),
                "Dowel zone":str((selected["zone"] or {}).get("Zone") or "-"),
                "Capacity factor":m.get("capacity_factor"),"Mechanism D/C":m.get("utilization"),
                "Anchorage":anchor.get("status","REVIEW"),"Anchorage dimension D/C":max(dc) if dc else None,
                "Contact width mm":context.get("width_mm"),"Leg centres mm":cfg.get("row_spacing_mm"),
                "Slab ldh required mm":anchor.get("hook_required_mm"),"Girder ld required mm":anchor.get("straight_required_mm"),
                "Source":action.get("Source"),"Reason":" | ".join(dict.fromkeys(out["reasons"])) or SCOPE})
            traces.append({"action":dict(action),"context":context,"zone":selected["zone"],"result":out})
    def safe(value):
        if isinstance(value,float) and not math.isfinite(value):return None
        if isinstance(value,Mapping):return {k:safe(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [safe(v) for v in value]
        return value
    return safe({"version":VERSION,"scope":SCOPE,"requirements":requirements,"rows":rows,"traces":traces,
            "missing_actions":not bool(action_rows)})
