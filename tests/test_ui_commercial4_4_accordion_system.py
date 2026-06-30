from __future__ import annotations

from pathlib import Path


def test_ui_commercial4_4_light_blue_expander_system() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert "UI.COMMERCIAL4.4: light-blue accordion system" in source
    assert 'div[data-testid="stExpander"] details > summary' in source
    assert "#f4f8ff" in source
    assert "#eaf2ff" in source
    assert "#123a6b" in source
    assert "#1d6fe7" in source


def test_ui_commercial4_4_removes_global_solid_navy_expander_fill() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("/* UI.COMMERCIAL4.4: light-blue accordion system")
    end = source.index("/* Data tables/editors", start)
    block = source[start:end]

    assert "var(--cpmm-theme-navy) 0%" not in block
    assert "#f7fbff !important" not in block
    assert "details[open] > summary" in block


def test_ui_commercial4_4_is_presentation_only() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    doc = Path("docs/design/ui_commercial4_4.md").read_text(encoding="utf-8")

    assert "No solver equations were changed" in doc
    assert "widget keys" in doc
    assert "project schema" in doc
    assert "presentation-only UI polish" in readme
