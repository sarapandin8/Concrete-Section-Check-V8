from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.crossbeam_uls import (
    build_crossbeam_uls_flexure_preparation,
    run_crossbeam_uls_flexure,
)
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json


_FIXTURE = Path(__file__).with_name("data") / "crossbeam_analysis4_direct_solver_benchmark.json"


def _benchmark_state() -> dict[str, object]:
    state: dict[str, object] = {}
    apply_project_to_session_state(project_from_json(_FIXTURE.read_text(encoding="utf-8")), state)
    return state


def _result(state: dict[str, object]) -> dict[str, object]:
    preparation = build_crossbeam_uls_flexure_preparation(state)
    assert preparation.ready, preparation.errors
    return run_crossbeam_uls_flexure(preparation)


def _unique_capacity(rows: pd.DataFrame, *, section_id: str, credit: str) -> list[float]:
    selected = rows[
        (rows["Section ID"].astype(str) == section_id)
        & (rows["Ordinary rebar credit"].astype(str) == credit)
        & (rows["Bending direction"].astype(str).str.contains("Sagging"))
    ]
    values = sorted({round(float(value), 6) for value in selected["Capacity kN-m"].dropna()})
    return values


def test_direct_solver_matches_independent_crossbeam_benchmark_values() -> None:
    result = _result(_benchmark_state())
    rows = pd.DataFrame(result["rows"])

    assert result["status"] == "PASS"
    assert result["schema"] == "crossbeam-analysis4c7d3-segmental-tendon-only-flexure-v1"
    assert result["flexure_credit_basis"] == "TENDON-ONLY"
    assert result["solver_route"] == "DIRECT UNIAXIAL P-M3"
    assert result["accuracy_preset_dependency"].startswith("NONE")
    assert result["physical_joint_side_checks"] == 10

    # Independently checked ACI 318-19 strain-compatibility benchmarks for the
    # uploaded 30 m Crossbeam project (Pu = 5,000 kN, positive M3).
    assert _unique_capacity(rows, section_id="CB-S01", credit="TENDON-ONLY") == pytest.approx([16422.326175], abs=0.02)
    assert _unique_capacity(rows, section_id="CB-H01", credit="TENDON-ONLY") == pytest.approx([15112.431773], abs=0.02)

    solid_joint = rows[
        (rows["Section ID"] == "CB-S01")
        & (rows["Location type"] == "PHYSICAL SEGMENT JOINT")
    ]
    hollow_joint = rows[
        (rows["Section ID"] == "CB-H01")
        & (rows["Location type"] == "PHYSICAL SEGMENT JOINT")
    ]
    assert set(solid_joint["Ordinary rebar credit"]) == {"TENDON-ONLY"}
    assert set(hollow_joint["Ordinary rebar credit"]) == {"TENDON-ONLY"}
    assert sorted({round(float(value), 6) for value in solid_joint["Capacity kN-m"]}) == pytest.approx([16422.326190], abs=0.02)
    assert sorted({round(float(value), 6) for value in hollow_joint["Capacity kN-m"]}) == pytest.approx([15112.431770], abs=0.02)

    residuals = pd.to_numeric(rows["Force residual ratio"], errors="coerce").dropna().abs()
    assert not residuals.empty
    assert float(residuals.max()) <= 1.0e-6


def test_direct_crossbeam_result_is_independent_of_accuracy_preset() -> None:
    capacities: dict[str, list[tuple[float, str, str, float, float]]] = {}
    for preset in ("Fast", "Standard", "High Accuracy"):
        state = _benchmark_state()
        state["crossbeam_flexure_accuracy_preset"] = preset
        state["analysis_accuracy_preset"] = preset
        result = _result(state)
        rows = pd.DataFrame(result["rows"])
        capacities[preset] = sorted(
            (
                round(float(row["Station s (m)"]), 9),
                str(row["Check Point"]),
                str(row["Segment"]),
                round(float(row["Capacity kN-m"]), 6),
                round(float(row["D/C value"]), 9),
            )
            for _, row in rows.iterrows()
        )
    assert capacities["Fast"] == capacities["Standard"] == capacities["High Accuracy"]


def test_precast_flexure_is_tendon_only_at_interior_near_joint_and_joint_rows() -> None:
    result = _result(_benchmark_state())
    rows = pd.DataFrame(result["rows"])

    assert set(rows["Ordinary rebar credit"].astype(str)) == {"TENDON-ONLY"}
    assert set(pd.to_numeric(rows["Ordinary bars credited"], errors="coerce").fillna(0).astype(int)) == {0}
    assert result["development_zone_checks"] == 0

    joint_rows = rows[rows["Location type"] == "PHYSICAL SEGMENT JOINT"]
    assert len(joint_rows.index) == 10
    assert set(joint_rows["Check Point"]) == {
        "J1-L", "J1-R", "J2-L", "J2-R", "J3-L", "J3-R", "J4-L", "J4-R", "J5-L", "J5-R"
    }

    near_joint_rows = rows[rows["Location type"] == "NEAR JOINT SECTION"]
    assert not near_joint_rows.empty
    assert set(near_joint_rows["Ordinary rebar credit"].astype(str)) == {"TENDON-ONLY"}

    j3 = joint_rows[(pd.to_numeric(joint_rows["Station s (m)"]) - 15.0).abs() <= 1.0e-9]
    assert set(j3["Segment"]) == {"S3", "S4"}
    assert set(j3["Section ID"]) == {"CB-S01"}


def test_crossbeam_direct_route_does_not_call_generic_pmm_solver(monkeypatch: pytest.MonkeyPatch) -> None:
    import concrete_pmm_pro.analysis.pmm_solver as generic_pmm

    monkeypatch.setattr(
        generic_pmm,
        "run_pmm_solver",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generic PMM route must not run")),
    )
    result = _result(_benchmark_state())
    assert result["status"] == "PASS"
