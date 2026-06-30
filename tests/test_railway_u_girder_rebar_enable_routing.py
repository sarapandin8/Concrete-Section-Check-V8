from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.core.reinforcement_system import ORDINARY_REBAR_FLAG_KEY, REINFORCEMENT_FLAGS_PRESET_KEY, ordinary_rebar_enabled
from concrete_pmm_pro.ui.rebar_page import publish_ordinary_rebar_system_flag

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_rebar_enable1_section_builder_checkbox_synchronizes_metadata_on_change() -> None:
    source = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "section_builder.py").read_text(encoding="utf-8")

    ordinary_widget_start = source.index('"Include ordinary rebar / longitudinal Al"')
    ordinary_widget_end = source.index('with col2:', ordinary_widget_start)
    ordinary_widget = source[ordinary_widget_start:ordinary_widget_end]

    assert "key=ORDINARY_REBAR_FLAG_KEY" in ordinary_widget
    assert "on_change=_store_reinforcement_flags_metadata" in ordinary_widget


def test_rebar_enable1_rebar_page_has_in_page_enable_recovery_action() -> None:
    source = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "rebar_page.py").read_text(encoding="utf-8")
    disabled_branch_start = source.index("if not ordinary_rebar_system_enabled:")
    disabled_branch_end = source.index('    if "rebar_table" not in st.session_state:', disabled_branch_start)
    disabled_branch = source[disabled_branch_start:disabled_branch_end]

    assert "_render_enable_ordinary_rebar_action()" in disabled_branch
    assert "Enable ordinary rebar / longitudinal Al" in source
    assert "publish_ordinary_rebar_system_flag(st.session_state, True)" in source


def test_rebar_enable1_publish_helper_aligns_top_level_state_and_metadata_for_railway_u_girder() -> None:
    state = {
        "analysis_mode_settings": {"member_type": "beam_girder"},
        "section_category": "General / Non-composite Girder",
        "section_preset_key": "railway_u_girder",
        "project_metadata": {
            ORDINARY_REBAR_FLAG_KEY: False,
            REINFORCEMENT_FLAGS_PRESET_KEY: "railway_u_girder",
        },
    }

    assert ordinary_rebar_enabled(state, default=True) is False

    publish_ordinary_rebar_system_flag(state, True)

    assert state[ORDINARY_REBAR_FLAG_KEY] is True
    assert state[REINFORCEMENT_FLAGS_PRESET_KEY] == "railway_u_girder"
    assert state["project_metadata"][ORDINARY_REBAR_FLAG_KEY] is True
    assert state["project_metadata"][REINFORCEMENT_FLAGS_PRESET_KEY] == "railway_u_girder"
    assert ordinary_rebar_enabled(state, default=False) is True
