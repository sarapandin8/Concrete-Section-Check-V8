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


def test_elevation_has_compact_engineering_legend():
    fig = _elevation_figure(_rows(), 9.0)
    visible_names = [trace.name for trace in fig.data if trace.showlegend is not False]
    assert visible_names[:3] == ["Solid segment", "Hollow segment", "Hidden void boundary"]
    assert "Anchorage heads" not in visible_names


def test_segment_labels_are_compact_and_full_preset_is_in_hover():
    fig = _elevation_figure(_rows(), 9.0)
    annotation_text = [str(annotation.text) for annotation in fig.layout.annotations]
    assert "<b>S1 · CB-S01</b><br>Solid" in annotation_text
    assert "<b>S2 · CB-H01</b><br>Hollow" in annotation_text
    assert not any("Rectangular Solid" in text or "Rectangular Hollow" in text for text in annotation_text)

    hover_templates = [str(trace.hovertemplate) for trace in fig.data if str(trace.name).endswith(" hover")]
    assert any(CROSSBEAM_SOLID_PRESET_NAME in template for template in hover_templates)
    assert any(CROSSBEAM_HOLLOW_PRESET_NAME in template for template in hover_templates)


def test_anchorage_labels_are_arrowed_outside_segment_text():
    fig = _elevation_figure(_rows(), 9.0)
    by_text = {str(annotation.text): annotation for annotation in fig.layout.annotations}
    left = by_text["<b>Left anchorage</b>"]
    right = by_text["<b>Right anchorage</b>"]
    assert left.showarrow is True and right.showarrow is True
    assert float(left.ay) < 0 and float(right.ay) < 0
    assert float(left.ax) > 0 and float(right.ax) < 0
