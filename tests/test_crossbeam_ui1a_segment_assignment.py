from pathlib import Path

from concrete_pmm_pro.crossbeam.workflow import (
    CROSSBEAM_HOLLOW_PRESET_KEY,
    CROSSBEAM_HOLLOW_PRESET_NAME,
    CROSSBEAM_SOLID_PRESET_KEY,
    CROSSBEAM_SOLID_PRESET_NAME,
    DEFAULT_CROSSBEAM_LENGTH_M,
    default_crossbeam_segment_rows,
)
from concrete_pmm_pro.ui.crossbeam_pages import _canonical_segment_rows, _validate_segments


def test_crossbeam_ui1a_navigation_places_layout_after_builder():
    source = Path("app.py").read_text()
    assert (
        'return ["Section Builder", "Segment Layout", "Rebar", "Tendon System", '
        '"Tendon Profile", "Prestress Loss"]'
        in source
    )
    assert '"Sections": ["Section Builder", "Rebar", "Prestress"]' in source


def test_crossbeam_ui1a_default_length_is_20_m():
    assert DEFAULT_CROSSBEAM_LENGTH_M == 20.0
    rows = default_crossbeam_segment_rows()
    assert rows[0]["x_start_m"] == 0.0
    assert rows[-1]["x_end_m"] == 20.0


def test_segment_seed_references_section_builder_presets_not_free_text_ids():
    rows = default_crossbeam_segment_rows(20.0)
    assert {row["Section preset key"] for row in rows} == {
        CROSSBEAM_SOLID_PRESET_KEY,
        CROSSBEAM_HOLLOW_PRESET_KEY,
    }
    assert {row["Section type / preset"] for row in rows} == {
        CROSSBEAM_SOLID_PRESET_NAME,
        CROSSBEAM_HOLLOW_PRESET_NAME,
    }
    assert all(row["Section ID"] == row["Section preset key"] for row in rows)


def test_legacy_role_rows_migrate_to_section_builder_preset_dropdown_values():
    legacy = [
        {"Segment": "S1", "x_start_m": 0.0, "x_end_m": 8.0, "Section role": "Solid", "Section ID": "CS-S1"},
        {"Segment": "S2", "x_start_m": 8.0, "x_end_m": 20.0, "Section role": "Hollow", "Section ID": "CS-H2"},
    ]
    rows = _canonical_segment_rows(legacy)
    assert rows[0]["Section preset key"] == CROSSBEAM_SOLID_PRESET_KEY
    assert rows[1]["Section preset key"] == CROSSBEAM_HOLLOW_PRESET_KEY
    normalized, errors = _validate_segments(rows, 20.0)
    assert not errors
    assert normalized[-1]["x_end_m"] == 20.0


def test_segment_layout_editor_uses_project_section_id_selectbox():
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text()
    assert 'SelectboxColumn(\n                "Section ID"' in source
    assert "Section IDs are created and edited in Section Builder" in source
    assert 'TextColumn("Section name", disabled=True)' in source
    assert 'TextColumn("Preset family", disabled=True)' in source
