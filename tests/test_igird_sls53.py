"""Acceptance scope, missing input, runtime binding and chart regression."""
from copy import deepcopy
import math
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json
from concrete_pmm_pro.ui import analysis_page as ap, igird_sls53_results as results
from concrete_pmm_pro.visualization.igird_sls53 import stress_figure

ROOT = Path(__file__).resolve().parents[1]


def seed():
    state = {}
    apply_project_to_session_state(project_from_json(
        (ROOT/'qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()), state)
    return state


def test_fingerprint_tracks_every_force_cell_material_and_profile_but_not_view():
    state = seed()
    state['beam_sls_loads_table'] = pd.DataFrame([
        {'Station x (m)': i/10, 'Case Name': 'A', 'N': 0., 'Mx': 1.} for i in range(201)])
    initial = results.fingerprint(state)
    state['igird_sls53_case_Service_stage'] = 'B'
    state['igird_sls53_component'] = 'CIP / topping'
    state['igird_sls53_stage'] = 'Transfer stage'
    assert results.fingerprint(state) == initial
    state['beam_sls_loads_table'].loc[100, 'Mx'] = 2.
    assert results.fingerprint(state) != initial
    state['beam_sls_loads_table'].loc[100, 'Mx'] = 1.
    state['girder_code_loss_fci_mpa'] = 20.
    assert results.fingerprint(state) != initial
    state['girder_code_loss_fci_mpa'] = 25.
    signature = results.fingerprint(state)
    state['girder_tension_limit_bonded_confirm_Test'] = True
    assert results.fingerprint(state) != signature


@pytest.mark.parametrize('bad', [None, '', 'broken', float('nan'), float('inf'), True])
def test_invalid_source_is_never_silently_zero(bad):
    with pytest.raises(ValueError, match='finite number'):
        results.validate_source([{'Station x (m)': 0., 'N': 0., 'Mx': bad}], 20.)


def test_zero_allowable_is_infinite_and_failing_case_cannot_be_hidden():
    rows = [{'Status': 'Preview PASS', 'Case Name': 'A', 'Utilization': .8},
            {'Status': 'Preview FAIL', 'Case Name': 'B', 'Utilization': '∞'}]
    assert results.overall_status(rows) == 'Preview FAIL'
    assert results.controlling(rows)['Case Name'] == 'B'
    assert results.ratio('∞') == math.inf
    assert results.overall_status([{'Status': 'REVIEW', 'Utilization': None}]) == 'REVIEW'


def test_chart_preserves_unknown_points_endpoint_stress_and_full_span():
    raw = pd.DataFrame({'Station x (m)': [0., 10., 20.],
        'Top total (MPa)': [2., float('nan'), 3.], 'Bottom total (MPa)': [-4., -5., -4.]})
    case = {'raw': raw, 'split': pd.DataFrame(), 'checks': [], 'limits': {
        'Precast beam': {'compression': 20., 'x': [0., 20.], 'tension': [3., 3.]}}}
    fig = stress_figure(case, stage='Service stage', component='Precast beam', span_m=20.)
    assert list(fig.layout.xaxis.range) == [0., 20.]
    top = next(t for t in fig.data if t.name == 'Top fiber')
    assert list(top.y)[0] == 2. and list(top.y)[-1] == 3.
    assert math.isnan(list(top.y)[1]) and top.connectgaps is False
    assert not fig.layout.annotations
    assert len({t.line.color for t in fig.data}) == 4


def test_actual_app_calculate_only_review_filters_and_stale_handoff():
    state = seed()
    # Distinct hypothetical Service cases: a passing view must never mask the
    # high-moment failing case in the all-case stage handoff.
    table = pd.DataFrame(state['beam_sls_loads_table'])
    service = table.loc[table['Stage'] == 'Service stage'].iloc[0].to_dict()
    sources = [r for r in table.to_dict('records') if r['Stage'] != 'Service stage']
    for case, moment in [('QA-small', 0.), ('QA-high', 100000.)]:
        sources.extend({**service, 'Case Name': case, 'Station x (m)': x, 'N': 0., 'Mx': moment}
                       for x in (0., 10., 20.))
    state['beam_sls_loads_table'] = pd.DataFrame(sources)
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=120)
    for k, v in state.items():
        app.session_state[k] = deepcopy(v)
    app.session_state['_nav_active_workspace'] = 'Analysis'
    app.session_state['_nav_analysis_subpage'] = 'SLS / Stress & Cracking'
    def run():
        app.run(timeout=120)
        assert not app.exception, [e.message for e in app.exception]
        assert not app.error, [e.value for e in app.error]
    with patch.object(ap, '_girder_full_length_sls_stage_rows', wraps=ap._girder_full_length_sls_stage_rows) as engine:
        run()
        assert engine.call_count == 0
        next(b for b in app.button if b.key == 'igird_sls53_calculate').click()
        run()
        calls = engine.call_count
        assert calls == 4
        summary = deepcopy(app.session_state['result_summary_beam_girder_sls_stage_summary_rows'])
        service_summary = next(r for r in summary if r['Stage'] == 'Service stage')
        assert service_summary['Status'] == 'Preview FAIL'
        assert service_summary['Case Name'] == 'QA-high' and service_summary['Cases checked'] == 2
        signature = app.session_state[results.HANDOFF_KEY]
        next(s for s in app.selectbox if s.label == 'Load case to review').set_value('QA-small')
        run()
        assert engine.call_count == calls
        assert app.session_state['result_summary_beam_girder_sls_stage_summary_rows'] == summary
        next(r for r in app.radio if r.label == 'Concrete component').set_value('CIP / topping')
        run()
        assert engine.call_count == calls
        next(r for r in app.radio if r.label == 'Stage to review').set_value('Transfer stage')
        run()
        assert engine.call_count == calls
        assert app.session_state['result_summary_beam_girder_sls_stage_summary_rows'] == summary
        assert app.session_state[results.HANDOFF_KEY] == signature
        for workspace in ['Result Summary', 'Report / QA']:
            app.session_state['_nav_active_workspace'] = workspace
            run()
            assert engine.call_count == calls
        app.session_state['girder_code_loss_fci_mpa'] = 12.
        assert not results.handoff_is_current(app.session_state.filtered_state)
        # Downstream render remains read-only even while rejecting a stale result.
        run()
        assert engine.call_count == calls
        app.session_state['_nav_active_workspace'] = 'Analysis'
        app.session_state['_nav_analysis_subpage'] = 'SLS / Stress & Cracking'
        run()
        assert results.HANDOFF_KEY not in app.session_state
        assert results.current(app.session_state.filtered_state) is None
