from __future__ import annotations

from pathlib import Path

import app


APP_SOURCE = Path("app.py").read_text(encoding="utf-8")
SECTION_PLOT_SOURCE = Path("concrete_pmm_pro/visualization/section_plot.py").read_text(encoding="utf-8")
REBAR_SOURCE = Path("concrete_pmm_pro/ui/rebar_page.py").read_text(encoding="utf-8")


def test_main_workspace_order_keeps_report_qa_after_results() -> None:
    assert list(app.WORKSPACE_NAVIGATION) == [
        "Setup",
        "Sections",
        "Loads",
        "Analysis",
        "Result Summary",
        "Report / QA",
    ]


def test_results_workspace_uses_commercial_read_only_foundation() -> None:
    start = APP_SOURCE.index("def render_results_workspace()")
    end = APP_SOURCE.index("\n\ndef render_report_qa_workspace()", start)
    body = APP_SOURCE[start:end]

    assert "render_page_header(" in body
    assert "render_metric_cards(" in body
    assert "render_section_bar(" in body
    assert "st.info(RESULTS_WORKSPACE_PLACEHOLDER)" not in body
    assert "Opening Result Summary does not rerun PMM, ULS, or SLS" in body
    assert "Diagram Review" not in body


def test_analysis_workspace_does_not_keep_report_qa_subpage() -> None:
    assert "Report / QA" not in app.WORKSPACE_NAVIGATION["Analysis"]
    assert app.WORKSPACE_NAVIGATION["Result Summary"] == ["Overview", "ULS Summary", "SLS Summary", "Traceability"]
    assert app.WORKSPACE_NAVIGATION["Report / QA"] == ["Report / QA"]


def test_shared_preview_title_and_legend_guards_remain_in_place() -> None:
    assert SECTION_PLOT_SOURCE.count('title=dict(text="", font=dict(size=1, color="rgba(0,0,0,0)"))') >= 2
    assert 'legend=dict(' in SECTION_PLOT_SOURCE


def test_rebar_auto_perimeter_default_remains_50_mm() -> None:
    offset_label = REBAR_SOURCE.index('"Bar center offset (mm)"')
    offset_control = REBAR_SOURCE[offset_label : offset_label + 260]

    assert "value=50.0" in offset_control
    assert "Default controls: 50 mm to bar center" in REBAR_SOURCE
