"""One chart grammar for staged I-girder SLS; stored stresses only."""
import math
from html import escape
import textwrap
import pandas as pd
import plotly.graph_objects as go

COLORS = {'top': '#1565c0', 'bottom': '#008577', 'compression': '#c62828',
          'tension': '#c2185b', 'governing': '#263238'}


def apply_sls_layout(fig):
    """Keep the same legend footprint after the app's global readability pass."""
    fig.update_layout(legend={'itemwidth': 35, 'entrywidth': 112,
        'entrywidthmode': 'pixels', 'font': {'size': 12},
        'x': .5, 'xanchor': 'center', 'y': -.22, 'yanchor': 'top'})
    return fig


def stress_figure(case_result, *, stage, component, span_m, context_label=''):
    split = case_result['split']
    data = case_result['raw']
    fig = go.Figure()
    fibers = []
    if not split.empty:
        data = split.loc[split['Concrete component'] == component]
        for fiber in data['Fiber'].drop_duplicates():
            points = data.loc[data['Fiber'] == fiber].sort_values('Station x (m)')
            fibers.append(('Top' if str(fiber).startswith('Top') else 'Bottom',
                           points['Station x (m)'].tolist(), points['Total stress (MPa)'].tolist()))
    else:
        for name, col in [('Top', 'Top total (MPa)'), ('Bottom', 'Bottom total (MPa)')]:
            points = data.sort_values('Station x (m)')
            fibers.append((name, points['Station x (m)'].tolist(), points[col].tolist()))
    for name, x, y in sorted(fibers):
        fig.add_trace(go.Scatter(x=x, y=y, name=name+' fiber', mode='lines+markers',
            line={'color': COLORS[name.lower()], 'width': 2.6, 'dash': 'solid' if name == 'Top' else 'dash'},
            marker={'size': 4, 'symbol': 'circle' if name == 'Top' else 'square'}, cliponaxis=False,
            connectgaps=False, hovertemplate=name+' · %{y:.3f} MPa<extra></extra>'))
    limits = case_result['limits'][component]
    fig.add_trace(go.Scatter(x=[0, span_m], y=[-limits['compression']]*2,
        name='Compression limit', mode='lines', line={'color': COLORS['compression'], 'dash': 'dash', 'width': 1.7},
        hovertemplate='Compression limit · %{y:.3f} MPa<extra></extra>'))
    fig.add_trace(go.Scatter(x=limits['x'], y=limits['tension'], name='Tension limit', mode='lines',
        line={'color': COLORS['tension'], 'dash': 'dot', 'width': 1.9},
        connectgaps=False, hovertemplate='Tension limit · %{y:.3f} MPa<extra></extra>'))
    checks = [r for r in case_result['checks'] if r.get('Concrete component', 'Precast beam') == component]
    # Hover carries the detail. Text placed on curves collided with limits and
    # endpoint stresses in the old graph, especially on narrow screens.
    for row in checks:
        x, y = row.get('Station x (m)'), row.get('Actual stress (MPa)')
        if x is not None and y is not None and math.isfinite(float(y)):
            fig.add_trace(go.Scatter(x=[x], y=[y], name=str(row.get('Controls', row.get('Demand'))),
                mode='markers', marker={'size': 10, 'symbol': 'diamond-open', 'color': COLORS['governing'], 'line': {'width': 2}},
                showlegend=False, cliponaxis=False, hovertemplate='Controlling '+str(row.get('Controls', row.get('Demand')))+
                ' · x=%{x:.3f} m<br>%{y:.3f} MPa<extra></extra>'))
    title_component = 'Slab' if component == 'CIP / topping' else 'Precast beam'
    context_lines = textwrap.wrap(context_label, width=82, break_long_words=True) if context_label else []
    title = escape(stage.replace(' stage', '')+' · '+title_component)
    if context_lines:
        title += '<br><sup>'+'<br>'.join(escape(s) for s in context_lines)+'</sup>'
    extra = 16 * max(0, len(context_lines)-1)
    fig.update_layout(template='plotly_white', height=470+extra, meta={'igird_sls_version': 'IGIRDER.SLS53'},
        title={'text': title,
               'font': {'size': 19}, 'x': .5, 'xanchor': 'center', 'y': .92, 'yanchor': 'top'},
        margin={'l': 66, 'r': 26, 't': 66+extra, 'b': 100},
        font={'family': 'Arial, sans-serif', 'size': 13, 'color': '#334155'},
        hovermode='x unified', hoverlabel={'font_size': 12},
        legend={'orientation': 'h', 'x': .5, 'xanchor': 'center', 'y': -.22,
                'yanchor': 'top', 'entrywidth': 156, 'font': {'size': 12}},
        xaxis={'title': {'text': 'Distance x (m)', 'standoff': 12}, 'range': [0, float(span_m)],
               'fixedrange': False, 'showline': True, 'linecolor': '#cbd5e1', 'automargin': True},
        yaxis={'title': {'text': 'Stress (MPa)', 'standoff': 10}, 'showline': True,
               'linecolor': '#cbd5e1', 'gridcolor': '#e8edf3', 'zeroline': True,
               'zerolinecolor': '#64748b', 'zerolinewidth': 1.2, 'automargin': True})
    return apply_sls_layout(fig)
