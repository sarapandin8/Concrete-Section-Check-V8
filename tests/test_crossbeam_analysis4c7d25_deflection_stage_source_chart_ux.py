from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_sls_deflection import (
    CROSSBEAM_SLS_DISPLACEMENT_COLUMNS,
    CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY,
    build_crossbeam_deflection_preparation,
    run_crossbeam_deflection_camber,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.project_geometry import CROSSBEAM_COLUMN_ROWS_KEY
from concrete_pmm_pro.crossbeam.station_force_contract import canonical_sls_stage


def _load_stage_merge_helpers():
    root = Path(__file__).resolve().parents[1]
    source_path = root / "concrete_pmm_pro" / "ui" / "analysis_page.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    wanted = {
        "_analysis_value_is_blank",
        "_analysis_to_bool",
        "_normalize_crossbeam_sls_displacement_source_table",
        "_merge_crossbeam_sls_displacement_stage_source",
    }
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    assert {node.name for node in nodes} == wanted
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "Any": object,
        "pd": pd,
        "canonical_sls_stage": canonical_sls_stage,
        "CROSSBEAM_SLS_DISPLACEMENT_COLUMNS": CROSSBEAM_SLS_DISPLACEMENT_COLUMNS,
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace["_merge_crossbeam_sls_displacement_stage_source"]


def _row(stage: str, case: str, x: float, d: float) -> dict[str, object]:
    return {
        "Active": True,
        "Station s (m)": x,
        "Case Name": case,
        "Stage": stage,
        "Vertical displacement (mm)": d,
        "Source point": f"N{x:g}",
        "Note": "verified",
    }


def test_d25_replacing_final_service_source_preserves_transfer_source() -> None:
    merge = _load_stage_merge_helpers()
    current = pd.DataFrame(
        [
            _row("Transfer stage", "TR", 0.0, 0.0),
            _row("Transfer stage", "TR", 20.0, 0.0),
            _row("Final service stage", "OLD", 0.0, 0.0),
            _row("Final service stage", "OLD", 20.0, -1.0),
        ]
    )
    replacement = pd.DataFrame(
        [
            _row("Transfer stage", "SERV", 0.0, 0.0),  # stage must be pinned by UI owner
            _row("Transfer stage", "SERV", 20.0, -5.0),
        ]
    )
    merged = merge(current, replacement, stage="Final service stage")
    transfer = merged[merged["Stage"] == "Transfer stage"]
    service = merged[merged["Stage"] == "Final service stage"]
    assert transfer["Case Name"].tolist() == ["TR", "TR"]
    assert service["Case Name"].tolist() == ["SERV", "SERV"]
    assert service["Vertical displacement (mm)"].tolist() == [0.0, -5.0]


def test_d25_ui_has_independent_stage_import_and_csp_chart_language() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
    assert 'st.tabs(["At Transfer source", "At Final Service source"])' in source
    assert 'f"Replace {stage_title} source"' in source
    assert "Replacing this source preserves the other stage" in source
    assert 'name="Absolute FEA displacement"' in source
    assert 'name="Relative span deflection"' in source
    assert 'name="Deflection limit"' in source
    assert '"color": "#1f77b4"' in source
    assert '"color": "#0f766e"' in source
    assert 'line=dict(_BEAM_ULS_CHECK_LINE_STYLE)' in source
    assert "NO DEFLECTION LIMIT SELECTED" in source
    assert "span-specific red dashed limits" in source


def test_d25_solver_exposes_span_extents_for_span_specific_limit_plotting() -> None:
    columns = [
        {"Column ID": "C1", "Station s (m)": 2.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C2", "Station s (m)": 10.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C3", "Station s (m)": 18.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
    ]
    rows = []
    for x, d in [(0.0, 0.0), (2.0, 0.0), (6.0, -10.0), (10.0, 0.0), (14.0, -8.0), (18.0, 0.0), (20.0, 0.0)]:
        rows.append(_row("Final service stage", "SERV", x, d))
    state = {
        "crossbeam_ui1_length_m": 20.0,
        CROSSBEAM_COLUMN_ROWS_KEY: columns,
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY: pd.DataFrame(rows),
        "crossbeam_sls_deflection_limit_basis": "L/360",
    }
    prep = build_crossbeam_deflection_preparation(state)
    assert prep.ready
    result = run_crossbeam_deflection_camber(prep)
    assert result["schema"] == "crossbeam-sls2-deflection-result-v2"
    spans = result["span_rows"]
    assert [(row["Span start m"], row["Span end m"]) for row in spans] == [(2.0, 10.0), (10.0, 18.0)]
    assert all(float(row["Limit mm"]) > 0.0 for row in spans)


def test_d25_final_service_only_still_runs_without_transfer_rows() -> None:
    columns = [
        {"Column ID": "C1", "Station s (m)": 2.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C2", "Station s (m)": 10.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
    ]
    rows = [_row("Final service stage", "SERV", x, d) for x, d in [(0.0, 0.0), (2.0, 0.0), (6.0, -3.0), (10.0, 0.0), (12.0, 0.0)]]
    state = {
        "crossbeam_ui1_length_m": 12.0,
        CROSSBEAM_COLUMN_ROWS_KEY: columns,
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY: pd.DataFrame(rows),
        "crossbeam_sls_deflection_limit_basis": "L/360",
    }
    prep = build_crossbeam_deflection_preparation(state)
    assert prep.ready
    assert any("No active Transfer-stage" in warning for warning in prep.warnings)
    result = run_crossbeam_deflection_camber(prep)
    assert result["governing_row"] is not None
    assert result["transfer_governing_row"] is None
