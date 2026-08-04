from __future__ import annotations

import inspect

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import (
    build_crossbeam_uls_combined_vt_preparation,
    run_crossbeam_uls_combined_vt,
)
from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_combined_vt_component_governing,
    _crossbeam_combined_vt_component_summary,
    _make_crossbeam_uls_combined_vt_component_figure,
    _make_crossbeam_uls_combined_vt_joint_review_figure,
    _render_crossbeam_uls_combined_vt_workspace,
)
from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state


@pytest.fixture(scope="module")
def combined_result():
    state, segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_combined_vt_preparation(state)
    result = run_crossbeam_uls_combined_vt(preparation)
    return segments, preparation, pd.DataFrame(result["rows"]), result


@pytest.mark.parametrize(
    ("component", "trace_name", "forbidden", "title_text"),
    [
        ("stress", "Stress D/C", {"Transverse D/C", "Longitudinal D/C"}, "Section-Size Interaction"),
        ("transverse", "Transverse D/C", {"Stress D/C", "Longitudinal D/C"}, "Combined Transverse Reinforcement"),
        ("longitudinal", "Longitudinal D/C", {"Stress D/C", "Transverse D/C"}, "Longitudinal Torsion Reinforcement"),
    ],
)
def test_component_figures_show_one_engineering_meaning(
    component: str,
    trace_name: str,
    forbidden: set[str],
    title_text: str,
    combined_result,
) -> None:
    segments, preparation, result_df, _ = combined_result
    figure = _make_crossbeam_uls_combined_vt_component_figure(
        result_df,
        list(preparation.support_footprints),
        segments,
        component=component,
    )

    names = [str(trace.name) for trace in figure.data]
    assert trace_name in names
    assert "Limit = 1.0" in names
    if component != "longitudinal":
        assert "Column Face check" in names
        assert "ACI h/2 check" in names
    assert forbidden.isdisjoint(names)
    assert title_text in str(figure.layout.title.text)

    if component == "longitudinal":
        traces = [trace for trace in figure.data if str(trace.name) == trace_name]
        assert traces
        assert all(str(trace.line.shape) == "hv" for trace in traces)

    annotations = {str(annotation.text) for annotation in figure.layout.annotations}
    assert {"S1", "S2", "S3", "S4", "S5", "S6"}.issubset(annotations)
    assert {"J1", "J2", "J3", "J4", "J5"}.issubset(annotations)
    assert not any("FAIL —" in item for item in annotations)


def test_longitudinal_view_reports_exact_minimum_al_reason(combined_result) -> None:
    _, _, result_df, _ = combined_result
    row = _crossbeam_combined_vt_component_governing(result_df, "longitudinal")
    summary = _crossbeam_combined_vt_component_summary(row, "longitudinal")

    assert summary["label"] == "Minimum longitudinal torsion reinforcement Aℓ"
    assert summary["status"] == "FAIL"
    assert float(summary["dc"]) == pytest.approx(2.2621281911)
    assert summary["required"] == "22,741 mm²"
    assert summary["provided"] == "10,053 mm²"
    assert summary["shortfall"] == "12,688 mm²"


def test_joint_review_map_has_no_artificial_utilization_trace(combined_result) -> None:
    segments, preparation, result_df, _ = combined_result
    figure = _make_crossbeam_uls_combined_vt_joint_review_figure(
        result_df,
        list(preparation.support_footprints),
        segments,
    )

    names = [str(trace.name) for trace in figure.data]
    assert names == ["Crossbeam axis", "Physical joint — REVIEW"]
    assert figure.layout.yaxis.visible is False
    assert "no artificial joint D/C" in str(figure.layout.title.text)
    annotations = {str(annotation.text) for annotation in figure.layout.annotations}
    assert {"J1 REVIEW", "J2 REVIEW", "J3 REVIEW", "J4 REVIEW", "J5 REVIEW"}.issubset(annotations)


def test_workspace_uses_selective_component_views_instead_of_legacy_combined_chart() -> None:
    source = inspect.getsource(_render_crossbeam_uls_combined_vt_workspace)
    assert "Section-size interaction" in source
    assert "Transverse reinforcement" in source
    assert "Longitudinal reinforcement" in source
    assert "Joint review" in source
    assert "_make_crossbeam_uls_combined_vt_component_figure" in source
    assert "_make_crossbeam_uls_combined_vt_joint_review_figure" in source
    assert "_make_crossbeam_uls_combined_vt_figure(" not in source
