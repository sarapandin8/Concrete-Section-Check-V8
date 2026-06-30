from __future__ import annotations

from pathlib import Path


SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")


def test_beam_uls_static_plot_uses_compact_fixed_review_size() -> None:
    assert "_BEAM_ULS_STATIC_FIG_WIDTH = 980" in SOURCE
    assert "_BEAM_ULS_STATIC_FIG_HEIGHT = 460" in SOURCE
    assert "height=_BEAM_ULS_STATIC_FIG_HEIGHT" in SOURCE
    assert "width=_BEAM_ULS_STATIC_FIG_WIDTH" in SOURCE
    assert "st.image(image_bytes, width=_BEAM_ULS_STATIC_FIG_WIDTH" in SOURCE


def test_beam_uls_static_plot_does_not_use_container_width_poster_scaling() -> None:
    start = SOURCE.index("def _render_beam_uls_static_plotly_figure")
    end = SOURCE.index("\n\nBEAM_ULS_CHECK_TAB_LABELS", start)
    body = SOURCE[start:end]

    assert "use_container_width=True" not in body
    assert "use_column_width=True" not in body
    assert "make the chart look" in body
