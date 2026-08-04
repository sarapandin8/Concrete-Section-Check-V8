from __future__ import annotations

import math

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.crossbeam_uls import (
    build_crossbeam_uls_flexure_preparation,
    run_crossbeam_uls_flexure,
)
from concrete_pmm_pro.analysis.crossbeam_uls_shear import (
    build_crossbeam_uls_shear_preparation,
    run_crossbeam_uls_shear,
)
from concrete_pmm_pro.analysis.crossbeam_uls_torsion import run_crossbeam_uls_torsion
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.project_geometry import CROSSBEAM_COLUMN_ROWS_KEY
from concrete_pmm_pro.crossbeam.rebar import (
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_DEFINITIONS_KEY,
    default_section_definitions,
)
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY,
    CB_STATION_FORCE_CONTRACT_KEY,
    default_station_force_contract,
)
from concrete_pmm_pro.crossbeam.tendon import (
    TENDON_BOND_STATE_BONDED,
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import (
    CB_PROFILE_ROWS_KEY,
    CB_TENDON_SYSTEM_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.transverse import default_crossbeam_transverse_templates
from concrete_pmm_pro.ui.analysis_page import (
    _crossbeam_flexure_chart_rows,
    _crossbeam_flexure_region_trace_points,
    _crossbeam_shear_demand_plot_rows,
    _crossbeam_uls_demand_dataframe,
    _make_crossbeam_uls_flexure_figure,
    _make_crossbeam_uls_shear_figure,
    _make_crossbeam_uls_torsion_figure,
)


JOINTS = [4.5, 10.5, 15.0, 19.5, 25.5]


def _mixed_30m_state() -> tuple[dict[str, object], list[dict[str, object]]]:
    length_m = 30.0
    definitions = default_section_definitions()
    definitions_by_id = {str(row["Section ID"]): row for row in definitions}
    segment_data = [
        ("S1", 0.0, 4.5, "CB-S01", "Solid"),
        ("S2", 4.5, 10.5, "CB-H01", "Hollow"),
        ("S3", 10.5, 15.0, "CB-S01", "Solid"),
        ("S4", 15.0, 19.5, "CB-S01", "Solid"),
        ("S5", 19.5, 25.5, "CB-H01", "Hollow"),
        ("S6", 25.5, 30.0, "CB-S01", "Solid"),
    ]
    segments: list[dict[str, object]] = []
    for segment_id, start, end, section_id, role in segment_data:
        definition = definitions_by_id[section_id]
        segments.append(
            {
                "Segment": segment_id,
                "x_start_m": start,
                "x_end_m": end,
                "s_start (m)": start,
                "s_end (m)": end,
                "Section ID": section_id,
                "Section name": definition["Section name"],
                "Section role": role,
                "Preset family": definition["Preset family"],
            }
        )

    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    for template in transverse:
        if template.get("Applicable role") == "Hollow":
            template["Use outer torsion cage"] = True
            template["Torsion cage bar size"] = template["Bar size"]
            template["Torsion cage spacing mm"] = template["Spacing mm"]
            template["Torsion cage center offset mm"] = template["Center offset mm"]
            template["Torsion cage relationship"] = "Additional outer cage"
            template["Torsion cage closure"] = "Verified closed loop"
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)

    tendons = default_tendon_system_rows(3)
    for tendon in tendons:
        tendon["Bond state"] = TENDON_BOND_STATE_BONDED
    profile = default_tendon_profile_points(
        length_m,
        tendon_ids=[str(row["Tendon ID"]) for row in tendons],
        width_mm=2500.0,
        height_mm=1500.0,
    )
    link = {
        "ready": True,
        "source_id": "analysis3b-source",
        "contract_id": "analysis3b-contract",
        "average_total_loss_percent": 20.0,
        "effective_prestress_ratio_percent": 80.0,
        "average_effective_stress_mpa": 1300.0,
    }
    columns = []
    for index, station in enumerate((2.75, 15.0, 27.25), start=1):
        columns.append(
            {
                "Column ID": f"C{index}",
                "Station s (m)": station,
                "Shape": "Rectangular — Equal Chamfer 4 Corners",
                "Blong (mm)": 2000.0,
                "Btrans (mm)": 2000.0,
                "Corner (mm)": 200.0,
                "Diameter (mm)": 2000.0,
                "Height (m)": 10.0,
                "f'c (MPa)": 35.0,
            }
        )
    loads = []
    for station in range(0, 31, 2):
        loads.append(
            {
                "Active": True,
                "Station s (m)": float(station),
                "Check Point": "",
                "Case Name": "ULS-01",
                "P": 5000.0,
                "V2": 2000.0 - 125.0 * station,
                "T": 1000.0,
                "M3": max(0.0, 10000.0 - abs(15.0 - station) * 1000.0),
                "Note": "",
            }
        )
    state: dict[str, object] = {
        "crossbeam_ui1_length_m": length_m,
        "crossbeam_ui1_segment_layout_rows": segments,
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        CB_RB_TEMPLATE_ROWS_KEY: longitudinal,
        CB_RB_ZONE_ROWS_KEY: zones,
        CB_TR_TEMPLATE_ROWS_KEY: transverse,
        CB_TENDON_SYSTEM_ROWS_KEY: tendons,
        CB_PROFILE_ROWS_KEY: profile,
        CROSSBEAM_COLUMN_ROWS_KEY: columns,
        CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY: link,
        CB_STATION_FORCE_CONTRACT_KEY: default_station_force_contract(
            effective_prestress_link=link
        ),
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        "concrete_materials": default_concrete_materials(),
        "load_cases": [],
        "crossbeam_uls_loads_table": loads,
    }
    return state, segments


def test_all_five_physical_joints_have_two_one_sided_calculation_rows() -> None:
    state, _segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_shear_preparation(state)

    assert preparation.ready, preparation.errors
    joint_rows = [row for row in preparation.rows if row.generated_joint_side_check]
    assert len(joint_rows) == 10
    assert sorted({round(float(row.joint_station_m), 6) for row in joint_rows}) == JOINTS
    for station in JOINTS:
        rows = [row for row in joint_rows if float(row.joint_station_m) == pytest.approx(station)]
        assert {row.joint_side for row in rows} == {"L", "R"}
        assert len({row.segment_id for row in rows}) == 2

    shear = run_crossbeam_uls_shear(preparation)
    torsion = run_crossbeam_uls_torsion(preparation)
    assert shear["joint_review_count"] == 5
    assert torsion["joint_review_count"] == 5
    assert len(shear["joint_side_rows"]) == 10
    assert len(torsion["joint_side_rows"]) == 10

    # The Solid/Hollow J1 sides must retain their own actual capacities.
    shear_j1 = [row for row in shear["joint_side_rows"] if row["Joint station s (m)"] == pytest.approx(4.5)]
    torsion_j1 = [row for row in torsion["joint_side_rows"] if row["Joint station s (m)"] == pytest.approx(4.5)]
    assert len({round(float(row["φVn kN"]), 6) for row in shear_j1}) == 2
    assert len({round(float(row["phiTth kN-m"]), 6) for row in torsion_j1}) == 2


def test_shear_chart_splits_capacity_by_segment_and_plots_joint_side_values() -> None:
    state, segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_shear_preparation(state)
    result = run_crossbeam_uls_shear(preparation)
    rows = pd.DataFrame(result["rows"])
    guard = rows[rows["Location type"].astype(str) == "PHYSICAL SEGMENT JOINT"]
    support = rows[rows["Location type"].isin(["COLUMN FACE", "ACI h/2 CRITICAL SECTION"])]
    figure = _make_crossbeam_uls_shear_figure(
        _crossbeam_shear_demand_plot_rows(rows),
        rows,
        guard,
        support,
        list(result["support_footprints"]),
        segments,
    )

    capacity_traces = [trace for trace in figure.data if str(trace.name) in {"±φVn", "±φVc"}]
    assert capacity_traces
    for trace in capacity_traces:
        finite_x = [float(value) for value in list(trace.x) if value is not None and math.isfinite(float(value))]
        assert finite_x
        assert not any(min(finite_x) < joint < max(finite_x) for joint in JOINTS)

    traces = {str(trace.name): trace for trace in figure.data}
    assert len(list(traces["Joint s−/s+ demand"].x)) == 10
    assert len(list(traces["Joint-side φVn"].x)) == 20  # ± capacity for 10 one-sided rows
    assert len(list(traces["Joint-side φVc"].x)) == 20
    assert sum(str(trace.name) == "Physical joint — REVIEW" for trace in figure.data) == 5


def test_torsion_capacity_is_horizontal_per_segment_with_all_joint_sides_plotted() -> None:
    state, segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_shear_preparation(state)
    result = run_crossbeam_uls_torsion(preparation)
    rows = pd.DataFrame(result["rows"])
    figure = _make_crossbeam_uls_torsion_figure(
        rows,
        list(preparation.support_footprints),
        segments,
    )

    capacity_traces = [trace for trace in figure.data if str(trace.name) in {"±φTn", "±φTth"}]
    assert capacity_traces
    for trace in capacity_traces:
        finite_y = [float(value) for value in list(trace.y) if value is not None and math.isfinite(float(value))]
        assert finite_y
        assert len({round(value, 8) for value in finite_y}) == 1
        finite_x = [float(value) for value in list(trace.x) if value is not None and math.isfinite(float(value))]
        assert not any(min(finite_x) < joint < max(finite_x) for joint in JOINTS)

    traces = {str(trace.name): trace for trace in figure.data}
    assert len(list(traces["Joint s−/s+ demand"].x)) == 10
    assert len(list(traces["Joint-side φTth"].x)) == 20
    assert len(list(traces["Joint-side φTn"].x)) == 20
    assert sum(str(trace.name) == "Physical joint — REVIEW" for trace in figure.data) == 5


def test_torsion_demand_is_segment_owned_and_omitted_only_inside_supports() -> None:
    state, segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_shear_preparation(state)
    result = run_crossbeam_uls_torsion(preparation)
    rows = pd.DataFrame(result["rows"])
    figure = _make_crossbeam_uls_torsion_figure(
        rows,
        list(preparation.support_footprints),
        segments,
    )

    demand_traces = [trace for trace in figure.data if str(trace.name).startswith("Demand Tu")]
    assert demand_traces
    all_x = [
        round(float(value), 6)
        for trace in demand_traces
        for value in list(trace.x)
        if value is not None and math.isfinite(float(value))
    ]
    # Both adjacent Segment traces reach every physical joint except J3, which
    # lies inside the C2 support footprint and is intentionally omitted.
    for joint in [4.5, 10.5, 19.5, 25.5]:
        assert all_x.count(round(joint, 6)) >= 2
    assert round(15.0, 6) not in all_x

    for footprint in preparation.support_footprints:
        left = float(footprint["s_left (m)"])
        right = float(footprint["s_right (m)"])
        assert not any(left + 1.0e-8 < value < right - 1.0e-8 for value in all_x)


def test_flexure_capacity_is_one_clean_step_envelope_per_segment() -> None:
    state, segments = _mixed_30m_state()
    preparation = build_crossbeam_uls_flexure_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_flexure(preparation)
    result_df = pd.DataFrame(result["rows"])
    figure = _make_crossbeam_uls_flexure_figure(
        _crossbeam_uls_demand_dataframe(preparation),
        result_df,
        segment_rows=segments,
    )

    capacity_traces = [trace for trace in figure.data if str(trace.name) == "Adopted φMn"]
    assert len(capacity_traces) == len(segments)
    traced_by_segment: dict[str, object] = {}
    for trace in capacity_traces:
        finite_x = [float(value) for value in list(trace.x) if value is not None and math.isfinite(float(value))]
        finite_y = [float(value) for value in list(trace.y) if value is not None and math.isfinite(float(value))]
        assert finite_x and finite_y
        assert not any(min(finite_x) < joint < max(finite_x) for joint in JOINTS)
        custom = [item for item in list(trace.customdata or []) if item is not None]
        segment_id = str(custom[0][0])
        traced_by_segment[segment_id] = trace

        # In this symmetric benchmark each capacity region is constant. Any
        # positive horizontal run must therefore remain level; capacity changes
        # occur only at duplicate-x vertical steps.
        raw_x = list(trace.x)
        raw_y = list(trace.y)
        for x0, x1, y0, y1 in zip(raw_x[:-1], raw_x[1:], raw_y[:-1], raw_y[1:]):
            if None in (x0, x1, y0, y1):
                continue
            if float(x1) > float(x0) + 1.0e-9:
                assert float(y1) == pytest.approx(float(y0), rel=1.0e-8, abs=1.0e-6)

    for segment in segments:
        segment_id = str(segment["Segment"])
        trace = traced_by_segment[segment_id]
        finite_x = [float(value) for value in list(trace.x) if value is not None]
        assert min(finite_x) == pytest.approx(float(segment["x_start_m"]))
        assert max(finite_x) == pytest.approx(float(segment["x_end_m"]))

    joint_markers = [trace for trace in figure.data if str(trace.name) == "Joint one-sided φMn"]
    assert len(joint_markers) == 1
    assert len(list(joint_markers[0].x)) == 10
    symbols = list(joint_markers[0].marker.symbol)
    assert symbols.count("triangle-left-open") == 5
    assert symbols.count("triangle-right-open") == 5

    no_credit_legend = [trace for trace in figure.data if str(trace.name) == "No rebar credit zone"]
    assert len(no_credit_legend) == 1
    amber_bands = [shape for shape in figure.layout.shapes if str(shape.type) == "rect"]
    assert len(amber_bands) >= 12

    title = str(figure.layout.title.text)
    assert "direct Crossbeam P–M3" in title
    assert "adopted capacity envelope" in title

def test_flexure_credit_region_trace_does_not_invent_boundary_values_when_capacity_varies() -> None:
    rows = pd.DataFrame(
        [
            {
                "__x_m": 6.0,
                "__capacity_kNm": 17000.0,
                "__plot_sign": 1.0,
                "__demand_kNm": 2000.0,
                "Segment": "S2",
                "Case": "ULS-01",
                "Section ID": "CB-H01",
                "Ordinary rebar credit": "FULL CREDIT",
                "Development region": "FULLY DEVELOPED INTERIOR",
                "Check Point": "",
            },
            {
                "__x_m": 10.0,
                "__capacity_kNm": 16500.0,
                "__plot_sign": 1.0,
                "__demand_kNm": 7000.0,
                "Segment": "S2",
                "Case": "ULS-01",
                "Section ID": "CB-H01",
                "Ordinary rebar credit": "FULL CREDIT",
                "Development region": "FULLY DEVELOPED INTERIOR",
                "Check Point": "",
            },
        ]
    )
    x_values, y_values, custom = _crossbeam_flexure_region_trace_points(
        rows, region_start_m=4.5, region_end_m=10.5
    )
    assert x_values == [6.0, 10.0]
    assert y_values == [17000.0, 16500.0]
    assert all(item[6] == "SOLVED CHECK" for item in custom)
