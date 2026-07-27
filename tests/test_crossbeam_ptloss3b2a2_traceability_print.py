from __future__ import annotations

from pathlib import Path


def _elastic_source() -> str:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    return source.split("with elastic_shortening_tab:", 1)[1].split(
        "with time_dependent_tab:", 1
    )[0]


def test_ptloss3b2a2_exposes_member_and_prestress_loss_code_sources() -> None:
    elastic = _elastic_source()
    assert '"title": "Member design code"' in elastic
    assert "workflow_project_code_label_from_session" in elastic
    assert '"title": "Prestress-loss basis"' in elastic
    assert '"value": "AASHTO LRFD 2020"' in elastic
    assert "Prestress losses §5.9.3 · Elastic Shortening §5.9.3.2.3b" in elastic
    assert "The active member design code and the prestress-loss methodology are separate" in elastic


def test_ptloss3b2a2_print_css_targets_each_plotly_figure_container() -> None:
    elastic = _elastic_source()
    assert ".ptloss3b2-print-figure-anchor" in elastic
    assert 'div[data-testid="stPlotlyChart"]' in elastic
    assert ':has(.ptloss3b2-print-figure-anchor)' in elastic
    assert "break-inside: avoid-page" in elastic
    assert "page-break-inside: avoid" in elastic
    assert elastic.count("_render_ptloss3b2a_print_figure(") >= 2


def test_ptloss3b2a2_uses_on_demand_lightweight_fcgp_and_keeps_downstream_handoffs_locked() -> None:
    elastic = _elastic_source()
    assert "Run Lightweight ES Analysis" in elastic
    assert "single cumulative AASHTO design route" in elastic
    assert "AASHTO f_cgp route" in elastic
    assert "Pe/Pe_eff assembly and Time-Dependent losses remain locked" in elastic

