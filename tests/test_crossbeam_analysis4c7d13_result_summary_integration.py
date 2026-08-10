from __future__ import annotations

import inspect

from concrete_pmm_pro.analysis.crossbeam_uls import (
    CROSSBEAM_ULS_RESULT_HASH_KEY,
    CROSSBEAM_ULS_RESULT_KEY,
    build_crossbeam_uls_flexure_preparation,
    run_crossbeam_uls_flexure,
)
from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import (
    CROSSBEAM_ULS_COMBINED_VT_RESULT_HASH_KEY,
    CROSSBEAM_ULS_COMBINED_VT_RESULT_KEY,
    build_crossbeam_uls_combined_vt_preparation,
    run_crossbeam_uls_combined_vt,
)
from concrete_pmm_pro.analysis.crossbeam_uls_shear import (
    CROSSBEAM_ULS_SHEAR_RESULT_HASH_KEY,
    CROSSBEAM_ULS_SHEAR_RESULT_KEY,
    build_crossbeam_uls_shear_preparation,
    run_crossbeam_uls_shear,
)
from concrete_pmm_pro.analysis.crossbeam_uls_torsion import (
    CROSSBEAM_ULS_TORSION_RESULT_HASH_KEY,
    CROSSBEAM_ULS_TORSION_RESULT_KEY,
    build_crossbeam_uls_torsion_preparation,
    run_crossbeam_uls_torsion,
)
from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state
from tests.test_crossbeam_analysis4c6b_station_geometry import _cip_ready_state

import app


def _store_all_crossbeam_uls(state: dict[str, object]) -> dict[str, object]:
    state["analysis_mode_settings"] = AnalysisModeSettings(member_type="portal_frame_crossbeam")

    flexure_preparation = build_crossbeam_uls_flexure_preparation(state)
    assert flexure_preparation.ready, flexure_preparation.errors
    flexure = run_crossbeam_uls_flexure(flexure_preparation)
    state[CROSSBEAM_ULS_RESULT_KEY] = flexure
    state[CROSSBEAM_ULS_RESULT_HASH_KEY] = flexure_preparation.fingerprint

    shear_preparation = build_crossbeam_uls_shear_preparation(state)
    assert shear_preparation.ready, shear_preparation.errors
    shear = run_crossbeam_uls_shear(shear_preparation)
    state[CROSSBEAM_ULS_SHEAR_RESULT_KEY] = shear
    state[CROSSBEAM_ULS_SHEAR_RESULT_HASH_KEY] = shear_preparation.fingerprint

    torsion_preparation = build_crossbeam_uls_torsion_preparation(state)
    assert torsion_preparation.ready, torsion_preparation.errors
    torsion = run_crossbeam_uls_torsion(torsion_preparation)
    state[CROSSBEAM_ULS_TORSION_RESULT_KEY] = torsion
    state[CROSSBEAM_ULS_TORSION_RESULT_HASH_KEY] = torsion_preparation.fingerprint

    combined_preparation = build_crossbeam_uls_combined_vt_preparation(state)
    assert combined_preparation.ready, combined_preparation.errors
    combined = run_crossbeam_uls_combined_vt(combined_preparation)
    state[CROSSBEAM_ULS_COMBINED_VT_RESULT_KEY] = combined
    state[CROSSBEAM_ULS_COMBINED_VT_RESULT_HASH_KEY] = combined_preparation.fingerprint
    return state


def test_cip_crossbeam_result_summary_reads_all_four_stored_uls_packages() -> None:
    state = _store_all_crossbeam_uls(_cip_ready_state())

    rows = app._results_crossbeam_uls_summary_rows(state)
    assert [row["Check"] for row in rows] == ["Flexure", "Shear", "Torsion", "Shear + Torsion"]
    assert [row["Status"] for row in rows] == ["PASS", "PASS", "BELOW THRESHOLD", "PASS"]
    assert all(row["Module"] == "ULS Crossbeam" for row in rows)
    assert all(row["__calculated"] for row in rows)
    assert all("Cast-in-Place" in row["Scope"] for row in rows)
    assert rows[0]["Governing Check"] == "Direct P–M3 flexure"
    assert rows[0]["D/C / Util."] != "-"
    assert rows[2]["Governing Check"] == "Torsion threshold screen"
    assert rows[3]["Governing Check"] == "Shear-only section-size check"
    assert "NOT APPLICABLE" in rows[3]["Scope"]

    calculated, total, missing = app._results_active_uls_completion(state)
    assert (calculated, total, missing) == (4, 4, [])


def test_crossbeam_result_summary_replaces_beam_girder_route_for_active_workflow() -> None:
    state = _store_all_crossbeam_uls(_cip_ready_state())
    state["_beam_girder_uls_manual_calculation_cache"] = {
        "Flexure": {"flexure_preview_df": object()},
    }

    governing = app._results_governing_rows(state)
    uls_rows = [row for row in governing if str(row.get("Module", "")).startswith("ULS")]
    assert len(uls_rows) == 4
    assert {row["Module"] for row in uls_rows} == {"ULS Crossbeam"}
    assert {row["Check"] for row in uls_rows} == {"Flexure", "Shear", "Torsion", "Shear + Torsion"}


def test_segmental_crossbeam_summary_preserves_sectional_failure_and_joint_scope() -> None:
    state, _segments = _mixed_30m_state()
    state = _store_all_crossbeam_uls(state)

    rows = {row["Check"]: row for row in app._results_crossbeam_uls_summary_rows(state)}
    assert rows["Flexure"]["Status"] == "PASS"
    assert "tendon-only" in rows["Flexure"]["Scope"].lower()

    assert rows["Shear"]["Status"] in {"PASS", "REVIEW"}
    assert "physical-joint" in rows["Shear"]["Scope"].lower()

    assert rows["Torsion"]["Status"] == "FAIL"
    assert rows["Torsion"]["Governing Check"] == "Minimum longitudinal torsion reinforcement Aℓ"
    assert float(rows["Torsion"]["D/C / Util."]) > 1.0

    assert rows["Shear + Torsion"]["Status"] == "FAIL"
    assert rows["Shear + Torsion"]["Governing Check"] == "Minimum longitudinal torsion reinforcement Aℓ"
    assert "NOT EVALUATED" in rows["Shear + Torsion"]["Scope"]


def test_construction_type_switch_marks_dormant_crossbeam_results_stale() -> None:
    state = _store_all_crossbeam_uls(_cip_ready_state())
    state[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] = "Precast Segmental"

    rows = app._results_crossbeam_uls_summary_rows(state)
    assert {row["Status"] for row in rows} == {"STALE"}
    assert all(not row["__calculated"] for row in rows)
    assert all("Stored: Cast-in-Place; active: Precast Segmental" in row["Scope"] for row in rows)

    calculated, total, missing = app._results_active_uls_completion(state)
    assert calculated == 0
    assert total == 4
    assert missing == ["Flexure", "Shear", "Torsion", "Shear + Torsion"]

    governing = app._results_governing_rows(state)
    handoff = app._results_report_handoff_state(state, governing)
    assert handoff["value"] == "Not ready"
    assert "stale/inactive" in handoff["detail"]


def test_crossbeam_result_summary_is_read_only_and_does_not_prepare_or_run_solvers() -> None:
    source = inspect.getsource(app._results_crossbeam_uls_summary_rows) + inspect.getsource(app._results_crossbeam_summary_row)
    assert "run_crossbeam_uls" not in source
    assert "build_crossbeam_uls" not in source
    assert "Calculate" not in source
    assert "_results_crossbeam_stored_result" in source


def test_crossbeam_uls_summary_dashboard_is_explicitly_read_only() -> None:
    source = inspect.getsource(app._render_results_crossbeam_uls_dashboard)
    assert '"Runtime mode"' in source
    assert '"READ-ONLY"' in source
    assert "does not rerun Crossbeam solvers" in source
    assert "Joint semantics" in source
