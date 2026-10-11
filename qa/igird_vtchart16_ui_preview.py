"""Actual app preview using an internal, explicitly calculated QA checkpoint."""
import os
from pathlib import Path
import pickle
import sys
import streamlit as st
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if not st.session_state.get('_vtchart16_seed_loaded'):
    seed = Path(os.environ['CSP_VTCHART16_QA_SEED']).resolve()
    assert not seed.is_relative_to(ROOT)
    for key,value in pickle.loads(seed.read_bytes()).items():
        if key.startswith(('_sidebar_','ui_commercial4_3_sidebar_','igird_member_calculate_','igird_advisor_calculate_')) or '__nav_button__' in key:
            continue
        st.session_state[key] = value
    st.session_state['_vtchart16_seed_loaded'] = True
import app
app.main()
