"""Read-only Top slab rows for Result Summary and Report / QA."""
from __future__ import annotations

import math

from concrete_pmm_pro.analysis import slab_top65 as top
from concrete_pmm_pro.io.slab_shell_import import BANK_KEY


def summary_rows(state):
    if state.get(BANK_KEY) is None and state.get(top.RESULT_KEY) is None:
        return []
    source = 'Analysis → Slab Reinforcement · '+top.VERSION
    result = top.current(state)
    def row(check, status, ratio=None, case='-', point='-', action='Review source Analysis check.'):
        return {'Module': 'Top slab ULS', 'Check': check, 'Status': status,
            'Code Basis': 'AASHTO LRFD 9th Edition (2020)', 'Governing Case': case,
            'Station / Point': point, 'Demand': 'Current imported shell actions',
            'Capacity / Limit': 'Directional section / detail limit', 'D/C / Util.': ratio,
            'Required Action': action, 'Source': source}
    if result is None:
        return [row('Top slab sections', 'STALE' if state.get(top.RESULT_KEY) is not None else 'NOT CALCULATED',
            action='Open Analysis → Slab Reinforcement and Calculate Top slab for the current inputs.')]
    output = []
    for _, check in result['summary'].iterrows():
        ratio = float(check['Max D/C'])
        output.append(row(check.Check, check.Status, ratio if math.isfinite(ratio) else None,
            case=f'{check.Case} / {check.Step}', point=f"X={check['X (m)']:.3f}, Y={check['Y (m)']:.3f} m",
            action='Review the governing retained source vector and the matching reinforcement / section.' if check.Status != 'PASS' else
                'Component passes its directional scope; retain the separate deck scope review.'))
    for _, detail in result['clear_spacing'].iterrows():
        ratio = float(detail['Clear spacing D/C'])
        output.append(row('Clear spacing · '+detail.Mat, detail['Clear spacing status'],
            ratio if math.isfinite(ratio) else None, action=detail.Basis))
    punching = result['punching']
    if len(punching['rows']):
        known = punching['rows'].loc[punching['rows']['D/C'].notna()]
        ratio = float(known['D/C'].max()) if len(known) else None
        output.append(row('Local punching normal force', punching['status'], ratio,
            action='Review the defined physical loaded areas, critical perimeters and demand bounds.'))
    output.append(row('Deck scope / remaining checks', 'REVIEW',
        action='Directional results do not resolve Nxy/Mxy coupling, local support/load paths, available anchorage, fatigue or SLS. Local punching requires an actual isolated footprint when applicable.'))
    return output
