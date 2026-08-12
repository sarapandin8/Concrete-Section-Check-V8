from __future__ import annotations

import math

import pandas as pd
import pytest

import app
from concrete_pmm_pro.analysis.crossbeam_sls_transfer import (
    PreparedCrossbeamTransferRow,
    build_crossbeam_service_stress_preparation,
    build_crossbeam_transfer_stress_preparation,
    run_crossbeam_service_stress,
    run_crossbeam_transfer_stress,
)
from concrete_pmm_pro.ui.analysis_page import _make_crossbeam_transfer_stress_figure
from tests.test_crossbeam_sls1a_transfer_stress import (
    _base_state,
    _manual_preparation,
    _service_row,
)


def _joint_transfer_small_tension() -> PreparedCrossbeamTransferRow:
    return PreparedCrossbeamTransferRow(
        station_m=10.0,
        check_point="Joint",
        case_name="TR-JOINT",
        section_face="LEFT LIMIT (s-)",
        location_type="PHYSICAL SEGMENT JOINT",
        segment_id="S2",
        section_id="RECT",
        material_name="Concrete",
        source_p_kn=0.0,
        source_v2_kn=0.0,
        source_t_knm=0.0,
        source_m3_knm=10.0,
        fc_mpa=50.0,
        fci_mpa=40.0,
        area_mm2=1_000_000.0,
        ix_mm4=83_333_333_333.33333,
        z_top_mm3=166_666_666.66666666,
        z_bottom_mm3=166_666_666.66666666,
        is_physical_joint=True,
    )


def _service_source(*, moment_knm: float) -> PreparedCrossbeamTransferRow:
    return PreparedCrossbeamTransferRow(
        station_m=5.0,
        check_point="Service benchmark",
        case_name="ULS-01",
        section_face="INTERIOR",
        location_type="SEGMENT / ZONE INTERIOR",
        segment_id="S2",
        section_id="RECT",
        material_name="Concrete",
        source_p_kn=1000.0,
        source_v2_kn=0.0,
        source_t_knm=0.0,
        source_m3_knm=moment_knm,
        fc_mpa=40.0,
        fci_mpa=40.0,
        area_mm2=1_000_000.0,
        ix_mm4=83_333_333_333.33333,
        z_top_mm3=166_666_666.66666666,
        z_bottom_mm3=166_666_666.66666666,
        is_physical_joint=False,
    )


def test_transfer_zero_gate_row_does_not_show_aci_ratio_as_governing_utilization() -> None:
    result = run_crossbeam_transfer_stress(_manual_preparation(_joint_transfer_small_tension()))
    row = result["rows"][0]

    assert row["Status"] == "FAIL"
    assert math.isnan(float(row["Governing utilization"]))
    assert float(row["ACI governing utilization"]) < 1.0
    assert result["governing_row"]["Criterion"] == "Physical-joint no tension at Transfer"


def test_final_service_classification_fields_are_explicit_and_class_c_has_no_active_060fc_limit() -> None:
    class_u = run_crossbeam_service_stress(_manual_preparation(_service_source(moment_knm=500.0)))
    class_c = run_crossbeam_service_stress(_manual_preparation(_service_source(moment_knm=1300.0)))

    urow = class_u["rows"][0]
    crow = class_c["rows"][0]
    assert urow["Section ACI class"] == "Class U"
    assert math.isfinite(float(urow["Class U/T compression limit MPa"]))
    assert urow["Class U threshold MPa"] < urow["Class C threshold MPa"]

    assert crow["Section ACI class"] == "Class C"
    assert math.isnan(float(crow["Class U/T compression limit MPa"]))
    assert math.isnan(float(crow["Compression limit MPa"]))
    assert math.isfinite(float(crow["0.60f'c reference MPa"]))
    assert crow["Class U threshold MPa"] < crow["Class C threshold MPa"]


def test_final_service_figure_uses_classification_threshold_names_not_generic_tension_limit() -> None:
    result = run_crossbeam_service_stress(_manual_preparation(_service_source(moment_knm=1300.0)))
    result_rows = pd.DataFrame(result["rows"])
    fiber_rows = pd.DataFrame(result["fiber_rows"])
    figure = _make_crossbeam_transfer_stress_figure(
        result_rows,
        fiber_rows,
        case_name="ULS-01",
        member_length_m=20.0,
        column_rows=[],
        stage_title="Concrete Stress At Final Service",
        joint_transfer_no_tension=False,
        compression_column="Class U/T compression limit MPa",
        compression_trace_name="Class U/T compression limit",
        tension_column="Class U threshold MPa",
        tension_trace_name="Class U threshold",
        upper_class_threshold_column="Class C threshold MPa",
        upper_class_threshold_trace_name="Class C threshold",
    )
    names = {str(trace.name) for trace in figure.data}
    assert "Class U threshold" in names
    assert "Class C threshold" in names
    assert "Class U/T compression limit" in names
    assert "Tension limit" not in names


def test_final_service_stage_routes_by_stage_and_preserves_imported_case_label_verbatim() -> None:
    state = _base_state(construction_method="Cast-in-Place")
    state["crossbeam_sls_loads_table"] = [
        _service_row(0.0, case="ULS-01"),
        _service_row(10.0, case="ULS-01", m3=500.0),
        _service_row(20.0, case="ULS-01"),
    ]
    preparation = build_crossbeam_service_stress_preparation(state)

    assert preparation.ready, preparation.errors
    assert {row["Stage"] for row in preparation.demand_rows} == {"Final service stage"}
    assert {row.case_name for row in preparation.rows} == {"ULS-01"}


def test_d19_schema_bumps_force_rebuild_of_transfer_and_final_service_stored_results() -> None:
    import inspect

    assert "crossbeam-sls1a-transfer-preparation-v5" in inspect.getsource(build_crossbeam_transfer_stress_preparation)
    assert "crossbeam-sls1b-service-preparation-v2" in inspect.getsource(build_crossbeam_service_stress_preparation)


def test_result_summary_capacity_labels_use_final_service_classification_language() -> None:
    assert app._results_crossbeam_sls_capacity_label(
        "At Final Service", {"Criterion": "ACI Class U tension", "Limit MPa": 4.159}
    ) == "Class U threshold = +4.159 MPa"
    assert app._results_crossbeam_sls_capacity_label(
        "At Final Service", {"Criterion": "ACI Class T classification", "Limit MPa": 6.708}
    ) == "Class C threshold = +6.708 MPa"
    assert app._results_crossbeam_sls_capacity_label(
        "At Final Service", {"Criterion": "ACI Class C cracked-section route", "Limit MPa": 6.708}
    ) == "Cracked transformed-section verification required"
