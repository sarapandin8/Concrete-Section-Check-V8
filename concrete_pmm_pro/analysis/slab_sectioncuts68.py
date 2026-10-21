"""Signed native-result line integrals at selected governing sections.

These are source-backed comparisons, not a verified strip-design envelope.
Missing/excluded interpolation sources invalidate a cut; partial widths are
never normalized into a passing result. Each side of an FE edge is separate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.analysis.slab_aashto63_sections import in_support
from concrete_pmm_pro.analysis.slab_review61 import step_columns

ACTIONS = ['Nx','Ny','Nxy','Mx','My','Mxy','Vx','Vy']
TOL = 2e-5


class CutSource:
    def __init__(self, rows, geometry):
        self.rows, self.geometry = rows, geometry
        axes = list(geometry.parent_axes.values())
        if not axes or geometry.corners.empty:
            raise ValueError('Section-cut review requires recovered deck geometry')
        self.long = np.array(axes[0]['long'][:2],float)
        if not np.isfinite(self.long).all() or np.linalg.norm(self.long)<1e-12:
            raise ValueError('Section-cut review requires a finite reinforcement alignment')
        self.long /= np.linalg.norm(self.long)
        if any(not np.allclose(a['long'][:2],self.long,atol=1e-8) for a in axes):
            raise ValueError('Section-cut review requires one straight reinforcement alignment')
        self.basis = np.column_stack((self.long,[-self.long[1],self.long[0]]))
        self.groups = list(geometry.corners.groupby('AreaElem',sort=False))
        if any(len(g)!=4 for _,g in self.groups):
            raise ValueError('Section-cut review requires four distinct corners per mesh cell')
        self.points = np.array([g[['X (m)','Y (m)']].to_numpy(float)@self.basis for _,g in self.groups])
        self.h = np.array([g['Thickness (mm)'].to_numpy(float) for _,g in self.groups])
        if not np.isfinite(self.points).all() or not np.isfinite(self.h).all() or (self.h<=0).any():
            raise ValueError('Section-cut review requires finite coordinates and positive thickness')
        self.low,self.high = self.points.min(1),self.points.max(1)
        if np.any(self.high-self.low<=TOL) or not (np.isclose(self.points,self.low[:,None,:],atol=TOL,rtol=0)|np.isclose(self.points,self.high[:,None,:],atol=TOL,rtol=0)).all():
            raise ValueError('Section-cut review requires rectangular aligned mesh cells')
        if any(len(np.unique(p,axis=0))!=4 for p in self.points):
            raise ValueError('Section-cut review requires four distinct corners per mesh cell')
        self.keys = pd.MultiIndex.from_tuples([(str(e),str(j)) for e,g in self.groups for j in g.Joint],names=['AreaElem','Joint'])
        self.steps = step_columns(rows)
        self.cache = {}

    def source(self, case):
        token = tuple(None if pd.isna(case[k]) else case[k] for k in self.steps)
        if token not in self.cache:
            mask = np.ones(len(self.rows),bool)
            for key in self.steps:
                mask &= (self.rows[key].isna() if pd.isna(case[key]) else self.rows[key].eq(case[key])).to_numpy()
            selected = self.rows.loc[mask]
            index = pd.MultiIndex.from_frame(selected[['AreaElem','Joint']].astype(str))
            if not index.is_unique:
                raise ValueError('Section cuts require unique native corner/case/step records')
            positions = index.get_indexer(self.keys)
            missing = positions<0
            safe = np.maximum(positions,0)
            if not len(selected):
                values = np.full((len(self.keys),8),np.nan)
                valid = np.zeros(len(self.keys),bool)
            else:
                values = selected[ACTIONS].to_numpy(float)[safe]
                valid = ~missing & selected[INCLUDED].to_numpy(bool)[safe] & np.isfinite(values).all(1)
            self.cache[token] = values.reshape(-1,4,8),valid.reshape(-1,4)
        return self.cache[token]

    def window(self, direction, point, supports, width=1.):
        if direction not in ('Longitudinal','Transverse') or not np.isfinite(width) or width<=TOL:
            raise ValueError('Invalid section-cut direction or width')
        n = 0 if direction=='Longitudinal' else 1
        w = 1-n
        p = np.asarray(point)@self.basis
        edges = [float(self.low[:,w].min()),float(self.high[:,w].max())]
        for support in supports:
            a,b = support['a'],support['b']
            normal = support['normal']*support['half_width']
            q = np.array([a-normal,b-normal,b+normal,a+normal])@self.basis
            low,high = q.min(0),q.max(0)
            if low[n]-TOL <= p[n] <= high[n]+TOL and high[w]>edges[0]+TOL and low[w]<edges[1]-TOL:
                edges.extend([max(edges[0],low[w]),min(edges[1],high[w])])
        edges = sorted(set(round(float(v),8) for v in edges))
        intervals = [(a,b) for a,b in zip(edges[:-1],edges[1:]) if a-TOL<=p[w]<=b+TOL and b-a>TOL]
        if not intervals:
            raise ValueError('Governing section lies outside the recovered deck')
        # At a contact face choose the interval outside the footprint.
        def contact(interval):
            middle=p.copy();middle[w]=sum(interval)/2
            return bool(in_support((middle@self.basis.T)[None,:],supports)[0])
        interval = next((i for i in intervals if not contact(i)),intervals[0])
        return {'station':float(p[n]),'a':max(interval[0],float(p[w]-width/2)),
            'b':min(interval[1],float(p[w]+width/2)),
            'reaction_footprint':contact(interval),'direction':direction}

    def integrate(self, direction, station, a, b, case, side='Plus'):
        if direction not in ('Longitudinal','Transverse') or side not in ('Plus','Minus') or b-a<=TOL:
            raise ValueError('Invalid section-cut direction, side or width')
        n = 0 if direction=='Longitudinal' else 1
        w = 1-n
        # One-sided ownership prevents counting an FE edge twice.
        if side=='Plus':
            take=(self.low[:,n]<=station+TOL)&(self.high[:,n]>station+TOL)
        else:
            take=(self.low[:,n]<station-TOL)&(self.high[:,n]>=station-TOL)
        take &= (self.high[:,w]>a+TOL)&(self.low[:,w]<b-TOL)
        values,valid=self.source(case)
        total=np.zeros(8);absolute=np.zeros(8);intervals=[];available=[];min_h=np.inf
        for e in np.flatnonzero(take):
            left,right=max(a,self.low[e,w]),min(b,self.high[e,w])
            if right-left<=TOL:
                continue
            intervals.append((left,right))
            weights=[]
            for transverse in (left,right):
                p=np.empty(2);p[n]=station;p[w]=transverse
                t=np.clip((p-self.low[e])/(self.high[e]-self.low[e]),0,1)
                high_corner=np.isclose(self.points[e],self.high[e],atol=TOL,rtol=0)
                weights.append(np.prod(np.where(high_corner,t,1-t),axis=1))
            weights=np.array(weights)
            required=(weights>1e-10).any(0)
            if not valid[e,required].all():
                continue
            available.append((left,right))
            v=weights@np.where(valid[e,:,None],values[e],0.)
            total+=(right-left)*v.mean(0)
            # Exact integral of the absolute linear interpolant, including
            # an internal zero. Cancellation is therefore reported explicitly.
            same=v[0]*v[1]>=0
            ends=abs(v)
            denom=ends.sum(0)
            opposite=np.divide(ends[0]**2+ends[1]**2,2*denom,out=np.zeros(8),where=denom>0)
            absolute+=(right-left)*np.where(same,denom/2,opposite)
            min_h=min(min_h,float((weights@self.h[e]).min()))
        def complete(parts):
            ordered=sorted(parts);end=a
            for left,right in ordered:
                if abs(left-end)>TOL:
                    return False
                end=right
            return bool(ordered) and abs(end-b)<=TOL
        ready=complete(intervals) and complete(available)
        width=b-a
        result={'Direction':direction,'Section coordinate (m)':station,'Cut side':side,
            'Width start (m)':a,'Width end (m)':b,'Width (m)':width,
            'Geometric coverage':complete(intervals),'Source coverage':ready,
            'Available width (m)':sum(y-x for x,y in available),
            'Thickness (mm)':min_h if ready else np.nan,
            'Status':'REVIEW','Basis':'Selected signed line integral; not a strip-design envelope',**case}
        for i,c in enumerate(ACTIONS):
            result[c]=total[i]/width if ready else np.nan
            result[c+' integral']=total[i] if ready else np.nan
            result[c+' absolute integral']=absolute[i] if ready else np.nan
        return result
