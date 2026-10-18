"""Explicit strand positions and developed STM tie-force ceilings, N/mm/MPa.

These are idealized tie bounds, not a strain-compatible section resistance.
Pe is never added a second time to the imported external axial force.
"""
import math
import re

from .igird_flexure_development import strand_stress_limit
from concrete_pmm_pro.serviceability.girder_prestress_station import active_girder_strand_rows, debonded_strand_numbers_for_row


def positions(text, count):
    try:
        values=[float(v.strip()) for v in str(text).replace(';',',').replace('|',',').split(',') if v.strip()]
    except (TypeError,ValueError):values=[]
    if len(values)!=count or not all(math.isfinite(v) for v in values) or len(set(values))!=count:
        raise ValueError("Explicit strand x positions must be finite, unique and match the strand count; no x=0 collapse or inferred positions.")
    return values


def strand_ties(table, *, x_m, span_m, y_min_mm, depth_mm, fy_tie_MPa, settings, left_cut_m=0., right_cut_m=None, require_x_positions=True):
    """5.8.2.4 tie term Aps(fpe+fy), capped by fpy AND development.

    Ordinary-bar fy comes from the actual cage, not fpu or an invented grade.
    Every strand keeps its own x position and sleeve identification.
    """
    vals=(x_m,span_m,y_min_mm,depth_mm,fy_tie_MPa)
    if not all(math.isfinite(float(v)) and not isinstance(v,bool) for v in vals) or min(span_m,depth_mm,fy_tie_MPa)<=0:
        raise ValueError("Finite station / span / steel inputs are required.")
    right_cut_m=span_m if right_cut_m is None else float(right_cut_m)
    left_cut_m=float(left_cut_m)
    if not math.isfinite(left_cut_m+right_cut_m) or right_cut_m<=left_cut_m:raise ValueError('Valid physical cut ends are required.')
    left=left_cut_m-float(settings.get('left_extension_m',0.));right=right_cut_m+float(settings.get('right_extension_m',0.))
    if not left<=x_m<=right:raise ValueError("Station lies outside the physical strand length.")
    result=[]
    for row in active_girder_strand_rows(table):
        n=int(round(float(row['No. Strands'])))
        if require_x_positions:
            xs=positions(row.get('Strand x positions mm'),n)
        else:
            # A y-layer force inventory does not use transverse coordinates.
            # Keep known positions; never invent x=0 or a spatial distribution.
            try: xs=positions(row.get('Strand x positions mm'),n)
            except ValueError: xs=[None]*n
        token=re.search(r'\d+(?:\.\d+)?',str(row.get('Strand Size') or ''))
        if token is None:raise ValueError('Strand nominal diameter is missing.')
        db=float(token.group());area=float(row['Area/Strand_mm2']);pe=float(row['Pe_eff_final/strand_kN'])*1000
        if not all(math.isfinite(v) and v>0 for v in (db,area,pe)):raise ValueError('Strand area / force / diameter is invalid.')
        fpe=pe/area
        if fpe>=1670.:raise ValueError('Strand effective stress exceeds the adopted 1670 MPa proof stress.')
        fpt=min(1670.,fpe+fy_tie_MPa)
        selected=set(debonded_strand_numbers_for_row(row))
        for number,x in enumerate(xs,1):
            debonded=number in selected
            l=float(row.get('Left debond m') or 0.) if debonded else 0.
            r=float(row.get('Right debond m') or 0.) if debonded else 0.
            if not math.isfinite(l+r) or min(l,r)<0 or left+l>=right-r:raise ValueError('Invalid strand sleeve lengths.')
            distance=max(0.,min(x_m-(left+l),(right-r)-x_m))*1000.
            limit=strand_stress_limit(distance_mm=distance,db_mm=db,fpe_mpa=fpe,fps_mpa=fpt,
                depth_mm=depth_mm,debonded=debonded,service_condition=settings.get('debonded_service_condition','unknown'))
            result.append({'label':f"{row['Group ID']} / strand {number}",'kind':'prestress','x_mm':x,
                'spatial_position_verified':x is not None,
                'y_mm':y_min_mm+float(row['y_mm_from_bottom']),'area_mm2':area,'capacity_N':area*limit['fpx_limit_MPa'],
                'fpe_MPa':fpe,'tie_stress_ceiling_MPa':fpt,'developed_stress_MPa':limit['fpx_limit_MPa'],
                'bonded_distance_mm':distance,'debonded':debonded,'development':limit,
                'basis':'5.8.2.4.1 tie ceiling + existing 5.9.4.3 development; rigid-plastic bound only'})
    if not result:raise ValueError('No active dedicated strand layout is available.')
    return result
