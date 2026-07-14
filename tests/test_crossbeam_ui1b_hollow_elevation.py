from concrete_pmm_pro.crossbeam.workflow import (
    CROSSBEAM_HOLLOW_PRESET_KEY,
    CROSSBEAM_HOLLOW_PRESET_NAME,
    CROSSBEAM_SOLID_PRESET_KEY,
    CROSSBEAM_SOLID_PRESET_NAME,
)
from concrete_pmm_pro.ui.crossbeam_pages import _elevation_figure


def _rows():
    return [
        {
            "Segment": "S1",
            "x_start_m": 0.0,
            "x_end_m": 4.0,
            "Section type / preset": CROSSBEAM_SOLID_PRESET_NAME,
            "Section preset key": CROSSBEAM_SOLID_PRESET_KEY,
            "Section role": "Solid",
            "Section ID": CROSSBEAM_SOLID_PRESET_KEY,
        },
        {
            "Segment": "S2",
            "x_start_m": 4.0,
            "x_end_m": 9.0,
            "Section type / preset": CROSSBEAM_HOLLOW_PRESET_NAME,
            "Section preset key": CROSSBEAM_HOLLOW_PRESET_KEY,
            "Section role": "Hollow",
            "Section ID": CROSSBEAM_HOLLOW_PRESET_KEY,
        },
    ]


def test_hollow_void_outline_spans_full_segment_and_is_dashed():
    fig = _elevation_figure(_rows(), 9.0)
    hollow_voids = [
        shape
        for shape in fig.layout.shapes
        if shape.type == "rect"
        and abs(float(shape.y0) - 0.25) < 1e-9
        and abs(float(shape.y1) - 0.75) < 1e-9
    ]
    assert len(hollow_voids) == 1
    void = hollow_voids[0]
    assert float(void.x0) == 4.0
    assert float(void.x1) == 9.0
    assert void.line.dash == "dash"
    assert void.fillcolor == "rgba(0,0,0,0)"


def test_hollow_elevation_does_not_draw_inset_solid_cutout():
    fig = _elevation_figure(_rows(), 9.0)
    inset_voids = [
        shape
        for shape in fig.layout.shapes
        if shape.type == "rect"
        and 4.0 < float(shape.x0) < float(shape.x1) < 9.0
        and abs(float(shape.y0) - 0.25) < 1e-9
        and abs(float(shape.y1) - 0.75) < 1e-9
    ]
    assert not inset_voids
