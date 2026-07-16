from __future__ import annotations

import json
from pathlib import Path

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.analysis_modes import analysis_mode_label, is_portal_frame_crossbeam_workflow
from concrete_pmm_pro.core.design_code import allowed_project_design_codes_for_workflow, default_project_design_code_for_workflow
from concrete_pmm_pro.core.reinforcement_system import default_section_reinforcement_flags
from concrete_pmm_pro.crossbeam.workflow import (
    DEFAULT_FPJ_RATIO,
    DEFAULT_STRAND_APS_MM2,
    DEFAULT_STRAND_FPU_MPA,
    calculated_fpj_mpa,
    default_crossbeam_tendon_rows,
    tendon_eccentricity_from_top_mm,
)
from concrete_pmm_pro.geometry.generators import (
    crossbeam_rectangular_hollow_bottom_fillets_inner_chamfers,
    crossbeam_rectangular_solid_bottom_fillets,
)
from concrete_pmm_pro.geometry.summary import summarize_geometry


def test_portal_crossbeam_workflow_routes_to_aci_only() -> None:
    settings = AnalysisModeSettings(member_type="portal_frame_crossbeam")
    assert is_portal_frame_crossbeam_workflow(settings)
    assert analysis_mode_label(settings) == "Portal Frame Crossbeam — Prestressed Concrete"
    assert settings.analysis_workflow == "portal_frame_crossbeam"
    assert settings.allow_pmm_workflow is False
    assert settings.allow_sls_workflow is False
    assert allowed_project_design_codes_for_workflow("portal_frame_crossbeam") == ("ACI 318",)
    assert default_project_design_code_for_workflow("portal_frame_crossbeam", "AASHTO LRFD") == "ACI 318"


def test_crossbeam_presets_are_workflow_scoped() -> None:
    presets = json.loads(Path("data/section_presets.json").read_text())["presets"]
    crossbeam = [preset for preset in presets if "portal_frame_crossbeam" in preset.get("allowed_workflows", [])]
    keys = {preset["key"] for preset in crossbeam}
    assert keys == {
        "crossbeam_rectangular_solid_bottom_fillets",
        "crossbeam_rectangular_hollow_bottom_fillets_inner_chamfers",
    }
    for preset in crossbeam:
        assert preset["category"] == "Portal Frame Crossbeam"


def test_crossbeam_section_generators_use_bottom_fillets_and_wall_thickness_void() -> None:
    solid = crossbeam_rectangular_solid_bottom_fillets(2500, 1500, bottom_fillet_radius_mm=200)
    assert solid.metadata["crossbeam_section_role"] == "Solid"
    assert not solid.holes
    assert len(solid.outer_polygon) > 4

    hollow = crossbeam_rectangular_hollow_bottom_fillets_inner_chamfers(
        2500,
        1500,
        t_top_mm=300,
        t_bottom_mm=350,
        t_left_mm=300,
        t_right_mm=400,
        bottom_fillet_radius_mm=200,
        inner_chamfer_mm=150,
    )
    assert hollow.metadata["crossbeam_section_role"] == "Hollow"
    assert len(hollow.holes) == 1
    assert hollow.metadata["opening_width_mm"] == 1800
    assert hollow.metadata["opening_height_mm"] == 850
    summary = summarize_geometry(hollow)
    assert summary.area_mm2 > 0
    assert summary.centroid_y_from_bottom_mm > 0


def test_crossbeam_tendon_defaults_and_top_reference_eccentricity() -> None:
    assert DEFAULT_STRAND_FPU_MPA == 1860.0
    assert DEFAULT_STRAND_APS_MM2 == 140.0
    assert DEFAULT_FPJ_RATIO == 0.75
    assert calculated_fpj_mpa() == 1395.0
    assert tendon_eccentricity_from_top_mm(900, total_depth_mm=1500, centroid_y_from_bottom_mm=650) == 50
    rows = default_crossbeam_tendon_rows(30.0, tendon_count=3, section_depth_mm=1500)
    assert len(rows) == 9
    assert {row["Jacking end"] for row in rows} == {"Both"}
    assert {row["Type"] for row in rows} == {"Internal"}


def test_crossbeam_rebar_and_prestress_default_on() -> None:
    assert default_section_reinforcement_flags(
        member_type="portal_frame_crossbeam",
        section_category="Portal Frame Crossbeam",
        section_preset_key="crossbeam_rectangular_hollow_bottom_fillets_inner_chamfers",
    ) == (True, True)
