"""Shared-style top-slab maps and station envelopes, without smoothing."""
from __future__ import annotations

from html import escape
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.analysis.slab_top65 import VERSION
from concrete_pmm_pro.visualization.slab_shell56 import ALL_CASES, plan_figure, SAFE, FAIL, UNKNOWN
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability
from concrete_pmm_pro.visualization.slab_print72 import add_profile_references


def plan(result, adapted, view, case=ALL_CASES):
    version = result.get('version', VERSION)
    fig = plan_figure(adapted, view='Overall section', case=case)
    if view.startswith(('Shear ·', 'Flexural shear tie ·')):
        direction = 'Transverse' if view.endswith('transverse') else 'Longitudinal'
        segments = []
        for support in result['supports']:
            if support['Direction'] == direction:
                for sign in (-1, 1):
                    offset = sign*support['half_width']*support['normal']
                    segments.extend([support['a']+offset, support['b']+offset, [np.nan, np.nan]])
        if segments:
            xy = np.asarray(segments)
            fig.add_trace(go.Scatter(x=xy[:, 0], y=xy[:, 1], mode='lines',
                line={'color': SAFE, 'width': 1}, hoverinfo='skip', name='Support faces', connectgaps=False,
                meta={'slab_context': 'Support faces'}))
    fig.update_layout(title_text=view+' · '+('all ULS cases' if case == ALL_CASES else escape(case)),
        uirevision=f'{version}:{view}:{case}', meta={**(fig.layout.meta or {}), 'slab_version': version,
            'aggregation': 'maximum retained actual corner/case; no averaging',
            'full_deck_acceptance': False})
    return fig


def station_envelope(adapted, case=ALL_CASES):
    """Maximum at each physical station; no spatial averaging or peak clipping.

    A fixed reference direction follows native station progression. A profile
    is declined if parent longitudinal axes differ; the plan remains available.
    Grouping at 1 nm tolerance joins floating-point copies of the same station
    only and never changes a force, capacity or governing D/C.
    """
    axes = [a['long'][:2] for a in adapted['geometry'].parent_axes.values()]
    direction = np.array(axes[0], dtype=float, copy=True)
    direction /= np.linalg.norm(direction)
    if any(not np.allclose(a, direction, atol=1e-6, rtol=0) for a in axes):
        raise ValueError('A single station profile requires parallel native longitudinal axes; use Plan map.')
    points = np.concatenate([a[:, :2] for a in adapted['geometry'].elements.values()])
    bounds = points@direction
    origin, end = float(bounds.min()), float(bounds.max())
    frame = adapted['rows']
    if case != ALL_CASES:
        frame = frame.loc[frame.OutputCase.eq(case)]
    if frame.empty:
        return pd.DataFrame(), end-origin
    work = frame[['X (m)', 'Y (m)', 'Field D/C', 'OutputCase', 'StepType', 'Joint', 'AreaElem', INCLUDED, 'Status']].copy()
    work['Station (m)'] = np.round(work[['X (m)', 'Y (m)']].to_numpy()@direction-origin, 9)
    work['Value'] = work['Field D/C'].where(work[INCLUDED])
    work['Unresolved'] = work[INCLUDED] & (work.Status.eq('REVIEW') | work['Field D/C'].isna())
    if 'Source incomplete' in frame:
        work['Unresolved'] |= frame['Source incomplete'].fillna(True)
    grouped = work.groupby('Station (m)', sort=True)
    summary = grouped.agg(**{'D/C': ('Value', 'max'), 'Retained': (INCLUDED, 'sum'),
        'Unresolved': ('Unresolved', 'any')})
    known = work.loc[work.Value.notna()]
    governors = known.loc[known.groupby('Station (m)').Value.idxmax()].set_index('Station (m)') if len(known) else known.set_index('Station (m)')
    for column in ('OutputCase', 'StepType', 'AreaElem', 'Joint', 'X (m)', 'Y (m)'):
        summary[column] = governors[column].reindex(summary.index)
    return summary.reset_index(), end-origin


def profile(adapted, view, case=ALL_CASES):
    version = adapted.get('version', VERSION)
    data, length = station_envelope(adapted, case)
    fig = go.Figure()
    if len(data):
        hover = [f"s={r['Station (m)']:.3f} m · D/C={r['D/C']:.3f}<br>"
            f"{escape(str(r.OutputCase))} / {escape(str(r.StepType))} · joint {escape(str(r.Joint))}<br>"
            f"X={r['X (m)']:.3f}, Y={r['Y (m)']:.3f} m" if pd.notna(r['D/C']) else
            'Excluded or unresolved station; no nominal D/C' for _, r in data.iterrows()]
        fig.add_trace(go.Scatter(x=data['Station (m)'], y=data['D/C'], text=hover,
            mode='lines+markers', marker={'size': 4}, line={'color': SAFE, 'width': 2.5},
            connectgaps=False, name='Known max D/C', hovertemplate='%{text}<extra></extra>'))
        unavailable = data.loc[data['D/C'].isna() | data.Unresolved]
        if len(unavailable):
            fig.add_trace(go.Scatter(x=unavailable['Station (m)'], y=np.full(len(unavailable), .025), yaxis='y2',
                mode='markers', marker={'symbol': 'line-ns-open', 'color': '#a66a12', 'size': 10},
                name='Scope / missing', hovertemplate='Scope or source review at s=%{x:.3f} m<extra></extra>'))
        known = data.loc[data['D/C'].notna()]
        if len(known):
            row = known.loc[known['D/C'].idxmax()]
            fig.add_trace(go.Scatter(x=[row['Station (m)']], y=[row['D/C']], mode='markers',
                marker={'symbol': 'diamond-open', 'size': 13, 'color': FAIL, 'line': {'width': 2}},
                name=f"Gov. D/C {row['D/C']:.3f}", cliponaxis=False))
    fig.add_trace(go.Scatter(x=[0, length], y=[1, 1], mode='lines',
        line={'color': FAIL, 'dash': 'dash', 'width': 2.5}, name='Limit = 1.0', hoverinfo='skip'))
    # Match the shared engineering chart margins / legend / font standards.
    fig.update_layout(template='plotly_white', height=560,
        title={'text': view+' · station envelope', 'x': .5, 'xanchor': 'center'},
        margin={'l': 76, 'r': 42, 't': 65, 'b': 105},
        legend={'orientation': 'h', 'x': .5, 'xanchor': 'center', 'y': -.23, 'yanchor': 'top'},
        xaxis={'title': 'Distance along bridge (m)', 'range': [0, length], 'showgrid': True, 'zeroline': False},
        yaxis={'title': 'D/C', 'rangemode': 'tozero', 'showgrid': True, 'zeroline': False},
        yaxis2={'overlaying': 'y', 'range': [0, 1], 'visible': False, 'fixedrange': True},
        hovermode='closest', uirevision=f'{version}:profile:{view}:{case}',
        meta={'slab_version': version, 'aggregation': 'maximum at each actual station; no smoothing / averaging',
              'scope_markers_use_secondary_axis': True, 'full_deck_acceptance': False})
    ends = adapted.get('connections', {}).get('end_zones', {})
    if ends.get('active'):
        for zone in ends['zones']:
            fig.add_vrect(x0=zone['From station (m)'], x1=zone['To station (m)'],
                fillcolor=UNKNOWN, opacity=.45, line_width=0, layer='below')
    add_profile_references(fig, adapted)
    return apply_global_plot_readability(fig)
