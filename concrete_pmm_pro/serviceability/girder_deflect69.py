"""Stage-aware deflection criteria for the existing elastic girder preview.

LL checks use the LL increment, never the remaining prestress camber. Railway
limits are an explicitly labelled project criterion, not an AASHTO highway
rule. This module does not upgrade the existing constant-EI/midspan-Pe model
to a long-term, nonprismatic or cracked-section analysis.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
import math
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import pandas as pd

VERSION = 'SLS.DEFLECT69'
SETTINGS_KEY = 'girder_deflect69_settings'
RESULT_KEY = 'girder_deflect69_result'
PROFILES = {
    'rail_project': 'Railway project · min(L/1500, 30 mm)',
    'aashto_vehicle': 'AASHTO highway · LL+IM L/800',
    'project_360': 'Project · immediate LL L/360',
    'custom': 'Project · custom LL limit',
    'review': 'Review only',
}


def default_profile(state):
    mode = state.get('analysis_mode_settings') or {}
    if hasattr(mode, 'model_dump'):
        mode = mode.model_dump()
    return 'project_360' if 'building' in str(mode.get('analysis_workflow', '')) else 'rail_project'


def settings(state):
    raw = state.get(SETTINGS_KEY) or {}
    result = {'profile': raw.get('profile', default_profile(state))}
    if result['profile'] not in PROFILES:
        raise ValueError('Select a recognized deflection criterion')
    for key in ('custom_limit_mm', 'live_udl_kN_m', 'transfer_limit_mm', 'construction_limit_mm'):
        value = raw.get(key)
        if value is None:
            result[key] = None
            continue
        if isinstance(value, bool):
            raise ValueError(key+' must be numeric')
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValueError(key+' must be numeric') from None
        if not math.isfinite(value) or value < 0 or (key != 'live_udl_kN_m' and value == 0):
            raise ValueError(key+' must be finite and '+('nonnegative' if key == 'live_udl_kN_m' else 'positive'))
        result[key] = value
    return result


def criterion(config, span_m):
    if not math.isfinite(span_m) or span_m <= 0:
        raise ValueError('Deflection span must be finite and positive')
    profile = config['profile']
    if profile == 'rail_project':
        return min(span_m*1000/1500, 30.), 'min(L/1500, 30 mm)', 'Project railway criterion; not an AASHTO highway limit'
    if profile == 'aashto_vehicle':
        return span_m*1000/800, 'L/800', 'AASHTO LRFD 2.5.2.6.2 optional highway LL+IM criterion; loading per 3.6.1.3.2'
    if profile == 'project_360':
        return span_m*1000/360, 'L/360', 'Project immediate live-load criterion; verify member/use category'
    if profile == 'custom':
        return config['custom_limit_mm'], 'Custom LL', 'Project-specified LL increment limit'
    return None, 'Review only', 'No LL acceptance criterion selected'


def _encode(value):
    if isinstance(value, pd.DataFrame):
        return value.to_dict('records')
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if hasattr(value, 'tolist'):
        return value.tolist()
    return str(value)


def fingerprint(state):
    keys = ['section_parameters', 'section_geometry', 'analysis_mode_settings', 'section_preset_key',
        'section_preset_name','concrete_materials','active_concrete_material_name','deck_topping_material_name',
        'girder_strand_layout_table', 'girder_prestress_system_settings', 'girder_prestress_code_loss_settings',
        'beam_girder_system_settings', 'beam_girder_sls_auto_load_settings',
        'building_beam_girder_service_load_settings', 'project_design_code', 'project_code_edition','design_code', 'code_edition']
    payload = {k: state.get(k) for k in keys}
    payload.update(version=VERSION, settings=settings(state))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=_encode).encode()).hexdigest()


def current(state):
    result = state.get(RESULT_KEY)
    try:
        return result if isinstance(result, dict) and result.get('fingerprint') == fingerprint(state) else None
    except (ValueError, TypeError):
        return None


def _extreme(group):
    y = group['Deflection (mm)'].to_numpy(float)
    index = int(np.argmax(abs(y)))
    return float(abs(y[index])), float(group['Station x (m)'].iloc[index])


def calculate(state, source, span_m):
    config = settings(state)
    limit, label, basis = criterion(config, span_m)
    if source.empty or not np.isfinite(source[['Station x (m)', 'Deflection (mm)']].to_numpy(float)).all():
        raise ValueError('Complete finite stage-response curves are required')
    curves = []
    for stage, short in [('Transfer stage', 'Transfer response'), ('Construction stage', 'Construction response'),
                         ('Service stage', 'Sustained · elastic')]:
        group = source.loc[source.Stage.eq(stage)]
        if group.empty:
            raise ValueError('Missing '+stage+' source curve')
        first = group.loc[group.Curve.eq(group.Curve.iloc[0])].sort_values('Station x (m)').copy()
        if first['Station x (m)'].duplicated().any() or not np.allclose(first['Station x (m)'].iloc[[0,-1]], [0, span_m], atol=1e-8):
            raise ValueError('Each stage must cover the whole member, with unique stations from 0 to L')
        first['Curve'] = short
        first['Role'] = 'Net response'
        curves.append(first)
    service = curves[-1]
    existing_w = float(service['Service LL w (kN/m)'].iloc[0])
    w = config['live_udl_kN_m']
    live_source = 'Explicit service LL+IM UDL per girder' if w is not None else 'Existing generated live-load component'
    if w is None and existing_w > 0:
        w = existing_w
    live_available = w is not None
    live = None
    if live_available:
        row = service.iloc[0]
        e, inertia = float(row['E used (MPa)']), float(row['Composite Ix (mm^4)'])
        if not np.isfinite([e,inertia]).all() or min(e,inertia) <= 0:
            raise ValueError('Positive finite composite EI is required for LL deflection')
        x = service['Station x (m)'].to_numpy(float)*1000
        length = span_m*1000
        y = -w*x*(length**3 - 2*length*x*x + x**3)/(24*e*inertia)
        live = service.copy()
        live['Curve'], live['Role'] = 'LL+IM increment', 'Live increment'
        live['Deflection (mm)'] = y
        live['Basis note'] = live_source+'; unfactored service input, no further dynamic/load multiplier'
        live['Service LL w (kN/m)'] = w
        if np.max(abs(y)) > 1e-10:
            loaded = service.copy()
            loaded['Curve'] = 'Net with LL+IM'
            loaded['Deflection (mm)'] = service['Deflection (mm)'].to_numpy()+y
            loaded['Service LL w (kN/m)'] = w
            curves.append(loaded)
        curves.append(live)
    table = []
    for group in curves[:3]:
        stage = group.Stage.iloc[0]
        demand, station = _extreme(group)
        bound = config['transfer_limit_mm'] if stage == 'Transfer stage' else config['construction_limit_mm'] if stage == 'Construction stage' else None
        up, down = max(float(group['Deflection (mm)'].max()),0.), max(-float(group['Deflection (mm)'].min()),0.)
        response = 'CAMBER' if up>.005 and down<.005 else 'DEFLECTION' if down>.005 and up<.005 else 'RESPONSE'
        table.append({'Stage':stage,'Check':'Net elastic response','Response':response,'Demand (mm)':demand,
            'Limit (mm)':bound,'Utilization':demand/bound if bound else np.nan,'x (m)':station,
            'Status':('Preview FAIL' if demand>bound+1e-8 else 'Preview PASS') if bound else 'REVIEW',
            'Basis':'Project absolute-response tolerance' if bound else 'Response only; no universal stage camber limit assigned'})
    demand, station = _extreme(live) if live is not None else (np.nan,np.nan)
    status = 'REVIEW'
    if live_available and limit is not None:
        status = 'NOT REQUIRED' if w == 0 else 'Preview FAIL' if demand>limit+1e-8 else 'Preview PASS'
    table.append({'Stage':'Service stage','Check':'LL+IM increment','Response':'DEFLECTION' if live_available else 'SOURCE MISSING',
        'Demand (mm)':demand,'Limit (mm)':limit,'Utilization':demand/limit if limit else np.nan,'x (m)':station,
        'Status':status,'Basis':basis if live_available else 'LL source missing; prestress camber cannot establish an LL PASS'})
    table.append({'Stage':'Service stage','Check':'Long-term / full response','Response':'NOT CALCULATED',
        'Demand (mm)':np.nan,'Limit (mm)':np.nan,'Utilization':np.nan,'x (m)':np.nan,'Status':'REVIEW',
        'Basis':'Creep/shrinkage, nonprismatic EI, Pe(x), cracked stiffness and track response require their applicable analysis'})
    summary = pd.DataFrame(table)
    return {'version':VERSION,'fingerprint':fingerprint(state),'settings':config,'span_m':span_m,
        'code_edition':str(state.get('project_code_edition') or state.get('code_edition') or 'Project criterion'),
        'curves':pd.concat(curves,ignore_index=True),'source_audit':source.copy(),'summary':summary,
        'limit_mm':limit,'limit_label':label,'limit_basis':basis,'live_available':live_available,
        'live_udl_kN_m':w,'live_source':live_source if live_available else 'Not supplied',
        'status':'Preview FAIL' if summary.Status.eq('Preview FAIL').any() else 'REVIEW REQUIRED',
        'scope':'Instantaneous constant-EI simple-span generated-load preview; midspan effective Pe. No long-term certification.',
        'full_deflection_acceptance':False}


def report_zip(result):
    buffer = BytesIO()
    with ZipFile(buffer,'w',ZIP_DEFLATED) as archive:
        for name,key in [('Checks','summary'),('Curves','curves'),('Generated_Source_Audit','source_audit')]:
            archive.writestr(name+'.csv',result[key].to_csv(index=False).encode('utf-8-sig'))
        archive.writestr('Scope.json',json.dumps({k:result[k] for k in ['version','code_edition','settings','span_m','limit_mm',
            'limit_label','limit_basis','live_available','live_udl_kN_m','live_source','status','scope','full_deflection_acceptance']},indent=2))
    return buffer.getvalue()


def summary_rows(state):
    if RESULT_KEY not in state:
        return []
    result = current(state)
    if result is None:
        return [{'Module':'SLS Deflection','Check':'Stage deflection','Status':'STALE',
            'Required Action':'Calculate deflection / camber again in Analysis.'}]
    return [{'Module':'SLS Deflection','Check':r.Check+' · '+r.Stage,'Status':r.Status,
        'Code Basis':r.Basis,'Governing Case':r.Check,'Station / Point':f"x={r['x (m)']:.3f} m" if pd.notna(r['x (m)']) else '-',
        'Demand':f"{r['Demand (mm)']:.3f} mm" if pd.notna(r['Demand (mm)']) else 'Unavailable',
        'Capacity / Limit':f"{r['Limit (mm)']:.3f} mm" if pd.notna(r['Limit (mm)']) else 'Review',
        'D/C / Util.':float(r.Utilization) if pd.notna(r.Utilization) else None,
        'Required Action':r.Basis,'Source':'Analysis → SLS Deflection / Camber · '+VERSION} for _,r in result['summary'].iterrows()]
