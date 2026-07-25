from __future__ import annotations

from pathlib import Path


def test_crossbeam_chrome_reads_active_project_section_definition() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "app.py").read_text(encoding="utf-8")
    start = source.index("def _current_section_label_for_chrome()")
    end = source.index("\ndef _project_code_label_for_chrome()", start)
    block = source[start:end]

    assert "is_portal_frame_crossbeam_workflow(mode)" in block
    assert "CB_SECLIB_DEFINITIONS_KEY" in block
    assert "CB_SECLIB_ACTIVE_ID_KEY" in block
    assert "canonical_section_definitions" in block
    assert "definition_map(definitions).get(active_id)" in block
    assert 'active.get("Preset family")' in block


def test_crossbeam_chrome_rejects_stale_generic_preset_label() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "app.py").read_text(encoding="utf-8")
    start = source.index("def _current_section_label_for_chrome()")
    end = source.index("\ndef _project_code_label_for_chrome()", start)
    block = source[start:end]

    assert "CROSSBEAM_SOLID_PRESET_KEY" in block
    assert "CROSSBEAM_HOLLOW_PRESET_KEY" in block
    assert 'preset_name.startswith("PC Crossbeam —")' in block
    assert 'return "Crossbeam section not selected"' in block
