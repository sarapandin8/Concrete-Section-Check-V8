"""Sparse equilibrium limits and compatible complementary-energy witness.

KKT checks prove only the explicitly declared spring / plastic-domain model.
In particular, associated contact-cone flow is dilatant and uncalibrated.
This module NEVER returns a production composite resistance or PASS.
"""
import math
import numpy as np
from scipy import sparse
from scipy.optimize import linprog
from dataclasses import replace

from .igird_joint37_model import VERSION,number


def system(model):
    nodes=np.asarray(model.nodes);B=model.B.tocsr();m=B.shape[1]
    if nodes.ndim!=2 or nodes.shape[1]!=3 or B.shape[0]!=3*len(nodes):raise ValueError('Invalid 3D equilibrium system.')
    if not np.isfinite(nodes).all() or not np.isfinite(B.data).all() or not np.isfinite(model.A.data).all():raise ValueError('Finite model data required.')
    if model.bounds.shape!=(m,2) or not np.isfinite(model.bounds).all() or np.any(model.bounds[:,0]>model.bounds[:,1]):raise ValueError('Finite ordered member bounds required.')
    if model.A.shape!=(len(model.limits),m) or not np.isfinite(model.limits).all():raise ValueError('Invalid shared resource matrix.')
    if len(model.end_nodes)<3 or len(set(model.end_nodes))!=len(model.end_nodes):raise ValueError('A rank-six loaded cut is required.')
    ends=[3*i+j for i in model.end_nodes for j in range(3)];fixed=set(model.fixed_dofs)
    if fixed&set(ends):raise ValueError('Loaded cut cannot be fixed.')
    free=[i for i in range(3*len(nodes)) if i not in fixed and i not in set(ends)]
    points=nodes[model.end_nodes];cut=np.zeros((6,len(ends)))
    for i,(_,y,z) in enumerate(points):
        cut[:3,3*i:3*i+3]=np.eye(3);cut[3:,3*i:3*i+3]=[[0,-z,y],[z,0,0],[-y,0,0]]
    L=max(1.,float(np.ptp(points[:,1])),float(np.ptp(points[:,2])));scale=np.array([1.,1.,1.,L,L,L])
    if np.linalg.matrix_rank(cut/scale[:,None])<6:raise ValueError('Loaded cut cannot carry all six actions.')
    E=sparse.vstack((B[free],sparse.csr_matrix((cut@B[ends])/scale[:,None])),format='csr')
    # Keep force-like numerical units for all inequalities. This changes no
    # feasible set and makes the energy dual far better conditioned.
    amax=np.asarray(abs(model.A).max(axis=1).toarray()).ravel();row_scale=np.maximum(amax,1.)
    A=sparse.diags(1/row_scale)@model.A;b=model.limits/row_scale
    return {'E':E,'A':A.tocsr(),'b':b,'scale':scale,'free':free,'ends':ends,'cut':cut,'row_scale':row_scale}


def wrench(value):
    result=np.array([number(v) for v in value])
    if result.shape!=(6,):raise ValueError('All six actions must be explicitly finite.')
    return result


def base():
    return {'version':VERSION,'production_status':'UNVALIDATED — REVIEW','accepted_phiTn_Nmm':None,
        'accepted_VT_factor':None,'full_composite_Tn_Nmm':None}


def rhs(sys,h):return np.r_[np.zeros(len(sys['free'])),-h/sys['scale']]


def witness(model,sys,forces,expected,*,force_floor_N=1.,tolerance=2e-7):
    f=np.asarray(forces);E,A=sys['E'],sys['A'];r=rhs(sys,expected)
    eq_residual=E@f-r
    eq=float(np.max(abs(eq_residual)/np.maximum(force_floor_N,abs(E)@abs(f)+abs(r))))
    ub=float(np.max(np.maximum(0.,A@f-sys['b'])/np.maximum(force_floor_N,abs(A)@abs(f)+abs(sys['b'])))) if len(sys['b']) else 0.
    lo,hi=model.bounds.T
    bound=float(max(np.max(np.maximum(0.,lo-f)/np.maximum(1.,abs(lo))),np.max(np.maximum(0.,f-hi)/np.maximum(1.,abs(hi)))))
    internal=model.B@f;external=np.zeros(len(internal));external[sys['ends']]=-internal[sys['ends']]
    reaction=np.zeros_like(internal);reaction[model.fixed_dofs]=-internal[model.fixed_dofs]
    all_forces=(external+reaction).reshape(-1,3);force_residual=all_forces.sum(axis=0);moment_residual=np.cross(model.nodes,all_forces).sum(axis=0)
    magnitude=max(1.,float(abs(external).sum()+abs(reaction).sum()));length=max(1.,float(np.linalg.norm(model.nodes,axis=1).max()))
    global_error=max(float(abs(force_residual).max())/magnitude,float(abs(moment_residual).max())/(magnitude*length))
    # Independent free body: the slab has no supports / external loads.
    cross=[i for i,e in enumerate(model.elements) if e['component']=='joint'];slab=[i for i,c in enumerate(model.components) if c=='slab']
    slab_force=(model.B[:,cross]@f[cross]).reshape(-1,3)[slab]+external.reshape(-1,3)[slab]
    slab_res=slab_force.sum(axis=0);slab_moment=np.cross(model.nodes[slab],slab_force).sum(axis=0)
    slab_error=max(float(abs(slab_res).max())/magnitude,float(abs(slab_moment).max())/(magnitude*length))
    return {'verified':max(eq,ub,bound,global_error,slab_error)<tolerance,'equilibrium_relative':eq,'resource_relative':ub,
        'maximum_nodal_residual_N':float(abs(eq_residual).max()),'equilibrium_scale_floor_N':float(force_floor_N),
        'bounds_relative':bound,'global_relative':global_error,'slab_freebody_relative':slab_error,
        'rebuilt_wrench_N_Nmm':(sys['cut']@external[sys['ends']]).tolist(),'global_force_residual_N':force_residual.tolist(),
        'global_moment_residual_Nmm':moment_residual.tolist(),'slab_force_residual_N':slab_res.tolist(),'slab_moment_residual_Nmm':slab_moment.tolist()}


def interface_witness(model,forces,displacements=None):
    """Model-derived interface tractions. Never label these as CSI recovery."""
    forces=np.asarray(forces);planes=[];contacts=[];dowels=[];p=model.trace['pitch_mm'];oy=model.trace['origin']['target_y_mm']
    top=max(y for x,y in model.trace['girder_polygon_xy_mm']);z0=model.trace['origin'].get('target_local3_mm',0.)
    for k in range(3):
        cross_force=np.zeros_like(model.nodes)
        for i,e in enumerate(model.elements):
            if e['component']!='joint':continue
            # Both ends of each cross-component member belong to this plane.
            if abs(model.nodes[e['j'],0]-k*p)>1e-7:continue
            cross_force+=(model.B[:,i].toarray().ravel()*forces[i]).reshape(-1,3)
        ids=[i for i,c in enumerate(model.components) if c=='slab'];part=cross_force[ids]
        position=model.nodes[ids]-[k*p,top-oy,-z0]
        planes.append({'plane':k,'longitudinal_mm':k*p,'force_on_slab_N':part.sum(axis=0).tolist(),
            'moment_on_slab_Nmm':np.cross(position,part).sum(axis=0).tolist(),'source':'JOINT37 internal solution, not exported CSI interface forces'})
    for c in model.contacts:
        n=forces[c['normal']];sx=forces[c['qx']];sz=forces[c['qz']]
        row={**c,'compression_N':-float(n),'qx_N':float(sx),'qz_N':float(sz),'friction_circle_ratio':None if n>=-1e-8 else float(math.hypot(sx,sz)/(model.trace['mu']*(-n))) if model.trace['mu']>0 else None}
        if displacements is not None:
            d=displacements[c['slab_node']]-displacements[c['girder_node']]
            row.update(model_opening_mm=float(d[1]),model_slip_mm=float(math.hypot(d[0],d[2])))
        contacts.append(row)
    for d in model.dowels:
        force=float(forces[d['element']]);row={**d,'force_N':force,'utilization':force/max(d['single_leg_capacity_N'],1e-30)}
        db=model.trace['U_geometry']['db_mm'];count=d['area_mm2']/(math.pi*db*db/4)
        row.update(represented_bar_count=count,force_per_physical_leg_N=force/count)
        if displacements is not None:row['end_extension_mm']=float(displacements[d['slab_node'],1]-displacements[d['girder_node'],1])
        # Required face only. A standard hook check does not establish these
        # individual concrete strut-to-node face areas or splitting details.
        node=d.get('hook_node',d['slab_node']);incident=[]
        for i,e in enumerate(model.elements):
            if e['kind']=='concrete' and node in (e['i'],e['j']) and forces[i]<-1e-7:
                stress=model.trace['concrete_factor']*.45*model.trace['slab_fc_MPa']
                required=float(-forces[i])/stress
                incident.append({'member':model.labels[i],'compression_N':float(-forces[i]),
                    'required_equivalent_face_mm2':required,'required_face_per_represented_bar_mm2':required/count,
                    'available_face_mm2':None,'scope':'Demand only — actual effective nodal face is not established.'})
        row['incident_compression_struts']=incident;dowels.append(row)
    return {'plane_wrenches':planes,'contacts':contacts,'dowels':dowels,'status':'MODEL INTERFACE RESPONSE ONLY'}


def limit(model,h,*,mode='signed_torsion'):
    sys=system(model);h=wrench(h);held=h.copy();ray=np.zeros(6)
    if mode=='signed_torsion':held[3]=0.;ray[3]=(-1 if h[3]<0 else 1)*1e6
    elif mode=='VT_ray':held[1:4]=0.;ray[1:4]=h[1:4]
    else:raise ValueError('Unknown load path.')
    if not np.any(ray):return {**base(),'ready':False,'status':'NO V–T RAY','model_limit':None}
    E=sys['E'];r=rhs(sys,held);R=-rhs(sys,ray)
    # kN force variables avoid a 10^6 imbalance between N member variables
    # and a dimensionless load-ray column. Verify dual stationarity as well
    # as objective equality: equal objectives alone are insufficient.
    eq=sparse.hstack((E,sparse.csr_matrix((R/1000.)[:,None])),format='csr');ub=sparse.hstack((sys['A'],sparse.csr_matrix((len(sys['b']),1))),format='csr')
    obj=np.r_[np.zeros(E.shape[1]),-1.];bounds=[*map(tuple,model.bounds/1000.),(0.,None)]
    result=linprog(obj,A_ub=ub,b_ub=sys['b']/1000.,A_eq=eq,b_eq=r/1000.,bounds=bounds,method='highs',
        options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9})
    if not result.success:return {**base(),'ready':False,'status':'MODEL DOMAIN INFEASIBLE' if result.status==2 else 'NUMERICAL FAILURE','reason':str(result.message),'model_limit':None}
    f=result.x[:-1]*1000.;lam=max(0.,float(result.x[-1]));expected=held+lam*ray;checks=witness(model,sys,f,expected)
    dual=float((sys['b']/1000.)@result.ineqlin.marginals+(r/1000.)@result.eqlin.marginals)
    for (lo,hi),dl,du in zip(bounds,result.lower.marginals,result.upper.marginals):
        if lo is not None:dual+=lo*dl
        if hi is not None:dual+=hi*du
    gap=abs(-lam-dual)/max(1.,lam);checks['duality_relative']=gap
    stat=eq.T@result.eqlin.marginals+ub.T@result.ineqlin.marginals+result.lower.marginals+result.upper.marginals
    checks['dual_stationarity_relative']=float(np.max(abs(obj-stat)/np.maximum(1.,abs(obj)+abs(eq.T)@abs(result.eqlin.marginals)+abs(ub.T)@abs(result.ineqlin.marginals))))
    if not checks['verified'] or max(gap,checks['dual_stationarity_relative'])>2e-7:return {**base(),'ready':False,'status':'NUMERICAL VERIFICATION FAILED','checks':checks,'model_limit':None}
    return {**base(),'ready':True,'status':'CONDITIONAL MODEL LIMIT','mode':mode,'model_limit':lam,
        'model_T_limit_Nmm':lam*1e6 if mode=='signed_torsion' else None,'model_VT_factor':lam if mode=='VT_ray' else None,
        'force_wrench_N_Nmm':expected.tolist(),'checks':checks,'forces_N':f.tolist(),'interface':interface_witness(model,f)}


def _energy_state(model,h,*,maxiter=100000):
    """Minimum complementary energy in the SAME force/yield domain.

    Elastic extension=(f-f0)/k; total nodal extension=-B^T u. Their difference
    is associated plastic extension from active resource/cone/member bounds.
    The declared contact law contains dilation, not a measured bond-slip law.
    """
    sys=system(model);h=wrench(h);E,A=sys['E'],sys['A'];r=rhs(sys,h)
    feasible=linprog(np.zeros(E.shape[1]),A_ub=A,b_ub=sys['b']/1000.,A_eq=E,b_eq=r/1000.,bounds=list(map(tuple,model.bounds/1000.)),method='highs')
    if not feasible.success:return {**base(),'ready':False,'status':'ACTUAL ACTIONS OUTSIDE MODEL DOMAIN','reason':'No compatible state is reported for an infeasible force domain.'}
    k=np.asarray(model.stiffness)/1000.;f0=np.asarray(model.initial)/1000.;lo,hi=(model.bounds/1000.).T
    if not np.isfinite(k).all() or np.min(k)<=0:raise ValueError('Positive finite spring stiffnesses required.')
    try:import osqp
    except ImportError:return {**base(),'ready':False,'status':'COMPATIBILITY SOLVER UNAVAILABLE','reason':'Install the requirements OSQP 1.x dependency; LP results remain separate.'}
    ne=E.shape[0];na=A.shape[0];m=len(k)
    C=sparse.vstack((E,A,sparse.eye(m)),format='csc')
    lower=np.r_[r/1000.,np.full(na,-np.inf),lo];upper=np.r_[r/1000.,sys['b']/1000.,hi]
    escale=1/float(np.median(1/k))
    qp=osqp.OSQP();qp.setup(P=sparse.diags(escale/k,format='csc'),q=-escale*f0/k,A=C,l=lower,u=upper,
        verbose=False,polishing=True,polish_refine_iter=10,scaling=20,eps_abs=1e-9,eps_rel=1e-8,
        max_iter=int(maxiter),time_limit=25.,delta=1e-9)
    qp.warm_start(x=feasible.x)
    opt=qp.solve(raise_error=False)
    if opt.info.status_val not in (1,2) or opt.x is None or not np.isfinite(opt.x).all():
        return {**base(),'ready':False,'status':'COMPATIBILITY NOT CONVERGED','reason':str(opt.info.status),'iterations':int(opt.info.iter)}
    f=np.asarray(opt.x);y=np.asarray(opt.y)/escale;forces=f*1000.
    characteristic=max(1.,float(np.max(abs(E)@abs(forces)+abs(r))))
    checks=witness(model,sys,forces,h,force_floor_N=characteristic,tolerance=2e-6)
    primal=.5*float(np.sum((f-f0)**2/k));stress_dual=np.asarray(C.T@y).ravel()
    normal=y[ne+na:];mu=y[ne:ne+na]
    dual=float(f0@stress_dual-.5*np.sum(k*stress_dual**2)-y[:ne]@(r/1000.)-mu@(sys['b']/1000.)
        -np.maximum(normal,0.)@hi-np.minimum(normal,0.)@lo)
    gap=abs(primal-dual)/max(1.,primal)
    elastic=(f-f0)/k;stationarity=float(np.max(abs(elastic+stress_dual)/np.maximum(1.,abs(elastic)+abs(stress_dual))))
    checks.update(energy_duality_relative=gap,energy_stationarity_relative=stationarity,iterations=int(opt.info.iter),solver_version=osqp.__version__)
    if not checks['verified'] or gap>2e-6:
        return {**base(),'ready':False,'status':'COMPATIBILITY NOT CONVERGED','checks':checks,'reason':str(opt.info.status)}
    multiplier=y[:ne];u=np.zeros_like(model.nodes);u.reshape(-1)[sys['free']]=multiplier[:len(sys['free'])]
    cut_motion=multiplier[len(sys['free']):]/sys['scale'];translation=cut_motion[:3];rotation=cut_motion[3:]
    for node in model.end_nodes:
        position=np.array([0.,model.nodes[node,1],model.nodes[node,2]])
        u[node]=translation+np.cross(rotation,position)
    total=-np.asarray(model.B.T@u.ravel()).ravel()
    plastic=np.asarray(A.T@mu).ravel()+normal
    compat=float(np.max(abs(total-elastic-plastic)/np.maximum(1.,abs(total)+abs(elastic)+abs(plastic))))
    checks['compatibility_relative']=compat
    if max(compat,stationarity)>2e-6 or (len(mu) and np.min(mu)<-1e-7):return {**base(),'ready':False,'status':'KINEMATIC RECONSTRUCTION FAILED','checks':checks}
    return {**base(),'ready':True,'status':'ASSUMED-LAW COMPATIBLE STATE','checks':checks,'forces_N':forces.tolist(),
        'node_displacements_mm':u.tolist(),'total_extensions_mm':total.tolist(),'elastic_extensions_mm':elastic.tolist(),
        'plastic_extensions_mm':plastic.tolist(),'interface':interface_witness(model,forces,u),
        'law_scope':'Perfect embedded bond + elastic/plastic force bounds + associated (dilatant) friction. Not calibrated joint slip or structural acceptance.'}


def compatible_state(model,h,*,maxiter=100000):
    """Increment about a self-equilibrated post-loss prestress reference.

    Hold each supplied developed Pe at the reference, balance it in the
    GIRDER alone, then restore the U/slab. Do not apply Pe as external Nu or
    repeat elastic-shortening loss by treating final fpe as a free eigenforce.
    Material bounds must be nominal for this mechanical state calculation.
    """
    if not model.trace.get('nominal'):
        return {**base(),'ready':False,'status':'NOMINAL MATERIAL MODEL REQUIRED','reason':'Design supply factors are not constitutive material stress/strain laws.'}
    indices=[i for i,k in enumerate(model.kinds) if k=='prestress' and model.initial[i]>0]
    if indices:
        from .igird_joint37_model import without
        reference=without(model,'dowel','contact_normal','contact_shear','slab_transverse','slab_longitudinal')
        bounds=reference.bounds.copy()
        for i in indices:
            target=model.initial[i]
            if target>model.bounds[i,1]+1e-7:return {**base(),'ready':False,'status':'PRESTRESS REFERENCE BLOCKED','reason':'Known Pe exceeds the developed nominal tie ceiling; Pe is not reduced silently.'}
            bounds[i]=[target,target]
        reference=replace(reference,bounds=bounds,initial=np.zeros_like(reference.initial))
        prestress=_energy_state(reference,np.zeros(6),maxiter=maxiter)
        if not prestress['ready']:return {**base(),'ready':False,'status':'PRESTRESS REFERENCE BLOCKED','reference':prestress}
        forces=np.array(prestress['forces_N']);error=float(np.max(abs(forces[indices]-model.initial[indices])))
        ref={'status':'GIRDER-ONLY SELF-EQUILIBRATED REFERENCE','maximum_Pe_error_N':error,'checks':prestress['checks'],
            'stage_scope':'Post-loss Pe retained; creep/shrinkage restraint and the full casting history are not reconstructed.'}
        model=replace(model,initial=forces)
    else:ref={'status':'ZERO PRESTRESS REFERENCE','maximum_Pe_error_N':0.}
    result=_energy_state(model,h,maxiter=maxiter);result['prestress_reference']=ref
    return result
