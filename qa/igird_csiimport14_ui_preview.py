"""Visual QA seed; production users run app.py and load their own project."""
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import streamlit as st
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json

if not st.session_state.get('qa_csiimport14_seeded'):
    state = {}
    apply_project_to_session_state(project_from_json(
        (ROOT / 'qa/fixtures/I_Girder_20m_IGIRDER_FLEXSIGN1_CSiBridge_deck250.json').read_text()), state)
    state['_nav_active_workspace'] = 'Loads'
    state['qa_csiimport14_seeded'] = True
    for key, value in state.items():
        st.session_state[key] = value
runpy.run_path(str(ROOT / 'app.py'), run_name='__main__')
