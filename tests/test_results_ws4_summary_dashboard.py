from __future__ import annotations

from pathlib import Path

import app


SOURCE = Path("app.py").read_text(encoding="utf-8")


def test_results_workspace_uses_summary_uls_sls_traceability_subpages() -> None:
    assert app.WORKSPACE_NAVIGATION["Result Summary"] == [
        "Overview",
        "ULS Summary",
        "SLS Summary",
        "Traceability",
    ]
    assert 'key="_results_active_subpage"' in SOURCE
    assert 'active_subpage == "Overview"' in SOURCE
    assert 'active_subpage == "ULS Summary"' in SOURCE
    assert 'active_subpage == "SLS Summary"' in SOURCE
    assert 'active_subpage == "Traceability"' in SOURCE


def test_results_main_dashboard_is_not_a_diagram_gallery() -> None:
    start = SOURCE.index("def render_results_workspace")
    end = SOURCE.index("\n\ndef render_report_qa_workspace", start)
    body = SOURCE[start:end]

    assert "Diagram Review" not in body
    assert "_render_results_diagram_review" not in body
    assert "Professional decision dashboard" in body
    assert "Required Actions" in body


def test_results_summary_cards_include_next_engineering_action() -> None:
    assert "def _results_next_engineering_action" in SOURCE
    assert "Next engineering action" in SOURCE
    assert "Run SLS Stress & Cracking" in SOURCE
    assert "Run SLS Stress & Cracking before Report / QA." in SOURCE


def test_results_has_dedicated_sls_dashboard_without_solver_rerun() -> None:
    assert "def _render_results_sls_dashboard" in SOURCE
    assert "SLS Summary Dashboard" in SOURCE
    assert "No stored SLS result rows are available yet" in SOURCE
    start = SOURCE.index("def _render_results_sls_dashboard")
    end = SOURCE.index("\n\n_RESULTS_STATIC_FIG_WIDTH", start)
    body = SOURCE[start:end]
    assert "Run Elastic SLS Stress Check" not in body
    assert "st.button" not in body
