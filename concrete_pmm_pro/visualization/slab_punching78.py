"""Local actual-thickness shear index on the accepted slab plan system."""
from html import unescape
import numpy as np
import plotly.graph_objects as go
from shapely.geometry import LineString

from concrete_pmm_pro.analysis.slab_punching78 import map_adapter, VERSION
from concrete_pmm_pro.visualization.slab_shell56 import plan_figure, element_envelope, ALL_CASES
from concrete_pmm_pro.visualization.slab_print72 import UNKNOWN, GIRDER, apply_print_layout
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability


def figure(result, case=ALL_CASES):
    screen = result['punching_screen78']
    adapted = map_adapter(result, screen)
    fig = plan_figure(adapted, view='Overall section', case=case)
    selected = element_envelope(adapted, view='Overall section', case=case)
    # Physical contact widths are geometry, never inferred from a force peak.
    for support in result.get('supports', []):
        polygon = LineString([support['a'], support['b']]).buffer(support['half_width'], cap_style=2)
        if polygon.is_empty:
            continue
        points = np.asarray(polygon.exterior.coords)
        fig.add_shape(type='path', path='M '+' L '.join(f'{x:.12g},{y:.12g}' for x, y in points)+' Z',
            fillcolor=UNKNOWN, line={'color': GIRDER, 'width': .6}, opacity=.95, layer='above')
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
        marker={'symbol': 'square', 'size': 10, 'color': UNKNOWN},
        name='Contact / omitted scope', hoverinfo='skip'))
    # Replace misleading full-strength status in shared-map hover text.
    for trace in fig.data:
        if trace.name == 'Source details' and trace.text is not None:
            texts = []
            for t in trace.text:
                text = str(t).replace('D/C =', 'Local D/C =')
                elem = unescape(str(t).split(' · ')[0])
                if elem in selected.index:
                    row = selected.loc[elem]
                    text += f"<br>Actual h={row['Thickness (mm)']:.3f} mm; dv={row['dv (mm)']:.3f} mm"
                texts.append(text)
            trace.text = tuple(texts)
    fig.data = tuple(t for t in fig.data if not str(t.name).startswith('Gov. D/C'))
    known = screen['rows'].loc[screen['rows']['Local D/C'].notna()]
    if case != ALL_CASES:
        known = known.loc[known.OutputCase.eq(case)]
    if len(known):
        governor = known.loc[known['Local D/C'].idxmax()]
        fig.add_trace(go.Scatter(x=[governor['X (m)']], y=[governor['Y (m)']], mode='markers',
            marker={'symbol': 'diamond-open', 'size': 13, 'color': '#111827', 'line': {'width': 2}},
            name=f"Gov. local {governor['Local D/C']:.3f}", cliponaxis=False,
            hovertemplate=f"{governor.OutputCase}<br>Local D/C {governor['Local D/C']:.6f}<br>Actual h={governor['Thickness (mm)']:.3f} mm<br>Physical-perimeter acceptance remains separate<extra></extra>"))
    fig.update_layout(title_text='Punching review · local D/C using actual thickness',
        uirevision=VERSION+':'+case,
        meta={**dict(fig.layout.meta or {}), 'punching_version': VERSION,
            'bound_not_actual_perimeter_ratio': True, 'source_actions_multiplier': 1.,
            'quantity': screen['quantity'], 'thickness_basis': screen['thickness_basis'],
            'full_deck_acceptance': False})
    return apply_print_layout(apply_global_plot_readability(fig))
