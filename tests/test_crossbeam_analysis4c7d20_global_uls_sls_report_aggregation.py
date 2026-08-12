from __future__ import annotations

import app


def _row(
    module: str,
    check: str,
    *,
    status: str = "FAIL",
    util: str = "-",
    demand: str = "-",
    capacity: str = "-",
    case: str = "ULS-01",
) -> dict[str, object]:
    return {
        "Module": module,
        "Check": check,
        "Status": status,
        "Governing Case": case,
        "Station / Point": "s=6.000 m",
        "Demand": demand,
        "Capacity / Limit": capacity,
        "D/C / Util.": util,
        "Source": "Analysis",
        "Code Basis": "ACI 318-19",
    }


def test_crossbeam_global_critical_does_not_rank_sls_ratio_above_uls_strength_failure() -> None:
    rows = [
        _row("ULS Crossbeam", "Torsion", util="2.262"),
        _row("ULS Crossbeam", "Shear + Torsion", util="2.262"),
        _row(
            "SLS Crossbeam",
            "At Final Service",
            util="13.798",
            demand="Stress = +8.958 MPa",
            capacity="Joint stress ≤ -0.700 MPa",
        ),
    ]

    critical = app._results_critical_row(rows)
    assert critical is not None
    assert critical["Module"] == "ULS Crossbeam"
    assert critical["Check"] == "Shear + Torsion"

    cards = {card["title"]: card for card in app._results_crossbeam_critical_cards(rows)}
    assert cards["Critical ULS"]["value"] == "Shear + Torsion"
    assert "D/C 2.262" in cards["Critical ULS"]["detail"]
    assert cards["Critical SLS"]["value"] == "At Final Service"
    assert "Stress = +8.958 MPa" in cards["Critical SLS"]["detail"]
    assert "Joint stress ≤ -0.700 MPa" in cards["Critical SLS"]["detail"]


def test_crossbeam_failing_summary_keeps_uls_and_sls_domains_visible_without_cross_domain_dc_comparison() -> None:
    rows = [
        _row("ULS Crossbeam", "Torsion", util="2.262"),
        _row("ULS Crossbeam", "Shear + Torsion", util="2.262"),
        _row(
            "SLS Crossbeam",
            "At Transfer",
            util="N/A",
            demand="Stress = +8.958 MPa",
            capacity="Joint stress ≤ +0.000 MPa",
        ),
        _row(
            "SLS Crossbeam",
            "At Final Service",
            util="13.798",
            demand="Stress = +8.958 MPa",
            capacity="Joint stress ≤ -0.700 MPa",
        ),
    ]

    summary = app._results_failing_check_summary(rows, limit=6)
    assert "ULS Torsion (FAIL; 2.262)" in summary
    assert "ULS Shear + Torsion (FAIL; 2.262)" in summary
    assert "SLS Crossbeam · At Transfer (FAIL; Stress = +8.958 MPa vs Joint stress ≤ +0.000 MPa)" in summary
    assert "SLS Crossbeam · At Final Service (FAIL; Stress = +8.958 MPa vs Joint stress ≤ -0.700 MPa)" in summary
    assert summary.index("ULS Shear + Torsion") < summary.index("SLS Crossbeam · At Final Service")
    assert "SLS Crossbeam · At Final Service (FAIL; 13.798)" not in summary


def test_crossbeam_executive_failure_discloses_missing_uls_and_pending_deflection(monkeypatch) -> None:
    monkeypatch.setattr(app, "_results_is_crossbeam_workflow", lambda _state: True)
    monkeypatch.setattr(
        app,
        "_results_active_uls_completion",
        lambda _state: (0, 4, ["Flexure", "Shear", "Torsion", "Shear + Torsion"]),
    )
    monkeypatch.setattr(app, "_results_crossbeam_sls_completion", lambda _state: (2, 2, []))
    monkeypatch.setattr(app, "_results_sls_complete_for_report", lambda _state: False)

    rows = [
        _row(
            "SLS Crossbeam",
            "At Final Service",
            util="13.798",
            demand="Stress = +8.958 MPa",
            capacity="Joint stress ≤ -0.700 MPa",
        )
    ]
    executive = app._results_executive_status(rows, {})
    assert executive["title"] == "Overall Status: FAIL"
    assert "ULS results 0/4 current" in executive["detail"]
    assert "Deflection / Camber remains pending" in executive["detail"]

    handoff = app._results_report_handoff_state({}, rows)
    assert handoff["value"] == "Review required"
    assert "ULS results 0/4 current" in handoff["detail"]
    assert "Deflection / Camber remains pending" in handoff["detail"]


def test_report_qa_cards_show_separate_crossbeam_critical_domains(monkeypatch) -> None:
    rows = [
        _row("ULS Crossbeam", "Shear + Torsion", util="2.262"),
        _row(
            "SLS Crossbeam",
            "At Final Service",
            util="13.798",
            demand="Stress = +8.958 MPa",
            capacity="Joint stress ≤ -0.700 MPa",
        ),
    ]
    monkeypatch.setattr(app, "_results_governing_rows", lambda _state: rows)
    monkeypatch.setattr(app, "_results_is_crossbeam_workflow", lambda _state: True)
    monkeypatch.setattr(
        app,
        "_results_executive_status",
        lambda _rows, _state: {"title": "Overall Status: FAIL", "detail": "combined", "status": "danger"},
    )
    monkeypatch.setattr(
        app,
        "_results_report_handoff_state",
        lambda _state, _rows: {"value": "Review required", "detail": "review", "status": "danger"},
    )

    cards = app._report_qa_dashboard_cards({})
    by_title = {card["title"]: card for card in cards}
    assert "Critical check" not in by_title
    assert by_title["Critical ULS"]["value"] == "Shear + Torsion"
    assert by_title["Critical SLS"]["value"] == "At Final Service"
    assert by_title["Overall status"]["value"] == "FAIL"
