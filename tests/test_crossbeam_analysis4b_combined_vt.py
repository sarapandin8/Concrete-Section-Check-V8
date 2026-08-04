from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import (
    CROSSBEAM_ULS_COMBINED_VT_RESULT_HASH_KEY,
    CROSSBEAM_ULS_COMBINED_VT_RESULT_KEY,
    build_crossbeam_uls_combined_vt_preparation,
    run_crossbeam_uls_combined_vt,
)
from concrete_pmm_pro.analysis.crossbeam_uls_shear import run_crossbeam_uls_shear
from concrete_pmm_pro.analysis.crossbeam_uls_torsion import run_crossbeam_uls_torsion
from concrete_pmm_pro.ui.analysis_page import _make_crossbeam_uls_combined_vt_figure
from tests.test_crossbeam_analysis2_uls_shear import _ready_state


def _set_torsion(state: dict[str, object], value_knm: float) -> None:
    for row in state["crossbeam_uls_loads_table"]:
        row["T"] = float(value_knm)


def _row_at(result: dict[str, object], station_m: float, check_point: str = "") -> dict[str, object]:
    return next(
        row
        for row in result["rows"]
        if float(row["Station s (m)"]) == pytest.approx(station_m)
        and str(row.get("Check Point") or "") == check_point
        and str(row.get("Station type") or "") != "PHYSICAL JOINT SIDE"
    )


def test_combined_preparation_aligns_shear_torsion_and_exact_axis_flexure_sources() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 1_500.0)

    preparation = build_crossbeam_uls_combined_vt_preparation(state)

    assert preparation.ready, preparation.errors
    sectional_sources = [
        row
        for row in preparation.shear.rows
        if row.location_type != "PHYSICAL SEGMENT JOINT" and not row.generated_joint_side_check
    ]
    assert sectional_sources
    assert sum(row.generated_support_check for row in sectional_sources) == 6
    assert any(row.generated_joint_side_check for row in preparation.shear.rows)
    rebuilt = build_crossbeam_uls_combined_vt_preparation(state)
    assert rebuilt.fingerprint == preparation.fingerprint


def test_below_threshold_combined_route_reduces_to_shear_without_longitudinal_torsion_gate() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 45.0)
    preparation = build_crossbeam_uls_combined_vt_preparation(state)
    result = run_crossbeam_uls_combined_vt(preparation)
    row = _row_at(result, 5.0)

    assert result["sectional_status"] == "PASS"
    assert row["Torsion required"] is False
    assert row["Longitudinal status"] == "NOT REQUIRED"
    assert math.isnan(float(row["Longitudinal D/C value"]))
    assert float(row["Transverse D/C value"]) == pytest.approx(
        float(row["Av/s adopted required mm2/mm"])
        / float(row["Av/s provided all shear legs mm2/mm"])
    )


def test_aci_9_5_4_3_adds_required_areas_without_double_counting_outer_stirrup_legs() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 1_500.0)
    preparation = build_crossbeam_uls_combined_vt_preparation(state)
    result = run_crossbeam_uls_combined_vt(preparation)
    shear_result = run_crossbeam_uls_shear(preparation.shear)
    torsion_result = run_crossbeam_uls_torsion(preparation.torsion)

    combined = _row_at(result, 5.0)
    shear = next(row for row in shear_result["rows"] if float(row["Station s (m)"]) == pytest.approx(5.0))
    torsion = next(row for row in torsion_result["rows"] if float(row["Station s (m)"]) == pytest.approx(5.0))

    expected_required = max(
        float(shear["Av/s adopted required mm2/mm"])
        + 2.0 * float(torsion["At/s required mm2/mm"]),
        float(torsion["(Av+2At)/s min mm2/mm"]),
    )
    expected_provided = 2.0 * float(torsion["At/s mm2/mm"])
    assert float(combined["(Av+2At)/s adopted required mm2/mm"]) == pytest.approx(expected_required)
    assert float(combined["Outer side legs/s provided mm2/mm"]) == pytest.approx(expected_provided)
    assert float(combined["Transverse D/C value"]) == pytest.approx(expected_required / expected_provided)
    # The same outer closed-stirrup legs are physical steel and cannot be
    # credited once as Av and again as 2At.
    assert float(combined["Outer side legs/s provided mm2/mm"]) < (
        float(shear["Av/s mm2/mm"]) + 2.0 * float(torsion["At/s mm2/mm"])
    )


def test_aci_9_5_4_4_direct_interaction_can_use_bonded_tendon_overstrength_but_keeps_al_minimum() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 5_000.0)
    result = run_crossbeam_uls_combined_vt(build_crossbeam_uls_combined_vt_preparation(state))
    row = _row_at(result, 5.0)

    assert float(row["Al strength equivalent mm2"]) > float(row["Al provided mm2"])
    assert float(row["Al minimum D/C value"]) < 1.0
    assert row["Flexure+torsion status"] == "PASS"
    assert float(row["Flexure+torsion D/C value"]) < 1.0
    assert row["Longitudinal status"] == "PASS"
    assert abs(float(row["Direct solver force residual N"])) <= 1.0
    expected_combined_pu = float(row["P kN"]) - float(row["Torsional tensile force kN"])
    assert float(row["Combined Pu for 9.5.4.4 kN"]) == pytest.approx(expected_combined_pu)


def test_high_torsion_fails_combined_transverse_adoption_gate() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 5_000.0)
    result = run_crossbeam_uls_combined_vt(build_crossbeam_uls_combined_vt_preparation(state))

    assert result["sectional_status"] == "FAIL"
    assert any(
        row["Transverse status"] == "FAIL" and float(row["Transverse D/C value"]) > 1.0
        for row in result["rows"]
        if row["Station type"] != "PHYSICAL JOINT SIDE"
    )


def test_precast_development_zone_keeps_minimum_torsion_bar_development_at_review() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 1_500.0)
    result = run_crossbeam_uls_combined_vt(build_crossbeam_uls_combined_vt_preparation(state))
    end_row = _row_at(result, 0.0)
    interior_row = _row_at(result, 5.0)

    assert end_row["Ordinary rebar credit"] == "NO CREDIT"
    assert end_row["Longitudinal status"] == "REVIEW"
    assert end_row["Status"] == "REVIEW"
    assert interior_row["Ordinary rebar credit"] == "FULL CREDIT"
    assert interior_row["Longitudinal status"] == "PASS"


def test_physical_joint_sides_remain_review_and_do_not_govern_sectional_dc() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 1_500.0)
    result = run_crossbeam_uls_combined_vt(build_crossbeam_uls_combined_vt_preparation(state))

    joint_rows = [row for row in result["rows"] if row["Station type"] == "PHYSICAL JOINT SIDE"]
    assert joint_rows
    assert all(row["Status"] == "REVIEW" for row in joint_rows)
    assert all(math.isnan(float(row["Overall D/C value"])) for row in joint_rows)
    assert result["governing_row"]["Station type"] != "PHYSICAL JOINT SIDE"
    assert result["joint_review_count"] > 0


def test_combined_chart_uses_shared_utilization_language_and_single_limit_legend() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 1_500.0)
    preparation = build_crossbeam_uls_combined_vt_preparation(state)
    result = run_crossbeam_uls_combined_vt(preparation)
    figure = _make_crossbeam_uls_combined_vt_figure(
        pd.DataFrame(result["rows"]),
        list(preparation.support_footprints),
        state["crossbeam_ui1_segment_layout_rows"],
    )
    names = [str(trace.name) for trace in figure.data if trace.showlegend is not False]

    assert names.count("Stress D/C") == 1
    assert names.count("Transverse D/C") == 1
    assert names.count("Longitudinal D/C") == 1
    assert names.count("Limit = 1.0") == 1
    assert names.count("Gov. V+T") == 1
    assert names.count("Physical joint — REVIEW") == 1


def test_combined_module_is_crossbeam_scoped_and_selector_is_exposed() -> None:
    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
    module_source = Path("concrete_pmm_pro/analysis/crossbeam_uls_combined_vt.py").read_text(encoding="utf-8")

    assert '["Flexure", "Shear", "Torsion", "Shear + Torsion"]' in source
    assert "_render_crossbeam_uls_combined_vt_workspace()" in source
    assert CROSSBEAM_ULS_COMBINED_VT_RESULT_KEY in module_source
    assert CROSSBEAM_ULS_COMBINED_VT_RESULT_HASH_KEY in module_source
    assert "pmm_solver.py" not in module_source
