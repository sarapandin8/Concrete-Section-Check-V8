from __future__ import annotations

import pandas as pd

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.concrete_materials import c45_precast_material
from concrete_pmm_pro.core.models import LoadCase, RebarMaterial
from concrete_pmm_pro.core.reinforcement_system import (
    ORDINARY_REBAR_FLAG_KEY,
    PRESTRESSING_STEEL_FLAG_KEY,
    default_section_reinforcement_flags,
)
from concrete_pmm_pro.geometry.generators import rectangle
from concrete_pmm_pro.io.project_io import (
    ANALYSIS_RESULTS_METADATA_KEY,
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)
from concrete_pmm_pro.serviceability.models import ServiceabilitySettings, ServiceabilitySummary
from concrete_pmm_pro.state.dirty_state import ANALYSIS_STATUS_KEY, input_group_hashes


def _beam_session() -> dict[str, object]:
    return {
        "project_name": "Cached girder",
        "design_code": "AASHTO LRFD",
        "code_edition": "AASHTO LRFD 9th Edition",
        "section_preset_key": "railway_u_girder",
        "section_preset_name": "Railway U-Girder",
        "section_category": "Precast Composite Girder",
        "girder_section_family": "precast_composite_girder",
        "section_parameters": {"B_mm": 5500.0, "H_mm": 1600.0},
        "section_geometry": rectangle(width_mm=5500.0, height_mm=1600.0),
        "concrete_material": c45_precast_material(),
        "rebar_materials": [RebarMaterial(name="SD40", fy_MPa=400.0, Es_MPa=200000.0)],
        "load_cases": [LoadCase(name="Strength I", Pu_N=0.0, Mux_Nmm=100_000_000.0, Muy_Nmm=0.0)],
        "analysis_mode_settings": AnalysisModeSettings(member_type="beam_girder"),
        ORDINARY_REBAR_FLAG_KEY: True,
        PRESTRESSING_STEEL_FLAG_KEY: True,
        "reinforcement_flags_preset_key": "railway_u_girder",
    }


def test_bridge_beam_girder_defaults_keep_ordinary_rebar_and_prestress_active() -> None:
    rebar, prestress = default_section_reinforcement_flags(
        member_type="beam_girder",
        section_category="Precast Composite Girder",
        section_preset_key="railway_u_girder",
        girder_section_family="precast_composite_girder",
    )

    assert rebar is True
    assert prestress is True


def test_steel_system_flags_are_dirty_state_inputs() -> None:
    groups = input_group_hashes(_beam_session())

    assert "section_has_ordinary_rebar" in __import__("concrete_pmm_pro.state.dirty_state", fromlist=["INPUT_GROUP_KEYS"]).INPUT_GROUP_KEYS["Section"]
    assert "section_has_prestressing_steel" in __import__("concrete_pmm_pro.state.dirty_state", fromlist=["INPUT_GROUP_KEYS"]).INPUT_GROUP_KEYS["Section"]
    assert groups["Section"]


def test_project_save_load_restores_beam_uls_cached_tables() -> None:
    session = _beam_session()
    session["_beam_girder_uls_manual_calculation_cache"] = {
        "Flexure": {
            "input_hash": "beam-flexure-hash",
            "check": "Flexure",
            "calculated_at": "2026-06-22 10:00:00",
            "flexure_preview_df": pd.DataFrame(
                [
                    {
                        "Status": "PASS",
                        "Case": "Strength I",
                        "Governing x": "5.000 m",
                        "Demand": "3,805.24 kN-m",
                        "Capacity": "φMn = 15,427.74 kN-m",
                        "Utilization": "0.247",
                        "Utilization value": 0.247,
                    }
                ]
            ),
        }
    }

    project = project_from_session_state(session)
    assert ANALYSIS_RESULTS_METADATA_KEY in project.metadata
    json_text = project_to_json(project)
    restored: dict[str, object] = {}

    apply_project_to_session_state(project_from_json(json_text), restored)

    cache = restored.get("_beam_girder_uls_manual_calculation_cache")
    assert isinstance(cache, dict)
    assert "Flexure" in cache
    restored_df = cache["Flexure"]["flexure_preview_df"]
    assert isinstance(restored_df, pd.DataFrame)
    assert restored_df.iloc[0]["Status"] == "PASS"
    assert restored[ANALYSIS_STATUS_KEY] == "Current"


def test_project_save_load_restores_sls_summary_cache() -> None:
    session = _beam_session()
    session["serviceability_summary"] = ServiceabilitySummary(
        enabled=True,
        settings=ServiceabilitySettings(enabled=True),
        section_properties=None,
        overall_status="PASS",
        governing_combo="SLS-01",
        governing_point="Top fiber",
        max_utilization=0.52,
    )
    session["serviceability_summary_hash"] = "sls-hash-1"
    session["serviceability_runtime_cache_status"] = "Recalculated"

    project = project_from_session_state(session)
    assert ANALYSIS_RESULTS_METADATA_KEY in project.metadata
    restored: dict[str, object] = {}

    apply_project_to_session_state(project_from_json(project_to_json(project)), restored)

    summary = restored.get("serviceability_summary")
    assert isinstance(summary, ServiceabilitySummary)
    assert summary.overall_status == "PASS"
    assert summary.governing_combo == "SLS-01"
    assert restored["serviceability_summary_hash"] == "sls-hash-1"
    assert restored[ANALYSIS_STATUS_KEY] == "Current"
