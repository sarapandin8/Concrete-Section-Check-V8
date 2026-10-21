"""Trace local transfer regions and assess AASHTO relief prerequisites.

No unverified area cap, support dv shift or selected-cut comparison can replace
production checks. Local-reaction scope is already handled by the sectional
engine and remains REVIEW in both physical directions.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
import math
import time
from zipfile import ZipFile,ZIP_DEFLATED

import numpy as np
import pandas as pd

from concrete_pmm_pro.analysis import slab_design66 as base,slab_aashto63 as code
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.analysis.slab_sectioncuts68 import CutSource,ACTIONS

VERSION='SLAB.REVIEW68'
RESULT_KEY='slab_shell55_review68_result'
VIEWS=base.VIEWS
METHODS=base.METHODS
save_load_basis=base.save_load_basis


def fingerprint(state):
    value=base.fingerprint(state)
    return hashlib.sha256((VERSION+str(value)).encode()).hexdigest() if value else None


def current(state):
    value=state.get(RESULT_KEY)
    try:
        return value if isinstance(value,dict) and value.get('version')==VERSION and value.get('fingerprint')==fingerprint(state) else None
    except (ValueError,TypeError):
        return None


def governing_vectors(actual):
    records=[]
    rows=actual['rows'].loc[actual['rows'][INCLUDED]]
    faces=actual['support_faces']
    for direction,*_ in code.AXES:
        samples=faces.loc[faces['Target in accepted scope']&faces[INCLUDED]&faces.Direction.eq(direction)] if len(faces) else faces
        all_rows=pd.concat((rows,samples),ignore_index=True) if len(samples) else rows
        for kind in ('shear','tie'):
            c=direction+' '+kind+' D/C'
            for region in ('Sectional scope','Local transfer'):
                source=all_rows
                if region=='Local transfer':
                    source=source.loc[source[direction+' local support region']]
                    c_used=direction+' '+kind+' native D/C'
                else:
                    c_used=c
                if c_used not in source or not source[c_used].notna().any():
                    continue
                row=source.loc[source[c_used].idxmax()]
                fields=['Area','AreaElem','Joint','OutputCase','StepType','StepNum',
                    'X (m)','Y (m)','Thickness (mm)','Record type',*ACTIONS]
                record={k:row[k] for k in fields if k in row}
                phi_f=row[direction+' tie phi_f'];dv=row[direction+' dv (mm)'];theta=row[direction+' theta (deg)']
                record.update({'Direction':direction,'Check':kind,'Region':region,
                    'D/C':float(row[c_used]),'Review status':'REVIEW' if region=='Local transfer' else row[direction+' '+kind+' status'],
                    'M term (kN/m)':abs(row[direction+' Mu (kN·m/m)'])*1000/(dv*phi_f),
                    'N term (kN/m)':row[direction+' Nu (kN/m)']/(2*.75),
                    'V term (kN/m)':abs(row[direction+' Vu (kN/m)'])/.9/math.tan(math.radians(theta)),
                    'Tie demand (kN/m)':row[direction+' tie required (kN/m)'],
                    'Tie capacity (kN/m)':row[direction+' tie capacity (kN/m)'],
                    'dv (mm)':dv,'theta (deg)':theta,
                    'Interpretation':'Local slab/support load transfer; slab-only sectional index is not an acceptance check' if region=='Local transfer' else 'Directional sectional component; retain the separate deck scope review'})
                records.append(record)
    columns=['Direction','Check','Region','Review status','D/C','OutputCase','StepType',
        'X (m)','Y (m)','M term (kN/m)','N term (kN/m)','V term (kN/m)',
        'Tie demand (kN/m)','Tie capacity (kN/m)']
    return pd.DataFrame(records) if records else pd.DataFrame(columns=columns)


def assess(actual,parameters):
    vectors=governing_vectors(actual)
    audit=[]
    for direction in ('Longitudinal','Transverse'):
        audit.extend([
            {'Direction':direction,'Article':'5.7.1.2 / 5.7.3.1','Option':'Finite reaction footprints',
             'Assessment':'LOCAL TRANSFER REVIEW','Applied':True,
             'Evidence':'Existing girder flange / diaphragm geometry. Both sectional directions remain REVIEW over contact patches; source actions and raw indices retained.'},
            {'Direction':direction,'Article':'5.7.3.5','Option':'Maximum-moment reinforcement limit',
             'Assessment':'NOT ESTABLISHED','Applied':False,
             'Evidence':'Four force/mesh exports do not establish the maximum-moment direct-compression load path. A corner ratio or nominal UDL metadata is insufficient evidence.'},
            {'Direction':direction,'Article':'5.7.3.2','Option':'Critical section at dv from support',
             'Assessment':'NOT ESTABLISHED','Applied':False,
             'Evidence':'Reaction direction and absence of a concentrated load inside dv are not established by the four exports. Physical-face sampling retained.'},
        ])
    aggregate=code.aggregate_from_parameters(parameters)
    audit.append({'Direction':'Both','Article':'5.7.3.4.2-7','Option':'Verified aggregate size',
        'Assessment':'APPLIED' if parameters.get('shear_aggregate_confirmed',False) else 'UNVERIFIED; ag=0',
        'Applied':bool(parameters.get('shear_aggregate_confirmed',False)),
        'Evidence':f'ag used = {aggregate:g} mm; existing material input. Simplified beta=2 / theta=45 degrees unaffected.'})
    for face in ('top','bottom'):
        continuous=bool(parameters.get(f'deck_long_rebar_{face}_continuous_confirmed',False))
        anchored=all(bool(parameters.get(f'deck_long_rebar_{face}_{end}_anchored',False)) for end in ('left','right'))
        audit.append({'Direction':'Longitudinal','Article':'5.7.3.5 / 5.10.8','Option':face.title()+' bar continuity / end anchorage',
            'Assessment':'DECLARED IN PROJECT' if continuous and anchored else 'NOT ESTABLISHED','Applied':False,
            'Evidence':'Existing project declarations are reused. They do not independently establish the load path or development along every slab design strip.'})
    cuts=[];cut_errors=[]
    try:
        source=CutSource(actual['rows'],actual['geometry'])
        unique=vectors.drop_duplicates(['Direction','OutputCase','StepType','X (m)','Y (m)']+[c for c in ('StepNum',) if c in vectors])
        for _,row in unique.iterrows():
            window=source.window(row.Direction,[row['X (m)'],row['Y (m)']],actual['supports'])
            case={k:row[k] for k in source.steps}
            for side in ('Minus','Plus'):
                cut=source.integrate(row.Direction,window['station'],window['a'],window['b'],case,side)
                cut.update({'Origin check':row.Check,'Origin region':row.Region,
                    'Origin X (m)':row['X (m)'],'Origin Y (m)':row['Y (m)'],
                    'Reaction footprint':window['reaction_footprint']})
                if cut['Source coverage']:
                    checked=code.section_checks(pd.DataFrame([cut]),actual['steel'],aggregate_mm=aggregate).iloc[0]
                    for kind in ('shear','tie'):
                        cut['Sectional '+kind+' D/C']=checked[row.Direction+' '+kind+' D/C']
                    cut['Coupling review']=any(abs(cut[c])>1e-8 for c in ('Nxy','Mxy')) or abs(cut['Vx']*cut['Vy'])>1e-12
                    cut['Status']='REVIEW'  # selected cuts never certify an envelope or an exception
                cuts.append(cut)
    except ValueError as exc:
        cut_errors.append(str(exc))
    return {'governing_vectors':vectors,'eligibility':pd.DataFrame(audit),'section_cuts':pd.DataFrame(cuts),
        'cut_errors':cut_errors,'status':'REVIEW','exceptions_applied':0,
        'source_actions_changed':False,'new_source_exclusions':0,'full_deck_acceptance':False}


def calculate(state,*,progress=None,reuse=None):
    start=time.monotonic()
    result=base.current(state)
    if result is None:
        result=base.calculate(state,progress=progress,reuse=reuse)
    assessment=assess(result,state.get('section_parameters') or {})
    # Summary / Report consume the stored applied-input result, never this
    # selected-cut comparison. Carry the unresolved local indices with it so
    # a small sectional maximum cannot conceal a local transfer review.
    local=assessment['governing_vectors'].loc[lambda f:f.Region.eq('Local transfer')].copy()
    applied={**result['top65_result'],'local_transfer_review':local}
    result={**result,'top65_result':applied,'local_transfer_review':local}
    return {**result,'version':VERSION,'fingerprint':fingerprint(state),'design66_result':result,
        'code_review':assessment,'review68_seconds':time.monotonic()-start}


def map_adapter(result,view):
    return base.map_adapter(result,view)


def report_zip(result,*,interface=None):
    buffer=BytesIO();review=result['code_review']
    with ZipFile(BytesIO(base.report_zip(result['design66_result'],interface=interface))) as old,ZipFile(buffer,'w',ZIP_DEFLATED) as archive:
        for name in old.namelist():
            archive.writestr(name,old.read(name))
        for name,key in [('Local_and_Sectional_Governing_Vectors','governing_vectors'),('AASHTO_Eligibility','eligibility'),('Selected_Section_Cuts','section_cuts')]:
            archive.writestr('Review68/'+name+'.csv',review[key].to_csv(index=False).encode('utf-8-sig'))
        archive.writestr('Review68/Scope.json',json.dumps({k:review[k] for k in ('status','exceptions_applied','source_actions_changed','new_source_exclusions','full_deck_acceptance','cut_errors')},indent=2))
    return buffer.getvalue()
