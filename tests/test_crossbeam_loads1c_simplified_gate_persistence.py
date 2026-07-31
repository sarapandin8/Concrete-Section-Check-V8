from __future__ import annotations

import json

import pandas as pd

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_STATION_FORCE_CONTRACT_KEY,
    canonical_station_force_contract,
    default_station_force_contract,
    validate_station_force_contract,
)
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)


def _uls_row() -> dict[str, object]:
    return {
        "Active": True,
        "Station s (m)": 10.0,
        "Check Point": "C2-Right",
        "Case Name": "ULS-01",
        "P": 5000.0,
        "V2": 750.0,
        "T": 1000.0,
        "M3": 7000.0,
        "Note": "factored final-stage row",
    }


def _sls_row(case: str, stage: str) -> dict[str, object]:
    row = _uls_row()
    row["Case Name"] = case
    row["Stage"] = stage
    row["Note"] = f"{stage} row"
    return row


def test_optional_fea_metadata_and_final_loss_do_not_block_import() -> None:
    contract = default_station_force_contract()
    contract.update(
        {
            "fea_program": "",
            "model_revision": "",
            "adopted_total_loss_percent": 0.0,
            "prestress_source_id": "",
            "prestress_contract_id": "",
            "confirmed_uls_dataset": True,
        }
    )
    errors, warnings = validate_station_force_contract(contract, response_type="ULS")
    assert errors == []
    assert warnings == []


def test_each_dataset_has_only_one_independent_confirmation_gate() -> None:
    contract = default_station_force_contract()
    contract.update(
        {
            "confirmed_uls_dataset": True,
            "confirmed_sls_transfer_dataset": False,
            "confirmed_sls_service_dataset": True,
        }
    )
    assert validate_station_force_contract(contract, response_type="ULS")[0] == []
    transfer_errors, _ = validate_station_force_contract(
        contract, response_type="SLS", sls_stage="Transfer stage"
    )
    assert len(transfer_errors) == 1
    assert "SLS At Transfer dataset" in transfer_errors[0]
    assert (
        validate_station_force_contract(
            contract, response_type="SLS", sls_stage="Final service stage"
        )[0]
        == []
    )


def test_v2_detailed_contract_migrates_to_single_dataset_confirmations() -> None:
    migrated = canonical_station_force_contract(
        {
            "schema": "crossbeam-station-force-import-contract-v2",
            "fea_program": "SAP2000",
            "model_revision": "CB-R07",
            "adopted_total_loss_percent": 18.5,
            "confirmed_final_prestress_applied_once": True,
            "confirmed_external_fea_secondary": True,
            "confirmed_uls_final_stage_response_basis": True,
            "confirmed_sls_service_response_basis": True,
            "confirmed_transfer_immediate_loss_basis": True,
            "confirmed_transfer_stage_response_basis": True,
            "confirmed_row_coupled_forces": True,
        }
    )
    assert migrated["schema"] == "crossbeam-station-force-import-contract-v3"
    assert migrated["confirmed_uls_dataset"] is True
    assert migrated["confirmed_sls_transfer_dataset"] is True
    assert migrated["confirmed_sls_service_dataset"] is True
    # Optional legacy inputs remain available for safe round-trip persistence.
    assert migrated["fea_program"] == "SAP2000"
    assert migrated["model_revision"] == "CB-R07"
    assert migrated["adopted_total_loss_percent"] == 18.5


def test_project_json_round_trip_preserves_current_inputs_and_all_three_datasets() -> None:
    contract = canonical_station_force_contract(
        {
            "fea_program": "SAP2000",
            "model_revision": "STATION-CB-R08",
            "source_force_unit": "kN",
            "source_moment_unit": "kN-m",
            "confirmed_uls_dataset": True,
            "confirmed_sls_transfer_dataset": True,
            "confirmed_sls_service_dataset": True,
        }
    )
    source: dict[str, object] = {
        "project_name": "Crossbeam LOADS1C",
        "analysis_mode_settings": AnalysisModeSettings(member_type="portal_frame_crossbeam"),
        "crossbeam_ui1_length_m": 30.0,
        "crossbeam_uls_loads_table": pd.DataFrame([_uls_row()]),
        "crossbeam_sls_loads_table": pd.DataFrame(
            [
                _sls_row("SLS-TR-01", "Transfer stage"),
                _sls_row("SLS-SERV-01", "Final service stage"),
            ]
        ),
        CB_STATION_FORCE_CONTRACT_KEY: contract,
    }
    restored: dict[str, object] = {}
    project = project_from_session_state(source)
    apply_project_to_session_state(project_from_json(project_to_json(project)), restored)

    restored_contract = restored[CB_STATION_FORCE_CONTRACT_KEY]
    assert restored_contract["fea_program"] == "SAP2000"
    assert restored_contract["model_revision"] == "STATION-CB-R08"
    assert restored_contract["confirmed_uls_dataset"] is True
    assert restored_contract["confirmed_sls_transfer_dataset"] is True
    assert restored_contract["confirmed_sls_service_dataset"] is True

    restored_uls = pd.DataFrame(restored["crossbeam_uls_loads_table"])
    restored_sls = pd.DataFrame(restored["crossbeam_sls_loads_table"])
    assert restored_uls.to_dict(orient="records") == [_uls_row()]
    assert set(restored_sls["Stage"]) == {"Transfer stage", "Final service stage"}
    assert set(restored_sls["Case Name"]) == {"SLS-TR-01", "SLS-SERV-01"}


def test_loading_old_v2_project_preserves_rows_and_migrates_confirmations() -> None:
    source: dict[str, object] = {
        "project_name": "Legacy Crossbeam LOADS1B",
        "analysis_mode_settings": AnalysisModeSettings(member_type="portal_frame_crossbeam"),
        "crossbeam_ui1_length_m": 30.0,
        "crossbeam_uls_loads_table": pd.DataFrame([_uls_row()]),
        "crossbeam_sls_loads_table": pd.DataFrame(
            [
                _sls_row("SLS-TR-LEGACY", "Transfer stage"),
                _sls_row("SLS-SERV-LEGACY", "Final service stage"),
            ]
        ),
    }
    payload = json.loads(project_to_json(project_from_session_state(source)))
    payload["metadata"][CB_STATION_FORCE_CONTRACT_KEY] = {
        "schema": "crossbeam-station-force-import-contract-v2",
        "fea_program": "CSiBridge",
        "model_revision": "LEGACY-CB-R04",
        "source_force_unit": "kN",
        "source_moment_unit": "kN-m",
        "adopted_total_loss_percent": 20.2148,
        "confirmed_final_prestress_applied_once": True,
        "confirmed_external_fea_secondary": True,
        "confirmed_uls_final_stage_response_basis": True,
        "confirmed_sls_service_response_basis": True,
        "confirmed_transfer_immediate_loss_basis": True,
        "confirmed_transfer_stage_response_basis": True,
        "confirmed_row_coupled_forces": True,
    }

    restored: dict[str, object] = {}
    apply_project_to_session_state(
        project_from_json(json.dumps(payload, ensure_ascii=False)), restored
    )
    contract = restored[CB_STATION_FORCE_CONTRACT_KEY]
    assert contract["schema"] == "crossbeam-station-force-import-contract-v3"
    assert contract["model_revision"] == "LEGACY-CB-R04"
    assert contract["confirmed_uls_dataset"] is True
    assert contract["confirmed_sls_transfer_dataset"] is True
    assert contract["confirmed_sls_service_dataset"] is True

    restored_uls = pd.DataFrame(restored["crossbeam_uls_loads_table"])
    restored_sls = pd.DataFrame(restored["crossbeam_sls_loads_table"])
    assert restored_uls.iloc[0]["Case Name"] == "ULS-01"
    assert set(restored_sls["Case Name"]) == {"SLS-TR-LEGACY", "SLS-SERV-LEGACY"}


def test_loads_page_exposes_simple_per_dataset_confirmations_only() -> None:
    source = open("concrete_pmm_pro/ui/loads_page.py", encoding="utf-8").read()
    assert "FEA program (optional)" in source
    assert "I confirm that each imported row is a factored final-stage FEA result" in source
    assert "I confirm that each imported row is a transfer-stage service result" in source
    assert "I confirm that each imported row is a final-service FEA result" in source
    assert "Final uniform loss (%)" not in source
    assert "Final effective prestress / total loss applied exactly once in FEA" not in source
    assert "External portal-frame FEA includes final-stage secondary prestress response" not in source
