from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.girder_construction_uls import (
    BEAM_GIRDER_CONSTRUCTION_ULS_SETTINGS_KEY,
    BeamGirderConstructionULSSettings,
    build_construction_uls_demand,
    construction_uls_station_rows,
)
from concrete_pmm_pro.core.project import ProjectModel
from concrete_pmm_pro.geometry.generators import rectangle
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_session_state, project_to_json
from concrete_pmm_pro.serviceability.girder_sls_load_components import BeamGirderSystemSettings
from concrete_pmm_pro.ui.analysis_page import (
    _beam_uls_girder_strand_elements_for_station,
    _beam_uls_is_precast_composite_bridge,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
LOADS_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "loads_page.py").read_text(encoding="utf-8")


def _strand_layout() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Active": True,
                "Group ID": "Bottom strands",
                "No. Strands": 4,
                "Area/Strand_mm2": 100.0,
                "Total Aps_mm2": 400.0,
                "y_mm_from_bottom": 50.0,
                "Pe_transfer/strand_kN": 150.0,
                "Pe_construction/strand_kN": 140.0,
                "Pe_eff_final/strand_kN": 120.0,
                "Left debond m": 0.0,
                "Right debond m": 0.0,
            }
        ]
    )


def test_construction_uls_auto_demand_builds_factored_simple_span_actions() -> None:
    system = BeamGirderSystemSettings(span_length_m=30.0, girder_spacing_m=2.0, tributary_width_m=2.0)
    settings = BeamGirderConstructionULSSettings(
        include_formwork=True,
        formwork_line_load_kN_m=2.0,
        include_construction_live_load=True,
        construction_live_load_kN_m=3.0,
        gamma_girder_self_weight=1.25,
        gamma_wet_deck=1.25,
        gamma_formwork=1.25,
        gamma_construction_live=1.50,
        factors_confirmed=True,
        factor_basis="Project construction strength factors",
    )
    demand = build_construction_uls_demand(
        system=system,
        settings=settings,
        precast_area_mm2=800_000.0,
        deck_thickness_mm=200.0,
    )

    # 0.8 m² × 24 = 19.2 kN/m; wet deck = 0.2 × 2.0 × 24 = 9.6 kN/m.
    assert demand.unfactored_total_kN_m == pytest.approx(19.2 + 9.6 + 2.0 + 3.0)
    assert demand.factored_total_kN_m == pytest.approx(19.2 * 1.25 + 9.6 * 1.25 + 2.0 * 1.25 + 3.0 * 1.50)
    assert demand.status == "READY"
    assert demand.acceptance_ready is True

    rows = construction_uls_station_rows(demand, extra_stations_m=[15.0], divisions=30)
    mid = next(row for row in rows if abs(float(row["Station x (m)"]) - 15.0) < 1e-9)
    w = demand.factored_total_kN_m
    assert mid["Mux"] == pytest.approx(w * 30.0**2 / 8.0)
    left = rows[0]
    assert left["Vuy"] == pytest.approx(w * 30.0 / 2.0)
    assert all(row["Case Name"] == "AUTO-CONSTRUCTION-ULS" for row in rows)


def test_construction_uls_factor_gate_keeps_unconfirmed_demand_in_review() -> None:
    demand = build_construction_uls_demand(
        system=BeamGirderSystemSettings(span_length_m=20.0, girder_spacing_m=1.8),
        settings=BeamGirderConstructionULSSettings(factors_confirmed=False),
        precast_area_mm2=700_000.0,
        deck_thickness_mm=200.0,
    )
    assert demand.status == "REVIEW"
    assert demand.acceptance_ready is False
    assert demand.factored_total_kN_m > 0.0
    assert any("not engineer-confirmed" in warning for warning in demand.warnings)


def test_shored_construction_is_blocked_from_simple_noncomposite_auto_route() -> None:
    demand = build_construction_uls_demand(
        system=BeamGirderSystemSettings(span_length_m=20.0, girder_spacing_m=1.8),
        settings=BeamGirderConstructionULSSettings(construction_support="Shored", factors_confirmed=True),
        precast_area_mm2=700_000.0,
        deck_thickness_mm=200.0,
    )
    assert demand.status == "BLOCKED"
    assert construction_uls_station_rows(demand) == []
    assert any("Shored construction" in warning for warning in demand.warnings)


def test_construction_flexure_uses_construction_effective_prestress_force_not_final_force() -> None:
    state = {"girder_strand_layout_table": _strand_layout()}
    geometry = rectangle(500.0, 1000.0)
    construction = _beam_uls_girder_strand_elements_for_station(
        state,
        geometry=geometry,
        x_m=5.0,
        span_length_m=10.0,
        prestress_force_stage="construction",
    )
    final = _beam_uls_girder_strand_elements_for_station(
        state,
        geometry=geometry,
        x_m=5.0,
        span_length_m=10.0,
        prestress_force_stage="final",
    )
    assert len(construction) == len(final) == 1
    assert construction[0].pe_eff_n == pytest.approx(140_000.0)
    assert final[0].pe_eff_n == pytest.approx(120_000.0)
    assert construction[0].initial_stress_mpa == pytest.approx(1400.0)
    assert final[0].initial_stress_mpa == pytest.approx(1200.0)


def test_project_io_preserves_construction_uls_settings() -> None:
    session = {
        BEAM_GIRDER_CONSTRUCTION_ULS_SETTINGS_KEY: {
            "construction_support": "Unshored",
            "include_formwork": True,
            "formwork_line_load_kN_m": 2.5,
            "gamma_girder_self_weight": 1.25,
            "gamma_wet_deck": 1.25,
            "gamma_formwork": 1.25,
            "gamma_construction_live": 1.50,
            "factor_basis": "Project construction factors",
            "factors_confirmed": True,
        }
    }
    project = project_from_session_state(session)
    raw = json.loads(project_to_json(project))
    saved = raw["metadata"][BEAM_GIRDER_CONSTRUCTION_ULS_SETTINGS_KEY]
    assert saved["formwork_line_load_kN_m"] == pytest.approx(2.5)
    assert saved["factors_confirmed"] is True

    restored: dict[str, object] = {}
    apply_project_to_session_state(ProjectModel.model_validate(raw), restored)
    assert restored[BEAM_GIRDER_CONSTRUCTION_ULS_SETTINGS_KEY]["gamma_wet_deck"] == pytest.approx(1.25)
    assert restored[BEAM_GIRDER_CONSTRUCTION_ULS_SETTINGS_KEY]["factor_basis"] == "Project construction factors"


def test_ui_stage_separates_construction_noncomposite_and_final_composite_flexure() -> None:
    assert "Construction ULS — Auto Demand · Noncomposite" in LOADS_SOURCE
    assert "Final Composite ULS — Imported FEA Demand" in LOADS_SOURCE
    assert "I have verified these Construction ULS factors for the project" in LOADS_SOURCE
    assert "Construction — Noncomposite" in ANALYSIS_SOURCE
    assert "Final — Composite" in ANALYSIS_SOURCE
    assert "Calculate Construction Flexure" in ANALYSIS_SOURCE
    assert 'prestress_force_stage="construction"' in ANALYSIS_SOURCE


def test_final_composite_flexure_does_not_reuse_precast_only_capacity_and_keeps_interface_gate() -> None:
    assert "Calculate Final Composite Flexure" in ANALYSIS_SOURCE
    assert "IGIRDER.ULS3A.composite-flexure-audit-closeout" in ANALYSIS_SOURCE
    assert "use_aashto_solver=True" in ANALYSIS_SOURCE
    assert "INTERFACE SHEAR PENDING" in ANALYSIS_SOURCE
    assert "Final effective prestress" in ANALYSIS_SOURCE


def test_igird_uls1_scope_is_isolated_to_parametric_i_girder_not_all_composite_capable_presets() -> None:
    assert _beam_uls_is_precast_composite_bridge(
        {"section_preset_key": "parametric_i_girder", "girder_section_family": "precast_composite_girder"},
        is_bridge=True,
    ) is True
    assert _beam_uls_is_precast_composite_bridge(
        {"section_preset_key": "u_girder", "girder_section_family": "precast_composite_girder"},
        is_bridge=True,
    ) is False
    assert _beam_uls_is_precast_composite_bridge(
        {"section_preset_key": "parametric_i_girder", "girder_section_family": "precast_composite_girder"},
        is_bridge=False,
    ) is False
    assert 'return preset_key == "parametric_i_girder"' in LOADS_SOURCE
    assert "U-/box-/plank" in ANALYSIS_SOURCE


def test_igird_project_save_drops_legacy_generic_flexure_cache_but_keeps_stage_owned_construction_cache() -> None:
    legacy_df = pd.DataFrame([{"Status": "PASS", "Demand": "100", "Capacity": "200", "Utilization": "0.5"}])
    construction_df = pd.DataFrame([{"Status": "PASS", "Demand": "80", "Capacity": "200", "Utilization": "0.4"}])
    session = {
        "section_preset_key": "parametric_i_girder",
        "_beam_girder_uls_manual_calculation_cache": {
            "Flexure": {"input_hash": "legacy", "flexure_preview_df": legacy_df},
            "Flexure — Construction": {"input_hash": "new", "flexure_preview_df": construction_df},
        },
    }
    raw = json.loads(project_to_json(project_from_session_state(session)))
    saved_cache = raw["metadata"]["analysis_results"]["beam_girder_uls_manual_calculation_cache"]
    assert "Flexure" not in saved_cache
    assert "Flexure — Construction" in saved_cache


def test_igird_project_restore_drops_legacy_generic_flexure_cache() -> None:
    session = {
        "section_preset_key": "parametric_i_girder",
        "_beam_girder_uls_manual_calculation_cache": {
            "Flexure": {"input_hash": "legacy", "flexure_preview_df": pd.DataFrame([{"Status": "PASS"}])},
            "Flexure — Construction": {"input_hash": "new", "flexure_preview_df": pd.DataFrame([{"Status": "PASS"}])},
        },
    }
    project = project_from_session_state(session)
    # Re-inject a legacy cache entry to emulate a D30-era project JSON.
    raw = json.loads(project_to_json(project))
    cache = raw["metadata"]["analysis_results"]["beam_girder_uls_manual_calculation_cache"]
    cache["Flexure"] = {
        "input_hash": "legacy",
        "flexure_preview_df": {"__type__": "dataframe", "columns": ["Status"], "records": [{"Status": "PASS"}]},
    }
    restored: dict[str, object] = {}
    apply_project_to_session_state(ProjectModel.model_validate(raw), restored)
    restored_cache = restored.get("_beam_girder_uls_manual_calculation_cache", {})
    assert isinstance(restored_cache, dict)
    assert "Flexure" not in restored_cache
    assert "Flexure — Construction" in restored_cache


def test_result_summary_source_suppresses_legacy_igird_generic_flexure_cache() -> None:
    app_source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    assert 'preset_key == "parametric_i_girder" and "Flexure" in cache' in app_source
    assert 'filtered.pop("Flexure", None)' in app_source
