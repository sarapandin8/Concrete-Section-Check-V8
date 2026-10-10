"""Advisor safety boundaries, physical hoop allocation and independent trials."""
from copy import deepcopy
import math
import pickle

import pandas as pd
import pytest

from concrete_pmm_pro.analysis import igird_rebar_advisor as advisor
from concrete_pmm_pro.ui import igird_rebar_advisor as ui


def layout(legs=2):
    return pd.DataFrame([dict(Active=True, Zone="Midspan", x_start_m=0., x_end_m=20.,
        **{"Bar Size": "DB12", "Diameter_mm": 12., "Legs": legs, "Spacing_mm": 200., "fy_MPa": 390., "Note": "actual hoop"})])


def combined(case="LC1", x=10., q=2.5, **values):
    return {"Case": case, "Governing x": f"{x:g} m", "Zone": "Midspan", "Station type": "PHYSICAL",
        "Combined transverse req mm2/mm": q, "Provided transverse mm2/mm": math.pi*12**2/4*2/200,
        "Transverse D/C value": q/(math.pi*12**2/4*2/200), "s max mm": 300.,
        "Spacing D/C": 200/300, "Status": "REVIEW", "Source row": 3, "Tension face": "bottom",
        "Source coupling": "ENVELOPE — REVIEW", "Calculation status": "COMPLETE",
        "Longitudinal D/C value": .8, "Stress D/C value": .3, **values}


def packages(*rows):
    return {"Girder A": {"combined_vt_df": pd.DataFrame(rows)}}


def test_all_cases_and_repeated_occurrences_control_without_combining_action_vectors():
    rows = [combined("LC1", q=1.0), combined("LC2", q=2.5, **{"Source row": 3}),
            combined("LC2", q=3.2, **{"Source row": 9})]
    p = advisor.recommend(layout(), packages(*rows))
    assert p.layout.iloc[0].Spacing_mm == 70
    assert p.zones.iloc[0]["Governing case"] == "LC2"
    assert p.zones.iloc[0]["Sizing rows"] == 3
    assert p.zones.iloc[0]["Required transverse mm2/mm"] == 3.2


def test_one_torsion_leg_remains_governing_with_four_shear_legs():
    rows = pd.DataFrame([{"Case": "T", "Zone": "Midspan", "Governing x": "10 m",
        "Threshold status": "DESIGN REQUIRED", "Torsion At/s req mm2/mm": 1.5,
        "At D/C": 1.5/(math.pi*12**2/4/200), "s max torsion mm": 250}])
    p = advisor.recommend(layout(legs=4), {"A": {"torsion_check_df": rows}})
    assert p.zones.iloc[0]["Required transverse mm2/mm"] == 6
    assert p.layout.iloc[0].Spacing_mm == 70
    assert not p.complete_combined


def test_shared_layout_uses_the_other_girders_governing_case():
    r = {"A": {"combined_vt_df": pd.DataFrame([combined(q=1.0)])},
         "B": {"combined_vt_df": pd.DataFrame([combined("LC_OTHER", x=14, q=4.8)])}}
    p = advisor.recommend(layout(), r)
    assert p.zones.iloc[0]["Governing girder"] == "B"
    assert p.layout.iloc[0].Diameter_mm == 16
    assert p.layout.iloc[0].Spacing_mm == 80


@pytest.mark.parametrize("q", [float("nan"), float("inf"), -1])
def test_unavailable_transverse_resistance_is_not_zero_or_averaged(q):
    p = advisor.recommend(layout(), packages(combined(q=.8), combined("LC_UNKNOWN", q=q)))
    assert not p.can_verify
    assert p.zones.iloc[0].Action == "DATA REQUIRED"
    assert p.zones.iloc[0]["Missing rows"] == 1


def test_spacing_limit_and_minimum_screen_are_independent_of_strength_sizing():
    p = advisor.recommend(layout(), packages(combined(q=.5, **{"s max mm": 65., "Spacing D/C": 200/65})))
    assert p.layout.iloc[0].Spacing_mm == 60
    p = advisor.recommend(layout(), packages(combined(q=.5, **{"s max mm": 45.})))
    assert not p.can_verify
    assert p.zones.iloc[0].Action == "LAYOUT REVIEW"


def test_existing_adequate_spacing_is_not_relaxed():
    table = layout()
    table.loc[0, "Spacing_mm"] = 70
    p = advisor.recommend(table, packages(combined(q=.5)))
    assert p.layout.iloc[0].Spacing_mm == 70
    assert p.layout.iloc[0].Diameter_mm == 12
    assert p.zones.iloc[0].Action == "KEEP"


def test_uncovered_or_duplicate_zone_blocks_shared_proposal():
    p = advisor.recommend(layout(), packages(combined(x=25)))
    assert not p.can_verify
    doubled = pd.concat([layout(), layout()], ignore_index=True)
    assert not advisor.recommend(doubled, packages(combined())).can_verify


def test_boundary_uses_actual_solver_zone_but_does_not_size_diagram_placeholders():
    table = layout()
    table.loc[0, "x_end_m"] = 10
    second = layout()
    second.loc[0, ["Zone", "x_start_m"]] = ["Right", 10.]
    table = pd.concat([table, second], ignore_index=True)
    r = packages(combined(x=10, q=2.5), combined(x=10, q=5, **{"Zone": "Right"}),
        combined(x=5, q=1e6, **{"Station type": "DIAGRAM BOUNDARY"}))
    p = advisor.recommend(table, r)
    assert p.can_verify
    assert p.zones["Required transverse mm2/mm"].tolist() == [2.5, 5.]


def test_minimum_shear_steel_is_not_mistaken_for_total_required_force_steel():
    shear = pd.DataFrame([{"Case": "S", "Zone": "Midspan", "Governing x": "10 m",
        "Av/s mm2/mm": 2., "Av/s required mm2/mm": .2, "φVs kN": 200., "φVc kN": 100.,
        "Abs demand kN": 400., "φ": .9, "Vp kN": 0., "s max mm": 300., "Strength D/C value": 4/3,
        "Vn limit D/C": 2., "φVn limit kN": 1000.}])
    p = advisor.recommend(layout(), {"A": {"shear_check_df": shear}})
    assert p.zones.iloc[0]["Required transverse mm2/mm"] == 3.
    assert p.layout.iloc[0].Spacing_mm == 70
    assert p.actions.empty  # Capped resistance is not a concrete-demand failure.


def test_steel_condition_can_fail_below_force_ratio_one_and_envelope_stays_review():
    p = advisor.recommend(layout(), packages(combined(q=.5,
        **{"Prestress dominance status": "FAIL", "Longitudinal D/C value": .8})))
    assert "Pretensioned steel condition" in p.actions.Issue.tolist()
    assert "Force concurrency" in p.actions.Issue.tolist()
    summary = advisor.trial_summary(packages(combined(q=.5,
        **{"Transverse D/C value": .4, "Status": "FAIL"})))
    assert summary.iloc[0]["Transverse verification"] == "MEETS NUMERIC CHECKS"
    assert summary.iloc[0]["Overall V+T"] == "FAIL"


def test_declared_concurrent_source_is_not_unnecessarily_flagged():
    p = advisor.recommend(layout(), packages(combined(q=.5, **{"Source coupling": "CONCURRENT — DECLARED"})))
    assert p.actions.empty


def test_trial_isolated_from_original_inputs_and_production_caches_even_if_calculator_mutates():
    original = {advisor.TABLE_KEY: layout(), "beam_uls_loads_table": pd.DataFrame([{"Tu": 80}]),
        "igird_member_uls_runtime_results": {"production": "accepted"},
        "_igird_rebaradvisor_trial_runtime": {"large_old_trial": 1}}
    rows = {"A": pd.DataFrame([{"Mux": 10, "Tu": 80}])}
    before_state, before_rows = pickle.dumps(original), deepcopy(rows)
    trial = layout()
    trial.loc[0, "Spacing_mm"] = 50

    def calculate(local, forces, **kwargs):
        assert local[advisor.TABLE_KEY].iloc[0].Spacing_mm == 50
        assert "igird_member_uls_runtime_results" not in local
        assert "_igird_rebaradvisor_trial_runtime" not in local
        local[advisor.TABLE_KEY].loc[0, "Spacing_mm"] = 10
        forces.loc[0, "Tu"] = 1
        return {"combined_vt_df": pd.DataFrame([combined(q=.5)])}

    ui.calculate_trial(original, rows, trial, route=None, calculator=calculate)
    assert pickle.dumps(original) == before_state
    pd.testing.assert_frame_equal(rows["A"], before_rows["A"])
    assert trial.iloc[0].Spacing_mm == 50


def test_trial_summary_keeps_detailing_failure_and_missing_transverse_data():
    rows = packages(combined(q=.5, **{"Transverse D/C value": .4, "Spacing D/C": 1.2}))
    assert advisor.trial_summary(rows).iloc[0]["Transverse verification"] == "FAIL"
    rows = packages(combined(q=float("nan"), **{"Transverse D/C value": float("nan")}))
    assert advisor.trial_summary(rows).iloc[0]["Transverse verification"] == "DATA REQUIRED"


def test_recommendation_and_issue_display_do_not_mutate_inputs_or_results():
    table, r = layout(), packages(combined())
    before = pickle.dumps((table, r))
    advisor.recommend(table, r)
    assert pickle.dumps((table, r)) == before
