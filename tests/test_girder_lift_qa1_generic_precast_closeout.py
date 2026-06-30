from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.serviceability.girder_sls_load_components import (
    BeamGirderSLSAutoLoadSettings,
    BeamGirderSystemSettings,
    BuildingBeamGirderServiceLoadSettings,
    auto_load_breakdown_for_stage,
    building_auto_load_breakdown_for_stage,
    default_sls_station_grid,
    two_point_lifting_moment_kNm,
    two_point_lifting_shear_kN,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
SECTION_BUILDER_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "section_builder.py").read_text(encoding="utf-8")


def test_girder_lift_qa1_generic_precast_preset_family_is_routed_but_railway_is_excluded() -> None:
    assert "def _is_generic_precast_lifting_active_for_sls()" in ANALYSIS_SOURCE
    for preset_key in (
        "parametric_i_girder",
        "box_section_fillet",
        "precast_box_beam_exterior",
        "parametric_plank_girder_interior",
        "parametric_plank_girder_exterior",
        "parametric_plank_girder_voided_interior",
        "parametric_plank_girder_voided_exterior",
    ):
        assert preset_key in ANALYSIS_SOURCE

    assert "Railway U-Girder remains routed through its dedicated rail-specific lifting" in ANALYSIS_SOURCE
    assert "if _is_railway_u_girder_active_for_sls_material_routing():\n        return False" in ANALYSIS_SOURCE
    assert "Railway U-Girder temporary two-point lifting" in ANALYSIS_SOURCE
    assert "Generic precast lifting: individual precast unit" in ANALYSIS_SOURCE


def test_girder_lift_qa1_generic_lifting_load_basis_excludes_deck_service_and_assembly_loads() -> None:
    system = BeamGirderSystemSettings(
        span_length_m=24.0,
        number_of_girders=6,
        girder_spacing_m=2.50,
        tributary_width_m=3.00,
        concrete_unit_weight_kN_m3=24.0,
        lifting_point_ratio=0.18,
        lifting_impact_factor=1.15,
    )
    bridge_settings = BeamGirderSLSAutoLoadSettings(
        include_construction_wet_topping=True,
        include_service_barrier_sidewalk=True,
        include_service_wearing_surface=True,
        include_service_other_sdl=True,
        other_sdl_area_load_kN_m2=8.0,
    )
    bridge_lift = auto_load_breakdown_for_stage(
        stage_label="Lifting stage",
        system=system,
        settings=bridge_settings,
        precast_area_mm2=620_000.0,
        topping_thickness_mm=220.0,
    )

    assert bridge_lift.component_loads_kN_m == (("Precast unit self-weight × lifting IF", pytest.approx(0.620 * 24.0 * 1.15)),)
    assert "Wet" not in bridge_lift.component_label
    assert "Barrier" not in bridge_lift.component_label
    assert "Wearing" not in bridge_lift.component_label
    assert "Other SDL" not in bridge_lift.component_label

    building_lift = building_auto_load_breakdown_for_stage(
        stage_label="Lifting stage",
        system=system,
        service_settings=BuildingBeamGirderServiceLoadSettings(
            include_service_sdl=True,
            service_sdl_kN_m2=4.0,
            include_service_ll=True,
            service_ll_kN_m2=6.0,
            include_additional_sdl=True,
            additional_sdl_kN_m2=3.0,
        ),
        precast_area_mm2=620_000.0,
        topping_thickness_mm=220.0,
    )
    assert building_lift.component_loads_kN_m == bridge_lift.component_loads_kN_m
    assert "Building SDL" not in building_lift.component_label
    assert "Building LL" not in building_lift.component_label
    assert "Additional SDL" not in building_lift.component_label


def test_girder_lift_qa1_two_point_lifting_diagram_has_negative_overhang_and_positive_midspan() -> None:
    span = 24.0
    ratio = 0.20
    w = 14.0
    a = span * ratio
    stations = default_sls_station_grid(span, extra_stations_m=[a, span - a], divisions=24)

    assert round(a, 6) in stations
    assert round(span - a, 6) in stations
    assert two_point_lifting_moment_kNm(w, a, span, ratio) == pytest.approx(-w * a * a / 2.0)
    assert two_point_lifting_moment_kNm(w, span / 2.0, span, ratio) > 0.0
    assert abs(two_point_lifting_shear_kN(w, span / 2.0, span, ratio)) < w


def test_girder_lift_qa1_full_length_sls_preview_uses_lifting_moment_shear_and_transfer_pe() -> None:
    assert "if _beam_sls_stage_label_for_analysis(stage_label) == \"Lifting stage\":" in ANALYSIS_SOURCE
    assert "two_point_lifting_moment_kNm(" in ANALYSIS_SOURCE
    assert "two_point_lifting_shear_kN(" in ANALYSIS_SOURCE
    assert "a={lifting_a_m:.3f} m from each end, IF={system_settings.lifting_impact_factor:.2f}" in ANALYSIS_SOURCE
    assert "if normalized == \"Lifting stage\":\n        return float(getattr(station_result, \"pe_transfer_eff_kN\", 0.0) or 0.0)" in ANALYSIS_SOURCE


def test_girder_lift_qa1_section_builder_lifting_inputs_are_generic_not_rail_only() -> None:
    assert "Lifting a/L" in SECTION_BUILDER_SOURCE
    assert "Lifting impact factor" in SECTION_BUILDER_SOURCE
    assert "Individual precast unit" in SECTION_BUILDER_SOURCE
    assert "not bridge assembly" in SECTION_BUILDER_SOURCE


def test_girder_lift_qa1_analysis_station_grid_syncs_to_current_section_builder_lifting_points() -> None:
    assert "def _girder_sls_lifting_station_extras(span_length_m: float)" in ANALYSIS_SOURCE
    assert "railway_u_girder_stage_settings" in ANALYSIS_SOURCE
    assert "system.lifting_point_ratio" in ANALYSIS_SOURCE
    assert "extra.extend(_girder_sls_lifting_station_extras(span_length_m))" in ANALYSIS_SOURCE
    assert "grid = _girder_sls_auto_station_grid(span_length_m, stage_label=stage)" in ANALYSIS_SOURCE
    assert "if len(unique_stations) >= 2 and stage != \"Lifting stage\":" in ANALYSIS_SOURCE
    assert "span - a_m" in ANALYSIS_SOURCE
