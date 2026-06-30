from __future__ import annotations

import pytest

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.geometry import default_registry
from concrete_pmm_pro.geometry.presets import preset_by_key
from concrete_pmm_pro.geometry.summary import summarize_geometry
from concrete_pmm_pro.geometry.validation import validate_section_geometry
from concrete_pmm_pro.ui.section_builder import _preset_matches_member_type


DEFAULT_PARAMS = {
    "width_mm": 5500,
    "depth_mm": 1600,
    "top_wall_width_mm": 600,
    "bottom_side_width_mm": 650,
    "haunch_x_mm": 300,
    "haunch_y_mm": 300,
    "h1_step_height_mm": 670,
    "h2_bottom_opening_mm": 305,
    "h3_floor_side_thickness_mm": 395,
    "h4_floor_center_thickness_mm": 450,
}


def _vertices_down_from_top():
    geometry = default_registry.geometry("railway_u_girder")(**DEFAULT_PARAMS)
    depth = DEFAULT_PARAMS["depth_mm"]
    return [(round(point.x, 6), round(depth / 2.0 - point.y, 6)) for point in geometry.outer_polygon]


def test_railway_u_girder_preset_is_available_for_bridge_beam_girder() -> None:
    preset = preset_by_key("railway_u_girder")

    assert preset["display_name"] == "Railway U-Girder"
    assert preset["category"] == "General / Non-composite Girder"
    assert preset["generator"] == "railway_u_girder"
    parameter_names = [parameter["name"] for parameter in preset["parameters"]]
    parameter_labels = [parameter["label"] for parameter in preset["parameters"]]
    assert parameter_names == [
        "width_mm",
        "depth_mm",
        "top_wall_width_mm",
        "bottom_side_width_mm",
        "haunch_x_mm",
        "haunch_y_mm",
        "h1_step_height_mm",
        "h2_bottom_opening_mm",
        "h3_floor_side_thickness_mm",
        "h4_floor_center_thickness_mm",
    ]
    assert "Haunch X (mm)" in parameter_labels
    assert "Haunch Y (mm)" in parameter_labels
    assert "h1 Step from bottom (mm)" in parameter_labels
    assert "h2 Bottom recess (mm)" in parameter_labels
    assert "h3 Side floor thk (mm)" in parameter_labels
    assert "h4 Center floor thk (mm)" in parameter_labels
    assert _preset_matches_member_type(preset, AnalysisModeSettings(member_type="beam_girder")) is True


def test_railway_u_girder_default_geometry_matches_user_drawing_dimensions() -> None:
    geometry = default_registry.geometry("railway_u_girder")(**DEFAULT_PARAMS)
    validation = validate_section_geometry(geometry)
    summary = summarize_geometry(geometry)

    assert validation.is_valid, validation.errors
    assert len(geometry.holes) == 0
    assert geometry.metadata["preset"] == "railway_u_girder"
    assert geometry.metadata["derived_details"] == {
        "outside_notch_mm": pytest.approx(50.0),
        "outside_step_y_from_top_mm": pytest.approx(930.0),
        "chamfer_mm": pytest.approx(25.0),
        "inner_half_width_mm": pytest.approx(2100.0),
        "haunch_start_y_from_top_mm": pytest.approx(600.0),
        "floor_side_top_y_from_top_mm": pytest.approx(900.0),
        "floor_center_top_y_from_top_mm": pytest.approx(845.0),
        "floor_underside_y_from_top_mm": pytest.approx(1295.0),
    }
    assert summary.x_min_mm == pytest.approx(-2750.0)
    assert summary.x_max_mm == pytest.approx(2750.0)
    assert summary.y_min_mm == pytest.approx(-800.0)
    assert summary.y_max_mm == pytest.approx(800.0)
    assert summary.area_mm2 == pytest.approx(3_833_125.0)
    assert summary.centroid_x_mm == pytest.approx(0.0, abs=1e-9)
    assert summary.centroid_y_from_top_mm == pytest.approx(939.1259851078863)


def test_railway_u_girder_vertices_include_notches_chamfers_and_haunches() -> None:
    assert _vertices_down_from_top() == [
        (-2675.0, 0.0),
        (-2125.0, 0.0),
        (-2100.0, 25.0),
        (-2100.0, 600.0),
        (-1800.0, 900.0),
        (0.0, 845.0),
        (1800.0, 900.0),
        (2100.0, 600.0),
        (2100.0, 25.0),
        (2125.0, 0.0),
        (2675.0, 0.0),
        (2700.0, 25.0),
        (2700.0, 930.0),
        (2750.0, 930.0),
        (2750.0, 1575.0),
        (2725.0, 1600.0),
        (2100.0, 1600.0),
        (2100.0, 1295.0),
        (-2100.0, 1295.0),
        (-2100.0, 1600.0),
        (-2725.0, 1600.0),
        (-2750.0, 1575.0),
        (-2750.0, 930.0),
        (-2700.0, 930.0),
        (-2700.0, 25.0),
    ]


def test_railway_u_girder_dimension_guides_show_drawing_and_derived_values() -> None:
    dimensions = default_registry.dimensions("railway_u_girder")(**DEFAULT_PARAMS)
    values_by_symbol = {dimension.symbol: dimension.value_mm for dimension in dimensions}

    assert values_by_symbol["B"] == pytest.approx(5500.0)
    assert values_by_symbol["B/2 L"] == pytest.approx(2750.0)
    assert values_by_symbol["B/2 R"] == pytest.approx(2750.0)
    assert values_by_symbol["t_wall_top"] == pytest.approx(600.0)
    assert values_by_symbol["clear_half"] == pytest.approx(2100.0)
    assert values_by_symbol["H"] == pytest.approx(1600.0)
    assert values_by_symbol["h1"] == pytest.approx(670.0)
    assert values_by_symbol["h2"] == pytest.approx(305.0)
    assert values_by_symbol["h3"] == pytest.approx(395.0)
    assert values_by_symbol["h4"] == pytest.approx(450.0)
    assert values_by_symbol["hx"] == pytest.approx(300.0)
    assert values_by_symbol["hy"] == pytest.approx(300.0)
    assert values_by_symbol["bottom_leg"] == pytest.approx(650.0)
    assert values_by_symbol["notch"] == pytest.approx(50.0)
    assert values_by_symbol["CL"] is None




def test_railway_u_girder_haunch_dimension_labels_are_separated() -> None:
    dimensions = default_registry.dimensions("railway_u_girder")(**DEFAULT_PARAMS)
    by_symbol = {dimension.symbol: dimension for dimension in dimensions}

    hx = by_symbol["hx"]
    hy = by_symbol["hy"]

    # hx and hy are intentionally annotated on opposite haunches so the small
    # labels do not overlap or visually truncate as "hx = 30 hy = 300 mm".
    assert hx.text_position.x < 0.0
    assert hy.text_position.x > 0.0
    assert abs(hx.text_position.x - hy.text_position.x) > 3500.0
    assert hx.display_label() == "hx = 300 mm"
    assert hy.display_label() == "hy = 300 mm"

def test_railway_u_girder_h1_to_h4_and_haunch_xy_drive_geometry() -> None:
    params = dict(DEFAULT_PARAMS)
    params.update(
        {
            "haunch_x_mm": 360,
            "haunch_y_mm": 260,
            "h1_step_height_mm": 700,
            "h2_bottom_opening_mm": 330,
            "h3_floor_side_thickness_mm": 420,
            "h4_floor_center_thickness_mm": 500,
        }
    )

    geometry = default_registry.geometry("railway_u_girder")(**params)
    depth = params["depth_mm"]
    vertices = [(round(point.x, 6), round(depth / 2.0 - point.y, 6)) for point in geometry.outer_polygon]
    details = geometry.metadata["derived_details"]

    assert details["outside_step_y_from_top_mm"] == pytest.approx(900.0)
    assert details["floor_underside_y_from_top_mm"] == pytest.approx(1270.0)
    assert details["floor_side_top_y_from_top_mm"] == pytest.approx(850.0)
    assert details["floor_center_top_y_from_top_mm"] == pytest.approx(770.0)
    assert details["haunch_start_y_from_top_mm"] == pytest.approx(590.0)
    assert (-1740.0, 850.0) in vertices
    assert (1740.0, 850.0) in vertices
    assert (-2100.0, 590.0) in vertices
    assert (2100.0, 590.0) in vertices


def test_railway_u_girder_rejects_invalid_notch_relationship() -> None:
    params = dict(DEFAULT_PARAMS)
    params["top_wall_width_mm"] = 650

    with pytest.raises(ValueError, match="top wall width must be less than bottom side width"):
        default_registry.geometry("railway_u_girder")(**params)
