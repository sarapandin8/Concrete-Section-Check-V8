"""Actual app preview: source project seed contains input data only."""
import os,pickle,sys
from pathlib import Path
import streamlit as st
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
if not st.session_state.get('_autoload17_seed_loaded'):
    seed=Path(os.environ['CSP_AUTOLOAD17_SEED']).resolve()
    assert not seed.is_relative_to(ROOT)
    for k,v in pickle.loads(seed.read_bytes()).items():st.session_state[k]=v
    st.session_state['_autoload17_seed_loaded']=True
import app
app.main()
