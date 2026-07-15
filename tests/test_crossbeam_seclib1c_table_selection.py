from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from concrete_pmm_pro.ui.crossbeam_section_library import (
    _selected_section_id_from_summary_event,
    _summary_selection_rows,
)


def _rows() -> list[dict[str, object]]:
    return [
        {"Section ID": "CB-S01", "Section name": "Solid"},
        {"Section ID": "CB-H01", "Section name": "Hollow typical"},
        {"Section ID": "CB-H02", "Section name": "Hollow heavy web"},
    ]


def test_summary_selection_supports_streamlit_attribute_event_shape() -> None:
    event = SimpleNamespace(selection=SimpleNamespace(rows=[2]))

    assert _summary_selection_rows(event) == [2]
    assert _selected_section_id_from_summary_event(event, _rows()) == "CB-H02"


def test_summary_selection_supports_mapping_event_shape() -> None:
    event = {"selection": {"rows": [1]}}

    assert _summary_selection_rows(event) == [1]
    assert _selected_section_id_from_summary_event(event, _rows()) == "CB-H01"


def test_summary_selection_rejects_empty_invalid_and_out_of_range_rows() -> None:
    assert _selected_section_id_from_summary_event(None, _rows()) == ""
    assert _selected_section_id_from_summary_event({"selection": {"rows": []}}, _rows()) == ""
    assert _selected_section_id_from_summary_event({"selection": {"rows": [99]}}, _rows()) == ""
    assert _summary_selection_rows({"selection": {"rows": ["bad", 0]}}) == [0]


def test_seclib1c_selection_staging_remains_available_after_button_upgrade() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")

    assert "_project_section_summary_button_click" in source
    assert "_stage_definition_selection(" in source
    assert "geometry, properties, live preview, and management controls update together." in source
