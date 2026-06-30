from __future__ import annotations

from concrete_pmm_pro.geometry.generators import circle
from concrete_pmm_pro.visualization import create_section_preview


def test_section_preview_forces_blank_legend_title_to_avoid_undefined_label() -> None:
    geometry = circle(diameter_mm=600)

    fig = create_section_preview(geometry)

    assert fig.layout.legend.title.text == ""
