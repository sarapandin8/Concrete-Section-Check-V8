"""The displayed combined components must explain the stored numerical control."""
from copy import deepcopy
import math

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.igird_combined_vt import RESULT_VERSION
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_case_review import component_values
from concrete_pmm_pro.ui.igird_vt_workspace import make_overview_figure


def rows():
    return pd.DataFrame([{
        'Case': 'C1', 'Governing x': f'{x:.3f} m', 'Station type': 'LOAD STATION',
        'Status': 'REVIEW', 'Result version': RESULT_VERSION, 'Zone': 'Midspan',
        'Spacing mm': 200., 's max mm': 300., 'Vu kN': 300.,
        'Stress D/C value': .1, 'Conservative Veff guard D/C': 1.4,
        'Transverse D/C value': .4, 'Longitudinal D/C value': .5,
        'Spacing D/C': spacing, 'Overall D/C value': max(.5, spacing),
    } for x, spacing in [(1., .6), (2., 1.2), (3., .7)]])


def figure(frame):
    return ap._make_beam_uls_combined_vt_utilization_figure(
        frame, code_label='AASHTO LRFD 9th Edition', member_length_m=20.)


def test_spacing_governing_marker_is_explained_by_a_visible_curve():
    frame = rows()
    frame.loc[1, 'Status'] = 'FAIL'
    before = deepcopy(frame)
    fig = figure(frame)
    traces = {t.name: t for t in fig.data}
    assert list(traces['Spacing D/C'].y) == [.6, 1.2, .7]
    assert list(traces['Gov. V+T'].x) == [2.]
    assert list(traces['Gov. V+T'].y) == [1.2]
    assert traces['Spacing D/C'].line.color != traces['Transverse D/C'].line.color
    pd.testing.assert_frame_equal(frame, before)


def test_shear_limit_label_and_hover_do_not_claim_to_plot_veff():
    fig = figure(rows())
    trace = next(t for t in fig.data if t.name == 'Shear limit D/C')
    assert list(trace.y) == [.1, .1, .1]
    assert not any('Veff' in str(t.name) for t in fig.data)
    assert 'Shear limit D/C' in trace.hovertemplate
    assert list(trace.customdata[0]) == ['C1', 'Midspan', 200.]
    assert 'Zone=' in trace.hovertemplate
    assert 'Concrete shear limit' in dict(component_values(rows(), 'Shear + Torsion'))


def test_two_tension_faces_take_larger_spacing_and_retain_missingness():
    frame = pd.concat([rows(), rows()], ignore_index=True)
    frame.loc[3, 'Spacing D/C'] = .9
    frame.loc[4, 'Spacing D/C'] = float('nan')
    trace = next(t for t in figure(frame).data if t.name == 'Spacing D/C')
    assert trace.y[0] == .9
    assert math.isnan(trace.y[1])
    assert trace.y[2] == .7
    assert trace.connectgaps is False


def test_distinct_cases_keep_their_own_spacing_paths_and_source():
    second = rows().assign(Case='C2', **{'Spacing D/C': [.8, .9, 1.4]})
    fig = figure(pd.concat([rows(), second], ignore_index=True))
    traces = [t for t in fig.data if t.name == 'Spacing D/C']
    assert len(traces) == 2
    assert [list(t.y) for t in traces] == [[.6, 1.2, .7], [.8, .9, 1.4]]
    assert {row[0] for row in traces[0].customdata} == {'C1'}
    assert {row[0] for row in traces[1].customdata} == {'C2'}
    assert sum(t.showlegend is not False for t in traces) == 1


def test_unavailable_spacing_is_not_fabricated_or_extrapolated():
    frame = rows().drop(columns=['Spacing D/C'])
    fig = figure(frame)
    assert not any(t.name == 'Spacing D/C' for t in fig.data)
    assert list(fig.layout.xaxis.range) == [0., 20.]
    assert set(next(t for t in fig.data if t.name == 'Transverse D/C').x) == {1., 2., 3.}


def test_overview_and_components_agree_when_spacing_controls():
    frame = rows()
    active = pd.DataFrame({'Case Name': frame.Case, 'Station x (m)': [1., 2., 3.], 'Vuy': 300.})
    overview = make_overview_figure(active, frame, check_name='Shear + Torsion',
        code_label='AASHTO LRFD 9th Edition', span_m=20.)
    trace = next(t for t in overview.data if t.name == 'Max D/C')
    assert list(trace.y) == [.6, 1.2, .7]
    assert trace.customdata[1][1] in {'Spacing', 'Combined overall'}
    assert max(trace.y) < 1.4  # The additional Veff review screen is separate.


def test_legacy_combined_chart_retains_its_stress_label():
    fig = figure(rows().drop(columns=['Result version']))
    assert any(str(t.name).startswith('Stress D/C') for t in fig.data)
    assert not any(t.name == 'Shear limit D/C' for t in fig.data)
