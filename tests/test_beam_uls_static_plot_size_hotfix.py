from __future__ import annotations

from pathlib import Path


SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")


def test_beam_uls_static_plot_uses_wide_full_container_review_size() -> None:
    assert "_BEAM_ULS_STATIC_FIG_WIDTH = 1440" in SOURCE
    assert "_BEAM_ULS_STATIC_FIG_HEIGHT = 560" in SOURCE
    assert "height=_BEAM_ULS_STATIC_FIG_HEIGHT" in SOURCE
    assert "width=_BEAM_ULS_STATIC_FIG_WIDTH" in SOURCE
    assert "st.image(image_bytes, use_container_width=True" in SOURCE


def test_beam_uls_static_plot_keeps_high_resolution_export_before_scaling() -> None:
    start = SOURCE.index("def _render_beam_uls_static_plotly_figure")
    end = SOURCE.index("\n\nBEAM_ULS_CHECK_TAB_LABELS", start)
    body = SOURCE[start:end]

    assert "wide high-resolution PNG" in body
    assert "scale=2" in body
    assert "use_container_width=True" in body
    assert "use_column_width=True" in body
