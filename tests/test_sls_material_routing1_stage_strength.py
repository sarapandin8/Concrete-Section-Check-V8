from __future__ import annotations

import pytest

from concrete_pmm_pro.core.models import ConcreteMaterial
from concrete_pmm_pro.ui import analysis_page


def _with_session_state(values: dict[str, object]):
    state = analysis_page.st.session_state
    backup = dict(state)
    state.clear()
    state.update(values)
    return state, backup


def _restore_session_state(backup: dict[str, object]) -> None:
    state = analysis_page.st.session_state
    state.clear()
    state.update(backup)


def test_railway_u_girder_sls_limit_strength_routes_transfer_to_web_fci() -> None:
    state, backup = _with_session_state(
        {
            "section_preset_key": "railway_u_girder",
            "concrete_material": ConcreteMaterial(name="C45_PRECAST", fc_MPa=45.0, density_kg_m3=2400.0),
            "railway_u_girder_stage_settings": {
                "web_fc_MPa": 45.0,
                "web_fci_MPa": 36.0,
                "slab_fc_MPa": 35.0,
            },
        }
    )
    try:
        transfer = analysis_page._stage_material_strength_values_for_sls_limit_preview("Transfer stage")
        construction = analysis_page._stage_material_strength_values_for_sls_limit_preview("Construction stage")
        service = analysis_page._stage_material_strength_values_for_sls_limit_preview("Service stage")

        assert transfer["strength_MPa"] == pytest.approx(36.0)
        assert "web f'ci" in str(transfer["strength_label"])
        assert "not web final f'c" in str(transfer["audit_note"])
        assert construction["strength_MPa"] == pytest.approx(45.0)
        assert "pre-composite" in str(construction["strength_label"])
        assert service["strength_MPa"] == pytest.approx(45.0)
        assert "CIP slab f'c = 35.000 MPa" in str(service["audit_note"])
    finally:
        _restore_session_state(backup)


def test_generic_prestressed_girder_transfer_uses_fci_not_final_fc() -> None:
    _state, backup = _with_session_state(
        {
            "section_preset_key": "parametric_i_girder",
            "concrete_material": ConcreteMaterial(name="C45_PRECAST", fc_MPa=45.0, density_kg_m3=2400.0),
            "girder_prestress_system_settings": {"fci_MPa": 36.0},
        }
    )
    try:
        transfer = analysis_page._stage_material_strength_values_for_sls_limit_preview("Transfer stage")
        service = analysis_page._stage_material_strength_values_for_sls_limit_preview("Service stage")

        assert transfer["strength_MPa"] == pytest.approx(36.0)
        assert "f'ci" in str(transfer["strength_label"])
        assert "primary f'c = 45.000 MPa" in str(transfer["audit_note"])
        assert service["strength_MPa"] == pytest.approx(45.0)
    finally:
        _restore_session_state(backup)


def test_railway_u_girder_transfer_strength_routes_from_geometry_metadata_when_selector_missing() -> None:
    from concrete_pmm_pro.geometry.generators import railway_u_girder

    geometry = railway_u_girder(
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
    _state, backup = _with_session_state(
        {
            # Stale/missing selector condition reproduced from Analysis reroute paths.
            "section_preset_key": "parametric_i_girder",
            "section_geometry": geometry,
            "concrete_material": ConcreteMaterial(name="C45_PRECAST", fc_MPa=45.0, density_kg_m3=2400.0),
            "railway_u_girder_stage_settings": {
                "web_fc_MPa": 45.0,
                "web_fci_MPa": 36.0,
                "slab_fc_MPa": 35.0,
            },
        }
    )
    try:
        transfer = analysis_page._stage_material_strength_values_for_sls_limit_preview("Transfer stage")
        assert transfer["strength_MPa"] == pytest.approx(36.0)
        assert "Railway U-Girder" in str(transfer["audit_note"])
    finally:
        _restore_session_state(backup)


def test_railway_u_girder_transfer_strength_routes_from_display_name_when_geometry_unavailable() -> None:
    _state, backup = _with_session_state(
        {
            "section_preset_name": "Railway U-Girder",
            "concrete_material": ConcreteMaterial(name="C45_PRECAST", fc_MPa=45.0, density_kg_m3=2400.0),
            "railway_u_girder_stage_settings": {
                "web_fc_MPa": 45.0,
                "web_fci_MPa": 36.0,
                "slab_fc_MPa": 35.0,
            },
        }
    )
    try:
        transfer = analysis_page._stage_material_strength_values_for_sls_limit_preview("Transfer stage")
        assert transfer["strength_MPa"] == pytest.approx(36.0)
    finally:
        _restore_session_state(backup)


def test_stage_strength_routing_is_threaded_into_analysis_page_source() -> None:
    from pathlib import Path

    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
    assert "SLS.MATERIAL.ROUTING1" in source
    assert "SLS.MATERIAL.ROUTING2" in source
    assert "web f'ci at transfer / release" in source
    assert "_stage_material_strength_values_for_sls_limit_preview(locked_stage_label or stage)" in source
    assert "must not reuse a stale service f'c" in source
    assert "geometry metadata before the" in source


def test_railway_u_girder_transfer_strength_routes_from_section_parameters_when_other_signals_are_stale() -> None:
    _state, backup = _with_session_state(
        {
            # Reproduce the Analysis-page failure mode: stale generic selector and
            # stale generic transfer fci must not override Railway U-Girder stage settings.
            "section_preset_key": "parametric_i_girder",
            "section_parameters": {
                "width_mm": 5500.0,
                "depth_mm": 1600.0,
                "top_wall_width_mm": 600.0,
                "bottom_side_width_mm": 650.0,
                "h1_step_height_mm": 670.0,
                "h2_bottom_opening_mm": 305.0,
                "h3_floor_side_thickness_mm": 395.0,
                "h4_floor_center_thickness_mm": 450.0,
            },
            "concrete_material": ConcreteMaterial(name="C45_PRECAST", fc_MPa=45.0, density_kg_m3=2400.0),
            "girder_code_loss_fci_mpa": 45.0,
            "girder_prestress_system_settings": {"fci_MPa": 45.0},
            "railway_u_girder_stage_settings": {
                "web_fc_MPa": 45.0,
                "web_fci_MPa": 36.0,
                "slab_fc_MPa": 35.0,
                "construction_method": "Case B - wet slab carried by precast webs",
            },
        }
    )
    try:
        transfer = analysis_page._stage_material_strength_values_for_sls_limit_preview("Transfer stage")
        assert transfer["strength_MPa"] == pytest.approx(36.0)
        assert "web f'ci" in str(transfer["strength_label"])
    finally:
        _restore_session_state(backup)


def test_railway_u_girder_transfer_strength_routes_from_stage_settings_guarded_fallback() -> None:
    _state, backup = _with_session_state(
        {
            "section_preset_key": "parametric_i_girder",
            "concrete_material": ConcreteMaterial(name="C45_PRECAST", fc_MPa=45.0, density_kg_m3=2400.0),
            "girder_code_loss_fci_mpa": 45.0,
            "railway_u_girder_stage_settings": {
                "web_fc_MPa": 45.0,
                "web_fci_MPa": 36.0,
                "slab_fc_MPa": 35.0,
                "construction_method": "Case B - wet slab carried by precast webs",
            },
        }
    )
    try:
        transfer = analysis_page._stage_material_strength_values_for_sls_limit_preview("Transfer stage")
        assert transfer["strength_MPa"] == pytest.approx(36.0)
    finally:
        _restore_session_state(backup)


def test_visible_tensile_guide_uses_stage_routed_strength_not_generic_fc_helper() -> None:
    from pathlib import Path

    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
    assert "SLS.MATERIAL.ROUTING3" in source
    assert "guide_stage_strength = _stage_material_strength_values_for_sls_limit_preview(stage)" in source
    assert "guide_strength_label" in source
    assert "guide_strength_note" in source
    assert "Tension formula substitution" in source


def test_railway_u_girder_transfer_strength_routes_from_canonical_transfer_stage_label() -> None:
    _state, backup = _with_session_state(
        {
            "section_preset_key": "railway_u_girder",
            "concrete_material": ConcreteMaterial(name="C45_PRECAST", fc_MPa=45.0, density_kg_m3=2400.0),
            "railway_u_girder_stage_settings": {
                "web_fc_MPa": 45.0,
                "web_fci_MPa": 36.0,
                "slab_fc_MPa": 35.0,
                "construction_method": "Case B - wet slab carried by precast webs",
            },
        }
    )
    try:
        # The visible tensile guide passes the canonical code-limit stage, not the
        # simplified tab label.  This was the remaining bug: "Transfer / Release"
        # was being remapped to User-defined and then falling through to service f'c.
        transfer = analysis_page._stage_material_strength_values_for_sls_limit_preview("Transfer / Release")
        assert transfer["strength_MPa"] == pytest.approx(36.0)
        assert transfer["strength_label"] == "web f'ci at transfer / release"
        assert "not web final f'c = 45.000 MPa" in str(transfer["audit_note"])
    finally:
        _restore_session_state(backup)
