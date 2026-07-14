from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_ACTIVE_ID_KEY,
    CB_SECLIB_DEFINITIONS_KEY,
    CB_SECLIB_LOADED_ID_KEY,
    DEFAULT_HOLLOW_SECTION_ID,
    DEFAULT_SOLID_SECTION_ID,
    default_section_definitions,
    duplicate_definition,
)
from concrete_pmm_pro.ui.crossbeam_section_library import (
    CB_SECLIB_NOTICE_KEY,
    CB_SECLIB_PENDING_ACTIVE_ID_KEY,
    _apply_pending_definition_selection,
    _stage_definition_selection,
)


def test_library_actions_stage_active_id_until_next_render_cycle() -> None:
    definitions = default_section_definitions()
    updated, new_id = duplicate_definition(definitions, DEFAULT_HOLLOW_SECTION_ID)
    state: dict[str, object] = {
        CB_SECLIB_ACTIVE_ID_KEY: DEFAULT_HOLLOW_SECTION_ID,
        CB_SECLIB_LOADED_ID_KEY: DEFAULT_HOLLOW_SECTION_ID,
    }

    _stage_definition_selection(
        state,
        updated,
        new_id,
        notice="Created a duplicate.",
    )

    # The rendered selectbox key must not be mutated by the button action.
    assert state[CB_SECLIB_ACTIVE_ID_KEY] == DEFAULT_HOLLOW_SECTION_ID
    assert state[CB_SECLIB_PENDING_ACTIVE_ID_KEY] == new_id
    assert state[CB_SECLIB_NOTICE_KEY] == "Created a duplicate."
    assert CB_SECLIB_LOADED_ID_KEY not in state
    assert state[CB_SECLIB_DEFINITIONS_KEY] == updated

    applied = _apply_pending_definition_selection(state, updated)

    assert applied is True
    assert state[CB_SECLIB_ACTIVE_ID_KEY] == new_id
    assert state[CB_SECLIB_LOADED_ID_KEY] == new_id
    assert CB_SECLIB_PENDING_ACTIVE_ID_KEY not in state
    assert state["section_preset_selector_key"] == updated[-1]["Preset key"]
    assert state["section_parameters"] == updated[-1]["Parameters"]


def test_invalid_pending_section_id_is_ignored_safely() -> None:
    definitions = default_section_definitions()
    state: dict[str, object] = {
        CB_SECLIB_ACTIVE_ID_KEY: DEFAULT_SOLID_SECTION_ID,
        CB_SECLIB_PENDING_ACTIVE_ID_KEY: "DOES-NOT-EXIST",
    }

    assert _apply_pending_definition_selection(state, definitions) is False
    assert state[CB_SECLIB_ACTIVE_ID_KEY] == DEFAULT_SOLID_SECTION_ID
    assert CB_SECLIB_PENDING_ACTIVE_ID_KEY not in state


def test_seclib1a_primary_workflow_is_one_click_and_crossbeam_scoped() -> None:
    root = Path(__file__).resolve().parents[1]
    library_source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")
    builder_source = (root / "concrete_pmm_pro" / "ui" / "section_builder.py").read_text(encoding="utf-8")

    assert '"Section to edit"' in library_source
    assert '"Duplicate current"' in library_source
    assert '"New Hollow"' in library_source
    assert '"New Solid"' in library_source
    assert "New section family" not in library_source
    assert "CB_SECLIB_PENDING_ACTIVE_ID_KEY" in library_source
    assert "preset family is fixed for each Section ID" in library_source
    assert "if is_portal_frame_crossbeam_workflow(analysis_mode_settings):" in builder_source
    assert "Controlled by the selected Crossbeam Project Section above" in builder_source
