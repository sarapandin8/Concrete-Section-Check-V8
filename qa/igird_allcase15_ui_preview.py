"""Browser QA uses an internal calculated checkpoint, never a saved Project result."""
from pathlib import Path
import os
import hashlib
import pickle
import sys
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if not st.session_state.get('_allcase15_qa_seed_loaded'):
    seed = Path(os.environ['CSP_ALLCASE15_QA_SEED']).resolve()
    assert not seed.is_relative_to(ROOT)
    state = pickle.loads(seed.read_bytes())
    check = st.query_params.get('qa_check')
    if check in {'Shear','Torsion'}:
        state['beam_girder_uls_lazy_check'] = check
        for member in ('BOBJ1 / Left Exterior Girder','BOBJ1 / Interior Girder 2'):
            token = hashlib.sha256(member.encode()).hexdigest()[:16]
            state[f'igird_review_case_{check}_{token}'] = 'All load cases'
            state[f'member_{token}igird_vt_{check}_chart_view_all'] = 'All cases — demand / capacity'
    for key,value in state.items():
        # AppTest checkpoints can contain button values. A real browser must
        # let Streamlit create these momentary widgets, not preassign them.
        if (key.startswith(('_sidebar_', 'ui_commercial4_3_sidebar_',
                            'igird_member_calculate_', 'igird_advisor_calculate_'))
                or '__nav_button__' in key):
            continue
        st.session_state[key] = value
    st.session_state['_allcase15_qa_seed_loaded'] = True
import app
app.main()
