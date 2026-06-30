from __future__ import annotations

from concrete_pmm_pro.geometry.generators import rectangular_hollow
from concrete_pmm_pro.visualization import create_section_preview


def test_hollow_section_preview_uses_solid_inner_hole_outline() -> None:
    geometry = rectangular_hollow(width_mm=1000, height_mm=800, t_top_mm=120, t_bottom_mm=140, t_left_mm=110, t_right_mm=130)
    fig = create_section_preview(geometry)

    hole_trace = next(trace for trace in fig.data if getattr(trace, "name", "") == "Hole 1")
    assert hole_trace.line.dash in (None, "solid")
