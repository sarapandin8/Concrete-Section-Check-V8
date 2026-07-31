from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.crossbeam.analysis_charts import make_crossbeam_station_coverage_figure
from concrete_pmm_pro.crossbeam.analysis_foundation import (
    CONSTRUCTION_PRECAST_SEGMENTAL,
    DATASET_ORDER,
    STATION_COVERAGE_READY,
    build_crossbeam_analysis_foundation,
)
from concrete_pmm_pro.crossbeam.construction_stage import default_column_stage_rows
from concrete_pmm_pro.crossbeam.rebar import (
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
)
from concrete_pmm_pro.crossbeam.section_library import default_section_definitions
from concrete_pmm_pro.crossbeam.station_force_contract import (
    build_station_force_analysis_handoff,
    canonical_station_force_contract,
    default_station_force_contract,
)
from concrete_pmm_pro.crossbeam.transverse import default_crossbeam_transverse_templates
from concrete_pmm_pro.ui.analysis_page import _analysis_runtime_state_for_workflow


APP_SOURCE = Path("app.py").read_text(encoding="utf-8")
ANALYSIS_SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
CROSSBEAM_PAGE_SOURCE = Path("concrete_pmm_pro/ui/crossbeam_analysis_page.py").read_text(encoding="utf-8")


def _ready_contract() -> dict[str, object]:
    contract = default_station_force_contract(
        effective_prestress_link={
            "ready": True,
            "source_id": "PT-SOURCE-QA",
            "contract_id": "PT-CONTRACT-QA",
            "average_total_loss_percent": 20.0,
            "effective_prestress_ratio_percent": 80.0,
        }
    )
    contract.update(
        {
            "fea_program": "SAP2000",
            "model_revision": "CB-ANALYSIS1A-QA",
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


def _station_rows(prefix: str, *, stage: str | None = None) -> list[dict[str, object]]:
    contexts = [
        (0.0, "Left end"),
        (1.5, "C1-Left"),
        (1.5, "C1-Right"),
        (10.0, "Segment joint"),
        (18.5, "C2-Left"),
        (18.5, "C2-Right"),
        (20.0, "Right end"),
    ]
    rows: list[dict[str, object]] = []
    for index, (station, check_point) in enumerate(contexts, start=1):
        row: dict[str, object] = {
            "Active": True,
            "Station s (m)": station,
            "Check Point": check_point,
            "Case Name": f"{prefix}-{index:02d}",
            "P": 800.0 + 10.0 * index,
            "V2": 120.0 + 5.0 * index,
            "T": 1.5 + 0.1 * index,
            "M3": 2.5 + 0.2 * index,
            "Note": "one populated row-coupled FEA state",
        }
        if stage:
            row["Stage"] = stage
        rows.append(row)
    return rows


def _populated_foundation() -> dict[str, object]:
    length_m = 20.0
    handoff = build_station_force_analysis_handoff(
        uls_rows=_station_rows("ULS"),
        sls_transfer_rows=_station_rows("TR", stage="Transfer stage"),
        sls_service_rows=_station_rows("SERV", stage="Final service stage"),
        contract=_ready_contract(),
        member_length_m=length_m,
    )
    segments = [
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
    longitudinal = deepcopy(default_crossbeam_rebar_templates())
    for index, row in enumerate(longitudinal, start=1):
        row["Top As mm²"] = 1200.0 + 100.0 * index
        row["Bottom As mm²"] = 1400.0 + 100.0 * index
        row["Side As mm²"] = 800.0 + 50.0 * index
        row["Av/s mm²/mm"] = 1.0 + 0.1 * index
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)
    columns = default_column_stage_rows(length_m)
    return build_crossbeam_analysis_foundation(
        handoff=handoff,
        member_length_m=length_m,
        construction_method=CONSTRUCTION_PRECAST_SEGMENTAL,
        segment_rows=segments,
        section_definitions=default_section_definitions(),
        rebar_zone_rows=zones,
        rebar_template_rows=longitudinal,
        transverse_template_rows=transverse,
        column_rows=columns,
    )


def test_populated_three_stage_source_mapping_covers_member_ends_columns_and_joint_faces() -> None:
    foundation = _populated_foundation()
    assert foundation["ready"] is True
    assert foundation["solver_run"] is False
    assert {row["Dataset"] for row in foundation["mapped_rows"]} == set(DATASET_ORDER)

    coverage = foundation["station_coverage"]
    assert coverage["status"] == STATION_COVERAGE_READY
    assert coverage["ready"] is True
    assert coverage["covered_requirements"] == coverage["required_requirements"]
    assert coverage["missing_rows"] == []

    joint_rows = [
        row
        for row in foundation["mapped_rows"]
        if row["Station s (m)"] == 10.0
    ]
    assert {row["Station face"] for row in joint_rows} == {"s-", "s+"}
    assert {row["Section ID"] for row in joint_rows} == {"CB-S01", "CB-H01"}

    c1_rows = [row for row in foundation["mapped_rows"] if row["Column ID"] == "C1"]
    assert {row["Column side"] for row in c1_rows} == {"LEFT", "RIGHT"}


def test_full_length_chart_has_member_range_column_footprints_centerlines_and_all_dataset_markers() -> None:
    foundation = _populated_foundation()
    figure = make_crossbeam_station_coverage_figure(foundation)

    assert list(figure.layout.xaxis.range) == [0.0, 20.0]
    trace_names = {str(trace.name) for trace in figure.data}
    assert trace_names == set(DATASET_ORDER)

    annotations = [str(item.text) for item in figure.layout.annotations]
    assert any("C1" in text and "1.500" in text for text in annotations)
    assert any("C2" in text and "18.500" in text for text in annotations)
    assert any("S1" in text and "CB-S01" in text for text in annotations)
    assert any("S2" in text and "CB-H01" in text for text in annotations)

    rectangles = [shape for shape in figure.layout.shapes if str(shape.type) == "rect"]
    lines = [shape for shape in figure.layout.shapes if str(shape.type) == "line"]
    # Two Segment bands + two physical Column footprints.
    assert len(rectangles) >= 4
    # Member ends, one physical joint, and two Column centerlines.
    assert len(lines) >= 5


def test_crossbeam_runtime_card_is_input_review_only_even_when_generic_status_says_ready() -> None:
    settings = AnalysisModeSettings(member_type="portal_frame_crossbeam")
    value, detail, status = _analysis_runtime_state_for_workflow(
        settings,
        {"analysis_status": "Ready to review"},
    )
    assert value == "INPUT REVIEW ONLY"
    assert "no SLS/ULS solver" in detail
    assert status == "warning"


def test_non_crossbeam_runtime_card_preserves_existing_status_wording() -> None:
    settings = AnalysisModeSettings(member_type="beam_girder")
    value, detail, status = _analysis_runtime_state_for_workflow(
        settings,
        {"analysis_status": "Current"},
    )
    assert value == "Current"
    assert "solver routing is unchanged" in detail
    assert status == "info"


def test_crossbeam_sidebar_and_main_router_share_station_foundation_navigation() -> None:
    assert 'return ["Station Check Foundation"]' in APP_SOURCE
    assert '"Station Check Foundation": "A1"' in APP_SOURCE
    assert 'ANALYSIS_CROSSBEAM_SUBTABS = ["Station Check Foundation"]' in ANALYSIS_SOURCE
    assert "render_crossbeam_analysis_foundation()" in ANALYSIS_SOURCE


def test_analysis_cards_display_full_code_edition_and_hide_developer_diagnostics_for_crossbeam() -> None:
    assert "code = workflow_project_code_label_from_session(st.session_state)" in ANALYSIS_SOURCE
    assert '"INPUT REVIEW ONLY"' in ANALYSIS_SOURCE
    assert "if not is_portal_frame_crossbeam_workflow(settings):\n        _render_runtime_diagnostics_expander()" in ANALYSIS_SOURCE


def test_crossbeam_page_renders_shared_full_length_chart_and_explicit_no_interpolation_caption() -> None:
    assert "make_crossbeam_station_coverage_figure" in CROSSBEAM_PAGE_SOURCE
    assert '"Full-Length Source Coverage"' in CROSSBEAM_PAGE_SOURCE
    assert "No production stress/capacity envelope is interpolated" in CROSSBEAM_PAGE_SOURCE
    assert "actual Column footprint" in CROSSBEAM_PAGE_SOURCE
