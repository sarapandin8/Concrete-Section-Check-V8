"""Actual Streamlit registration and source-preserving CSI legend regression.

The same stored Max/Min figures must render in member and detail workspaces.
No solver, imported force, capacity, or engineering acceptance is changed.
"""
from copy import deepcopy
from unittest.mock import patch

import plotly.graph_objects as go
import pytest
import streamlit as st

from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.visualization.igird_uls_chart_display import (
    compact_csi_flexure_demand_labels,
)
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability


RENDER_APP = '''
from copy import deepcopy
import plotly.graph_objects as go
import streamlit as st
from concrete_pmm_pro.ui.igird_maxmin_charts import BoundFamily, render_bound_figures
family=BoundFamily('same-source-family',
    {'case':'U1A','source_file':'QA.xlsx','distance_column':'Girder Distance'},
    {'Max':('Max set 1',),'Min':('Min set 1',)})
figures={step:go.Figure(go.Scatter(x=[0,10,20], y=[0,200,0])).update_layout(
    title=step, meta={'igird_maxmin_step':step,
        'igird_maxmin_selected_control':{},'igird_maxmin_stored_rows':3})
    for step in ('Max','Min')}
for scope in ('member_left_Flexure','final_composite_Flexure','report_Flexure'):
    render_bound_figures(deepcopy(figures),family=family,key_prefix=scope)
st.success('All six charts rendered')
'''


def test_identical_stored_bounds_render_in_collection_detail_and_report():
    if not isinstance(st.__dict__.get('__version__'), str):
        pytest.skip('Real AppTest requires Streamlit; preload it before pytest to bypass the legacy import-only stub.')
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_string(RENDER_APP, default_timeout=30).run()
    assert not app.exception, [item.message for item in app.exception]
    charts = app.get('plotly_chart')
    assert len(charts) == 6
    identities = [chart.proto.id for chart in charts]
    assert len(set(identities)) == 6
    app.run()
    assert not app.exception
    assert [chart.proto.id for chart in app.get('plotly_chart')] == identities
    assert app.success[0].value == 'All six charts rendered'


def test_explicit_chart_key_survives_legacy_width_fallback():
    calls = []

    def plotly_chart(fig, **kwargs):
        calls.append(kwargs)
        if 'width' in kwargs:
            raise TypeError('old Streamlit width API')

    fig = go.Figure(go.Scatter(x=[0, 20], y=[0, 0]))
    with patch.object(ap.st, 'plotly_chart', side_effect=plotly_chart):
        ap._render_beam_uls_browser_plotly_figure(fig, key='detail_max', interactive=True)
    assert len(calls) == 2
    assert all(call['key'] == 'detail_max' for call in calls)
    assert calls[1]['use_container_width'] is True


def test_global_readability_keeps_bound_notes_wrapped_and_engineering_metadata_exact():
    lines = ['Blue: signed Mux. Red: stored sectional resistance. '*4,
             'Max control (D/C): unavailable at physical end; original FAIL remains.',
             'All LCs: source and development gates remain required.']
    fig = go.Figure(go.Scatter(x=[0, 20], y=[200, 0], name='Mux Max 1'))
    fig.update_layout(meta={'igird_maxmin_check':'Flexure','igird_report_note':lines})
    fig.add_annotation(name='igird_report_note', text='<br>'.join(lines), x=.5, y=-.47,
                       xref='paper', yref='paper')
    previous = deepcopy(fig)
    for _ in range(2):
        apply_global_plot_readability(fig)
        assert dict(fig.layout.meta) == dict(previous.layout.meta)
        assert fig.data[0].to_plotly_json() == previous.data[0].to_plotly_json()
        wrapped = fig.layout.annotations[0].text.split('<br>')
        assert all(len(line) <= 90 for line in wrapped)
        assert fig.layout.margin.b >= 224
        assert fig.layout.legend.itemwidth == 40
        assert fig.layout.legend.entrywidth == 135


@pytest.mark.parametrize('location', ['', 'Before / ', 'After / '])
def test_native_location_names_have_distinct_short_legends_and_original_vectors(location):
    fig = go.Figure()
    for step in ('Max', 'Min'):
        for occurrence in (1, 2):
            case = f'BOBJ1 / Left Exterior Girder / source.xlsx / U1A / {step} / {location}set {occurrence}'
            custom = [[case, case, 'Bridge Object Girder Forces', 4, 'original source'] for _ in range(3)]
            fig.add_trace(go.Scatter(name='Demand Mux — '+case, x=[0, 10, 20],
                y=[1, 200*occurrence, 2], customdata=custom, line={'color':'blue'}))
    original = deepcopy(fig)
    compact_csi_flexure_demand_labels(fig)
    assert [trace.name for trace in fig.data] == ['Mux Max 1','Mux Max 2','Mux Min 1','Mux Min 2']
    for trace, old in zip(fig.data, original.data):
        assert tuple(trace.x) == tuple(old.x)
        assert tuple(trace.y) == tuple(old.y)
        assert list(map(list, trace.customdata)) == list(map(list, old.customdata))
        assert trace.line.color == old.line.color
        assert 'customdata[1]' in trace.hovertemplate
