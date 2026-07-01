from __future__ import annotations

import pandas as pd

import app
from concrete_pmm_pro.reporting.readiness import check_report_readiness, report_readiness_to_dataframe
from concrete_pmm_pro.reporting.traceability import build_result_traceability_snapshot


def test_preview_pass_is_ready_not_required_action() -> None:
    assert app._results_style_for_status("Preview PASS") == "ready"
    assert app._results_style_for_status("Preview FAIL") == "danger"
    assert app._results_style_for_status("NOT_READY") == "warning"

    rows = [
        {
            "Module": "SLS Railway U-Girder",
            "Check": "Final service",
            "Status": "Preview PASS",
            "Governing Case": "SLS-SERV",
            "Station / Point": "2.0",
            "Demand": "Compression -8.367 MPa; tension 2.014 MPa",
            "Capacity / Limit": "Locked web fibers + full Railway U-Girder incremental service",
            "D/C / Util.": "0.681",
            "Required Action": "This should not become a required action.",
            "Source": "Analysis → Railway U-Girder staged SLS stress preview",
            "Code Basis": "AASHTO LRFD 9th Edition",
        }
    ]
    actions = app._results_required_action_rows(
        {
            "_beam_girder_uls_manual_calculation_cache": {"Flexure": {"summary_df": pd.DataFrame([{"Status": "PASS"}])}},
            "railway_u_girder_sls_decision_summary_df": pd.DataFrame([{"Decision": "Preview PASS", "Max utilization": 0.681}]),
        },
        rows,
    )

    assert not any("Preview PASS" in str(action.get("Issue")) for action in actions)


def test_traceability_snapshot_detects_beam_uls_and_railway_sls() -> None:
    decision = pd.DataFrame(
        [
            {"Check stage": "Lifting", "Decision": "REVIEW", "Governing source": "Stage stress-limit preview", "Max utilization": 3.077},
            {"Check stage": "Final service", "Decision": "Preview PASS", "Governing source": "Final staged service accumulation", "Max utilization": 0.681},
        ]
    )
    state = {
        "_beam_girder_uls_manual_calculation_cache": {
            "Flexure": {"summary_df": pd.DataFrame([{"Status": "PASS"}])},
            "Shear": {"summary_df": pd.DataFrame([{"Status": "PASS"}])},
        },
        "railway_u_girder_sls_decision_summary_df": decision,
    }

    snapshot = build_result_traceability_snapshot(state)

    assert snapshot.pmm_result_available is False
    assert snapshot.uls_result_available is True
    assert snapshot.uls_result_label == "Beam/Girder ULS"
    assert snapshot.uls_result_count == 2
    assert snapshot.sls_result_available is True
    assert snapshot.sls_result_label == "Railway U-Girder staged SLS"
    assert snapshot.sls_overall_status == "REVIEW"
    assert snapshot.max_sls_utilization == 3.077

    readiness = check_report_readiness(snapshot)
    readiness_df = report_readiness_to_dataframe(readiness)
    by_item = {row["Item"]: row for row in readiness_df.to_dict("records")}

    assert by_item["At least one analysis result"]["Status"] == "READY"
    assert by_item["ULS result"]["Status"] == "READY"
    assert by_item["SLS result"]["Status"] == "READY"
    assert "Beam/Girder ULS" in by_item["ULS result"]["Message"]
    assert "Railway U-Girder staged SLS" in by_item["SLS result"]["Message"]


def test_report_qa_expander_uses_workflow_aware_labels() -> None:
    source = __import__("pathlib").Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")

    assert "Stored Result Traceability / Export QA" in source
    assert "ULS Beam/Girder Result" in source
    assert "SLS Railway U-Girder Result" in source
    assert "No stored ULS result is currently available" in source
    assert "No ULS PMM result is currently available" not in source
