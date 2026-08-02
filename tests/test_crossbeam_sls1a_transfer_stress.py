from __future__ import annotations

import math

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.crossbeam_sls_transfer import (
    ACI_SERVICE_CLASS_T_TENSION_FACTOR_MPA,
    ACI_SERVICE_CLASS_U_TENSION_FACTOR_MPA,
    ACI_SERVICE_TOTAL_COMPRESSION_FACTOR,
    ACI_TRANSFER_COMPRESSION_FACTOR,
    ACI_TRANSFER_TENSION_FACTOR_MPA,
    CROSSBEAM_TRANSFER_RESULT_HASH_KEY,
    CROSSBEAM_TRANSFER_RESULT_KEY,
    PHYSICAL_JOINT_MIN_COMPRESSION_MPA,
    CrossbeamTransferPreparation,
    PreparedCrossbeamTransferRow,
    build_crossbeam_service_stress_preparation,
    build_crossbeam_transfer_stress_preparation,
    run_crossbeam_service_stress,
    run_crossbeam_transfer_stress,
)
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials
from concrete_pmm_pro.crossbeam.prestress_loss import (
    CB_LOSS_ES_COLUMN_ROWS_KEY,
    CB_LOSS_ES_CONSTRUCTION_METHOD_KEY,
    CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY,
)
from concrete_pmm_pro.crossbeam.rebar import (
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_DEFINITIONS_KEY,
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY,
    CB_STATION_FORCE_CONTRACT_KEY,
    default_station_force_contract,
)
from concrete_pmm_pro.crossbeam.transverse import default_crossbeam_transverse_templates
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows


def _base_state(*, construction_method: str = "Precast Segmental") -> dict[str, object]:
    length_m = 20.0
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(default_crossbeam_segment_rows(length_m), definitions)
    solid_id = str(definitions[0]["Section ID"])
    for segment in segments:
        segment["Section ID"] = solid_id
        segment["Section role"] = "Solid"
    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)
    link = {
        "ready": False,
        "source_id": "sls1a-external-fea-source",
        "contract_id": "sls1a-transfer-contract",
        "average_total_loss_percent": 20.0,
        "effective_prestress_ratio_percent": 80.0,
        "average_effective_stress_mpa": 0.0,
    }
    return {
        "crossbeam_ui1_length_m": length_m,
        "crossbeam_ui1_segment_layout_rows": segments,
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        CB_RB_TEMPLATE_ROWS_KEY: longitudinal,
        CB_RB_ZONE_ROWS_KEY: zones,
        CB_TR_TEMPLATE_ROWS_KEY: transverse,
        CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY: link,
        CB_STATION_FORCE_CONTRACT_KEY: default_station_force_contract(
            effective_prestress_link=link
        ),
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: construction_method,
        CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY: 0.80,
        CB_LOSS_ES_COLUMN_ROWS_KEY: [
            {
                "Column ID": "C1",
                "Station s (m)": 1.5,
                "Height (m)": 10.0,
                "Shape": "Rectangular — Equal Chamfer 4 Corners",
                "Btrans (mm)": 2000.0,
                "Blong (mm)": 1500.0,
                "Corner (mm)": 200.0,
                "Diameter (mm)": 2000.0,
                "f'c (MPa)": 35.0,
            }
        ],
        "concrete_materials": default_concrete_materials(),
        "load_cases": [],
        "crossbeam_sls_loads_table": [],
    }


def _transfer_row(station: float, *, case: str = "TR-1", check_point: str = "", p: float = 5000.0, m3: float = 0.0) -> dict[str, object]:
    return {
        "Active": True,
        "Station s (m)": station,
        "Check Point": check_point,
        "Case Name": case,
        "Stage": "Transfer stage",
        "P": p,
        "V2": 125.0,
        "T": 18.0,
        "M3": m3,
        "Note": "row-coupled external FEA Transfer response",
    }


def _complete_joint_rows(*, case: str = "TR-1") -> list[dict[str, object]]:
    # Default Crossbeam segment joints at 3, 7, 10, 13, and 17 m.
    return [_transfer_row(station, case=case, m3=750.0 if station == 10.0 else 0.0) for station in (0.0, 3.0, 7.0, 10.0, 13.0, 17.0, 20.0)]


def _service_row(station: float, *, case: str = "SERV-1", p: float = 5000.0, m3: float = 0.0) -> dict[str, object]:
    row = _transfer_row(station, case=case, p=p, m3=m3)
    row["Stage"] = "Final service stage"
    row["Note"] = "verified final-service external FEA total response"
    return row


def _manual_preparation(row: PreparedCrossbeamTransferRow) -> CrossbeamTransferPreparation:
    return CrossbeamTransferPreparation(
        ready=True,
        rows=(row,),
        errors=(),
        warnings=(),
        info=(),
        fingerprint="manual-benchmark",
        demand_rows=(),
        member_length_m=20.0,
        construction_method="Cast-in-Place",
        stressing_strength_ratio=0.8,
        joint_stations_m=(),
        column_rows=(),
    )


def test_transfer_stress_rectangular_hand_check_preserves_p_m3_signs_and_aci_limits() -> None:
    # 1000 x 1000 rectangle: A=1,000,000 mm2 and Z=166,666,666.667 mm3.
    # P=1000 kN -> -1 MPa. M3=500 kN-m -> top -3 MPa, bottom +3 MPa.
    # Total top=-4 MPa and bottom=+2 MPa.
    source = PreparedCrossbeamTransferRow(
        station_m=5.0,
        check_point="Benchmark",
        case_name="TR-BENCH",
        section_face="INTERIOR",
        location_type="SEGMENT / ZONE INTERIOR",
        segment_id="SEG-1",
        section_id="RECT",
        material_name="Concrete",
        source_p_kn=1000.0,
        source_v2_kn=0.0,
        source_t_knm=0.0,
        source_m3_knm=500.0,
        fc_mpa=50.0,
        fci_mpa=40.0,
        area_mm2=1_000_000.0,
        ix_mm4=83_333_333_333.33333,
        z_top_mm3=166_666_666.66666666,
        z_bottom_mm3=166_666_666.66666666,
        is_physical_joint=False,
    )
    result = run_crossbeam_transfer_stress(_manual_preparation(source))
    row = result["rows"][0]

    assert row["Axial stress MPa"] == pytest.approx(-1.0)
    assert row["Top bending stress MPa"] == pytest.approx(-3.0)
    assert row["Bottom bending stress MPa"] == pytest.approx(3.0)
    assert row["Top stress MPa"] == pytest.approx(-4.0)
    assert row["Bottom stress MPa"] == pytest.approx(2.0)
    assert row["Compression limit MPa"] == pytest.approx(-ACI_TRANSFER_COMPRESSION_FACTOR * 40.0)
    assert row["Tension limit MPa"] == pytest.approx(ACI_TRANSFER_TENSION_FACTOR_MPA * math.sqrt(40.0))
    assert row["Status"] == "FAIL"
    assert result["status"] == "FAIL"
    assert any(action["Module"] == "ACI transfer tension" for action in result["required_actions"])


def test_final_service_hand_check_uses_total_load_limit_and_classifies_u_t_c() -> None:
    def result_for(moment_knm: float) -> dict[str, object]:
        source = PreparedCrossbeamTransferRow(
            station_m=5.0,
            check_point="Benchmark",
            case_name="SERV-BENCH",
            section_face="INTERIOR",
            location_type="SEGMENT / ZONE INTERIOR",
            segment_id="SEG-1",
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
        return run_crossbeam_service_stress(_manual_preparation(source))

    class_u = result_for(500.0)
    assert class_u["status"] == "PASS"
    assert class_u["rows"][0]["Bottom ACI class"] == "Class U"
    assert class_u["rows"][0]["Compression limit MPa"] == pytest.approx(
        -ACI_SERVICE_TOTAL_COMPRESSION_FACTOR * 40.0
    )
    assert class_u["rows"][0]["Tension limit MPa"] == pytest.approx(
        ACI_SERVICE_CLASS_U_TENSION_FACTOR_MPA * math.sqrt(40.0)
    )

    class_t = result_for(1000.0)
    assert class_t["status"] == "REVIEW"
    assert class_t["rows"][0]["Bottom ACI class"] == "Class T"
    assert any(action["Module"] == "ACI Class T service route" for action in class_t["required_actions"])

    class_c = result_for(1300.0)
    assert class_c["status"] == "REVIEW"
    assert class_c["rows"][0]["Bottom ACI class"] == "Class C"
    assert class_c["rows"][0]["Class T upper MPa"] == pytest.approx(
        ACI_SERVICE_CLASS_T_TENSION_FACTOR_MPA * math.sqrt(40.0)
    )
    assert any(action["Module"] == "ACI Class C service route" for action in class_c["required_actions"])


def test_final_service_preparation_filters_stage_and_auto_interpolates_precast_joints() -> None:
    state = _base_state()
    state["crossbeam_sls_loads_table"] = [
        _transfer_row(0.0),
        *[
            _service_row(float(station), p=4000.0 + station, m3=50.0 * station)
            for station in range(0, 21, 2)
        ],
    ]

    preparation = build_crossbeam_service_stress_preparation(state)

    assert preparation.ready, preparation.errors
    assert {row["Stage"] for row in preparation.demand_rows} == {"Final service stage"}
    assert [row["Station s (m)"] for row in preparation.derived_joint_rows] == pytest.approx(
        [3.0, 7.0, 13.0, 17.0]
    )
    for station in preparation.joint_stations_m:
        faces = {
            row.section_face
            for row in preparation.rows
            if row.station_m == pytest.approx(station)
        }
        assert faces == {"LEFT LIMIT (s-)", "RIGHT LIMIT (s+)"}


def test_precast_preparation_expands_each_unlabeled_joint_row_to_s_minus_and_s_plus() -> None:
    state = _base_state()
    state["crossbeam_sls_loads_table"] = _complete_joint_rows()
    preparation = build_crossbeam_transfer_stress_preparation(state)

    assert preparation.ready, preparation.errors
    assert preparation.joint_stations_m == pytest.approx((3.0, 7.0, 10.0, 13.0, 17.0))
    for station in preparation.joint_stations_m:
        faces = {
            row.section_face
            for row in preparation.rows
            if row.station_m == pytest.approx(station)
        }
        assert faces == {"LEFT LIMIT (s-)", "RIGHT LIMIT (s+)"}
    # External FEA total resultants do not require the generic load_cases table
    # or a ready effective-prestress tendon-capacity gate.
    assert state["load_cases"] == []
    assert state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY]["ready"] is False


def test_precast_preparation_blocks_missing_joint_for_every_transfer_case() -> None:
    state = _base_state()
    state["crossbeam_sls_loads_table"] = _complete_joint_rows(case="TR-1") + [
        _transfer_row(0.0, case="TR-2"),
    ]
    preparation = build_crossbeam_transfer_stress_preparation(state)

    assert preparation.ready is False
    assert any("TR-2: physical joint at s = 3.000000 m" in error for error in preparation.errors)
    assert not any("TR-1: physical joint" in error for error in preparation.errors)


def test_precast_preparation_auto_interpolates_missing_joint_stations_and_both_faces() -> None:
    state = _base_state()
    state["crossbeam_sls_loads_table"] = [
        _transfer_row(float(station), p=3000.0 + 10.0 * station, m3=100.0 * station)
        for station in range(0, 21, 2)
    ]

    preparation = build_crossbeam_transfer_stress_preparation(state)

    assert preparation.ready, preparation.errors
    assert [row["Station s (m)"] for row in preparation.derived_joint_rows] == pytest.approx(
        [3.0, 7.0, 13.0, 17.0]
    )
    joint_3 = preparation.derived_joint_rows[0]
    assert joint_3["P"] == pytest.approx(3030.0)
    assert joint_3["M3"] == pytest.approx(300.0)
    assert joint_3["_interpolation_from_m"] == pytest.approx([2.0, 4.0])
    for station in preparation.joint_stations_m:
        faces = {
            row.section_face
            for row in preparation.rows
            if row.station_m == pytest.approx(station)
        }
        assert faces == {"LEFT LIMIT (s-)", "RIGHT LIMIT (s+)"}
    assert any("linearly interpolated" in warning for warning in preparation.warnings)


def test_explicit_single_joint_side_is_blocked_until_opposite_face_is_imported() -> None:
    state = _base_state()
    rows = _complete_joint_rows()
    rows = [row for row in rows if float(row["Station s (m)"]) != 10.0]
    rows.append(_transfer_row(10.0, check_point="Joint Left", m3=750.0))
    state["crossbeam_sls_loads_table"] = rows
    preparation = build_crossbeam_transfer_stress_preparation(state)

    assert preparation.ready is False
    assert any("RIGHT LIMIT (s+)" in error for error in preparation.errors)

    state["crossbeam_sls_loads_table"].append(
        _transfer_row(10.0, check_point="Joint Right", m3=750.0)
    )
    repaired = build_crossbeam_transfer_stress_preparation(state)
    assert repaired.ready, repaired.errors


def test_cast_in_place_route_has_no_physical_joint_minimum_compression_gate() -> None:
    state = _base_state(construction_method="Cast-in-Place")
    state["crossbeam_sls_loads_table"] = [
        _transfer_row(0.0),
        _transfer_row(10.0, m3=500.0),
        _transfer_row(20.0),
    ]
    preparation = build_crossbeam_transfer_stress_preparation(state)

    assert preparation.ready, preparation.errors
    assert preparation.joint_stations_m == ()
    result = run_crossbeam_transfer_stress(preparation)
    assert all(row["Location type"] != "PHYSICAL SEGMENT JOINT" for row in result["rows"])
    assert all(math.isnan(float(row["Joint utilization"])) for row in result["fiber_rows"])


def test_joint_minimum_compression_is_checked_for_both_fibers_and_creates_action() -> None:
    source = PreparedCrossbeamTransferRow(
        station_m=10.0,
        check_point="Joint",
        case_name="TR-JOINT",
        section_face="LEFT LIMIT (s-)",
        location_type="PHYSICAL SEGMENT JOINT",
        segment_id="SEG-1",
        section_id="RECT",
        material_name="Concrete",
        source_p_kn=500.0,
        source_v2_kn=0.0,
        source_t_knm=0.0,
        source_m3_knm=0.0,
        fc_mpa=50.0,
        fci_mpa=40.0,
        area_mm2=1_000_000.0,
        ix_mm4=83_333_333_333.33333,
        z_top_mm3=166_666_666.66666666,
        z_bottom_mm3=166_666_666.66666666,
        is_physical_joint=True,
    )
    result = run_crossbeam_transfer_stress(_manual_preparation(source))

    assert result["status"] == "FAIL"
    assert {row["Fiber"] for row in result["fiber_rows"]} == {"Top", "Bottom"}
    assert all(row["Criterion"] == "Physical-joint minimum compression" for row in result["fiber_rows"])
    assert all(row["Joint compression margin MPa"] == pytest.approx(-0.20) for row in result["fiber_rows"])
    assert result["required_actions"][0]["Module"] == "Physical joint"


def test_joint_tension_failure_reports_both_joint_and_aci_tension_actions() -> None:
    source = PreparedCrossbeamTransferRow(
        station_m=10.0,
        check_point="Joint",
        case_name="TR-JOINT-TENSION",
        section_face="RIGHT LIMIT (s+)",
        location_type="PHYSICAL SEGMENT JOINT",
        segment_id="SEG-2",
        section_id="RECT",
        material_name="Concrete",
        source_p_kn=0.0,
        source_v2_kn=0.0,
        source_t_knm=0.0,
        source_m3_knm=400.0,
        fc_mpa=50.0,
        fci_mpa=40.0,
        area_mm2=1_000_000.0,
        ix_mm4=83_333_333_333.33333,
        z_top_mm3=166_666_666.66666666,
        z_bottom_mm3=166_666_666.66666666,
        is_physical_joint=True,
    )
    result = run_crossbeam_transfer_stress(_manual_preparation(source))
    modules = {action["Module"] for action in result["required_actions"]}
    assert "Physical joint" in modules
    assert "ACI transfer tension" in modules


def test_transfer_fingerprint_is_stable_and_changes_with_engineering_or_chart_sources() -> None:
    state = _base_state(construction_method="Cast-in-Place")
    state["crossbeam_sls_loads_table"] = [_transfer_row(0.0), _transfer_row(10.0), _transfer_row(20.0)]
    first = build_crossbeam_transfer_stress_preparation(state)
    second = build_crossbeam_transfer_stress_preparation(state)
    assert first.ready and second.ready
    assert first.fingerprint == second.fingerprint

    state["crossbeam_sls_loads_table"][1]["M3"] = 100.0
    changed_demand = build_crossbeam_transfer_stress_preparation(state)
    assert changed_demand.fingerprint != first.fingerprint

    state[CB_LOSS_ES_COLUMN_ROWS_KEY][0]["Blong (mm)"] = 1800.0
    changed_column = build_crossbeam_transfer_stress_preparation(state)
    assert changed_column.fingerprint != changed_demand.fingerprint

    state[CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY] = 0.75
    changed_fci = build_crossbeam_transfer_stress_preparation(state)
    assert changed_fci.fingerprint != changed_column.fingerprint


def test_transfer_preparation_ignores_final_service_rows_but_blocks_invalid_fci_ratio() -> None:
    state = _base_state(construction_method="Cast-in-Place")
    service = _transfer_row(5.0, case="SERV")
    service["Stage"] = "Final service stage"
    state["crossbeam_sls_loads_table"] = [
        _transfer_row(0.0),
        _transfer_row(20.0),
        service,
    ]
    preparation = build_crossbeam_transfer_stress_preparation(state)
    assert preparation.ready, preparation.errors
    assert {row["Case Name"] for row in preparation.demand_rows} == {"TR-1"}

    state[CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY] = 0.10
    blocked = build_crossbeam_transfer_stress_preparation(state)
    assert blocked.ready is False
    assert any("between 0.50 and 1.00" in error for error in blocked.errors)


def test_analysis_page_routes_crossbeam_sls_to_sls1a_and_exposes_cache_and_chart_contract() -> None:
    source = open("concrete_pmm_pro/ui/analysis_page.py", encoding="utf-8").read()
    block = source[source.index("def render_analysis_sls_stress"):source.index("def render_analysis_sls_deflection_camber")]
    assert "_render_crossbeam_transfer_stress_workspace()" in block
    assert "_render_crossbeam_service_stress_workspace()" in block
    assert '["At Transfer", "At Final Service"]' in block
    assert "generic SLS solver" not in block
    assert "CROSSBEAM_TRANSFER_RESULT_KEY" in source
    assert "CROSSBEAM_TRANSFER_RESULT_HASH_KEY" in source
    assert "CROSSBEAM_SERVICE_RESULT_KEY" in source
    assert "CROSSBEAM_SERVICE_RESULT_HASH_KEY" in source
    assert "Stored Crossbeam Transfer Stress result is STALE" in source
    assert "Stored Crossbeam Final Service Stress result is STALE" in source
    assert "Column bands show actual Blong footprints" in source
    assert "no compliance is inferred between unverified stations" in source


def test_transfer_figure_contains_stress_limits_joint_marker_and_column_geometry() -> None:
    from concrete_pmm_pro.ui.analysis_page import _make_crossbeam_transfer_stress_figure

    result_rows = pd.DataFrame(
        [
            {
                "Status": "PASS", "Station s (m)": 0.0, "Case": "TR-1", "Section face": "INTERIOR",
                "Location type": "SEGMENT / ZONE INTERIOR", "Section ID": "S1", "Top stress MPa": -4.0,
                "Bottom stress MPa": -2.0, "Compression limit MPa": -21.6, "Tension limit MPa": 1.5,
            },
            {
                "Status": "PASS", "Station s (m)": 10.0, "Case": "TR-1", "Section face": "LEFT LIMIT (s-)",
                "Location type": "PHYSICAL SEGMENT JOINT", "Section ID": "S1", "Top stress MPa": -3.0,
                "Bottom stress MPa": -1.0, "Compression limit MPa": -21.6, "Tension limit MPa": 1.5,
            },
            {
                "Status": "PASS", "Station s (m)": 20.0, "Case": "TR-1", "Section face": "INTERIOR",
                "Location type": "SEGMENT / ZONE INTERIOR", "Section ID": "S1", "Top stress MPa": -4.0,
                "Bottom stress MPa": -2.0, "Compression limit MPa": -21.6, "Tension limit MPa": 1.5,
            },
        ]
    )
    fiber_rows = pd.DataFrame(
        [
            {"Case": "TR-1", "Station s (m)": 10.0, "Fiber": "Top", "Stress MPa": -3.0, "Compression utilization": 0.14, "Tension utilization": 0.0, "Joint utilization": 0.23},
            {"Case": "TR-1", "Station s (m)": 10.0, "Fiber": "Bottom", "Stress MPa": -1.0, "Compression utilization": 0.05, "Tension utilization": 0.0, "Joint utilization": 0.70},
        ]
    )
    figure = _make_crossbeam_transfer_stress_figure(
        result_rows,
        fiber_rows,
        case_name="TR-1",
        member_length_m=20.0,
        column_rows=[{"Column ID": "C1", "Station s (m)": 1.5, "Blong (mm)": 1500.0}],
    )
    trace_names = {str(trace.name) for trace in figure.data}
    assert {"Top total stress", "Bottom total stress", "Compression limit", "Tension limit", "Joint min comp."}.issubset(trace_names)
    assert "Gov. compression" in trace_names
    assert "Gov. joint" in trace_names
    assert figure.layout.xaxis.range == (0.0, 20.0)
    assert any(shape.type == "rect" and float(shape.x0) == pytest.approx(0.75) and float(shape.x1) == pytest.approx(2.25) for shape in figure.layout.shapes)
