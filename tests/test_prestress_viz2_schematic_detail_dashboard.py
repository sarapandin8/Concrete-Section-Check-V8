from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd

SOURCE = Path("concrete_pmm_pro/ui/prestress_page.py").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    start = SOURCE.index(f"def {name}")
    end = SOURCE.index("\n\ndef ", start + 1)
    return SOURCE[start:end]


def test_cross_section_layout_is_overall_schematic_not_single_clutter_plot() -> None:
    body = _function_source("_plot_girder_strand_cross_section_layout")

    assert "Overall section schematic" in body
    assert "Strand row summary" not in body
    assert "fig.add_annotation" not in body or "strand block" in body
    assert "_add_strand_state_marker_traces" in body
    assert "marker_size=5" in body
    assert "type=\"rect\"" in body


def test_dashboard_renderer_splits_overall_summary_and_detail_panels() -> None:
    body = _function_source("_render_girder_strand_cross_section_dashboard")

    assert "Split dashboard" in body
    assert "Strand row summary" in body
    assert "Zoomed strand block detail" in body
    assert "_plot_girder_strand_block_detail" in body
    assert "displayModeBar" in body
    assert "_should_split_girder_strand_detail" in body


def test_detail_panel_uses_large_markers_and_no_row_summary_annotation() -> None:
    body = _function_source("_plot_girder_strand_block_detail")

    assert "marker_size=13" in body
    assert "_add_strand_detail_dimensions" in body
    assert "ticktext" in body
    assert "Strand row summary" not in body


def test_row_summary_combines_symmetric_railway_rows(monkeypatch) -> None:
    st = types.ModuleType("streamlit")
    st.session_state = {}
    st.column_config = types.SimpleNamespace(
        CheckboxColumn=lambda *args, **kwargs: None,
        TextColumn=lambda *args, **kwargs: None,
        NumberColumn=lambda *args, **kwargs: None,
        SelectboxColumn=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", st)

    from concrete_pmm_pro.ui.prestress_page import (  # noqa: PLC0415
        _girder_strand_row_summary_dataframe,
        _normalize_girder_strand_layout_table,
    )

    raw = pd.DataFrame(
        [
            {
                "Active": True,
                "Group ID": "L Row 1",
                "Strand Size": "12.7 mm low-relaxation strand",
                "No. Strands": 9,
                "y_mm_from_bottom": 95.0,
                "Left debond m": 2.0,
                "Right debond m": 2.0,
                "Debonded strand nos": "1,9",
            },
            {
                "Active": True,
                "Group ID": "R Row 1",
                "Strand Size": "12.7 mm low-relaxation strand",
                "No. Strands": 9,
                "y_mm_from_bottom": 95.0,
                "Left debond m": 2.0,
                "Right debond m": 2.0,
                "Debonded strand nos": "1,9",
            },
        ]
    )
    table = _normalize_girder_strand_layout_table(raw, span_length_m=10.0)
    summary = _girder_strand_row_summary_dataframe(table, None)

    assert summary.shape[0] == 1
    assert summary.loc[0, "Row"] == "Row 1"
    assert summary.loc[0, "Total strands"] == 18
    assert summary.loc[0, "Bonded"] == 14
    assert summary.loc[0, "Debonded"] == 4
    assert summary.loc[0, "Left debond (m)"] == 2.0
    assert summary.loc[0, "Right debond (m)"] == 2.0


def test_non_railway_layout_policy_merges_symmetric_bottom_cluster(monkeypatch) -> None:
    st = types.ModuleType("streamlit")
    st.session_state = {}
    monkeypatch.setitem(sys.modules, "streamlit", st)

    from concrete_pmm_pro.ui.prestress_page import _should_split_girder_strand_detail  # noqa: PLC0415

    points = pd.DataFrame({"x_mm": [-150.0, -75.0, 75.0, 150.0], "y_mm_abs": [-700.0] * 4})

    assert _should_split_girder_strand_detail(points, None) is False


def test_detail_panel_source_contains_spacing_and_edge_dimension_helpers() -> None:
    body = _function_source("_add_strand_detail_dimensions")

    assert "s =" in body
    assert "eL =" in body
    assert "eR =" in body
    assert "eb =" in body
    assert "v =" in body


def test_detail_panel_draws_local_concrete_envelope_and_keeps_dimensions(monkeypatch) -> None:
    st = types.ModuleType("streamlit")
    st.session_state = {}
    st.column_config = types.SimpleNamespace(
        CheckboxColumn=lambda *args, **kwargs: None,
        TextColumn=lambda *args, **kwargs: None,
        NumberColumn=lambda *args, **kwargs: None,
        SelectboxColumn=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", st)

    from concrete_pmm_pro.geometry.generators import box_section_fillet  # noqa: PLC0415
    from concrete_pmm_pro.ui.prestress_page import (  # noqa: PLC0415
        _normalize_girder_strand_layout_table,
        _plot_girder_strand_block_detail,
    )

    geometry = box_section_fillet(
        width_mm=1000.0,
        height_mm=700.0,
        t_top_mm=120.0,
        t_bottom_mm=140.0,
        t_left_mm=120.0,
        t_right_mm=120.0,
        r_inner_mm=0.0,
    )
    table = _normalize_girder_strand_layout_table(None, span_length_m=20.0, geometry=geometry)
    fig = _plot_girder_strand_block_detail(table, geometry, side="All")

    trace_names = [trace.name for trace in fig.data]
    assert any(str(name).startswith("Full section context") for name in trace_names)
    assert any("void" in str(name).lower() for name in trace_names)
    labels = " | ".join(str(annotation.text) for annotation in fig.layout.annotations)
    assert "typ. s =" in labels
    assert "eL =" in labels
    assert "eR =" in labels
    assert "eb =" in labels


def test_overall_non_railway_schematic_does_not_show_left_right_block_labels(monkeypatch) -> None:
    st = types.ModuleType("streamlit")
    st.session_state = {}
    monkeypatch.setitem(sys.modules, "streamlit", st)

    from concrete_pmm_pro.geometry.generators import psc_i_girder  # noqa: PLC0415
    from concrete_pmm_pro.ui.prestress_page import (  # noqa: PLC0415
        _normalize_girder_strand_layout_table,
        _plot_girder_strand_cross_section_layout,
    )

    geometry = psc_i_girder(
        depth_mm=1500.0,
        top_flange_width_mm=700.0,
        top_flange_thickness_mm=200.0,
        web_width_mm=180.0,
        bottom_flange_width_mm=550.0,
        bottom_flange_thickness_mm=250.0,
    )
    table = _normalize_girder_strand_layout_table(None, span_length_m=20.0, geometry=geometry)
    fig = _plot_girder_strand_cross_section_layout(table, geometry)

    labels = [str(annotation.text) for annotation in fig.layout.annotations]
    assert not any("Left strand block" in label or "Right strand block" in label for label in labels)


def test_non_split_box_detail_uses_full_section_bounds(monkeypatch) -> None:
    st = types.ModuleType("streamlit")
    st.session_state = {}
    st.column_config = types.SimpleNamespace(
        CheckboxColumn=lambda *args, **kwargs: None,
        TextColumn=lambda *args, **kwargs: None,
        NumberColumn=lambda *args, **kwargs: None,
        SelectboxColumn=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", st)

    from concrete_pmm_pro.geometry.generators import box_section_fillet  # noqa: PLC0415
    from concrete_pmm_pro.geometry.summary import to_shapely_polygon  # noqa: PLC0415
    from concrete_pmm_pro.ui.prestress_page import (  # noqa: PLC0415
        _normalize_girder_strand_layout_table,
        _plot_girder_strand_block_detail,
    )

    geometry = box_section_fillet(
        width_mm=1000.0,
        height_mm=700.0,
        t_top_mm=120.0,
        t_bottom_mm=140.0,
        t_left_mm=120.0,
        t_right_mm=120.0,
        r_inner_mm=0.0,
    )
    table = _normalize_girder_strand_layout_table(None, span_length_m=20.0, geometry=geometry)
    fig = _plot_girder_strand_block_detail(table, geometry, side="All")
    minx, miny, maxx, maxy = [float(value) for value in to_shapely_polygon(geometry).bounds]

    assert fig.layout.xaxis.range[0] <= minx
    assert fig.layout.xaxis.range[1] >= maxx
    assert fig.layout.yaxis.range[0] <= miny
    assert fig.layout.yaxis.range[1] >= maxy


def test_railway_u_girder_split_detail_uses_web_scale_not_full_section(monkeypatch) -> None:
    st = types.ModuleType("streamlit")
    st.session_state = {}
    st.column_config = types.SimpleNamespace(
        CheckboxColumn=lambda *args, **kwargs: None,
        TextColumn=lambda *args, **kwargs: None,
        NumberColumn=lambda *args, **kwargs: None,
        SelectboxColumn=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", st)

    from concrete_pmm_pro.geometry.generators import railway_u_girder  # noqa: PLC0415
    from concrete_pmm_pro.geometry.summary import to_shapely_polygon  # noqa: PLC0415
    from concrete_pmm_pro.ui.prestress_page import (  # noqa: PLC0415
        _normalize_girder_strand_layout_table,
        _plot_girder_strand_block_detail,
    )

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
    table = _normalize_girder_strand_layout_table(None, span_length_m=30.0, geometry=geometry)
    fig = _plot_girder_strand_block_detail(table, geometry, side="Left")
    section_minx, _, section_maxx, _ = [float(value) for value in to_shapely_polygon(geometry).bounds]
    detail_width = float(fig.layout.xaxis.range[1]) - float(fig.layout.xaxis.range[0])
    section_width = float(section_maxx) - float(section_minx)

    assert detail_width < section_width * 0.40
    assert float(fig.layout.xaxis.range[1]) < 0.0



def test_non_split_detail_uses_single_full_section_panel(monkeypatch) -> None:
    st = types.ModuleType("streamlit")
    st.session_state = {}
    st.column_config = types.SimpleNamespace(
        CheckboxColumn=lambda *args, **kwargs: None,
        TextColumn=lambda *args, **kwargs: None,
        NumberColumn=lambda *args, **kwargs: None,
        SelectboxColumn=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", st)

    from concrete_pmm_pro.geometry.generators import box_section_fillet  # noqa: PLC0415
    from concrete_pmm_pro.ui.prestress_page import (  # noqa: PLC0415
        _normalize_girder_strand_layout_table,
        _plot_girder_strand_block_detail,
    )

    geometry = box_section_fillet(
        width_mm=1000.0,
        height_mm=700.0,
        t_top_mm=120.0,
        t_bottom_mm=140.0,
        t_left_mm=120.0,
        t_right_mm=120.0,
        r_inner_mm=0.0,
    )
    table = _normalize_girder_strand_layout_table(None, span_length_m=20.0, geometry=geometry)
    fig = _plot_girder_strand_block_detail(table, geometry, side="All")

    assert getattr(fig.layout, "xaxis2", None) is None
    assert getattr(fig.layout, "yaxis2", None) is None
    assert not any("Magnified strand detail" in str(annotation.text) for annotation in fig.layout.annotations)



def test_non_split_dimension_annotations_live_on_main_axes(monkeypatch) -> None:
    st = types.ModuleType("streamlit")
    st.session_state = {}
    st.column_config = types.SimpleNamespace(
        CheckboxColumn=lambda *args, **kwargs: None,
        TextColumn=lambda *args, **kwargs: None,
        NumberColumn=lambda *args, **kwargs: None,
        SelectboxColumn=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "streamlit", st)

    from concrete_pmm_pro.geometry.generators import psc_i_girder  # noqa: PLC0415
    from concrete_pmm_pro.ui.prestress_page import (  # noqa: PLC0415
        _normalize_girder_strand_layout_table,
        _plot_girder_strand_block_detail,
    )

    geometry = psc_i_girder(
        depth_mm=1500.0,
        top_flange_width_mm=700.0,
        top_flange_thickness_mm=200.0,
        web_width_mm=180.0,
        bottom_flange_width_mm=550.0,
        bottom_flange_thickness_mm=250.0,
    )
    table = _normalize_girder_strand_layout_table(None, span_length_m=20.0, geometry=geometry)
    fig = _plot_girder_strand_block_detail(table, geometry, side="All")

    dimension_labels = ("typ. s =", "eL =", "eR =", "eb =", "v =")
    dimension_annotations = [
        annotation for annotation in fig.layout.annotations if any(label in str(annotation.text) for label in dimension_labels)
    ]
    assert dimension_annotations
    assert all(annotation.xref == "x" and annotation.yref == "y" for annotation in dimension_annotations)
