"""Actual app.py: collection plus detailed Flexure, read-only report, chart export.

Archived CSI forces with a hypothetical section model; not project approval.
"""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import logging
import os
from pathlib import Path
import pickle
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json
from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY, BANK_KEY
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui import igird_maxmin_charts as mm
from qa.igird_maxmin10_model import native_model

logging.getLogger('streamlit').setLevel(logging.ERROR)
OUT = ROOT / 'qa/evidence/igird_flexchart24'
OUT.mkdir(parents=True, exist_ok=True)
state = {}
apply_project_to_session_state(project_from_json(
    (ROOT/'qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()), state)
state.update(native_model(second_lc=False))
state['_nav_active_workspace'] = 'Analysis'
state['_nav_analysis_subpage'] = 'ULS Strength'
app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=120)
for key, value in state.items():
    app.session_state[key] = deepcopy(value)
figures = []
calls = {'calculate': 0}
original_render = ap._render_beam_uls_browser_plotly_figure
original_calculate = mr.calculate_member


def capture(fig, **kwargs):
    original_render(fig, **kwargs)
    if (fig.layout.meta or {}).get('igird_maxmin_check') == 'Flexure':
        figures.append(deepcopy(fig))


def counted(*args, **kwargs):
    calls['calculate'] += 1
    return original_calculate(*args, **kwargs)


def run():
    figures.clear()
    app.run(timeout=120)
    assert not app.exception, [item.message for item in app.exception]


def element(items, label):
    return next(item for item in items if item.label == label)


with patch.object(ap, '_render_beam_uls_browser_plotly_figure', side_effect=capture), \
        patch.object(mr, 'calculate_member', side_effect=counted):
    run()
    element(app.radio, 'Flexure stage').set_value('Final — Composite')
    run()
    next(item for item in app.button if item.label.startswith('Calculate Flexure — all 2 girders')).click()
    run()
    assert calls['calculate'] == 2
    assert len(figures) == 4
    before = {key: pickle.dumps(app.session_state[key]) for key in
        (ACTIVE_KEY, BANK_KEY, 'beam_uls_loads_table', mr.CACHE_KEY,
         ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY)}
    with ExitStack() as stack:
        for name in ('_beam_uls_calculate_selected_check', '_beam_uls_flexure_preview_dataframe'):
            stack.enter_context(patch.object(ap, name, side_effect=AssertionError('Review solver: '+name)))
        stack.enter_context(patch.object(mr, 'calculate_member', side_effect=AssertionError('Review member solve')))
        app.toggle(key='igird_compact_details_Flexure').set_value(True)
        run()
        assert len(figures) == 6
        charts = app.get('plotly_chart')
        assert len(set(chart.proto.id for chart in charts)) == len(charts)
        assert any(button.label == 'Calculate Final Composite Flexure' for button in app.button)
        demand_figures = deepcopy(figures)
        for radio in app.radio:
            if radio.label == 'Chart view':
                radio.set_value(mm.UTILIZATION_VIEW)
        run()
        assert len(figures) == 6
        for key, previous in before.items():
            assert pickle.dumps(app.session_state[key]) == previous, key
        for radio in app.radio:
            if radio.label == 'Chart view':
                radio.set_value(mm.DEMAND_VIEW)
        run()
        assert len(figures) == 6
        for key, previous in before.items():
            assert pickle.dumps(app.session_state[key]) == previous, key
        if os.environ.get('CSP_FLEXCHART24_INTERNAL_SEED'):
            buttons = {button.key for button in app.button}
            seed = {key: value for key, value in app.session_state.filtered_state.items() if key not in buttons}
            Path(os.environ['CSP_FLEXCHART24_INTERNAL_SEED']).write_bytes(pickle.dumps(seed))
        app.session_state['_nav_active_workspace'] = 'Report / QA'
        run()
        assert len(figures) == 2
        for key, previous in before.items():
            assert pickle.dumps(app.session_state[key]) == previous, key
    for figure in demand_figures[-2:]:
        step = figure.layout.meta['igird_maxmin_step'].lower()
        figure.write_json(OUT/f'flexure_{step}.plotly.json')
        figure.write_image(OUT/f'flexure_{step}.png', width=1440, height=560, scale=2)

record = {'milestone':'IGIRDER.FLEXCHART24','status':'PASS','entrypoint':'app.py',
    'scope':'Archived CSI forces and hypothetical section; not current rev1 project approval',
    'members':2,'member_max_min_charts':4,'member_plus_detail_charts':6,
    'demand_and_utilization_views':True,'streamlit_exceptions':0,
    'review_solver_calls':0,'input_and_result_snapshots_unchanged':True,
    'report_read_only':True,'export_png_size_px':[2880,1120]}
(OUT/'app_checks.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2), flush=True)
