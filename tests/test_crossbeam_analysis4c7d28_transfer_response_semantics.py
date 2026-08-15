from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_transfer_response_extrema,
    _make_crossbeam_sls_deflection_figure,
)


def _result() -> dict[str, object]:
    return {
        "response_rows": [
            {
                "Stage": "Transfer stage",
                "Case": "TR",
                "Region": "C1–C2",
                "Station s (m)": 2.0,
                "Relative displacement mm": 0.0,
                "Absolute displacement mm": -1.0,
                "Source": "RELATIVE",
            },
            {
                "Stage": "Transfer stage",
                "Case": "TR",
                "Region": "C1–C2",
                "Station s (m)": 6.0,
                "Relative displacement mm": -7.5,
                "Absolute displacement mm": -8.5,
                "Source": "RELATIVE",
            },
            {
                "Stage": "Transfer stage",
                "Case": "TR",
                "Region": "Left overhang",
                "Station s (m)": 0.0,
                "Relative displacement mm": 0.8,
                "Absolute displacement mm": -0.2,
                "Source": "RELATIVE",
            },
            {
                "Stage": "Transfer stage",
                "Case": "TR",
                "Station s (m)": 0.0,
                "Vertical displacement mm": -0.2,
                "Source": "IMPORTED",
            },
            {
                "Stage": "Transfer stage",
                "Case": "TR",
                "Station s (m)": 6.0,
                "Vertical displacement mm": -8.5,
                "Source": "IMPORTED",
            },
        ],
        "span_rows": [
            {
                "Stage": "Transfer stage",
                "Case": "TR",
                "Region": "C1–C2",
                "Region type": "SUPPORT SPAN",
                "Span": "C1–C2",
                "Max upward camber mm": 0.0,
                "x up m": 2.0,
                "Max downward deflection mm": 7.5,
                "x down m": 6.0,
            }
        ],
        "overhang_rows": [
            {
                "Stage": "Transfer stage",
                "Case": "TR",
                "Region": "Left overhang",
                "Region type": "OVERHANG",
                "Span": "Left overhang",
                "Max upward camber mm": 0.8,
                "x up m": 0.0,
                "Max downward deflection mm": 0.0,
                "x down m": 2.0,
            }
        ],
    }


def test_d28_transfer_extrema_keep_upward_and_downward_response_separate() -> None:
    max_up, max_down = _crossbeam_transfer_response_extrema(_result())
    assert max_up is not None and max_down is not None
    assert max_up["Region"] == "Left overhang"
    assert max_up["Max upward camber mm"] == 0.8
    assert max_down["Region"] == "C1–C2"
    assert max_down["Max downward deflection mm"] == 7.5


def test_d28_transfer_chart_uses_response_language_and_two_extrema_markers() -> None:
    fig = _make_crossbeam_sls_deflection_figure(
        _result(),
        stage="Transfer stage",
        case_name="TR",
        member_length_m=10.0,
        column_rows=[
            {"Column ID": "C1", "Station s (m)": 2.0, "Blong (mm)": 1000.0},
            {"Column ID": "C2", "Station s (m)": 8.0, "Blong (mm)": 1000.0},
        ],
    )
    names = [str(trace.name) for trace in fig.data]
    assert "Relative member response" in names
    assert "Max camber" in names
    assert "Max deflection" in names
    assert "Gov. camber" not in names


def test_d28_transfer_workspace_removes_acceptance_columns_and_duplicate_camber_status() -> None:
    source = (Path(__file__).resolve().parents[1] / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
    workspace = source[source.index("def _render_crossbeam_sls_deflection_workspace"):source.index("def render_analysis_sls_deflection_camber")]
    assert '"title": "Max upward camber"' in workspace
    assert '"title": "Max downward deflection"' in workspace
    assert '"title": "Transfer response"' in workspace
    assert '"title": "Governing camber"' not in workspace
    assert '"title": "Transfer camber status"' not in workspace
    assert 'transfer_span_columns = [' in workspace
    assert 'transfer_overhang_columns = [' in workspace
    transfer_column_block = workspace[workspace.index("transfer_span_columns = ["):workspace.index("span_title =")]
    assert '"Limit basis"' not in transfer_column_block
    assert '"Limit mm"' not in transfer_column_block
    assert '"Utilization"' not in transfer_column_block
