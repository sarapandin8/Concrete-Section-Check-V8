from __future__ import annotations

from pathlib import Path

import pandas as pd

import app

SOURCE = Path("app.py").read_text(encoding="utf-8")


def test_result_summary_navigation_uses_professional_dashboard_names() -> None:
    assert "Result Summary" in app.WORKSPACE_NAVIGATION
    assert app.WORKSPACE_NAVIGATION["Result Summary"] == ["Overview", "ULS Summary", "SLS Summary", "Traceability"]
    assert '"Results": ["Summary Dashboard"' not in SOURCE
    assert "Result Summary Dashboard" in SOURCE
    assert "Professional decision dashboard for stored analysis results" in SOURCE


def test_empty_result_summary_actions_prioritize_uls_and_sls() -> None:
    rows: list[dict[str, object]] = []
    actions = app._results_required_action_rows({}, rows)

    assert actions[0]["Module"] == "ULS"
    assert actions[0]["Priority"] == "High"
    assert actions[0]["Issue"] == "ULS not calculated"
    assert any(action["Module"] == "SLS" and action["Issue"] == "SLS not calculated" for action in actions)


def test_report_handoff_is_not_ready_without_stored_results() -> None:
    state: dict[str, object] = {}
    handoff = app._results_report_handoff_state(state, [])

    assert handoff["value"] == "Not ready"
    assert handoff["status"] == "warning"
    assert "No stored Analysis result set" in handoff["detail"]


def test_column_pier_vt_stored_result_appears_in_governing_rows() -> None:
    state: dict[str, object] = {
        "column_pier_combined_vt_result_df": pd.DataFrame(
            [
                {
                    "Status": "PASS",
                    "Case": "ULS-01",
                    "Direction": "Vux",
                    "Vu kN": 70.0,
                    "Tu kN-m": 60.0,
                    "Overall D/C value": 0.889,
                },
                {
                    "Status": "FAIL",
                    "Case": "ULS-02",
                    "Direction": "Vux",
                    "Vu kN": 80.0,
                    "Tu kN-m": 75.0,
                    "Overall D/C value": 1.111,
                },
            ]
        ),
        "column_pier_combined_vt_controlling_cause": "source torsion strength + source/stress gate",
        "column_pier_combined_vt_governing_label": "Tied governing rows: 2 rows at D/C 1.111; first = ULS-02 / Vux",
        "column_pier_combined_vt_route_label": "AASHTO LRFD V+T",
    }

    rows = app._results_governing_rows(state)

    assert len(rows) == 1
    assert rows[0]["Module"] == "ULS Shear + Torsion"
    assert rows[0]["Check"] == "Column/Pier V+T"
    assert rows[0]["Status"] == "FAIL"
    assert rows[0]["D/C / Util."] == "1.111"
    assert "ULS-02 / Vux" in rows[0]["Governing Case"]
    assert "torsion" in rows[0]["Required Action"].lower()


def test_result_summary_read_only_does_not_rerun_solver() -> None:
    start = SOURCE.index("def render_results_workspace()")
    end = SOURCE.index("\n\ndef render_report_qa_workspace()", start)
    body = SOURCE[start:end]

    assert "does not rerun PMM, ULS, or SLS" in body
    assert "st.button" not in body
    assert "_column_pier_combined_vt_check_dataframe" not in body
