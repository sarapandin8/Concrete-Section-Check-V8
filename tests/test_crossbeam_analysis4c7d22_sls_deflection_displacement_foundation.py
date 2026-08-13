from __future__ import annotations

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_sls_deflection import (
    CROSSBEAM_SLS_DEFLECTION_RESULT_HASH_KEY,
    CROSSBEAM_SLS_DEFLECTION_RESULT_KEY,
    CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY,
    build_crossbeam_deflection_preparation,
    run_crossbeam_deflection_camber,
)
from concrete_pmm_pro.crossbeam.project_geometry import CROSSBEAM_COLUMN_ROWS_KEY
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY


def _columns() -> list[dict[str, object]]:
    return [
        {"Column ID": "C1", "Station s (m)": 2.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C2", "Station s (m)": 10.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C3", "Station s (m)": 18.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
    ]


def _stage_rows(stage: str, case: str, *, offset: float = 0.0, peak: float = -10.0) -> list[dict[str, object]]:
    values = {0.0: 0.0, 2.0: 0.0, 6.0: peak, 10.0: 0.0, 14.0: peak, 18.0: 0.0, 20.0: 0.0}
    if stage == "Transfer stage":
        values = {x: -0.4 * y for x, y in values.items()}  # upward camber +4 mm at span midpoints
    return [
        {
            "Active": True,
            "Station s (m)": x,
            "Case Name": case,
            "Stage": stage,
            "Vertical displacement (mm)": y + offset,
            "Source point": f"J{x:g}",
            "Note": "verified external-FEA movement",
        }
        for x, y in values.items()
    ]


def _state(*, limit: str = "Review only", final_offset: float = 0.0) -> dict[str, object]:
    return {
        "crossbeam_ui1_length_m": 20.0,
        CROSSBEAM_COLUMN_ROWS_KEY: _columns(),
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY: pd.DataFrame(
            _stage_rows("Transfer stage", "TR-DISP")
            + _stage_rows("Final service stage", "SERV-DISP", offset=final_offset)
        ),
        "crossbeam_sls_deflection_limit_basis": limit,
    }


def test_d22_blocks_force_only_crossbeam_instead_of_fabricating_frame_displacement() -> None:
    prep = build_crossbeam_deflection_preparation(
        {
            "crossbeam_ui1_length_m": 20.0,
            CROSSBEAM_COLUMN_ROWS_KEY: _columns(),
            CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        }
    )
    assert not prep.ready
    assert any("external-FEA vertical displacements" in message for message in prep.errors)


def test_d22_span_response_removes_support_translation_and_preserves_sign() -> None:
    prep = build_crossbeam_deflection_preparation(_state(final_offset=3.25))
    assert prep.ready
    result = run_crossbeam_deflection_camber(prep)
    assert result["status"] == "REVIEW"  # safe default: no fabricated code limit
    transfer = result["transfer_governing_row"]
    final = result["governing_row"]
    assert round(float(transfer["Max upward camber mm"]), 6) == 4.0
    assert round(float(final["Max downward deflection mm"]), 6) == 10.0
    # A rigid +3.25 mm support translation is removed by the adjacent-column chord.
    supports = [row for row in result["support_rows"] if row["Stage"] == "Final service stage"]
    assert all(round(float(row["Vertical displacement mm"]), 6) == 3.25 for row in supports)


def test_d22_final_service_project_limit_pass_fail_is_span_specific() -> None:
    pass_result = run_crossbeam_deflection_camber(build_crossbeam_deflection_preparation(_state(limit="L/360")))
    assert pass_result["status"] == "PASS"
    assert round(float(pass_result["governing_row"]["Limit mm"]), 3) == round(8000.0 / 360.0, 3)
    fail_result = run_crossbeam_deflection_camber(build_crossbeam_deflection_preparation(_state(limit="L/1000")))
    assert fail_result["status"] == "FAIL"
    assert float(fail_result["governing_row"]["Utilization"]) > 1.0
    assert fail_result["required_actions"]


def test_d22_result_keys_and_ui_keep_generic_simple_span_solver_out_of_crossbeam_route() -> None:
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
    block = source[source.index("def render_analysis_sls_deflection_camber"):source.index("def render_analysis_report_qa")]
    assert "_render_crossbeam_sls_deflection_workspace()" in block
    assert "_render_girder_deflection_camber_workspace" not in block.split("return", 1)[0]
    assert "does not reconstruct absolute Crossbeam displacement from beam M3/EI" in source
    assert CROSSBEAM_SLS_DEFLECTION_RESULT_KEY == "crossbeam_sls2_deflection_camber_result"
    assert CROSSBEAM_SLS_DEFLECTION_RESULT_HASH_KEY == "crossbeam_sls2_deflection_camber_input_hash"


def test_d22_loads_and_project_json_persist_displacement_source_key() -> None:
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    loads_source = (root / "concrete_pmm_pro" / "ui" / "loads_page.py").read_text(encoding="utf-8")
    io_source = (root / "concrete_pmm_pro" / "io" / "project_io.py").read_text(encoding="utf-8")
    assert "SLS Deflection / Camber displacement source" in loads_source
    assert "Vertical displacement (mm; upward +)" in loads_source
    assert 'CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY,' in loads_source
    assert 'CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY,' in io_source
