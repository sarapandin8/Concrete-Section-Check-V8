"""AASHTO LRFD 2020 directional RC slab section checks.

Eight signed shell actions and the local-3 convention are retained. The
section checks use N/M/V in each reinforcement direction, never a resultant
shear with a shared capacity. This is not a biaxial shell interaction solver.
Connection/end exclusions and the engineer-selected REVIEW61 peak rule are
applied before resistance is evaluated; original source actions are untouched.
"""
from __future__ import annotations

import hashlib
import json
import time

import numpy as np
import pandas as pd

from concrete_pmm_pro.analysis import slab_shell56 as inputs
from concrete_pmm_pro.analysis.slab_connections59 import (
    INCLUDED, REASON, END_REASON, layout, annotate,
)
from concrete_pmm_pro.analysis.slab_review61 import peak_screen, PEAK, step_columns
from concrete_pmm_pro.analysis.slab_shell56_geometry import recover, steel_axis_forces
from concrete_pmm_pro.code_checks.aashto_lrfd import (
    aashto_alpha1, aashto_beta1, aashto_compression_controlled_strain_limit,
    aashto_tension_controlled_strain_limit,
)
from concrete_pmm_pro.io.slab_shell_import import current_package
from concrete_pmm_pro.analysis.slab_aashto63_sections import (
    support_geometry, in_support, sample_faces,
)

VERSION = 'SLAB.AASHTO63'
RESULT_KEY = 'slab_shell55_aashto62_result'
ES, PHI_V, KSI = 200000., .90, 6.894757293
AXES = (('Longitudinal', 0, 1, 'Nx', 'Mx', 'Vx'),
        ('Transverse', 2, 3, 'Ny', 'My', 'Vy'))
VIEWS = {
    'Shear · transverse': ('Transverse shear D/C', 'Transverse shear status'),
    'Shear · longitudinal': ('Longitudinal shear D/C', 'Longitudinal shear status'),
    'Direct N–M · transverse': ('Transverse N–M D/C', 'Transverse N–M status'),
    'Direct N–M · longitudinal': ('Longitudinal N–M D/C', 'Longitudinal N–M status'),
    'Flexural minimum · transverse': ('Transverse flexural minimum D/C', 'Transverse flexural minimum status'),
    'Flexural minimum · longitudinal': ('Longitudinal flexural minimum D/C', 'Longitudinal flexural minimum status'),
    'Flexural shear tie · transverse': ('Transverse tie D/C', 'Transverse tie status'),
    'Flexural shear tie · longitudinal': ('Longitudinal tie D/C', 'Longitudinal tie status'),
    'Temperature minimum': ('Temperature minimum D/C', 'Temperature minimum status'),
    'Bar spacing': ('Bar spacing D/C', 'Bar spacing status'),
}
SCOPE = ('AASHTO LRFD Ninth Edition (2020), normal-weight nonprestressed RC slab: '
    'directional sectional shear (5.7.3.3–5.7.3.4), flexural shear tie (5.7.3.5), '
    'direct N–M strain-compatible strip checks (5.6.2 / 5.6.3.2.5), '
    'four-mat temperature minimum and spacing; flexural minimum (5.6.3.3) '
    'using an explicitly sufficient gamma3=1 upper bound when steel fu is unavailable; '
    'girder/diaphragm support-face shear sampling (5.7.3.2), with no assumed dv relaxation; '
    'required straight-bar development length (5.10.8.2.1). Nxy/Mxy transfer, simultaneous '
    'biaxial shear (5.7.3.1), local support/load-path qualification, actual '
    'bar ends/laps/available anchorage, local '
    'rail-load/punching effects, fatigue and SLS remain separate. A component '
    'PASS does not establish full deck acceptance. Exclusions are project '
    'review assumptions, not code-authorized removal of equilibrium actions.')


def fingerprint(state):
    base = inputs.fingerprint(state)
    if base is None:
        return None
    return hashlib.sha256(json.dumps({'version': VERSION, 'base': base,
        'peak_rule': 'REVIEW61-one-pass', 'aggregate_mm': 0.,
        'reinforcement': 'four-mats-minimum-upper-bound-gamma3-development-reference',
        'support_sections': 'physical-top-flange-face-no-dv-relaxation'}, sort_keys=True).encode()).hexdigest()


def current(state):
    result = state.get(RESULT_KEY)
    return result if isinstance(result, dict) and result.get('version') == VERSION and result.get('fingerprint') == fingerprint(state) else None


def _status(dc, qualified=None):
    dc = np.asarray(dc, float)
    valid = np.isfinite(dc) if qualified is None else np.asarray(qualified, bool) & np.isfinite(dc)
    return np.where(~valid, 'REVIEW', np.where(dc > 1+1e-8, 'FAIL', 'PASS'))


from concrete_pmm_pro.analysis.slab_aashto62 import nm_curve, nm_ratios


def fixed_axial_resistance(h, n, steel, top, bottom):
    """Both signed design moment capacities at the SAME applied axial force.

    Intersect the strain-compatible design boundary with N=Nu. The radial
    N-M ratio is not reused as |Mu|/Mr: these are different design questions.
    No hull, compression-bar credit or new force reference is introduced.
    """
    h,n = np.asarray(h,float),np.asarray(n,float)
    out = np.full((len(h),6),np.nan)
    for thickness in np.unique(h):
        ids = np.flatnonzero(h==thickness)
        curve = nm_curve(thickness,steel,top,bottom)
        p,edge = curve[:-1],np.diff(curve,axis=0)
        for start in range(0,len(ids),2048):
            pick = ids[start:start+2048]
            with np.errstate(divide='ignore',invalid='ignore'):
                u = (n[pick,None]-p[:,0])/edge[:,0]
                moment = p[:,1]+u*edge[:,1]
            valid = np.isfinite(u)&(u>=-1e-10)&(u<=1+1e-10)
            for side,sign in enumerate((1.,-1.)):
                trial = np.where(valid,sign*moment,-np.inf)
                j = trial.argmax(1)
                finite = np.isfinite(trial[np.arange(len(pick)),j])
                ratio = u[np.arange(len(pick)),j]
                out[pick,side*3] = np.where(finite,moment[np.arange(len(pick)),j],np.nan)
                out[pick,side*3+1] = np.where(finite,p[j,3]+ratio*edge[j,3],np.nan)
                # Infinite pure-tension endpoint strain is a valid limit, not
                # a reason to make a finite moment capacity disappear.
                e0,e1 = p[j,4],curve[j+1,4]
                with np.errstate(invalid='ignore'):
                    strain = np.where(np.isinf(e0)|np.isinf(e1),np.inf,e0+ratio*(e1-e0))
                out[pick,side*3+2] = np.where(finite,strain,np.nan)
    return out


def flexural_minimum(h,n,m,steel,top,bottom,resistance):
    """5.6.3.3: Mr >= min(1.33|Mu|, Mcr), gamma3<=1.

    No reinforcement standard or fu is fabricated. gamma3=1 is an UPPER
    bound on fy/fu, so passing this stricter threshold is sufficient. A
    failure of the upper bound is REVIEW, not a manufactured code failure.
    At fixed Nu, use the matching sign of bending and variable phi. A
    compression-controlled component is outside this minimum provision.
    """
    h,n,m = map(lambda a:np.asarray(a,float),(h,n,m))
    positive = m>=0
    mr = np.where(positive,resistance[:,0],-resistance[:,3])
    phi = np.where(positive,resistance[:,1],resistance[:,4])
    strain = np.where(positive,resistance[:,2],resistance[:,5])
    # RC strip: no prestress/noncomposite dead-load terms; fr in MPa.
    fr = .24*np.sqrt(steel.fc/KSI)*KSI
    mcr_upper = 1.6*fr*h*h/6000.
    # For combined axial force use the universally sufficient 1.33Mu branch;
    # do not invent a cracking-moment formula for external axial actions.
    required = np.where(abs(n)<=1e-9,np.minimum(1.33*abs(m),mcr_upper),1.33*abs(m))
    ratio = np.divide(required,mr,out=np.full(len(h),np.nan),where=mr>0)
    no_moment = abs(m)<=1e-12
    compression = (strain<=aashto_compression_controlled_strain_limit(max(steel.fy[[top,bottom]]))+1e-12)
    sufficient = (ratio<=1+1e-8)&np.isfinite(ratio)
    # Unknown fu is only needed if this sufficient proof does not pass.
    dc = np.where(no_moment|compression,0.,np.where(sufficient,ratio,np.nan))
    status = np.where(no_moment|compression,'NOT REQUIRED',np.where(sufficient,'PASS','REVIEW'))
    return {'flexural minimum D/C':dc,'flexural minimum status':status,
        'minimum trial D/C':ratio,'minimum Mu (kN·m/m)':abs(m),
        'minimum Mr (kN·m/m)':mr,'minimum phi':phi,
        'Mcr upper bound (kN·m/m)':mcr_upper,'minimum required upper bound (kN·m/m)':required,
        'minimum basis':np.where(no_moment,'No directional bending',np.where(compression,
            '5.6.3.3 not applicable: compression-controlled boundary',np.where(sufficient,
            np.where(abs(n)<=1e-9,'5.6.3.3 sufficient proof; gamma3=1 upper bound',
                '5.6.3.3 sufficient 1.33Mu proof at the same axial force'),
            'Exact cracking-moment / gamma3 branch required to resolve minimum')))}


def development_reference(h,steel):
    """Required straight-bar ld only; actual anchorage is never inferred.

    Factors: no confinement/excess-steel reduction; normal-weight concrete.
    Unreported coating uses the applicable epoxy bound 1.2/1.5, cap 1.7. This
    upper-bound requirement is conservative for uncoated/epoxy bars alike.
    """
    h = np.asarray(h,float)
    below = np.column_stack((h-steel.centre[0],np.full(len(h),steel.centre[1]),
        h-steel.centre[2],np.full(len(h),steel.centre[3])))
    location = np.where((below>12*25.4)|(steel.fc>10*KSI),1.3,1.)
    clear_cover = steel.centre-steel.diameter/2
    coating = np.where((clear_cover<3*steel.diameter)|
        (steel.spacing-steel.diameter<6*steel.diameter),1.5,1.2)
    factors = np.minimum(location*coating,1.7)
    basic = 2.4*steel.diameter*(steel.fy/KSI)/np.sqrt(steel.fc/KSI)
    ld = np.maximum(12*25.4,basic*factors)
    return ld,location


def directional_shear(h, n, m, v, steel, top, bottom, *, resistance=None):
    """5.7.3.3/4: matching N,M,V, tension-side As, face-specific dv.

    Vs=Vp=0. In-plane slab mesh is not credited as vertical shear steel.
    No aggregate input is invented: ag=0. sx uses qualified actual layers,
    bounded above by dv. Negative strain uses the explicitly permitted zero
    branch. An actual strain >.006 is REVIEW, never silently capped to PASS.
    """
    h, n, m, v = map(lambda a: np.asarray(a, float), (h, n, m, v))
    # At zero moment the smaller of the two physical tension mats controls.
    selected = np.where(m > 1e-12, bottom, np.where(m < -1e-12, top,
        top if steel.area[top] <= steel.area[bottom] else bottom))
    area, fy, cover = steel.area[selected], steel.fy[selected], steel.centre[selected]
    dv = np.maximum(.9*(h-cover), .72*h)
    # At an inflection, evaluate the conservative geometric depth of both mats.
    dv = np.where(abs(m) <= 1e-12, np.maximum(.9*(h-max(steel.centre[[top, bottom]])), .72*h), dv)
    layer_gap = h-steel.centre[top]-steel.centre[bottom]
    sx_trial = np.minimum(dv, np.maximum.reduce((layer_gap,
        np.full(len(h), steel.centre[top]), np.full(len(h), steel.centre[bottom]))))
    adequate_layers = np.minimum(steel.area[top], steel.area[bottom]) >= .003*1000*sx_trial
    sx = np.where(adequate_layers, sx_trial, dv)
    sxe = np.clip(sx*1.38/.63, 12*25.4, 80*25.4)
    demand = abs(v)
    moment_term = np.maximum(abs(m)*1000/dv, demand)
    eps_raw = (moment_term+.5*n+demand)/(ES*area/1000)
    # Conservative cracked-section rule: if even the nominal compression
    # face is in axial tension, double strain. No concrete tensile credit.
    both_tension = n > 6*abs(m)*1000/h+1e-9
    eps_raw = np.where(both_tension, 2*eps_raw, eps_raw)
    eps = np.maximum(eps_raw, 0.)
    simplified = (h < 16*25.4) & (n <= 1e-9)
    qualified = simplified | (eps <= .006+1e-12)
    # Trial parameters remain auditable even where applicability fails.
    trial_eps = np.minimum(eps, .006)
    beta = np.where(simplified, 2., 4.8/(1+750*trial_eps)*51/(39+sxe/25.4))
    theta = np.where(simplified, 45., 29+3500*trial_eps)
    vc = .0316*np.sqrt(steel.fc/KSI)*KSI*beta*dv
    vn = np.minimum(vc, .25*steel.fc*dv)
    capacity = np.where(qualified, PHI_V*vn, np.nan)
    dc = demand/capacity
    # Use the phi of the flexural resistance at this same Nu and moment
    # sign. A fixed .90 would be unsafe for transition/controlled sections.
    if resistance is None:
        resistance = fixed_axial_resistance(h,n,steel,top,bottom)
    phi_f = np.where(m>1e-12,resistance[:,1],np.where(m< -1e-12,
        resistance[:,4],np.fmin(resistance[:,1],resistance[:,4])))
    qualified &= np.isfinite(phi_f)
    # 5.7.3.5-1, no shear steel or prestress. No unconditional addition to
    # both shell faces: this is the flexural tension-side strip tie only.
    tie = np.maximum(0., abs(m)*1000/(dv*phi_f)+.5*n/.75+
        demand/PHI_V/np.tan(np.deg2rad(theta)))
    tie_dc = np.where(qualified, tie/(area*fy/1000), np.nan)
    return {'shear D/C': dc, 'shear status': _status(dc, np.isfinite(dc)),
        'Nu (kN/m)': n, 'Mu (kN·m/m)': m, 'Vu (kN/m)': v,
        'tension mat': np.where(selected == top, 'Top', 'Bottom'),
        'As tension (mm²/m)': area, 'fy tension (MPa)': fy,
        'dv (mm)': dv, 'sx (mm)': sx, 'sxe (mm)': sxe,
        'strain raw': eps_raw, 'strain used': np.where(simplified, np.nan, eps),
        'both faces tension': both_tension, 'beta': beta, 'theta (deg)': theta,
        'procedure': np.where(simplified, '5.7.3.4.1 · simplified', '5.7.3.4.2 · general'),
        'Vn (kN/m)': np.where(qualified, vn, np.nan), 'phiVn (kN/m)': capacity,
        'tie required (kN/m)': tie, 'tie phi_f':phi_f, 'tie capacity (kN/m)': area*fy/1000,
        'tie D/C': tie_dc, 'tie status': _status(tie_dc, qualified)}


def section_checks(rows, steel):
    h = rows['Thickness (mm)'].to_numpy(float)
    if np.any(h <= 0) or not np.isfinite(rows[['Thickness (mm)', 'Nx','Ny','Nxy','Mx','My','Mxy','Vx','Vy']].to_numpy(float)).all():
        raise ValueError('Directional checks require finite complete actions and positive thickness')
    if np.any((steel.centre[[0,2]]+steel.diameter[[0,2]]/2+
               steel.centre[[1,3]]+steel.diameter[[1,3]]/2)[None, :] >= h[:, None]):
        raise ValueError('Opposite slab reinforcement mats overlap')
    data = {}
    for label, top, bottom, nc, mc, vc in AXES:
        n, m, v = (rows[c].to_numpy(float) for c in (nc, mc, vc))
        resistance = fixed_axial_resistance(h,n,steel,top,bottom)
        data.update({label+' '+key: value for key, value in directional_shear(h,n,m,v,steel,top,bottom,resistance=resistance).items()})
        nm = nm_ratios(h,n,m,steel,top,bottom)
        data[label+' N–M D/C'] = nm[:, 0]
        data[label+' N–M status'] = _status(nm[:, 0])
        for i, key in enumerate(('N boundary (kN/m)', 'M boundary (kN·m/m)', 'c boundary (mm)', 'phi boundary', 'strain boundary'), 1):
            data[label+' '+key] = nm[:, i]
        data.update({label+' '+key:value for key,value in flexural_minimum(h,n,m,steel,top,bottom,resistance).items()})
        for k,name in enumerate(('positive Mr (kN·m/m)','positive phi','positive strain',
                                 'negative Mr (kN·m/m)','negative phi','negative strain')):
            data[label+' '+name] = resistance[:,k]
    data['Temperature minimum D/C'] = np.max(inputs.temperature_minimum(h, steel.fy)/steel.area, axis=1)
    # 5.10.3.2 plus 5.10.6: other components thicker than 36 in. also
    # have a 12-in. temperature-steel spacing ceiling.
    spacing_limit = np.minimum(np.minimum(1.5*h,18*25.4),
        np.where(h>36*25.4,12*25.4,np.inf))
    data['Bar spacing D/C'] = np.max(steel.spacing/spacing_limit[:,None], axis=1)
    data['Temperature minimum status'] = _status(data['Temperature minimum D/C'])
    data['Bar spacing status'] = _status(data['Bar spacing D/C'])
    temperature = inputs.temperature_minimum(h,steel.fy)
    ld,location = development_reference(h,steel)
    for mat,label in enumerate(inputs.GROUPS):
        data[label+' As temperature (mm²/m)'] = temperature[:,mat]
        data[label+' temperature D/C'] = temperature[:,mat]/steel.area[mat]
        data[label+' spacing limit (mm)'] = spacing_limit
        data[label+' spacing D/C'] = steel.spacing[mat]/spacing_limit
        data[label+' ld required upper bound (mm)'] = ld[:,mat]
        data[label+' location factor'] = location[:,mat]
    out = pd.DataFrame(data, index=rows.index)
    ratio_columns = [col for col, _ in VIEWS.values()]
    values = out[ratio_columns].to_numpy(float)
    out['Known component max D/C'] = np.nanmax(values, axis=1)
    out['Controlling check'] = np.array(list(VIEWS))[np.where(np.isfinite(values),values,-np.inf).argmax(1)]
    out['Section status'] = np.where(out['Known component max D/C']>1+1e-8,'FAIL',
        np.where(np.isnan(values).any(1),'REVIEW','PASS'))
    coupling = (rows[['Nxy','Mxy']].abs().max(axis=1)>1e-8) | ((rows['Vx'].abs()>1e-8)&(rows['Vy'].abs()>1e-8))
    out['Shell coupling status'] = np.where(coupling,'REVIEW','Not activated by this vector')
    # A finite section ratio never certifies anchorage or omitted support/end
    # actions. Keep overall design acceptance separate from component status.
    out['Design acceptance'] = 'REVIEW REQUIRED'
    return out


def _summary(rows,labels=None):
    output = []
    for label in VIEWS if labels is None else labels:
        column,status_column=VIEWS[label]
        values=rows[column]
        # Select the governing row only. Filtering the entire wide source
        # frame for every view needlessly copies hundreds of MB per summary.
        peak = rows.loc[values.idxmax()] if values.notna().any() else None
        unknown = rows[status_column].eq('REVIEW')
        status = 'FAIL' if values.gt(1+1e-8).any() else 'REVIEW' if unknown.any() else 'PASS'
        output.append({'Check': label, 'Status': status,
            'Max D/C': peak[column] if peak is not None else np.nan,
            'Case': peak['OutputCase'] if peak is not None else '',
            'Step': peak['StepType'] if peak is not None else '',
            'X (m)': peak['X (m)'] if peak is not None else np.nan,
            'Y (m)': peak['Y (m)'] if peak is not None else np.nan,
            'AreaElem': peak['AreaElem'] if peak is not None else '',
            'Joint': peak['Joint'] if peak is not None else '',
            'Failed nodes': rows.loc[values>1+1e-8,'Joint'].nunique(),
            'Review nodes': rows.loc[unknown,'Joint'].nunique()})
    return pd.DataFrame(output)


def reinforcement_summary(rows,steel):
    """Four physical mats, no repeated input or adding both areas as Vs."""
    output = []
    for i,label in enumerate(inputs.GROUPS):
        direction = 'Longitudinal' if i<2 else 'Transverse'
        side = 'Top' if i%2==0 else 'Bottom'
        active = rows.loc[rows[direction+' tension mat'].eq(side)]
        temp = rows[label+' temperature D/C'].max()
        spacing = rows[label+' spacing D/C'].max()
        minimum = active[direction+' flexural minimum D/C'].max() if len(active) else 0.
        tie = active[direction+' tie D/C'].max() if len(active) else 0.
        output.append({'Mat':label,'Bar (mm)':steel.diameter[i],'Spacing (mm)':steel.spacing[i],
            'As provided (mm²/m)':steel.area[i],'fy (MPa)':steel.fy[i],
            'Clear cover (mm)':steel.centre[i]-steel.diameter[i]/2,
            'Bar centre (mm)':steel.centre[i],
            'As temperature max (mm²/m)':rows[label+' As temperature (mm²/m)'].max(),
            'Temperature D/C':temp,'Spacing D/C':spacing,
            'Flexural minimum sufficient D/C':minimum,'Tension-side shear tie D/C':tie,
            'ld required upper bound (mm)':rows[label+' ld required upper bound (mm)'].max(),
            'Anchorage status':'REVIEW: available length / laps / hooks not in shell export'})
    return pd.DataFrame(output)


def code_coverage(rows,faces,connections):
    """Explicit checklist: computed component resistance is not deck approval."""
    coupling = bool(rows[['Nxy','Mxy']].abs().gt(1e-8).any().any())
    biaxial = bool(((rows.Vx.abs()>1e-8)&(rows.Vy.abs()>1e-8)).any())
    return pd.DataFrame([
        {'Check':'Direct N–M, both physical mats','Article':'5.6.2 / 5.6.3.2.5','Coverage':'CALCULATED',
         'Basis / remaining action':'Both bending signs; variable phi; compression steel strength not credited'},
        {'Check':'Flexural minimum','Article':'5.6.3.3','Coverage':
         'REVIEW' if any(rows[d+' flexural minimum status'].eq('REVIEW').any() for d,*_ in AXES) else 'SUFFICIENT PROOF',
         'Basis / remaining action':'1.33Mu at the same Nu; N=0 may also use conservative gamma3=1 Mcr upper bound'},
        {'Check':'Temperature / spacing: four mats','Article':'5.10.6 / 5.10.3.2','Coverage':'CALCULATED',
         'Basis / remaining action':'Each face / each direction separately; temperature bound uses b→infinity'},
        {'Check':'Directional one-way shear / flexural shear tie','Article':'5.7.3 / 5.12.8.6.2','Coverage':'CALCULATED',
         'Basis / remaining action':'Matching N/M/V/As; in-plane mesh is not vertical shear steel (Vs=0)'},
        {'Check':'Girder / diaphragm support-face shear','Article':'5.7.3.2','Coverage':
         ('PARTIAL: source exclusions' if not faces[INCLUDED].all() else 'CALCULATED') if len(faces) else 'REVIEW',
         'Basis / remaining action':'Existing flange width / native diaphragm thickness; full contact assumed; no dv relaxation; unavailable source samples are not reconstructed'},
        {'Check':'Support width / local D-regions','Article':'5.7.1.2 / 5.7.3.2 / 5.8.2','Coverage':'REVIEW',
         'Basis / remaining action':'Native support footprints retained as local-support review; local bearing/load paths not qualified'},
        {'Check':'Nxy / Mxy transfer','Article':'5.7.3.1','Coverage':'REVIEW' if coupling else 'NOT ACTIVATED',
         'Basis / remaining action':'All concurrent components retained; separate directional N–M does not resolve shell coupling'},
        {'Check':'Simultaneous biaxial shear','Article':'5.7.3.1','Coverage':'REVIEW' if biaxial else 'NOT ACTIVATED',
         'Basis / remaining action':'Requires compatible refined analysis or 3D STM when warranted; separate PASS is not interaction acceptance'},
        {'Check':'Straight-bar development','Article':'5.10.8.2.1 / 5.7.3.5','Coverage':'REQUIRED LENGTH CALCULATED',
         'Basis / remaining action':'Applicable epoxy upper bound 1.2/1.5; no confinement reduction; actual ends/laps/hooks not supplied'},
        {'Check':'Two-way / punching shear','Article':'5.12.8.6','Coverage':'REVIEW',
         'Basis / remaining action':'Load/reaction footprint and concurrent perimeter resultants required; shell corner forces alone do not define the loaded area'},
        {'Check':'Slab–girder interface / U-dowels','Article':'5.7.4','Coverage':'REVIEW',
         'Basis / remaining action':'Cross-interface demand, surface condition, crossing steel and anchorage required; no automatic U-leg credit in slab Vs'},
        {'Check':'Fatigue / SLS / exposure cover','Article':'5.5 / 5.6.7 / 5.10','Coverage':'SEPARATE CHECK',
         'Basis / remaining action':'Current supplied demand package is ULS; not a complete deck detailing or serviceability acceptance'},
    ])


def calculate(state, *, progress=None):
    start = time.monotonic()
    package = current_package(state)
    if package is None:
        raise ValueError('Import the complete current shell package first')
    steel = inputs.steel_from_state(state)
    if np.max(steel.fy)>100*KSI:
        raise ValueError('Slab reinforcement exceeds the documented AASHTO 100 ksi material range')
    geometry = recover(package)
    frame = package.tables['forces'].loc[package.tables['forces']['Area'].isin(set(geometry.corners['Area']))].copy().reset_index(drop=True)
    frame = frame.merge(geometry.corners,on=['Area','AreaElem','Joint'],how='left',validate='many_to_one')
    if frame['Thickness (mm)'].isna().any():
        raise ValueError('Missing shell corner geometry or thickness')
    frame = steel_axis_forces(frame, geometry.parent_axes)
    connections = layout(package, geometry, state)
    missing_exclusions = [note for note in connections.get('notes', [])
        if 'unavailable' in note.casefold() or 'no inferred exclusion' in note.casefold()]
    if missing_exclusions:
        raise ValueError('Agreed connection exclusions cannot be located: '+' '.join(missing_exclusions))
    frame = annotate(frame, connections)
    geometry_mask = frame[INCLUDED].copy()
    mask, ledger = peak_screen({'rows':frame,'geometry':geometry})
    frame[PEAK] = mask
    frame.loc[mask, INCLUDED] = False
    frame.loc[mask, REASON] = 'Isolated peak · REVIEW61 engineer-selected rule'
    retained = frame.loc[frame[INCLUDED]]
    if retained.empty:
        raise ValueError('No slab records remain outside the agreed exclusions')
    if progress:
        progress(.3, 'Checking directional AASHTO sections…')
    # Exact native thickness is retained; group-independent curves are reused
    # across all case/element samples with that thickness.
    checked = section_checks(retained, steel)
    if progress:
        progress(.65,'Extracting girder / diaphragm faces from native geometry…')
    result_rows = pd.concat((frame, checked.reindex(frame.index)), axis=1)
    result_rows['Record type'] = 'Native corner'
    supports = support_geometry(connections,package)
    # This is NOT another source exclusion: N-M and minimum checks remain.
    # A one-way strip is not continued through the physical reaction area.
    for direction,*_ in AXES:
        region=in_support(result_rows[['X (m)','Y (m)']].to_numpy(float),
            [s for s in supports if s['Direction']==direction])
        result_rows[direction+' local support region']=region
        for kind in ('shear','tie'):
            column = direction+' '+kind
            result_rows[column+' native D/C'] = result_rows[column+' D/C']
            inside = result_rows[INCLUDED]&region
            result_rows.loc[inside,column+' D/C'] = np.nan
            result_rows.loc[inside,column+' status'] = 'REVIEW'
    ratios = result_rows[[c for c,_ in VIEWS.values()]]
    result_rows['Known component max D/C'] = ratios.max(axis=1)
    result_rows['Controlling check']='EXCLUDED'
    has_value=ratios.notna().any(axis=1)
    result_rows.loc[has_value,'Controlling check'] = ratios.loc[has_value].rename(columns={c:v for v,(c,_) in VIEWS.items()}).idxmax(axis=1)
    result_rows['Section status'] = np.where(ratios.gt(1+1e-8).any(axis=1),'FAIL',
        np.where(ratios.isna().any(axis=1),'REVIEW','PASS'))
    faces,recipes = sample_faces(frame,geometry,supports)
    if len(faces):
        target_scope=annotate(faces,connections)[INCLUDED]
        faces['Target in accepted scope']=target_scope
        faces[INCLUDED]&=target_scope
        faces.loc[~target_scope,REASON]='Target lies on an agreed connection / bearing exclusion'
        available = faces.loc[faces[INCLUDED]]
        if len(available):
            face_checks = section_checks(available,steel)
            faces = pd.concat((faces,face_checks.reindex(faces.index)),axis=1)
        else:
            empty_checks=checked.iloc[:0].reindex(faces.index)
            faces=pd.concat((faces,empty_checks),axis=1)
        for direction,*_ in AXES:
            faces[direction+' local support region'] = False
        for _,status in VIEWS.values():
            faces.loc[~faces[INCLUDED],status] = 'REVIEW'
    for _, status in VIEWS.values():
        result_rows.loc[~result_rows[INCLUDED],status]='EXCLUDED'
    result_rows.loc[~result_rows[INCLUDED],['Section status','Design acceptance']]='EXCLUDED'
    keys=step_columns(frame)
    coverage=frame.groupby(keys,dropna=False).agg(**{'Imported records':('Joint','size'),
        'Checked records':(INCLUDED,'sum'),'Peak excluded records':(PEAK,'sum')}).reset_index()
    coverage['Expected records']=len(geometry.corners)
    coverage['Missing records']=coverage['Expected records']-coverage['Imported records']
    coverage['Excluded records']=coverage['Imported records']-coverage['Checked records']
    incomplete=bool(coverage['Missing records'].ne(0).any())
    design=result_rows.loc[result_rows[INCLUDED]]
    summary=_summary(design)
    # Only shear and its tension tie use the face samples. Direct N-M and
    # minimum envelopes retain the original accepted native-corner scope.
    shear_designs={}
    for direction,*_ in AXES:
        # An in-scope target with unavailable source interpolation is a
        # REVIEW sample, not an omitted check that can disappear from PASS.
        compatible=faces.loc[faces['Target in accepted scope']&faces.Direction.eq(direction)] if len(faces) else faces
        shear_designs[direction]=pd.concat((design,compatible),ignore_index=True) if len(compatible) else design
        labels=[prefix+direction.lower() for prefix in ('Shear · ','Flexural shear tie · ')]
        face_summary_table=_summary(shear_designs[direction],labels).set_index('Check')
        for view in labels:
            face_summary = face_summary_table.loc[view]
            summary.loc[summary.Check.eq(view),face_summary.index] = face_summary.to_numpy()
    if incomplete:
        summary.loc[summary.Status.eq('PASS'),'Status']='REVIEW'
    raw_counts=frame[REASON].value_counts().rename_axis('Reason').reset_index(name='Records')
    axes=pd.DataFrame([{'Area':area, 'Local 1':np.round(a['local1'],8).tolist(),
        'Local 2':np.round(a['local2'],8).tolist(),'Local 3':np.round(a['local3'],8).tolist(),
        'Longitudinal':np.round(a['long'],8).tolist(),'Transverse':np.round(a['transverse'],8).tolist(),
        'Rotation angle (deg)':float(np.degrees(np.arctan2(a['rotation'][0,1],a['rotation'][0,0]))),
        'Normal sign':a['normal_sign']} for area,a in geometry.parent_axes.items()])
    if progress:
        progress(1., 'Directional checks complete')
    steel_summary = reinforcement_summary(design,steel)
    # Include support-face tension-tie maxima in the physical transverse mats.
    if len(faces):
        for i in range(4):
            direction='Longitudinal' if i<2 else 'Transverse'
            side='Top' if i%2==0 else 'Bottom'
            active=shear_designs[direction].loc[shear_designs[direction][direction+' tension mat'].eq(side)]
            steel_summary.loc[i,'Tension-side shear tie D/C'] = active[direction+' tie D/C'].max()
    return {'version':VERSION,'fingerprint':fingerprint(state),'code':'AASHTO LRFD 9th Edition (2020)',
        'rows':result_rows,'geometry':geometry,'connections':connections,'steel':steel,
        'summary':summary,'coverage':coverage,'incomplete':incomplete,'peak_ledger':ledger,
        'support_faces':faces,'face_recipes':recipes,'supports':supports,
        'reinforcement_summary':steel_summary,'code_coverage':code_coverage(design,faces,connections),
        'source_rows':len(frame),'design_rows':len(design),'excluded_rows':int((~frame[INCLUDED]).sum()),
        'geometry_excluded_rows':int((~geometry_mask).sum()),'peak_excluded_rows':int(mask.sum()),
        'exclusion_counts':raw_counts,'axes':axes,'scope':SCOPE,'seconds':time.monotonic()-start,
        'component_status':'FAIL' if summary.Status.eq('FAIL').any() else 'REVIEW' if summary.Status.eq('REVIEW').any() else 'PASS',
        'status':'REVIEW REQUIRED'}


def map_adapter(result, view):
    """Reuse the accepted full-plan chart; all exclusion and coverage rules stay."""
    column,status = VIEWS[view]
    frame=result['rows'].copy(deep=False)
    if (view.startswith('Shear ·') or view.startswith('Flexural shear tie ·')) and len(result['support_faces']):
        # Additional cut samples cannot conceal missing native coverage.
        step_keys=step_columns(frame)
        expected=4*len(frame[step_keys].drop_duplicates())
        sizes=frame.groupby('AreaElem').size()
        frame=frame.assign(**{'Source incomplete':frame.AreaElem.map(sizes).lt(expected)})
        direction='Transverse' if view.endswith('transverse') else 'Longitudinal'
        faces=result['support_faces'].loc[result['support_faces'].Direction.eq(direction)].copy()
        # Display-only inclusion of unresolved in-scope cut targets. Their
        # numerical checks are NaN; actual inclusion masks stay in the audit.
        faces[INCLUDED]=faces['Target in accepted scope']
        faces['Source incomplete']=(faces['Source incomplete']|
            ~result['support_faces'].loc[faces.index,INCLUDED])&faces['Target in accepted scope']
        frame=pd.concat((frame,faces),ignore_index=True)
    frame=frame.assign(**{'Field D/C':frame[column],
        'Status':frame[status],'Combined N–M–V status':frame['Shell coupling status']})
    return {**result,'rows':frame}
