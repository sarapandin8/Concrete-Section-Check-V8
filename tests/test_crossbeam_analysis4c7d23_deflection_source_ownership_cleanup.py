from __future__ import annotations

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_sls_deflection import (
    CROSSBEAM_SLS_DEFLECTION_RESULT_HASH_KEY,
    CROSSBEAM_SLS_DEFLECTION_RESULT_KEY,
    CROSSBEAM_SLS_DISPLACEMENT_SOURCE_METADATA_KEY,
    CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY,
    build_crossbeam_deflection_preparation,
    run_crossbeam_deflection_camber,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.project_geometry import CROSSBEAM_COLUMN_ROWS_KEY
from concrete_pmm_pro.io.project_io import ANALYSIS_SOURCES_METADATA_KEY, project_from_session_state
from concrete_pmm_pro.state.dirty_state import project_input_hash


def _columns() -> list[dict[str, object]]:
    return [
        {"Column ID": "C1", "Station s (m)": 2.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C2", "Station s (m)": 10.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C3", "Station s (m)": 18.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
    ]


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for stage, case, peak in [
        ("Transfer stage", "TR-DISP", 4.0),
        ("Final service stage", "SERV-DISP", -10.0),
    ]:
        for station, value in [(0.0, 0.0), (2.0, 0.0), (6.0, peak), (10.0, 0.0), (14.0, peak), (18.0, 0.0), (20.0, 0.0)]:
            rows.append(
                {
                    "Active": True,
                    "Station s (m)": station,
                    "Case Name": case,
                    "Stage": stage,
                    "Vertical displacement (mm)": value,
                    "Source point": f"N{station:g}",
                    "Note": "verified external-FEA movement",
                }
            )
    return rows


def _state() -> dict[str, object]:
    return {
        "crossbeam_ui1_length_m": 20.0,
        CROSSBEAM_COLUMN_ROWS_KEY: _columns(),
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY: pd.DataFrame(_rows()),
        "crossbeam_sls_deflection_limit_basis": "Review only",
    }


def test_d23_ui_owns_displacement_import_in_analysis_not_loads() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    loads_source = (root / "concrete_pmm_pro" / "ui" / "loads_page.py").read_text(encoding="utf-8")
    analysis_source = (root / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
    assert "Upload Crossbeam SLS displacement source" not in loads_source
    assert "_render_crossbeam_sls_displacement_source" not in loads_source
    assert "Upload Crossbeam SLS displacement source" in analysis_source
    assert "Analysis → SLS Deflection / Camber → Deflection / Camber source" in analysis_source
    assert "response data for the Deflection / Camber check, not a Loads-workspace force input" in analysis_source


def test_d23_project_json_stores_displacement_under_analysis_sources_not_workflow_load_tables() -> None:
    project = project_from_session_state(_state())
    sources = project.metadata.get(ANALYSIS_SOURCES_METADATA_KEY)
    assert isinstance(sources, dict)
    source = sources[CROSSBEAM_SLS_DISPLACEMENT_SOURCE_METADATA_KEY]
    assert source["owner"] == "Analysis → SLS Deflection / Camber"
    assert len(source["rows"]) == len(_rows())
    workflow_tables = project.metadata.get("workflow_load_tables") or {}
    assert CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY not in workflow_tables


def test_d23_displacement_change_stales_only_deflection_fingerprint_not_global_project_hash() -> None:
    state = _state()
    state["crossbeam_uls_flexure_result"] = {"sentinel": "keep"}
    state["crossbeam_sls1a_transfer_result"] = {"sentinel": "keep"}
    original_project_hash = project_input_hash(state)
    original_prep = build_crossbeam_deflection_preparation(state)
    assert original_prep.ready
    state[CROSSBEAM_SLS_DEFLECTION_RESULT_KEY] = run_crossbeam_deflection_camber(original_prep)
    state[CROSSBEAM_SLS_DEFLECTION_RESULT_HASH_KEY] = original_prep.fingerprint

    changed = pd.DataFrame(state[CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY]).copy()
    mask = (changed["Stage"] == "Final service stage") & (changed["Station s (m)"] == 6.0)
    changed.loc[mask, "Vertical displacement (mm)"] = -12.0
    state[CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY] = changed

    changed_prep = build_crossbeam_deflection_preparation(state)
    assert changed_prep.ready
    assert changed_prep.fingerprint != state[CROSSBEAM_SLS_DEFLECTION_RESULT_HASH_KEY]
    assert project_input_hash(state) == original_project_hash
    assert state["crossbeam_uls_flexure_result"] == {"sentinel": "keep"}
    assert state["crossbeam_sls1a_transfer_result"] == {"sentinel": "keep"}


def test_d23_loads_legacy_d22_project_source_and_migrates_on_next_save() -> None:
    from concrete_pmm_pro.io.project_io import apply_project_to_session_state

    project = project_from_session_state(_state())
    source = project.metadata.pop(ANALYSIS_SOURCES_METADATA_KEY)[CROSSBEAM_SLS_DISPLACEMENT_SOURCE_METADATA_KEY]
    workflow = dict(project.metadata.get("workflow_load_tables") or {})
    workflow[CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY] = list(source["rows"])
    project.metadata["workflow_load_tables"] = workflow

    restored: dict[str, object] = {}
    apply_project_to_session_state(project, restored)
    restored_rows = pd.DataFrame(restored[CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY])
    assert len(restored_rows) == len(_rows())

    migrated = project_from_session_state(restored)
    migrated_sources = migrated.metadata[ANALYSIS_SOURCES_METADATA_KEY]
    assert CROSSBEAM_SLS_DISPLACEMENT_SOURCE_METADATA_KEY in migrated_sources
    assert CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY not in (migrated.metadata.get("workflow_load_tables") or {})
