"""Actual app.py: explicit trial, all-case sizing, stale and read-only guards.

Use the runtime checkpoint from igird_rebaradvisor13_user_verify.py; it is not
part of the release. The app test calculates the real trial once, then guards
every subsequent review, Summary and Report route against solver calls.
"""
from contextlib import ExitStack
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import pickle
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui import igird_rebar_advisor as ui
from concrete_pmm_pro.analysis import igird_rebar_advisor as advisor
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY, ACTIVE_KEY, save_active

logging.getLogger("streamlit").setLevel(logging.ERROR)
data = pickle.loads(Path(os.environ["CSP_REBARADVISOR_BASELINE"]).read_bytes())
state = deepcopy(data["state"])
save_active(state)
route = ap._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
state[mr.CACHE_KEY] = {member: {"Shear + Torsion": {
    "input_hash": mr.result_hash(state, data["inputs"][member], check_name="Shear + Torsion", route=route),
    "result": result}} for member, result in data["results"].items()}
active = state[ACTIVE_KEY]
ap._beam_uls_store_manual_result(state, "Shear + Torsion", input_hash=state[mr.CACHE_KEY][active]["Shear + Torsion"]["input_hash"], result=data["results"][active])
state["_nav_active_workspace"] = "Analysis"
state["beam_girder_uls_lazy_check"] = "Shear + Torsion"
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
for key, value in state.items():
    at.session_state[key] = value


def run():
    at.run(timeout=120)
    assert not at.exception, [e.message for e in at.exception]


def snapshot():
    return {key: pickle.dumps(at.session_state[key]) for key in
        (advisor.TABLE_KEY, BANK_KEY, ACTIVE_KEY, "beam_uls_loads_table", mr.CACHE_KEY, ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY)}


def unchanged(before):
    for key, value in before.items():
        assert pickle.dumps(at.session_state[key]) == value, key


def forbid(stack):
    for name in ("_beam_uls_calculate_selected_check", "_beam_uls_flexure_preview_dataframe",
                 "_beam_uls_igird_torsion_diagram_capacity_dataframe", "_beam_uls_igird_shear_diagram_capacity_dataframe"):
        stack.enter_context(patch.object(ap, name, side_effect=AssertionError("Hidden solver: " + name)))
    stack.enter_context(patch.object(mr, "calculate_member", side_effect=AssertionError("Hidden member solver")))
    stack.enter_context(patch.object(ui, "calculate_trial", side_effect=AssertionError("Hidden trial solver")))


with ExitStack() as stack:
    forbid(stack)
    run()
    button = at.button(key="igird_advisor_calculate_collection")
    assert not button.disabled
    table = next(df.value for df in at.dataframe if "Proposed trial" in df.value.columns)
    assert table["Proposed trial"].tolist() == ["DB12 @50 mm", "DB12 @80 mm", "DB12 @80 mm", "DB12 @50 mm", "DB16 @70 mm"]
    before = snapshot()
    run()
    unchanged(before)

calls = []
calculator = mr.calculate_member


def counted(state, rows, **kwargs):
    calls.append({"rows": len(rows), "check": kwargs["check_name"]})
    return calculator(state, rows, **kwargs)


with patch.object(mr, "calculate_member", counted):
    at.button(key="igird_advisor_calculate_collection").click()
    run()
assert len(calls) == 2 and all(c["rows"] == 320 for c in calls)
unchanged(before)
summary = at.session_state[ui.RUNTIME_KEY]["summary"]
assert len(summary) == 10
assert summary["Transverse verification"].eq("MEETS NUMERIC CHECKS").all()
assert summary["Overall V+T"].isin(["FAIL", "REVIEW"]).all()
original_trial = pickle.dumps(at.session_state[ui.RUNTIME_KEY])
print("Explicit real-project trial: 2 girders × 320 vectors; production inputs/cache unchanged", flush=True)

with ExitStack() as stack:
    forbid(stack)
    # Case selection never narrows advisor requirements.
    for selector in list(at.selectbox):
        if selector.label.startswith("Load case to review — "):
            selector.set_value(selector.options[-1])
    run()
    unchanged(before)
    table2 = next(df.value for df in at.dataframe if "Proposed trial" in df.value.columns)
    pd.testing.assert_frame_equal(table, table2)
    at.toggle(key="igird_compact_details_Shear + Torsion").set_value(True)
    run()
    assert len([b for b in at.button if b.key == "igird_advisor_calculate_collection"]) == 1
    assert not any(b.key == "igird_advisor_calculate_design" for b in at.button)
    unchanged(before)
    at.toggle(key="igird_compact_details_Shear + Torsion").set_value(False)
    run()
    at.number_input(key="igird_advisor_min_collection").set_value(60.)
    run()
    assert any("STALE —" in c.value for c in at.caption)
    assert not any("Trial verification —" in m.value for m in at.markdown)
    at.number_input(key="igird_advisor_min_collection").set_value(50.)
    run()
    assert pickle.dumps(at.session_state[ui.RUNTIME_KEY]) == original_trial
    for workspace in ("Result Summary", "Report / QA"):
        at.session_state["_nav_active_workspace"] = workspace
        run()
        assert not any(b.key and b.key.startswith("igird_advisor_calculate") for b in at.button)
        unchanged(before)
        assert pickle.dumps(at.session_state[ui.RUNTIME_KEY]) == original_trial
        print("Read-only " + workspace + ": no production/trial solver; no trial publication", flush=True)
    at.session_state["_nav_active_workspace"] = "Analysis"
    changed = deepcopy(at.session_state[advisor.TABLE_KEY])
    changed.loc[0, "Spacing_mm"] = 60.
    at.session_state[advisor.TABLE_KEY] = changed
    run()
    assert not any("Trial verification —" in m.value for m in at.markdown)
    assert any("Results unavailable" in w.value for w in at.warning)

OUT = ROOT / "qa/evidence/igird_rebaradvisor13/app"
OUT.mkdir(parents=True, exist_ok=True)
record = {"actual_app_py": True, "original_project": True, "trial_solver_calls": calls,
    "all_case_shared_recommendations": True, "display_case_does_not_narrow_plan": True,
    "production_inputs_and_caches_unchanged": True, "detailed_view_single_advisor": True,
    "stale_options_and_inputs_hidden": True, "summary_report_hidden_solver_calls": 0,
    "trial_results_not_published": True, "transverse_numeric_meets_zones": 10,
    "overall_status_retained": summary["Overall V+T"].value_counts().to_dict()}
(OUT / "app_verification.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record), flush=True)
