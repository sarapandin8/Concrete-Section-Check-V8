"""Exact track influence / girder-contact polygons on the shared slab plan."""
from shapely.geometry import shape
import numpy as np
import plotly.graph_objects as go

from concrete_pmm_pro.analysis import slab_track77 as geometry
from concrete_pmm_pro.visualization.slab_punching64 import figure as punching_figure
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability


def _polygons(value):
    if value.is_empty:
        return
    if value.geom_type == 'Polygon':
        if value.area > 1e-10:
            yield value
    else:
        for part in getattr(value, 'geoms', ()):
            yield from _polygons(part)


def _path(polygon):
    paths = []
    for ring in (polygon.exterior, *polygon.interiors):
        coordinates = list(ring.coords)
        paths.append('M '+' L '.join(f'{x:.12g},{y:.12g}' for x, y in coordinates)+' Z')
    return ' '.join(paths)


def figure(result, case='All punching cases'):
    distribution = result['track_distribution']
    fig = punching_figure(result, case)
    # The shared plan supplies axes, structural references and real perimeters.
    # Its neutral missing-D/C fill must not cover the geometry-only colours.
    fig.data = tuple(t for t in fig.data if t.name not in ('Review / missing', 'Source details', 'D/C scale'))
    colors = [(geometry.OUTSIDE, 'Outside strip', '#e4e9ef', '#8796a5'),
              (geometry.SPREAD, '45° spread', '#9fc9ef', '#2c73b8'),
              (geometry.DIRECT, 'Direct footprint', '#e9c786', '#9c7028'),
              (geometry.SUPPORTED, 'Girder contact', '#b9bdc5', '#4e5d6f')]
    for key, name, fill, line in colors:
        value = distribution['zones'].get(key)
        if value is None:
            continue
        polygons = list(_polygons(shape(value)))
        for polygon in polygons:
            fig.add_shape(type='path', path=_path(polygon), xref='x', yref='y',
                          fillrule='evenodd', fillcolor=fill, opacity=.65,
                          line={'color': line, 'width': 1.2}, layer='below')
        if polygons:
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                marker={'symbol': 'square', 'size': 11, 'color': fill, 'line': {'color': line, 'width': 1}},
                name=name, hoverinfo='skip'))
    # Show the full physical/distributed boundaries even where the two overlap
    # a grey girder contact. Geometry colours never conceal the 2.60 m width.
    for key, name, color, dash in [('direct', 'Track edge', '#9c7028', 'dot'),
                                    ('distributed', '45° edge', '#2c73b8', 'dash')]:
        value = distribution.get('footprints', {}).get(key)
        polygons = list(_polygons(shape(value))) if value else []
        if polygons:
            xy = np.concatenate([np.vstack((np.asarray(p.exterior.coords), [np.nan, np.nan])) for p in polygons])
            fig.add_trace(go.Scatter(x=xy[:, 0], y=xy[:, 1], mode='lines', name=name,
                line={'color': color, 'width': 1.7, 'dash': dash}, hoverinfo='skip', connectgaps=False))
    bounds = distribution['deck_bounds_local']
    basis = np.asarray(distribution['basis'])
    for row in distribution['tracks'].to_dict('records'):
        p = np.array([(bounds[0]+bounds[2])/2,
                      (bounds[1]+bounds[3])/2+row['Offset from deck CL (m)']])@basis
        fig.add_annotation(x=p[0], y=p[1], text=f"{row['Track']} · B={row['Distributed width (m)']:.2f} m",
            showarrow=False, font={'size': 12, 'color': '#25364a'},
            bgcolor='rgba(255,255,255,.94)', borderpad=2)
    skipped = set(result['punching'].get('project_supported_areas', []))
    for i, area in enumerate(a for a in result['punching']['areas'] if a['Area'] in skipped):
        fig.add_trace(go.Scatter(x=[area['X (m)']], y=[area['Y (m)']], mode='markers',
            marker={'symbol': 'square-open', 'size': 13, 'color': '#4e5d6f'},
            name='Supported area', showlegend=i == 0,
            hovertemplate=area['Area']+'<br>Outside slab-only punching scope<br>Project full-contact assumption; not PASS<extra></extra>'))
    fig.update_layout(title_text='Track load distribution · 45° project assumption',
                      uirevision='SLAB.TRACK45-77:'+case)
    meta = dict(fig.layout.meta or {})
    meta.update(track_distribution_version=geometry.VERSION, color_is_utilization=False,
                code_exemption=False, full_deck_acceptance=False)
    fig.update_layout(meta=meta)
    return apply_global_plot_readability(fig)
