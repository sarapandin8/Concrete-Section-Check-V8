"""QA view of the actual supplied model using production Prestress/Analysis pages.

Run: streamlit run qa/igird_dbqa_perf_runtime.py
This fixture loads the original input JSON and keeps QA results in its own session.
"""
import os,sys
from pathlib import Path
ROOT=Path(os.environ.get('CSP_QA_REPO',Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(ROOT))
import streamlit as st
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.ui.prestress_page import render_prestress_page
from concrete_pmm_pro.ui.analysis_page import _render_beam_girder_uls_workspace
from app import _render_global_commercial_tab_styles,install_streamlit_plotly_readability_patch
st.set_page_config(page_title='Concrete Section Pro — I-Girder 20 m',layout='wide')
_render_global_commercial_tab_styles();install_streamlit_plotly_readability_patch(st)
if 'qa_actual_20m_loaded' not in st.session_state:
    file=Path(os.environ.get('CSP_QA_INPUT',ROOT/'qa/fixtures/I_Girder_20m.json'))
    apply_project_to_session_state(project_from_json(file.read_text()),st.session_state)
    st.session_state['qa_actual_20m_loaded']=True
st.title('Concrete Section Pro')
st.caption('Bridge Beam / Girder · Precast I-Girder · AASHTO LRFD 9th Edition · L = 20 m')
view=st.radio('Workspace',['Prestress','Analysis'],horizontal=True)
if view=='Prestress':render_prestress_page()
else:_render_beam_girder_uls_workspace(st.session_state['analysis_mode_settings'])
