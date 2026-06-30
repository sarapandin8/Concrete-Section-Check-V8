from __future__ import annotations

from pathlib import Path


SOURCE = Path("app.py").read_text(encoding="utf-8")


def test_results_executive_state_reports_partial_beam_uls_results() -> None:
    assert 'title": "Overall Status: INCOMPLETE"' in SOURCE
    assert 'Beam/Girder ULS checks have stored results' in SOURCE
    assert '_render_results_executive_summary(governing_rows, st.session_state)' in SOURCE


def test_results_governing_section_states_only_calculated_checks_are_listed() -> None:
    assert "Decision-level status, critical check, result completeness" in SOURCE
    assert "Required Actions" in SOURCE


def test_results_diagram_review_uses_cached_beam_uls_dataframes() -> None:
    assert 'def _results_beam_uls_cached_figure' in SOURCE
    assert 'def _results_available_diagram_figures' in SOURCE
    assert 'Beam/Girder ULS · {check_name}' in SOURCE
    assert '_render_results_static_plotly_figure(' in SOURCE
    assert 'does not rerun solvers' in SOURCE


def test_results_diagram_review_no_longer_requires_stored_plotly_figure_object() -> None:
    start = SOURCE.index("def _render_results_diagram_review")
    end = SOURCE.index("\n\ndef _render_results_traceability", start)
    body = SOURCE[start:end]

    assert "_results_available_diagram_figures(state)" in body
    assert "st.plotly_chart" not in body
    assert "cached result data" in body


def test_results_availability_counts_cached_result_diagrams() -> None:
    assert "Critical check" in SOURCE
    assert "ULS/SLS completeness" in SOURCE
    assert "Run SLS Stress & Cracking" in SOURCE
