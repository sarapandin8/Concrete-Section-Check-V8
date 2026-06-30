from __future__ import annotations

from pathlib import Path


def test_ui_commercial4_5_soft_metric_cards() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert "UI.COMMERCIAL4.5: soften Streamlit metric cards" in source
    assert 'div[data-testid="stMetric"]' in source
    assert "linear-gradient(180deg, #ffffff 0%, #f4f8ff 100%)" in source
    assert "border-left: 5px solid #1d6fe7" in source
    assert "color: #175cd3" in source


def test_ui_commercial4_5_removes_solid_blue_metric_fill() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("/* UI.COMMERCIAL4.5: soften Streamlit metric cards")
    end = source.index("/* UI.COMMERCIAL4.4: light-blue accordion system", start)
    block = source[start:end]

    assert "linear-gradient(135deg, #175cd3 0%, #1d6fe7 100%)" not in block
    assert "color: #ffffff !important" not in block


def test_ui_commercial4_5_is_presentation_only() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    doc = Path("docs/design/ui_commercial4_5.md").read_text(encoding="utf-8")

    assert "presentation-only UI polish" in readme
    assert "solver equations" in doc
    assert "widget keys" in doc
    assert "project schema" in doc
