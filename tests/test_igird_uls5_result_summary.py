import pandas as pd

import app


def _base_state():
    return {
        "section_preset_key": "parametric_i_girder",
        "project_design_code": "AASHTO LRFD",
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "_beam_girder_uls_manual_calculation_cache": {
            # Legacy generic flexure must be ignored for I-Girder summary.
            "Flexure": {
                "flexure_preview_df": pd.DataFrame([
                    {"Status": "FAIL", "Case": "LEGACY", "Governing x": "9.000 m", "Demand": "9999 kN-m", "Capacity": "-", "Utilization value": 9.99}
                ])
            },
            "Flexure — Construction": {
                "factors_confirmed": True,
                "flexure_preview_df": pd.DataFrame([
                    {"Status": "PASS", "Case": "AUTO-CONSTR", "Governing x": "10.000 m", "Demand": "500.00 kN-m", "Capacity": "φMn = 5000.00 kN-m", "Utilization value": 0.10}
                ]),
            },
            "Flexure — Final Composite": {
                "flexure_preview_df": pd.DataFrame([
                    {"Status": "PASS", "Case": "Strength I", "Governing x": "10.000 m", "Demand": "1000.00 kN-m", "Capacity": "φMn = 7268.87 kN-m", "Utilization value": 0.138}
                ]),
            },
            "Interface Shear — Final Composite": {
                "result_version": app._IGIRDER_INTERFACE_SHEAR_RESULT_VERSION,
                "interface_status": "PASS",
                "interface_shear_df": pd.DataFrame([
                    {"Status": "PASS", "Case": "Strength I", "Station x (m)": 8.0, "vui (MPa)": 0.514, "phi vni (MPa)": 2.730, "Strength D/C": 0.188, "Minimum Avf D/C": 0.0}
                ]),
            },
            "Shear": {
                "result_version": app._IGIRDER_SHEAR_RESULT_VERSION,
                "shear_check_df": pd.DataFrame([
                    {"Status": "PASS", "Strength status": "PASS", "Detailing status": "PASS", "Case": "Strength I", "Governing x": "2.000 m", "Demand": "400.00 kN", "Capacity": "φVn = 900.00 kN", "Strength D/C value": 0.444, "Detailing D/C value": 0.80, "Governing D/C value": 0.80}
                ]),
            },
            "Torsion": {
                "result_version": app._IGIRDER_TORSION_RESULT_VERSION,
                "torsion_check_df": pd.DataFrame([
                    {"Status": "BELOW THRESHOLD", "Case": "Strength I", "Governing x": "2.000 m", "Tu kN-m": 1.0, "Capacity": "φTn = 100 kN-m", "D/C value": 0.01}
                ]),
            },
            "Shear + Torsion": {
                "result_version": app._IGIRDER_COMBINED_VT_RESULT_VERSION,
                "combined_vt_df": pd.DataFrame([
                    {"Status": "REVIEW", "Case": "Strength I", "Governing x": "2.000 m", "Vu kN": 400.0, "Tu kN-m": 20.0, "Overall D/C value": 0.60, "Notes": "theta consistency guard"}
                ]),
            },
        },
    }


def test_igird_result_summary_uses_stage_specific_rows_and_ignores_legacy_flexure():
    rows = app._results_beam_uls_summary_rows(_base_state())
    by_check = {row["Check"]: row for row in rows}

    assert "Construction Flexure — Noncomposite" in by_check
    assert "Final Composite Flexure" in by_check
    assert "Girder–Deck Interface Shear" in by_check
    assert "Shear" in by_check
    assert "Torsion" in by_check
    assert "Shear + Torsion" in by_check
    assert "Overall ULS" in by_check
    assert "Flexure" not in by_check

    assert by_check["Construction Flexure — Noncomposite"]["Status"] == "PASS"
    assert by_check["Final Composite Flexure"]["Status"] == "PASS"
    assert by_check["Final Composite Flexure"]["D/C / Util."] == "0.138"
    assert by_check["Girder–Deck Interface Shear"]["Status"] == "PASS"
    assert by_check["Girder–Deck Interface Shear"]["D/C / Util."] == "0.188"
    assert by_check["Shear"]["Status"] == "PASS"
    assert by_check["Shear + Torsion"]["Status"] == "REVIEW"
    assert by_check["Overall ULS"]["Status"] == "REVIEW"


def test_igird_result_summary_filters_old_shear_version_without_staling_accepted_flexure_interface():
    state = _base_state()
    state["_beam_girder_uls_manual_calculation_cache"]["Shear"]["result_version"] = "IGIRDER.ULS4.old-shear"

    rows = app._results_beam_uls_summary_rows(state)
    by_check = {row["Check"]: row for row in rows}

    assert by_check["Shear"]["Status"] == "NOT CALCULATED"
    assert by_check["Final Composite Flexure"]["Status"] == "PASS"
    assert by_check["Girder–Deck Interface Shear"]["Status"] == "PASS"
    assert by_check["Overall ULS"]["Status"] == "INCOMPLETE"


def test_igird_result_summary_is_read_only_source_contract():
    source = open("app.py", encoding="utf-8").read()
    block = source[source.index("def _results_igird_uls_summary_rows"): source.index("def _render_results_beam_uls_dashboard")]
    assert "run_" not in block
    assert "_beam_uls_calculate_selected_check" not in block
    assert "run_rc_pmm_solver" not in block
    assert "stored results only" in block


def test_igird_result_summary_filters_old_torsion_version_without_staling_shear():
    state = _base_state()
    state["_beam_girder_uls_manual_calculation_cache"]["Torsion"]["result_version"] = "IGIRDER.ULS5.legacy-torsion"
    rows = app._results_beam_uls_summary_rows(state)
    by_check = {row["Check"]: row for row in rows}
    assert by_check["Torsion"]["Status"] == "NOT CALCULATED"
    assert by_check["Shear"]["Status"] == "PASS"
    assert by_check["Final Composite Flexure"]["Status"] == "PASS"
    assert by_check["Girder–Deck Interface Shear"]["Status"] == "PASS"
    assert by_check["Overall ULS"]["Status"] == "INCOMPLETE"
