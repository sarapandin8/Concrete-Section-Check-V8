from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.core.reinforcement_system import ORDINARY_REBAR_FLAG_KEY, REINFORCEMENT_FLAGS_PRESET_KEY
from concrete_pmm_pro.ui.rebar_page import (
    SECTION_BUILDER_ORDINARY_REBAR_SYNC_KEY,
    SECTION_BUILDER_STEEL_SYSTEMS_PRESET_KEY,
    reconcile_ordinary_rebar_system_flag_for_rebar_page,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _railway_state(**extra: object) -> dict[str, object]:
    state: dict[str, object] = {
        "analysis_mode_settings": {"member_type": "beam_girder"},
        "section_category": "General / Non-composite Girder",
        "section_preset_key": "railway_u_girder",
        REINFORCEMENT_FLAGS_PRESET_KEY: "railway_u_girder",
        ORDINARY_REBAR_FLAG_KEY: False,
        "project_metadata": {
            REINFORCEMENT_FLAGS_PRESET_KEY: "railway_u_girder",
            ORDINARY_REBAR_FLAG_KEY: False,
        },
    }
    state.update(extra)
    return state


def test_rebar_ugirder3_rebar_page_prefers_live_section_builder_enabled_mirror() -> None:
    state = _railway_state(
        **{
            SECTION_BUILDER_ORDINARY_REBAR_SYNC_KEY: True,
            SECTION_BUILDER_STEEL_SYSTEMS_PRESET_KEY: "railway_u_girder",
        }
    )

    assert reconcile_ordinary_rebar_system_flag_for_rebar_page(state, default=False) is True
    assert state[ORDINARY_REBAR_FLAG_KEY] is True
    assert state["project_metadata"][ORDINARY_REBAR_FLAG_KEY] is True
    assert state["project_metadata"][REINFORCEMENT_FLAGS_PRESET_KEY] == "railway_u_girder"


def test_rebar_ugirder3_rebar_page_ignores_stale_mirror_from_another_preset() -> None:
    state = _railway_state(
        **{
            SECTION_BUILDER_ORDINARY_REBAR_SYNC_KEY: True,
            SECTION_BUILDER_STEEL_SYSTEMS_PRESET_KEY: "parametric_i_girder",
        }
    )

    assert reconcile_ordinary_rebar_system_flag_for_rebar_page(state, default=False) is False
    assert state[ORDINARY_REBAR_FLAG_KEY] is False


def test_rebar_ugirder3_rebar_page_recovers_from_metadata_enabled_when_top_level_is_stale() -> None:
    state = _railway_state(
        project_metadata={
            REINFORCEMENT_FLAGS_PRESET_KEY: "railway_u_girder",
            ORDINARY_REBAR_FLAG_KEY: True,
        }
    )

    assert reconcile_ordinary_rebar_system_flag_for_rebar_page(state, default=False) is True
    assert state[ORDINARY_REBAR_FLAG_KEY] is True


def test_rebar_ugirder3_section_builder_writes_non_widget_steel_system_mirrors() -> None:
    source = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "section_builder.py").read_text(encoding="utf-8")
    store_start = source.index("def _store_reinforcement_flags_metadata")
    store_end = source.index("def _render_reinforcement_prestress_system_panel", store_start)
    store_block = source[store_start:store_end]

    assert "SECTION_BUILDER_ORDINARY_REBAR_SYNC_KEY" in store_block
    assert "SECTION_BUILDER_STEEL_SYSTEMS_PRESET_KEY" in store_block
    assert "metadata[SECTION_BUILDER_ORDINARY_REBAR_SYNC_KEY]" in store_block


def test_rebar_ugirder3_disabled_branch_uses_reconciled_section_builder_flag() -> None:
    source = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "rebar_page.py").read_text(encoding="utf-8")
    assert "ordinary_rebar_system_enabled = reconcile_ordinary_rebar_system_flag_for_rebar_page" in source
    assert "if not ordinary_rebar_system_enabled:" in source
