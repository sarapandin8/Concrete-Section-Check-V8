from __future__ import annotations

from pathlib import Path


APP_SOURCE = Path("app.py").read_text(encoding="utf-8")


def test_results_traceability_does_not_call_missing_analysis_mode_factory() -> None:
    assert "AnalysisModeSettings.from_session_state" not in APP_SOURCE
    assert "analysis_mode_label(_analysis_mode_from_session_for_chrome())" in APP_SOURCE


def test_results_workspace_remains_read_only_dashboard() -> None:
    start = APP_SOURCE.index("def render_results_workspace()")
    end = APP_SOURCE.index("\n\ndef render_report_qa_workspace()", start)
    body = APP_SOURCE[start:end]

    assert "render_page_header(" in body
    assert "Result Summary Dashboard" in body
    assert "_render_results_traceability(st.session_state)" in body
    assert "Run / Recalculate" not in body
    assert "Run Elastic SLS Stress Check" not in body
