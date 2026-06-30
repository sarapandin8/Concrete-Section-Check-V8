from __future__ import annotations

import app


def test_workspace_navigation_groups_required_top_level_tabs() -> None:
    assert list(app.WORKSPACE_NAVIGATION) == ["Setup", "Sections", "Loads", "Analysis", "Result Summary", "Report / QA"]


def test_setup_workspace_contains_project_and_materials() -> None:
    assert app.WORKSPACE_NAVIGATION["Setup"] == ["Project", "Materials"]


def test_sections_workspace_contains_section_rebar_prestress() -> None:
    assert app.WORKSPACE_NAVIGATION["Sections"] == ["Section Builder", "Rebar", "Prestress"]


def test_analysis_workspace_contains_required_subtabs() -> None:
    assert app.WORKSPACE_NAVIGATION["Analysis"] == ["ULS Strength", "SLS / Stress & Cracking", "SLS Deflection / Camber"]
    assert app.WORKSPACE_NAVIGATION["Result Summary"] == ["Overview", "ULS Summary", "SLS Summary", "Traceability"]
    assert app.WORKSPACE_NAVIGATION["Report / QA"] == ["Report / QA"]


def test_analysis_page_exports_real_subtab_render_functions() -> None:
    from concrete_pmm_pro.ui import analysis_page

    assert analysis_page.ANALYSIS_SUBTABS == ["ULS Strength", "SLS / Stress & Cracking", "SLS Deflection / Camber"]
    assert analysis_page.ANALYSIS_COLUMN_PIER_SUBTABS == ["ULS Strength"]
    assert callable(analysis_page.render_analysis_uls_pmm)
    assert callable(analysis_page.render_analysis_sls_stress)
    assert callable(analysis_page.render_analysis_sls_deflection_camber)
    assert callable(analysis_page.render_analysis_report_qa)
    assert callable(analysis_page.render_report_qa_page)


def test_results_workspace_placeholder_text_names_future_workspace() -> None:
    assert "Future Result Summary workspace" in app.RESULTS_WORKSPACE_PLACEHOLDER
    assert "Current detailed outputs remain available under Analysis" in app.RESULTS_WORKSPACE_PLACEHOLDER


def test_workspace_render_functions_exist() -> None:
    assert callable(app.render_setup_workspace)
    assert callable(app.render_sections_workspace)
    assert callable(app.render_loads_workspace)
    assert callable(app.render_analysis_workspace)
    assert callable(app.render_results_workspace)
    assert callable(app.render_report_qa_workspace)
