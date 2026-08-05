from __future__ import annotations

from pathlib import Path


def test_torsion_chart_does_not_add_large_decision_annotation_inside_plot() -> None:
    source = (Path(__file__).parents[1] / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text()
    start = source.index("def _make_crossbeam_uls_torsion_figure(")
    end = source.index("def _render_crossbeam_uls_torsion_workspace()", start)
    function_source = source[start:end]

    assert "PASS — {summary.get('label')}" not in function_source
    assert "REVIEW — {summary.get('label')}" not in function_source
    assert 'bgcolor="rgba(254,226,226,0.90)"' not in function_source
    assert 'bgcolor="rgba(220,252,231,0.90)"' not in function_source
    assert "Gov. torsional-strength D/C" in function_source
