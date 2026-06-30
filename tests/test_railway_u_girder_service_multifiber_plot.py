from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.core.models import ConcreteMaterial
from concrete_pmm_pro.ui import analysis_page


SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")


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


def test_railway_u_girder_service_multifiber_plot_source_markers() -> None:
    assert "SLS.RAIL.UGIRDER8" in SOURCE
    assert "Top web fiber" in SOURCE
    assert "Bottom web fiber" in SOURCE
    assert "CIP slab top fiber" in SOURCE
    assert "CIP slab bottom fiber" in SOURCE
    assert "Web tension limit" in SOURCE
    assert "Slab tension limit" in SOURCE
    assert "separate web/slab material limits" in SOURCE


def test_railway_u_girder_service_multifiber_dataframe_interpolates_slab_fibers() -> None:
    backup = _with_session_state(
        {
            "section_preset_key": "railway_u_girder",
            "section_parameters": {
                "depth_mm": 1600.0,
                "h2_bottom_opening_mm": 305.0,
                "h4_floor_center_thickness_mm": 450.0,
            },
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
        df = pd.DataFrame(
            {
                "Station x (m)": [0.0],
                "Top total (MPa)": [-5.0],
                "Bottom total (MPa)": [3.0],
            }
        )
        multi = analysis_page._railway_u_girder_service_multifiber_dataframe(df)
        assert set(multi["Fiber"]) == {
            "Top web fiber",
            "Bottom web fiber",
            "CIP slab top fiber",
            "CIP slab bottom fiber",
        }
        by_fiber = {row["Fiber"]: row for _, row in multi.iterrows()}
        assert by_fiber["Top web fiber"]["Total stress (MPa)"] == pytest.approx(-5.0)
        assert by_fiber["Bottom web fiber"]["Total stress (MPa)"] == pytest.approx(3.0)
        # CIP slab top y = h2 + h4 = 755 mm from bottom. Linear stress from bottom=3 to top=-5 over 1600 mm.
        assert by_fiber["CIP slab top fiber"]["Total stress (MPa)"] == pytest.approx(3.0 + (-8.0) * 755.0 / 1600.0)
        assert by_fiber["CIP slab top fiber"]["f'c basis (MPa)"] == pytest.approx(35.0)
        assert by_fiber["Top web fiber"]["f'c basis (MPa)"] == pytest.approx(45.0)
    finally:
        _restore_session_state(backup)


def test_railway_u_girder_service_multifiber_figure_has_labeled_web_slab_limits() -> None:
    backup = _with_session_state(
        {
            "section_preset_key": "railway_u_girder",
            "section_parameters": {
                "depth_mm": 1600.0,
                "h2_bottom_opening_mm": 305.0,
                "h4_floor_center_thickness_mm": 450.0,
            },
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
        df = pd.DataFrame(
            {
                "Station x (m)": [0.0, 5.0, 10.0],
                "Top total (MPa)": [-5.0, -4.0, -5.0],
                "Bottom total (MPa)": [3.0, 2.0, 3.0],
            }
        )
        fig = analysis_page._make_girder_full_length_sls_figure(df, stage_label="Service stage")
        names = {trace.name for trace in fig.data}
        assert "Top web fiber" in names
        assert "Bottom web fiber" in names
        assert "CIP slab top fiber" in names
        assert "CIP slab bottom fiber" in names
        annotation_text = " ".join(str(getattr(annotation, "text", "")) for annotation in fig.layout.annotations)
        assert "Web tension limit" in annotation_text
        assert "Slab tension limit" in annotation_text
        assert "Web compression limit" in annotation_text
        assert "Slab compression limit" in annotation_text
    finally:
        _restore_session_state(backup)


def test_ui_plot3_service_multifiber_legend_and_limit_labels_do_not_overlap_plot() -> None:
    backup = _with_session_state(
        {
            "section_preset_key": "railway_u_girder",
            "section_parameters": {
                "depth_mm": 1600.0,
                "h2_bottom_opening_mm": 305.0,
                "h4_floor_center_thickness_mm": 450.0,
            },
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
        df = pd.DataFrame(
            {
                "Station x (m)": [0.0, 5.0, 10.0],
                "Top total (MPa)": [3.8, 2.5, 3.2],
                "Bottom total (MPa)": [-5.0, -4.0, -5.0],
            }
        )
        fig = analysis_page._make_girder_full_length_sls_figure(df, stage_label="Service stage")
        assert fig.layout.height >= 760
        assert fig.layout.margin.r >= 220
        assert fig.layout.margin.b >= 170
        assert fig.layout.legend.y <= -0.28
        names = {trace.name for trace in fig.data}
        assert "Web comp. limit" in names
        assert "Slab comp. limit" in names
        assert "Web compression limit = -27.000 MPa" not in names
        limit_annotations = [annotation for annotation in fig.layout.annotations if "limit" in str(annotation.text)]
        assert limit_annotations
        assert all(getattr(annotation, "xref", None) == "paper" for annotation in limit_annotations)
        assert all(float(getattr(annotation, "x", 0.0)) > 1.0 for annotation in limit_annotations)
    finally:
        _restore_session_state(backup)
