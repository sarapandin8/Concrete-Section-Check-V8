from __future__ import annotations

import ast
import inspect
import math

import pandas as pd

from concrete_pmm_pro.analysis.crossbeam_uls import (
    build_crossbeam_uls_flexure_preparation,
    run_crossbeam_uls_flexure,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY,
    CB_STATION_FORCE_CONTRACT_KEY,
    default_station_force_contract,
)
from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_uls_demand_dataframe,
    _make_crossbeam_uls_flexure_figure,
    _render_crossbeam_uls_flexure_workspace,
)
from tests.test_crossbeam_analysis3b_joint_capacity_plot import _mixed_30m_state


def test_flexure_workspace_defines_construction_method_before_runtime_use() -> None:
    source = inspect.getsource(_render_crossbeam_uls_flexure_workspace)
    tree = ast.parse(source)
    stores: list[int] = []
    loads: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "construction_method":
            if isinstance(node.ctx, ast.Store):
                stores.append(node.lineno)
            elif isinstance(node.ctx, ast.Load):
                loads.append(node.lineno)
    assert stores, "construction_method must be initialized inside the Flexure workspace"
    assert loads, "construction_method should be used by the Flexure workspace"
    assert min(stores) < min(loads)


def test_segmental_station_dependent_phi_mn_uses_one_tendon_only_full_member_trace() -> None:
    state, segments = _mixed_30m_state()
    link = state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY]
    for row in link["tendon_station_profiles"]:
        station = float(row["Station s (m)"])
        row["fpe (MPa)"] = 1200.0 + 80.0 * (1.0 - abs(station - 15.0) / 15.0)
    state[CB_STATION_FORCE_CONTRACT_KEY] = default_station_force_contract(
        effective_prestress_link=link
    )

    preparation = build_crossbeam_uls_flexure_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_flexure(preparation)
    rows = pd.DataFrame(result["rows"])

    assert result["flexure_credit_basis"] == "TENDON-ONLY"
    assert result["development_zone_checks"] == 0
    assert set(rows["Ordinary rebar credit"].astype(str)) == {"TENDON-ONLY"}
    assert set(pd.to_numeric(rows["Ordinary bars credited"], errors="coerce").fillna(0).astype(int)) == {0}

    figure = _make_crossbeam_uls_flexure_figure(
        _crossbeam_uls_demand_dataframe(preparation),
        rows,
        segment_rows=segments,
        support_footprints=list(preparation.support_footprints),
        pt_end_zone_settings=preparation.pt_end_zone_settings,
        construction_method=str(state[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY]),
        member_length_m=preparation.member_length_m,
    )
    capacity_traces = [
        trace for trace in figure.data
        if str(getattr(trace, "name", "") or "").startswith("Adopted tendon-only φMn")
    ]
    assert len(capacity_traces) == 1
    trace = capacity_traces[0]
    xs = [float(value) for value in list(trace.x) if value is not None and math.isfinite(float(value))]
    ys = [float(value) for value in list(trace.y) if value is not None and math.isfinite(float(value))]
    assert xs and len(xs) == len(ys)
    assert xs == sorted(xs)
    assert min(xs) <= 1.0e-9
    assert max(xs) >= preparation.member_length_m - 1.0e-9
    assert all(value is not None for value in list(trace.x))

    # Every exact physical joint keeps both one-sided capacities at the same x,
    # allowing a vertical step when adjacent Segment sections differ without a gap.
    joint_rows = rows[rows["Location type"].astype(str) == "PHYSICAL SEGMENT JOINT"]
    for station, group in joint_rows.groupby("Station s (m)", sort=False):
        assert len(group.index) == 2
        assert sum(abs(value - float(station)) <= 1.0e-8 for value in xs) >= 2
