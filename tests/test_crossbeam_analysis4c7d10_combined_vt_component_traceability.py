from __future__ import annotations

import math

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import (
    build_crossbeam_uls_combined_vt_preparation,
    run_crossbeam_uls_combined_vt,
)
from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_combined_vt_component_governing,
    _crossbeam_combined_vt_component_table,
)
from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state


def _benchmark_result() -> tuple[pd.DataFrame, dict[str, object]]:
    state, _segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_combined_vt_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_combined_vt(preparation)
    return pd.DataFrame(result["rows"]), result


def test_component_evidence_tables_use_component_status_not_combined_status() -> None:
    rows, _result = _benchmark_result()

    stress = _crossbeam_combined_vt_component_table(rows, "stress")
    transverse = _crossbeam_combined_vt_component_table(rows, "transverse")
    longitudinal = _crossbeam_combined_vt_component_table(rows, "longitudinal")

    # The benchmark fails overall because Aℓ is insufficient, but every
    # section-size station passes.  A section-size evidence table must therefore
    # never inherit the overall Combined V+T FAIL status.
    assert set(stress["Status"].astype(str)) == {"PASS"}
    assert set(transverse["Status"].astype(str)) <= {"PASS", "NOT REQUIRED"}
    assert "FAIL" in set(longitudinal["Status"].astype(str))

    source = rows[rows["Station type"].astype(str) != "PHYSICAL JOINT SIDE"].copy()
    expected_stress = source["Stress status"].astype(str).tolist()
    expected_transverse = source["Transverse status"].astype(str).tolist()
    expected_longitudinal = source["Longitudinal status"].astype(str).tolist()
    assert stress["Status"].astype(str).tolist() == expected_stress
    assert transverse["Status"].astype(str).tolist() == expected_transverse
    assert longitudinal["Status"].astype(str).tolist() == expected_longitudinal


def test_combined_governing_tie_prefers_imported_station_over_near_joint() -> None:
    rows, result = _benchmark_result()
    governing = dict(result["governing_row"])

    assert float(governing["Overall D/C value"]) == pytest.approx(2.2621281911, rel=1.0e-8)
    assert str(governing["Demand source"]) == "IMPORTED"
    assert str(governing["Station type"]) == "SEGMENT INTERIOR"
    assert float(governing["Station s (m)"]) == pytest.approx(6.0)

    near = rows[
        (rows["Station type"].astype(str) == "NEAR PHYSICAL JOINT")
        & (pd.to_numeric(rows["Station s (m)"], errors="coerce") - 4.6).abs().le(1.0e-9)
    ]
    assert len(near.index) == 1
    assert float(near.iloc[0]["Overall D/C value"]) == pytest.approx(float(governing["Overall D/C value"]), rel=1.0e-12)

    # The longitudinal component view must resolve the same governing plateau
    # to the same actual imported station.
    component = _crossbeam_combined_vt_component_governing(rows, "longitudinal")
    assert component is not None
    assert float(component["Station s (m)"]) == pytest.approx(6.0)
    assert str(component["Demand source"]) == "IMPORTED"


def test_genuinely_larger_generated_row_can_still_govern() -> None:
    rows, _result = _benchmark_result()
    # This is a source-level guard: deterministic tie ownership must not turn
    # into a blanket ban on generated stations.  The production selector is
    # exercised indirectly by perturbing one near-joint D/C above the plateau.
    from concrete_pmm_pro.analysis.crossbeam_uls_combined_vt import _select_governing_row

    sectional = rows[rows["Station type"].astype(str) != "PHYSICAL JOINT SIDE"].to_dict("records")
    target = next(row for row in sectional if math.isclose(float(row["Station s (m)"]), 4.6, abs_tol=1.0e-9))
    target["Overall D/C value"] = float(target["Overall D/C value"]) + 0.01
    governing = _select_governing_row(sectional)
    assert governing is target
