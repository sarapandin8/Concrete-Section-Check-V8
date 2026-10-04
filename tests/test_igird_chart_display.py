"""Check visible scalar envelopes and duplicate legends without altering engineering results."""
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.visualization.igird_uls_chart_display import (
    deduplicate_coincident_flexure_capacity, interface_station_envelope,
)


def source_rows():
    rows = []
    for step, occurrence, factor in [('Max', 1, .4), ('Min', 1, 1.), ('Max', 2, .5), ('Min', 2, .9)]:
        for x in [0, 1, 2]:
            rows.append({'Case': f'ENV_ULS / Left Exterior Girder / {step} / set {occurrence}',
                'Station x (m)': x, 'Governing x': f'{x:.3f} m', 'vui (MPa)': factor*(x+1),
                'phi vni (MPa)': 4.-x, 'Strength D/C': factor*(x+1)/(4.-x),
                'Minimum Avf D/C': .3, 'Status': 'PASS',
                'Demand kN-m': 100.*factor*(x+1), 'Capacity kN-m': 500.*(x+1),
                'Utilization value': .2*factor, 'Capacity plot sign': 1., 'Numerical status': 'PASS'})
    return pd.DataFrame(rows)


def test_interface_envelope_includes_both_bounds_and_occurrences_without_changing_rows():
    source = source_rows()
    before = source.copy(deep=True)
    envelope = interface_station_envelope(source)
    assert envelope['vui (MPa)'].tolist() == [1., 2., 3.]
    assert envelope['phi vni (MPa)'].tolist() == [4., 3., 2.]
    assert envelope['Demand source case'].str.endswith('Min / set 1').all()
    assert envelope['Source rows'].tolist() == [4, 4, 4]
    pd.testing.assert_frame_equal(source, before)


def test_interface_retains_a_gap_where_all_resistance_values_are_unavailable():
    source = source_rows()
    source.loc[source['Station x (m)'].eq(1), 'phi vni (MPa)'] = float('nan')
    envelope = interface_station_envelope(source)
    assert math.isnan(envelope.iloc[1]['phi vni (MPa)'])
    fig = ap._igird_interface_figure(source, code_label='AASHTO LRFD 9th Edition', member_length_m=20)
    capacity = next(t for t in fig.data if t.name == 'φvni')
    assert capacity.connectgaps is False and math.isnan(capacity.y[1])


def test_interface_figure_has_one_blue_demand_one_red_resistance_and_the_original_governing_row():
    source = source_rows()
    gov = ap._igird_interface_governing_row(source)
    fig = ap._igird_interface_figure(source, code_label='AASHTO LRFD 9th Edition', member_length_m=20)
    assert [t.name for t in fig.data] == ['vui max', 'φvni', 'Gov.']
    assert fig.data[0].line.color == ap._BEAM_ULS_DEMAND_LINE_STYLE['color']
    assert fig.data[1].line.color == ap._BEAM_ULS_CHECK_LINE_STYLE['color']
    assert fig.data[1].line.dash == 'dash'
    assert list(fig.data[2].customdata[0]) == [gov['Case'], gov['Strength D/C']]
    assert tuple(fig.layout.xaxis.range) == (0, 20)


def test_interface_lower_resistance_curve_does_not_recalculate_mixed_case_dc():
    source = source_rows()
    source.loc[0, 'phi vni (MPa)'] = .1
    before = source.copy(deep=True)
    envelope = interface_station_envelope(source)
    assert envelope.iloc[0]['phi vni (MPa)'] == .1
    assert envelope.iloc[0]['Resistance source case'].endswith('Max / set 1')
    assert envelope.iloc[0]['Demand source case'].endswith('Min / set 1')
    assert 'Strength D/C' not in envelope
    pd.testing.assert_frame_equal(source, before)


def make_flexure():
    result = source_rows()
    active = result.rename(columns={'Case': 'Case Name', 'Demand kN-m': 'Mux'})
    return ap._make_beam_uls_flexure_preview_figure(active, result, code_label='AASHTO LRFD 9th Edition')


def test_flexure_short_labels_keep_all_four_source_vectors_and_one_coincident_capacity():
    fig = make_flexure()
    demands = {t.name: (list(t.x), list(t.y)) for t in fig.data if str(t.name).startswith('Demand Mux')}
    polished = ap._polish_igird_uls_flexure_legend(fig)
    assert {'Mux Max 1', 'Mux Max 2', 'Mux Min 1', 'Mux Min 2'} <= {t.name for t in polished.data}
    for t in polished.data:
        if str(t.name).startswith('Mux '):
            original = 'Demand Mux — '+t.customdata[0][0]
            assert (list(t.x), list(t.y)) == demands[original]
            assert t.line.color == ap._BEAM_ULS_DEMAND_LINE_STYLE['color']
    assert len([t for t in polished.data if t.name == 'φMn']) == 1
    names = [t.name for t in polished.data if t.showlegend is not False]
    assert len(names) == len(set(names))


def test_different_resistance_paths_remain_but_share_one_legend_entry():
    fig = make_flexure()
    capacities = [t for t in fig.data if t.name == 'φMn']
    capacities[-1].y = [1., 2., 3.]
    before = [(list(t.x), list(t.y)) for t in capacities]
    deduplicate_coincident_flexure_capacity(fig)
    after = [t for t in fig.data if t.name == 'φMn']
    assert len(after) == 4
    assert [(list(t.x), list(t.y)) for t in after] == before
    assert sum(t.showlegend for t in after) == 1


def test_missing_equilibrium_paths_are_not_joined_or_deduplicated_away():
    fig = make_flexure()
    capacities = [t for t in fig.data if t.name == 'φMn']
    capacities[0].y = [float('nan'), 1000., 1500.]
    deduplicate_coincident_flexure_capacity(fig)
    after = [t for t in fig.data if t.name == 'φMn']
    assert len(after) == 4 and math.isnan(after[0].y[0])
    assert all(t.connectgaps is False for t in after)


def test_partial_case_paths_can_coincide_only_with_a_covering_original_curve():
    fig = go.Figure([go.Scatter(x=[0,1,2], y=[0,10,0], name='φMn'),
        go.Scatter(x=[1], y=[10], name='φMn')])
    deduplicate_coincident_flexure_capacity(fig)
    assert len(fig.data) == 1 and list(fig.data[0].x) == [0,1,2]
    disjoint = go.Figure([go.Scatter(x=[0,1], y=[0,10], name='φMn'),
        go.Scatter(x=[2,3], y=[10,0], name='φMn')])
    deduplicate_coincident_flexure_capacity(disjoint)
    assert len(disjoint.data) == 2
