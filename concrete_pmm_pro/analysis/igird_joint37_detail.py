"""Actual input paths, physical intersections and feasible A intervals.

A verified full-hook dimension at the construction joint does not verify the
interior STM nodal faces, slab mat anchorage, or an interference-free cage.
Never silently move explicit longitudinal bars / strands to manufacture room.
"""
import math
from shapely.geometry import LineString,Point,Polygon
from .igird_joint37_model import number,u_path


def diameter(bar):
    dev=bar.get('development',{})
    if bar.get('kind')=='prestress':return number(dev['lt_mm'])/60.
    return number(dev['db_mm'])


def audit(*,girder,bars,hoop,detail,db_mm,web_width_mm):
    db=number(db_mm);D=number(detail['hook_inside_bend_mm']);A=number(detail['row_spacing_mm']);F=number(detail['girder_ld_available_mm'])
    top=girder.bounds[3];centre=girder.centroid.x;cover=number(hoop['cover_mm']);dg=number(hoop['Diameter_mm'])
    path=u_path(centre=centre,top=top,a=A,F=F,B=number(detail['slab_ldh_available_mm']),D=D,db=db,tail=number(detail['hook_tail_mm']),levels=[],arc_steps=64)
    curve=LineString(path);hoop_poly=girder.buffer(-(cover+dg/2),join_style=2);hoop_line=LineString(hoop_poly.exterior.coords)
    collisions=[];hoop_collisions=[]
    minimum=float('inf')
    for bar in bars:
        d=diameter(bar);point=Point(bar['x_mm'],bar['y_mm'])
        clear=curve.distance(point)-(db+d)/2;minimum=min(minimum,clear)
        row={'Bar':bar['label'],'Kind':bar.get('kind'),'x_mm':bar['x_mm'],'y_mm':bar['y_mm'],'db_mm':d,'U_clear_gap_mm':clear}
        if clear<-.1:collisions.append(row)
        gap=hoop_line.distance(point)-(dg+d)/2
        if gap<-.1:hoop_collisions.append({**row,'Derived_hoop_gap_mm':gap})
    amin=D+db;amax=number(web_width_mm)-2*cover-db;intervals=[(amin,amax)] if amin<=amax else []
    blocking=[];ylow=top-F;yhigh=top+number(detail['slab_ldh_available_mm'])-(D+db)/2-db/2
    # Necessary straight-web-leg clearance only. This is NOT a complete
    # constructibility / minimum-code-spacing test or a recommended new layout.
    for bar in bars:
        y=number(bar['y_mm'])
        if not ylow<=y<=yhigh:continue
        x=abs(number(bar['x_mm'])-centre);r=(db+diameter(bar))/2;lo,hi=2*max(0.,x-r),2*(x+r)
        updated=[]
        for a,b in intervals:
            if hi<=a or lo>=b:updated.append((a,b));continue
            if a<lo:updated.append((a,min(b,lo)))
            if hi<b:updated.append((max(a,hi),b))
        if updated!=intervals:blocking.append({'Bar':bar['label'],'excluded_A_interval_mm':[lo,hi]})
        intervals=updated
    return {'status':'INPUT GEOMETRY REVIEW' if collisions or hoop_collisions else 'NO INTERSECTIONS IN TESTED PATHS',
        'U_intersections':collisions,'derived_hoop_intersections':hoop_collisions,'minimum_U_clear_gap_mm':minimum,
        'A_bend_minimum_mm':amin,'A_web_cover_maximum_mm':amax,'A_necessary_feasible_intervals_mm':intervals,'A_blocking_bars':blocking,
        'A_only_can_resolve_straight_leg_intersections':bool(intervals),
        'action':'Revise / verify the explicit longitudinal cage and strand placement together with the U path. A alone cannot fix conflicting inequalities.' if not intervals else
                 'Intervals are necessary geometric clearance only; verify all bends, bar spacing, anchorage and placement tolerances.',
        'scope':'Physical centreline/radius intersections in the input model. Derived hoop is hypothetical; minimum code clear spacing, construction tolerances and actual drawing verification remain separate.',
        'no_silent_relocation':True}
