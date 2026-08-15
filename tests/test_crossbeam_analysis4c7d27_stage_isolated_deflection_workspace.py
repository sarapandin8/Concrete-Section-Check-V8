from __future__ import annotations

from pathlib import Path

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
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.project_geometry import CROSSBEAM_COLUMN_ROWS_KEY


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


def _state() -> dict[str, object]:
    return {
        "crossbeam_ui1_length_m": 20.0,
        CROSSBEAM_COLUMN_ROWS_KEY: _columns(),
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY: pd.DataFrame(
            _rows(TRANSFER_STAGE, "TR", 4.0) + _rows(FINAL_SERVICE_STAGE, "SERV", -8.0)
        ),
        "crossbeam_sls_deflection_limit_basis": "L/360",
        "crossbeam_sls_deflection_overhang_limit_basis": "Lo/180",
    }


def test_d27_stage_preparations_are_source_and_criterion_isolated() -> None:
    state = _state()
    transfer = build_crossbeam_deflection_stage_preparation(state, TRANSFER_STAGE)
    final = build_crossbeam_deflection_stage_preparation(state, FINAL_SERVICE_STAGE)
    assert transfer.ready and final.ready
    assert {row["Stage"] for row in transfer.rows} == {TRANSFER_STAGE}
    assert {row["Stage"] for row in final.rows} == {FINAL_SERVICE_STAGE}

    transfer_hash = transfer.fingerprint
    final_hash = final.fingerprint
    state["crossbeam_sls_deflection_limit_basis"] = "L/480"
    assert build_crossbeam_deflection_stage_preparation(state, TRANSFER_STAGE).fingerprint == transfer_hash
    assert build_crossbeam_deflection_stage_preparation(state, FINAL_SERVICE_STAGE).fingerprint != final_hash

    table = state[CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY].copy()
    table.loc[table["Stage"] == FINAL_SERVICE_STAGE, "Vertical displacement (mm)"] *= 1.25
    state[CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY] = table
    assert build_crossbeam_deflection_stage_preparation(state, TRANSFER_STAGE).fingerprint == transfer_hash


def test_d27_stage_result_keys_are_independent() -> None:
    assert CROSSBEAM_SLS_DEFLECTION_TRANSFER_RESULT_KEY != CROSSBEAM_SLS_DEFLECTION_FINAL_RESULT_KEY
    assert CROSSBEAM_SLS_DEFLECTION_TRANSFER_RESULT_HASH_KEY != CROSSBEAM_SLS_DEFLECTION_FINAL_RESULT_HASH_KEY


def test_d27_ui_has_one_stage_selector_and_no_nested_stage_tabs() -> None:
    source = (Path(__file__).resolve().parents[1] / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
    workspace = source[source.index("def _render_crossbeam_sls_deflection_workspace"):source.index("def render_analysis_sls_deflection_camber")]
    assert 'render_active_choice(\n        "Deflection / Camber stage"' in workspace
    assert 'st.tabs(["At Transfer source", "At Final Service source"])' not in workspace
    assert 'st.tabs(["At Transfer", "At Final Service"])' not in workspace
    assert "Run Transfer Camber Review" in workspace
    assert "Run Final Service Deflection Check" in workspace
    assert "Final Service deflection criteria" in workspace
    assert "AT TRANSFER — camber/deflection response review only" in workspace
