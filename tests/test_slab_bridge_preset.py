from __future__ import annotations

import pytest

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.geometry import default_registry
from concrete_pmm_pro.geometry.presets import preset_by_key
from concrete_pmm_pro.geometry.summary import summarize_geometry
from concrete_pmm_pro.geometry.validation import validate_section_geometry
from concrete_pmm_pro.ui.section_builder import _preset_matches_member_type


DEFAULT_PARAMS = {
    "width_mm": 5100,
    "edge_depth_mm": 400,
    "center_depth_mm": 450,
}


def test_slab_bridge_preset_is_available_for_bridge_beam_girder() -> None:
    preset = preset_by_key("slab_bridge")

    assert preset["display_name"] == "Slab Bridge"
    assert preset["category"] == "General / Non-composite Girder"
    assert preset["generator"] == "slab_bridge"
    assert _preset_matches_member_type(preset, AnalysisModeSettings(member_type="beam_girder")) is True


def test_slab_bridge_default_geometry_matches_user_drawing_dimensions() -> None:
    geometry = default_registry.geometry("slab_bridge")(**DEFAULT_PARAMS)
    validation = validate_section_geometry(geometry)
    summary = summarize_geometry(geometry)

    assert validation.is_valid, validation.errors
    assert len(geometry.holes) == 0
    assert geometry.metadata["preset"] == "slab_bridge"
    assert geometry.metadata["crown_rise_mm"] == pytest.approx(50.0)
    assert summary.area_mm2 == pytest.approx(5100 * 400 + 0.5 * 5100 * 50)
    assert summary.x_min_mm == pytest.approx(-2550.0)
    assert summary.x_max_mm == pytest.approx(2550.0)
    assert summary.y_min_mm == pytest.approx(-225.0)
    assert summary.y_max_mm == pytest.approx(225.0)

    vertices = [(round(point.x, 6), round(point.y, 6)) for point in geometry.outer_polygon]
    assert vertices == [
        (-2550.0, -225.0),
        (2550.0, -225.0),
        (2550.0, 175.0),
        (0.0, 225.0),
        (-2550.0, 175.0),
    ]


def test_slab_bridge_dimension_guides_show_all_drawing_values() -> None:
    dimensions = default_registry.dimensions("slab_bridge")(**DEFAULT_PARAMS)
    values_by_symbol = {dimension.symbol: dimension.value_mm for dimension in dimensions}

    assert values_by_symbol["B"] == pytest.approx(5100.0)
    assert values_by_symbol["B/2 L"] == pytest.approx(2550.0)
    assert values_by_symbol["B/2 R"] == pytest.approx(2550.0)
    assert values_by_symbol["Hc"] == pytest.approx(450.0)
    assert values_by_symbol["He L"] == pytest.approx(400.0)
    assert values_by_symbol["He R"] == pytest.approx(400.0)
    assert values_by_symbol["CL"] is None


def test_slab_bridge_rejects_edge_depth_greater_than_center_depth() -> None:
    with pytest.raises(ValueError, match="center_depth_mm must be greater than or equal to edge_depth_mm"):
        default_registry.geometry("slab_bridge")(width_mm=5100, edge_depth_mm=500, center_depth_mm=450)
