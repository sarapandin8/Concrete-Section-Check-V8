from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.models import ConcreteMaterial
from concrete_pmm_pro.geometry.generators import railway_u_girder
from concrete_pmm_pro.io.project_io import (
    RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY,
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)
from concrete_pmm_pro.serviceability.girder_prestress_station import (
    evaluate_girder_prestress_station,
    girder_station_participation_dataframe,
)
from concrete_pmm_pro.serviceability.girder_sls_load_components import BEAM_GIRDER_SYSTEM_SETTINGS_KEY
from concrete_pmm_pro.ui import analysis_page
from concrete_pmm_pro.ui.prestress_page import (
    _normalize_girder_strand_layout_table,
    _railway_u_girder_default_strand_layout_table,
)


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SOURCE = (ROOT / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
README_SOURCE = (ROOT / "README.md").read_text(encoding="utf-8")


def _railway_geometry():
    return railway_u_girder(
        width_mm=5500.0,
        depth_mm=1600.0,
        top_wall_width_mm=600.0,
        bottom_side_width_mm=650.0,
        haunch_x_mm=300.0,
        haunch_y_mm=300.0,
        h1_step_height_mm=670.0,
        h2_bottom_opening_mm=305.0,
        h3_floor_side_thickness_mm=395.0,
        h4_floor_center_thickness_mm=450.0,
    )


def _railway_section_parameters() -> dict[str, float]:
    return {
        "width_mm": 5500.0,
        "depth_mm": 1600.0,
        "top_wall_width_mm": 600.0,
        "bottom_side_width_mm": 650.0,
        "haunch_x_mm": 300.0,
        "haunch_y_mm": 300.0,
        "h1_step_height_mm": 670.0,
        "h2_bottom_opening_mm": 305.0,
        "h3_floor_side_thickness_mm": 395.0,
        "h4_floor_center_thickness_mm": 450.0,
    }


def _stage_settings() -> dict[str, object]:
    return {
        "web_fc_MPa": 45.0,
        "web_fci_MPa": 36.0,
        "slab_fc_MPa": 35.0,
        "concrete_unit_weight_kN_m3": 24.0,
        "support_condition": "Simply supported",
        "construction_method": "Case B - wet slab carried by precast webs",
        "wet_slab_distribution_each_web": 0.50,
        "formwork_construction_load_kN_m2": 2.5,
        "lifting_point_ratio": 0.20,
        "lifting_impact_factor": 1.10,
    }


def _railway_strand_table_with_symmetric_debonding() -> pd.DataFrame:
    geometry = _railway_geometry()
    raw = _railway_u_girder_default_strand_layout_table(geometry)
    raw.loc[raw["Group ID"] == "L Row 1", "Debonded strand nos"] = "1,9"
    raw.loc[raw["Group ID"] == "L Row 1", "Left debond m"] = 2.0
    raw.loc[raw["Group ID"] == "L Row 1", "Right debond m"] = 2.0
    raw.loc[raw["Group ID"] == "L Row 2", "Debonded strand nos"] = "1,9"
    raw.loc[raw["Group ID"] == "L Row 2", "Left debond m"] = 1.5
    raw.loc[raw["Group ID"] == "L Row 2", "Right debond m"] = 1.5
    return _normalize_girder_strand_layout_table(
        raw,
        span_length_m=10.0,
        debond_model="Symmetric left/right",
        geometry=geometry,
    )


def test_qa_rail_ugirder1_save_load_preserves_full_workflow_contract() -> None:
    """Protect the Railway U-Girder geometry/material/assembly/strand/stage handoff.

    This catches the high-risk regression mode where the UI still renders but a
    saved project silently loses the rail-specific assembly, debonding, or stage
    material routing metadata after reload.
    """

    geometry = _railway_geometry()
    strand_table = _railway_strand_table_with_symmetric_debonding()
    session_state = {
        "project_name": "QA.RAIL.UGIRDER1 regression fixture",
        "design_code": "ACI 318",
        "section_preset_key": "railway_u_girder",
        "section_preset_name": "Railway U-Girder",
        "section_parameters": _railway_section_parameters(),
        "section_geometry": geometry,
        "concrete_material": ConcreteMaterial(name="C45_PRECAST_WEB", fc_MPa=45.0, density_kg_m3=2400.0),
        "concrete_materials": [
            ConcreteMaterial(name="C45_PRECAST_WEB", fc_MPa=45.0, density_kg_m3=2400.0),
            ConcreteMaterial(name="C35_CIP_SLAB", fc_MPa=35.0, density_kg_m3=2400.0),
        ],
        "active_concrete_material_name": "C45_PRECAST_WEB",
        "deck_topping_material_name": "C35_CIP_SLAB",
        "analysis_mode_settings": AnalysisModeSettings(member_type="beam_girder"),
        BEAM_GIRDER_SYSTEM_SETTINGS_KEY: {
            "span_length_m": 10.0,
            "girder_spacing_m": 5.5,
            "number_of_girders": 1,
            "concrete_unit_weight_kN_m3": 24.0,
            "tributary_width_m": 5.5,
            "use_girder_spacing_as_tributary_width": False,
        },
        "girder_prestress_system_settings": {
            "girder_system": "Railway U-Girder",
            "prestress_type": "Pretensioned strand",
            "span_length_m": 10.0,
            "station_convention": "x from left support",
            "debond_model": "Symmetric left/right",
        },
        RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY: _stage_settings(),
        "girder_strand_layout_table": strand_table,
    }

    saved_project = project_from_session_state(session_state)
    reloaded_project = project_from_json(project_to_json(saved_project))
    restored_state: dict[str, object] = {}
    apply_project_to_session_state(reloaded_project, restored_state)

    assert restored_state["section_preset_key"] == "railway_u_girder"
    assert restored_state["section_preset_name"] == "Railway U-Girder"
    assert restored_state["section_geometry"].metadata["preset"] == "railway_u_girder"
    assert restored_state["section_parameters"]["width_mm"] == pytest.approx(5500.0)
    assert restored_state["section_parameters"]["h4_floor_center_thickness_mm"] == pytest.approx(450.0)

    stage = restored_state[RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY]
    assert stage["web_fc_MPa"] == pytest.approx(45.0)
    assert stage["web_fci_MPa"] == pytest.approx(36.0)
    assert stage["slab_fc_MPa"] == pytest.approx(35.0)
    assert stage["construction_method"] == "Case B - wet slab carried by precast webs"
    assert stage["lifting_point_ratio"] == pytest.approx(0.20)
    assert stage["lifting_impact_factor"] == pytest.approx(1.10)

    system = restored_state[BEAM_GIRDER_SYSTEM_SETTINGS_KEY]
    assert system["span_length_m"] == pytest.approx(10.0)
    assert restored_state["girder_prestress_system_settings"]["span_length_m"] == pytest.approx(10.0)
    assert restored_state["railway_u_girder_girder_length_mm"] == pytest.approx(10000.0)

    restored_strands = restored_state["girder_strand_layout_table"]
    assert isinstance(restored_strands, pd.DataFrame)
    assert len(restored_strands.index) == 10
    assert int(restored_strands["No. Strands"].sum()) == 72
    l1 = restored_strands.loc[restored_strands["Group ID"] == "L Row 1"].iloc[0]
    r1 = restored_strands.loc[restored_strands["Group ID"] == "R Row 1"].iloc[0]
    assert l1["Debonded strand nos"] == r1["Debonded strand nos"] == "1,9"
    assert float(l1["Left debond m"]) == pytest.approx(2.0)
    assert float(r1["Right debond m"]) == pytest.approx(2.0)
    assert "Railway U-Girder symmetric mode" in str(r1["Note"])


def test_qa_rail_ugirder1_symmetric_debonding_station_participation_is_consistent() -> None:
    table = _railway_strand_table_with_symmetric_debonding()

    support = evaluate_girder_prestress_station(table, x_m=0.0, span_length_m=10.0)
    midspan = evaluate_girder_prestress_station(table, x_m=5.0, span_length_m=10.0)
    right_sleeve = evaluate_girder_prestress_station(table, x_m=9.5, span_length_m=10.0)

    # L/R Row 1 and L/R Row 2 each have two selected strands debonded near the ends:
    # total strand reduction at x=0 and x=9.5 is 8 strands, while midspan is fully effective.
    assert support.effective_strands == 64
    assert midspan.effective_strands == 72
    assert right_sleeve.effective_strands == 64

    participation = girder_station_participation_dataframe(table, span_length_m=10.0, stations_m=[0.0, 1.5, 5.0, 9.5])
    at_support = participation.loc[participation["x_m"] == 0.0]
    for group_id in ["L Row 1", "R Row 1", "L Row 2", "R Row 2"]:
        row = at_support.loc[at_support["Group ID"] == group_id].iloc[0]
        assert int(row["Ineffective strands"]) == 2
        assert bool(row["Left sleeve active"]) is True
        assert "selected debonded strands excluded" in row["Participation note"]

    at_midspan = participation.loc[participation["x_m"] == 5.0]
    assert int(at_midspan["Effective strands"].sum()) == 72
    assert int(at_midspan["Ineffective strands"].sum()) == 0


def test_qa_rail_ugirder1_source_and_docs_keep_guarded_review_language() -> None:
    assert "SLS.RAIL.UGIRDER8.RECOVERY" in README_SOURCE
    assert "not change stress equations" in README_SOURCE
    assert "final code-certified" not in README_SOURCE.split("### SLS.RAIL.UGIRDER8.RECOVERY", 1)[0]

    assert "Transfer stage" in ANALYSIS_SOURCE
    assert "Lifting stage" in ANALYSIS_SOURCE
    assert "Construction stage" in ANALYSIS_SOURCE
    assert "Service stage" in ANALYSIS_SOURCE
    assert "default_method = \"Engineer-confirmed bonded auxiliary reinforcement\"" in ANALYSIS_SOURCE
    assert "Top web fiber" in ANALYSIS_SOURCE
    assert "CIP slab bottom fiber" in ANALYSIS_SOURCE


def test_qa_rail_ugirder1_visible_transfer_guide_still_routes_to_web_fci() -> None:
    backup = dict(analysis_page.st.session_state)
    analysis_page.st.session_state.clear()
    analysis_page.st.session_state.update(
        {
            "section_preset_key": "railway_u_girder",
            "section_preset_name": "Railway U-Girder",
            "section_geometry": _railway_geometry(),
            "concrete_material": ConcreteMaterial(name="C45_PRECAST_WEB", fc_MPa=45.0, density_kg_m3=2400.0),
            RAILWAY_U_GIRDER_STAGE_SETTINGS_KEY: _stage_settings(),
        }
    )
    try:
        transfer = analysis_page._stage_material_strength_values_for_sls_limit_preview("Transfer / Release")
        lifting = analysis_page._stage_material_strength_values_for_sls_limit_preview("Lifting stage")
        service = analysis_page._stage_material_strength_values_for_sls_limit_preview("Service stage")

        assert transfer["strength_MPa"] == pytest.approx(36.0)
        assert transfer["strength_label"] == "web f'ci at transfer / release"
        assert "not web final f'c = 45.000 MPa" in str(transfer["audit_note"])
        assert lifting["strength_MPa"] == pytest.approx(36.0)
        assert service["strength_MPa"] == pytest.approx(45.0)
        assert "CIP slab f'c = 35.000 MPa" in str(service["audit_note"])
    finally:
        analysis_page.st.session_state.clear()
        analysis_page.st.session_state.update(backup)
