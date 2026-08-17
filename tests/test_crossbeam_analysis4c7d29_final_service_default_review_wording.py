from __future__ import annotations

from types import SimpleNamespace

from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_final_service_acceptance_detail,
    _crossbeam_final_service_criterion_caption,
    _crossbeam_final_service_review_reason,
)


def test_d29_criterion_caption_distinguishes_current_selection_from_new_project_default() -> None:
    review = _crossbeam_final_service_criterion_caption(
        "Review only",
        "L/360",
        verify_text="verify project/serviceability requirements",
    )
    assert "Current project selection: Review only" in review
    assert "new-project general-practice default: L/360" in review

    default = _crossbeam_final_service_criterion_caption(
        "L/360",
        "L/360",
        verify_text="verify project/serviceability requirements",
    )
    assert "Current project selection: L/360" in default
    assert "new-project general-practice default" in default
    assert "default: L/360" not in default


def test_d29_overhang_caption_keeps_geometry_context() -> None:
    text = _crossbeam_final_service_criterion_caption(
        "Review only",
        "Lo/180",
        verify_text="verify project/serviceability requirements",
        geometry_text="Left Lo=2.750 m · Right Lo=2.750 m",
    )
    assert "new-project general-practice default: Lo/180" in text
    assert "Left Lo=2.750 m" in text
    assert "Right Lo=2.750 m" in text


def test_d29_acceptance_detail_does_not_call_review_only_a_default() -> None:
    review = SimpleNamespace(
        left_overhang_m=2.75,
        right_overhang_m=2.75,
        limit_basis="Review only",
        overhang_limit_basis="Review only",
    )
    assert _crossbeam_final_service_acceptance_detail(review) == (
        "current project selections preserved; new-project defaults: L/360 · Lo/180"
    )

    default = SimpleNamespace(
        left_overhang_m=2.75,
        right_overhang_m=2.75,
        limit_basis="L/360",
        overhang_limit_basis="Lo/180",
    )
    assert _crossbeam_final_service_acceptance_detail(default) == (
        "general-practice new-project defaults; verify project criteria"
    )


def test_d29_review_reason_is_visible_and_region_specific() -> None:
    result = {
        "status": "REVIEW",
        "span_rows": [
            {"Stage": "Final service stage", "Status": "REVIEW", "Region type": "SUPPORT SPAN"},
        ],
        "overhang_rows": [
            {"Stage": "Final service stage", "Status": "REVIEW", "Region type": "OVERHANG"},
        ],
    }
    assert _crossbeam_final_service_review_reason(result) == (
        "No active support-span L/n or overhang Lo/n acceptance criterion"
    )

    pass_result = {"status": "PASS", "span_rows": [], "overhang_rows": []}
    assert _crossbeam_final_service_review_reason(pass_result) == "stored stage-owned deflection check"
