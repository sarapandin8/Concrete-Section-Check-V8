from __future__ import annotations

from pathlib import Path

import pandas as pd

from concrete_pmm_pro.ui.loads_page import (
    BEAM_SLS_LOAD_COLUMNS,
    BEAM_SLS_STAGE_EDITOR_COLUMNS,
    COLUMN_ULS_LOAD_COLUMNS,
    _beam_sls_table_after_stage_edit,
    _data_editor_payload_to_dataframe as loads_editor_payload_to_dataframe,
    _stringify_table,
)
from concrete_pmm_pro.ui.rebar_page import (
    SHEAR_REINFORCEMENT_COLUMNS,
    _data_editor_payload_to_dataframe as rebar_editor_payload_to_dataframe,
    _ensure_shear_reinforcement_columns,
)


def test_dataeditor_commit1_payload_reconstructs_load_table_first_edit() -> None:
    fallback = _stringify_table(
        pd.DataFrame(
            [
                {
                    "Active": True,
                    "Case Name": "U1",
                    "Pu": "0",
                    "Mux": "0",
                    "Muy": "0",
                    "Vux": "0",
                    "Vuy": "0",
                    "Tu": "0",
                    "Note": "old",
                }
            ]
        ),
        COLUMN_ULS_LOAD_COLUMNS,
    )
    payload = {"edited_rows": {0: {"Vuy": "1355.74", "Note": "first edit"}}, "added_rows": [], "deleted_rows": []}

    reconstructed = loads_editor_payload_to_dataframe(payload, fallback)
    normalized = _stringify_table(reconstructed, COLUMN_ULS_LOAD_COLUMNS)

    assert normalized.at[0, "Vuy"] == "1355.74"
    assert normalized.at[0, "Note"] == "first edit"


def test_dataeditor_commit1_stage_payload_merges_into_backend_table() -> None:
    backend = pd.DataFrame(
        [
            {
                "Active": True,
                "Station x (m)": "0.000",
                "Case Name": "SLS-TR",
                "Stage": "Transfer stage",
                "Load Component": "Girder self-weight",
                "Section Basis": "Precast gross",
                "N": "0",
                "Mx": "0",
                "My": "0",
                "Vy": "0",
                "Vx": "0",
                "T": "0",
                "Note": "transfer",
            },
            {
                "Active": True,
                "Station x (m)": "5.000",
                "Case Name": "SLS-SERV",
                "Stage": "Service stage",
                "Load Component": "Total SLS resultant",
                "Section Basis": "Composite transformed",
                "N": "0",
                "Mx": "100",
                "My": "0",
                "Vy": "0",
                "Vx": "0",
                "T": "0",
                "Note": "service",
            },
        ],
        columns=BEAM_SLS_LOAD_COLUMNS,
    )
    stage_fallback = _stringify_table(
        pd.DataFrame(
            [
                {
                    "Active": True,
                    "Station x (m)": "5.000",
                    "Case Name": "SLS-SERV",
                    "Section Basis": "Composite transformed",
                    "N": "0",
                    "Mx": "100",
                    "My": "0",
                    "Vy": "0",
                    "Vx": "0",
                    "T": "0",
                    "Note": "service",
                }
            ]
        ),
        BEAM_SLS_STAGE_EDITOR_COLUMNS,
    )
    payload = {"edited_rows": {0: {"Mx": "250", "Note": "first service edit"}}, "added_rows": [], "deleted_rows": []}

    edited_stage = _stringify_table(loads_editor_payload_to_dataframe(payload, stage_fallback), BEAM_SLS_STAGE_EDITOR_COLUMNS)
    merged = _beam_sls_table_after_stage_edit(backend, "Service stage", edited_stage)

    service_rows = merged[merged["Stage"] == "Service stage"]
    transfer_rows = merged[merged["Stage"] == "Transfer stage"]
    assert service_rows.iloc[0]["Mx"] == "250"
    assert service_rows.iloc[0]["Note"] == "first service edit"
    assert transfer_rows.iloc[0]["Mx"] == "0"


def test_dataeditor_commit1_payload_reconstructs_transverse_rebar_first_edit() -> None:
    fallback = _ensure_shear_reinforcement_columns(
        pd.DataFrame(
            [
                {
                    "Active": True,
                    "Zone": "Midspan",
                    "x_start_m": 3.0,
                    "x_end_m": 7.0,
                    "Bar Size": "DB12",
                    "Diameter_mm": 12.0,
                    "Legs": 2,
                    "Spacing_mm": 250.0,
                    "fy_MPa": 390.0,
                    "Note": "old",
                }
            ],
            columns=SHEAR_REINFORCEMENT_COLUMNS,
        )
    )
    payload = {"edited_rows": {0: {"Spacing_mm": 125.0, "Note": "first edit"}}, "added_rows": [], "deleted_rows": []}

    reconstructed = rebar_editor_payload_to_dataframe(payload, fallback)

    assert float(reconstructed.at[0, "Spacing_mm"]) == 125.0
    assert reconstructed.at[0, "Note"] == "first edit"


def test_dataeditor_commit1_ui_tables_have_on_change_commit_callbacks() -> None:
    root = Path(__file__).resolve().parents[1]
    loads_source = (root / "concrete_pmm_pro" / "ui" / "loads_page.py").read_text(encoding="utf-8")
    rebar_source = (root / "concrete_pmm_pro" / "ui" / "rebar_page.py").read_text(encoding="utf-8")

    assert "UI.DATAEDITOR.COMMIT1" in loads_source
    assert "on_change=_sync_simple_load_editor_to_table" in loads_source
    assert "on_change=_sync_beam_sls_stage_editor_to_table" in loads_source
    assert "column_uls_loads_editor" in loads_source and "column_sls_loads_editor" in loads_source
    assert "beam_uls_loads_editor" in loads_source and "building_beam_uls_loads_editor" in loads_source
    assert "beam_sls_{stage_key}_loads_editor" in loads_source

    assert "UI.DATAEDITOR.COMMIT1" in rebar_source
    assert "on_change=_sync_beam_girder_shear_reinforcement_editor_to_table" in rebar_source
    assert "on_change=_sync_column_pier_transverse_reinforcement_editor_to_table" in rebar_source
