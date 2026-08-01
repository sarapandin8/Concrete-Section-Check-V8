from __future__ import annotations

import math
from pathlib import Path

from concrete_pmm_pro.core.concrete_materials import c45_precast_material
from concrete_pmm_pro.crossbeam.analysis_charts import make_crossbeam_flexure_pm3_figure
from concrete_pmm_pro.crossbeam.rebar import default_crossbeam_rebar_templates
from concrete_pmm_pro.crossbeam.section_library import default_section_definitions
from concrete_pmm_pro.crossbeam.uls_flexure import (
    CB_ANALYSIS_ULS_FLEXURE_RESULT_KEY,
    calculate_crossbeam_uls_flexure,
    flexure_input_fingerprint,
)


PAGE_SOURCE = Path("concrete_pmm_pro/ui/crossbeam_analysis_page.py").read_text(encoding="utf-8")
PROJECT_IO_SOURCE = Path("concrete_pmm_pro/io/project_io.py").read_text(encoding="utf-8")


def _row(*, station: float = 5.0, p_kn: float = 1000.0, m3_knm: float = 500.0, case: str = "ULS-01") -> dict[str, object]:
    return {
        "Dataset": "ULS Final Stage",
        "Context status": "READY",
        "Context ID": f"{case}:{station:g}",
        "Source row": f"ULS Final Stage:{station:g}",
        "Case / Combination": case,
        "Station s (m)": station,
        "Check Point": "Midspan",
        "Station face": "INTERIOR",
        "Boundary type": "Interior",
        "Segment / Zone": "S1",
        "Section ID": "CB-S01",
        "Longitudinal template": "RB-SOLID-COLUMN",
        "P (kN; compression +)": p_kn,
        "M3 (kN-m; sagging +)": m3_knm,
    }


def _foundation(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "fingerprint": "uls-foundation-001",
        "member_length_m": 10.0,
        "construction_method": "Precast Segmental",
        "mapped_rows": rows,
        "columns": [{"Column ID": "C1", "Station s (m)": 2.0}],
        "column_footprints": [{"Column": "C1", "s_left (m)": 1.5, "s_right (m)": 2.5}],
        "internal_boundaries": [
            {"Boundary ID": "S1 / S2", "Station s (m)": 5.0, "Boundary type": "Physical segment joint"}
        ],
    }


def _calculate(rows: list[dict[str, object]]):
    return calculate_crossbeam_uls_flexure(
        foundation=_foundation(rows),
        section_definitions=default_section_definitions(),
        rebar_template_rows=default_crossbeam_rebar_templates(),
        concrete_materials=[c45_precast_material()],
    )


def test_uls_flexure_keeps_row_coupled_p_and_m3_and_returns_interaction_dcr() -> None:
    result = _calculate([_row(p_kn=1200.0, m3_knm=700.0)])
    assert result["solver_run"] is True
    assert result["status"] == "REVIEW"  # no adopted PT source in this fixture
    row = result["rows"][0]
    assert math.isclose(row["P (kN; compression +)"], 1200.0)
    assert math.isclose(row["M3 (kN-m; sagging +)"], 700.0)
    assert row["phiMn at Pu (kN-m)"] > 0.0
    assert math.isclose(row["P-M3 D/C"], 700.0 / row["phiMn at Pu (kN-m)"], rel_tol=1.0e-9)


def test_uls_flexure_large_moment_fails_without_being_downgraded_to_review() -> None:
    result = _calculate([_row(m3_knm=100_000.0)])
    assert result["status"] == "FAIL"
    assert result["rows"][0]["Status"] == "FAIL"
    assert result["rows"][0]["P-M3 D/C"] > 1.0


def test_uls_flexure_source_blocks_missing_longitudinal_template() -> None:
    row = _row()
    row["Longitudinal template"] = "MISSING"
    result = _calculate([row])
    assert result["status"] == "SOURCE BLOCKED"
    assert result["rows"] == []
    assert any("MISSING" in item for item in result["errors"])


def test_uls_flexure_fingerprint_changes_with_row_coupled_demand() -> None:
    kwargs = {
        "section_definitions": default_section_definitions(),
        "rebar_template_rows": default_crossbeam_rebar_templates(),
        "concrete_materials": [c45_precast_material()],
    }
    fp1 = flexure_input_fingerprint(foundation=_foundation([_row(m3_knm=500.0)]), **kwargs)
    changed = _foundation([_row(m3_knm=600.0)])
    changed["fingerprint"] = "uls-foundation-002"
    fp2 = flexure_input_fingerprint(foundation=changed, **kwargs)
    assert fp1 != fp2


def test_uls_flexure_chart_compares_mu_with_phi_mn_and_keeps_crossbeam_landmarks() -> None:
    foundation = _foundation([_row(station=0.0, m3_knm=0.0), _row(station=5.0), _row(station=10.0)])
    result = calculate_crossbeam_uls_flexure(
        foundation=foundation,
        section_definitions=default_section_definitions(),
        rebar_template_rows=default_crossbeam_rebar_templates(),
        concrete_materials=[c45_precast_material()],
    )
    fig = make_crossbeam_flexure_pm3_figure(foundation, result, case_name="ULS-01")
    trace_names = [trace.name for trace in fig.data]
    assert "Mu" in trace_names
    assert "φMn" in trace_names
    assert "Gov. flexure" in trace_names
    assert fig.layout.yaxis.title.text == "Moment, Mu / φMn (kN-m)"
    assert "Mu versus φMn at concurrent Pu" in fig.layout.title.text
    assert len(fig.layout.shapes) >= 3

    mu_trace = next(trace for trace in fig.data if trace.name == "Mu")
    phi_trace = next(trace for trace in fig.data if trace.name == "φMn")
    assert list(mu_trace.y)[0] == 0.0
    assert list(phi_trace.y)[0] == 0.0
    assert list(phi_trace.y)[1] > 0.0


def test_uls_flexure_chart_plots_capacity_in_negative_mu_direction() -> None:
    foundation = _foundation([_row(station=5.0, m3_knm=-700.0)])
    result = calculate_crossbeam_uls_flexure(
        foundation=foundation,
        section_definitions=default_section_definitions(),
        rebar_template_rows=default_crossbeam_rebar_templates(),
        concrete_materials=[c45_precast_material()],
    )
    fig = make_crossbeam_flexure_pm3_figure(foundation, result, case_name="ULS-01")
    mu_trace = next(trace for trace in fig.data if trace.name == "Mu")
    phi_trace = next(trace for trace in fig.data if trace.name == "φMn")
    assert list(mu_trace.y) == [-700.0]
    assert list(phi_trace.y)[0] < 0.0
    assert abs(list(phi_trace.y)[0]) == result["rows"][0]["phiMn at Pu (kN-m)"]


def test_uls1a_ui_connects_only_flexure_and_keeps_result_session_only() -> None:
    assert "calculate_crossbeam_uls_flexure" in PAGE_SOURCE
    assert 'selected_check != "Flexure"' in PAGE_SOURCE
    assert "Shear and torsion remain isolated future milestones." in PAGE_SOURCE
    assert CB_ANALYSIS_ULS_FLEXURE_RESULT_KEY not in PROJECT_IO_SOURCE


def test_precast_physical_joint_reports_one_governing_result_and_no_ordinary_rebar_credit() -> None:
    left = _row(station=5.0)
    left.update({"Context ID": "left", "Station face": "s-", "Boundary type": "Physical segment joint", "Segment / Zone": "S1"})
    right = _row(station=5.0)
    right.update({"Context ID": "right", "Station face": "s+", "Boundary type": "Physical segment joint", "Segment / Zone": "S2"})
    result = _calculate([left, right])
    assert len(result["rows"]) == 1
    joint = result["rows"][0]
    assert joint["Station face"] == ""
    assert joint["Internal section contexts"] == 2
    assert joint["Ordinary rebar credited"] is False
    assert joint["Rebar count"] == 0
    assert "S1 / S2" in joint["Segment / Zone"]


def test_uls_flexure_supports_negative_m3_direction_without_using_absolute_capacity_symmetry() -> None:
    positive = _calculate([_row(m3_knm=700.0)])["rows"][0]
    negative = _calculate([_row(m3_knm=-700.0)])["rows"][0]
    assert negative["M3 (kN-m; sagging +)"] == -700.0
    assert negative["phiMn at Pu (kN-m)"] > 0.0
    assert negative["P-M3 D/C"] > 0.0
    # The bottom-filleted section and reinforcement layout need not be vertically symmetric.
    assert not math.isclose(
        positive["phiMn at Pu (kN-m)"],
        negative["phiMn at Pu (kN-m)"],
        rel_tol=1.0e-6,
    )
