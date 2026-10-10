"""Reproduce the user's input model without publishing diagnostic results.

Pass --project to the original Project JSON. Runtime checkpoints stay outside
the release; only scoped evidence is written into the new milestone folder.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import logging
from pathlib import Path
import pickle
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.analysis import igird_rebar_advisor as advisor
from concrete_pmm_pro.ui.igird_rebar_advisor import calculate_trial


def run(project_path, checkpoint):
    logging.getLogger("streamlit").setLevel(logging.ERROR)
    data = Path(project_path).read_bytes()
    state = {}
    apply_project_to_session_state(project_from_json(data.decode()), state)
    route = ap._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
    inputs = mr.member_inputs(state)
    output = ROOT / "qa/evidence/igird_rebaradvisor13/user_project"
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    summaries = []
    for member, rows in inputs.items():
        started = time.monotonic()
        result = mr.calculate_member(state, rows, check_name="Shear + Torsion", route=route)
        results[member] = result
        summary = {"Girder": member, "Source rows": len(rows),
                   "Seconds": round(time.monotonic() - started, 2)}
        for key in ("shear_check_df", "torsion_check_df", "combined_vt_df"):
            frame = result.get(key)
            if isinstance(frame, pd.DataFrame):
                token = member.lower().replace(" ", "_")
                frame.to_csv(output / f"{token}.{key}.csv", index=False)
                summary[key] = {"rows": len(frame), "statuses": frame["Status"].value_counts().to_dict()}
        summaries.append(summary)
        print(json.dumps(summary, default=str), flush=True)
    record = {"project_sha256": hashlib.sha256(data).hexdigest(),
              "scope": "original Project JSON; fresh production Shear + Torsion for both girders; diagnostic results not published",
              "summaries": summaries}
    (output / "baseline_verification.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    Path(checkpoint).write_bytes(pickle.dumps({"state": state, "inputs": inputs, "results": results}))


def verify_trial(checkpoint, trial_checkpoint):
    logging.getLogger("streamlit").setLevel(logging.ERROR)
    data = pickle.loads(Path(checkpoint).read_bytes())
    state, inputs, results = data["state"], data["inputs"], data["results"]
    before = pickle.dumps(state)
    route = ap._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
    proposal = advisor.recommend(state[advisor.TABLE_KEY], results)
    assert proposal.can_verify and proposal.complete_combined
    output = ROOT / "qa/evidence/igird_rebaradvisor13/user_project"
    proposal.zones.to_csv(output / "stirrup_recommendations.csv", index=False, encoding="utf-8-sig")
    proposal.layout.to_csv(output / "trial_stirrup_layout.csv", index=False, encoding="utf-8-sig")
    trial = calculate_trial(state, inputs, proposal.layout, route=route,
        progress=lambda member: print("Verifying trial: " + member, flush=True))
    assert pickle.dumps(state) == before, "Trial changed production inputs/cache"
    summary = advisor.trial_summary(trial)
    summary.to_csv(output / "trial_verification.csv", index=False, encoding="utf-8-sig")
    advisor.action_summary(advisor.remaining_issues(trial)).to_csv(output / "trial_remaining_actions.csv", index=False, encoding="utf-8-sig")
    for member, result in trial.items():
        for key in advisor.FRAME_KINDS:
            frame = result.get(key)
            if isinstance(frame, pd.DataFrame):
                frame.to_csv(output / (member.lower().replace(" ", "_") + ".trial." + key + ".csv"), index=False)
        pd.testing.assert_frame_equal(result["combined_vt_df"][["Case", "Governing x", "Source row", "Mu kN-m", "Nu input kN", "Vu kN", "Tu kN-m"]],
            results[member]["combined_vt_df"][["Case", "Governing x", "Source row", "Mu kN-m", "Nu input kN", "Vu kN", "Tu kN-m"]])
    print(summary.to_string(index=False), flush=True)
    Path(trial_checkpoint).write_bytes(pickle.dumps({**data, "proposal": proposal, "trial": trial}))
    assert summary["Transverse verification"].eq("MEETS NUMERIC CHECKS").all(), "Trial needs refinement"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--trial-checkpoint")
    args = parser.parse_args()
    if args.trial_checkpoint:
        verify_trial(args.checkpoint, args.trial_checkpoint)
    else:
        parser.error("--project is required for a fresh baseline") if not args.project else run(args.project, args.checkpoint)
