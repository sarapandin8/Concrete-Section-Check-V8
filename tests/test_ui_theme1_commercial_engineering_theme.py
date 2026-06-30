from __future__ import annotations

from pathlib import Path


def test_ui_theme1_adds_visual_only_commercial_engineering_theme() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert "UI.THEME1" in source
    assert "visual-only commercial engineering theme foundation" in source
    assert "--cpmm-theme-navy: #071a33" in source
    assert "--cpmm-theme-bg: #f4f7fb" in source
    assert 'section[data-testid="stSidebar"]' in source
    assert 'div[data-testid="stExpander"] details > summary' in source
    assert 'div[data-testid="stMetric"]' in source
    assert 'div[data-testid="stDataEditor"]' in source
    assert 'div[data-testid="stPlotlyChart"]' in source
    assert ".cpmm-executive-header" in source


def test_ui_theme1_is_css_only_and_preserves_navigation_structure() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert "It does not add, remove, move, or rename widgets" in source
    assert source.count('WORKSPACE_NAVIGATION = {') == 1
    assert source.count('"Setup": ["Project", "Materials"]') == 1
    assert source.count('"Sections": ["Section Builder", "Rebar", "Prestress"]') == 1
    assert source.count('"Loads": ["Loads"]') == 1
    assert source.count('"Analysis": ["ULS Strength", "SLS / Stress & Cracking", "SLS Deflection / Camber"]') == 1
    assert source.count('"Result Summary": ["Overview", "ULS Summary", "SLS Summary", "Traceability"]') == 1
    assert source.count('"Report / QA": ["Report / QA"]') == 1


def test_ui_theme1_does_not_touch_dataeditor_commit_hotfix_or_solver_files() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    doc = Path("docs/design/ui_theme1.md").read_text(encoding="utf-8")

    assert "No solver equations" in readme
    assert "data-editor commit logic" in readme
    assert "widget keys" in readme
    assert "No solver equations" in doc
    assert "data-editor commit logic" in doc
    assert "widget keys" in doc
