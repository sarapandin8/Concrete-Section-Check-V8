from __future__ import annotations

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import (
    build_crossbeam_uls_combined_vt_preparation,
    run_crossbeam_uls_combined_vt,
)
from concrete_pmm_pro.analysis.crossbeam_uls_torsion import (
    build_crossbeam_uls_torsion_preparation,
    run_crossbeam_uls_torsion,
)
from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_combined_vt_applicability_state,
    _crossbeam_combined_vt_component_summary,
    _crossbeam_combined_vt_decision_rows,
    _crossbeam_governing_component_summary,
    _make_crossbeam_uls_combined_vt_component_figure,
)
from tests.test_crossbeam_analysis4c6b_station_geometry import _cip_ready_state


@pytest.fixture(scope="module")
def cip_below_threshold_result():
    state = _cip_ready_state()
    preparation = build_crossbeam_uls_combined_vt_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_combined_vt(preparation)
    return state, preparation, pd.DataFrame(result["rows"]), result


def _limit_trace(figure):
    return next(trace for trace in figure.data if str(trace.name) == "Limit = 1.0")


def test_combined_rows_expose_threshold_evidence(cip_below_threshold_result) -> None:
    _, _, result_df, _ = cip_below_threshold_result
    assert "Torsion threshold D/C value" in result_df
    assert "phiTth kN-m" in result_df
    assert result_df["Torsion threshold D/C value"].notna().all()
    assert result_df["phiTth kN-m"].notna().all()

    state = _crossbeam_combined_vt_applicability_state(result_df)
    assert state["all_torsion_below_threshold"] is True
    assert state["all_transverse_zero"] is True
    assert int(state["torsion_required_rows"]) == 0
    assert float(state["threshold_utilization"]) < 1.0


@pytest.mark.parametrize("component", ["stress", "transverse", "longitudinal"])
def test_component_acceptance_line_is_full_span_and_not_broken(
    component: str,
    cip_below_threshold_result,
) -> None:
    state, preparation, result_df, result = cip_below_threshold_result
    figure = _make_crossbeam_uls_combined_vt_component_figure(
        result_df,
        list(preparation.support_footprints),
        state["crossbeam_ui1_segment_layout_rows"],
        component=component,
        construction_method="Cast-in-Place",
        member_length_m=float(result["member_length_m"]),
    )
    limit = _limit_trace(figure)
    assert list(limit.x) == pytest.approx([0.0, float(result["member_length_m"])])
    assert list(limit.y) == pytest.approx([1.0, 1.0])
    assert None not in list(limit.x)
    assert None not in list(limit.y)


def test_zero_transverse_view_is_explicit_not_required(cip_below_threshold_result) -> None:
    state, preparation, result_df, result = cip_below_threshold_result
    figure = _make_crossbeam_uls_combined_vt_component_figure(
        result_df,
        list(preparation.support_footprints),
        state["crossbeam_ui1_segment_layout_rows"],
        component="transverse",
        construction_method="Cast-in-Place",
        member_length_m=float(result["member_length_m"]),
    )
    names = [str(trace.name) for trace in figure.data]
    assert "Transverse D/C" in names
    assert "Limit = 1.0" in names
    assert not any(name.startswith("Gov.") for name in names)
    assert float(figure.layout.yaxis.range[0]) < 0.0
    annotations = [str(item.text) for item in figure.layout.annotations]
    assert any("NOT REQUIRED AT ALL ELIGIBLE STATIONS" in text for text in annotations)
    assert "NOT REQUIRED" in str(figure.layout.title.text)

    row = result_df.iloc[0]
    summary = _crossbeam_combined_vt_component_summary(
        row, "transverse", result_df=result_df
    )
    assert summary["status"] == "NOT REQUIRED"
    assert summary["dc"] == pytest.approx(0.0)


def test_longitudinal_view_shows_threshold_applicability_instead_of_blank_chart(
    cip_below_threshold_result,
) -> None:
    state, preparation, result_df, result = cip_below_threshold_result
    figure = _make_crossbeam_uls_combined_vt_component_figure(
        result_df,
        list(preparation.support_footprints),
        state["crossbeam_ui1_segment_layout_rows"],
        component="longitudinal",
        construction_method="Cast-in-Place",
        member_length_m=float(result["member_length_m"]),
    )
    names = [str(trace.name) for trace in figure.data]
    assert "Tu/φTth activation" in names
    assert "Longitudinal D/C" not in names
    assert "Limit = 1.0" in names
    annotations = [str(item.text) for item in figure.layout.annotations]
    assert any("LONGITUDINAL TORSION REINFORCEMENT — NOT REQUIRED" in text for text in annotations)
    assert "NOT REQUIRED" in str(figure.layout.title.text)

    applicability = _crossbeam_combined_vt_applicability_state(result_df)
    summary = _crossbeam_combined_vt_component_summary(
        applicability["threshold_governing_row"],
        "longitudinal",
        result_df=result_df,
    )
    assert summary["status"] == "NOT REQUIRED"
    assert float(summary["dc"]) < 1.0
    assert "not activated" in str(summary["required"]).lower()


def test_section_size_semantics_switch_to_shear_only(cip_below_threshold_result) -> None:
    _, _, result_df, result = cip_below_threshold_result
    summary = _crossbeam_combined_vt_component_summary(
        result["governing_row"], "stress", result_df=result_df
    )
    assert summary["label"] == "Shear-only section-size check"
    assert summary["required"] == "Shear section-size demand"


def test_cip_joint_review_is_not_applicable(cip_below_threshold_result) -> None:
    _, _, result_df, _ = cip_below_threshold_result
    rows = _crossbeam_combined_vt_decision_rows(
        result_df,
        joint_review_count=0,
        construction_method="Cast-in-Place",
    )
    by_check = {str(row["Check"]): row for row in rows}
    assert by_check["Minimum longitudinal torsion reinforcement Aℓ"]["Status"] == "NOT REQUIRED"
    assert by_check["Direct flexure + torsional longitudinal tension"]["Status"] == "NOT REQUIRED"
    assert by_check["Physical-joint V+T transfer"]["Status"] == "NOT APPLICABLE"


def test_standalone_below_threshold_summary_uses_threshold_utilization() -> None:
    state = _cip_ready_state()
    preparation = build_crossbeam_uls_torsion_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_torsion(preparation)
    summary = _crossbeam_governing_component_summary(
        result["sectional_governing_row"], combined=False
    )
    assert summary["label"] == "Torsion threshold screen"
    assert summary["short_label"] == "Tu/φTth"
    assert float(summary["dc"]) < 1.0
    assert "No sectional torsion-design action" in str(summary["action"])
