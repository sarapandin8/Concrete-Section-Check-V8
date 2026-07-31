from __future__ import annotations

import math
from pathlib import Path

from concrete_pmm_pro.core.concrete_materials import c45_precast_material
from concrete_pmm_pro.crossbeam.analysis_charts import make_crossbeam_transfer_stress_figure
from concrete_pmm_pro.crossbeam.sls_transfer import (
    CB_ANALYSIS_SLS_TRANSFER_RESULT_KEY,
    calculate_crossbeam_transfer_stress,
    transfer_stress_input_fingerprint,
)
from concrete_pmm_pro.crossbeam.section_library import default_section_definitions


PAGE_SOURCE = Path("concrete_pmm_pro/ui/crossbeam_analysis_page.py").read_text(encoding="utf-8")
PROJECT_IO_SOURCE = Path("concrete_pmm_pro/io/project_io.py").read_text(encoding="utf-8")


def _context(
    *,
    context_id: str,
    station: float,
    face: str = "INTERIOR",
    case: str = "TR-01",
    p_kn: float = 1000.0,
    m_knm: float = 100.0,
    physical_joint: bool = False,
) -> dict[str, object]:
    return {
        "Dataset": "SLS At Transfer",
        "Stage": "Transfer stage",
        "Source row": f"SLS At Transfer:{context_id}",
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
        "fingerprint": "foundation-001",
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


def _calculate(foundation: dict[str, object], *, ratio: float = 0.8):
    return calculate_crossbeam_transfer_stress(
        foundation=foundation,
        section_definitions=default_section_definitions(),
        concrete_materials=[c45_precast_material()],
        stressing_strength_ratio=ratio,
    )


def test_transfer_stress_uses_row_coupled_p_and_m3_with_accepted_sign_convention() -> None:
    result = _calculate(_foundation([_context(context_id="1", station=4.0)]))
    assert result["status"] == "PASS"
    row = result["rows"][0]
    assert math.isclose(row["Axial stress (MPa)"], -1.0)
    assert math.isclose(row["Top bending stress (MPa)"], -1.0)
    assert math.isclose(row["Bottom bending stress (MPa)"], 1.0)
    assert math.isclose(row["Top stress (MPa)"], -2.0)
    assert math.isclose(row["Bottom stress (MPa)"], 0.0)


def test_transfer_limits_use_aci_all_other_locations_for_portal_frame() -> None:
    result = _calculate(_foundation([_context(context_id="1", station=0.0)]))
    row = result["rows"][0]
    assert math.isclose(row["f'ci (MPa)"], 36.0)
    assert math.isclose(row["Compression limit magnitude (MPa)"], 21.6)
    assert math.isclose(row["Tension limit (MPa)"], 1.5)
    assert "not a simply supported member" in result["limit_basis"]["compression"]
    assert "additional bonded reinforcement" in result["limit_basis"]["tension"]


def test_precast_joint_gate_fails_below_0_70_mpa_even_when_aci_stress_passes() -> None:
    rows = [
        _context(context_id="left", station=5.0, face="s-", p_kn=500.0, m_knm=0.0, physical_joint=True),
        _context(context_id="right", station=5.0, face="s+", p_kn=500.0, m_knm=0.0, physical_joint=True),
    ]
    result = _calculate(_foundation(rows, physical_boundary=True))
    assert result["stress_status"] == "PASS"
    assert result["joint_status"] == "FAIL"
    assert result["status"] == "FAIL"
    assert math.isclose(result["governing_joint"]["Compression (MPa)"], 0.5)


def test_every_transfer_case_requires_both_one_sided_joint_faces() -> None:
    rows = [
        _context(context_id="left", station=5.0, face="s-", p_kn=1000.0, m_knm=0.0, physical_joint=True),
    ]
    result = _calculate(_foundation(rows, physical_boundary=True))
    assert result["status"] == "INCOMPLETE"
    assert result["solver_run"] is True
    assert any("requires both s- and s+ checks" in issue for issue in result["joint_coverage_issues"])


def test_transfer_input_fingerprint_changes_with_stressing_strength_ratio() -> None:
    foundation = _foundation([_context(context_id="1", station=4.0)])
    kwargs = {
        "foundation": foundation,
        "section_definitions": default_section_definitions(),
        "concrete_materials": [c45_precast_material()],
    }
    fp_08 = transfer_stress_input_fingerprint(**kwargs, stressing_strength_ratio=0.8)
    fp_09 = transfer_stress_input_fingerprint(**kwargs, stressing_strength_ratio=0.9)
    assert fp_08 != fp_09


def test_active_internal_tendon_keeps_gross_section_nonfailure_at_review() -> None:
    result = calculate_crossbeam_transfer_stress(
        foundation=_foundation([_context(context_id="1", station=4.0)]),
        section_definitions=default_section_definitions(),
        concrete_materials=[c45_precast_material()],
        tendon_system_rows=[
            {
                "Tendon ID": "T1",
                "Active": True,
                "Type": "Internal",
            }
        ],
        stressing_strength_ratio=0.8,
    )
    assert result["status"] == "REVIEW"
    assert result["stress_status"] == "REVIEW"
    assert result["section_basis_status"] == "REVIEW"
    assert result["active_internal_tendon_ids"] == ["T1"]
    assert any("duct-void geometry" in warning for warning in result["warnings"])


def test_transfer_chart_uses_beam_girder_stress_language_and_crossbeam_landmarks() -> None:
    foundation = _foundation(
        [
            _context(context_id="1", station=0.0, p_kn=1000.0, m_knm=0.0),
            _context(context_id="2", station=5.0, p_kn=1000.0, m_knm=100.0),
            _context(context_id="3", station=10.0, p_kn=1000.0, m_knm=0.0),
        ]
    )
    result = _calculate(foundation)
    fig = make_crossbeam_transfer_stress_figure(foundation, result, case_name="TR-01")
    names = [trace.name for trace in fig.data]
    assert "Top total stress" in names
    assert "Bottom total stress" in names
    assert "Compression limit" in names
    assert "Tension limit" in names
    assert fig.layout.height == 560
    assert "compression negative / tension positive" in fig.layout.yaxis.title.text
    annotation_text = [str(item.text) for item in fig.layout.annotations]
    assert any("−0.60f′ci = −0.60(36.00) = −21.60 MPa" in item for item in annotation_text)
    assert any("+0.25√f′ci = +0.25√(36.00) = +1.50 MPa" in item for item in annotation_text)
    compression_trace = next(trace for trace in fig.data if trace.name == "Compression limit")
    tension_trace = next(trace for trace in fig.data if trace.name == "Tension limit")
    assert "f′ci=%{customdata[0]:.3f} MPa" in compression_trace.hovertemplate
    assert "f′ci=%{customdata[0]:.3f} MPa" in tension_trace.hovertemplate
    assert len(fig.layout.shapes) >= 5  # 2 footprints, 2 centerlines, zero line/member ends


def test_sls1a_enables_only_transfer_calculation_and_keeps_result_session_only() -> None:
    assert "calculate_crossbeam_transfer_stress" in PAGE_SOURCE
    assert "disabled=(not source_ready) or stage != SLS_STAGE_TRANSFER" in PAGE_SOURCE
    assert "At Service is implemented in the next SLS milestone." in PAGE_SOURCE
    assert CB_ANALYSIS_SLS_TRANSFER_RESULT_KEY not in PROJECT_IO_SOURCE
