from __future__ import annotations

import inspect

import app
from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state
from tests.test_crossbeam_analysis4c7d13_result_summary_integration import _store_all_crossbeam_uls


def test_segmental_result_summary_actions_and_critical_tie_are_deterministic() -> None:
    state, _segments = _mixed_30m_state()
    state = _store_all_crossbeam_uls(state)

    summary = {row["Check"]: row for row in app._results_crossbeam_uls_summary_rows(state)}
    assert summary["Flexure"]["Status"] == "PASS"
    assert summary["Flexure"]["Required Action"].startswith("No sectional flexure action required.")

    governing = app._results_governing_rows(state)
    by_check = {row["Check"]: row for row in governing if row.get("Module") == "ULS Crossbeam"}
    assert by_check["Shear"]["Required Action"].startswith("Sectional shear is PASS")
    assert "Increase developed outer-cage-associated longitudinal bars" in by_check["Torsion"]["Required Action"]
    assert "do not add Aℓ to As a second time" in by_check["Shear + Torsion"]["Required Action"]

    actions = app._results_required_action_rows(state, governing)
    action_by_issue = {row["Issue"]: row["Required Action"] for row in actions}
    assert action_by_issue["Shear — REVIEW"].startswith("Sectional shear is PASS")
    assert "Increase developed outer-cage-associated longitudinal bars" in action_by_issue["Torsion — FAIL"]
    assert "do not add Aℓ to As a second time" in action_by_issue["Shear + Torsion — FAIL"]
    assert "Analysis → ULS Strength" not in action_by_issue["Torsion — FAIL"]

    critical = app._results_critical_row(governing)
    assert critical is not None
    assert critical["Check"] == "Shear + Torsion"
    assert critical["D/C / Util."] == "2.262"


def test_crossbeam_result_completeness_copy_does_not_overstate_joint_scope() -> None:
    state, _segments = _mixed_30m_state()
    state = _store_all_crossbeam_uls(state)

    cards = {card["title"]: card for card in app._results_availability_cards(state)}
    assert "Result completeness" in cards
    assert cards["Result completeness"]["value"].startswith("ULS results 4/4")
    assert "sectional ULS result packages: 4/4" in cards["Result completeness"]["detail"]

    source = inspect.getsource(app._render_results_crossbeam_uls_dashboard)
    assert '"ULS analysis results"' in source
    assert '"ULS completeness"' not in source
    assert "Stored sectional modules" in source
