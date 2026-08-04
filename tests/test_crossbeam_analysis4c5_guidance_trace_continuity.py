from __future__ import annotations

import inspect

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import (
    build_crossbeam_uls_combined_vt_preparation,
    run_crossbeam_uls_combined_vt,
)
from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_combined_vt_plot_groups,
    _crossbeam_combined_vt_view_guidance,
    _make_crossbeam_uls_combined_vt_component_figure,
    _render_crossbeam_uls_combined_vt_workspace,
)
from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state


def _result_context():
    state, segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_combined_vt_preparation(state)
    result = run_crossbeam_uls_combined_vt(preparation)
    return segments, preparation, pd.DataFrame(result["rows"])


def test_every_combined_view_has_visible_check_reading_and_exclusion_guidance() -> None:
    for component in ("stress", "transverse", "longitudinal", "joint"):
        guidance = _crossbeam_combined_vt_view_guidance(component)
        assert guidance["title"].startswith("What this")
        assert guidance["verifies"]
        assert guidance["read"]
        assert guidance["excludes"]

    source = inspect.getsource(_render_crossbeam_uls_combined_vt_workspace)
    assert "Section-size interaction" in source
    assert "How to read it" in source
    assert "Not covered by this view" in source
    assert "_crossbeam_combined_vt_view_guidance" in source


def test_connected_groups_include_support_checks_but_never_cross_support_interior() -> None:
    _, preparation, result_df = _result_context()
    groups = _crossbeam_combined_vt_plot_groups(
        result_df,
        list(preparation.support_footprints),
        include_support_checks=True,
    )
    x_groups = [tuple(pd.to_numeric(group["__x"]).astype(float)) for group in groups]

    # C1 left exterior / h/2 / face are connected, and the opposite face starts a new trace.
    assert any(group == (0.0, 1.0, 1.75) for group in x_groups)
    assert any(group == (3.75, 4.0) for group in x_groups)
    assert not any(1.75 in group and 3.75 in group for group in x_groups)

    # C3 behaves the same way near the right end.
    assert any(group == (26.0, 26.25) for group in x_groups)
    assert any(group == (28.25, 29.0, 30.0) for group in x_groups)
    assert not any(26.25 in group and 28.25 in group for group in x_groups)


def test_stress_and_transverse_traces_use_evaluated_support_points_for_visual_continuity() -> None:
    segments, preparation, result_df = _result_context()
    for component, trace_name in (("stress", "Stress D/C"), ("transverse", "Transverse D/C")):
        figure = _make_crossbeam_uls_combined_vt_component_figure(
            result_df,
            list(preparation.support_footprints),
            segments,
            component=component,
        )
        traces = [trace for trace in figure.data if str(trace.name) == trace_name]
        assert traces
        x_groups = [tuple(float(value) for value in trace.x) for trace in traces]
        assert any(group == (0.0, 1.0, 1.75) for group in x_groups)
        assert any(group == (3.75, 4.0) for group in x_groups)
        assert not any(1.75 in group and 3.75 in group for group in x_groups)


def test_longitudinal_view_marks_below_threshold_segments_as_not_applicable() -> None:
    segments, preparation, result_df = _result_context()
    figure = _make_crossbeam_uls_combined_vt_component_figure(
        result_df,
        list(preparation.support_footprints),
        segments,
        component="longitudinal",
    )
    annotations = [str(annotation.text) for annotation in figure.layout.annotations]
    na_annotations = [item for item in annotations if "Aℓ N/A" in item]
    assert len(na_annotations) == 4
    assert all("below torsion threshold" in item for item in na_annotations)

    longitudinal_traces = [trace for trace in figure.data if str(trace.name) == "Longitudinal D/C"]
    assert longitudinal_traces
    trace_x = {float(value) for trace in longitudinal_traces for value in trace.x}
    assert trace_x == {6.0, 8.0, 10.0, 20.0, 22.0, 24.0}
