from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REBAR_SOURCE = (ROOT / "concrete_pmm_pro" / "ui" / "rebar_page.py").read_text(encoding="utf-8")


def test_compact1_rebar_page_uses_panel_titles_and_compact_preview_cards() -> None:
    assert "cpmm-rebar-panel-title" in REBAR_SOURCE
    assert "cpmm-rebar-panel-subtitle" in REBAR_SOURCE
    assert "cpmm-rebar-preview-title" in REBAR_SOURCE
    assert "Longitudinal Rebar Input" in REBAR_SOURCE
    assert "Section Preview with Rebar — Longitudinal" in REBAR_SOURCE
    assert "Longitudinal Rebar Summary" in REBAR_SOURCE


def test_compact1_active_rebar_status_exposes_included_analysis_participation() -> None:
    assert 'RebarMetric("Analysis Participation", "Included"' in REBAR_SOURCE
    assert "Ordinary rebar enabled" in REBAR_SOURCE
    assert "Active analysis participation and validation gate" in REBAR_SOURCE


def test_compact1_disabled_rebar_workspace_is_two_column_and_collapsed_details() -> None:
    disabled_start = REBAR_SOURCE.index("if not ordinary_rebar_enabled(st.session_state, default=True):")
    disabled_end = REBAR_SOURCE.index('    if "rebar_table" not in st.session_state:', disabled_start)
    disabled_branch = REBAR_SOURCE[disabled_start:disabled_end]

    assert "input_col, review_col = st.columns" in disabled_branch
    assert "Stored Longitudinal Rebar" in disabled_branch
    assert "Stored Rebar table data is preserved for later use" in disabled_branch
    assert 'with st.expander("Stored Rebar table preview", expanded=False)' in disabled_branch
    assert "Stored but excluded from analysis" in disabled_branch
    assert "Preview only — excluded from analysis" in disabled_branch


def test_compact1_detailed_active_summary_is_collapsed_below_decision_view() -> None:
    assert 'with st.expander("Longitudinal Rebar Summary", expanded=False)' in REBAR_SOURCE
    assert 'with st.expander("Longitudinal rebar / torsion Al workflow notes", expanded=False)' in REBAR_SOURCE
