from __future__ import annotations

from pathlib import Path

import pandas as pd

import app

SOURCE = Path("app.py").read_text(encoding="utf-8")


def _beam_cache() -> dict[str, dict[str, object]]:
    return {
        "Flexure": {"flexure_preview_df": pd.DataFrame([{"Status": "PASS", "Case": "Strength I", "Governing x": "5.000 m", "Demand": "3,805.24 kN-m", "Capacity": "φMn = 15,427.74 kN-m", "Utilization value": 0.247}])},
        "Shear": {"shear_check_df": pd.DataFrame([{"Status": "PASS", "Case": "Strength I", "Governing x": "9.000 m", "Demand": "1,355.74 kN", "Capacity": "φVn = 3,282.00 kN", "Strength D/C value": 0.413}])},
        "Torsion": {"torsion_check_df": pd.DataFrame([{"Status": "BELOW THRESHOLD", "Case": "Strength I", "Governing x": "4.000 m", "Tu kN-m": "100.00 kN-m", "Capacity": "φTn = 1,686.90 kN-m", "D/C value": 0.059}])},
        "Shear + Torsion": {"combined_vt_df": pd.DataFrame([{"Status": "PASS", "Case": "Strength I", "Governing x": "4.000 m", "Vu kN": 57.137, "Tu kN-m": "100.00 kN-m", "Overall D/C value": 0.426}])},
    }


def _failing_sls_state() -> dict[str, object]:
    return {
        "project_design_code": "AASHTO LRFD",
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "_beam_girder_uls_manual_calculation_cache": _beam_cache(),
        "result_summary_beam_girder_sls_stage_summary_df": pd.DataFrame(
            [
                {
                    "Stage": "Lifting",
                    "Case Name": "AUTO-LIFT",
                    "Status": "Preview FAIL",
                    "Controls": "Tension",
                    "Station x (m)": 2.0,
                    "Fiber": "Top",
                    "Actual stress (MPa)": 4.246,
                    "Limit stress (MPa)": 1.38,
                    "Utilization": 3.077,
                    "Limit profile": "Temporary release — no bonded auxiliary tension reinforcement",
                }
            ]
        ),
        "railway_u_girder_sls_decision_summary_df": pd.DataFrame(
            [
                {
                    "Check stage": "Lifting",
                    "Decision": "REVIEW",
                    "Governing source": "AUTO-LIFT",
                    "Governing x / case": "2.000 m / Top",
                    "Compression (MPa)": 0.0,
                    "Tension (MPa)": 4.246,
                    "Section basis": "Temporary release — no bonded auxiliary tension reinforcement",
                    "Max utilization": 3.077,
                }
            ]
        ),
    }


def test_sls_preview_fail_wins_over_generic_railway_review_card() -> None:
    cards = app._results_sls_summary_cards(_failing_sls_state())
    by_title = {str(card["title"]): card for card in cards}

    assert by_title["SLS status"]["value"] == "Preview FAIL"
    assert by_title["SLS status"]["status"] == "danger"
    assert by_title["Governing stage"]["value"] == "Lifting"
    assert by_title["Max utilization"]["value"] == "3.077"
    assert "x = 2.000 m" in str(by_title["Max utilization"]["detail"])
    assert "Top fiber" in str(by_title["Max utilization"]["detail"])


def test_required_actions_include_specific_sls_failure_guidance() -> None:
    state = _failing_sls_state()
    rows = app._results_governing_rows(state)
    actions = app._results_required_action_rows(state, rows)
    sls_action = next(action for action in actions if action["Module"] == "SLS Stress")

    assert sls_action["Priority"] == "High"
    assert "Preview FAIL" in sls_action["Issue"]
    assert "x = 2.000 m" in sls_action["Required Action"]
    assert "utilization = 3.077" in sls_action["Required Action"]
    assert "temporary reinforcement" in sls_action["Required Action"].lower()


def test_complete_but_failing_summary_completeness_card_is_not_green_ready() -> None:
    cards = app._results_availability_cards(_failing_sls_state())
    by_title = {str(card["title"]): card for card in cards}

    assert by_title["Overall status"]["value"] == "FAIL"
    assert by_title["ULS/SLS completeness"]["value"] == "ULS 4 · SLS complete"
    assert by_title["ULS/SLS completeness"]["status"] == "info"
    assert "failing check exists" in by_title["ULS/SLS completeness"]["detail"]


def test_traceability_runtime_state_is_read_only_not_misleading_not_run() -> None:
    assert "Result Summary runtime" in SOURCE
    assert "Read-only summary; stored analysis results available" in SOURCE
    assert '{"Item": "Runtime status", "Value": str(state.get("analysis_runtime_last_status") or "-")}' not in SOURCE


def test_result_summary_torsion_unit_suffix_is_not_duplicated() -> None:
    assert app._results_beam_uls_demand("Torsion", {"Tu kN-m": "100.00 kN-m"}) == "Tu = 100.00 kN-m"
    assert app._results_beam_uls_demand("Shear + Torsion", {"Vu kN": "57.137 kN", "Tu kN-m": "100.00 kN-m"}) == "Vu = 57.137 kN; Tu = 100.00 kN-m"
