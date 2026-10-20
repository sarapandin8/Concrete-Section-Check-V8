"""AASHTO LRFD 2020 5.12.8.6 punching, isolated rectangular normal-load areas.

No patch size, load factor, vertical shear steel or missing force is invented.
Native force outputs alone do not define the loaded area. Automatic demand is
an explicitly sufficient upper bound from absolute corner shear envelopes,
not an assumed simultaneous sum of moving-load extrema around a perimeter.
An exceeded upper bound is REVIEW, never a fabricated actual-load FAIL.
A supplied factored design Vu provides a direct, independently sourced check.
"""
from __future__ import annotations

import hashlib,json,math
import numpy as np
import pandas as pd
from shapely.geometry import Polygon,LineString,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED

VERSION='SLAB.PUNCHING64'
CONFIG_KEY='slab_punching64'
COLUMNS=['Area','X (m)','Y (m)','L (mm)','B (mm)','Vu (kN, optional)']
KSI=6.894757293
TOL=2e-5


def config(state):
    raw=(state.get('project_metadata') or {}).get(CONFIG_KEY,{})
    return normalise(raw.get('areas',[]) if isinstance(raw,dict) else [])


def normalise(records):
    if isinstance(records,pd.DataFrame):records=records.to_dict('records')
    if records is None:return []
    if not isinstance(records,(list,tuple)):raise ValueError('Punching areas must be a table')
    out=[]
    for i,row in enumerate(records):
        if not isinstance(row,dict):raise ValueError('Each punching area must be a table row')
        if all(row.get(c) is None or pd.isna(row.get(c)) or str(row.get(c)).strip()=='' for c in COLUMNS):continue
        label=row.get('Area')
        record={'Area':str(label).strip() if label is not None and not pd.isna(label) and str(label).strip() else f'P{i+1}'}
        for c in COLUMNS[1:]:
            value=row.get(c)
            if value is None or pd.isna(value) or str(value).strip()=='':record[c]=None;continue
            if isinstance(value,(bool,np.bool_)):raise ValueError(c+' must be numeric')
            try:value=float(value)
            except (TypeError,ValueError):raise ValueError(c+' must be numeric') from None
            if not math.isfinite(value):raise ValueError(c+' must be finite')
            record[c]=value
        if any(record[c] is None for c in COLUMNS[1:5]):
            raise ValueError(record['Area']+': enter X, Y and the loaded-area L/B dimensions')
        if record['L (mm)']<=0 or record['B (mm)']<=0:raise ValueError('Loaded-area dimensions must be positive')
        if record[COLUMNS[-1]] is not None and record[COLUMNS[-1]]<0:raise ValueError('Factored design Vu cannot be negative')
        out.append(record)
    if len({r['Area'] for r in out})!=len(out):raise ValueError('Punching area names must be unique')
    return out


def signature(state):
    return hashlib.sha256(json.dumps({'version':VERSION,'areas':config(state)},sort_keys=True).encode()).hexdigest()


def resistance(fc_MPa,beta_c,b0_mm,dv_mm,*,phi=.9):
    """US source equation converted once to MPa/mm/kN; no added mesh/U Vs."""
    if any(not math.isfinite(v) or v<=0 for v in (fc_MPa,beta_c,b0_mm,dv_mm,phi)):
        raise ValueError('Positive finite punching-resistance inputs required')
    if fc_MPa>15*KSI or beta_c<1-1e-12 or phi>.9:
        raise ValueError('Outside the documented normal-weight AASHTO punching scope')
    coefficient=min(.063+.126/beta_c,.126)
    stress=coefficient*math.sqrt(fc_MPa/KSI)*KSI
    vn=stress*b0_mm*dv_mm/1000
    return {'beta_c':beta_c,'coefficient (US)':coefficient,'vn (MPa)':stress,
        'b0 (mm)':b0_mm,'dv (mm)':dv_mm,'Vn (kN)':vn,'phi':phi,'phiVn (kN)':phi*vn}


def critical_perimeters(bounds,loaded,dv_m):
    """Interior, four edge and four corner paths for a rectangular slab.

    Endpoints on a free edge do NOT add that free edge to resisting b0.
    Select the minimum valid path, not the lowest utilization. This also
    catches edge paths shorter than a closed contour wholly inside the deck.
    """
    xmin,ymin,xmax,ymax=bounds;a,c,b,d=loaded
    if a<xmin-TOL or b>xmax+TOL or c<ymin-TOL or d>ymax+TOL:
        raise ValueError('Loaded area lies outside the slab')
    a-=dv_m/2;b+=dv_m/2;c-=dv_m/2;d+=dv_m/2
    paths=[('Interior',[(a,c),(b,c),(b,d),(a,d),(a,c)]),
        ('Left edge',[(xmin,c),(b,c),(b,d),(xmin,d)]),
        ('Right edge',[(xmax,c),(a,c),(a,d),(xmax,d)]),
        ('Bottom edge',[(a,ymin),(a,d),(b,d),(b,ymin)]),
        ('Top edge',[(a,ymax),(a,c),(b,c),(b,ymax)]),
        ('Left-bottom corner',[(xmin,d),(b,d),(b,ymin)]),
        ('Left-top corner',[(xmin,c),(b,c),(b,ymax)]),
        ('Right-bottom corner',[(xmax,d),(a,d),(a,ymin)]),
        ('Right-top corner',[(xmax,c),(a,c),(a,ymax)])]
    valid=[]
    for label,points in paths:
        xy=np.asarray(points,float)
        if (xy[:,0].min()<xmin-TOL or xy[:,0].max()>xmax+TOL or
            xy[:,1].min()<ymin-TOL or xy[:,1].max()>ymax+TOL):continue
        line=LineString(xy)
        if line.length>TOL:valid.append({'type':label,'points':xy,'length_m':float(line.length)})
    if not valid:raise ValueError('No valid critical punching perimeter')
    return sorted(valid,key=lambda p:(p['length_m'],p['type']))


def _domain(base):
    direction=np.array(next(iter(base['geometry'].parent_axes.values()))['long'][:2],float)
    direction/=np.linalg.norm(direction)
    basis=np.array([direction,[-direction[1],direction[0]]])
    ids=list(base['geometry'].elements)
    polygons=[Polygon(base['geometry'].elements[e][:,:2]@basis.T) for e in ids]
    deck=unary_union(polygons)
    rectangle=box(*deck.bounds)
    rectangular=deck.is_valid and deck.geom_type=='Polygon' and not deck.interiors and deck.symmetric_difference(rectangle).area<max(1e-8,deck.area*1e-8)
    return basis,ids,polygons,deck,rectangular


def _cut_segments(path,tree,polygons,ids,geometry,basis):
    out=[]
    points=path['points']
    for side,(start,end) in enumerate(zip(points[:-1],points[1:])):
        cut=LineString([start,end]);delta=end-start
        component=1 if abs(delta[0])>abs(delta[1]) else 0
        candidates=[]
        for index in tree.query(cut):
            intersection=polygons[index].intersection(cut)
            if intersection.is_empty or intersection.length<=TOL:continue
            if intersection.geom_type!='LineString':
                raise ValueError('Non-simple FE intersection on punching perimeter')
            # For a cut coinciding with an FE edge, choose the FE outside the
            # control region. Both sides of a discontinuous stress field are
            # never added together or averaged.
            midpoint=np.asarray(intersection.interpolate(.5,normalized=True).coords[0])
            # The loaded patch is on the inward side of every valid segment.
            centre=np.asarray(path['centre'])
            normal=np.array([-delta[1],delta[0]])/np.linalg.norm(delta)
            if np.dot(centre-midpoint,normal)>0:normal=-normal
            vertices=np.asarray(polygons[index].exterior.coords)[:-1]
            if np.max((vertices-midpoint)@normal)<=TOL:continue
            p=np.asarray(intersection.coords)
            from concrete_pmm_pro.analysis.slab_shell56_geometry import inverse_quad
            # Nonzero shape-function support over this segment. On an FE
            # edge only its two corners are used; an interior cut uses four.
            gauss=[p[0],p[-1],p.mean(axis=0)]
            weights=np.array([inverse_quad(vertices,v) for v in gauss])
            active=np.flatnonzero(weights.max(axis=0)>1e-8)
            corner=geometry.corners.loc[geometry.corners.AreaElem.eq(ids[index])]
            joints=corner.Joint.to_numpy()[active]
            candidates.append(intersection)
            out.append({'Side':side,'AreaElem':ids[index],'Joints':joints.tolist(),
                'Component':'Vy' if component else 'Vx','Length (m)':float(intersection.length),
                'Start':p[0].tolist(),'End':p[-1].tolist()})
        length=sum(p.length for p in candidates)
        union=unary_union(candidates).length if candidates else 0.
        if abs(length-cut.length)>max(TOL,cut.length*1e-6) or abs(length-union)>TOL:
            raise ValueError('Incomplete / overlapping FE coverage on punching perimeter')
    return out


def calculate(base,areas):
    areas=normalise(areas)
    if not areas:
        return {'version':VERSION,'status':'NOT CALCULATED','rows':pd.DataFrame(),
            'areas':[],'paths':{},'segments':pd.DataFrame(),
            'reason':'Define the position and L/B dimensions of the physical load/reaction area.'}
    basis,ids,polygons,deck,rectangular=_domain(base)
    tree=STRtree(polygons)
    frame=base['rows']
    # A corner-wise absolute envelope is used ONLY to bound punching force;
    # it never becomes an invented simultaneous design vector.
    group=['AreaElem','Joint','OutputCase']
    envelopes=frame.assign(_vxb=frame.Vx.abs(),_vyb=frame.Vy.abs(),_finite=np.isfinite(frame.Vx)&np.isfinite(frame.Vy)).groupby(group,dropna=False).agg(
        vx=('_vxb','max'),vy=('_vyb','max'),included=(INCLUDED,'all'),finite=('_finite','all'))
    cases=list(dict.fromkeys(frame.OutputCase))
    steps=['OutputCase','StepType']+(['StepNum'] if 'StepNum' in frame else [])
    case_steps=frame[steps].drop_duplicates().groupby('OutputCase').size()
    sizes=frame.groupby(group,dropna=False).size()
    distinct=frame[group+steps[1:]].drop_duplicates().groupby(group,dropna=False).size()
    envelopes['complete']=[int(sizes.loc[k])==int(distinct.loc[k])==int(case_steps.loc[k[2]]) for k in envelopes.index]
    rows=[];paths={};all_segments=[];definitions=[]
    for area in areas:
        centre=np.array([area['X (m)'],area['Y (m)']])@basis.T
        l,b=area['L (mm)']/1000,area['B (mm)']/1000
        loaded=box(centre[0]-l/2,centre[1]-b/2,centre[0]+l/2,centre[1]+b/2)
        nearby=tree.query(loaded)
        h_values=[]
        for idx in nearby:
            h_values.extend(base['geometry'].corners.loc[lambda f:f.AreaElem.eq(ids[idx]),'Thickness (mm)'].tolist())
        h=float(min(h_values)) if h_values else np.nan
        definitions.append((area,centre,loaded,h))
    for area,centre,loaded,h in definitions:
        name=area['Area'];reason=[];capacity={};path=None;segments=[]
        try:
            if not rectangular:raise ValueError('Irregular deck / openings require a dedicated critical-perimeter assessment')
            if not math.isfinite(h):raise ValueError('No slab thickness at this loaded area')
            cover=float(max(base['steel'].centre))
            dv=max(.9*(h-cover),.72*h)
            choices=critical_perimeters(deck.bounds,loaded.bounds,dv/1000)
            path=choices[0];path['centre']=centre;path['basis']=basis
            paths[name]=path
            control=loaded.buffer(dv/2000,join_style=2)
            close=tree.query(control)
            corners=base['geometry'].corners.loc[lambda f:f.AreaElem.isin([ids[i] for i in close])]
            if corners['Thickness (mm)'].max()-corners['Thickness (mm)'].min()>.05:
                raise ValueError('Thickness change requires additional critical perimeters (5.12.8.6.1)')
            for parent in corners.Area.unique():
                normal=np.array(base['geometry'].parent_axes[parent]['up'])
                if normal[2]<1-1e-8:
                    raise ValueError('Inclined / folded slab requires a surface-based punching assessment')
            for other,c2,p2,h2 in definitions:
                if other['Area']==name:continue
                dv2=max(.9*(h2-cover),.72*h2) if math.isfinite(h2) else dv
                if control.intersection(p2.buffer(dv2/2000,join_style=2)).area>TOL*TOL:
                    raise ValueError('Overlapping load-area perimeters require a combined envelope (5.12.8.6.3)')
            # A critical surface cannot claim concrete resistance through a
            # linear girder/diaphragm bearing footprint.
            critical=LineString(path['points'])
            perimeter_elements=[ids[i] for i in tree.query(critical)]
            cut_corners=base['geometry'].corners.loc[lambda f:f.AreaElem.isin(perimeter_elements)]
            if cut_corners['Thickness (mm)'].max()-cut_corners['Thickness (mm)'].min()>.05:
                raise ValueError('Thickness change on critical surface requires additional perimeters (5.12.8.6.1)')
            if any(base['geometry'].parent_axes[p]['up'][2]<1-1e-8 for p in cut_corners.Area.unique()):
                raise ValueError('Inclined critical surface requires a surface-based punching assessment')
            for support in base.get('supports',[]):
                p1,p2=support['a']@basis.T,support['b']@basis.T
                footprint=LineString([p1,p2]).buffer(support['half_width'],cap_style=2)
                if critical.intersection(footprint).length>TOL:
                    raise ValueError('Critical surface crosses a linear support footprint; local load/reaction path requires review')
            capacity=resistance(base['steel'].fc,max(l,b)/min(l,b),path['length_m']*1000,dv)
            segments=_cut_segments(path,tree,polygons,ids,base['geometry'],basis)
        except (ValueError,KeyError,TypeError) as exc:
            reason.append(str(exc))
        manual=area['Vu (kN, optional)']
        for case in (['User design Vu'] if manual is not None else cases):
            result={'Area':name,'Case':case,'X (m)':area['X (m)'],'Y (m)':area['Y (m)'],
                'L (mm)':area['L (mm)'],'B (mm)':area['B (mm)'],'Thickness (mm)':h,
                'Perimeter type':path['type'] if path else '',
                **{k:np.nan for k in ('beta_c','coefficient (US)','vn (MPa)','b0 (mm)','dv (mm)','Vn (kN)','phi','phiVn (kN)')},**capacity,
                'Demand basis':'Direct factored design shear' if manual is not None else 'Absolute native-corner envelope upper bound',
                'Vu (kN)':np.nan,'D/C':np.nan,'Status':'REVIEW','Reason':'; '.join(reason)}
            if not reason:
                vu=float(manual) if manual is not None else 0.
                problems=[]
                if manual is None:
                    for segment in segments:
                        values=[]
                        for joint in segment['Joints']:
                            key=(segment['AreaElem'],joint,case)
                            if key not in envelopes.index:
                                problems.append('Missing corner / case');continue
                            source=envelopes.loc[key]
                            if not source['included']:
                                problems.append('Previously excluded source corner');continue
                            if not source['complete']:
                                problems.append('Incomplete case/step coverage');continue
                            if not source['finite']:
                                problems.append('Non-finite source shear');continue
                            value=float(source.vx if segment['Component']=='Vx' else source.vy)
                            if not math.isfinite(value):
                                problems.append('Non-finite source shear');continue
                            values.append(value)
                        if len(values)!=len(segment['Joints']):continue
                        q=max(values)
                        vu+=q*segment['Length (m)']
                        all_segments.append({'Area':name,'Case':case,**segment,'q upper (kN/m)':q})
                if problems:
                    result['Reason']='; '.join(sorted(set(problems)))
                else:
                    dc=vu/capacity['phiVn (kN)']
                    result.update({'Vu (kN)':vu,'D/C':dc,
                        'Status':('FAIL' if dc>1+1e-8 else 'PASS') if manual is not None else
                            ('REVIEW' if dc>1+1e-8 else 'PASS (sufficient)'),
                        'Reason':('Factored design Vu exceeds resistance' if dc>1+1e-8 else 'Direct force-component check passes') if manual is not None else
                            ('Conservative demand bound exceeded; actual perimeter force required' if dc>1+1e-8 else 'Upper demand bound is below code resistance')})
            rows.append(result)
    rows=pd.DataFrame(rows)
    status='FAIL' if rows.Status.eq('FAIL').any() else 'REVIEW' if rows.Status.eq('REVIEW').any() else 'PASS (sufficient)' if rows.Status.eq('PASS (sufficient)').any() else 'PASS'
    return {'version':VERSION,'status':status,'rows':rows,'areas':areas,'paths':paths,
        'segments':pd.DataFrame(all_segments),'reason':'Isolated rectangular normal-force punching component; moment-transfer / local support acceptance remains separate.'}
