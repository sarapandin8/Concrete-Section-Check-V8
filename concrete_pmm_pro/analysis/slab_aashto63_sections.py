"""Geometric support-face sampling; no force threshold or new peak filter.

The conservative default is the physical face, never an assumed dv relaxation.
Every interpolated eight-component vector belongs to one element/case/step.
A nonzero interpolation weight on any previously omitted or missing corner
makes that sample unavailable. Native rows and the REVIEW61 masks are intact.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED, REASON, TOLERANCE
from concrete_pmm_pro.analysis.slab_review61 import step_columns

ACTIONS = ['Nx','Ny','Nxy','Mx','My','Mxy','Vx','Vy']
NATIVE = ['F11','F22','F12','M11','M22','M12','V13','V23']
GEOMETRY = ['X (m)','Y (m)','Z (m)','Thickness (mm)']


def support_geometry(connections,package=None):
    """Girder contact faces from the existing physical flange width.

    Diaphragm widths come from constant native shell thickness overwrites.
    No contact width or bearing length is invented when unavailable.
    """
    width = connections.get('top_flange_mm')
    lines = connections['lines']
    if lines.empty:
        return []
    output = []
    counts={'Girder':0,'Diaphragm':0}
    for row in lines.to_dict('records'):
        kind=row['Connection']
        if kind=='Girder':
            actual_width=width/1000. if width and np.isfinite(width) and width>0 else None
        elif kind=='Diaphragm' and package is not None:
            ids=[item.strip() for item in str(row['ID']).split(',')]
            table=package.tables['thickness'].set_index('Area')
            if not set(ids).issubset(table.index):
                continue
            values=table.loc[ids,['Thick1','Thick2','Thick3','Thick4']].to_numpy(float)
            actual_width=float(values.flat[0]) if (np.isfinite(values).all() and
                values.min()>0 and np.ptp(values)<=TOLERANCE) else None
        else:
            continue
        if actual_width is None:
            continue
        counts[kind]+=1
        a = np.array([row['X1 (m)'],row['Y1 (m)']])
        b = np.array([row['X2 (m)'],row['Y2 (m)']])
        unit = (b-a)/np.linalg.norm(b-a)
        normal = np.array([-unit[1],unit[0]])
        output.append({'Support':f'{kind} {counts[kind]}','Kind':kind,
            'Direction':'Transverse' if kind=='Girder' else 'Longitudinal',
            'a':a,'b':b,'unit':unit,'normal':normal,'half_width':actual_width/2,
            'basis':('Existing I-girder top-flange width' if kind=='Girder' else 'Native constant diaphragm shell thickness')+
                '; full contact assumed; local interface not certified'})
    return output


def in_support(points, supports):
    mask = np.zeros(len(points),bool)
    for support in supports:
        delta = points-support['a']
        along, across = delta@support['unit'], abs(delta@support['normal'])
        mask |= ((along >= -TOLERANCE) &
                 (along <= np.linalg.norm(support['b']-support['a'])+TOLERANCE) &
                 (across < support['half_width']-TOLERANCE))
    return mask


def face_recipes(geometry, supports):
    """Intersections of straight support faces with native FE polygon edges.

    Edge values are linear FE output interpolation, not extrapolation, force
    smoothing, cross-element averaging or a synthetic component envelope.
    Adjacent elements retain their own output discontinuities.
    """
    output = []
    corners = geometry.corners
    for element, group in corners.groupby('AreaElem',sort=False):
        points = group[['X (m)','Y (m)']].to_numpy(float)
        joints = group.Joint.to_numpy()
        area = group.Area.iloc[0]
        for support in supports:
            # Check shear normal to the relevant physical support axis.
            direction = np.array(geometry.parent_axes[area]['long'][:2])
            direction /= np.linalg.norm(direction)
            if support.get('Direction','Transverse')=='Longitudinal':
                direction=np.array([-direction[1],direction[0]])
            if abs(support['unit']@direction) < 1-1e-8:
                raise ValueError('Support faces are skewed relative to the physical slab reinforcement directions')
            for sign in (-1,1):
                origin = support['a']+sign*support['half_width']*support['normal']
                distance = (points-origin)@support['normal']
                if distance.min()>TOLERANCE or distance.max() < -TOLERANCE:
                    continue
                # The FE must have actual clear-span/overhang area beyond
                # this face. Its centroid may lie inside a broad support;
                # rejecting by centroid would silently lose valid cuts.
                if float(np.max(sign*distance)) <= TOLERANCE:
                    continue
                candidates = []
                for i in range(4):
                    j = (i+1)%4
                    if abs(distance[i]) <= TOLERANCE:
                        candidates.append((i,i,0.,points[i]))
                    if distance[i]*distance[j] < -TOLERANCE**2:
                        weight = distance[i]/(distance[i]-distance[j])
                        candidates.append((i,j,float(weight),(1-weight)*points[i]+weight*points[j]))
                unique = []
                for recipe in candidates:
                    if not any(np.linalg.norm(recipe[3]-other[3]) <= TOLERANCE for other in unique):
                        unique.append(recipe)
                for endpoint,(i,j,weight,point) in enumerate(unique):
                    along = float((point-support['a'])@support['unit'])
                    if not -TOLERANCE<=along<=np.linalg.norm(support['b']-support['a'])+TOLERANCE:
                        continue
                    output.append({'Area':area,'AreaElem':element,'Support':support['Support'],
                        'Direction':support.get('Direction','Transverse'),
                        'Face':'Minus' if sign<0 else 'Plus','Endpoint':endpoint,
                        'Source joint 1':joints[i],'Source joint 2':joints[j],
                        'Weight 2':weight,'X target (m)':point[0],'Y target (m)':point[1],
                        'Section basis':'5.7.3.2 conservative support face; no dv reduction'})
    return pd.DataFrame(output)


def sample_faces(rows, geometry, supports):
    recipes = face_recipes(geometry,supports)
    if recipes.empty:
        return pd.DataFrame(), recipes
    steps = step_columns(rows)
    cases = rows[steps].drop_duplicates()
    target = recipes.merge(cases,how='cross')
    keys = ['Area','AreaElem','Joint',*steps]
    index = pd.MultiIndex.from_frame(rows[keys])
    if not index.is_unique:
        raise ValueError('Support-face sampling requires unique native corner/case/step keys')
    def positions(column):
        frame = target[['Area','AreaElem',column,*steps]].rename(columns={column:'Joint'})
        return index.get_indexer(pd.MultiIndex.from_frame(frame))
    left,right = positions('Source joint 1'),positions('Source joint 2')
    missing = (left<0)|(right<0)
    l,r = np.maximum(left,0),np.maximum(right,0)
    values = rows[[*GEOMETRY,*ACTIONS,*NATIVE]].to_numpy(float)
    weight = target['Weight 2'].to_numpy(float)
    interpolated = values[l]*(1-weight[:,None])+values[r]*weight[:,None]
    omitted = (~rows[INCLUDED].to_numpy(bool)[l] & (weight<1-1e-12)) | (~rows[INCLUDED].to_numpy(bool)[r] & (weight>1e-12))
    valid = ~(missing|omitted)
    target = pd.concat((target.reset_index(drop=True),pd.DataFrame(interpolated,columns=[*GEOMETRY,*ACTIONS,*NATIVE])),axis=1)
    target['Joint'] = (target['Support']+'/'+target.Face+'/'+target['Source joint 1'].astype(str)+'→'+target['Source joint 2'].astype(str))
    target['Record type'] = 'Support face'
    target[INCLUDED] = valid
    target[REASON] = np.select([missing,omitted],['Missing source corner/case','Previously excluded source corner'],default='')
    target['Source incomplete'] = ~valid
    target.loc[missing,[*ACTIONS,*NATIVE]] = np.nan
    # Even unresolved endpoints retain exact target coordinates for the audit.
    target['X (m)'] = target['X target (m)']
    target['Y (m)'] = target['Y target (m)']
    return target, recipes
