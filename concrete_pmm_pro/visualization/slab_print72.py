"""Shared print palette and physical references for all slab result figures.

References are read from the calculated connection layout. They never infer
supports from force peaks, bridge ends, girder count or nominal spacing.
"""
from __future__ import annotations

from html import escape

import numpy as np
import plotly.graph_objects as go

VERSION = 'SLAB.PRINT72'
# SLAB.COLOR73: medium saturation for a clearer printed result field.
SAFE_FILL = '#acd0e2'
MID_FILL = '#52a5c4'
LIMIT_FILL = '#f4cf75'
FAIL_FILL = '#ed9f91'
HIGH_FILL = '#c94f64'
RESPONSE = '#2f7fa3'
FAIL = '#bf4b55'
UNKNOWN = '#edf0f3'
GIRDER = '#5b7180'
DIAPHRAGM = '#9a8b7b'
BEARING = '#646b8a'


def export_config():
    """The standard camera action exports a white, scalable print figure."""
    return {'displaylogo': False, 'toImageButtonOptions': {
        'format': 'svg', 'filename': 'Top_slab_result', 'width': 1440, 'height': 780}}


def references(result):
    """Retain native line segments and the project's CL/face distinction."""
    elements = result['geometry'].elements
    xy = np.concatenate([np.asarray(p)[:, :2] for p in elements.values()])
    axes = result['geometry'].parent_axes
    direction = np.array(next(iter(axes.values()))['long'][:2], dtype=float)
    direction /= np.linalg.norm(direction)
    normal = np.array([-direction[1], direction[0]])
    con = result.get('connections', {})
    frame = con.get('lines')
    lines = []
    counts = {'Girder': 0, 'Diaphragm': 0}
    for row in frame.to_dict('records') if frame is not None else []:
        kind = row['Connection']
        if kind not in counts:
            continue
        a = np.array([row['X1 (m)'], row['Y1 (m)']], dtype=float)
        b = np.array([row['X2 (m)'], row['Y2 (m)']], dtype=float)
        if not np.isfinite([a, b]).all() or np.linalg.norm(b-a) < 1e-10:
            continue
        counts[kind] += 1
        lines.append({'kind': kind, 'label': ('G' if kind == 'Girder' else 'D')+str(counts[kind]),
            'source_id': str(row['ID']), 'a': a, 'b': b})
    girders = [line for line in lines if line['kind'] == 'Girder']
    ends = con.get('end_zones', {})
    bearings = []
    if ends.get('active') and ends.get('reference') in ('centerline', 'inside_face'):
        basis = np.asarray(ends['longitudinal'], dtype=float)
        transverse = np.array([-basis[1], basis[0]])
        low, high = float((xy@transverse).min()), float((xy@transverse).max())
        for zone in ends['zones']:
            side = zone['Side']
            station = float(zone['To station (m)'] if side == 'Left' else zone['From station (m)'])
            absolute = float(ends['origin_s_m'])+station
            a, b = absolute*basis+low*transverse, absolute*basis+high*transverse
            points = []
            for line in girders:
                start, delta = line['a'], line['b']-line['a']
                denominator = float(delta@basis)
                if abs(denominator) < 1e-10:
                    continue
                ratio = (absolute-float(start@basis))/denominator
                if -1e-8 <= ratio <= 1+1e-8:
                    points.append(start+np.clip(ratio, 0, 1)*delta)
            bearings.append({'side': side, 'station_m': station, 'a': a, 'b': b,
                'points': points, 'reference': ends['reference'],
                'label': 'Bearing '+('CL' if ends['reference'] == 'centerline' else 'inside face')+' '+side[0]})
    return {'lines': lines, 'girders': girders, 'bearings': bearings,
        'direction': direction, 'normal': normal, 'xy': xy}


def _position(line):
    a, b = line['a'], line['b']
    if abs(a[1]-b[1]) < 2e-5:
        return f"Y={((a[1]+b[1])/2):+.2f} m"
    if abs(a[0]-b[0]) < 2e-5:
        return f"X={((a[0]+b[0])/2):+.2f} m"
    return ''


def _register(fig, refs, mode):
    meta = dict(fig.layout.meta or {})
    meta.update(slab_print_version=VERSION, slab_print_mode=mode,
        girder_count=len(refs['girders']), bearing_stations_m=[b['station_m'] for b in refs['bearings']],
        bearing_reference=refs['bearings'][0]['reference'] if refs['bearings'] else None,
        reference_source='Imported connection lines and confirmed project bearing offsets',
        bearing_symbols_are_footprints=False)
    fig.update_layout(meta=meta)


def add_plan_references(fig, result):
    refs = references(result)
    for kind, color, dash, name in [('Girder', GIRDER, 'dash', 'I-girder CL'),
                                   ('Diaphragm', DIAPHRAGM, 'dot', 'Diaphragm CL')]:
        lines = [line for line in refs['lines'] if line['kind'] == kind]
        if not lines:
            continue
        xy = np.concatenate([np.vstack((line['a'], line['b'], [np.nan, np.nan])) for line in lines])
        fig.add_trace(go.Scatter(x=xy[:, 0], y=xy[:, 1], mode='lines',
            line={'color': color, 'dash': dash, 'width': 1.15}, name=name,
            hoverinfo='skip', connectgaps=False, meta={'slab_context': kind}))
    for line in refs['girders']:
        point = max((line['a'], line['b']), key=lambda p: (p[0], p[1]))
        text = line['label']+' · '+_position(line) if _position(line) else line['label']
        fig.add_annotation(x=float(point[0]), y=float(point[1]), xref='x', yref='y',
            text=text, showarrow=False, xanchor='left', yanchor='middle', xshift=13,
            bgcolor='rgba(255,255,255,.96)', borderpad=2,
            font={'size': 12, 'color': '#263c4a'}, name='slab-girder-'+line['label'],
            hovertext='Imported frame IDs: '+escape(line['source_id']))
    if refs['bearings']:
        xy = np.concatenate([np.vstack((b['a'], b['b'], [np.nan, np.nan])) for b in refs['bearings']])
        reference = refs['bearings'][0]['reference']
        fig.add_trace(go.Scatter(x=xy[:, 0], y=xy[:, 1], mode='lines',
            line={'color': BEARING, 'dash': 'dashdot', 'width': 1.2},
            name='Bearing '+('CL' if reference == 'centerline' else 'inside face'), hoverinfo='skip',
            connectgaps=False, meta={'slab_context': 'Bearing'}))
        points = [p for b in refs['bearings'] for p in b['points']]
        if points:
            xy = np.asarray(points)
            fig.add_trace(go.Scatter(x=xy[:, 0], y=xy[:, 1], mode='markers',
                marker={'symbol': 'square-open', 'size': 8, 'color': BEARING, 'line': {'width': 1.3}},
                name='Bearing reference points', showlegend=False,
                hovertemplate='Girder / bearing reference intersection<br>Symbol is not a bearing footprint<extra></extra>',
                meta={'slab_context': 'Bearing markers'}))
        for bearing in refs['bearings']:
            point = max((bearing['a'], bearing['b']), key=lambda p: p[1])
            fig.add_annotation(x=float(point[0]), y=float(point[1]), xref='x', yref='y',
                text=f"{bearing['label']}<br>s={bearing['station_m']:.2f} m", showarrow=False,
                xanchor='left' if bearing['side'] == 'Left' else 'right', yanchor='bottom', yshift=10,
                bgcolor='rgba(255,255,255,.96)', borderpad=2, font={'size': 12, 'color': BEARING},
                name='slab-bearing-'+bearing['side'])
    _register(fig, refs, 'plan')
    return apply_print_layout(fig)


def add_profile_references(fig, result):
    refs = references(result)
    for bearing in refs['bearings']:
        station = bearing['station_m']
        fig.add_shape(type='line', x0=station, x1=station, y0=0, y1=1, xref='x', yref='paper',
            line={'color': BEARING, 'width': 1.2, 'dash': 'dashdot'}, layer='above',
            name='slab-bearing-'+bearing['side'])
        fig.add_annotation(x=station, y=1.015, xref='x', yref='paper',
            text=f"{bearing['label']} · s={station:.2f} m", showarrow=False,
            xanchor='left' if bearing['side'] == 'Left' else 'right', yanchor='bottom',
            font={'size': 12, 'color': BEARING}, name='slab-bearing-'+bearing['side'])
    pieces = [line['label']+' '+_position(line) for line in refs['girders']]
    if pieces:
        text = 'I-girder plan CLs: '+'<br>'.join(' · '.join(pieces[i:i+3]) for i in range(0, len(pieces), 3))
        fig.add_annotation(x=.5, y=0, yshift=-62, xref='paper', yref='paper', text=text,
            showarrow=False, xanchor='center', yanchor='top', font={'size': 12, 'color': '#3e5360'},
            name='slab-girder-key')
    _register(fig, refs, 'profile')
    return apply_print_layout(fig)


def apply_print_layout(fig):
    """Idempotent final layer, also reapplied after global Plotly readability."""
    meta = fig.layout.meta or {}
    if not isinstance(meta, dict) or meta.get('slab_print_version') != VERSION:
        return fig
    for trace in fig.data:
        trace_meta = trace.meta if isinstance(trace.meta, dict) else {}
        if trace_meta.get('slab_context') in ('Girder', 'Diaphragm', 'Bearing', 'Support faces'):
            trace.line.width = 1.2 if trace_meta['slab_context'] == 'Bearing' else 1.15
    for annotation in fig.layout.annotations:
        if str(annotation.name or '').startswith(('slab-girder-', 'slab-bearing-')):
            annotation.font.size = 13 if annotation.name == 'slab-girder-key' else 14
    fig.update_layout(paper_bgcolor='#ffffff', plot_bgcolor='#ffffff',
        legend={'bgcolor': '#ffffff', 'bordercolor': '#dce2e7', 'borderwidth': 1,
                'yref': 'container', 'y': .02, 'yanchor': 'bottom'})
    if meta.get('slab_print_mode') == 'plan':
        fig.update_layout(height=max(660, 270+38*int(meta.get('girder_count', 0))),
            margin={'l': 70, 'r': 86, 't': 86, 'b': 130},
            xaxis={'domain': [0, .78]})
    else:
        fig.update_layout(height=650, margin={'l': 76, 'r': 42, 't': 90, 'b': 178})
        for annotation in fig.layout.annotations:
            if annotation.name == 'slab-girder-key':
                annotation.update(y=0, yshift=-62, yanchor='top')
    return fig
