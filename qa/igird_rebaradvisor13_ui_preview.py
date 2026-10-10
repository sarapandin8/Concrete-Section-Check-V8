"""Local visual QA seed for the actual app; no calculation on page opening.

Run with streamlit, CSP_REBARADVISOR_TRIAL pointing to the external runtime
checkpoint. Production users run app.py directly and load their Project JSON.
"""
from copy import deepcopy
import os
from pathlib import Path
import pickle
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import streamlit as st
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui import igird_rebar_advisor as ui
from concrete_pmm_pro.analysis import igird_rebar_advisor as advisor
from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY, save_active

if not st.session_state.get("qa_rebaradvisor_seeded"):
    data = pickle.loads(Path(os.environ["CSP_REBARADVISOR_TRIAL"]).read_bytes())
    state = deepcopy(data["state"])
    save_active(state)
    route = ap._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
    rows = mr.member_inputs(state)
    state[mr.CACHE_KEY] = {member: {"Shear + Torsion": {
        "input_hash": mr.result_hash(state, rows[member], check_name="Shear + Torsion", route=route),
        "result": result}} for member, result in data["results"].items()}
    active = state[ACTIVE_KEY]
    ap._beam_uls_store_manual_result(state, "Shear + Torsion",
        input_hash=state[mr.CACHE_KEY][active]["Shear + Torsion"]["input_hash"], result=data["results"][active])
    state["_nav_active_workspace"] = "Analysis"
    state["beam_girder_uls_lazy_check"] = "Shear + Torsion"
    state["qa_rebaradvisor_seeded"] = True
    for key, value in state.items():
        st.session_state[key] = value
runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
