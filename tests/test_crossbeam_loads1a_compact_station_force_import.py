from __future__ import annotations

import pandas as pd
import pytest

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY,
    CB_STATION_FORCE_CONTRACT_KEY,
    PRESTRESS_BASIS_UNIFORM_AVERAGE_LOSS,
    build_station_force_analysis_handoff,
    canonical_station_force_contract,
    default_station_force_contract,
    normalize_station_force_rows,
    validate_station_force_rows,
)
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)


def _ready_contract(**overrides: object) -> dict[str, object]:
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
            "model_revision": "CB-FINAL-R03",
            "confirmed_final_prestress_applied_once": True,
            "confirmed_external_fea_secondary": True,
            "confirmed_uls_final_stage_response_basis": True,
            "confirmed_sls_service_response_basis": True,
            "confirmed_transfer_immediate_loss_basis": True,
            "confirmed_transfer_stage_response_basis": True,
            "confirmed_row_coupled_forces": True,
        }
    )
    contract.update(overrides)
    return canonical_station_force_contract(contract)


def _uls_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Active": True,
        "Station s (m)": 10.0,
        "Check Point": "Midspan",
        "Case Name": "ULS-01",
        "P": 1_000_000.0,
        "V2": 200_000.0,
        "T": 3_000_000.0,
        "M3": 4_000_000.0,
        "Note": "selected FEA row",
    }
    row.update(overrides)
    return row


def _sls_row(**overrides: object) -> dict[str, object]:
    row = _uls_row(**overrides)
    row["Case Name"] = str(overrides.get("Case Name", "SLS-SERV-01"))
    row["Stage"] = str(overrides.get("Stage", "Service stage"))
    return row


def test_import_normalizes_source_units_and_signs_without_element_end_fields() -> None:
    contract = _ready_contract(
        source_force_unit="N",
        source_moment_unit="N-mm",
        p_sign="TENSION_POSITIVE",
        v2_sign="DOWNWARD_POSITIVE",
        t_sign="OPPOSITE_RIGHT_HAND_ABOUT_INCREASING_S",
        m3_sign="HOGGING_POSITIVE",
    )
    rows = normalize_station_force_rows(
        [_uls_row()], contract=contract, response_type="ULS"
    )
    assert rows[0]["P"] == pytest.approx(-1000.0)
    assert rows[0]["V2"] == pytest.approx(-200.0)
    assert rows[0]["T"] == pytest.approx(-3.0)
    assert rows[0]["M3"] == pytest.approx(-4.0)
    assert "FEA Element" not in rows[0]
    assert "End / Side" not in rows[0]


def test_optional_check_point_distinguishes_selected_rows_at_same_station() -> None:
    contract = _ready_contract(source_force_unit="kN", source_moment_unit="kN-m")
    rows = [
        _uls_row(**{"Check Point": "C1-Left", "P": 1000.0, "V2": 200.0, "T": 3.0, "M3": 4.0}),
        _uls_row(**{"Check Point": "C1-Right", "P": 1100.0, "V2": 250.0, "T": 3.5, "M3": 5.0}),
    ]
    validation = validate_station_force_rows(
        rows,
        contract=contract,
        member_length_m=20.0,
        response_type="ULS",
        rows_are_canonical=True,
    )
    assert validation.ready is True
    assert validation.total_rows == 2
    assert validation.check_points == 2
    assert not validation.errors


def test_multiple_same_station_rows_require_check_point_labels() -> None:
    contract = _ready_contract(source_force_unit="kN", source_moment_unit="kN-m")
    rows = [
        _uls_row(**{"Check Point": "", "P": 1000.0, "V2": 200.0, "T": 3.0, "M3": 4.0}),
        _uls_row(**{"Check Point": "C1-Right", "P": 1100.0, "V2": 250.0, "T": 3.5, "M3": 5.0}),
    ]
    validation = validate_station_force_rows(
        rows,
        contract=contract,
        member_length_m=20.0,
        response_type="ULS",
        rows_are_canonical=True,
    )
    assert validation.ready is False
    assert any("enter Check Point labels" in error for error in validation.errors)


def test_duplicate_case_stage_station_check_point_is_blocked() -> None:
    contract = _ready_contract(source_force_unit="kN", source_moment_unit="kN-m")
    row = _sls_row(P=1000.0, V2=200.0, T=3.0, M3=4.0)
    validation = validate_station_force_rows(
        [row, row],
        contract=contract,
        member_length_m=20.0,
        response_type="SLS",
        rows_are_canonical=True,
    )
    assert validation.ready is False
    assert any("duplicate station-force row" in error for error in validation.errors)



def test_invalid_numeric_station_force_is_not_silently_converted_to_zero() -> None:
    contract = _ready_contract(source_force_unit="kN", source_moment_unit="kN-m")
    row = _uls_row(P="not-a-number", V2=200.0, T=3.0, M3=4.0)
    validation = validate_station_force_rows(
        [row],
        contract=contract,
        member_length_m=20.0,
        response_type="ULS",
        rows_are_canonical=True,
    )
    assert validation.ready is False
    assert any("P must be a finite numeric value" in error for error in validation.errors)

def test_analysis_handoff_uses_row_coupled_station_forces_and_uniform_loss_contract() -> None:
    contract = _ready_contract(source_force_unit="kN", source_moment_unit="kN-m")
    uls = [_uls_row(P=1000.0, V2=200.0, T=3.0, M3=4.0)]
    sls_transfer = [_sls_row(**{"Case Name": "SLS-TR-01", "Stage": "Transfer stage", "P": 950.0, "V2": 190.0, "T": 2.7, "M3": 3.8})]
    sls_service = [_sls_row(P=900.0, V2=180.0, T=2.5, M3=3.5)]
    handoff = build_station_force_analysis_handoff(
        uls_rows=uls,
        sls_transfer_rows=sls_transfer,
        sls_service_rows=sls_service,
        contract=contract,
        member_length_m=20.0,
    )
    assert handoff["ready_for_analysis"] is True
    assert handoff["contract"]["prestress_application_basis"] == PRESTRESS_BASIS_UNIFORM_AVERAGE_LOSS
    assert handoff["contract"]["adopted_total_loss_percent"] == pytest.approx(20.2148)
    assert handoff["sls_transfer_rows"][0]["Stage"] == "Transfer stage"
    assert handoff["sls_service_rows"][0]["Stage"] == "Final service stage"
    assert len(handoff["fingerprint"]) == 64


def test_project_json_round_trip_preserves_compact_contract_link_and_check_point_rows() -> None:
    contract = _ready_contract(source_force_unit="kN", source_moment_unit="kN-m")
    link = {
        "ready": True,
        "source_id": "383f604ba96c",
        "contract_id": "88c15d9ba20fc234",
        "source_fingerprint": "f" * 64,
        "application_route": "DIRECT_EFFECTIVE_FORCE",
        "engineer_adopted_td": True,
        "average_total_loss_percent": 20.2148,
        "effective_prestress_ratio_percent": 79.7852,
        "average_effective_stress_mpa": 1113.0032,
        "average_effective_force_kn": 23684.709,
    }
    source: dict[str, object] = {
        "project_name": "Crossbeam LOADS1A",
        "analysis_mode_settings": AnalysisModeSettings(member_type="portal_frame_crossbeam"),
        "crossbeam_ui1_length_m": 20.0,
        "crossbeam_uls_loads_table": pd.DataFrame([_uls_row(P=1000.0, V2=200.0, T=3.0, M3=4.0)]),
        "crossbeam_sls_loads_table": pd.DataFrame([_sls_row(P=900.0, V2=180.0, T=2.5, M3=3.5)]),
        CB_STATION_FORCE_CONTRACT_KEY: contract,
        CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY: link,
    }
    restored: dict[str, object] = {}
    project = project_from_session_state(source)
    apply_project_to_session_state(project_from_json(project_to_json(project)), restored)
    assert restored[CB_STATION_FORCE_CONTRACT_KEY]["model_revision"] == "CB-FINAL-R03"
    assert restored[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY]["source_id"] == "383f604ba96c"
    restored_uls = pd.DataFrame(restored["crossbeam_uls_loads_table"])
    restored_sls = pd.DataFrame(restored["crossbeam_sls_loads_table"])
    assert restored_uls.iloc[0]["Check Point"] == "Midspan"
    assert restored_sls.iloc[0]["Stage"] == "Service stage"


def test_loads_page_keeps_old_member_ux_and_does_not_require_raw_i_j_element_output() -> None:
    source = open("concrete_pmm_pro/ui/loads_page.py", encoding="utf-8").read()
    assert "Portal Frame Crossbeam — Selected Station Forces" in source
    assert "Raw element I/J-end output is not required" in source
    assert "Check Point" in source
    assert "Canonical import preview — kN / kN·m" in source
    assert "every P/V2/T/M3 row must come from one FEA output state" in source
    block = source[source.index("def _render_crossbeam_uls_sls_load_tables"):source.index("def _commercial_load_dashboard_cards")]
    assert '"FEA Element"' not in block
    assert '"End / Side"' not in block

def test_effective_prestress_page_publishes_compact_loads_link() -> None:
    source = open("concrete_pmm_pro/ui/crossbeam_pages.py", encoding="utf-8").read()
    assert "st.session_state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY]" in source
    assert '"average_total_loss_percent"' in source
    assert '"effective_prestress_ratio_percent"' in source
    assert '"source_id"' in source
    assert '"contract_id"' in source
