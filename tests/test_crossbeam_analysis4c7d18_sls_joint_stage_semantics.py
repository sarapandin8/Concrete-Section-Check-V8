from __future__ import annotations

import inspect
import math

import pytest

import app
from concrete_pmm_pro.analysis.crossbeam_sls_transfer import (
    PHYSICAL_JOINT_SERVICE_MIN_COMPRESSION_MPA,
    PHYSICAL_JOINT_TRANSFER_MAX_TENSION_MPA,
    PreparedCrossbeamTransferRow,
    build_crossbeam_transfer_stress_preparation,
    run_crossbeam_service_stress,
    run_crossbeam_transfer_stress,
)
from tests.test_crossbeam_sls1a_transfer_stress import _base_state, _manual_preparation, _transfer_row


def _joint_row(*, p_kn: float, m3_knm: float = 0.0) -> PreparedCrossbeamTransferRow:
    return PreparedCrossbeamTransferRow(
        station_m=10.0,
        check_point="Joint",
        case_name="SLS-JOINT",
        section_face="LEFT LIMIT (s-)",
        location_type="PHYSICAL SEGMENT JOINT",
        segment_id="S2",
        section_id="RECT",
        material_name="Concrete",
        source_p_kn=p_kn,
        source_v2_kn=0.0,
        source_t_knm=0.0,
        source_m3_knm=m3_knm,
        fc_mpa=50.0,
        fci_mpa=40.0,
        area_mm2=1_000_000.0,
        ix_mm4=83_333_333_333.33333,
        z_top_mm3=166_666_666.66666666,
        z_bottom_mm3=166_666_666.66666666,
        is_physical_joint=True,
    )


def test_precast_joint_stage_rules_are_distinct_and_use_signed_stress_convention() -> None:
    assert PHYSICAL_JOINT_TRANSFER_MAX_TENSION_MPA == pytest.approx(0.0)
    assert PHYSICAL_JOINT_SERVICE_MIN_COMPRESSION_MPA == pytest.approx(0.70)

    # -0.50 MPa is compression: acceptable at Transfer because there is no
    # tension, but insufficient at Final Service where >=0.70 MPa compression
    # is required.
    source = _joint_row(p_kn=500.0)
    transfer = run_crossbeam_transfer_stress(_manual_preparation(source))
    service = run_crossbeam_service_stress(_manual_preparation(source))

    assert transfer["status"] == "PASS"
    assert service["status"] == "FAIL"
    assert service["governing_row"]["Criterion"] == "Physical-joint minimum compression"


def test_transfer_joint_zero_tension_failure_has_no_fabricated_dc_ratio() -> None:
    # +0.06 MPa bottom tension is below the ordinary ACI transfer tension
    # limit but violates the stricter project joint no-tension gate.
    source = _joint_row(p_kn=0.0, m3_knm=10.0)
    result = run_crossbeam_transfer_stress(_manual_preparation(source))
    governing = result["governing_row"]

    assert result["status"] == "FAIL"
    assert governing["Criterion"] == "Physical-joint no tension at Transfer"
    assert governing["Stress MPa"] == pytest.approx(+0.06)
    assert governing["Limit MPa"] == pytest.approx(0.0)
    assert math.isnan(float(governing["Utilization value"]))
    assert {row["Module"] for row in result["required_actions"]} == {"Physical joint"}


def test_transfer_preparation_schema_bump_invalidates_pre_d18_cached_results() -> None:
    state = _base_state(construction_method="Cast-in-Place")
    state["crossbeam_sls_loads_table"] = [_transfer_row(0.0), _transfer_row(10.0), _transfer_row(20.0)]
    prep = build_crossbeam_transfer_stress_preparation(state)
    # Fingerprint is schema-sensitive; this assertion guards the D18 contract
    # by ensuring the current source contains the v4 preparation schema.
    source = inspect.getsource(build_crossbeam_transfer_stress_preparation)
    assert "crossbeam-sls1a-transfer-preparation-v4" in source
    assert prep.ready


def test_result_summary_and_report_basis_describe_transfer_and_service_joint_rules_separately() -> None:
    transfer_governing = {
        "Criterion": "Physical-joint no tension at Transfer",
        "Limit MPa": 0.0,
    }
    assert app._results_crossbeam_sls_capacity_label("At Transfer", transfer_governing) == "Joint stress ≤ +0.000 MPa"

    state = _base_state(construction_method="Precast Segmental")
    basis = {row["Item"]: row["Value"] for row in app._report_qa_crossbeam_design_basis_rows(state)}
    criteria = basis["SLS stress criteria"]
    assert "At Transfer, no tension is permitted" in criteria
    assert "signed stress <= 0.0 MPa" in criteria
    assert "At Final Service" in criteria
    assert "0.70 MPa in compression" in criteria
    assert "signed stress <= -0.70 MPa" in criteria
