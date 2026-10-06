"""Exercise the actual app.py Analysis routes with a controlled QA model."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, 'tests')
import streamlit as st
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json
from concrete_pmm_pro.io.girder_load_bank import activate_member, ACTIVE_KEY
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from test_igird_casecontrol5 import review_model

state = {}
apply_project_to_session_state(project_from_json(Path('qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()), state)
state.update(review_model())
activate_member(state, 'Exterior Girder')
at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=60)
for key, value in state.items():
    at.session_state[key] = deepcopy(value)
at.session_state['_nav_active_workspace'] = 'Analysis'
at.session_state['qa_app_calculations'] = 0
calculate = mr.calculate_member


def counted(*args, **kwargs):
    st.session_state['qa_app_calculations'] += 1
    return calculate(*args, **kwargs)


def ok():
    assert not at.exception, [item.message for item in at.exception]


def element(items, label):
    return next(item for item in items if item.label == label)


records = []
with patch.object(mr, 'calculate_member', counted):
    at.run(); ok()
    element(at.radio, 'Flexure stage').set_value('Final — Composite').run(); ok()
    for check in ('Flexure', 'Shear', 'Torsion', 'Shear + Torsion'):
        element(at.radio, 'ULS check to calculate').set_value(check).run(); ok()
        next(button for button in at.button if button.label.startswith('Calculate ' + check + ' — all')).click().run(); ok()
        before = at.session_state['qa_app_calculations']
        assert before == 2 * (len(records) + 1)
        summary = next(frame.value for frame in at.dataframe if 'Result state' in frame.value)
        assert summary['Result state'].eq('CURRENT').all()
        with ExitStack() as stack:
            for function in ('_beam_uls_calculate_selected_check', '_beam_uls_flexure_preview_dataframe',
                             '_beam_uls_igird_torsion_diagram_capacity_dataframe'):
                stack.enter_context(patch.object(ap, function, side_effect=AssertionError('Review must not run a solver')))
            element(at.radio, 'Girder results view').set_value('Choose girder / load case — stored results').run(); ok()
            for member in ('Exterior Girder', 'Interior Girder 2'):
                element(at.selectbox, 'Girder to review').set_value(member).run(); ok()
                element(at.selectbox, 'Load case to review — ' + member).set_value(member + ' / ULS2').run(); ok()
                expander = element(at.expander, 'Stored check rows / source audit — ' + member)
                assert expander.dataframe[0].value['Case'].eq(member + ' / ULS2').all()
                assert at.session_state[ACTIVE_KEY] == 'Exterior Girder'
            assert at.session_state['qa_app_calculations'] == before
            element(at.radio, 'Girder results view').set_value('All imported girders — separate charts').run(); ok()
        records.append({'check': check, 'current_girders': 2, 'named_case_review_girders': 2,
                        'review_solver_calls': 0, 'design_member_preserved': True})

result = {'release': 'IGIRDER.CASECONTROL5', 'status': 'PASS', 'entrypoint': 'app.py',
          'scope': 'Hypothetical QA input; full Analysis page routing, not live deployment',
          'streamlit_exceptions': 0, 'checks': records}
out = Path('qa/evidence/igird_casecontrol5/app_integration.json')
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False), flush=True)
