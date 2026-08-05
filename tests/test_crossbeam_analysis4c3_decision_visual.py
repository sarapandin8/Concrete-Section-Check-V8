from __future__ import annotations

import math

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import (
    build_crossbeam_uls_combined_vt_preparation,
    run_crossbeam_uls_combined_vt,
)
from concrete_pmm_pro.analysis.crossbeam_uls_torsion import run_crossbeam_uls_torsion
from concrete_pmm_pro.analysis.crossbeam_uls_shear import build_crossbeam_uls_shear_preparation
from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_governing_component_summary,
    _make_crossbeam_uls_combined_vt_figure,
    _make_crossbeam_uls_torsion_figure,
)
from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state


def _build_results():
    state, segments = _mixed_30m_state()
    torsion_preparation = build_crossbeam_uls_shear_preparation(state)
    torsion = run_crossbeam_uls_torsion(torsion_preparation)
    combined_preparation = build_crossbeam_uls_combined_vt_preparation(state)
    combined = run_crossbeam_uls_combined_vt(combined_preparation)
    return segments, torsion_preparation, torsion, combined_preparation, combined


def test_decision_summary_names_minimum_al_and_reports_required_provided_shortfall() -> None:
    _, _, torsion, _, combined = _build_results()

    torsion_summary = _crossbeam_governing_component_summary(
        torsion["sectional_governing_row"], combined=False
    )
    combined_summary = _crossbeam_governing_component_summary(
        combined["governing_row"], combined=True
    )

    for summary in (torsion_summary, combined_summary):
        assert summary["label"] == "Minimum longitudinal torsion reinforcement Aℓ"
        assert summary["short_label"] == "Aℓ,min D/C"
        assert float(summary["dc"]) == pytest.approx(2.2621281911)
        assert summary["required"] == "22,741 mm²"
        assert summary["provided"] == "10,053 mm²"
        assert summary["shortfall"] == "12,688 mm²"


def test_torsion_figure_separates_strength_marker_from_overall_failure_reason() -> None:
    segments, preparation, result, _, _ = _build_results()
    figure = _make_crossbeam_uls_torsion_figure(
        pd.DataFrame(result["rows"]),
        list(preparation.support_footprints),
        segments,
    )

    names = [str(trace.name) for trace in figure.data]
    assert "Gov. torsional-strength D/C" in names
    assert names.count("Physical joint — REVIEW") == 1
    decision_annotations = [
        str(annotation.text)
        for annotation in figure.layout.annotations
        if "Minimum longitudinal torsion reinforcement" in str(annotation.text)
    ]
    assert not decision_annotations  # decision evidence remains in cards/table, not over the plot
    segment_labels = {str(annotation.text) for annotation in figure.layout.annotations}
    assert {"S1", "S2", "S3", "S4", "S5", "S6"}.issubset(segment_labels)


def test_combined_figure_uses_segment_support_joint_and_governing_semantics() -> None:
    segments, _, _, preparation, result = _build_results()
    figure = _make_crossbeam_uls_combined_vt_figure(
        pd.DataFrame(result["rows"]),
        list(preparation.support_footprints),
        segments,
    )

    names = [str(trace.name) for trace in figure.data]
    assert "Column Face combined check" in names
    assert "ACI h/2 combined check" in names
    assert "Physical joint — REVIEW" in names
    assert "Gov. Aℓ,min D/C" in names
    assert "Gov. V+T" not in names

    longitudinal_traces = [trace for trace in figure.data if str(trace.name) == "Longitudinal D/C"]
    assert longitudinal_traces
    assert all(str(trace.line.shape) == "hv" for trace in longitudinal_traces)

    annotation_text = {str(annotation.text) for annotation in figure.layout.annotations}
    assert {"S1", "S2", "S3", "S4", "S5", "S6"}.issubset(annotation_text)
    assert {"J1 REVIEW", "J2 REVIEW", "J3 REVIEW", "J4 REVIEW", "J5 REVIEW"}.issubset(annotation_text)
    assert any("Shortfall 12,688 mm²" in value for value in annotation_text)

    y_range = list(figure.layout.yaxis.range)
    assert y_range[0] == pytest.approx(0.0)
    assert y_range[1] > 2.262

    vrects = [
        shape for shape in list(figure.layout.shapes or [])
        if str(getattr(shape, "type", "")) == "rect"
    ]
    assert vrects  # accepted s_left/s_right footprint keys are now recognized
