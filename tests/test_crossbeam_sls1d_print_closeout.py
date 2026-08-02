from pathlib import Path

import pandas as pd

from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_print_safe_table_html,
    _make_crossbeam_transfer_stress_figure,
)


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
ANALYSIS = (ROOT / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")


def test_crossbeam_analysis_card_uses_design_code_edition_label() -> None:
    block = ANALYSIS.split("def _commercial_analysis_dashboard_cards", 1)[1].split(
        "def _analysis_subtabs_for_workflow", 1
    )[0]
    assert "workflow_project_code_label_from_session(st.session_state)" in block


def test_sls_required_actions_and_transfer_audit_use_wrapping_print_tables() -> None:
    assert 'label="Transfer required actions"' in ANALYSIS
    assert 'label="Final Service required actions"' in ANALYSIS
    assert "Transfer calculation audit - source identity" in ANALYSIS
    assert "Transfer calculation audit - forces and gross properties" in ANALYSIS
    assert "Transfer calculation audit - stress and criteria" in ANALYSIS
    assert "cpmm-sls-print-table" in ANALYSIS
    assert "overflow-wrap: anywhere" in ANALYSIS
    assert "table-layout: fixed" in ANALYSIS

    html = _crossbeam_print_safe_table_html(
        pd.DataFrame(
            [{"Priority": 1, "Required Action": "Review the complete right-side action without clipping."}]
        ),
        label="Required actions",
    )
    assert "Required Action" in html
    assert "without clipping" in html
    assert 'aria-label="Required actions"' in html


def test_coincident_governing_tension_and_joint_labels_are_separated() -> None:
    result_rows = pd.DataFrame(
        [
            {
                "Status": "FAIL",
                "Station s (m)": 15.0,
                "Case": "SLS-01",
                "Section face": "LEFT LIMIT (s-)",
                "Location type": "PHYSICAL SEGMENT JOINT",
                "Section ID": "S1",
                "Top stress MPa": -2.0,
                "Bottom stress MPa": 8.958,
                "Compression limit MPa": -27.0,
                "Tension limit MPa": 4.16,
            }
        ]
    )
    fiber_rows = pd.DataFrame(
        [
            {
                "Case": "SLS-01",
                "Station s (m)": 15.0,
                "Fiber": "Bottom",
                "Stress MPa": 8.958,
                "Compression utilization": 0.0,
                "Tension utilization": 2.15,
                "Joint utilization": 9.658,
            }
        ]
    )
    figure = _make_crossbeam_transfer_stress_figure(
        result_rows,
        fiber_rows,
        case_name="SLS-01",
        member_length_m=20.0,
        column_rows=[],
    )
    markers = {trace.name: trace for trace in figure.data if trace.name in {"Gov. tension", "Gov. joint"}}
    assert set(markers) == {"Gov. tension", "Gov. joint"}
    assert markers["Gov. tension"].textposition != markers["Gov. joint"].textposition


def test_developer_diagnostics_is_always_excluded_from_print() -> None:
    assert "cpmm-developer-diagnostics-print-guard" in ANALYSIS
    assert 'details:has(.cpmm-developer-diagnostics-print-guard)' in APP
