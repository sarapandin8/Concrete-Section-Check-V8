from __future__ import annotations

from pathlib import Path

import pytest


def _install_streamlit_stub(monkeypatch):
    import sys
    import types

    # These tests replace Streamlit with a minimal stub. If prestress_page was
    # imported by an earlier test, remove it so its module-level `st` reference
    # is rebound to the stub and the tests are order-independent.
    sys.modules.pop("concrete_pmm_pro.ui.prestress_page", None)

    st = types.ModuleType("streamlit")
    st.session_state = {}
    st.column_config = types.SimpleNamespace(
        CheckboxColumn=lambda *args, **kwargs: None,
        TextColumn=lambda *args, **kwargs: None,
        NumberColumn=lambda *args, **kwargs: None,
        SelectboxColumn=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", st)
    return st


def _railway_geometry():
    from concrete_pmm_pro.geometry.generators import railway_u_girder

    return railway_u_girder(
        width_mm=5500,
        depth_mm=1600,
        top_wall_width_mm=600,
        bottom_side_width_mm=650,
        haunch_x_mm=300,
        haunch_y_mm=300,
        h1_step_height_mm=670,
        h2_bottom_opening_mm=305,
        h3_floor_side_thickness_mm=395,
        h4_floor_center_thickness_mm=450,
    )


def test_railway_u_girder_prestress_span_defaults_to_10m_without_overwriting_existing(monkeypatch) -> None:
    st = _install_streamlit_stub(monkeypatch)

    from concrete_pmm_pro.ui.prestress_page import _girder_prestress_system_settings_from_session

    st.session_state["section_preset_key"] = "railway_u_girder"
    settings = _girder_prestress_system_settings_from_session()
    assert settings["span_length_m"] == pytest.approx(10.0)

    st.session_state["girder_prestress_system_settings"] = {"span_length_m": 14.5, "debond_model": "Left/right independent"}
    settings = _girder_prestress_system_settings_from_session()
    assert settings["span_length_m"] == pytest.approx(14.5)


def test_railway_u_girder_stage_defaults_and_aci_ec(monkeypatch) -> None:
    _install_streamlit_stub(monkeypatch)

    from concrete_pmm_pro.ui.prestress_page import (
        _aci_concrete_ec_mpa,
        _railway_u_girder_stage_settings_from_session,
    )

    settings = _railway_u_girder_stage_settings_from_session()
    assert settings["web_fc_MPa"] == pytest.approx(45.0)
    assert settings["web_fci_MPa"] == pytest.approx(36.0)
    assert settings["slab_fc_MPa"] == pytest.approx(35.0)
    assert settings["concrete_unit_weight_kN_m3"] == pytest.approx(24.0)
    assert settings["formwork_construction_load_kN_m2"] == pytest.approx(2.5)
    assert settings["lifting_point_ratio"] == pytest.approx(0.20)
    assert settings["lifting_impact_factor"] == pytest.approx(1.10)
    assert settings["construction_method"] == "Case B - wet slab carried by precast webs"
    assert _aci_concrete_ec_mpa(45.0) == pytest.approx(31528.558, rel=1e-6)
    assert _aci_concrete_ec_mpa(36.0) == pytest.approx(28200.0)


def test_railway_u_girder_stage_quantities_case_b(monkeypatch) -> None:
    _install_streamlit_stub(monkeypatch)

    from concrete_pmm_pro.ui.prestress_page import (
        _railway_u_girder_stage_quantities_dataframe,
        _railway_u_girder_stage_settings_from_session,
        _railway_u_girder_stage_summary_dataframe,
    )

    settings = _railway_u_girder_stage_settings_from_session()
    geom = _railway_geometry()
    quantities = _railway_u_girder_stage_quantities_dataframe(geom, settings, span_length_m=10.0).set_index("Quantity")

    assert quantities.loc["Precast web area (one side)", "Value"] == pytest.approx(0.9925625)
    assert quantities.loc["CIP slab area", "Value"] == pytest.approx(1.848)
    assert quantities.loc["Web self-weight (one side)", "Value"] == pytest.approx(23.8215)
    assert quantities.loc["Lifting web load with impact", "Value"] == pytest.approx(26.20365)
    assert quantities.loc["Wet slab self-weight to each web", "Value"] == pytest.approx(22.176)
    assert quantities.loc["Formwork/construction load to each web", "Value"] == pytest.approx(5.25)
    assert "a=2.000 m" in quantities.loc["Lifting web load with impact", "Stage use"]

    summary = _railway_u_girder_stage_summary_dataframe(settings)
    assert summary["Stage"].tolist() == [
        "Transfer",
        "Lifting",
        "Wet slab casting",
        "Composite construction",
        "Service",
    ]
    assert summary.loc[0, "Section basis"] == "One precast web only"
    assert summary.loc[2, "Automatic loads"].startswith("web self-weight + 50% wet slab")
    assert summary.loc[4, "Section basis"] == "Full Railway U-Girder"


def test_project_io_preserves_railway_u_girder_stage_settings() -> None:
    from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_session_state

    session_state = {
        "railway_u_girder_stage_settings": {
            "web_fc_MPa": 45.0,
            "web_fci_MPa": 36.0,
            "slab_fc_MPa": 35.0,
            "concrete_unit_weight_kN_m3": 24.0,
            "support_condition": "Simply supported",
            "construction_method": "Case B - wet slab carried by precast webs",
            "wet_slab_distribution_each_web": 0.5,
            "formwork_construction_load_kN_m2": 2.5,
            "lifting_point_ratio": 0.20,
            "lifting_impact_factor": 1.10,
        }
    }

    project = project_from_session_state(session_state)
    assert project.metadata["railway_u_girder_stage_settings"]["web_fci_MPa"] == pytest.approx(36.0)
    assert project.metadata["railway_u_girder_stage_settings"]["lifting_point_ratio"] == pytest.approx(0.20)

    restored: dict[str, object] = {}
    apply_project_to_session_state(project, restored)
    assert restored["railway_u_girder_stage_settings"]["formwork_construction_load_kN_m2"] == pytest.approx(2.5)
    assert restored["railway_u_girder_stage_settings"]["construction_method"] == "Case B - wet slab carried by precast webs"


def test_stage_model_ui_source_guardrails() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "prestress_page.py").read_text(encoding="utf-8")
    dirty = (root / "concrete_pmm_pro" / "state" / "dirty_state.py").read_text(encoding="utf-8")
    project_io = (root / "concrete_pmm_pro" / "io" / "project_io.py").read_text(encoding="utf-8")

    assert "Rail U-Girder stages" in source
    assert "STAGE.RAIL.UGIRDER1 defines the construction-stage basis" in source
    assert "Transfer, lifting, and wet slab casting must not use the full U-section inertia" in source
    assert "RAILWAY_U_GIRDER_DEFAULT_SPAN_LENGTH_M = 10.0" in source
    assert "railway_u_girder_stage_settings" in dirty
    assert "_railway_u_girder_stage_settings_metadata_from_session" in project_io
