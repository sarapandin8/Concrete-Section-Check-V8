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
    _crossbeam_combined_vt_decision_rows,
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


def test_overview_decision_rows_use_each_components_own_governing_source() -> None:
    result_df = pd.DataFrame(
        [
            {
                "Station type": "IMPORTED",
                "Case": "ULS-01",
                "Segment": "S2",
                "Station s (m)": 6.0,
                "Stress D/C value": 0.427,
                "Stress status": "PASS",
                "Transverse D/C value": 0.272,
                "Transverse status": "PASS",
                "(Av+2At)/s adopted required mm2/mm": 0.921,
                "Unique transverse provided/s mm2/mm": 3.393,
                "Al minimum D/C value": 2.262,
                "Al minimum required mm2": 22741.0,
                "Al provided mm2": 10053.0,
                "Flexure+torsion D/C value": 0.094,
                "Flexure+torsion status": "PASS",
                "M3 kN-m": 2000.0,
                "Flexure+torsion phiMn kN-m": 21302.3,
            },
            {
                "Station type": "IMPORTED",
                "Case": "ULS-01",
                "Segment": "S2",
                "Station s (m)": 8.0,
                "Stress D/C value": 0.454,
                "Stress status": "PASS",
                "Transverse D/C value": 0.180,
                "Transverse status": "PASS",
                "(Av+2At)/s adopted required mm2/mm": 0.611,
                "Unique transverse provided/s mm2/mm": 3.393,
                "Al minimum D/C value": 1.800,
                "Al minimum required mm2": 18095.0,
                "Al provided mm2": 10053.0,
                "Flexure+torsion D/C value": 0.125,
                "Flexure+torsion status": "PASS",
                "M3 kN-m": 2500.0,
                "Flexure+torsion phiMn kN-m": 20000.0,
            },
        ]
    )

    rows = _crossbeam_combined_vt_decision_rows(result_df, joint_review_count=5)
    by_check = {str(row["Check"]): row for row in rows}

    assert by_check["Section-size interaction"]["D/C"] == "0.454"
    assert by_check["Combined transverse reinforcement Av/s + 2At/s"]["D/C"] == "0.272"
    assert by_check["Minimum longitudinal torsion reinforcement Aℓ"]["D/C"] == "2.262"
    assert by_check["Direct flexure + torsional longitudinal tension"]["D/C"] == "0.125"
    assert by_check["Direct flexure + torsional longitudinal tension"]["Required"] == "Mu = 2,500.0 kN·m"
    assert by_check["Physical-joint V+T transfer"]["Status"] == "NOT EVALUATED"


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
    assert '"Joint review",' not in source
    assert "Physical-joint one-sided evidence — NOT EVALUATED" in source
    assert "_make_crossbeam_uls_combined_vt_component_figure" in source
    assert "_make_crossbeam_uls_combined_vt_joint_review_figure" not in source
    assert "_make_crossbeam_uls_combined_vt_figure(" not in source


def test_segmental_combined_vt_separates_prepared_support_overlap_from_decision_rows(combined_result) -> None:
    _, preparation, result_df, result = combined_result

    prepared_rows = list(preparation.shear.rows)
    prepared_support = [row for row in prepared_rows if bool(getattr(row, "generated_support_check", False))]
    overlap_review = [
        row for row in prepared_support
        if str(getattr(row, "location_type", "")) == "PHYSICAL SEGMENT JOINT"
    ]

    assert len(prepared_rows) == 42
    assert len(prepared_support) == 12
    assert len(overlap_review) == 2
    assert int(result["total_checks"]) == 40
    assert int(result["sectional_checks"]) == 30
    assert int(result["generated_support_checks"]) == 10
    assert int(result["joint_side_checks"]) == 10
    assert int(result["joint_review_count"]) == 5
    assert len(result_df[result_df["Station type"].astype(str) == "PHYSICAL JOINT SIDE"]) == 10


def test_combined_vt_ui_uses_calculation_source_wording_not_verified_overclaim() -> None:
    source = inspect.getsource(_render_crossbeam_uls_combined_vt_workspace)
    assert "Adopted calculation source · see station audit" in source
    assert "Adopted verified source" not in source
    assert "support/joint overlap row(s) are excluded from sectional decision and retained as audit-only physical-joint evidence" in source
