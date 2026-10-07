"""Local visual QA for actual app.py, using controlled hypothetical inputs.

Run from the project root: streamlit run qa/igird_compact6_browser_app.py
Never use this fixture launcher as the deployment entrypoint.
"""
from pathlib import Path
import runpy
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'tests'))
import streamlit as st
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json
from concrete_pmm_pro.io.girder_load_bank import activate_member
from test_igird_casecontrol5 import review_model

if '_compact6_visual_initialized' not in st.session_state:
    state = {}
    apply_project_to_session_state(project_from_json(
        (REPO / 'qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()), state)
    state.update(review_model())
    activate_member(state, 'Exterior Girder')
    st.session_state.update(state)
    st.session_state['_nav_active_workspace'] = 'Analysis'
    st.session_state['beam_girder_uls_lazy_check'] = 'Torsion'
    st.session_state['_compact6_visual_initialized'] = True

runpy.run_path(str(REPO / 'app.py'), run_name='__main__')
