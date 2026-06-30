from __future__ import annotations

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.geometry.presets import preset_by_key
from concrete_pmm_pro.ui import section_builder


def _keys_for(member_type: str) -> set[str]:
    presets = [
        preset_by_key("rectangle"),
        preset_by_key("parametric_i_girder"),
        preset_by_key("slab_bridge"),
        preset_by_key("railway_u_girder"),
        preset_by_key("box_section_fillet"),
        preset_by_key("psc_i_girder"),
    ]
    filtered = section_builder._filter_presets_for_member_type(
        presets, AnalysisModeSettings(member_type=member_type)
    )
    return {str(preset["key"]) for preset in filtered}


def test_building_workflow_hides_bridge_and_railway_only_presets() -> None:
    keys = _keys_for("building_beam_girder")

    assert "rectangle" in keys
    assert "parametric_i_girder" in keys
    assert "psc_i_girder" in keys
    assert "slab_bridge" not in keys
    assert "railway_u_girder" not in keys
    assert "box_section_fillet" not in keys


def test_bridge_workflow_shows_bridge_and_railway_presets_but_not_building_basic_sections() -> None:
    keys = _keys_for("beam_girder")

    assert "parametric_i_girder" in keys
    assert "slab_bridge" in keys
    assert "railway_u_girder" in keys
    assert "box_section_fillet" in keys
    assert "rectangle" not in keys


def test_parametric_i_girder_uses_workflow_specific_names_without_changing_key() -> None:
    preset = preset_by_key("parametric_i_girder")

    building_label = section_builder._preset_option_label(
        preset, AnalysisModeSettings(member_type="building_beam_girder")
    )
    bridge_label = section_builder._preset_option_label(
        preset, AnalysisModeSettings(member_type="beam_girder")
    )

    assert preset["key"] == "parametric_i_girder"
    assert building_label == "Precast I-Girder: Building · Precast Composite Girder"
    assert bridge_label == "Precast I-Girder: Bridge · Precast Composite Girder"


def test_preset_routing_uses_metadata_not_display_name_keyword_matching() -> None:
    railway = preset_by_key("railway_u_girder")
    assert railway.get("allowed_workflows") == ["beam_girder"]
    assert section_builder._preset_matches_member_type(
        railway, AnalysisModeSettings(member_type="beam_girder")
    )
    assert not section_builder._preset_matches_member_type(
        railway, AnalysisModeSettings(member_type="building_beam_girder")
    )
