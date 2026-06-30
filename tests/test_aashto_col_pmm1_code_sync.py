from __future__ import annotations

from concrete_pmm_pro.analysis.preflight import build_analysis_input_from_session_state
from concrete_pmm_pro.core.analysis import AnalysisModeSettings, AnalysisSettings
from concrete_pmm_pro.core.models import ConcreteMaterial, LoadCase, Rebar, RebarMaterial
from concrete_pmm_pro.geometry.generators import rectangle


def test_preflight_forces_analysis_settings_code_to_project_aashto_when_stale_aci() -> None:
    state = {
        "design_code": "AASHTO LRFD",
        "code_edition": "AASHTO LRFD 9th Edition",
        "analysis_mode_settings": AnalysisModeSettings(member_type="column_pier_pmm"),
        "analysis_settings": AnalysisSettings(code="ACI 318", neutral_axis_angle_steps=12, neutral_axis_depth_steps=10),
        "section_geometry": rectangle(width_mm=400.0, height_mm=600.0),
        "concrete_material": ConcreteMaterial(name="C40", fc_MPa=40.0),
        "rebar_materials": [RebarMaterial(name="SD40", fy_MPa=420.0, Es_MPa=200000.0)],
        "rebars": [
            Rebar(x_mm=-150.0, y_mm=-250.0, diameter_mm=25.0, material_name="SD40"),
            Rebar(x_mm=150.0, y_mm=250.0, diameter_mm=25.0, material_name="SD40"),
        ],
        "prestress_materials": [],
        "prestress_elements": [],
        "load_cases": [LoadCase(name="ULS", Pu_N=1000.0, Mux_Nmm=1_000_000.0, Muy_Nmm=0.0, load_type="ULS", active=True)],
    }

    analysis_input = build_analysis_input_from_session_state(state)

    assert analysis_input is not None
    assert analysis_input.settings.code == "AASHTO LRFD"


def test_analysis_page_source_syncs_code_before_rendering_cached_results() -> None:
    from pathlib import Path

    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
    assert "def _sync_analysis_settings_code_to_project" in source
    assert "_sync_analysis_settings_code_to_project()" in source
    assert 'st.session_state["analysis_settings"] = raw_settings.model_copy(update={"code": project_code})' in source
    assert '"rc_pmm_result"' in source
    assert "Cached PMM result was cleared" in source
