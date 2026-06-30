from __future__ import annotations

from pathlib import Path

import pandas as pd

import app


SOURCE = Path("app.py").read_text(encoding="utf-8")


def test_report_qa_workspace_uses_result_summary_readiness_cards() -> None:
    start = SOURCE.index("def render_report_qa_workspace()")
    body = SOURCE[start:]

    assert "Report readiness" in body
    assert "_report_qa_dashboard_cards(st.session_state)" in body
    assert "render_analysis_report_qa()" in body
    assert "render_report_qa_page()" not in body
    assert "Report / QA does not rerun PMM, ULS, SLS, or verification solvers." in SOURCE


def test_report_qa_cards_follow_result_summary_fail_state() -> None:
    state = {
        "_beam_girder_uls_manual_calculation_cache": {},
        "result_summary_beam_girder_sls_stage_summary_df": pd.DataFrame(
            [
                {
                    "Stage": "Lifting stage",
                    "Status": "Preview FAIL",
                    "Case Name": "AUTO-LIFT",
                    "Station x (m)": 2.0,
                    "Fiber": "Top",
                    "Controls": "Tension",
                    "Actual stress (MPa)": 4.246,
                    "Limit profile": "Temporary release",
                    "Utilization": 3.077,
                }
            ]
        ),
    }

    cards = app._report_qa_dashboard_cards(state)
    by_title = {card["title"]: card for card in cards}

    assert by_title["Overall status"]["value"] == "FAIL"
    assert by_title["Report readiness"]["value"] == "Review required"
    assert by_title["Critical check"]["value"] == "SLS Stress"
    assert "3.077" in by_title["Critical check"]["detail"]
    assert by_title["Runtime mode"]["value"] == "Read-only"


def test_report_qa_design_code_uses_edition_label() -> None:
    cards = app._report_qa_dashboard_cards({"project_design_code": "AASHTO LRFD", "project_code_edition": "9th Edition"})
    by_title = {card["title"]: card for card in cards}

    assert by_title["Design code"]["value"] == "AASHTO LRFD 9th Edition"
