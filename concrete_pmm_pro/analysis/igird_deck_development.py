"""Physical deck-layer development, independent of girder-bar end anchors."""
from __future__ import annotations
import math
from concrete_pmm_pro.analysis.igird_composite_flexure import DECK_REBAR_MATERIAL_NAME


def is_deck_bar(bar):
    return bar.material_name.startswith(DECK_REBAR_MATERIAL_NAME)


def deck_layer_settings(params, bar, *, span_m):
    face = 'top' if str(bar.label).startswith('Top') else 'bottom'
    prefix = 'deck_long_rebar_'+face+'_'
    def number(key, default):
        try:
            v = float(params.get(prefix+key, default))
        except (TypeError, ValueError):
            raise ValueError('Deck '+face+' '+key+' is invalid.')
        if not math.isfinite(v):
            raise ValueError('Deck '+face+' '+key+' must be finite.')
        return v
    start = number('start_m', 0)
    end = number('end_m', span_m)
    if not 0 <= start < end <= span_m:
        raise ValueError('Deck '+face+' bar start/end must lie within the physical member.')
    return {'bars_continuous_confirmed':bool(params.get(prefix+'continuous_confirmed',False)),
        'left_bar_anchored':bool(params.get(prefix+'left_anchored',False)),
        'right_bar_anchored':bool(params.get(prefix+'right_anchored',False)),
        'bar_ld_mm':number('ld_mm',0), 'start_m':start, 'end_m':end, 'face':face}


def station_bar_factors(state, bars, materials, *, x_m, span_m, girder_factor):
    """Verified V/T stiffness/strength factors and independent layer audit."""
    from types import SimpleNamespace
    from concrete_pmm_pro.analysis.igird_flexure_development import ordinary_bar_limits
    params = dict(state.get('section_parameters') or {})
    if not params.get('deck_fc_MPa'):
        for material in state.get('concrete_materials') or []:
            name = material.get('name') if isinstance(material,dict) else material.name
            if name == state.get('deck_topping_material_name'):
                params['deck_fc_MPa'] = material.get('fc_MPa') if isinstance(material,dict) else material.fc_MPa
    mats = {m.name:m for m in materials}
    factors, trace, ready = [], [], True
    for bar in bars:
        if not is_deck_bar(bar):
            factors.append(girder_factor or 0.)
            ready = ready and girder_factor is not None
            continue
        cfg = deck_layer_settings(params,bar,span_m=span_m)
        if bar.material_name not in mats:
            factors.append(0.); ready=False
            trace.append({'Layer':cfg['face'],'factor':0.,'status':'MATERIAL REQUIRED'})
            continue
        context = SimpleNamespace(bars=[bar], materials=mats, default=mats[bar.material_name])
        values, details = ordinary_bar_limits(context,x_m=x_m,span_m=span_m,settings={},params=params,girder_fc_mpa=0.)
        confirmed = cfg['bars_continuous_confirmed']
        factors.append(values[0] if confirmed else 0.)
        ready = ready and confirmed
        trace.append({**details[0], 'Layer':cfg['face'], 'factor':factors[-1],
            'status':'PASS' if confirmed else 'CONTINUITY REQUIRED'})
    return factors, ready, trace


def negative_composite_ready(params):
    return bool(params.get('deck_long_rebar_credit_positive_mn')) and any(
        float(params.get('deck_long_rebar_'+face+'_diameter_mm',0)) > 0 and
        bool(params.get('deck_long_rebar_'+face+'_continuous_confirmed')) for face in ('top','bottom'))
