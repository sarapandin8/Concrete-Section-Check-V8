from __future__ import annotations

import pandas as pd

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY,
    CB_STATION_FORCE_CONTRACT_KEY,
    build_station_force_analysis_handoff,
    canonical_sls_stage,
    canonical_station_force_contract,
    default_station_force_contract,
    validate_station_force_contract,
    validate_station_force_rows,
)
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)


def _ready_contract() -> dict[str, object]:
    contract = default_station_force_contract(
        effective_prestress_link={
            "ready": True,
            "source_id": "383f604ba96c",
            "contract_id": "88c15d9ba20fc234",
            "average_total_loss_percent": 20.2148,
            "effective_prestress_ratio_percent": 79.7852,
        }
    )
    contract.update(
        {
            "fea_program": "CSiBridge",
            "model_revision": "CB-FINAL-R04",
            "confirmed_final_prestress_applied_once": True,
            "confirmed_external_fea_secondary": True,
            "confirmed_uls_final_stage_response_basis": True,
            "confirmed_sls_service_response_basis": True,
            "confirmed_transfer_immediate_loss_basis": True,
            "confirmed_transfer_stage_response_basis": True,
            "confirmed_row_coupled_forces": True,
        }
    )
    return canonical_station_force_contract(contract)


def _row(case: str, stage: str | None = None) -> dict[str, object]:
    row: dict[str, object] = {
        "Active": True,
        "Station s (m)": 10.0,
        "Check Point": "Midspan",
        "Case Name": case,
        "P": 900.0,
        "V2": 180.0,
        "T": 2.5,
        "M3": 3.5,
        "Note": "selected row-coupled FEA response",
    }
    if stage is not None:
        row["Stage"] = stage
    return row


def test_fixed_sls_tabs_do_not_require_repeated_stage_declarations() -> None:
    contract = _ready_contract()
    contract["confirmed_sls_service_response_basis"] = False
    contract["confirmed_transfer_stage_response_basis"] = False

    transfer_errors, _ = validate_station_force_contract(
        contract, response_type="SLS", sls_stage="Transfer stage"
    )
    service_errors, _ = validate_station_force_contract(
        contract, response_type="SLS", sls_stage="Final service stage"
    )

    assert not transfer_errors
    assert not service_errors


def test_analysis_handoff_requires_uls_transfer_and_service_inputs() -> None:
    contract = _ready_contract()
    handoff = build_station_force_analysis_handoff(
        uls_rows=[_row("ULS-01")],
        sls_transfer_rows=[],
        sls_service_rows=[_row("SLS-SERV-01", "Final service stage")],
        contract=contract,
        member_length_m=20.0,
    )
    assert handoff["ready_for_analysis"] is False
    assert handoff["uls_validation"]["ready"] is True
    assert handoff["sls_transfer_validation"]["ready"] is False
    assert handoff["sls_service_validation"]["ready"] is True


def test_analysis_handoff_keeps_transfer_and_service_rows_separate() -> None:
    contract = _ready_contract()
    handoff = build_station_force_analysis_handoff(
        uls_rows=[_row("ULS-01")],
        sls_transfer_rows=[_row("SLS-TR-01", "Transfer stage")],
        sls_service_rows=[_row("SLS-SERV-01", "Final service stage")],
        contract=contract,
        member_length_m=20.0,
    )
    assert handoff["ready_for_analysis"] is True
    assert handoff["sls_transfer_rows"][0]["Stage"] == "Transfer stage"
    assert handoff["sls_service_rows"][0]["Stage"] == "Final service stage"
    assert len(handoff["sls_rows"]) == 2
    assert len(handoff["fingerprint"]) == 64


def test_wrong_stage_is_blocked_inside_fixed_sls_subtab() -> None:
    validation = validate_station_force_rows(
        [_row("SLS-WRONG", "Final service stage")],
        contract=_ready_contract(),
        member_length_m=20.0,
        response_type="SLS",
        rows_are_canonical=True,
        expected_sls_stage="Transfer stage",
    )
    assert validation.ready is False
    assert any("Stage must be Transfer stage" in error for error in validation.errors)


def test_loads_page_uses_fixed_at_transfer_and_at_service_subtabs() -> None:
    source = open("concrete_pmm_pro/ui/loads_page.py", encoding="utf-8").read()
    block = source[
        source.index("def _render_crossbeam_uls_sls_load_tables") : source.index(
            "def _commercial_load_dashboard_cards"
        )
    ]
    assert 'st.tabs(["At Transfer", "At Service"])' in block
    assert "immediate-loss prestress only" in block
    assert "Do not apply the final Time-Dependent loss at this stage" in block
    assert "CROSSBEAM_SLS_STAGE_EDITOR_COLUMNS" in block
    assert 'SelectboxColumn(\n                    "Stage"' not in block
    assert '"sls_transfer_validation"' in block
    assert '"sls_service_validation"' in block



def test_at_transfer_and_at_service_labels_normalize_to_storage_stages() -> None:
    assert canonical_sls_stage("At Transfer") == "Transfer stage"
    assert canonical_sls_stage("At Service") == "Final service stage"

def test_project_json_round_trip_preserves_both_sls_stage_rows_and_v2_contract() -> None:
    contract = _ready_contract()
    link = {
        "ready": True,
        "source_id": "383f604ba96c",
        "contract_id": "88c15d9ba20fc234",
        "average_total_loss_percent": 20.2148,
        "effective_prestress_ratio_percent": 79.7852,
    }
    source: dict[str, object] = {
        "project_name": "Crossbeam LOADS1B",
        "analysis_mode_settings": AnalysisModeSettings(member_type="portal_frame_crossbeam"),
        "crossbeam_ui1_length_m": 20.0,
        "crossbeam_uls_loads_table": pd.DataFrame([_row("ULS-01")]),
        "crossbeam_sls_loads_table": pd.DataFrame(
            [
                _row("SLS-TR-01", "Transfer stage"),
                _row("SLS-SERV-01", "Final service stage"),
            ]
        ),
        CB_STATION_FORCE_CONTRACT_KEY: contract,
        CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY: link,
    }
    restored: dict[str, object] = {}
    project = project_from_session_state(source)
    apply_project_to_session_state(project_from_json(project_to_json(project)), restored)
    rows = pd.DataFrame(restored["crossbeam_sls_loads_table"])
    assert set(rows["Stage"]) == {"Transfer stage", "Final service stage"}
    restored_contract = restored[CB_STATION_FORCE_CONTRACT_KEY]
    assert restored_contract["schema"] == "crossbeam-station-force-import-contract-v2"
    assert restored_contract["confirmed_transfer_immediate_loss_basis"] is True
    assert restored_contract["confirmed_sls_service_response_basis"] is True


def test_legacy_contract_migrates_to_fixed_automatic_stage_declarations() -> None:
    migrated = canonical_station_force_contract(
        {
            "fea_program": "CSiBridge",
            "model_revision": "LEGACY-R03",
            "adopted_total_loss_percent": 20.2148,
            "confirmed_prestress_applied_once": True,
            "confirmed_external_fea_secondary": True,
            "confirmed_final_stage_response_basis": True,
            "confirmed_row_coupled_forces": True,
        }
    )
    assert migrated["confirmed_final_prestress_applied_once"] is True
    assert migrated["confirmed_uls_final_stage_response_basis"] is True
    assert migrated["confirmed_sls_service_response_basis"] is True
    assert migrated["confirmed_transfer_immediate_loss_basis"] is True
    assert migrated["confirmed_transfer_stage_response_basis"] is True
    errors, _ = validate_station_force_contract(migrated)
    assert not any("Transfer-stage prestress" in error for error in errors)
