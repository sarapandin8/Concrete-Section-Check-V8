from __future__ import annotations

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.reinforcement_system import (
    ORDINARY_REBAR_FLAG_KEY,
    PRESTRESSING_STEEL_FLAG_KEY,
)
from concrete_pmm_pro.state.dirty_state import input_group_hashes, project_input_hash


def _bridge_girder_state() -> dict[str, object]:
    return {
        "analysis_mode_settings": AnalysisModeSettings(member_type="beam_girder"),
        "design_code": "AASHTO LRFD",
        "code_edition": "AASHTO LRFD 9th Edition",
        "section_preset_key": "railway_u_girder",
        "section_category": "Precast Composite Girder",
        "girder_section_family": "precast_composite_girder",
        "section_parameters": {"B_mm": 5500.0, "H_mm": 1600.0},
        "load_cases": [],
    }


def test_bridge_uls_input_hash_is_stable_when_section_builder_materializes_default_flags() -> None:
    before = _bridge_girder_state()
    after = dict(before)
    after.update(
        {
            ORDINARY_REBAR_FLAG_KEY: True,
            PRESTRESSING_STEEL_FLAG_KEY: True,
            "reinforcement_flags_preset_key": "railway_u_girder",
            "section_builder_ordinary_rebar_enabled": True,
            "section_builder_prestressing_steel_enabled": True,
            "section_builder_steel_systems_preset_key": "railway_u_girder",
        }
    )

    assert input_group_hashes(before)["Section"] == input_group_hashes(after)["Section"]
    assert project_input_hash(before) == project_input_hash(after)


def test_section_builder_user_override_marker_is_not_part_of_analysis_input_hash() -> None:
    before = _bridge_girder_state()
    before.update({ORDINARY_REBAR_FLAG_KEY: True, PRESTRESSING_STEEL_FLAG_KEY: True})

    after = dict(before)
    after["section_builder_steel_systems_user_overridden"] = True

    assert project_input_hash(before) == project_input_hash(after)


def test_section_builder_source_can_auto_upgrade_legacy_false_default_without_static_reset() -> None:
    source = ( __import__("concrete_pmm_pro.ui.section_builder", fromlist=["SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY"]))

    assert hasattr(source, "SECTION_BUILDER_STEEL_SYSTEMS_USER_OVERRIDE_KEY")
    text = open("concrete_pmm_pro/ui/section_builder.py", encoding="utf-8").read()
    assert "Legacy sessions/projects may contain False from the older Beam/Girder" in text
    assert "default_rebar if default_rebar and not user_overridden" in text
    assert "on_change=_on_reinforcement_flags_changed" in text
