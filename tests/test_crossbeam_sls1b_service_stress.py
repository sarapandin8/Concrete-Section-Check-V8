from __future__ import annotations

import math
from pathlib import Path

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.concrete_materials import c45_precast_material
from concrete_pmm_pro.crossbeam.analysis_charts import make_crossbeam_service_stress_figure
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_DEFINITIONS_KEY,
    default_section_definitions,
)
from concrete_pmm_pro.crossbeam.sls_service import (
    CB_ANALYSIS_SLS_SERVICE_RESULT_KEY,
    CB_ANALYSIS_SLS_SERVICE_SUSTAINED_CASES_KEY,
    calculate_crossbeam_service_stress,
    service_stress_input_fingerprint,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)


PAGE_SOURCE = Path("concrete_pmm_pro/ui/crossbeam_analysis_page.py").read_text(encoding="utf-8")
ANALYSIS_SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
PROJECT_IO_SOURCE = Path("concrete_pmm_pro/io/project_io.py").read_text(encoding="utf-8")


def _context(
    *,
    context_id: str,
    station: float,
    face: str = "INTERIOR",
    case: str = "SERV-TOTAL",
    p_kn: float = 1000.0,
    m_knm: float = 100.0,
    physical_joint: bool = False,
) -> dict[str, object]:
    return {
        "Dataset": "SLS At Service",
        "Stage": "Final service stage",
        "Source row": f"SLS At Service:{context_id}",
        "Case / Combination": case,
        "Station s (m)": station,
        "Check Point": "",
        "Station face": face,
        "Boundary type": "Physical segment joint" if physical_joint else "Interior",
        "Physical segment joint": physical_joint,
        "Segment / Zone": "S1" if face != "s+" else "S2",
        "Section ID": "CB-S01",
        "Section role": "Solid",
        "Area mm2": 1_000_000.0,
        "Z top mm3": 100_000_000.0,
        "Z bottom mm3": 100_000_000.0,
        "P (kN; compression +)": p_kn,
        "M3 (kN-m; sagging +)": m_knm,
        "Context status": "READY",
        "Context ID": context_id,
    }


def _foundation(rows: list[dict[str, object]], *, physical_boundary: bool = False) -> dict[str, object]:
    boundaries = []
    if physical_boundary:
        boundaries = [
            {
                "Boundary ID": "S1 / S2",
                "Station s (m)": 5.0,
                "Boundary type": "Physical segment joint",
            }
        ]
    return {
        "fingerprint": "service-foundation-001",
        "member_length_m": 10.0,
        "mapped_rows": rows,
        "internal_boundaries": boundaries,
        "columns": [
            {"Column ID": "C1", "Station s (m)": 2.0},
            {"Column ID": "C2", "Station s (m)": 8.0},
        ],
        "column_footprints": [
            {"Column": "C1", "s_left (m)": 1.5, "s_right (m)": 2.5},
            {"Column": "C2", "s_left (m)": 7.5, "s_right (m)": 8.5},
        ],
    }


def _calculate(
    foundation: dict[str, object],
    *,
    sustained: list[str] | None = None,
):
    return calculate_crossbeam_service_stress(
        foundation=foundation,
        section_definitions=default_section_definitions(),
        concrete_materials=[c45_precast_material()],
        sustained_case_names=sustained or [],
    )


def test_service_stress_uses_row_coupled_p_and_m3_and_class_u_tension_limit() -> None:
    rows = [
        _context(context_id="total", station=4.0, case="SERV-TOTAL"),
        _context(context_id="sust", station=4.0, case="SERV-SUST"),
    ]
    result = _calculate(_foundation(rows), sustained=["SERV-SUST"])
    assert result["status"] == "PASS"
    total = next(row for row in result["rows"] if row["Case / Combination"] == "SERV-TOTAL")
    sustained = next(row for row in result["rows"] if row["Case / Combination"] == "SERV-SUST")
    assert math.isclose(total["Axial stress (MPa)"], -1.0)
    assert math.isclose(total["Top stress (MPa)"], -2.0)
    assert math.isclose(total["Bottom stress (MPa)"], 0.0)
    assert math.isclose(total["Compression limit magnitude (MPa)"], 27.0)
    assert math.isclose(sustained["Compression limit magnitude (MPa)"], 20.25)
    assert math.isclose(total["Tension limit (MPa)"], 0.62 * math.sqrt(45.0))
    assert total["Service tensile class"] == "Class U"


def test_service_class_u_tension_exceedance_is_fail() -> None:
    rows = [
        _context(
            context_id="total",
            station=4.0,
            case="SERV-TOTAL",
            p_kn=0.0,
            m_knm=500.0,
        ),
        _context(
            context_id="sust",
            station=4.0,
            case="SERV-SUST",
            p_kn=0.0,
            m_knm=500.0,
        ),
    ]
    result = _calculate(_foundation(rows), sustained=["SERV-SUST"])
    assert result["status"] == "FAIL"
    assert result["stress_status"] == "FAIL"
    assert result["governing_tension"]["Stress (MPa)"] > result["governing_tension"]["Limit (MPa)"]


def test_service_without_sustained_case_is_review_not_false_pass() -> None:
    result = _calculate(_foundation([_context(context_id="1", station=4.0)]))
    assert result["status"] == "REVIEW"
    assert result["stress_status"] == "REVIEW"
    assert result["service_basis_status"] == "REVIEW"
    assert any("0.45f'c" in issue for issue in result["basis_coverage_issues"])


def test_service_joint_gate_fails_below_project_minimum() -> None:
    rows = [
        _context(
            context_id="left-total",
            station=5.0,
            face="s-",
            case="SERV-TOTAL",
            p_kn=500.0,
            m_knm=0.0,
            physical_joint=True,
        ),
        _context(
            context_id="right-total",
            station=5.0,
            face="s+",
            case="SERV-TOTAL",
            p_kn=500.0,
            m_knm=0.0,
            physical_joint=True,
        ),
        _context(
            context_id="left-sust",
            station=5.0,
            face="s-",
            case="SERV-SUST",
            p_kn=1000.0,
            m_knm=0.0,
            physical_joint=True,
        ),
        _context(
            context_id="right-sust",
            station=5.0,
            face="s+",
            case="SERV-SUST",
            p_kn=1000.0,
            m_knm=0.0,
            physical_joint=True,
        ),
    ]
    result = _calculate(_foundation(rows, physical_boundary=True), sustained=["SERV-SUST"])
    assert result["stress_status"] == "PASS"
    assert result["joint_status"] == "FAIL"
    assert result["status"] == "FAIL"
    assert math.isclose(result["governing_joint"]["Compression (MPa)"], 0.5)


def test_service_fingerprint_changes_with_sustained_case_assignment() -> None:
    foundation = _foundation(
        [
            _context(context_id="total", station=4.0, case="SERV-TOTAL"),
            _context(context_id="sust", station=4.0, case="SERV-SUST"),
        ]
    )
    kwargs = {
        "foundation": foundation,
        "section_definitions": default_section_definitions(),
        "concrete_materials": [c45_precast_material()],
    }
    fp_total_only = service_stress_input_fingerprint(**kwargs, sustained_case_names=[])
    fp_with_sustained = service_stress_input_fingerprint(
        **kwargs, sustained_case_names=["SERV-SUST"]
    )
    assert fp_total_only != fp_with_sustained


def test_service_chart_labels_aci_equations_and_column_joint_landmarks() -> None:
    rows = [
        _context(context_id="1", station=0.0, case="SERV-TOTAL", p_kn=1000.0, m_knm=0.0),
        _context(context_id="2", station=5.0, case="SERV-TOTAL", p_kn=1000.0, m_knm=100.0),
        _context(context_id="3", station=10.0, case="SERV-TOTAL", p_kn=1000.0, m_knm=0.0),
        _context(context_id="4", station=0.0, case="SERV-SUST", p_kn=1000.0, m_knm=0.0),
        _context(context_id="5", station=5.0, case="SERV-SUST", p_kn=1000.0, m_knm=100.0),
        _context(context_id="6", station=10.0, case="SERV-SUST", p_kn=1000.0, m_knm=0.0),
    ]
    foundation = _foundation(rows)
    result = _calculate(foundation, sustained=["SERV-SUST"])
    fig = make_crossbeam_service_stress_figure(
        foundation, result, case_name="SERV-TOTAL"
    )
    names = [trace.name for trace in fig.data]
    assert "Top total stress" in names
    assert "Bottom total stress" in names
    assert "Compression limit" in names
    assert "Class U tension limit" in names
    annotation_text = [str(item.text) for item in fig.layout.annotations]
    assert any("−0.60f′c = −0.60(45.00) = −27.00 MPa" in item for item in annotation_text)
    assert any("+0.62√f′c = +0.62√(45.00)" in item for item in annotation_text)
    assert "Class U" in fig.layout.title.text
    assert len(fig.layout.shapes) >= 5


def test_sustained_case_selection_round_trips_in_project_json_but_results_do_not() -> None:
    source: dict[str, object] = {
        "project_name": "Crossbeam SLS1B persistence",
        "analysis_mode_settings": AnalysisModeSettings(member_type="portal_frame_crossbeam"),
        "crossbeam_ui1_length_m": 20.0,
        "crossbeam_ui1_segment_layout_rows": default_crossbeam_segment_rows(20.0),
        CB_SECLIB_DEFINITIONS_KEY: default_section_definitions(),
        CB_ANALYSIS_SLS_SERVICE_SUSTAINED_CASES_KEY: ["SERV-SUST-02", "SERV-SUST-01"],
        CB_ANALYSIS_SLS_SERVICE_RESULT_KEY: {"status": "PASS", "solver_run": True},
    }
    restored: dict[str, object] = {}
    project = project_from_session_state(source)
    apply_project_to_session_state(project_from_json(project_to_json(project)), restored)
    assert restored[CB_ANALYSIS_SLS_SERVICE_SUSTAINED_CASES_KEY] == [
        "SERV-SUST-01",
        "SERV-SUST-02",
    ]
    assert CB_ANALYSIS_SLS_SERVICE_RESULT_KEY not in restored


def test_ui_exposes_service_solver_without_reusing_generic_solver() -> None:
    assert "calculate_crossbeam_service_stress" in PAGE_SOURCE
    assert "Prestress + sustained load cases" in PAGE_SOURCE
    assert "Class U" in PAGE_SOURCE
    assert "disabled=not source_ready" in PAGE_SOURCE
    assert "SLS CHECKS ACTIVE" in ANALYSIS_SOURCE
    assert CB_ANALYSIS_SLS_SERVICE_RESULT_KEY not in PROJECT_IO_SOURCE
