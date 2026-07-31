from __future__ import annotations

from copy import deepcopy

from concrete_pmm_pro.crossbeam.analysis_foundation import (
    CONSTRUCTION_CAST_IN_PLACE,
    CONSTRUCTION_PRECAST_SEGMENTAL,
    DATASET_SLS_SERVICE,
    DATASET_SLS_TRANSFER,
    DATASET_ULS_FINAL,
    build_crossbeam_analysis_foundation,
)
from concrete_pmm_pro.crossbeam.rebar import (
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
)
from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    duplicate_definition,
)
from concrete_pmm_pro.crossbeam.station_force_contract import (
    build_station_force_analysis_handoff,
    canonical_station_force_contract,
    default_station_force_contract,
)
from concrete_pmm_pro.crossbeam.transverse import default_crossbeam_transverse_templates


def _ready_contract() -> dict[str, object]:
    contract = default_station_force_contract(
        effective_prestress_link={
            "ready": True,
            "source_id": "PT-SOURCE-01",
            "contract_id": "PT-CONTRACT-01",
            "average_total_loss_percent": 20.0,
            "effective_prestress_ratio_percent": 80.0,
        }
    )
    contract.update(
        {
            "fea_program": "SAP2000",
            "model_revision": "CB-R01",
            "confirmed_final_prestress_applied_once": True,
            "confirmed_external_fea_secondary": True,
            "confirmed_uls_final_stage_response_basis": True,
            "confirmed_sls_service_response_basis": True,
            "confirmed_transfer_immediate_loss_basis": True,
            "confirmed_transfer_stage_response_basis": True,
            "confirmed_row_coupled_forces": True,
            "confirmed_uls_dataset": True,
            "confirmed_sls_transfer_dataset": True,
            "confirmed_sls_service_dataset": True,
        }
    )
    return canonical_station_force_contract(contract)


def _row(case: str, *, stage: str | None = None, check_point: str = "") -> dict[str, object]:
    row: dict[str, object] = {
        "Active": True,
        "Station s (m)": 10.0,
        "Check Point": check_point,
        "Case Name": case,
        "P": 900.0,
        "V2": 180.0,
        "T": 2.5,
        "M3": 3.5,
        "Note": "one selected row-coupled FEA state",
    }
    if stage:
        row["Stage"] = stage
    return row


def _handoff(*, check_point: str = "") -> dict[str, object]:
    return build_station_force_analysis_handoff(
        uls_rows=[_row("ULS-01", check_point=check_point)],
        sls_transfer_rows=[_row("SLS-TR-01", stage="Transfer stage", check_point=check_point)],
        sls_service_rows=[_row("SLS-SERV-01", stage="Final service stage", check_point=check_point)],
        contract=_ready_contract(),
        member_length_m=20.0,
    )


def _precast_inputs() -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    definitions = default_section_definitions()
    segments: list[dict[str, object]] = [
        {
            "Segment": "S1",
            "x_start_m": 0.0,
            "x_end_m": 10.0,
            "Section ID": "CB-S01",
            "Section role": "Solid",
        },
        {
            "Segment": "S2",
            "x_start_m": 10.0,
            "x_end_m": 20.0,
            "Section ID": "CB-H01",
            "Section role": "Hollow",
        },
    ]
    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)
    return segments, definitions, zones, longitudinal, transverse


def _build(
    *,
    construction_method: str = CONSTRUCTION_PRECAST_SEGMENTAL,
    check_point: str = "",
    segments: list[dict[str, object]] | None = None,
    definitions: list[dict[str, object]] | None = None,
    zones: list[dict[str, object]] | None = None,
    longitudinal: list[dict[str, object]] | None = None,
    transverse: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    default_segments, default_definitions, default_zones, default_longitudinal, default_transverse = _precast_inputs()
    return build_crossbeam_analysis_foundation(
        handoff=_handoff(check_point=check_point),
        member_length_m=20.0,
        construction_method=construction_method,
        segment_rows=segments if segments is not None else default_segments,
        section_definitions=definitions if definitions is not None else default_definitions,
        rebar_zone_rows=zones if zones is not None else default_zones,
        rebar_template_rows=longitudinal if longitudinal is not None else default_longitudinal,
        transverse_template_rows=transverse if transverse is not None else default_transverse,
    )


def test_precast_joint_without_side_label_maps_all_three_datasets_to_both_faces() -> None:
    foundation = _build()
    assert foundation["ready"] is True
    assert foundation["solver_run"] is False
    rows = foundation["mapped_rows"]
    assert len(rows) == 6
    assert {row["Dataset"] for row in rows} == {
        DATASET_ULS_FINAL,
        DATASET_SLS_TRANSFER,
        DATASET_SLS_SERVICE,
    }
    assert {row["Station face"] for row in rows} == {"s-", "s+"}
    assert {row["Section ID"] for row in rows} == {"CB-S01", "CB-H01"}
    assert all(row["Boundary type"] == "Physical segment joint" for row in rows)
    assert all(row["Physical segment joint"] is True for row in rows)


def test_precast_sls_joint_contexts_carry_project_compression_gate_but_uls_does_not() -> None:
    foundation = _build()
    sls_rows = [row for row in foundation["mapped_rows"] if row["Dataset"].startswith("SLS")]
    uls_rows = [row for row in foundation["mapped_rows"] if row["Dataset"] == DATASET_ULS_FINAL]
    assert sls_rows
    assert all(row["Joint compression gate"] == "REQUIRED >= 0.70 MPa" for row in sls_rows)
    assert all(row["Joint compression gate"] == "N/A" for row in uls_rows)
    assert all(row["Ordinary rebar across physical joint"] == "0 mm2 (LOCKED)" for row in sls_rows)


def test_left_and_right_check_point_labels_select_one_sided_section_context() -> None:
    left = _build(check_point="C1-Left")
    right = _build(check_point="C1-Right")
    assert len(left["mapped_rows"]) == 3
    assert len(right["mapped_rows"]) == 3
    assert {row["Station face"] for row in left["mapped_rows"]} == {"s-"}
    assert {row["Section ID"] for row in left["mapped_rows"]} == {"CB-S01"}
    assert {row["Station face"] for row in right["mapped_rows"]} == {"s+"}
    assert {row["Section ID"] for row in right["mapped_rows"]} == {"CB-H01"}


def test_row_coupled_forces_are_preserved_when_one_source_row_expands_to_two_faces() -> None:
    foundation = _build()
    uls = [row for row in foundation["mapped_rows"] if row["Dataset"] == DATASET_ULS_FINAL]
    assert len({row["Source row"] for row in uls}) == 1
    assert {(row["P (kN; compression +)"], row["V2 (kN; upward +)"], row["T (kN-m; RH +s)"], row["M3 (kN-m; sagging +)"]) for row in uls} == {
        (900.0, 180.0, 2.5, 3.5)
    }


def test_cast_in_place_boundary_is_not_a_physical_joint_and_has_no_070_mpa_gate() -> None:
    definitions = default_section_definitions()
    definitions, second_solid_id = duplicate_definition(definitions, "CB-S01")
    segments: list[dict[str, object]] = [
        {"Segment": "Z1", "x_start_m": 0.0, "x_end_m": 10.0, "Section ID": "CB-S01", "Section role": "Solid"},
        {"Segment": "Z2", "x_start_m": 10.0, "x_end_m": 20.0, "Section ID": second_solid_id, "Section role": "Solid"},
    ]
    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)
    foundation = _build(
        construction_method=CONSTRUCTION_CAST_IN_PLACE,
        segments=segments,
        definitions=definitions,
        zones=zones,
        longitudinal=longitudinal,
        transverse=transverse,
    )
    assert foundation["ready"] is True
    assert len(foundation["mapped_rows"]) == 6
    assert all(row["Boundary type"] == "Section / analysis zone boundary" for row in foundation["mapped_rows"])
    assert all(row["Physical segment joint"] is False for row in foundation["mapped_rows"])
    assert all(row["Joint compression gate"] == "N/A" for row in foundation["mapped_rows"])


def test_unknown_section_id_blocks_station_foundation_without_silent_replacement() -> None:
    segments, definitions, zones, longitudinal, transverse = _precast_inputs()
    broken_segments = deepcopy(segments)
    broken_segments[1]["Section ID"] = "CB-UNKNOWN"
    foundation = _build(
        segments=broken_segments,
        definitions=definitions,
        zones=zones,
        longitudinal=longitudinal,
        transverse=transverse,
    )
    assert foundation["ready"] is False
    assert foundation["status"] == "SOURCE BLOCKED"
    assert any("CB-UNKNOWN" in error for error in foundation["errors"])


def test_analysis_page_routes_crossbeam_to_foundation_without_marking_solver_current() -> None:
    source = open("concrete_pmm_pro/ui/analysis_page.py", encoding="utf-8").read()
    assert 'ANALYSIS_CROSSBEAM_SUBTABS = ["Station Check Foundation"]' in source
    assert "render_crossbeam_analysis_foundation()" in source
    assert "if not is_portal_frame_crossbeam_workflow(settings):\n        mark_analysis_current" in source


def test_non_crossbeam_analysis_subtabs_remain_unchanged() -> None:
    from concrete_pmm_pro.core.analysis import AnalysisModeSettings
    from concrete_pmm_pro.ui.analysis_page import _analysis_subtabs_for_workflow

    assert _analysis_subtabs_for_workflow(AnalysisModeSettings(member_type="column_pier_pmm")) == ["ULS Strength"]
    assert _analysis_subtabs_for_workflow(AnalysisModeSettings(member_type="beam_girder")) == [
        "ULS Strength",
        "SLS / Stress & Cracking",
        "SLS Deflection / Camber",
    ]
    assert _analysis_subtabs_for_workflow(AnalysisModeSettings(member_type="building_beam_girder")) == [
        "ULS Strength",
        "SLS / Stress & Cracking",
        "SLS Deflection / Camber",
    ]
    assert _analysis_subtabs_for_workflow(AnalysisModeSettings(member_type="portal_frame_crossbeam")) == [
        "Station Check Foundation"
    ]
