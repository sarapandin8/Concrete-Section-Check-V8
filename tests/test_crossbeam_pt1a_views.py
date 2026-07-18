from __future__ import annotations

from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    definition_map,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui.crossbeam_pages import (
    _cross_section_figure,
    _three_d_figure,
)


def _geometry_context():
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), definitions
    )
    return definitions, segments


def test_pt1a_cross_section_uses_exact_hollow_geometry_for_fit_review() -> None:
    definition = definition_map(default_section_definitions())["CB-H01"]
    positions = [
        {
            "Tendon ID": "T-IN",
            "Type": "Internal",
            "x lateral (mm)": 0.0,
            "dtop (mm)": 150.0,
            "Left point": "P1",
            "Right point": "P2",
            "Interpolation": "Piecewise linear",
        },
        {
            "Tendon ID": "T-VOID",
            "Type": "Internal",
            "x lateral (mm)": 0.0,
            "dtop (mm)": 750.0,
            "Left point": "P1",
            "Right point": "P2",
            "Interpolation": "Piecewise linear",
        },
        {
            "Tendon ID": "T-EXT",
            "Type": "External",
            "x lateral (mm)": 0.0,
            "dtop (mm)": 750.0,
            "Left point": "P1",
            "Right point": "P2",
            "Interpolation": "Piecewise linear",
        },
    ]

    figure, fit_rows = _cross_section_figure(
        definition,
        positions,
        station_m=5.0,
        segment_id="S2",
        station_face="Within segment",
    )

    fit_by_id = {row["Tendon ID"]: row for row in fit_rows}
    assert fit_by_id["T-IN"]["Cross-section fit"] == "IN CONCRETE"
    assert fit_by_id["T-VOID"]["Cross-section fit"] == "OUTSIDE / VOID — REVIEW"
    assert fit_by_id["T-EXT"]["Cross-section fit"] == "EXTERNAL — LOCATION SHOWN"
    assert any(trace.name == "Void" for trace in figure.data)
    assert "CB-H01" in figure.layout.title.text


def test_pt1a_3d_review_is_orthographic_and_uses_shared_profile_source() -> None:
    definitions, segments = _geometry_context()
    system = default_tendon_system_rows()
    active_ids = [row["Tendon ID"] for row in system]
    points = default_tendon_profile_points(
        20.0,
        tendon_ids=active_ids,
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )

    figure = _three_d_figure(
        points,
        active_ids,
        segments,
        section_definitions=definitions,
        transparent=True,
    )

    assert figure.layout.scene.camera.projection.type == "orthographic"
    assert figure.layout.scene.dragmode == "orbit"
    assert "3D Orthographic" in figure.layout.title.text
    tendon_traces = [trace for trace in figure.data if trace.name in active_ids]
    assert len(tendon_traces) == len(active_ids)
    assert all(len(trace.x) == 3 for trace in tendon_traces)
