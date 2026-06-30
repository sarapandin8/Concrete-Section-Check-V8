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
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
SECTION_BUILDER_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "section_builder.py").read_text(encoding="utf-8")


def test_qa_release2_generic_lifting_load_is_individual_precast_unit_only() -> None:
    system = BeamGirderSystemSettings(
        span_length_m=20.0,
        number_of_girders=8,
        girder_spacing_m=2.0,
        tributary_width_m=3.0,
        concrete_unit_weight_kN_m3=24.0,
        lifting_point_ratio=0.20,
        lifting_impact_factor=1.10,
    )
    settings = BeamGirderSLSAutoLoadSettings(
        include_construction_wet_topping=True,
        include_service_barrier_sidewalk=True,
        include_service_wearing_surface=True,
        include_service_other_sdl=True,
        other_sdl_area_load_kN_m2=5.0,
    )

    lifting = auto_load_breakdown_for_stage(
        stage_label="Lifting stage",
        system=system,
        settings=settings,
        precast_area_mm2=500_000.0,
        topping_thickness_mm=250.0,
    )

    assert lifting.component_loads_kN_m[0][0] == 'Precast unit self-weight × lifting IF'
    assert lifting.component_loads_kN_m[0][1] == pytest.approx(13.2)
    assert lifting.total_kN_m == pytest.approx(0.5 * 24.0 * 1.10)
    assert "Wet" not in lifting.component_label
    assert "Barrier" not in lifting.component_label
    assert "Wearing" not in lifting.component_label
    assert "Other SDL" not in lifting.component_label


def test_qa_release2_building_lifting_load_excludes_building_service_loads() -> None:
    system = BeamGirderSystemSettings(
        span_length_m=20.0,
        tributary_width_m=4.0,
        concrete_unit_weight_kN_m3=24.0,
        lifting_point_ratio=0.10,
        lifting_impact_factor=1.25,
    )
    service = BuildingBeamGirderServiceLoadSettings(
        include_service_sdl=True,
        service_sdl_kN_m2=3.0,
        include_service_ll=True,
        service_ll_kN_m2=5.0,
        include_additional_sdl=True,
        additional_sdl_kN_m2=2.0,
    )

    lifting = building_auto_load_breakdown_for_stage(
        stage_label="Lifting stage",
        system=system,
        service_settings=service,
        precast_area_mm2=400_000.0,
        topping_thickness_mm=150.0,
    )

    assert lifting.component_loads_kN_m[0][0] == 'Precast unit self-weight × lifting IF'
    assert lifting.component_loads_kN_m[0][1] == pytest.approx(12.0)
    assert lifting.total_kN_m == pytest.approx(0.4 * 24.0 * 1.25)
    assert "Building SDL" not in lifting.component_label
    assert "Building LL" not in lifting.component_label
    assert "Additional SDL" not in lifting.component_label


def test_qa_release2_lifting_station_grid_keeps_lifting_points_for_plots() -> None:
    span = 20.0
    for ratio in (0.05, 0.10, 0.20, 0.45):
        a = span * ratio
        grid = default_sls_station_grid(span, extra_stations_m=[a, span - a], divisions=20)
        assert 0.0 in grid
        assert span in grid
        assert round(a, 6) in grid
        assert round(span - a, 6) in grid


def test_qa_release2_two_point_lifting_moment_moves_with_lifting_ratio() -> None:
    w = 12.0
    span = 20.0

    m_at_2_for_ratio_010 = two_point_lifting_moment_kNm(w, 2.0, span, 0.10)
    m_at_4_for_ratio_020 = two_point_lifting_moment_kNm(w, 4.0, span, 0.20)
    m_mid_ratio_010 = two_point_lifting_moment_kNm(w, 10.0, span, 0.10)
    m_mid_ratio_020 = two_point_lifting_moment_kNm(w, 10.0, span, 0.20)

    assert m_at_2_for_ratio_010 == pytest.approx(-w * 2.0 * 2.0 / 2.0)
    assert m_at_4_for_ratio_020 == pytest.approx(-w * 4.0 * 4.0 / 2.0)
    assert m_mid_ratio_010 != pytest.approx(m_mid_ratio_020)


def test_qa_release2_analysis_ui_contains_lifting_regression_guards() -> None:
    assert '"Lifting stage"' in ANALYSIS_SOURCE
    assert "Generic precast lifting: individual precast unit" in ANALYSIS_SOURCE
    assert "Railway U-Girder temporary two-point lifting" in ANALYSIS_SOURCE
    assert "show_end_zone_controls=(stage_label == \"Transfer stage\")" in ANALYSIS_SOURCE
    assert "safe_stage = _beam_sls_stage_label_for_analysis(stage)" in ANALYSIS_SOURCE
    assert "aci_transfer_end_zone_length_basis_{safe_stage}" in ANALYSIS_SOURCE


def test_qa_release2_section_builder_exposes_lifting_inputs_without_rail_specific_labels() -> None:
    assert "Lifting a/L" in SECTION_BUILDER_SOURCE
    assert "Lifting impact factor" in SECTION_BUILDER_SOURCE
    assert "Individual precast unit" in SECTION_BUILDER_SOURCE
