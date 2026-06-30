from __future__ import annotations

from pathlib import Path


SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")


def test_combined_vt_chart_uses_distinct_stress_and_reinforcement_styles() -> None:
    assert "Stress D/C" in SOURCE
    assert "Transverse D/C" in SOURCE
    assert "_beam_uls_combined_vt_should_plot_trace" in SOURCE
    assert '"Stress D/C value": {"size": 8, "symbol": "circle"' in SOURCE
    assert '"Transverse D/C value": {"size": 8, "symbol": "square"' in SOURCE
    assert '"Longitudinal D/C value": {"size": 9, "symbol": "triangle-up"' in SOURCE


def test_combined_vt_caption_explains_stress_vs_transverse_dc() -> None:
    assert "Stress D/C is the combined concrete stress interaction" in SOURCE
    assert "Transverse D/C is the provided transverse reinforcement utilization" in SOURCE
