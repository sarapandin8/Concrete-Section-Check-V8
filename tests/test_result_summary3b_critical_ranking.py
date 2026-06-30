from __future__ import annotations

import pandas as pd

import app


def _state_with_shear_detailing_controlling_over_sls() -> dict[str, object]:
    return {
        "project_design_code": "AASHTO LRFD",
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "_beam_girder_uls_manual_calculation_cache": {
            "Flexure": {
                "flexure_preview_df": pd.DataFrame(
                    [
                        {
                            "Status": "PASS",
                            "Case": "Strength I",
                            "Governing x": "5.000 m",
                            "Demand": "3,805.24 kN-m",
                            "Capacity": "φMn = 15,427.74 kN-m",
                            "Utilization value": 0.247,
                        }
                    ]
                )
            },
            "Shear": {
                "shear_check_df": pd.DataFrame(
                    [
                        {
                            "Status": "PASS",
                            "Strength status": "PASS",
                            "Detailing status": "FAIL",
                            "Case": "Strength I",
                            "Governing x": "7.000 m",
                            "Demand": "805.09 kN",
                            "Capacity": "φVn = 1,908.64 kN",
                            "Strength D/C value": 0.422,
                            "Detailing D/C value": 1.893,
                            "Av/s min D/C": 1.893,
                            "Abs demand kN": 805.09,
                        }
                    ]
                )
            },
            "Torsion": {
                "torsion_check_df": pd.DataFrame(
                    [
                        {
                            "Status": "BELOW THRESHOLD",
                            "Case": "Strength I",
                            "Governing x": "4.000 m",
                            "Tu kN-m": "100.00 kN-m",
                            "Capacity": "φTn = 759.10 kN-m",
                            "D/C value": 0.132,
                        }
                    ]
                )
            },
            "Shear + Torsion": {
                "combined_vt_df": pd.DataFrame(
                    [
                        {
                            "Status": "PASS",
                            "Case": "Strength I",
                            "Governing x": "4.000 m",
                            "Vu kN": 57.137,
                            "Tu kN-m": "100.00 kN-m",
                            "Overall D/C value": 0.947,
                        }
                    ]
                )
            },
        },
        "result_summary_beam_girder_sls_stage_summary_df": pd.DataFrame(
            [
                {
                    "Stage": "Lifting",
                    "Case Name": "AUTO-LIFT",
                    "Status": "Preview FAIL",
                    "Controls": "Tension",
                    "Station x (m)": "2.000",
                    "Fiber": "Top",
                    "Actual stress (MPa)": 6.370,
                    "Limit stress (MPa)": 3.48,
                    "Utilization": 1.830,
                    "Limit profile": "Temporary release — bonded auxiliary reinforcement condition",
                }
            ]
        ),
    }


def test_critical_check_ranks_shear_detailing_dc_above_sls_preview_fail() -> None:
    rows = app._results_governing_rows(_state_with_shear_detailing_controlling_over_sls())
    critical = app._results_critical_row(rows)

    assert critical is not None
    assert app._results_critical_label(critical) == "ULS Shear"
    assert critical["Status"] == "FAIL"
    assert "Av/s min D/C 1.893" in critical["D/C / Util."]


def test_overview_critical_card_uses_check_label_not_generic_module() -> None:
    cards = app._results_availability_cards(_state_with_shear_detailing_controlling_over_sls())
    by_title = {str(card["title"]): card for card in cards}

    assert by_title["Critical check"]["value"] == "ULS Shear"
    assert "Av/s min D/C 1.893" in by_title["Critical check"]["detail"]


def test_source_blocked_vt_utilization_is_explicitly_informational() -> None:
    rows = app._results_beam_uls_summary_rows(_state_with_shear_detailing_controlling_over_sls())
    vt_row = next(row for row in rows if row["Check"] == "Shear + Torsion")

    assert vt_row["Status"] == "SOURCE BLOCKED"
    assert vt_row["D/C / Util."] == "Interaction D/C 0.947; source gate BLOCKED"
    assert "informational until source gates pass" in vt_row["Required Action"]


def test_shear_failure_action_names_minimum_stirrup_detailing_gate() -> None:
    rows = app._results_beam_uls_summary_rows(_state_with_shear_detailing_controlling_over_sls())
    shear_row = next(row for row in rows if row["Check"] == "Shear")

    assert shear_row["Status"] == "FAIL"
    assert "minimum stirrup/detailing gate" in shear_row["Required Action"]
    assert "reduce stirrup spacing" in shear_row["Required Action"]


def test_executive_fail_detail_lists_failing_checks() -> None:
    state = _state_with_shear_detailing_controlling_over_sls()
    executive = app._results_executive_status(app._results_governing_rows(state), state)

    assert executive["status"] == "danger"
    assert "Failing checks:" in executive["detail"]
    assert "ULS Shear" in executive["detail"]
    assert "SLS Stress" in executive["detail"]
