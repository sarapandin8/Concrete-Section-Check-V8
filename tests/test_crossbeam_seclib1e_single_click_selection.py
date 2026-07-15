from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_ACTIVE_ID_KEY,
    CB_SECLIB_DEFINITIONS_KEY,
    default_section_definitions,
)
from concrete_pmm_pro.ui import crossbeam_section_library as ui


def test_summary_callback_stages_clicked_row_in_one_selection_event() -> None:
    definitions = default_section_definitions()
    state = ui.st.session_state
    state.clear()
    state[CB_SECLIB_DEFINITIONS_KEY] = definitions
    state[CB_SECLIB_ACTIVE_ID_KEY] = "CB-S01"
    widget_key = "summary_event_for_test"
    state[ui.CB_SECLIB_SUMMARY_WIDGET_KEY_STATE] = widget_key
    state[ui.CB_SECLIB_SUMMARY_ROW_IDS_KEY] = ["CB-S01", "CB-H01"]
    state[widget_key] = {"selection": {"rows": [1]}}

    ui._project_section_summary_on_select()

    assert state[ui.CB_SECLIB_PENDING_ACTIVE_ID_KEY] == "CB-H01"
    assert state[CB_SECLIB_ACTIVE_ID_KEY] == "CB-S01"


def test_summary_callback_ignores_current_or_invalid_selection() -> None:
    definitions = default_section_definitions()
    state = ui.st.session_state
    state.clear()
    state[CB_SECLIB_DEFINITIONS_KEY] = definitions
    state[CB_SECLIB_ACTIVE_ID_KEY] = "CB-H01"
    widget_key = "summary_event_for_test"
    state[ui.CB_SECLIB_SUMMARY_WIDGET_KEY_STATE] = widget_key
    state[ui.CB_SECLIB_SUMMARY_ROW_IDS_KEY] = ["CB-S01", "CB-H01"]
    state[widget_key] = {"selection": {"rows": [1]}}

    ui._project_section_summary_on_select()

    assert ui.CB_SECLIB_PENDING_ACTIVE_ID_KEY not in state


def test_seclib1e_uses_pre_rerun_callback_not_post_render_second_rerun() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")

    assert "on_select=_project_section_summary_on_select" in source
    assert 'on_select="rerun",' not in source
    assert "selected_from_table =" not in source
    assert "summary_widget_key = f\"crossbeam_seclib1e_project_section_summary_{summary_revision}\"" in source
