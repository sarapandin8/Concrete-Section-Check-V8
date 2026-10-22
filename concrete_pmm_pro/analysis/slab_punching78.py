"""Local normal-shear index using the actual imported thickness at each point.

The saved-step demand bound is retained; resistance now uses the native
corner thickness, never the minimum thickness of another slab region.
This is not an AASHTO-prescribed pointwise punching equation. A local index
below one is not a physical-perimeter PASS, especially across depth changes.
The uniform-depth sufficient-bound interpretation remains limited to an
eligible, fully covered, constant-depth domain. Physical-area checks remain
separate in slab_punching64; their thickness-change guards are preserved.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from shapely.ops import unary_union

from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.analysis.slab_aashto63_sections import in_support

VERSION = 'SLAB.PUNCHLOCAL79'
KSI = 6.894757293
PHI = .9
CODE = 'AASHTO LRFD 9th Edition (2020), 5.12.8.6.3-1'
SCOPE = ('Local normal-shear index for the adopted CSiBridge transverse-shear field; '
    'normal-weight concrete, Vs=0, source actions multiplier=1.0. '
    'Resistance uses actual imported thickness at the same native corner as the force. '
    'A local index below one does not certify a critical perimeter crossing different '
    'thicknesses, folded surfaces or omitted regions. Actual critical-perimeter resistance, '
    'moment transfer, bearing/interface resistance and full deck acceptance remain separate.')
KEYS = ['Area', 'AreaElem', 'Joint', 'OutputCase']


def unit_resistance(fc, h, cover):
    """Return MPa, mm and kN/m. One metre cancels; no arbitrary 1 m patch."""
    fc, cover = float(fc), float(cover)
    h = np.asarray(h, dtype=float)
    if not math.isfinite(fc) or not 0 < fc <= 15*KSI:
        raise ValueError('Punching bound requires normal-weight concrete within 15 ksi')
    if not math.isfinite(cover) or cover < 0:
        raise ValueError('Invalid reinforcement centre depth')
    valid = np.isfinite(h) & (h > cover) & (h > 0)
    dv = np.where(valid, np.maximum(.9*(h-cover), .72*h), np.nan)
    stress = .063*math.sqrt(fc/KSI)*KSI
    # MPa * mm = N/mm = kN/m.
    return stress, dv, PHI*stress*dv


def _geometry_issues(base):
    issues = []
    axes = list(base['geometry'].parent_axes.values())
    for a in axes:
        rotation = np.asarray(a.get('rotation', np.eye(2)), float)
        if not np.allclose(rotation@rotation.T, np.eye(2), atol=1e-8):
            issues.append('Non-orthonormal shell shear axes require review')
            break
    normals = np.array([a.get('up', a.get('local3', [0, 0, 1])) for a in axes], float)
    if len(normals) and np.max(np.linalg.norm(normals-normals[0], axis=1)) > 1e-7:
        issues.append('Perimeters crossing folded shell surfaces require separate load-path assessment')
    polygons = [Polygon(p[:, :2]) for p in base['geometry'].elements.values()]
    if any(not p.is_valid or p.area <= 1e-12 or p.convex_hull.area-p.area > 1e-8 for p in polygons):
        issues.append('Invalid / concave shell geometry does not qualify for the convex force-field bound')
    deck = unary_union(polygons)
    if deck.geom_type != 'Polygon' or len(getattr(deck, 'interiors', ())):
        issues.append('Openings / disconnected slab require dedicated critical-perimeter assessment')
    return issues


def calculate(base):
    source = base['rows']
    if source.empty:
        raise ValueError('No imported shell forces for punching bound')
    required = [*KEYS, 'StepType', 'Vx', 'Vy', 'Thickness (mm)', 'X (m)', 'Y (m)', INCLUDED]
    if any(c not in source for c in required):
        raise ValueError('Incomplete physical shell force / geometry fields')
    frame = source[required+(['StepNum'] if 'StepNum' in source else [])].copy()
    finite = np.isfinite(frame[['Vx', 'Vy', 'Thickness (mm)']]).all(axis=1)
    frame['_finite'] = finite
    frame['_qx'] = frame.Vx.abs()
    frame['_qy'] = frame.Vy.abs()
    frame['_source_allowed'] = frame[INCLUDED].astype(bool)
    steps = ['OutputCase', 'StepType']+(['StepNum'] if 'StepNum' in frame else [])
    counts = frame[steps].drop_duplicates().groupby('OutputCase', dropna=False).size()
    distinct = frame[KEYS+steps[1:]].drop_duplicates().groupby(KEYS, dropna=False).size()
    grouped = frame.groupby(KEYS, sort=False, dropna=False)
    rows = grouped.agg(**{
        'X (m)': ('X (m)', 'first'), 'Y (m)': ('Y (m)', 'first'),
        'Thickness (mm)': ('Thickness (mm)', 'min'),
        'Maximum thickness (mm)': ('Thickness (mm)', 'max'),
        'Qx bound (kN/m)': ('_qx', 'max'), 'Qy bound (kN/m)': ('_qy', 'max'),
        'Finite source': ('_finite', 'all'), 'Source allowed': ('_source_allowed', 'all'),
        'Saved records': ('Vx', 'size')})
    expected_steps = counts.reindex(rows.index.get_level_values('OutputCase')).to_numpy()
    rows['Complete saved steps'] = (rows['Saved records'].eq(distinct.reindex(rows.index)) & rows['Saved records'].eq(expected_steps))
    rows = rows.reset_index()
    expected_corners = base['geometry'].corners.groupby('AreaElem').size()
    actual_corners = rows.groupby(['AreaElem', 'OutputCase']).Joint.transform('size')
    complete_element = actual_corners.eq(rows.AreaElem.map(expected_corners))
    missing_groups = len(base['geometry'].corners)*len(counts)-len(rows)
    rows['StepType'] = 'Saved-step bound'
    rows['Q bound (kN/m)'] = np.hypot(rows['Qx bound (kN/m)'], rows['Qy bound (kN/m)'])
    h_all = base['geometry'].corners['Thickness (mm)'].to_numpy(float)
    if not np.isfinite(h_all).all() or not len(h_all):
        raise ValueError('Complete imported slab thickness is required')
    h_min = float(h_all.min())
    h_max = float(h_all.max())
    stress, dv, capacity = unit_resistance(base['steel'].fc, rows['Thickness (mm)'], max(base['steel'].centre))
    rows['Resistance thickness (mm)'] = rows['Thickness (mm)']
    rows['dv (mm)'] = dv
    rows['v minimum (MPa)'] = stress
    rows['phi v dv (kN/m)'] = capacity
    physical_contact = in_support(rows[['X (m)', 'Y (m)']].to_numpy(float), base.get('supports', []))
    rows['Support contact'] = physical_contact
    rows['Local D/C'] = rows['Q bound (kN/m)']/capacity
    valid = (rows['Source allowed'] & rows['Finite source'] & rows['Complete saved steps'] &
        np.isfinite(rows['Local D/C']) & ~physical_contact &
        rows['Maximum thickness (mm)'].sub(rows['Thickness (mm)']).abs().le(.05))
    rows[INCLUDED] = valid
    rows['Status'] = np.where(valid, np.where(rows['Local D/C'] > 1+1e-8, 'ABOVE LOCAL LIMIT', 'BELOW LOCAL LIMIT'), 'EXCLUDED / REVIEW')
    rows['Reason'] = np.where(valid, np.where(rows['Local D/C'] > 1+1e-8,
        'Local index exceeds one; assess the physical perimeter before declaring FAIL',
        'Local normal-shear index below one; physical-perimeter acceptance is separate'),
        'Excluded / unavailable source or support contact; no nominal acceptance')
    rows.loc[~valid, 'Local D/C'] = np.nan
    # A missing/duplicate step or non-finite vector cannot disappear into PASS.
    source_gap = (~rows['Complete saved steps'] | ~rows['Finite source'] | ~complete_element |
        ~np.isfinite(capacity) | rows['Maximum thickness (mm)'].sub(rows['Thickness (mm)']).abs().gt(.05)) & ~physical_contact
    rows['Source incomplete'] = source_gap
    eligible = rows.loc[valid]
    governor = eligible.loc[eligible['Local D/C'].idxmax()].to_dict() if len(eligible) else None
    maximum = float(governor['Local D/C']) if governor else math.nan
    geometry_issues = _geometry_issues(base)
    variable_depth = h_max-h_min > .05
    if variable_depth:
        geometry_issues.append('Variable slab thickness: local indices do not establish resistance along an actual critical perimeter')
    missing = bool(base.get('incomplete', False) or missing_groups != 0 or source_gap.any())
    review = (governor is None or maximum > 1+1e-8 or missing or bool(geometry_issues))
    summary = []
    for case, block in rows.groupby('OutputCase', sort=False):
        known = block.loc[block[INCLUDED]]
        gov = known.loc[known['Local D/C'].idxmax()] if len(known) else None
        summary.append({'Case': case, 'Max local D/C': float(gov['Local D/C']) if gov is not None else math.nan,
            'Status': 'REVIEW' if gov is None or gov['Local D/C'] > 1+1e-8 or missing or geometry_issues else 'PASS (sufficient)',
            'X (m)': float(gov['X (m)']) if gov is not None else math.nan,
            'Y (m)': float(gov['Y (m)']) if gov is not None else math.nan,
            'AreaElem': gov.AreaElem if gov is not None else '', 'Joint': gov.Joint if gov is not None else '',
            'Q bound (kN/m)': float(gov['Q bound (kN/m)']) if gov is not None else math.nan,
            'phi v dv (kN/m)': float(gov['phi v dv (kN/m)']) if gov is not None else math.nan,
            'Thickness (mm)': float(gov['Thickness (mm)']) if gov is not None else math.nan,
            'dv (mm)': float(gov['dv (mm)']) if gov is not None else math.nan,
            'Evaluated records': len(known), 'Unresolved source records': int(block['Source incomplete'].sum())})
    return {'version': VERSION, 'code': CODE, 'status': 'REVIEW' if review else 'PASS (sufficient)',
        'rows': rows, 'summary': pd.DataFrame(summary), 'governing': governor,
        'max_dc': maximum, 'scope': SCOPE, 'geometry_issues': geometry_issues,
        'source_incomplete': missing, 'evaluated_records': int(valid.sum()),
        'excluded_records': int((~valid).sum()), 'missing_corner_case_groups': max(0, int(missing_groups)), 'source_actions_multiplier': 1.,
        'adopted_demand_basis': 'Existing CSiBridge forces adopted as conservative by project engineer',
        'coefficient_us': .063, 'phi': PHI, 'Vs': 0., 'minimum_thickness_mm': h_min,
        'maximum_thickness_mm': h_max, 'variable_depth': variable_depth,
        'thickness_basis': 'Actual imported native-corner thickness',
        'global_minimum_depth_applied': False, 'quantity': 'Local normal-shear D/C',
        'local_index_status': 'BELOW LOCAL LIMIT' if governor and maximum <= 1+1e-8 else 'REVIEW',
        'governing_unit_resistance_kN_per_m': float(governor['phi v dv (kN/m)']) if governor else math.nan,
        'full_deck_acceptance': False,
        'physical_perimeter_inferred': False, 'actual_local_train_equivalence_verified': False}


def map_adapter(base, screen):
    rows = screen['rows'].copy()
    rows['Field D/C'] = rows['Local D/C']
    rows['Controlling check'] = 'Local normal-shear index · actual thickness'
    rows['Combined N–M–V status'] = 'Separate checks'
    rows['Status'] = np.where(rows['Local D/C'].gt(1+1e-8) | rows['Source incomplete'], 'REVIEW', 'LOCAL INDEX')
    # Partial excluded elements do not become fully certified coloured cells.
    groups = rows.groupby('AreaElem')[INCLUDED].all()
    rows['Source incomplete'] |= ~rows.AreaElem.map(groups)
    return {**base, 'rows': rows, 'samples_per_element': 4}


def report_payload(screen):
    keys = ('version', 'code', 'status', 'max_dc', 'scope', 'geometry_issues',
        'source_incomplete', 'evaluated_records', 'excluded_records', 'missing_corner_case_groups',
        'source_actions_multiplier', 'adopted_demand_basis', 'coefficient_us', 'phi', 'Vs',
        'minimum_thickness_mm', 'maximum_thickness_mm', 'variable_depth',
        'thickness_basis', 'global_minimum_depth_applied', 'quantity', 'local_index_status',
        'governing_unit_resistance_kN_per_m',
        'full_deck_acceptance', 'physical_perimeter_inferred', 'actual_local_train_equivalence_verified')
    return {k: (None if isinstance(screen[k], float) and not math.isfinite(screen[k]) else screen[k]) for k in keys}
