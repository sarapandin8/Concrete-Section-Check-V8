from __future__ import annotations

import inspect

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import (
    build_crossbeam_uls_combined_vt_preparation,
    run_crossbeam_uls_combined_vt,
)
from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_combined_vt_decision_rows,
    _render_crossbeam_uls_combined_vt_workspace,
)
from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state


def test_precast_joint_transfer_is_not_evaluated_and_audit_only() -> None:
    state, _segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_combined_vt_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_combined_vt(preparation)
    rows = pd.DataFrame(result["rows"])

    assert result["joint_review_count"] == 5
    assert result["joint_transfer_status"] == "NOT EVALUATED"
    joint_rows = rows[rows["Station type"].astype(str) == "PHYSICAL JOINT SIDE"]
    assert len(joint_rows.index) == 10
    assert set(joint_rows["Status"].astype(str)) == {"NOT EVALUATED"}
    assert joint_rows["Overall D/C value"].isna().all()

    decision_rows = _crossbeam_combined_vt_decision_rows(
        rows,
        joint_review_count=int(result["joint_review_count"]),
        construction_method="Precast Segmental",
    )
    by_check = {str(row["Check"]): row for row in decision_rows}
    joint = by_check["Physical-joint V+T transfer"]
    assert joint["Status"] == "NOT EVALUATED"
    assert joint["D/C"] == "-"
    assert "does not calculate a joint D/C" in str(joint["Required action"])


def test_joint_locations_do_not_downgrade_passing_sectional_result() -> None:
    state, _segments = _mixed_30m_state()
    for row in state["crossbeam_uls_loads_table"]:
        row["T"] = 0.0
    preparation = build_crossbeam_uls_combined_vt_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_combined_vt(preparation)

    assert result["joint_review_count"] == 5
    assert result["joint_transfer_status"] == "NOT EVALUATED"
    assert result["sectional_status"] == "PASS"
    assert result["status"] == "PASS"


def test_combined_warning_traceability_matches_detailed_calculation_source() -> None:
    state, _segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_combined_vt_preparation(state)
    warnings = list(preparation.warnings)

    assert not any(
        "actual provided reinforcement quantities are not defined yet" in warning
        for warning in warnings
    )
    assert any(
        "Combined V+T uses the adopted detailed longitudinal bar layout for provided Aℓ" in warning
        for warning in warnings
    )
    assert any("transverse provided capacity comes from the adopted transverse template" in warning for warning in warnings)


def test_workspace_retires_joint_review_tab_but_keeps_collapsed_audit_evidence() -> None:
    source = inspect.getsource(_render_crossbeam_uls_combined_vt_workspace)

    assert '"Section-size interaction",' in source
    assert '"Transverse reinforcement",' in source
    assert '"Longitudinal reinforcement",' in source
    assert '"Joint review",' not in source
    assert "Physical-joint one-sided evidence — NOT EVALUATED" in source
    assert "outside the current milestone" in source
    assert "audit-only physical-joint evidence" in source
