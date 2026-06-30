from __future__ import annotations

from pathlib import Path


def test_rebar_page_compacts_streamlit_metric_values_for_seismic_advisor() -> None:
    source = Path("concrete_pmm_pro/ui/rebar_page.py").read_text(encoding="utf-8")

    assert "AASHTO.COL.SEISMIC3" in source
    assert 'div[data-testid="stMetricValue"]' in source
    assert "font-size: 1.04rem !important" in source
    assert "overflow-wrap: anywhere !important" in source
    assert "white-space: normal !important" in source
