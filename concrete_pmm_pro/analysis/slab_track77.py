"""Project-selected 45-degree continuous track-load influence geometry.

This is a load-distribution assumption above the structural top slab, not an
AASHTO railway load rule or a punching failure surface. It never disperses
already analysed CSI actions, manufactures a longitudinal wheel footprint, or
changes the accepted one-way/end/connection/peak masks. Exact girder contact
areas are separated from slab-only punching scope under the project's full
contact assumption; being between the outer girders is not full support.
"""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point, Polygon, box, mapping
from shapely.ops import unary_union

from concrete_pmm_pro.analysis.slab_punching64 import _domain, normalise

VERSION = 'SLAB.TRACK45-77'
CONFIG_KEY = 'slab_track45_77'
SUPPORTED = 'GIRDER CONTACT · PROJECT SCOPE'
DIRECT = 'DIRECT TRACK FOOTPRINT'
SPREAD = '45 DEGREE SPREAD'
OUTSIDE = 'OUTSIDE TRAIN STRIPS'
DEFAULT = {'version': 1, 'enabled': False, 'width_m': 2., 'depth_mm': 300.,
           'count': 2, 'spacing_m': 5., 'offset_m': 0., 'exclude_flange': True}
SCOPE = ('Continuous-strip geometry only. Full contact over the existing I-girder '
         'top flanges is the project assumption. Girder contact is outside the '
         'slab-only punching scope, not a code exemption or PASS. One-way shear, '
         'local bearing/interface and isolated-load checks remain separate. '
         'No local train punching D/C is derived from the full-span UDL.')


def config(state):
    raw = (state.get('project_metadata') or {}).get(CONFIG_KEY, {})
    if not isinstance(raw, dict):
        raise ValueError('Track distribution must be an input object')
    basis = (state.get('project_metadata') or {}).get('slab_top65_load_basis', {})
    depth = basis.get('ballast_mm', 300.) if isinstance(basis, dict) else 300.
    cfg = {**DEFAULT, 'depth_mm': depth, **raw}
    if cfg['version'] != 1:
        raise ValueError('Unsupported track distribution input version')
    for key in ('enabled', 'exclude_flange'):
        if not isinstance(cfg[key], bool):
            raise ValueError('Track setting must be true/false: '+key)
    for key in ('width_m', 'depth_mm', 'spacing_m', 'offset_m', 'count'):
        if isinstance(cfg[key], (bool, np.bool_)):
            raise ValueError('Track setting must be numeric: '+key)
        try:
            cfg[key] = float(cfg[key])
        except (ValueError, TypeError):
            raise ValueError('Invalid track setting: '+key) from None
        if not math.isfinite(cfg[key]):
            raise ValueError('Track setting must be finite: '+key)
    if cfg['width_m'] <= 0 or cfg['depth_mm'] < 0 or cfg['spacing_m'] <= 0:
        raise ValueError('Track width / spacing must be positive; spread depth must be nonnegative')
    if cfg['count'] != int(cfg['count']) or not 1 <= cfg['count'] <= 4:
        raise ValueError('Track count must be an integer from 1 to 4')
    cfg['count'] = int(cfg['count'])
    if cfg['count'] > 1 and cfg['spacing_m'] < cfg['width_m']:
        raise ValueError('Physical track footprints overlap; review track width and centre spacing')
    return {k: cfg[k] for k in DEFAULT}


def save(state, values):
    metadata = dict(state.get('project_metadata') or {})
    candidate = {**config(state), **values}
    checked = config({'project_metadata': {CONFIG_KEY: candidate}})
    metadata[CONFIG_KEY] = checked
    state['project_metadata'] = metadata
    return checked


def signature(state):
    return hashlib.sha256(json.dumps(config(state), sort_keys=True).encode()).hexdigest()


def _global_geometry(local, basis):
    """Serialisable exact polygons, including holes, in imported global axes."""
    from shapely.affinity import affine_transform
    return mapping(affine_transform(local, [basis[0, 0], basis[1, 0],
        basis[0, 1], basis[1, 1], 0., 0.]))


def contact_geometry(base, basis):
    pieces = []
    labels = []
    for support in base.get('supports', []):
        if support.get('Kind') != 'Girder':
            continue
        half = float(support['half_width'])
        if not math.isfinite(half) or half <= 0:
            continue
        a, b = np.asarray(support['a'])@basis.T, np.asarray(support['b'])@basis.T
        footprint = LineString([a, b]).buffer(half, cap_style=2)
        pieces.append(footprint)
        labels.append((support['Support'], footprint))
    return unary_union(pieces), labels


def calculate(base, cfg):
    """Calculate exact strip/contact intersections, without solving mechanics."""
    cfg = config({'project_metadata': {CONFIG_KEY: cfg}})
    empty = {'version': VERSION, 'config': cfg, 'status': 'DISABLED',
             'tracks': pd.DataFrame(), 'points': pd.DataFrame(), 'elements': pd.DataFrame(),
             'zones': {}, 'notes': [], 'scope': SCOPE, 'code_exemption': False,
             'full_deck_acceptance': False, 'actions_changed': False,
             'local_train_punching_status': 'NOT CALCULATED'}
    if not cfg['enabled']:
        return empty
    basis, ids, polygons, deck, _ = _domain(base)
    if deck.is_empty or not deck.is_valid:
        raise ValueError('A valid imported top-slab footprint is required for track distribution')
    a, low, b, high = deck.bounds
    centre = (low+high)/2+cfg['offset_m']
    width = cfg['width_m']+2*cfg['depth_mm']/1000
    contacts, supports = contact_geometry(base, basis)
    girder = contacts.intersection(deck)
    direct, spread, tracks, notes = [], [], [], []
    for i in range(cfg['count']):
        y = centre+(i-(cfg['count']-1)/2)*cfg['spacing_m']
        source = box(a, y-cfg['width_m']/2, b, y+cfg['width_m']/2)
        enlarged = box(a, y-width/2, b, y+width/2)
        direct.append(source.intersection(deck))
        spread.append(enlarged.intersection(deck))
        names = [name for name, polygon in supports if enlarged.intersection(polygon).area > 1e-10]
        inside = source.difference(deck).area <= 1e-8
        if not inside:
            notes.append(f'Track {i+1}: the physical 2D footprint extends beyond the slab; review alignment / edge load transfer.')
        tracks.append({'Track': f'T{i+1}', 'Offset from deck CL (m)': y-(low+high)/2,
                       'Physical width (m)': cfg['width_m'], 'Spread depth (mm)': cfg['depth_mm'],
                       'Distributed width (m)': width, 'Source inside slab': inside,
                       'Within outer girder extent': bool(supports and source.difference(contacts.convex_hull).area <= 1e-8),
                       'Intersected girders': ', '.join(names), 'Girder contacts': len(names),
                       'Load path': 'Continuous strip across line supports' if len(names) >= 2 else
                                    'Continuous strip; support path needs review',
                       'Local punching D/C': None})
    direct, spread = unary_union(direct), unary_union(spread)
    excluded = girder if cfg['exclude_flange'] else Polygon()
    zones = {SUPPORTED: excluded, DIRECT: direct.difference(excluded),
             SPREAD: spread.difference(direct).difference(excluded),
             OUTSIDE: deck.difference(spread).difference(excluded)}
    if not supports:
        notes.append('No finite I-girder top-flange contacts available. No flange exclusion was inferred from girder centre lines.')
    if cfg['exclude_flange']:
        notes.append('Girder contacts use existing flange widths and the project full-contact assumption; gaps, discontinuities and local bearing/interface need separate review.')
    corners = base['geometry'].corners[['AreaElem', 'Joint', 'X (m)', 'Y (m)']].copy()
    xy = corners[['X (m)', 'Y (m)']].to_numpy(float)@basis.T
    classifications = []
    for point in xy:
        p = Point(point)
        classifications.append(next((label for label in (SUPPORTED, DIRECT, SPREAD)
                                     if not zones[label].is_empty and zones[label].covers(p)), OUTSIDE))
    corners['Track zone'] = classifications
    elements = []
    for element, polygon in zip(ids, polygons):
        record = {'AreaElem': element, 'Area (m²)': polygon.area}
        record.update({label+' fraction': polygon.intersection(zone).area/polygon.area
                       for label, zone in zones.items()})
        elements.append(record)
    # Partial elements retain their exact fractions; no centroid-based deletion.
    return {**empty, 'status': 'GEOMETRY CALCULATED', 'tracks': pd.DataFrame(tracks),
            'points': corners, 'elements': pd.DataFrame(elements),
            'zones': {label: _global_geometry(zone, basis) for label, zone in zones.items()},
            'footprints': {'direct': _global_geometry(direct, basis),
                           'distributed': _global_geometry(spread, basis)},
            'notes': notes, 'distributed_width_m': width,
            'area_m2': {label: zone.area for label, zone in zones.items()},
            'basis': basis.tolist(), 'deck_bounds_local': list(deck.bounds)}


def apply_contact_scope(punching, base, cfg):
    """Only an ENTIRE loaded rectangle inside girder contact is out of scope.

    A centroid on a girder, or a patch between the outer girders, never suffices.
    The existing support-crossing guards remain for partially supported areas.
    """
    if not cfg['enabled'] or not cfg['exclude_flange'] or punching['rows'].empty:
        return punching
    basis, *_ = _domain(base)
    contacts, _ = contact_geometry(base, basis)
    supported = []
    for area in normalise(punching['areas']):
        x, y = np.array([area['X (m)'], area['Y (m)']])@basis.T
        l, w = area['L (mm)']/2000, area['B (mm)']/2000
        rectangle = box(x-l, y-w, x+l, y+w)
        if rectangle.difference(contacts).area <= min(1e-10, rectangle.area*1e-8):
            supported.append(area['Area'])
    if not supported:
        return punching
    rows = punching['rows'].copy(deep=True)
    selected = rows.Area.isin(supported)
    rows.loc[selected, 'Status'] = 'OUTSIDE SLAB PUNCHING SCOPE'
    quantities = ['Vu (kN)', 'D/C', 'beta_c', 'coefficient (US)', 'vn (MPa)',
                  'b0 (mm)', 'dv (mm)', 'Vn (kN)', 'phi', 'phiVn (kN)']
    rows.loc[selected, [c for c in quantities if c in rows]] = np.nan
    rows.loc[selected, 'Reason'] = 'Entire loaded area lies over I-girder flange contact; project support-scope exclusion. Check local bearing/interface separately. Not a code exemption or PASS.'
    statuses = rows.loc[~selected, 'Status']
    status = ('FAIL' if statuses.eq('FAIL').any() else 'REVIEW' if statuses.eq('REVIEW').any()
              else 'PASS (sufficient)' if statuses.eq('PASS (sufficient)').any()
              else 'PASS' if len(statuses) else 'OUTSIDE SLAB PUNCHING SCOPE')
    paths = {k: v for k, v in punching['paths'].items() if k not in supported}
    segments = punching['segments']
    if not segments.empty:
        segments = segments.loc[~segments.Area.isin(supported)].copy()
    return {**punching, 'rows': rows, 'paths': paths, 'segments': segments, 'status': status,
            'project_supported_areas': supported, 'before_contact_scope': punching}


def report_payload(result):
    return {k: v for k, v in result.items() if k not in ('tracks', 'points', 'elements')}
