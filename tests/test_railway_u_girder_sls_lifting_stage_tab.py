from __future__ import annotations

import pytest

from concrete_pmm_pro.core.models import ConcreteMaterial
from concrete_pmm_pro.geometry.generators import railway_u_girder
from concrete_pmm_pro.ui import analysis_page
from concrete_pmm_pro.ui.prestress_page import _default_girder_strand_layout_table


def _railway_geometry():
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


def _with_session_state(values: dict[str, object]):
    state = analysis_page.st.session_state
    backup = dict(state)
    state.clear()
    state.update(values)
    return backup


def _restore_session_state(backup: dict[str, object]) -> None:
    state = analysis_page.st.session_state
    state.clear()
    state.update(backup)


def test_railway_u_girder_analysis_tabs_include_lifting_stage_only_for_railway() -> None:
    geom = _railway_geometry()
    backup = _with_session_state(
        {
            "section_preset_key": "railway_u_girder",
            "section_geometry": geom,
            "railway_u_girder_stage_settings": {
                "web_fc_MPa": 45.0,
                "web_fci_MPa": 36.0,
                "slab_fc_MPa": 35.0,
                "construction_method": "Case B - wet slab carried by precast webs",
            },
        }
    )
    try:
        labels = [label for _key, label, _note in analysis_page._beam_sls_stage_tab_specs()]
        assert labels == ["Transfer stage", "Lifting stage", "Construction stage", "Service stage"]
    finally:
        _restore_session_state(backup)

    backup = _with_session_state({"section_preset_key": "slab_bridge"})
    try:
        labels = [label for _key, label, _note in analysis_page._beam_sls_stage_tab_specs()]
        assert labels == ["Transfer stage", "Construction stage", "Service stage"]
    finally:
        _restore_session_state(backup)


def test_generic_precast_girder_analysis_tabs_include_lifting_stage() -> None:
    for preset_key in (
        "parametric_i_girder",
        "box_section_fillet",
        "precast_box_beam_exterior",
        "parametric_plank_girder_interior",
        "parametric_plank_girder_voided_interior",
    ):
        backup = _with_session_state({"section_preset_key": preset_key})
        try:
            labels = [label for _key, label, _note in analysis_page._beam_sls_stage_tab_specs()]
            assert labels == ["Transfer stage", "Lifting stage", "Construction stage", "Service stage"]
        finally:
            _restore_session_state(backup)


def test_lifting_stage_uses_transfer_strength_profile_for_railway_u_girder() -> None:
    geom = _railway_geometry()
    backup = _with_session_state(
        {
            "section_preset_key": "railway_u_girder",
            "section_geometry": geom,
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
        assert analysis_page._beam_sls_stage_label_for_analysis("Temporary lifting") == "Lifting stage"
        lifting = analysis_page._stage_material_strength_values_for_sls_limit_preview("Lifting stage")
        assert lifting["strength_MPa"] == pytest.approx(36.0)
        assert "web f'ci" in str(lifting["strength_label"])
    finally:
        _restore_session_state(backup)


def test_railway_u_girder_lifting_stage_full_length_rows_use_one_web_lifting_basis() -> None:
    geom = _railway_geometry()
    strand_table = _default_girder_strand_layout_table(geom)
    backup = _with_session_state(
        {
            "section_preset_key": "railway_u_girder",
            "section_geometry": geom,
            "girder_strand_layout_table": strand_table,
            "railway_u_girder_stage_settings": {
                "span_length_m": 10.0,
                "web_fc_MPa": 45.0,
                "web_fci_MPa": 36.0,
                "slab_fc_MPa": 35.0,
                "concrete_unit_weight_kN_m3": 24.0,
                "wet_slab_distribution_each_web": 0.5,
                "formwork_construction_load_kN_m2": 2.5,
                "lifting_point_ratio": 0.20,
                "lifting_impact_factor": 1.10,
                "construction_method": "Case B - wet slab carried by precast webs",
            },
        }
    )
    try:
        df = analysis_page._girder_full_length_sls_stage_rows(
            stage_label="Lifting stage",
            load_rows=[],
            basis_options=object(),
            basis_names=[],
            span_length_m=10.0,
        )
        assert not df.empty
        assert set(df["Stage"]) == {"Lifting stage"}
        assert set(df["Basis"]) == {"Railway U-Girder one-web lifting section"}
        assert df["Auto load components"].astype(str).str.contains("two-point lifting").any()
        # Two-point lifting produces a negative overhang moment at the lifting point
        # and a positive midspan moment; a simple-span Transfer tab would not.
        row_at_lift = df.iloc[(df["Station x (m)"] - 2.0).abs().argsort()[:1]]
        row_at_mid = df.iloc[(df["Station x (m)"] - 5.0).abs().argsort()[:1]]
        assert float(row_at_lift["Auto Mx (kN-m)"].iloc[0]) < 0.0
        assert float(row_at_mid["Auto Mx (kN-m)"].iloc[0]) > 0.0
        assert float(df["Pe stage (kN)"].max()) > 0.0
    finally:
        _restore_session_state(backup)


def test_railway_u_girder_lifting_stage_uses_live_section_builder_lifting_widget_state() -> None:
    geom = _railway_geometry()
    strand_table = _default_girder_strand_layout_table(geom)
    backup = _with_session_state(
        {
            "section_preset_key": "railway_u_girder",
            "section_geometry": geom,
            "girder_strand_layout_table": strand_table,
            "railway_u_girder_stage_settings": {
                "span_length_m": 10.0,
                "web_fc_MPa": 45.0,
                "web_fci_MPa": 36.0,
                "slab_fc_MPa": 35.0,
                "concrete_unit_weight_kN_m3": 24.0,
                "wet_slab_distribution_each_web": 0.5,
                "formwork_construction_load_kN_m2": 2.5,
                "lifting_point_ratio": 0.20,
                "lifting_impact_factor": 1.10,
                "construction_method": "Case B - wet slab carried by precast webs",
            },
            # Simulate a user changing Section Builder to a/L = 0.05 and then
            # returning to Analysis before the persisted settings dict is the
            # only reliable source of truth.
            "rail_ugirder_assembly_lifting_ratio_input": 0.05,
            "rail_ugirder_assembly_lifting_impact_input": 1.10,
            "rail_ugirder_assembly_span_length_m_input": 10.0,
        }
    )
    try:
        extras = analysis_page._girder_sls_lifting_station_extras(10.0)
        assert 0.5 in [round(float(x), 6) for x in extras]
        assert 9.5 in [round(float(x), 6) for x in extras]

        df = analysis_page._girder_full_length_sls_stage_rows(
            stage_label="Lifting stage",
            load_rows=[],
            basis_options=object(),
            basis_names=[],
            span_length_m=10.0,
        )
        assert not df.empty
        assert df["Auto load components"].astype(str).str.contains("a/L=0.050").all()
        row_at_lift = df.iloc[(df["Station x (m)"] - 0.5).abs().argsort()[:1]]
        row_at_old_lift = df.iloc[(df["Station x (m)"] - 2.0).abs().argsort()[:1]]
        assert float(row_at_lift["Auto Mx (kN-m)"].iloc[0]) < 0.0
        assert float(row_at_old_lift["Auto Mx (kN-m)"].iloc[0]) > 0.0

        fig = analysis_page._make_girder_full_length_sls_figure(df, stage_label="Lifting stage")
        lift_marker_x = [float(shape.x0) for shape in fig.layout.shapes if getattr(shape, "xref", "") == "x"]
        assert any(abs(x - 0.5) <= 1.0e-9 for x in lift_marker_x)
        assert any(abs(x - 9.5) <= 1.0e-9 for x in lift_marker_x)
        annotation_text = "\n".join(str(annotation.text) for annotation in fig.layout.annotations)
        assert "x=0.500 m" in annotation_text
        assert "x=9.500 m" in annotation_text
    finally:
        _restore_session_state(backup)
