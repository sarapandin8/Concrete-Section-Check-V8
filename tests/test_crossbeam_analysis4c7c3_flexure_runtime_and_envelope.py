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


def test_segmental_station_dependent_phi_mn_envelope_solves_both_development_limits() -> None:
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

    boundary_rows = rows[rows["Location type"].astype(str) == "DEVELOPMENT BOUNDARY"]
    assert not boundary_rows.empty
    for (segment_id, station), group in boundary_rows.groupby(["Segment", "Station s (m)"], sort=False):
        assert set(group["Ordinary rebar credit"].astype(str)) == {"NO CREDIT", "FULL CREDIT"}
        assert set(group["Development region"].astype(str)) >= {
            "FULLY DEVELOPED INTERIOR"
        }

    figure = _make_crossbeam_uls_flexure_figure(
        _crossbeam_uls_demand_dataframe(preparation),
        rows,
        segment_rows=segments,
        support_footprints=list(preparation.support_footprints),
        pt_end_zone_settings=preparation.pt_end_zone_settings,
        construction_method=str(state[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY]),
        member_length_m=preparation.member_length_m,
    )
    capacity_traces = [trace for trace in figure.data if str(trace.name) == "Adopted φMn"]
    assert len(capacity_traces) == len(segments)

    trace_by_segment: dict[str, object] = {}
    for trace in capacity_traces:
        custom = [item for item in list(trace.customdata or []) if item is not None]
        assert custom
        trace_by_segment[str(custom[0][0])] = trace

    for (segment_id, station), _group in boundary_rows.groupby(["Segment", "Station s (m)"], sort=False):
        trace = trace_by_segment[str(segment_id)]
        xs = [
            float(value)
            for value in list(trace.x)
            if value is not None and math.isfinite(float(value))
        ]
        hits = sum(abs(value - float(station)) <= 1.0e-8 for value in xs)
        assert hits >= 2, (
            f"{segment_id} development boundary at s={station} must plot both binary phiMn limits "
            "at the same station so the Segment envelope has no artificial gap"
        )
