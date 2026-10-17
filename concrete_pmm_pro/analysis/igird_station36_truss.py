"""One-station 3D truss idealization, not composite acceptance.

All six section resultants act together. Steel is allocated once in nodal
equilibrium; concrete compression members share nonoverlapping volume budgets.
The volume trace interaction and end-traction distribution are declared model
assumptions. LP duality verifies the idealized optimization, not concrete
cracking, bond/slip, ductility, actual nodal-zone strength or structural validity.

Coordinates: (longitudinal, CSI local 2, CSI local 3), mm. N, N-mm throughout.
"""
from dataclasses import dataclass
import math
import numpy as np
from scipy.optimize import linprog

VERSION = "IGIRDER.STATION36"
PRODUCTION_VALIDATED = False


@dataclass
class Model:
    nodes: np.ndarray
    matrix: np.ndarray
    bounds: list
    labels: list
    kinds: list
    resource_matrix: np.ndarray
    resource_limits: np.ndarray
    resource_labels: list
    fixed_dofs: list
    end_nodes: list
    end_weights: list
    trace: dict


def _number(v):
    try:n=float(v)
    except (ValueError,TypeError):raise ValueError('Finite numeric input required.') from None
    if isinstance(v,bool) or not math.isfinite(n):
        raise ValueError("Finite numeric input required; booleans are not numbers.")
    return n


def end_tractions(points, wrench, weights=None):
    """Area-weighted minimum-norm cut tractions; preserve all six resultants.

    This boundary loading pattern is a submodel assumption, not a recovery of
    CSiBridge Beam/Slab interface forces. Wrench=(P,V2,V3,T,physical M2,M3).
    """
    points=np.asarray(points,dtype=float);w=np.array([_number(v) for v in wrench])
    if points.ndim!=2 or points.shape[1]!=3 or len(points)<3 or len(w)!=6 or not np.isfinite(points).all():
        raise ValueError("A finite 3D cut and six actions are required.")
    n=len(points);a=np.zeros((6,3*n))
    for i,(_,y,z) in enumerate(points):
        a[:3,3*i:3*i+3]=np.eye(3)
        a[3:,3*i:3*i+3]=[[0,-z,y],[z,0,0],[-y,0,0]]
    length=max(1.,float(np.ptp(points[:,1])),float(np.ptp(points[:,2])))
    scales=np.array([1,1,1,length,length,length]);c=a/scales[:,None]
    weights=np.ones(n) if weights is None else np.asarray(weights,dtype=float)
    if len(weights)!=n or not np.isfinite(weights).all() or np.min(weights)<=0:
        raise ValueError("Positive cut weights required.")
    diag=np.repeat(weights/weights.sum(),3)
    gram=(c*diag)@c.T
    if np.linalg.matrix_rank(gram)<6:raise ValueError("Cut geometry cannot carry all six resultants.")
    forces=diag*(c.T@np.linalg.solve(gram,w/scales))
    residual=a@forces-w
    if np.max(np.abs(residual)/np.maximum(1.,np.abs(a)@np.abs(forces)+np.abs(w)))>1e-9:
        raise ValueError("Cut traction reconstruction failed.")
    return forces.reshape(n,3),a@forces


def solve(model, held_wrench, *, torsion_sign=1., torque_unit_Nmm=1e6):
    """Maximize signed T with P,V2,V3,M2,M3 held. No V3/M2 omission.

    The signed-T domain is optimized directly: an infeasible T=0 alone would
    not prove infeasibility at another T. Witnesses use actual internal units.
    """
    nodes=np.asarray(model.nodes,dtype=float);B=np.asarray(model.matrix,dtype=float)
    if nodes.ndim!=2 or nodes.shape[1]!=3 or not np.isfinite(nodes).all() or B.ndim!=2 or B.shape[0]!=3*len(nodes) or not np.isfinite(B).all():raise ValueError("Invalid equilibrium matrix / nodes.")
    h=np.array([_number(x) for x in held_wrench])
    torque_unit_Nmm=_number(torque_unit_Nmm);torsion_sign=_number(torsion_sign)
    if len(h)!=6 or torque_unit_Nmm<=0 or torsion_sign not in (-1.,1.):raise ValueError("Six actions and a signed torque direction are required.")
    h[3]=0.
    if not model.end_nodes or len(set(model.end_nodes))!=len(model.end_nodes) or any(i<0 or i>=len(nodes) for i in model.end_nodes):raise ValueError("Invalid end node indices.")
    if len(set(model.fixed_dofs))!=len(model.fixed_dofs) or any(i<0 or i>=3*len(nodes) for i in model.fixed_dofs):raise ValueError("Invalid supports.")
    points=nodes[model.end_nodes]
    # Rigid end-section boundary: optimize the end nodal tractions subject to
    # their EXACT six resultants, rather than imposing an arbitrary traction
    # pattern. Internal nodes retain every individual equilibrium equation.
    end_tractions(points,h,model.end_weights)  # rank / geometry validation only
    end_dofs=[3*i+j for i in model.end_nodes for j in range(3)]
    if set(end_dofs)&set(model.fixed_dofs):raise ValueError("Loaded end cannot also be fixed.")
    free=np.array([i for i in range(3*len(nodes)) if i not in set(model.fixed_dofs)|set(end_dofs)],dtype=int)
    cut=np.zeros((6,len(end_dofs)))
    for i,(_,y,z) in enumerate(points):
        cut[:3,3*i:3*i+3]=np.eye(3)
        cut[3:,3*i:3*i+3]=[[0,-z,y],[z,0,0],[-y,0,0]]
    length=max(1.,float(np.ptp(points[:,1])),float(np.ptp(points[:,2])))
    scale=np.array([1.,1.,1.,length,length,length])
    beq=np.vstack((B[free],(cut@B[end_dofs])/scale[:,None]))
    fixed_rhs=np.r_[np.zeros(len(free)),-h/scale]
    signed=np.zeros(len(fixed_rhs));signed[len(free)+3]=torsion_sign*torque_unit_Nmm/length
    A=np.asarray(model.resource_matrix,dtype=float);limits=np.asarray(model.resource_limits,dtype=float)
    m=B.shape[1]
    if len(model.bounds)!=m or len(model.labels)!=m or len(model.kinds)!=m or len(model.resource_labels)!=len(limits) or A.shape!=(len(limits),m) or not np.isfinite(A).all() or not np.isfinite(limits).all() or np.any(limits<0):
        raise ValueError("Invalid force bounds / shared resource matrix.")
    if any(lo is None or hi is None or not math.isfinite(lo+hi) or lo>hi for lo,hi in model.bounds):
        raise ValueError("Finite ordered member bounds are required.")
    base={"version":VERSION,"production_status":"UNVALIDATED — REVIEW","accepted_phiTn_Nmm":None,
        "accepted_VT_factor":None,"full_composite_Tn_Nmm":None,"definition":"Signed truss model limit with all other five section actions held; not nominal full-composite Tn.","trace":model.trace}
    eq=np.column_stack((beq,signed));ub=np.column_stack((A,np.zeros(len(limits))))
    obj=np.zeros(m+1);obj[-1]=-1.
    bounds=[*model.bounds,(0.,None)]
    r=linprog(obj,A_ub=ub,b_ub=limits,A_eq=eq,b_eq=fixed_rhs,bounds=bounds,method="highs")
    if not r.success:return {**base,"ready":False,"status":"SIGNED T DOMAIN INFEASIBLE" if r.status==2 else "MODEL BLOCKED",
        "reason":"No admissible signed T>=0 with the five held actions in this idealization; no zero resistance is fabricated." if r.status==2 else str(r.message),"model_T_limit_Nmm":None}
    x=r.x;rhs=fixed_rhs
    eqerr=float(np.max(np.abs(eq@x-rhs)/np.maximum(1.,np.abs(eq)@np.abs(x)+np.abs(rhs))))
    uberr=float(np.max(np.maximum(0.,ub@x-limits)/np.maximum(1.,np.abs(ub)@np.abs(x)+np.abs(limits)))) if len(limits) else 0.
    berr=max([0.]+[max(0.,lo-v)/max(1.,abs(lo)) for v,(lo,hi) in zip(x,bounds)]+[max(0.,v-hi)/max(1.,abs(hi)) for v,(lo,hi) in zip(x,bounds) if hi is not None])
    dual=float(limits@r.ineqlin.marginals+rhs@r.eqlin.marginals)
    dual+=sum(lo*d for (lo,hi),d in zip(bounds,r.lower.marginals) if lo is not None)
    dual+=sum(hi*d for (lo,hi),d in zip(bounds,r.upper.marginals) if hi is not None)
    gap=abs(float(obj@x)-dual)/max(1.,abs(float(obj@x)))
    if max(eqerr,uberr,berr,gap)>1e-7 or not np.isfinite(x).all():
        return {**base,"ready":False,"status":"NUMERICAL VERIFICATION FAILED","reason":"Equilibrium / resource / bound / duality check failed.","model_T_limit_Nmm":None}
    internal=B@x[:-1];total_ext=np.zeros(3*len(nodes));total_ext[end_dofs]=-internal[end_dofs]
    reaction=np.zeros_like(internal);reaction[model.fixed_dofs]=-internal[model.fixed_dofs]
    global_forces=total_ext.reshape(-1,3)+reaction.reshape(-1,3)
    global_moment=np.cross(nodes,global_forces).sum(axis=0)
    force_scale=max(1.,float(np.abs(total_ext).sum()+np.abs(reaction).sum()))
    moment_scale=max(1.,force_scale*float(np.max(np.linalg.norm(nodes,axis=1))))
    global_error=max(float(np.max(np.abs(global_forces.sum(axis=0))))/force_scale,float(np.max(np.abs(global_moment)))/moment_scale)
    if global_error>1e-7:
        return {**base,"ready":False,"status":"NUMERICAL VERIFICATION FAILED","reason":"Independent global force/moment equilibrium failed.","model_T_limit_Nmm":None}
    active=[]
    for i,(lo,hi) in enumerate(model.bounds):
        if (abs(x[i]-lo)<1e-7*max(1.,abs(lo)) and abs(r.lower.marginals[i])>1e-10) or (abs(x[i]-hi)<1e-7*max(1.,abs(hi)) and abs(r.upper.marginals[i])>1e-10):active.append(model.labels[i])
    active += [label for label,slack,deriv in zip(model.resource_labels,limits-A@x[:-1],r.ineqlin.marginals) if abs(slack)<1e-7*max(1.,float(np.max(limits))) and abs(deriv)>1e-10]
    return {**base,"ready":True,"status":"MODEL LIMIT ONLY","model_T_limit_Nmm":float(x[-1])*torque_unit_Nmm,
        "torsion_sign":torsion_sign,"held_wrench_N_Nmm":h.tolist(),"member_forces_N":x[:-1].tolist(),
        "active_limits":active,"equilibrium_relative":eqerr,"resource_relative":uberr,"bounds_relative":berr,"duality_relative":gap,"global_relative":global_error,
        "end_tractions_N":total_ext[end_dofs].reshape(-1,3).tolist(),"rebuilt_wrench_N_Nmm":(cut@total_ext[end_dofs]).tolist(),
        "support_reactions_N":reaction.reshape(-1,3).tolist(),"global_force_residual_N":global_forces.sum(axis=0).tolist(),
        "global_moment_residual_Nmm":global_moment.tolist(),"resource_utilization":((A@x[:-1])/np.maximum(limits,1e-30)).tolist()}


def core_cage(polygon, *, cover_mm, db_mm, spacing_mm, fy_MPa, fc_MPa, longitudinal, origin_y_mm=0., origin_local3_mm=0., nominal=False):
    """Prismatic closed-girder-hoop benchmark, with actual embedded steel points.

    Does NOT create slab side ties, a U-to-mat transfer, or joint reactions.
    Ring outline is derived from the existing automatic hoop geometry policy.
    End sections receive half a tributary hoop supply; internal section one.
    Nonoverlapping clipped Voronoi cells allocate the concrete compression
    volume once, shared by axial and BOTH helical diagonal member families.
    """
    from shapely.geometry import Polygon,Point,MultiPoint
    from shapely.ops import voronoi_diagram
    from shapely import constrained_delaunay_triangles
    origin_y_mm=_number(origin_y_mm);origin_local3_mm=_number(origin_local3_mm)
    vals=[_number(v) for v in (cover_mm,db_mm,spacing_mm,fy_MPa,fc_MPa)]
    cover,db,s,fy,fc=vals
    if min(vals)<=0 or polygon.geom_type!="Polygon" or not polygon.is_valid or polygon.is_empty or polygon.interiors:
        raise ValueError("Positive concrete/hoop inputs and one solid valid girder polygon are required.")
    inset=polygon.buffer(-(cover+db/2),join_style=2)
    if inset.geom_type!="Polygon" or inset.is_empty:raise ValueError("Hoop inset is not a single valid polygon.")
    vertices=list(inset.exterior.coords)[:-1]
    lengths=[math.dist(a,b) for a,b in zip(vertices,vertices[1:]+vertices[:1])]
    pitch=min(300.,min(lengths)/math.tan(math.radians(35)))
    ring=[]
    for a,b,e in zip(vertices,vertices[1:]+vertices[:1],lengths):
        count=max(1,math.ceil(e/(pitch*math.tan(math.radians(60)))))
        ring.extend([(a[0]+(b[0]-a[0])*i/count,a[1]+(b[1]-a[1])*i/count) for i in range(count)])
    n=len(ring);planes=3
    ringpoly=Polygon(ring)
    cells=voronoi_diagram(MultiPoint(ring),envelope=polygon.envelope.buffer(max(polygon.bounds[2]-polygon.bounds[0],polygon.bounds[3]-polygon.bounds[1])))
    areas=np.zeros(n)
    for cell in cells.geoms:
        selected=min(range(n),key=lambda i:cell.distance(Point(ring[i])))
        areas[selected]+=cell.intersection(polygon).area
    if np.min(areas)<=0 or abs(areas.sum()-polygon.area)>1e-7*polygon.area:
        raise ValueError("Concrete cells do not form a nonoverlapping full-area partition.")
    nodes=np.array([(k*pitch,y-origin_y_mm,x-origin_local3_mm) for k in range(planes) for x,y in ring])
    columns=[];bounds=[];labels=[];kinds=[];resource_columns=[]
    steel_factor,concrete_factor=(1.,1.) if nominal else (.9,.7)
    stress=concrete_factor*.45*fc
    resource_limits=np.tile(areas*pitch*stress,planes-1)
    def add(label,kind,start,end,lo,hi,resource=None):
        col=np.zeros(3*len(nodes));p0=sum(nodes[i]*w for i,w in start.items());p1=sum(nodes[i]*w for i,w in end.items())
        length=float(np.linalg.norm(p1-p0));unit=(p1-p0)/length
        for i,w in start.items():col[3*i:3*i+3]+=w*unit
        for i,w in end.items():col[3*i:3*i+3]-=w*unit
        columns.append(col);bounds.append((float(lo),float(hi)));labels.append(label);kinds.append(kind)
        rc=np.zeros(len(resource_limits))
        if resource:
            for i,weight in resource.items():rc[i]=-length*weight
        resource_columns.append(rc)
    angles=[]
    for k in range(planes):
        weight=.5 if k in (0,planes-1) else 1.
        cap=steel_factor*math.pi*db*db/4*fy*pitch/s*weight
        for i in range(n):add(f"hoop {k}/{i}","hoop",{k*n+i:1.},{k*n+(i+1)%n:1.},0.,cap)
    for k in range(planes-1):
        for i in range(n):
            add(f"concrete axial {k}/{i}","concrete",{k*n+i:1.},{(k+1)*n+i:1.},-stress*areas[i],0.,{k*n+i:1.})
            j=(i+1)%n;e=math.dist(ring[i],ring[j]);angle=math.degrees(math.atan2(e,pitch));angles.append(angle)
            if not 25.-1e-8<=angle<=65.+1e-8:raise ValueError("Diagonal/tie angle is outside the declared 25–65 degree model range.")
            length=math.hypot(e,pitch);cap=2*stress*min(areas[i],areas[j])*pitch/length
            for a,b in ((i,j),(j,i)):
                add(f"concrete diagonal {k}/{a}/{b}","concrete",{k*n+a:1.},{(k+1)*n+b:1.},-cap,0.,{k*n+i:.5,k*n+j:.5})
    triangles=list(constrained_delaunay_triangles(ringpoly).geoms)
    ledger=[]
    for bar in longitudinal:
        x,y,cap=(_number(bar[k]) for k in ("x_mm","y_mm","capacity_N"))
        if cap<0:raise ValueError("Steel force capacity cannot be negative.")
        p=Point(x,y);weights=None
        for tri in triangles:
            if tri.buffer(1e-7).covers(p):
                xyz=np.array(list(tri.exterior.coords)[:3]);w=np.linalg.solve(np.vstack((xyz.T,np.ones(3))),[x,y,1.])
                ids=[min(range(n),key=lambda i:math.dist(ring[i],a)) for a in xyz]
                if min(w)<-1e-7 or any(math.dist(ring[i],a)>1e-5 for i,a in zip(ids,xyz)):continue
                weights={i:float(max(0.,v)) for i,v in zip(ids,w)};break
        record={**bar,"embedded":weights is not None,"scope":"Girder-core benchmark only"};ledger.append(record)
        if weights is None or cap==0:continue
        # Barycentric forces preserve the actual bar x/y and all section moments.
        for k in range(planes-1):
            add(str(bar["label"])+f" / bay {k}",str(bar.get("kind","longitudinal")),
                {k*n+i:w for i,w in weights.items()},{(k+1)*n+i:w for i,w in weights.items()},0.,steel_factor*cap)
    trace={"model_scope":"Girder-core 3D cage benchmark; NO slab/U-dowel resistance added", "ring_xy_mm":ring,
        "origin_y_mm":origin_y_mm,"origin_local3_mm":origin_local3_mm,
        "pitch_mm":pitch,"planes":planes,"hoop_Ao_mm2":ringpoly.area,"hoop_ph_mm":ringpoly.length,
        "concrete_cell_areas_mm2":areas.tolist(),"concrete_area_mm2":polygon.area,"concrete_efficiency":.45,
        "steel_factor":steel_factor,"concrete_factor":concrete_factor,"nominal":nominal,
        "strut_angle_min_deg":min(angles),"strut_angle_max_deg":max(angles),"longitudinal_ledger":ledger,
        "limitations":["Rigid end sections and derived cage are model assumptions, not a recovered CSiBridge interface state.",
            "Concrete compression trace/volume interaction is an assumed model domain, not a calibrated cracked-concrete constitutive law or a proven safe bound for the structure.",
            "Rigid-plastic nodal equilibrium/LP duality does not establish bond-slip, crack-width or finite-strain compatibility.",
            "This is a local prismatic cross-section idealization; development bounds are evaluated at the selected cut, not a recovered finite-length D-region.",
            "Barycentric bar embedding preserves forces/moments but does not validate local bond nodes or initial prestress strain compatibility.",
            "Actual hoop bending, anchorage zones, development, confinement, D-regions and structural validation remain separate."]}
    return Model(nodes,np.array(columns).T,bounds,labels,kinds,np.array(resource_columns).T,resource_limits,
        [f"shared concrete cell {k}/{i}" for k in range(planes-1) for i in range(n)],list(range(3*n)),
        list(range((planes-1)*n,planes*n)),areas.tolist(),trace)
