from __future__ import annotations

from pathlib import Path

import pandas as pd

import app

SOURCE = Path("app.py").read_text(encoding="utf-8")
ANALYSIS_SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")


def _stage_state() -> dict[str, object]:
    return {
        "project_design_code": "AASHTO LRFD",
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "member_type": "beam_girder",
        "result_summary_beam_girder_sls_stage_summary_df": pd.DataFrame(
            [
                {
                    "Stage": "Transfer stage",
                    "Case Name": "SLS-TR",
                    "Status": "Preview PASS",
                    "Controls": "Tension",
                    "Station x (m)": 5.0,
                    "Fiber": "Bottom",
                    "Actual stress (MPa)": 1.5,
                    "Limit stress (MPa)": 3.0,
                    "Utilization": 0.5,
                    "Limit profile": "AASHTO transfer limit",
                },
                {
                    "Stage": "Service stage",
                    "Case Name": "SLS-SV",
                    "Status": "Preview PASS",
                    "Controls": "Compression",
                    "Station x (m)": 9.0,
                    "Fiber": "Top",
                    "Actual stress (MPa)": -8.0,
                    "Limit stress (MPa)": -16.0,
                    "Utilization": 0.5,
                    "Limit profile": "AASHTO service limit",
                },
            ]
        ),
    }


def test_sls_stage_stress_rows_make_result_summary_partial_not_not_calculated() -> None:
    state = _stage_state()

    assert app._results_sls_available(state) is True
    assert app._results_sls_complete_for_report(state) is False

    cards = app._results_sls_summary_cards(state)
    values = [str(card["value"]) for card in cards]

    assert any("AASHTO LRFD" in value for value in values)
    assert "Partial / stress stored" in values
    assert "Not calculated" not in values


def test_sls_stage_stress_rows_appear_in_governing_rows() -> None:
    rows = app._results_governing_rows(_stage_state())

    sls_rows = [row for row in rows if row["Module"] == "SLS Stress"]
    assert len(sls_rows) == 1
    assert sls_rows[0]["Check"] == "Beam/Girder stage stress"
    assert sls_rows[0]["Status"] == "Preview PASS"
    assert sls_rows[0]["Governing Case"] in {"SLS-TR", "SLS-SV"}
    assert sls_rows[0]["Source"] == "Analysis → SLS / Stress & Cracking → staged stress diagram"


def test_overview_cards_show_design_code_and_sls_partial() -> None:
    cards = app._results_availability_cards(_stage_state())

    by_title = {card["title"]: card for card in cards}
    assert "Design code" in by_title
    assert "AASHTO LRFD" in str(by_title["Design code"]["value"])
    assert "SLS partial" in str(by_title["ULS/SLS completeness"]["value"])


def test_analysis_page_publishes_sls_stage_summary_for_result_summary() -> None:
    assert "result_summary_beam_girder_sls_stage_summary_df" in ANALYSIS_SOURCE
    assert "RESULT.SUMMARY2" in ANALYSIS_SOURCE
    assert "workflow_project_code_label_from_session(st.session_state)" in ANALYSIS_SOURCE
    assert "workflow_project_code_label_from_session," in ANALYSIS_SOURCE
