from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_ACTIVE_ID_KEY,
    CB_SECLIB_DEFINITIONS_KEY,
    default_section_definitions,
)
from concrete_pmm_pro.ui import crossbeam_section_library as ui


def test_button_column_callback_stages_clicked_section_in_one_event() -> None:
    definitions = default_section_definitions()
    state = ui.st.session_state
    state.clear()
    state[CB_SECLIB_DEFINITIONS_KEY] = definitions
    state[CB_SECLIB_ACTIVE_ID_KEY] = "CB-S01"
    click_key = "open_section_for_test"
    state[ui.CB_SECLIB_SUMMARY_BUTTON_KEY_STATE] = click_key
    state[ui.CB_SECLIB_SUMMARY_BUTTON_ROW_IDS_KEY] = ["CB-S01", "CB-H01"]
    state[click_key] = {"row": 1, "label": "Edit"}

    ui._project_section_summary_button_click()

    assert state[ui.CB_SECLIB_PENDING_ACTIVE_ID_KEY] == "CB-H01"
    assert state[CB_SECLIB_ACTIVE_ID_KEY] == "CB-S01"


def test_button_column_callback_ignores_active_or_invalid_rows() -> None:
    definitions = default_section_definitions()
    state = ui.st.session_state
    state.clear()
    state[CB_SECLIB_DEFINITIONS_KEY] = definitions
    state[CB_SECLIB_ACTIVE_ID_KEY] = "CB-H01"
    click_key = "open_section_for_test"
    state[ui.CB_SECLIB_SUMMARY_BUTTON_KEY_STATE] = click_key
    state[ui.CB_SECLIB_SUMMARY_BUTTON_ROW_IDS_KEY] = ["CB-S01", "CB-H01"]
    state[click_key] = {"row": 1, "label": "Edit"}

    ui._project_section_summary_button_click()
    assert ui.CB_SECLIB_PENDING_ACTIVE_ID_KEY not in state

    state[click_key] = {"row": 9, "label": "Edit"}
    ui._project_section_summary_button_click()
    assert ui.CB_SECLIB_PENDING_ACTIVE_ID_KEY not in state


def test_seclib1f_replaces_selection_checkbox_with_one_click_edit_button() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")

    assert 'rows_with_action = [{"Open": "Edit", **row}' in source
    assert '"Open": button_column(' in source
    assert "on_click=_project_section_summary_button_click" in source
    assert 'selection_mode="single-row"' not in source
    assert "on_select=_project_section_summary_on_select" not in source


def test_section_name_save_uses_standard_blue_action_button_not_form_primary() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")

    assert 'save_name = st.button(' in source
    assert '"Save name"' in source
    assert 'type="primary"' in source
    assert 'st.form_submit_button("Save section name"' not in source
