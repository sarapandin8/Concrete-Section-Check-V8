from __future__ import annotations

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_uls import (
    build_crossbeam_uls_flexure_preparation,
    run_crossbeam_uls_flexure,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_uls_demand_dataframe,
    _make_crossbeam_uls_flexure_figure,
)
from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state


def test_segmental_flexure_demand_mux_trace_remains_continuous_full_span() -> None:
    state, segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_flexure_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_flexure(preparation)
    rows = pd.DataFrame(result["rows"])
    demand_df = _crossbeam_uls_demand_dataframe(preparation)

    figure = _make_crossbeam_uls_flexure_figure(
        demand_df,
        rows,
        segment_rows=segments,
        support_footprints=list(preparation.support_footprints),
        pt_end_zone_settings=preparation.pt_end_zone_settings,
        construction_method=str(state[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY]),
        member_length_m=preparation.member_length_m,
    )

    demand_traces = [
        trace
        for trace in figure.data
        if str(getattr(trace, "name", "") or "").startswith("Demand Mux")
    ]
    assert demand_traces
    for trace in demand_traces:
        xs = list(trace.x)
        ys = list(trace.y)
        assert xs and len(xs) == len(ys)
        assert all(value is not None for value in xs)
        assert all(value is not None for value in ys)
        finite_x = [float(value) for value in xs]
        assert finite_x == sorted(finite_x)
        assert min(finite_x) <= 1.0e-9
        assert max(finite_x) >= preparation.member_length_m - 1.0e-9
