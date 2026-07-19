from __future__ import annotations

import inspect

from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui.crossbeam_pages import (
    CROSSBEAM_3D_CONCRETE_STYLES,
    CROSSBEAM_3D_OUTER_BOUNDARY_COLOR,
    CROSSBEAM_3D_TENDON_COLORS,
    CROSSBEAM_3D_VOID_BOUNDARY_COLOR,
    _profile_figure,
    _three_d_figure,
    render_crossbeam_tendon_profile_page,
)


def _source() -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[str],
    list[dict[str, object]],
]:
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), definitions
    )
    tendon_ids = [row["Tendon ID"] for row in default_tendon_system_rows()]
    points = default_tendon_profile_points(
        20.0,
        tendon_ids=tendon_ids,
        width_mm=2500.0,
        height_mm=1500.0,
    )
    return definitions, segments, tendon_ids, points


def _figure(*, transparent: bool, active_ids: list[str] | None = None):
    definitions, segments, tendon_ids, points = _source()
    return _three_d_figure(
        points,
        active_ids if active_ids is not None else tendon_ids,
        segments,
        section_definitions=definitions,
        transparent=transparent,
    )


def test_pt1e_concrete_meshes_use_two_explicit_neutral_role_colors() -> None:
    transparent = _figure(transparent=True)
    muted = _figure(transparent=False)

    for figure, opacity_key in (
        (transparent, "transparent_opacity"),
        (muted, "muted_opacity"),
    ):
        mesh_traces = [trace for trace in figure.data if trace.type == "mesh3d"]
        assert mesh_traces
        assert {trace.color for trace in mesh_traces} == {
            style["color"] for style in CROSSBEAM_3D_CONCRETE_STYLES.values()
        }
        for role, style in CROSSBEAM_3D_CONCRETE_STYLES.items():
            traces = [
                trace
                for trace in mesh_traces
                if trace.name == f"{role} segment"
            ]
            assert traces
            assert {trace.color for trace in traces} == {style["color"]}
            assert {trace.opacity for trace in traces} == {style[opacity_key]}
            assert sum(bool(trace.showlegend) for trace in traces) == 1
            assert all(trace.lighting.ambient >= 0.9 for trace in traces)


def test_pt1e_section_and_void_boundaries_are_clear_but_not_legend_noise() -> None:
    figure = _figure(transparent=True)
    outer = next(trace for trace in figure.data if trace.name == "Section boundaries")
    void = next(trace for trace in figure.data if trace.name == "Void boundaries")

    assert outer.type == "scatter3d"
    assert outer.line.color == CROSSBEAM_3D_OUTER_BOUNDARY_COLOR
    assert outer.line.width == 3
    assert outer.showlegend is False
    assert void.line.color == CROSSBEAM_3D_VOID_BOUNDARY_COLOR
    assert void.line.dash == "dash"
    assert void.showlegend is False
    assert None in outer.x
    assert None in void.x


def test_pt1e_tendon_colors_are_distinct_and_stable_when_visibility_changes() -> None:
    full = _figure(transparent=True)
    subset = _figure(transparent=True, active_ids=["T2", "T4"])
    full_tendons = {
        trace.name: trace
        for trace in full.data
        if trace.name in {"T1", "T2", "T3", "T4"}
    }
    subset_tendons = {
        trace.name: trace
        for trace in subset.data
        if trace.name in {"T2", "T4"}
    }

    assert len({trace.line.color for trace in full_tendons.values()}) == 4
    assert [full_tendons[f"T{index}"].line.color for index in range(1, 5)] == list(
        CROSSBEAM_3D_TENDON_COLORS[:4]
    )
    assert subset_tendons["T2"].line.color == full_tendons["T2"].line.color
    assert subset_tendons["T4"].line.color == full_tendons["T4"].line.color
    assert all(trace.line.width == 8 for trace in full_tendons.values())
    assert all(trace.marker.size == 5 for trace in full_tendons.values())
    assert all(trace.marker.line.color == "#FFFFFF" for trace in full_tendons.values())


def test_pt1e_3d_layout_and_caption_explain_the_visual_hierarchy() -> None:
    figure = _figure(transparent=True)
    source = inspect.getsource(render_crossbeam_tendon_profile_page)

    assert figure.layout.scene.bgcolor == "#FBFCFE"
    assert figure.layout.scene.camera.projection.type == "orthographic"
    assert figure.layout.uirevision == "crossbeam-pt1e-3d-view"
    assert figure.layout.scene.domain.y[1] <= 0.78
    assert figure.layout.legend.y >= 0.86
    assert figure.layout.margin.t >= 120
    assert "Concrete is intentionally neutral" in source
    assert "dashed loops mark Hollow voids" in source
    assert "not change geometry, tendon inputs, validation, or analysis" in source


def test_pt1e_elevation_reserves_header_band_for_legend_and_top_surface_label() -> None:
    definitions, segments, tendon_ids, points = _source()
    figure = _profile_figure(points, tendon_ids, segments, definitions)
    top_surface_labels = [
        annotation
        for annotation in figure.layout.annotations
        if "Top surface" in str(annotation.text)
    ]

    assert figure.layout.yaxis.domain[1] <= 0.8
    assert figure.layout.legend.y >= 0.86
    assert figure.layout.margin.t >= 110
    assert top_surface_labels
    assert top_surface_labels[0].yref == "paper"
    assert float(top_surface_labels[0].y) > float(figure.layout.yaxis.domain[1])
