"""Source-unit-safe AASHTO 5.7.3.4.2-7; conservative sx=dv by default."""
import math


def crack_spacing_source(state, *, dv_mm):
    params = state.get('section_parameters') or {}
    try:
        ag = float(params.get('shear_max_aggregate_mm',0))
        sx = float(params.get('shear_verified_sx_mm',0))
        dv = float(dv_mm)
    except (TypeError, ValueError):
        return {'ready':False,'note':'Invalid aggregate / crack spacing source.'}
    if not bool(params.get('shear_aggregate_confirmed')) or not all(math.isfinite(v) for v in (ag,sx,dv)) or ag <= 0 or dv <= 0:
        return {'ready':False,'note':'Below-minimum General Procedure requires confirmed maximum aggregate size.'}
    if sx > 0 and not bool(params.get('shear_sx_layers_verified')):
        return {'ready':False,'note':'Reduced sx needs layer-area verification As(layer) >= 0.003 bv sx.'}
    sx = min(dv,sx) if sx > 0 else dv
    raw = sx * 1.38 / (ag / 25.4 + 0.63)
    return {'ready':True,'sx mm':sx,'ag mm':ag,'sxe raw mm':raw,
        'sxe mm':min(max(raw,304.8),2032.),
        'note':'AASHTO 5.7.3.4.2-7: sxe=sx*1.38/(ag[in]+0.63); limited to 12–80 in. sx=dv unless a smaller verified crack-control layer spacing is entered. Below-minimum detailing remains FAIL.'}
