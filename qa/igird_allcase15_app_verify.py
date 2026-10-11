"""Real app.py selectors use cached results; the QA section is hypothetical."""
from contextlib import ExitStack
from copy import deepcopy
import argparse
import hashlib
import json
import logging
from pathlib import Path
import pickle
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json
from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY, BANK_KEY
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr, igird_maxmin_charts as mm
from concrete_pmm_pro.ui.igird_case_review import ALL_CASES
from qa.igird_allcase15_model import source_model

logging.getLogger('streamlit').setLevel(logging.ERROR)
parser = argparse.ArgumentParser()
parser.add_argument('--seed', required=True, help='Internal checkpoint outside the distributable project.')
args = parser.parse_args()
seed = Path(args.seed).resolve()
assert not seed.is_relative_to(ROOT)
seed.parent.mkdir(parents=True, exist_ok=True)
state = {}
apply_project_to_session_state(project_from_json(
    (ROOT/'qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()), state)
state.update(source_model())
at = AppTest.from_file(str(ROOT/'app.py'), default_timeout=120)
for key,value in state.items():
    at.session_state[key] = deepcopy(value)
at.session_state['_nav_active_workspace'] = 'Analysis'
figures, records = [], []
render = ap._render_beam_uls_browser_plotly_figure


def capture(fig, **kwargs):
    if str(fig.layout.title.text or '').startswith('Girder:'):
        figures.append(deepcopy(fig))
    return render(fig, **kwargs)


def element(items, label):
    return next(item for item in items if item.label == label)


def run():
    figures.clear()
    at.run(timeout=120)
    assert not at.exception, [e.message for e in at.exception]


names = ['BOBJ1 / Left Exterior Girder','BOBJ1 / Interior Girder 2']
with patch.object(mr, 'calculate_member', wraps=mr.calculate_member) as calculator, \
        patch.object(ap, '_render_beam_uls_browser_plotly_figure', capture):
    run()
    for check in ('Shear','Torsion'):
        element(at.radio, 'ULS check to calculate').set_value(check)
        run()
        element(at.button, f'Calculate {check} — all 2 girders (current model)').click()
        run()
    assert calculator.call_count == 4
    keys = (ACTIVE_KEY,BANK_KEY,'beam_uls_loads_table',mr.CACHE_KEY,ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY)
    original = {k:pickle.dumps(at.session_state[k]) for k in keys}
    with ExitStack() as stack:
        for name in ('_beam_uls_calculate_selected_check','_beam_uls_flexure_preview_dataframe',
                     '_beam_uls_igird_shear_diagram_capacity_dataframe',
                     '_beam_uls_igird_torsion_diagram_capacity_dataframe'):
            stack.enter_context(patch.object(ap,name,side_effect=AssertionError('Chart selection cannot solve')))
        stack.enter_context(patch.object(mr,'calculate_member',side_effect=AssertionError('Chart selection cannot calculate members')))
        for check in ('Shear','Torsion'):
            element(at.radio, 'ULS check to calculate').set_value(check)
            run()
            for n in names:
                element(at.selectbox,'Load case to review — '+n).set_value(ALL_CASES)
            run()
            assert len(figures) == 2
            assert all(len(f.layout.meta['member_case_legend']) == 16 for f in figures)
            assert not any(s.label == 'Case for diagram' for s in at.selectbox)
            for n in names:
                panel = element(at.expander, 'Girder: '+n)
                assert len(panel.get('plotly_chart')) == 1
                stored = element(at.expander, 'Stored check rows / source audit — '+n).dataframe[0].value
                assert stored.Case.nunique() == 16
                token = hashlib.sha256(n.encode()).hexdigest()[:16]
                at.radio(key=f'member_{token}igird_vt_{check}_chart_view_all').set_value('Overview — utilization')
            run()
            assert not any(s.label == 'Case for diagram' for s in at.selectbox)
            for n in names:
                token = hashlib.sha256(n.encode()).hexdigest()[:16]
                at.radio(key=f'member_{token}igird_vt_{check}_chart_view_all').set_value('All cases — demand / capacity')
            run()
            assert all(len(f.layout.meta['member_case_legend']) == 16 for f in figures)
            # Existing family and individual-source selection must still work.
            for n in names:
                rows = mr.member_inputs(at.session_state.filtered_state)[n]
                family = mm.csi_bound_families(rows)[0]
                element(at.selectbox, 'Load case to review — '+n).set_value(family.option)
            run()
            assert len(figures) == 4
            assert all(f.layout.meta['igird_maxmin_lc'] == 'U1A' for f in figures)
            for radio in [r for r in at.radio if r.label == 'Chart view']:
                radio.set_value(mm.SOURCE_VIEW)
            run()
            for radio in [r for r in at.radio if r.label == 'Chart view' and
                          'Selected case — demand / capacity' in r.options]:
                radio.set_value('Selected case — demand / capacity')
            run()
            assert len(figures) == 2
            for fig in figures:
                demand_component = 'Vuy' if check == 'Shear' else 'Tu'
                traces = [t for t in fig.data if str(t.name).startswith(('Demand '+demand_component, demand_component+' ', 'Vu '))]
                assert len(traces) == 1
                assert len({row[0] for row in traces[0].customdata}) == 1
            for n in names:
                element(at.selectbox,'Load case to review — '+n).set_value(ALL_CASES)
            run()
            assert all(len(f.layout.meta['member_case_legend']) == 16 for f in figures)
            for key,value in original.items():
                assert pickle.dumps(at.session_state[key]) == value, key+' mutated during chart review'
            records.append({'check':check,'members':2,'all_case_traces_per_member':16,
                'all_case_second_selector':False,'family_and_single_source_review':True,
                'overview_toggle':True,'review_solver_calls':0,'input_and_result_cache_unchanged':True})
            print(check+': all 16 source series, family / single-case review and read-only toggles passed.',flush=True)
    button_keys = {button.key for button in at.button if button.key}
    button_keys.update(item.proto.id.split('-', 2)[-1]
                       for widget in ('download_button','file_uploader') for item in at.get(widget))
    checkpoint = {key:value for key,value in at.session_state.filtered_state.items()
                  if key not in button_keys and '__nav_button__' not in key}
    seed.write_bytes(pickle.dumps(checkpoint))
out = ROOT/'qa/evidence/igird_allcase15'
out.mkdir(parents=True,exist_ok=True)
(out/'app_checks.json').write_text(json.dumps({'milestone':'IGIRDER.ALLCASE15',
    'scope':'Byte-exact native force fixture with a hypothetical QA section; no user design acceptance.',
    'manual_calculator_calls':4,'checks':records},indent=2)+'\n')
