from __future__ import annotations

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_sls_deflection import (
    CROSSBEAM_SLS_DEFLECTION_FINAL_RESULT_HASH_KEY,
    CROSSBEAM_SLS_DEFLECTION_FINAL_RESULT_KEY,
    CROSSBEAM_SLS_DEFLECTION_TRANSFER_RESULT_HASH_KEY,
    CROSSBEAM_SLS_DEFLECTION_TRANSFER_RESULT_KEY,
    CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY,
    FINAL_SERVICE_STAGE,
    TRANSFER_STAGE,
    build_crossbeam_deflection_stage_preparation,
    run_crossbeam_deflection_camber,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.project_geometry import CROSSBEAM_COLUMN_ROWS_KEY
from concrete_pmm_pro.ui.analysis_page import _crossbeam_sls_deflection_dashboard_state


def _columns() -> list[dict[str, object]]:
    return [
        {"Column ID": "C1", "Station s (m)": 2.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C2", "Station s (m)": 10.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C3", "Station s (m)": 18.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
    ]


def _rows(stage: str, case: str, peak: float) -> list[dict[str, object]]:
    return [
        {"Active": True, "Station s (m)": x, "Case Name": case, "Stage": stage, "Vertical displacement (mm)": d, "Source point": "", "Note": ""}
        for x, d in [(0.0, 0.0), (2.0, 0.0), (6.0, peak), (10.0, 0.0), (14.0, peak), (18.0, 0.0), (20.0, 0.0)]
    ]


def _state(*, span_basis: str = "L/360", overhang_basis: str = "Lo/180") -> dict[str, object]:
    return {
        "crossbeam_ui1_length_m": 20.0,
        CROSSBEAM_COLUMN_ROWS_KEY: _columns(),
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY: pd.DataFrame(
            _rows(TRANSFER_STAGE, "TR", 4.0) + _rows(FINAL_SERVICE_STAGE, "SERV", -8.0)
        ),
        "crossbeam_sls_deflection_limit_basis": span_basis,
        "crossbeam_sls_deflection_overhang_limit_basis": overhang_basis,
    }


def _store_current_result(state: dict[str, object], stage: str) -> dict[str, object]:
    prep = build_crossbeam_deflection_stage_preparation(state, stage)
    assert prep.ready
    result = run_crossbeam_deflection_camber(prep)
    if stage == TRANSFER_STAGE:
        state[CROSSBEAM_SLS_DEFLECTION_TRANSFER_RESULT_KEY] = result
        state[CROSSBEAM_SLS_DEFLECTION_TRANSFER_RESULT_HASH_KEY] = prep.fingerprint
    else:
        state[CROSSBEAM_SLS_DEFLECTION_FINAL_RESULT_KEY] = result
        state[CROSSBEAM_SLS_DEFLECTION_FINAL_RESULT_HASH_KEY] = prep.fingerprint
    return result


def test_d30_final_service_runtime_state_matches_current_review_result() -> None:
    state = _state(span_basis="Review only", overhang_basis="Review only")
    state["_nav_crossbeam_sls_deflection_stage"] = "At Final Service"
    result = _store_current_result(state, FINAL_SERVICE_STAGE)
    assert result["status"] == "REVIEW"
    assert _crossbeam_sls_deflection_dashboard_state(state) == (
        "REVIEW",
        "At Final Service current stage-owned result",
        "warning",
    )


def test_d30_final_service_runtime_state_matches_current_pass_result() -> None:
    state = _state(span_basis="L/360", overhang_basis="Lo/180")
    state["_nav_crossbeam_sls_deflection_stage"] = "At Final Service"
    result = _store_current_result(state, FINAL_SERVICE_STAGE)
    assert result["status"] == "PASS"
    assert _crossbeam_sls_deflection_dashboard_state(state) == (
        "PASS",
        "At Final Service current stage-owned result",
        "ready",
    )


def test_d30_runtime_state_rejects_previous_final_result_after_criterion_change() -> None:
    state = _state(span_basis="L/360", overhang_basis="Lo/180")
    state["_nav_crossbeam_sls_deflection_stage"] = "At Final Service"
    _store_current_result(state, FINAL_SERVICE_STAGE)
    state["crossbeam_sls_deflection_limit_basis"] = "L/480"
    value, detail, style = _crossbeam_sls_deflection_dashboard_state(state)
    assert value == "STALE"
    assert "does not match current inputs" in detail
    assert style == "warning"


def test_d30_transfer_runtime_state_is_stage_owned_response() -> None:
    state = _state()
    state["_nav_crossbeam_sls_deflection_stage"] = "At Transfer"
    _store_current_result(state, TRANSFER_STAGE)
    assert _crossbeam_sls_deflection_dashboard_state(state) == (
        "RESPONSE",
        "At Transfer current stage-owned response",
        "info",
    )


def test_d30_workspace_reruns_after_storing_stage_result_for_same_render_sync() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
    workspace = source[source.index("def _render_crossbeam_sls_deflection_workspace"):source.index("def render_analysis_sls_deflection_camber")]
    assert 'rerun = getattr(st, "rerun", None)' in workspace
    assert "top Runtime state is rebuilt from the new current fingerprint/result" in workspace
