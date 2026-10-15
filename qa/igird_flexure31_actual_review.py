"""Full app on the supplied INPUT30 model; real solvers, no resistance waiver."""
from copy import deepcopy
import argparse
import hashlib
import json
import logging
from pathlib import Path
import pickle
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json, project_from_session_state, project_to_json
from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY, BANK_KEY, save_active
from concrete_pmm_pro.ui import analysis_page as ap, igird_flexure_workspace as fw
from concrete_pmm_pro.ui import igird_member_results as mr, igird_dowel_joint as joint_ui


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--baseline-results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(); args.output_dir.mkdir(exist_ok=True, parents=True)
    logging.disable(logging.WARNING)
    original = json.loads(args.project.read_text())
    state = {}; apply_project_to_session_state(project_from_json(args.project.read_text()), state)
    save_active(state)
    state["_nav_active_workspace"] = "Analysis"
    state["_nav_analysis_subpage"] = "ULS Strength"
    state["beam_girder_composite_flexure_stage"] = "Final — Composite"
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120)
    for k, v in state.items(): app.session_state[k] = deepcopy(v)
    figures = []
    original_render = ap._render_beam_uls_browser_plotly_figure

    def capture(fig, **kwargs):
        original_render(fig, **kwargs)
        figures.append(deepcopy(fig))

    def run():
        figures.clear(); app.run(timeout=120)
        assert not app.exception, [e.message for e in app.exception]

    with patch.object(ap, "_render_beam_uls_browser_plotly_figure", side_effect=capture), \
            patch.object(mr, "calculate_member", wraps=mr.calculate_member) as section, \
            patch.object(ap, "_igird_interface_shear_dataframe", wraps=ap._igird_interface_shear_dataframe) as interface, \
            patch.object(ap, "_igird_dowel_joint_review", wraps=ap._igird_dowel_joint_review) as joint:
        run()
        assert section.call_count == interface.call_count == joint.call_count == 0
        calc = [b for b in app.button if b.label.startswith("Calculate")]
        assert [b.label for b in calc] == ["Calculate Flexure"]
        app.button(key="igird_flexure31_calculate").click(); run()
        assert section.call_count == interface.call_count == 2 and joint.call_count == 1
        assert len(figures) == len(app.get("plotly_chart")) == 1
        results = app.session_state[fw.CACHE_KEY]
        baseline = pickle.loads(args.baseline_results.read_bytes())
        summaries = []
        for name, entry in results.items():
            frame = entry["bundle"]["section"]["flexure_preview_df"]
            pd.testing.assert_frame_equal(frame, baseline["results"][name]["flexure_preview_df"])
            # The per-source results, including failures and NaNs, match INPUT30.
            row = fw.summary_row(name, entry["bundle"], length=20, separate_ends=True)
            assert row["Strength exceeded"] == row["Resistance unavailable"] == 0
            assert row["Section"] == row["Overall"] == "REVIEW"
            summaries.append(row)
            fw.endpoint_reference_table(frame, length=20).to_csv(args.output_dir / ("ends_interior.csv" if "Interior" in name else "ends_exterior.csv"), index=False)
        review_snapshots = {key: pickle.dumps(app.session_state[key]) for key in
            (fw.CACHE_KEY, mr.CACHE_KEY, ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY,
             ACTIVE_KEY, BANK_KEY, "beam_uls_loads_table", joint_ui.CACHE_KEY)}
        for view in (fw.UTILIZATION, fw.SOURCE, fw.INTERFACE, fw.DEMAND):
            app.radio(key="igird_flexure31_view").set_value(view); run()
            assert len(figures) == 1
            if view == fw.SOURCE:
                assert figures[0].layout.meta["flexure31_reference"] == "ORIGINAL CSI"
                endpoints = [float(y) for t in figures[0].data if t.name.startswith("M3")
                    for x, y in zip(t.x, t.y) if float(x) in (0., 20.)]
                assert endpoints and all(y == 0. for y in endpoints), endpoints
            figures[0].write_json(args.output_dir / ("exterior_" + view.lower().replace(" / ", "_").replace(" ", "_") + ".plotly.json"))
        app.radio(key="igird_flexure31_bound").set_value("Both"); run()
        assert len(figures) == 2
        app.radio(key="igird_flexure31_bound").set_value("Max"); run()
        app.selectbox(key="igird_flexure31_focus").set_value("Right end"); run()
        assert len(figures) == 1 and figures[0].layout.xaxis.range[1] > 20
        figures[0].write_json(args.output_dir / "exterior_right_end.plotly.json")
        other = next(n for n in results if n != app.selectbox(key="igird_flexure31_member").value)
        app.selectbox(key="igird_flexure31_member").set_value(other); run()
        assert len(figures) == 1 and other in figures[0].layout.title.text
        app.selectbox(key="igird_flexure31_focus").set_value("Full member"); run()
        figures[0].write_json(args.output_dir / "interior_full_member.plotly.json")
        app.toggle(key="igird_flexure31_edit_inputs").set_value(True); run()
        assert [b.label for b in app.button if b.label.startswith("Calculate")] == ["Calculate Flexure"]
        assert section.call_count == interface.call_count == 2 and joint.call_count == 1
        for key, snapshot in review_snapshots.items():
            assert pickle.dumps(app.session_state[key]) == snapshot, key
        payload = project_to_json(project_from_session_state(app.session_state.filtered_state))
        saved = json.loads(payload)
        assert digest(saved["loads"]) == digest(original["loads"])
        for key in (BANK_KEY, "beam_uls_loads_table"):
            assert digest(saved["metadata"]["workflow_load_tables"][key]) == digest(original["metadata"]["workflow_load_tables"][key])
        assert fw.CACHE_KEY not in payload and joint_ui.CACHE_KEY not in payload
        assert "NO EQUILIBRIUM" not in payload
        restored = {}; apply_project_to_session_state(project_from_json(payload), restored)
        assert restored["project_metadata"][fw.POLICY_KEY]["end_treatment"] == "separate_review"
        for workspace in ("Result Summary", "Report / QA"):
            app.session_state["_nav_active_workspace"] = workspace; run()
            assert any("physical cut ends" in info.value for info in app.info)
            assert section.call_count == interface.call_count == 2 and joint.call_count == 1
        for key, snapshot in review_snapshots.items():
            assert pickle.dumps(app.session_state[key]) == snapshot, key
    record = {"version": fw.VERSION, "source_project_sha256": hashlib.sha256(args.project.read_bytes()).hexdigest(),
        "real_section_calculations": 2, "real_interface_calculations": 2, "optional_joint_reviews": 1,
        "calculate_buttons": 1, "default_charts": 1, "explicit_both_bound_charts": 2,
        "input30_original_result_rows_identical": True, "review_solver_calls": 0,
        "raw_Loads_and_member_bank_preserved": True, "summary_report_read_only": True,
        "runtime_results_not_saved": True, "assessment_policy_roundtrip": True,
        "original_CSI_M3_exterior_endpoints_zero": True, "member_span_summaries": summaries,
        "streamlit_exceptions": 0, "browser_visual_QA": False,
        "browser_visual_QA_reason": "This script runs AppTest. Browser checks are recorded separately in FLEXURE31_browser_review.json."}
    (args.output_dir / "FLEXURE31_actual_review.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__": main()
