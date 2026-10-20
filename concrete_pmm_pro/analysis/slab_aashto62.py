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

VERSION = 'SLAB.AASHTO62'
RESULT_KEY = 'slab_shell55_aashto62_result'
ES, PHI_V, KSI = 200000., .90, 6.894757293
AXES = (('Longitudinal', 0, 1, 'Nx', 'Mx', 'Vx'),
        ('Transverse', 2, 3, 'Ny', 'My', 'Vy'))
VIEWS = {
    'Shear · transverse': ('Transverse shear D/C', 'Transverse shear status'),
    'Shear · longitudinal': ('Longitudinal shear D/C', 'Longitudinal shear status'),
    'Direct N–M · transverse': ('Transverse N–M D/C', 'Transverse N–M status'),
    'Direct N–M · longitudinal': ('Longitudinal N–M D/C', 'Longitudinal N–M status'),
    'Flexural shear tie · transverse': ('Transverse tie D/C', 'Transverse tie status'),
    'Flexural shear tie · longitudinal': ('Longitudinal tie D/C', 'Longitudinal tie status'),
    'Temperature minimum': ('Temperature minimum D/C', 'Temperature minimum status'),
    'Bar spacing': ('Bar spacing D/C', 'Bar spacing status'),
}
SCOPE = ('AASHTO LRFD Ninth Edition (2020), normal-weight nonprestressed RC slab: '
    'directional sectional shear (5.7.3.3–5.7.3.4), flexural shear tie (5.7.3.5), '
    'direct N–M strain-compatible strip checks (5.6.2 / 5.6.3.2.5), '
    'temperature minimum and bar spacing. Nxy/Mxy transfer, simultaneous '
    'biaxial shear (5.7.3.1), support critical-section qualification (5.7.3.2), '
    'anchorage/development, complete flexural-minimum qualification, local '
    'rail-load/punching effects, fatigue and SLS remain separate. A component '
    'PASS does not establish full deck acceptance. Exclusions are project '
    'review assumptions, not code-authorized removal of equilibrium actions.')


def fingerprint(state):
    base = inputs.fingerprint(state)
    if base is None:
        return None
    return hashlib.sha256(json.dumps({'version': VERSION, 'base': base,
        'peak_rule': 'REVIEW61-one-pass', 'aggregate_mm': 0.,
        'reinforcement': 'existing-four-mats-full-development-sectional-basis'}, sort_keys=True).encode()).hexdigest()


def current(state):
    result = state.get(RESULT_KEY)
    return result if isinstance(result, dict) and result.get('version') == VERSION and result.get('fingerprint') == fingerprint(state) else None


def _status(dc, qualified=None):
    dc = np.asarray(dc, float)
    valid = np.isfinite(dc) if qualified is None else np.asarray(qualified, bool) & np.isfinite(dc)
    return np.where(~valid, 'REVIEW', np.where(dc > 1+1e-8, 'FAIL', 'PASS'))


def nm_curve(h, steel, top, bottom, *, points=320):
    """Closed N–M design curve, kN/m and kN.m/m; no compression-bar credit.

    One metre width, ecu=.003, AASHTO rectangular block and variable phi.
    Concrete displaced by bars is removed from the stress block. Tension
    steel is elastic-perfectly-plastic. Compression steel is intentionally
    omitted: no invented buckling restraint. This is a short-strip section
    reference, not compression-member detailing or second-order acceptance.
    Segments join adjacent strain states, never a convex hull of the curve.
    """
    h = float(h)
    area = steel.area[[top, bottom]]
    fy = steel.fy[[top, bottom]]
    y = np.array([steel.centre[top], h-steel.centre[bottom]])
    z = h/2-y
    if h <= 0 or not (0 < y[0] < y[1] < h):
        raise ValueError('Reinforcement layers do not fit the local RC slab section')
    alpha, beta = aashto_alpha1(steel.fc), aashto_beta1(steel.fc)
    fy_control = float(max(fy))
    eps_cl = aashto_compression_controlled_strain_limit(fy_control)
    eps_tl = aashto_tension_controlled_strain_limit(fy_control)
    branches = []
    for face in (1., -1.):
        depths = y if face > 0 else h-y
        ratios = np.r_[np.geomspace(1e-5, 1000., points),
            depths/h, depths/h/(1+fy/ES/.003),
            depths/h/(1+eps_cl/.003), depths/h/(1+eps_tl/.003), 1/beta]
        c = np.unique(ratios)*h
        a = np.minimum(beta*c, h)
        eps = .003*(depths[None, :]/c[:, None]-1.)
        tension = area*np.minimum(np.maximum(ES*eps, 0.), fy)
        covered = depths[None, :] <= a[:, None]
        # Subtract the concrete volume occupied by embedded bars.
        cc = alpha*steel.fc*(1000*a-(covered*area).sum(1))
        first_cc = alpha*steel.fc*(1000*a*face*(h/2-a/2)-(covered*area*z).sum(1))
        n = (tension.sum(1)-cc)/1000
        m = (first_cc-(tension*z).sum(1))/1e6
        eps_t = np.maximum(eps.max(1), 0.)
        phi = .75+.15*np.clip((eps_t-eps_cl)/(eps_tl-eps_cl), 0., 1.)
        branches.append(np.column_stack((phi*n, phi*m, c, phi, eps_t)))
    tension_end = np.array([.9*np.sum(area*fy)/1000,
        -.9*np.sum(z*area*fy)/1e6, 0., .9, np.inf])
    # Start at pure tension, pass the top-compression branch, return by the
    # bottom-compression branch and close at pure tension.
    return np.vstack((tension_end, branches[0], branches[1][::-1], tension_end))


def nm_ratios(h, n, m, steel, top, bottom):
    """Radial N–M utilization; no axial demand is dropped at small moment.

    D/C=1/lambda, where lambda*(Nu,Mu) first intersects the closed design
    boundary. All intersections with neighbouring strain states are checked.
    """
    h, n, m = map(lambda a: np.asarray(a, float), (h, n, m))
    out = np.full((len(h), 6), np.nan)
    for thickness in np.unique(h):
        ids = np.flatnonzero(h == thickness)
        curve = nm_curve(thickness, steel, top, bottom)
        p = curve[:-1, :2]
        edge = np.diff(curve[:, :2], axis=0)
        numerator = p[:, 0]*edge[:, 1]-p[:, 1]*edge[:, 0]
        for start in range(0, len(ids), 2048):
            pick = ids[start:start+2048]
            den = n[pick, None]*edge[:, 1]-m[pick, None]*edge[:, 0]
            with np.errstate(divide='ignore', invalid='ignore'):
                lam = numerator[None, :]/den
                u = (p[:, 0]*m[pick, None]-p[:, 1]*n[pick, None])/den
            valid = (lam > 0) & (u >= -1e-9) & (u <= 1+1e-9)
            trial = np.where(valid, lam, np.inf)
            j = trial.argmin(1)
            length = trial[np.arange(len(pick)), j]
            blend = np.clip(u[np.arange(len(pick)), j], 0., 1.)
            with np.errstate(invalid='ignore'):
                state = curve[j, 2:]+blend[:, None]*(curve[j+1, 2:]-curve[j, 2:])
            out[pick, 0] = np.where(np.isfinite(length), 1/length, np.nan)
            with np.errstate(invalid='ignore'):
                out[pick, 1] = length*n[pick]
                out[pick, 2] = length*m[pick]
            out[pick, 3:] = state
    zero = (abs(n) <= 1e-12) & (abs(m) <= 1e-12)
    out[zero, :3] = 0.
    return out


def directional_shear(h, n, m, v, steel, top, bottom):
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
    phi_f = .90
    # 5.7.3.5-1, no shear steel or prestress. No unconditional addition to
    # both shell faces: this is the flexural tension-side strip tie only.
    tie = np.maximum(0., abs(m)*1000/(dv*phi_f)+.5*n/.75+
        demand/PHI_V/np.tan(np.deg2rad(theta)))
    tie_dc = np.where(qualified, tie/(area*fy/1000), np.nan)
    return {'shear D/C': dc, 'shear status': _status(dc, qualified),
        'Nu (kN/m)': n, 'Mu (kN·m/m)': m, 'Vu (kN/m)': v,
        'tension mat': np.where(selected == top, 'Top', 'Bottom'),
        'As tension (mm²/m)': area, 'fy tension (MPa)': fy,
        'dv (mm)': dv, 'sx (mm)': sx, 'sxe (mm)': sxe,
        'strain raw': eps_raw, 'strain used': np.where(simplified, np.nan, eps),
        'both faces tension': both_tension, 'beta': beta, 'theta (deg)': theta,
        'procedure': np.where(simplified, '5.7.3.4.1 · simplified', '5.7.3.4.2 · general'),
        'Vn (kN/m)': np.where(qualified, vn, np.nan), 'phiVn (kN/m)': capacity,
        'tie required (kN/m)': tie, 'tie capacity (kN/m)': area*fy/1000,
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
        data.update({label+' '+key: value for key, value in directional_shear(h,n,m,v,steel,top,bottom).items()})
        nm = nm_ratios(h,n,m,steel,top,bottom)
        data[label+' N–M D/C'] = nm[:, 0]
        data[label+' N–M status'] = _status(nm[:, 0])
        for i, key in enumerate(('N boundary (kN/m)', 'M boundary (kN·m/m)', 'c boundary (mm)', 'phi boundary', 'strain boundary'), 1):
            data[label+' '+key] = nm[:, i]
    data['Temperature minimum D/C'] = np.max(inputs.temperature_minimum(h, steel.fy)/steel.area, axis=1)
    data['Bar spacing D/C'] = np.max(steel.spacing/np.minimum(1.5*h[:, None],18*25.4), axis=1)
    data['Temperature minimum status'] = _status(data['Temperature minimum D/C'])
    data['Bar spacing status'] = _status(data['Bar spacing D/C'])
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


def _summary(rows):
    output = []
    for label, (column, status_column) in VIEWS.items():
        known = rows.loc[rows[column].notna()]
        peak = known.loc[known[column].idxmax()] if len(known) else None
        unknown = rows[status_column].eq('REVIEW')
        status = 'FAIL' if rows[column].gt(1+1e-8).any() else 'REVIEW' if unknown.any() else 'PASS'
        output.append({'Check': label, 'Status': status,
            'Max D/C': peak[column] if peak is not None else np.nan,
            'Case': peak['OutputCase'] if peak is not None else '',
            'Step': peak['StepType'] if peak is not None else '',
            'X (m)': peak['X (m)'] if peak is not None else np.nan,
            'Y (m)': peak['Y (m)'] if peak is not None else np.nan,
            'AreaElem': peak['AreaElem'] if peak is not None else '',
            'Joint': peak['Joint'] if peak is not None else '',
            'Failed nodes': rows.loc[rows[column]>1+1e-8,'Joint'].nunique(),
            'Review nodes': rows.loc[unknown,'Joint'].nunique()})
    return pd.DataFrame(output)


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
    result_rows = pd.concat((frame, checked.reindex(frame.index)), axis=1)
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
    return {'version':VERSION,'fingerprint':fingerprint(state),'code':'AASHTO LRFD 9th Edition (2020)',
        'rows':result_rows,'geometry':geometry,'connections':connections,'steel':steel,
        'summary':summary,'coverage':coverage,'incomplete':incomplete,'peak_ledger':ledger,
        'source_rows':len(frame),'design_rows':len(design),'excluded_rows':int((~frame[INCLUDED]).sum()),
        'geometry_excluded_rows':int((~geometry_mask).sum()),'peak_excluded_rows':int(mask.sum()),
        'exclusion_counts':raw_counts,'axes':axes,'scope':SCOPE,'seconds':time.monotonic()-start,
        'component_status':'FAIL' if summary.Status.eq('FAIL').any() else 'REVIEW' if summary.Status.eq('REVIEW').any() else 'PASS',
        'status':'REVIEW REQUIRED'}


def map_adapter(result, view):
    """Reuse the accepted full-plan chart; all exclusion and coverage rules stay."""
    column,status = VIEWS[view]
    frame=result['rows'].copy(deep=False).assign(**{'Field D/C':result['rows'][column],
        'Status':result['rows'][status],'Combined N–M–V status':result['rows']['Shell coupling status']})
    return {**result,'rows':frame}
