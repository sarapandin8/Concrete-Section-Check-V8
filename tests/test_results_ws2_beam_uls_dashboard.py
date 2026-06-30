from __future__ import annotations

from pathlib import Path


SOURCE = Path("app.py").read_text(encoding="utf-8")


def test_results_workspace_has_beam_girder_uls_dashboard_section() -> None:
    assert "ULS Summary Dashboard" in SOURCE
    assert "_render_results_beam_uls_dashboard(st.session_state)" in SOURCE
    assert "Read-only strength result summary from cached Analysis outputs." in SOURCE


def test_results_beam_uls_dashboard_uses_four_check_summary_rows() -> None:
    assert '_RESULTS_BEAM_ULS_CHECKS = ["Flexure", "Shear", "Torsion", "Shear + Torsion"]' in SOURCE
    assert "def _results_beam_uls_summary_rows" in SOURCE
    assert "Required Action" in SOURCE
    assert "Resolve source Shear/Torsion FAIL before accepting V+T interaction." in SOURCE


def test_results_governing_table_reads_richer_beam_uls_rows() -> None:
    start = SOURCE.index("def _results_add_beam_uls_rows")
    end = SOURCE.index("\n\ndef _results_add_sls_rows", start)
    body = SOURCE[start:end]

    assert "_results_beam_uls_summary_rows(state)" in body
    assert 'if bool(row.get("__calculated"))' in body
    assert '"Source": row["Source"]' in body


def test_results_source_blocked_is_treated_as_danger_status() -> None:
    assert '"BLOCKED"' in SOURCE
    assert '"SOURCE BLOCKED"' in SOURCE
    assert 'if any(token in label for token in ["FAIL", "ERROR", "DANGER", "EXCEED", "BLOCKED"])' in SOURCE


def test_results_not_calculated_is_warning_not_ready() -> None:
    start = SOURCE.index("def _results_style_for_status")
    end = SOURCE.index("\n\ndef _results_status_pill", start)
    body = SOURCE[start:end]

    assert '"NOT CALCULATED"' in body
    assert body.index('"NOT CALCULATED"') < body.index('"CALCULATED"')
