"""Named single-girder plots for calculated stages and CSI SLS envelopes."""
from html import escape

import plotly.graph_objects as go

from concrete_pmm_pro.visualization.igird_sls53 import COLORS, apply_sls_layout
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability


def figure(result, stage, girder=None):
    service = stage == 'Service stage'
    span = result['span_m']
    data = result['curves'].loc[result['curves'].Stage.eq(stage)]
    if service:
        girder = girder or (result['girders'][0] if result['girders'] else None)
        data = data.loc[data.Girder.eq(girder)]
    subject = girder or 'No imported girder' if service else 'single I-girder'
    source_label = 'WebTop Vert · Imported SLS envelope' if service else 'Current section model · calculated deflection / camber'
    fig = go.Figure()
    for index, (name, group) in enumerate(data.groupby('Curve', sort=False)):
        group = group.sort_values('Station x (m)')
        fig.add_trace(go.Scatter(x=group['Station x (m)'], y=group['Deflection (mm)'], name=name,
            mode='lines+markers', line={'color': COLORS['top'] if index == 0 else COLORS['bottom'],
                'width': 2.6, 'dash': 'solid' if index == 0 else 'dash'}, marker={'size': 4},
            fill='tonexty' if service and index == 1 else None, fillcolor='rgba(21,101,192,0.09)',
            connectgaps=False, cliponaxis=False,
            hovertemplate=escape(name) + '<br>x=%{x:.5f} m<br>δ=%{y:.3f} mm<extra></extra>'))
    cap = result['limit_mm'] if service else result['settings']['transfer_limit_mm' if stage == 'Transfer stage' else 'construction_limit_mm']
    if cap is not None:
        label = 'Limit' if service and result['limit_eligible'] else 'Reference' if service else 'Project'
        for sign in (-1, 1):
            fig.add_trace(go.Scatter(x=[0, span], y=[sign * cap] * 2, mode='lines',
                name=f'{label} ±{cap:.2f} mm', showlegend=sign == -1,
                line={'color': COLORS['compression'], 'width': 2.2, 'dash': 'dash'},
                hovertemplate=escape(label) + '<br>δ=%{y:.3f} mm<extra></extra>'))
    if len(data):
        row = data.loc[data['Deflection (mm)'].abs().idxmax()]
        fig.add_trace(go.Scatter(x=[row['Station x (m)']], y=[row['Deflection (mm)']],
            name='Governing response', mode='markers', showlegend=False, cliponaxis=False,
            marker={'symbol': 'diamond-open', 'size': 12, 'color': COLORS['governing'], 'line': {'width': 2}},
            hovertemplate='Governing |δ|<br>x=%{x:.5f} m<br>δ=%{y:.3f} mm<extra></extra>'))
    elif service:
        fig.add_annotation(x=.5, y=.5, xref='paper', yref='paper', showarrow=False,
            text='Upload Envelope SLS Girder Deflection<br>No calculated Service fallback',
            font={'size': 13, 'color': '#946200'}, bgcolor='white')
    fig.add_hline(y=0, line_color='#64748b', line_width=1.2)
    title = stage.replace(' stage', '') + ' deflection · ' + subject
    fig.update_layout(template='plotly_white', height=560,
        title={'text': escape(title) + '<br><sup>' + escape(source_label) + '</sup>', 'x': .5, 'xanchor': 'center'},
        margin={'l': 76, 'r': 36, 't': 88, 'b': 110}, font={'family': 'Arial, sans-serif', 'size': 13, 'color': '#334155'},
        xaxis={'title': 'Girder distance x (m)', 'range': [0, span], 'showgrid': True, 'zeroline': False, 'automargin': True},
        yaxis={'title': 'WebTop Vert (mm), as exported' if service else 'Deflection δ (mm), upward positive',
            'showgrid': True, 'zeroline': False, 'automargin': True}, hovermode='x unified',
        uirevision=result['fingerprint'] + ':' + stage + ':' + str(girder),
        meta={'version': result['version'], 'stage': stage, 'girder': girder if service else 'Current single-girder section model',
            'component': 'WebTop Vert' if service else 'Calculated vertical response',
            'source': 'Imported SLS envelope' if service else 'Generated stage loads',
            'service_available': result['service_available'], 'full_deflection_acceptance': False})
    apply_global_plot_readability(fig)
    apply_sls_layout(fig)
    fig.update_layout(legend={'orientation': 'h', 'entrywidth': 230, 'itemwidth': 35, 'y': -.23, 'traceorder': 'normal'})
    return fig
