from __future__ import annotations

from pathlib import Path

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_sls_deflection import (
    CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY,
    DEFAULT_LIMIT_BASIS,
    DEFAULT_OVERHANG_LIMIT_BASIS,
    build_crossbeam_deflection_preparation,
    run_crossbeam_deflection_camber,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.project_geometry import CROSSBEAM_COLUMN_ROWS_KEY
from concrete_pmm_pro.io.project_io import (
    ANALYSIS_SOURCES_METADATA_KEY,
    apply_project_to_session_state,
    project_from_session_state,
)
from concrete_pmm_pro.analysis.crossbeam_sls_deflection import CROSSBEAM_SLS_DISPLACEMENT_SOURCE_METADATA_KEY


def _columns_with_overhangs() -> list[dict[str, object]]:
    return [
        {"Column ID": "C1", "Station s (m)": 2.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C2", "Station s (m)": 10.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C3", "Station s (m)": 18.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
    ]


def _row(x: float, d: float, *, stage: str = "Final service stage") -> dict[str, object]:
    return {
        "Active": True,
        "Station s (m)": x,
        "Case Name": "SERV",
        "Stage": stage,
        "Vertical displacement (mm)": d,
        "Source point": f"N{x:g}",
        "Note": "verified",
    }


def _state_with_overhangs() -> dict[str, object]:
    # Span curvature plus downward free-end movement relative to each adjacent
    # column centre.  Member length 20 m -> 2 m overhang each side.
    rows = [
        _row(0.0, -4.0),
        _row(2.0, 0.0),
        _row(6.0, -8.0),
        _row(10.0, 0.0),
        _row(14.0, -6.0),
        _row(18.0, 0.0),
        _row(20.0, -3.0),
    ]
    return {
        "crossbeam_ui1_length_m": 20.0,
        CROSSBEAM_COLUMN_ROWS_KEY: _columns_with_overhangs(),
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY: pd.DataFrame(rows),
    }


def test_d26_general_practice_defaults_and_overhang_checks_are_active() -> None:
    prep = build_crossbeam_deflection_preparation(_state_with_overhangs())
    assert prep.ready
    assert DEFAULT_LIMIT_BASIS == "L/360"
    assert DEFAULT_OVERHANG_LIMIT_BASIS == "Lo/180"
    assert prep.limit_basis == "L/360"
    assert prep.overhang_limit_basis == "Lo/180"
    assert prep.left_overhang_m == 2.0
    assert prep.right_overhang_m == 2.0

    result = run_crossbeam_deflection_camber(prep)
    assert result["schema"] == "crossbeam-sls2-deflection-result-v3"
    assert len(result["overhang_rows"]) == 2
    left, right = result["overhang_rows"]
    assert left["Region"] == "Left overhang"
    assert right["Region"] == "Right overhang"
    assert round(float(left["Limit mm"]), 6) == round(2000.0 / 180.0, 6)
    assert round(float(right["Limit mm"]), 6) == round(2000.0 / 180.0, 6)
    assert round(float(left["Max downward deflection mm"]), 6) == 4.0
    assert round(float(right["Max downward deflection mm"]), 6) == 3.0
    assert all(row["Status"] == "PASS" for row in result["overhang_rows"])


def test_d26_relative_member_trace_covers_both_overhangs_and_support_spans() -> None:
    result = run_crossbeam_deflection_camber(build_crossbeam_deflection_preparation(_state_with_overhangs()))
    relative = [
        row for row in result["response_rows"]
        if row.get("Stage") == "Final service stage" and "Relative displacement mm" in row
    ]
    stations = [float(row["Station s (m)"]) for row in relative]
    regions = {str(row.get("Region")) for row in relative}
    assert min(stations) == 0.0
    assert max(stations) == 20.0
    assert {"Left overhang", "C1–C2", "C2–C3", "Right overhang"}.issubset(regions)
    # Relative response is zero at every column centre by construction.
    for x in (2.0, 10.0, 18.0):
        values = [float(row["Relative displacement mm"]) for row in relative if abs(float(row["Station s (m)"]) - x) < 1e-9]
        assert values and all(abs(value) < 1e-9 for value in values)


def test_d26_no_overhang_geometry_omits_overhang_checks() -> None:
    columns = [
        {"Column ID": "C1", "Station s (m)": 0.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C2", "Station s (m)": 10.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
        {"Column ID": "C3", "Station s (m)": 20.0, "Height (m)": 8.0, "Blong (mm)": 1500.0, "Btrans (mm)": 1500.0},
    ]
    state = {
        "crossbeam_ui1_length_m": 20.0,
        CROSSBEAM_COLUMN_ROWS_KEY: columns,
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        CROSSBEAM_SLS_DISPLACEMENT_TABLE_KEY: pd.DataFrame([
            _row(0.0, 0.0), _row(5.0, -4.0), _row(10.0, 0.0), _row(15.0, -3.0), _row(20.0, 0.0)
        ]),
    }
    prep = build_crossbeam_deflection_preparation(state)
    assert prep.ready
    assert prep.left_overhang_m == 0.0
    assert prep.right_overhang_m == 0.0
    result = run_crossbeam_deflection_camber(prep)
    assert result["overhang_rows"] == []


def test_d26_ui_is_geometry_aware_and_plots_overhang_limits_in_same_graph() -> None:
    source = (Path(__file__).resolve().parents[1] / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
    assert 'st.markdown("**Support-to-support spans**")' in source
    assert 'st.markdown("**Overhangs**")' in source
    assert '"Final-service overhang deflection criterion"' in source
    assert "No end overhang is present in the active Crossbeam geometry" in source
    assert 'name="Relative member deflection"' in source
    assert 'row.get("Overhang start m")' in source
    assert 'row.get("Overhang end m")' in source
    assert "General-practice default: L/360" in source
    assert "General-practice default: Lo/180" in source


def test_d26_project_json_persists_span_and_overhang_criteria() -> None:
    state = _state_with_overhangs()
    state["crossbeam_sls_deflection_limit_basis"] = "L/480"
    state["crossbeam_sls_deflection_overhang_limit_basis"] = "Lo/240"
    project = project_from_session_state(state)
    source = project.metadata[ANALYSIS_SOURCES_METADATA_KEY][CROSSBEAM_SLS_DISPLACEMENT_SOURCE_METADATA_KEY]
    assert source["settings"]["span_limit_basis"] == "L/480"
    assert source["settings"]["overhang_limit_basis"] == "Lo/240"

    restored: dict[str, object] = {}
    apply_project_to_session_state(project, restored)
    assert restored["crossbeam_sls_deflection_limit_basis"] == "L/480"
    assert restored["crossbeam_sls_deflection_overhang_limit_basis"] == "Lo/240"
