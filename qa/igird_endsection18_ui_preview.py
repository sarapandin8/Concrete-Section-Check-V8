"""Actual app.py visual QA from an external checkpoint."""
import os,pickle,sys
from pathlib import Path
import streamlit as st
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
if not st.session_state.get('_endsection18_qa_loaded'):
    path=Path(os.environ['CSP_ENDSECTION18_SEED']).resolve();assert not path.is_relative_to(ROOT)
    for key,value in pickle.loads(path.read_bytes()).items():
        if key.startswith(('_sidebar_','ui_commercial4_3_sidebar_','igird_member_calculate_','beam_uls_calculate_')) or '__nav_button__' in key:continue
        st.session_state[key]=value
    st.session_state['_endsection18_qa_loaded']=True
import app
app.main()
