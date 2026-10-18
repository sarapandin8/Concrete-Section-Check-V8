"""Independent physical-unit audit of a stored nominal LP witness.

No LP matrix, dual variables or optimization code is used here. Balances and
physical resource ceilings are re-evaluated from the saved resultants. This is
software verification of the declared model, NOT validation of its stress field.
"""
import math

VERSION = 'IGIRDER.FULLVT48.witness-audit'


def audit_witness(s, result, *, vu_N, tu_Nmm, mu_Nmm=0., nu_tension_N=0., tolerance=2e-7):
    s.validate()
    if not result.get('ready') or result.get('capacity_factor') is None:
        return {'status':'NOT AVAILABLE','structural_validation':False}
    lam=float(result['capacity_factor'])
    vi,vu,ti,tu=[float(result[k]) for k in ('core_V_N','U_V_N','core_T_Nmm','U_T_Nmm')]
    qi,qu=ti/(2*s.core_ao_mm2),tu/(2*s.u_ao_mm2)
    forces=list(map(float,result['U_force_each_N_per_mm']))
    y=list(map(float,result['contact_y_mm']))
    c=list(map(float,result['contact_compression_N_per_mm']))
    q=list(map(float,result['contact_qx_N_per_mm']))
    if not len(y)==len(c)==len(q) or len(forces)!=2 or not y:
        return {'status':'FAIL','reason':'Witness dimensions','structural_validation':False}
    if not all(math.isfinite(v) for v in (lam,vi,vu,ti,tu,vu_N,tu_Nmm,mu_Nmm,nu_tension_N,*forces,*y,*c,*q)):
        return {'status':'FAIL','reason':'Nonfinite witness/actions','structural_validation':False}
    errors={}
    def balance(name,a,b,terms=()):
        errors[name]=abs(a-b)/max(1.,abs(a),abs(b),sum(abs(t) for t in terms))
    def bound(name,demand,capacity):
        errors[name]=max(0.,demand-capacity)/max(1.,abs(demand),abs(capacity))
    cot=s.cot_theta
    balance('V resultant',vi+vu,lam*abs(vu_N))
    balance('T resultant',ti+tu,lam*abs(tu_Nmm))
    balance('joint normal resultant',sum(c),sum(forces))
    balance('joint normal moment',s.u_leg_spacing_mm*(forces[1]-forces[0]),2*sum(a*b for a,b in zip(y,c)),
        [2*a*b for a,b in zip(y,c)])
    balance('joint longitudinal shear',sum(q),vu/s.u_dv_mm,q)
    balance('joint torque couple',-sum(a*b for a,b in zip(y,q)),s.u_leg_spacing_mm*qu,
        [a*b for a,b in zip(y,q)])
    bound('I leg V+T',vi/(2*s.core_dv_mm*cot)+qi/cot,s.core_leg_N_per_mm)
    for side,force in enumerate(forces):
        bound(f'U {side+1} V+T',vu/(2*s.u_dv_mm*cot)+qu/cot,force)
        bound(f'U {side+1} force ceiling',force,s.u_leg_N_per_mm)
    bound('slab closure',qu/cot,s.slab_closing_N_per_mm)
    bound('one concrete budget',vi/(2*s.core_dv_mm)+vu/(2*s.u_dv_mm)+qi+qu,s.diagonal_q_N_per_mm)
    inc=(.5*(vi+vu)+.45*(s.core_ph_mm*qi+s.u_ph_mm*qu))*cot
    held=mu_Nmm/s.u_dv_mm
    bound('bottom longitudinal',inc+held+.5*nu_tension_N,s.bottom_longitudinal_N)
    bound('top longitudinal',inc-held+.5*nu_tension_N,s.top_longitudinal_N)
    bound('I upper longitudinal',(.5*vi+.45*s.core_ph_mm*qi)*cot-held+.5*nu_tension_N,s.top_girder_longitudinal_N)
    bound('U slab longitudinal',(.5*vu+.45*s.u_ph_mm*qu)*cot,s.top_slab_longitudinal_N)
    dy=s.contact_width_mm/len(y)
    for i,(normal,shear) in enumerate(zip(c,q)):
        bound(f'contact {i} compression',normal,s.contact_MPa*dy)
        bound(f'contact {i} tension',-normal,0.)
        bound(f'contact {i} friction',abs(shear),s.mu*normal)
        bound(f'contact {i} shear cap',abs(shear),s.interface_MPa*dy)
    for key,value in [('lambda',lam),('VI',vi),('VU',vu),('qI',qi),('qU',qu),*[(f'U{i}',f) for i,f in enumerate(forces)]]:
        bound(key+' nonnegative',-value,0.)
    finite=all(math.isfinite(x) for x in errors.values())
    return {'version':VERSION,'status':'PASS' if finite and max(errors.values())<tolerance else 'FAIL',
        'maximum_relative_error':max(errors.values()),'errors':errors,
        'structural_validation':False,'scope':'Declared magnitude-ray equilibrium/resources only; no constitutive or nodal validation.'}


def design_evidence(snapshot):
    """Read-only evidence inventory. User confirmations cannot override a method gap."""
    rows=snapshot.get('station_rows',[])
    coverage=snapshot.get('coverage',[])
    residuals=[r.get('Maximum numerical residual') for r in rows]
    numerical=bool(rows) and all(isinstance(v,(int,float)) and math.isfinite(v) and v<2e-7 for v in residuals)
    return {'version':VERSION,'design_status':'NOT ACCEPTED FOR FULL-COMPOSITE DESIGN',
        'numerical_verification':{'status':'VERIFIED' if numerical else 'INCOMPLETE',
            'maximum_solver_residual':max(residuals) if numerical else None},
        'interior_source_coverage':'COMPLETE' if coverage and all(c['Interior scan status']=='COMPLETE' for c in coverage) else 'INCOMPLETE',
        'independent_structural_validation':'NOT ESTABLISHED for this I-girder/slab/U detail under concurrent V–T/M/N',
        'method_gaps':[
            'No code-derived full stress field with concrete strut/node/splitting checks at the U-to-slab closure.',
            'The shared concrete-flow ceiling and longitudinal allocation are declared LP bounds, not an established safe lower-bound theorem for the actual member.',
            'No verified six-resultant resistance about the retained CSI reporting point (M2/V3 are excluded from this model).',
            'No justified LRFD resistance-factor treatment for the proposed combined method or verified physical end D-regions.'],
        'research_basis':[
            {'source':'Zhang, Wang & Lin, 2017 MOC & ISICT, pp.148–156',
             'url':'https://edocs.tib.eu/files/e01mr23/1840320877.pdf',
             'scope':'Pure torsion; rectangular 150 x 250 mm beams, U plus crosstie with 135-degree hooks. Not project-specific V–T validation.'},
            {'source':'Li et al., 2020, DOI 10.14006/j.jzjgxb.2019.0005',
             'url':'https://repository.lsu.edu/mechanical_engineering_pubs/1582/',
             'scope':'Overlapping hoops under monotonic torsion. 90-degree-hook post-peak ductility differs; not validation of this 90-degree U/slab detail.'},
            {'source':'FHWA-NHI-17-071, 2017; project AASHTO LRFD 9th Ed. 5.8.2',
             'url':'https://www.fhwa.dot.gov/bridge/concrete/nhi17071.pdf',
             'scope':'STM requires defined load paths, struts, ties, nodes and anchorage. A complete justified STM may be used without a full nonlinear slip solver; the present LP does not meet that standard.'}],
        'accepted_Vn_kN':None,'accepted_Tn_kNm':None,'accepted_VT_factor':None}
