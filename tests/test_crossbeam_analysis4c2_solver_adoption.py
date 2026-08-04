from __future__ import annotations

import math
from pathlib import Path

import pytest

from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import (
    CROSSBEAM_ULS_COMBINED_VT_RESULT_HASH_KEY,
    CROSSBEAM_ULS_COMBINED_VT_RESULT_KEY,
    build_crossbeam_uls_combined_vt_preparation,
    run_crossbeam_uls_combined_vt,
)
from concrete_pmm_pro.analysis.crossbeam_uls_shear import (
    build_crossbeam_uls_shear_preparation,
    run_crossbeam_uls_shear,
)
from concrete_pmm_pro.analysis.crossbeam_uls_torsion import (
    build_crossbeam_uls_torsion_preparation,
    run_crossbeam_uls_torsion,
)
from concrete_pmm_pro.crossbeam.transverse import transverse_bar_area_mm2
from tests.test_crossbeam_analysis2_uls_shear import _ready_state
from tests.test_crossbeam_analysis3_uls_torsion import _mixed_state


def _set_torsion(state: dict[str, object], value_knm: float) -> None:
    for row in state["crossbeam_uls_loads_table"]:
        row["T"] = float(value_knm)


def _first_hollow(rows: list[dict[str, object]]) -> dict[str, object]:
    return next(
        row for row in rows
        if row.get("Section ID") == "CB-H01"
        and row.get("Location type") != "PHYSICAL SEGMENT JOINT"
        and row.get("Station type") != "PHYSICAL JOINT SIDE"
    )


def test_additional_verified_outer_cage_contributes_two_unique_shear_legs() -> None:
    state = _mixed_state(torsion_knm=1_000.0)
    shear = run_crossbeam_uls_shear(build_crossbeam_uls_shear_preparation(state))
    torsion = run_crossbeam_uls_torsion(build_crossbeam_uls_torsion_preparation(state))
    shear_row = _first_hollow(shear["rows"])
    torsion_row = _first_hollow(torsion["rows"])

    area = transverse_bar_area_mm2("DB12")
    base = 4.0 * area / 200.0
    additional = 2.0 * area / 200.0
    total = base + additional

    assert float(shear_row["Base Av/s mm2/mm"]) == pytest.approx(base)
    assert float(shear_row["Additional cage Av/s mm2/mm"]) == pytest.approx(additional)
    assert float(shear_row["Av/s mm2/mm"]) == pytest.approx(total)
    assert float(torsion_row["Unique transverse provided/s mm2/mm"]) == pytest.approx(total)
    assert torsion_row["Torsion cage relationship"] == "Additional outer cage"


def test_shared_outer_cage_is_not_added_to_base_av_a_second_time() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 1_500.0)
    shear = run_crossbeam_uls_shear(build_crossbeam_uls_shear_preparation(state))
    row = next(item for item in shear["rows"] if item.get("Location type") != "PHYSICAL SEGMENT JOINT")

    assert row["Torsion cage relationship"] == "Shared with existing outer shear loop"
    assert float(row["Additional cage Av/s mm2/mm"]) == pytest.approx(0.0)
    assert float(row["Av/s mm2/mm"]) == pytest.approx(float(row["Base Av/s mm2/mm"]))


def test_combined_transverse_gate_uses_unique_physical_leg_pool() -> None:
    state = _mixed_state(torsion_knm=1_000.0)
    preparation = build_crossbeam_uls_combined_vt_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_combined_vt(preparation)
    row = _first_hollow(result["rows"])

    required = float(row["(Av+2At)/s adopted required mm2/mm"])
    provided = float(row["Unique transverse provided/s mm2/mm"])
    assert provided == pytest.approx(float(row["Av/s provided all shear legs mm2/mm"]))
    assert float(row["Transverse D/C value"]) == pytest.approx(required / provided)
    assert provided > float(row["Outer side legs/s provided mm2/mm"])


def test_longitudinal_al_is_a_subset_of_as_and_direct_interaction_does_not_add_steel() -> None:
    state = _mixed_state(torsion_knm=1_000.0)
    result = run_crossbeam_uls_combined_vt(build_crossbeam_uls_combined_vt_preparation(state))
    row = _first_hollow(result["rows"])

    assert float(row["Al provided mm2"]) > 0.0
    assert float(row["Torsional tensile force kN"]) > 0.0
    assert float(row["Combined Pu for 9.5.4.4 kN"]) == pytest.approx(
        float(row["P kN"]) - float(row["Torsional tensile force kN"])
    )
    assert math.isfinite(float(row["Flexure+torsion D/C value"]))
    assert abs(float(row["Direct solver force residual N"])) <= 1.0


def test_torsion_support_face_keeps_anchorage_as_review_without_hiding_numeric_failure() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 1_500.0)
    result = run_crossbeam_uls_combined_vt(build_crossbeam_uls_combined_vt_preparation(state))
    face_rows = [
        row for row in result["rows"]
        if row.get("Generated support check")
        and "COLUMN FACE" in f"{row.get('Location type')} {row.get('Requested location type')}".upper()
        and row.get("Torsion required")
    ]
    assert face_rows
    assert all(row["Torsion support anchorage status"] == "REVIEW" for row in face_rows)
    for row in face_rows:
        if any(
            math.isfinite(float(row.get(key, float("nan")))) and float(row[key]) > 1.0
            for key in ("Transverse D/C value", "Longitudinal D/C value", "Stress D/C value")
        ):
            assert row["Status"] == "FAIL"
        else:
            assert row["Status"] == "REVIEW"



def test_precast_torsion_bt_plus_d_extension_is_a_separate_station_gate() -> None:
    state = _mixed_state(torsion_knm=1_000.0)
    result = run_crossbeam_uls_combined_vt(build_crossbeam_uls_combined_vt_preparation(state))
    row = next(
        item for item in result["rows"]
        if item.get("Section ID") == "CB-H01"
        and abs(float(item.get("Station s (m)")) - 5.0) <= 1.0e-9
        and item.get("Station type") != "PHYSICAL JOINT SIDE"
    )

    required = float(row["Torsion bt+d extension m"])
    available = float(row["Available extension to nearest Segment end m"])
    assert required > available > 0.0
    assert float(row["Torsion extension D/C value"]) == pytest.approx(required / available)
    assert row["Torsion station development status"] == "REVIEW"
    assert "Reinforcement continuity across a Precast joint is not assumed" in row["Notes"]

def test_combined_module_and_selector_are_crossbeam_scoped() -> None:
    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
    module = Path("concrete_pmm_pro/analysis/crossbeam_uls_combined_vt.py").read_text(encoding="utf-8")

    assert '["Flexure", "Shear", "Torsion", "Shear + Torsion"]' in source
    assert "_render_crossbeam_uls_combined_vt_workspace()" in source
    assert CROSSBEAM_ULS_COMBINED_VT_RESULT_KEY in module
    assert CROSSBEAM_ULS_COMBINED_VT_RESULT_HASH_KEY in module
    assert "pmm_solver.py" not in module
