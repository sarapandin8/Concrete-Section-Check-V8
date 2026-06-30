from __future__ import annotations

from concrete_pmm_pro.core.reinforcement_system import (
    ORDINARY_REBAR_FLAG_KEY,
    PRESTRESSING_STEEL_FLAG_KEY,
    ordinary_rebar_enabled,
    prestressing_steel_enabled,
)


def test_reinforcement_flags_fall_back_to_project_metadata_when_top_level_missing() -> None:
    state = {
        "project_metadata": {
            ORDINARY_REBAR_FLAG_KEY: False,
            PRESTRESSING_STEEL_FLAG_KEY: True,
        }
    }

    assert ordinary_rebar_enabled(state, default=True) is False
    assert prestressing_steel_enabled(state, default=False) is True


def test_top_level_reinforcement_flags_override_project_metadata() -> None:
    state = {
        ORDINARY_REBAR_FLAG_KEY: True,
        PRESTRESSING_STEEL_FLAG_KEY: False,
        "project_metadata": {
            ORDINARY_REBAR_FLAG_KEY: False,
            PRESTRESSING_STEEL_FLAG_KEY: True,
        },
    }

    assert ordinary_rebar_enabled(state, default=False) is True
    assert prestressing_steel_enabled(state, default=True) is False


def test_bridge_beam_girder_defaults_to_rebar_included_when_flag_missing() -> None:
    state = {
        "analysis_mode_settings": {"member_type": "beam_girder"},
        "section_category": "Precast Composite Girder",
        "section_preset_key": "precast_box_beam_interior",
        "girder_section_family": "precast_composite_girder",
    }

    assert ordinary_rebar_enabled(state, default=True) is True
    assert prestressing_steel_enabled(state, default=False) is True


def test_building_shared_prestressed_girder_defaults_to_rebar_excluded_when_flag_missing() -> None:
    state = {
        "analysis_mode_settings": {"member_type": "building_beam_girder"},
        "section_category": "Precast Composite Girder",
        "section_preset_key": "parametric_i_girder",
        "girder_section_family": "precast_composite_girder",
    }

    assert ordinary_rebar_enabled(state, default=True) is False
    assert prestressing_steel_enabled(state, default=False) is True


def test_building_beam_girder_explicit_rebar_checkbox_overrides_workflow_default() -> None:
    state = {
        ORDINARY_REBAR_FLAG_KEY: True,
        PRESTRESSING_STEEL_FLAG_KEY: False,
        "analysis_mode_settings": {"member_type": "building_beam_girder"},
        "section_category": "Precast Composite Girder",
        "section_preset_key": "parametric_i_girder",
        "girder_section_family": "precast_composite_girder",
    }

    assert ordinary_rebar_enabled(state, default=False) is True
    assert prestressing_steel_enabled(state, default=True) is False


def test_building_basic_rc_beam_keeps_rebar_enabled_default_when_flag_missing() -> None:
    state = {
        "analysis_mode_settings": {"member_type": "building_beam_girder"},
        "section_category": "Basic Solid",
        "section_preset_key": "rectangle",
    }

    assert ordinary_rebar_enabled(state, default=False) is True
    assert prestressing_steel_enabled(state, default=True) is False
