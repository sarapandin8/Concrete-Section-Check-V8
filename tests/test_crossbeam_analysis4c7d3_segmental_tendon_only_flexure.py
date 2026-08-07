from __future__ import annotations

from copy import deepcopy

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_uls import (
    build_crossbeam_uls_flexure_preparation,
    run_crossbeam_uls_flexure,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_uls_demand_dataframe,
    _make_crossbeam_uls_flexure_figure,
)
from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state


def test_segmental_flexure_readiness_and_fingerprint_do_not_depend_on_rebar_source() -> None:
    state, _segments = _mixed_30m_state()
    baseline = build_crossbeam_uls_flexure_preparation(state)
    assert baseline.ready, baseline.errors

    modified = deepcopy(state)
    modified[CB_RB_TEMPLATE_ROWS_KEY] = []
    modified[CB_RB_ZONE_ROWS_KEY] = []
    modified[CB_TR_TEMPLATE_ROWS_KEY] = []
    without_rebar = build_crossbeam_uls_flexure_preparation(modified)

    assert without_rebar.ready, without_rebar.errors
    assert without_rebar.fingerprint == baseline.fingerprint
    assert all(row.rebar_credit_status == "TENDON-ONLY" for row in without_rebar.rows)
    assert all(row.ordinary_rebar_count == 0 for row in without_rebar.rows)
    assert all(abs(row.ordinary_rebar_area_mm2) <= 1.0e-12 for row in without_rebar.rows)


def test_segmental_tendon_only_phi_mn_and_mux_are_full_member_traces() -> None:
    state, segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_flexure_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_flexure(preparation)
    rows = pd.DataFrame(result["rows"])

    assert result["flexure_credit_basis"] == "TENDON-ONLY"
    assert result["development_zone_checks"] == 0
    assert set(rows["Ordinary rebar credit"].astype(str)) == {"TENDON-ONLY"}

    figure = _make_crossbeam_uls_flexure_figure(
        _crossbeam_uls_demand_dataframe(preparation),
        rows,
        segment_rows=segments,
        support_footprints=list(preparation.support_footprints),
        pt_end_zone_settings=preparation.pt_end_zone_settings,
        construction_method=str(state[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY]),
        member_length_m=preparation.member_length_m,
    )

    demand = [trace for trace in figure.data if str(getattr(trace, "name", "") or "").startswith("Demand Mux")]
    capacity = [trace for trace in figure.data if str(getattr(trace, "name", "") or "").startswith("Adopted tendon-only φMn")]
    assert demand
    assert len(capacity) == 1

    for trace in [*demand, *capacity]:
        xs = list(trace.x)
        ys = list(trace.y)
        assert xs and len(xs) == len(ys)
        assert all(value is not None for value in xs)
        assert all(value is not None for value in ys)
        finite_x = [float(value) for value in xs]
        assert finite_x == sorted(finite_x)
        assert min(finite_x) <= 1.0e-9
        assert max(finite_x) >= preparation.member_length_m - 1.0e-9

    assert not any(str(getattr(trace, "name", "") or "") == "No rebar credit zone" for trace in figure.data)
