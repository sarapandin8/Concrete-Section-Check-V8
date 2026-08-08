from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.analysis.crossbeam_uls_torsion import (
    build_crossbeam_uls_torsion_preparation,
    run_crossbeam_uls_torsion,
)
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json


_FIXTURE = Path(__file__).with_name("data") / "crossbeam_analysis4_direct_solver_benchmark.json"


def _benchmark_state() -> dict[str, object]:
    state: dict[str, object] = {}
    apply_project_to_session_state(project_from_json(_FIXTURE.read_text(encoding="utf-8")), state)
    return state


def test_torsion_result_rewords_blank_template_summary_without_disowning_detailed_al_source() -> None:
    preparation = build_crossbeam_uls_torsion_preparation(_benchmark_state())
    assert preparation.ready, preparation.errors
    assert any("actual provided reinforcement quantities are not defined yet" in warning for warning in preparation.warnings)

    result = run_crossbeam_uls_torsion(preparation)
    warnings = [str(item) for item in result.get("warnings") or []]

    assert not any("actual provided reinforcement quantities are not defined yet" in warning for warning in warnings)
    assert any(
        "summary Rebar Template quantity fields are unset" in warning
        and "adopted detailed longitudinal bar layout" in warning
        and "provided Aℓ" in warning
        for warning in warnings
    )


def test_torsion_scope_keeps_sectional_fail_distinct_from_overall_completion_review() -> None:
    preparation = build_crossbeam_uls_torsion_preparation(_benchmark_state())
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_torsion(preparation)
    scope = str(result.get("scope") or "")

    assert "keep a design-required standalone result at overall REVIEW" not in scope
    assert "They do not downgrade a standalone sectional FAIL" in scope
    assert "overall Crossbeam ULS adoption remains REVIEW/INCOMPLETE" in scope


def test_torsion_provided_card_does_not_overcertify_source() -> None:
    source = (Path(__file__).parents[1] / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
    assert '"detail": "Adopted calculation source · see station audit"' in source
    assert '"detail": "Adopted verified reinforcement / capacity source"' not in source
