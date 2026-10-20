"""Read-only spatial sensitivity studies, separate from nominal design checks.

Peak screening is a fixed one-pass heuristic, not proof of FEM error. Zone
means are retained-sample plan-area averages, not equilibrated design strips.
"""
from __future__ import annotations
from types import SimpleNamespace
import time
import warnings
import numpy as np
import pandas as pd
from concrete_pmm_pro.analysis import slab_shell56 as engine
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED, REASON, TOLERANCE
from concrete_pmm_pro.analysis.slab_code57 import strip_references, controlling_checks

VERSION='SLAB.REVIEW61'
RESULT_KEY='slab_shell61_sensitivity_review'
RAW='Nominal nodes'
FILTERED='Peaks excluded · study'
ZONES='Zone averages · study'
BASES=[RAW,FILTERED,ZONES]
ACTIONS=['Nx','Ny','Nxy','Mx','My','Mxy','Vx','Vy']
RATIO_LIMIT,Z_LIMIT,MIN_NEIGHBOURS=2.,3.5,4
PEAK='Peak excluded'
STUDY_INCLUDED='Study included'
WEIGHT='Corner sample area (m²)'


def step_columns(rows):
    return [c for c in ('OutputCase','StepType','StepNum') if c in rows]


def current(state,nominal):
    s=state.get(RESULT_KEY)
    return s if isinstance(s,dict) and s.get('version')==VERSION and s.get('fingerprint')==nominal.get('fingerprint') else None


def quad_weights(points):
    """Integrate bilinear corner shape functions over projected plan area."""
    p=np.asarray(points,float)[:,:2]
    if p.shape!=(4,2) or not np.isfinite(p).all():
        raise ValueError('Zone averaging requires four finite ordered plan corners')
    weights=np.zeros(4);signs=[]
    for u in (-1/np.sqrt(3),1/np.sqrt(3)):
        for v in (-1/np.sqrt(3),1/np.sqrt(3)):
            n=np.array([(1-u)*(1-v),(1+u)*(1-v),(1+u)*(1+v),(1-u)*(1+v)])/4
            du=np.array([-(1-v),1-v,1+v,-(1+v)])/4
            dv=np.array([-(1-u),-(1+u),1+u,1-u])/4
            det=np.linalg.det(np.column_stack((du@p,dv@p)));signs.append(det)
            weights+=n*abs(det)
    if min(abs(np.asarray(signs)))<=1e-12 or min(signs)*max(signs)<=0:
        raise ValueError('Degenerate / folded plan quad cannot be averaged')
    return weights


def force_indicators(rows):
    n=rows[ACTIONS[:3]].to_numpy(float)
    m=6*rows[ACTIONS[3:6]].to_numpy(float)/(rows['Thickness (mm)'].to_numpy(float)[:,None]/1000)
    def norm(t):return np.sqrt(t[:,0]**2+t[:,1]**2+2*t[:,2]**2)
    return np.column_stack((np.maximum(norm(n+m),norm(n-m)),np.linalg.norm(rows[ACTIONS[6:]].to_numpy(float),axis=1)))


def peak_screen(nominal):
    """Label isolated node/case/step peaks using original neighbours once.

    Requires >=4 retained one-ring neighbours, an opposing collinear pair,
    strict local maximum, ratio >2 and modified score >3.5. Shared-node
    unaveraged element maxima are used. No rebar or D/C enters this rule.
    """
    rows,geo=nominal['rows'],nominal['geometry'];steps=step_columns(rows)
    source=rows.loc[rows[INCLUDED]].copy()
    nodes=geo.corners.drop_duplicates('Joint').set_index('Joint')
    ids=list(nodes.index);index={j:i for i,j in enumerate(ids)};adj=[set() for _ in ids]
    ji=geo.corners['Joint'].map(index).to_numpy(int)
    for positions in geo.corners.groupby('AreaElem',sort=False).indices.values():
        members=ji[positions]
        for i in members:adj[i].update(j for j in members if j!=i)
    padded=np.full((len(ids),max(1,max(map(len,adj),default=0))),len(ids),int)
    for i,members in enumerate(adj):padded[i,:len(members)]=sorted(members)
    xy=nodes[['X (m)','Y (m)']].to_numpy(float)
    direction=np.array(next(iter(geo.parent_axes.values()))['long'][:2],float,copy=True)
    direction/=np.linalg.norm(direction);normal=np.array([-direction[1],direction[0]])
    local=xy@np.column_stack((direction,normal))
    delta=np.vstack((local,[[np.nan,np.nan]]))[padded]-local[:,None,:]
    line_x,line_y=abs(delta[:,:,1])<TOLERANCE,abs(delta[:,:,0])<TOLERANCE
    source[['NM magnitude','V magnitude']]=force_indicators(source)
    elements=source['AreaElem'].to_dict();diagnostics=[];excluded_keys=[]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        for key,group in source.groupby(steps,sort=False,dropna=False):
            key=key if isinstance(key,tuple) else (key,)
            grouped=group.groupby('Joint')[['NM magnitude','V magnitude']]
            matrix=grouped.max().reindex(ids).to_numpy(float)
            governors=grouped.idxmax().reindex(ids).to_numpy()
            near=np.vstack((matrix,[[np.nan,np.nan]]))[padded];present=np.isfinite(near[:,:,0])
            bracket=((line_x&present&(delta[:,:,0]<-TOLERANCE)).any(1)&(line_x&present&(delta[:,:,0]>TOLERANCE)).any(1))|((line_y&present&(delta[:,:,1]<-TOLERANCE)).any(1)&(line_y&present&(delta[:,:,1]>TOLERANCE)).any(1))
            median=np.nanmedian(near,axis=1);mad=np.nanmedian(abs(near-median[:,None,:]),axis=1)
            count=np.isfinite(near).sum(1);floor=np.maximum(abs(median)*1e-12,1e-9)
            ratio=matrix/np.maximum(median,floor);score=.67448975*(matrix-median)/np.maximum(mad,floor)
            highest=np.nanmax(near,axis=1)
            flag=(count>=MIN_NEIGHBOURS)&bracket[:,None]&(matrix>highest)&(ratio>RATIO_LIMIT)&(score>Z_LIMIT)
            for i,c in zip(*np.where(flag)):
                adjacent=[ids[j] for j in padded[i] if j<len(ids) and np.isfinite(matrix[j,c])]
                diagnostics.append({**dict(zip(steps,key)),'Joint':ids[i],'X (m)':xy[i,0],'Y (m)':xy[i,1],
                    'Indicator':['NM magnitude','V magnitude'][c],'Source AreaElem':elements[governors[i,c]],
                    'Magnitude (kN/m)':matrix[i,c],'Neighbour median (kN/m)':median[i,c],
                    'Neighbour MAD (kN/m)':mad[i,c],'Neighbour max (kN/m)':highest[i,c],
                    'Ratio to median':ratio[i,c],'Modified score':score[i,c],'Neighbour count':count[i,c],
                    'Neighbour joints':', '.join(adjacent),'Review status':'Unverified peak label'})
                excluded_keys.append((*key,ids[i]))
    columns=[*steps,'Joint','X (m)','Y (m)','Indicator','Source AreaElem','Magnitude (kN/m)',
        'Neighbour median (kN/m)','Neighbour MAD (kN/m)','Neighbour max (kN/m)',
        'Ratio to median','Modified score','Neighbour count','Neighbour joints','Review status']
    ledger=pd.DataFrame(diagnostics,columns=columns);mask=pd.Series(False,index=rows.index)
    if excluded_keys:
        flags=pd.MultiIndex.from_tuples(excluded_keys,names=[*steps,'Joint'])
        mask=pd.Series(pd.MultiIndex.from_frame(rows[[*steps,'Joint']]).isin(flags),index=rows.index)&rows[INCLUDED]
    return mask,ledger


def zone_layout(nominal):
    """Native parent Area longitudinal segment x transverse mesh row.

    Requires rectangular aligned plan mesh. No automatic averaging across an
    identified girder / finite diaphragm or a gap in the geometry.
    """
    geo=nominal['geometry'];corners=geo.corners
    direction=np.array(next(iter(geo.parent_axes.values()))['long'][:2],float,copy=True)
    direction/=np.linalg.norm(direction);basis=np.column_stack((direction,[-direction[1],direction[0]]))
    points=corners[['X (m)','Y (m)','Z (m)']].to_numpy(float);local=points[:,:2]@basis
    h=corners['Thickness (mm)'].to_numpy(float);parents=corners['Area'].to_numpy()
    weights=np.empty(len(corners));labels=np.empty(len(corners),object);tokens={};positions_by_zone={}
    for element,positions in corners.groupby('AreaElem',sort=False).indices.items():
        p,q=points[positions],local[positions];low,high=q.min(0),q.max(0)
        on_bounds=np.isclose(q,low,atol=TOLERANCE,rtol=0)|np.isclose(q,high,atol=TOLERANCE,rtol=0)
        if not on_bounds.all() or np.any(high-low<=TOLERANCE):
            raise ValueError('Automatic zone study requires rectangular plan mesh aligned with the straight bridge axes')
        token=(str(parents[positions[0]]),round(low[1]/TOLERANCE),round(high[1]/TOLERANCE))
        if token not in tokens:tokens[token]=f'Z{len(tokens)+1:04d}'
        zone=tokens[token];labels[positions]=zone;weights[positions]=quad_weights(p)
        positions_by_zone.setdefault(zone,[]).append(positions)
    mapping=corners[['Area','AreaElem','Joint']].copy();mapping[WEIGHT]=weights;mapping['Zone']=labels
    lines=[]
    for line in nominal.get('connections',{}).get('lines',pd.DataFrame()).to_dict('records'):
        ends=np.array([[line['X1 (m)'],line['Y1 (m)']],[line['X2 (m)'],line['Y2 (m)']]])@basis
        lines.append((ends.min(0),ends.max(0)))
    zones=[];polygons={}
    for zone,members in positions_by_zone.items():
        positions=np.concatenate(members);p,q=points[positions],local[positions];low,high=q.min(0),q.max(0)
        xy=np.array([[low[0],low[1]],[high[0],low[1]],[high[0],high[1]],[low[0],high[1]]])@basis.T
        area=float(weights[positions].sum())
        if not np.isclose(area,np.prod(high-low),rtol=1e-5,atol=1e-8):
            raise ValueError('A zone has a gap / overlap; it cannot be averaged as a continuous strip')
        for a,b in lines:
            crosses=((b[0]-a[0]<TOLERANCE and low[0]+TOLERANCE<a[0]<high[0]-TOLERANCE and min(high[1],b[1])-max(low[1],a[1])>TOLERANCE) or (b[1]-a[1]<TOLERANCE and low[1]+TOLERANCE<a[1]<high[1]-TOLERANCE and min(high[0],b[0])-max(low[0],a[0])>TOLERANCE))
            if crosses:raise ValueError('A native zone crosses a girder / diaphragm; automatic averaging is unavailable')
        polygons[zone]=np.column_stack((xy,np.full(4,p[:,2].mean())))
        zones.append({'Zone':zone,'Area':str(parents[positions[0]]),'Full sample area (m²)':area,
            'Length (m)':high[0]-low[0],'Width (m)':high[1]-low[1],
            'Thickness min (mm)':h[positions].min(),'Thickness max (mm)':h[positions].max(),
            'X centre (m)':xy[:,0].mean(),'Y centre (m)':xy[:,1].mean()})
    return mapping,pd.DataFrame(zones),polygons


def zone_means(nominal,peak_mask):
    mapping,layout,polygons=zone_layout(nominal)
    rows=nominal['rows'].merge(mapping,on=['Area','AreaElem','Joint'],how='left',validate='many_to_one')
    if rows[WEIGHT].isna().any():raise ValueError('Missing zone quadrature weights')
    rows[PEAK]=np.asarray(peak_mask,bool);rows[STUDY_INCLUDED]=rows[INCLUDED]&~rows[PEAK]
    keys=[*step_columns(rows),'Zone']
    full=rows.groupby(keys,dropna=False,sort=False).agg(**{'Imported sample area (m²)':(WEIGHT,'sum'),'Source records':(WEIGHT,'size')}).reset_index()
    keep=rows.loc[rows[STUDY_INCLUDED]].copy()
    for action in ACTIONS:
        keep['_weighted '+action]=keep[action]*keep[WEIGHT];keep['_absolute '+action]=abs(keep[action])*keep[WEIGHT]
    for c in ('X (m)','Y (m)'):keep['_weighted '+c]=keep[c]*keep[WEIGHT]
    groups=keep.groupby(keys,dropna=False,sort=False);weights=groups[WEIGHT].sum();data=weights.to_frame('Retained sample area (m²)')
    for action in ACTIONS:
        data[action]=groups['_weighted '+action].sum()/weights
        data['Mean abs '+action]=groups['_absolute '+action].sum()/weights
        data['Sign change '+action]=(groups[action].min()<-1e-8)&(groups[action].max()>1e-8)
    for c in ('X (m)','Y (m)'):data[c]=groups['_weighted '+c].sum()/weights
    data=full.merge(data.reset_index(),on=keys,how='left',validate='one_to_one').merge(layout,on='Zone',validate='many_to_one')
    data['Retained sample area (m²)']=data['Retained sample area (m²)'].fillna(0.)
    data['Sample area coverage']=data['Retained sample area (m²)']/data['Full sample area (m²)']
    data['Source area coverage']=data['Imported sample area (m²)']/data['Full sample area (m²)']
    data['Source incomplete']=data['Source area coverage']<1-1e-8
    data['Thickness (mm)']=data['Thickness min (mm)'];data[INCLUDED]=data['Retained sample area (m²)']>0
    data[REASON]=np.where(data[INCLUDED],'','No retained samples in zone')
    for c in ('X','Y'):data[c+' (m)']=data[c+' (m)'].fillna(data[c+' centre (m)'])
    part=data.loc[data[INCLUDED]]
    checks=engine.section_check(part['Thickness (mm)'].to_numpy(),part[ACTIONS[:3]].to_numpy(),part[ACTIONS[3:6]].to_numpy(),part[ACTIONS[6:]].to_numpy(),nominal['steel']);checks.index=part.index
    refs=strip_references(part['Thickness (mm)'].to_numpy(),part[ACTIONS[:3]].to_numpy(),part[ACTIONS[3:6]].to_numpy(),nominal['steel']);refs.index=part.index
    data=pd.concat((data,checks.reindex(data.index),refs.reindex(data.index)),axis=1)
    data['Controlling check']=controlling_checks(data);data['Status']='REVIEW';data['AreaElem']=data['Zone'];data['Joint']='Zone mean'
    for c in ['F11','F22','F12','M11','M22','M12','V13','V23']:data[c]=np.nan
    corners=pd.DataFrame([{'Area':z,'AreaElem':z,'Joint':f'{z}-{i}','X (m)':p[0],'Y (m)':p[1],'Z (m)':p[2]} for z,poly in polygons.items() for i,p in enumerate(poly)])
    return data,layout,SimpleNamespace(corners=corners,elements=polygons,parent_axes=nominal['geometry'].parent_axes),rows


def comparison(original,filtered,zones):
    metrics=[('N–M field','N–M field D/C'),('One-way shear','Shear D/C'),*[(g,g+' D/C') for g in engine.GROUPS],('Concrete compression','Concrete D/C')];result=[]
    for label,column in metrics:
        record={'Check':label}
        for prefix,rows in [('Nominal',original),('Peaks excluded',filtered),('Zone mean',zones)]:
            valid=rows.loc[rows[column].notna()];record[prefix+' max D/C']=valid[column].max() if len(valid) else np.nan
            if len(valid):
                r=valid.loc[valid[column].idxmax()];record[prefix+' location']=f"X={r['X (m)']:.3f}, Y={r['Y (m)']:.3f} · {r['OutputCase']} / {r['StepType']}"
            else:record[prefix+' location']='Unavailable / REVIEW'
        record['Study status']='REVIEW REQUIRED';result.append(record)
    return pd.DataFrame(result)


def calculate(nominal):
    start=time.monotonic();mask,ledger=peak_screen(nominal);error=None
    try:zones,layout,geo,source=zone_means(nominal,mask)
    except ValueError as exc:
        error=str(exc);zones=pd.DataFrame();layout=pd.DataFrame();geo=None
        source=nominal['rows'].copy();source[PEAK]=mask;source[STUDY_INCLUDED]=source[INCLUDED]&~source[PEAK]
    original=source.loc[source[INCLUDED]];kept=source.loc[source[STUDY_INCLUDED]]
    checked_zones=zones.loc[zones[INCLUDED]] if len(zones) else original.iloc[:0]
    return {'version':VERSION,'fingerprint':nominal.get('fingerprint'),'source':source,'ledger':ledger,
        'zone_rows':zones,'zone_layout':layout,'zone_geometry':geo,'zone_error':error,
        'comparison':comparison(original,kept,checked_zones),'excluded_records':int(mask.sum()),
        'excluded_nodes':int(source.loc[source[PEAK],'Joint'].nunique()),
        'excluded_node_cases':len(ledger[[*step_columns(source),'Joint']].drop_duplicates()),
        'retained_records':len(kept),'status':'REVIEW REQUIRED','seconds':time.monotonic()-start}


def map_result(nominal,study,basis):
    """Ephemeral chart adapter, never stored as the nominal RESULT_KEY."""
    if basis==RAW:return nominal
    out=dict(nominal)
    if basis==FILTERED:
        rows=study['source'].copy();rows[INCLUDED]=rows[STUDY_INCLUDED]
        rows.loc[rows[PEAK],REASON]='Isolated peak excluded for sensitivity study';out['rows']=rows
    elif basis==ZONES:
        if study['zone_error']:raise ValueError(study['zone_error'])
        out['rows']=study['zone_rows'];out['geometry']=study['zone_geometry'];out['samples_per_element']=1
    else:raise ValueError('Unknown slab review basis')
    out['status']='REVIEW REQUIRED';out['study_basis']=basis
    return out
