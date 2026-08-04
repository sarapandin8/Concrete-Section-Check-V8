from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.analysis.crossbeam_uls_torsion import (
    CROSSBEAM_ULS_TORSION_RESULT_HASH_KEY,
    CROSSBEAM_ULS_TORSION_RESULT_KEY,
    _minimum_longitudinal_area,
    _minimum_transverse_per_s,
    _torsion_thresholds,
    build_crossbeam_uls_torsion_preparation,
    run_crossbeam_uls_torsion,
)
from concrete_pmm_pro.crossbeam.rebar import default_crossbeam_rebar_zones
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_DEFINITIONS_KEY,
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui.analysis_page import _make_crossbeam_uls_torsion_figure
from tests.test_crossbeam_analysis2_uls_shear import _ready_state


def _set_torsion(state: dict[str, object], value_knm: float) -> None:
    for row in state["crossbeam_uls_loads_table"]:
        row["T"] = float(value_knm)


def _mixed_state(*, torsion_knm: float) -> dict[str, object]:
    state = _ready_state(include_guard_rows=False)
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), definitions
    )
    # Preserve a Solid support footprint at the right column while retaining
    # the S2/S4 Hollow interior regions for Torsion geometry checks.
    solid = definitions[0]
    for segment in segments:
        if segment["Segment"] == "S6":
            segment.update(
                {
                    "Section ID": solid["Section ID"],
                    "Section role": "Solid",
                    "Section name": solid["Section name"],
                    "Section preset key": solid["Preset key"],
                    "Section type / preset": solid["Preset family"],
                }
            )
    state[CB_SECLIB_DEFINITIONS_KEY] = definitions
    state["crossbeam_ui1_segment_layout_rows"] = segments
    state[CB_RB_ZONE_ROWS_KEY] = default_crossbeam_rebar_zones(
        segments,
        state[CB_RB_TEMPLATE_ROWS_KEY],
        state[CB_TR_TEMPLATE_ROWS_KEY],
    )
    # ANALYSIS4C1: Hollow torsion capacity is available only from an explicit
    # engineer-defined outer closed cage.  This fixture opts in deliberately;
    # legacy/default Hollow templates remain LAYOUT REQUIRED.
    for template in state[CB_TR_TEMPLATE_ROWS_KEY]:
        if template.get("Applicable role") == "Hollow":
            template["Use outer torsion cage"] = True
            template["Torsion cage bar size"] = template["Bar size"]
            template["Torsion cage spacing mm"] = template["Spacing mm"]
            template["Torsion cage center offset mm"] = template["Center offset mm"]
            template["Torsion cage relationship"] = "Additional outer cage"
            template["Torsion cage closure"] = "Verified closed loop"
    _set_torsion(state, torsion_knm)
    return state


def test_torsion_preparation_reuses_accepted_station_and_support_contract() -> None:
    state = _ready_state()
    preparation = build_crossbeam_uls_torsion_preparation(state)

    assert preparation.ready, preparation.errors
    assert len(preparation.derived_support_rows) == 6
    assert len(preparation.rows) == 15
    assert sum(row.generated_support_check for row in preparation.rows) == 6
    assert any(row.location_type == "PHYSICAL SEGMENT JOINT" for row in preparation.rows)
    rebuilt = build_crossbeam_uls_torsion_preparation(state)
    assert rebuilt.fingerprint == preparation.fingerprint


def test_aci_threshold_formulas_distinguish_solid_and_hollow_prestressed_sections() -> None:
    common = dict(
        fc_mpa=45.0,
        ag_mm2=2_000_000.0,
        acp_mm2=3_000_000.0,
        pcp_mm=8_000.0,
        fpc_mpa=8.0,
    )
    solid = _torsion_thresholds(**common, is_hollow=False)
    hollow = _torsion_thresholds(**common, is_hollow=True)

    sqrt_fc = min(math.sqrt(45.0), 8.3)
    factor = math.sqrt(1.0 + 8.0 / (0.33 * sqrt_fc))
    expected_solid = 0.083 * sqrt_fc * 3_000_000.0**2 / 8_000.0 * factor
    expected_hollow = 0.083 * sqrt_fc * 2_000_000.0**2 / 8_000.0 * factor
    expected_tcr = 0.33 * sqrt_fc * 3_000_000.0**2 / 8_000.0 * factor

    assert solid["Tth_Nmm"] == pytest.approx(expected_solid)
    assert hollow["Tth_Nmm"] == pytest.approx(expected_hollow)
    assert solid["Tcr_Nmm"] == pytest.approx(expected_tcr)
    assert hollow["Tcr_Nmm"] == pytest.approx(expected_tcr)
    assert solid["phiTth_Nmm"] == pytest.approx(0.75 * expected_solid)




def test_aci_minimum_torsion_reinforcement_equations_follow_9_6_4() -> None:
    fc = 45.0
    bw = 600.0
    fyt = 390.0
    acp = 3_750_000.0
    fy = 390.0
    at_per_s = 0.75
    ph = 8_200.0

    transverse = _minimum_transverse_per_s(fc_mpa=fc, bw_mm=bw, fyt_mpa=fyt)
    expected_transverse = max(0.062 * math.sqrt(fc) * bw / fyt, 0.35 * bw / fyt)
    assert transverse == pytest.approx(expected_transverse)

    minimum, route_a, route_b = _minimum_longitudinal_area(
        fc_mpa=fc,
        acp_mm2=acp,
        fy_mpa=fy,
        at_per_s=at_per_s,
        ph_mm=ph,
        bw_mm=bw,
        fyt_mpa=fyt,
    )
    expected_a = 0.42 * math.sqrt(fc) * acp / fy - at_per_s * ph * fyt / fy
    expected_b = (
        0.42 * math.sqrt(fc) * acp / fy
        - (0.175 * bw / fyt) * ph * fyt / fy
    )
    assert route_a == pytest.approx(expected_a)
    assert route_b == pytest.approx(expected_b)
    assert minimum == pytest.approx(max(min(expected_a, expected_b), 0.0))


def test_prestress_dominance_gate_selects_aci_theta_route() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 1_500.0)
    result = run_crossbeam_uls_torsion(build_crossbeam_uls_torsion_preparation(state))
    design_rows = [row for row in result["rows"] if row["Threshold status"] == "DESIGN REQUIRED"]

    assert design_rows
    for row in design_rows:
        expected = 37.5 if float(row["Prestress ratio"]) >= 0.4 else 45.0
        assert float(row["theta deg"]) == pytest.approx(expected)

def test_below_threshold_route_does_not_require_a_closed_torsion_cage() -> None:
    state = _ready_state(include_guard_rows=False)
    for template in state[CB_TR_TEMPLATE_ROWS_KEY]:
        template["Closed cage"] = False
        template["Credit inside segment"] = False
    _set_torsion(state, 45.0)

    result = run_crossbeam_uls_torsion(build_crossbeam_uls_torsion_preparation(state))

    assert result["status"] == "REVIEW"
    assert result["sectional_status"] == "BELOW THRESHOLD"
    assert result["combined_review_required"] is False
    assert all(row["Status"] == "BELOW THRESHOLD" for row in result["rows"])
    assert all(math.isnan(float(row["phiTn kN-m"])) for row in result["rows"])
    assert all(row["Threshold D/C value"] < 1.0 for row in result["rows"])


def test_design_required_component_can_pass_but_overall_remains_review_until_combined_vt() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 1_500.0)

    result = run_crossbeam_uls_torsion(build_crossbeam_uls_torsion_preparation(state))
    governing = result["sectional_governing_row"]

    assert result["sectional_status"] == "PASS"
    assert result["status"] == "REVIEW"
    assert result["combined_review_required"] is True
    assert result["design_required_checks"] > 0
    assert governing["Threshold status"] == "DESIGN REQUIRED"
    assert governing["Status"] == "PASS"
    assert math.isfinite(float(governing["phiTn kN-m"]))
    assert float(governing["Strength D/C value"]) < 1.0
    assert float(governing["Governing D/C value"]) < 1.0
    assert "Combined V+T" in result["scope"]


def test_larger_torsion_demand_produces_component_failure() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 5_000.0)

    result = run_crossbeam_uls_torsion(build_crossbeam_uls_torsion_preparation(state))

    assert result["status"] == "FAIL"
    assert result["sectional_status"] == "FAIL"
    assert any(row["Status"] == "FAIL" for row in result["rows"])
    assert max(
        float(row["Governing D/C value"])
        for row in result["rows"]
        if math.isfinite(float(row["Governing D/C value"]))
    ) > 1.0


def test_design_required_without_closed_cage_reports_layout_required_not_false_pass() -> None:
    state = _ready_state(include_guard_rows=False)
    _set_torsion(state, 5_000.0)
    for template in state[CB_TR_TEMPLATE_ROWS_KEY]:
        template["Closed cage"] = False

    result = run_crossbeam_uls_torsion(build_crossbeam_uls_torsion_preparation(state))

    assert result["sectional_status"] == "REVIEW"
    assert result["status"] == "REVIEW"
    assert all(row["Status"] == "LAYOUT REQUIRED" for row in result["rows"])
    assert all("not confirmed as a closed torsion cage" in row["Notes"] for row in result["rows"])


def test_physical_joint_review_is_separate_from_sectional_torsion_result() -> None:
    state = _ready_state(include_guard_rows=True)
    _set_torsion(state, 1_500.0)

    result = run_crossbeam_uls_torsion(build_crossbeam_uls_torsion_preparation(state))

    assert result["sectional_status"] == "PASS"
    assert result["status"] == "REVIEW"
    assert result["joint_review_count"] == 2
    joint = next(row for row in result["rows"] if row["Location type"] == "PHYSICAL SEGMENT JOINT")
    assert joint["Status"] == "REVIEW"
    assert joint["Detailing status"] == "NOT CHECKED"
    assert math.isnan(float(joint["phiTn kN-m"]))
    assert result["sectional_governing_row"]["Location type"] != "PHYSICAL SEGMENT JOINT"


def test_hollow_section_uses_local_wall_limit_and_keeps_piecewise_cage_review_visible() -> None:
    state = _mixed_state(torsion_knm=500.0)
    result = run_crossbeam_uls_torsion(build_crossbeam_uls_torsion_preparation(state))
    hollow = next(row for row in result["rows"] if row["Section ID"] == "CB-H01")

    assert hollow["Threshold status"] == "DESIGN REQUIRED"
    assert hollow["Hollow threshold route"] is True
    assert hollow["Hollow cage continuity review"] is False
    assert hollow["Hollow stress basis"] == "ACI 22.7.7.2 local minimum wall thickness"
    assert hollow["Hollow wall thickness mm"] < hollow["Aoh/ph mm"]
    assert "engineer-defined outer closed torsion-cage centerline" in hollow["Notes"]


def test_torsion_chart_has_single_signed_capacity_and_threshold_legend_entries() -> None:
    state = _ready_state(include_guard_rows=True)
    _set_torsion(state, 1_500.0)
    preparation = build_crossbeam_uls_torsion_preparation(state)
    result = run_crossbeam_uls_torsion(preparation)
    figure = _make_crossbeam_uls_torsion_figure(
        pd.DataFrame(result["rows"]), list(preparation.support_footprints)
    )
    names = [str(trace.name) for trace in figure.data if trace.showlegend is not False]

    assert names.count("±φTn") == 1
    assert names.count("±φTth") == 1
    assert names.count("Support-face screen") == 1
    assert names.count("ACI h/2 check") == 1
    assert names.count("Physical joint — REVIEW") == 1
    assert names.count("Max |Tu|") == 1
    assert names.count("Gov. torsional-strength D/C") == 1
    assert "Gov. Tu/φTn" not in names
    assert "Governing demand" not in names
    assert "capacity curves planned" not in str(figure.layout.title.text)
    dotted_blue_lines = [
        shape
        for shape in list(figure.layout.shapes or [])
        if getattr(getattr(shape, "line", None), "dash", None) == "dot"
        and "59, 130, 246" in str(getattr(getattr(shape, "line", None), "color", ""))
    ]
    assert dotted_blue_lines


def test_torsion_chart_plots_threshold_for_below_threshold_solid_sections_and_fits_scale() -> None:
    state = _mixed_state(torsion_knm=1_000.0)
    preparation = build_crossbeam_uls_torsion_preparation(state)
    result = run_crossbeam_uls_torsion(preparation)
    rows = pd.DataFrame(result["rows"])
    figure = _make_crossbeam_uls_torsion_figure(
        rows, list(preparation.support_footprints)
    )

    positive_threshold = next(
        trace
        for trace in figure.data
        if str(trace.name) == "±φTth"
        and any(
            float(value) > 0.0
            for value in list(trace.y)
            if value is not None and math.isfinite(float(value))
        )
    )
    plotted_thresholds = {
        round(float(value), 6)
        for value in list(positive_threshold.y)
        if value is not None and math.isfinite(float(value)) and float(value) > 0.0
    }
    expected_thresholds = {
        round(float(value), 6)
        for value in pd.to_numeric(rows["phiTth kN-m"], errors="coerce").dropna()
        if math.isfinite(float(value)) and float(value) > 0.0
    }
    assert expected_thresholds.issubset(plotted_thresholds)

    finite_plot_values = []
    for column in ("T kN-m", "phiTth kN-m", "phiTn kN-m"):
        finite_plot_values.extend(
            abs(float(value))
            for value in pd.to_numeric(rows[column], errors="coerce").dropna()
            if math.isfinite(float(value))
        )
    y_range = list(figure.layout.yaxis.range)
    assert y_range[0] == pytest.approx(-y_range[1])
    assert y_range[1] >= 1.10 * max(finite_plot_values)


def test_crossbeam_uls_navigation_exposes_torsion_and_combined_vt() -> None:
    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")

    assert '["Flexure", "Shear", "Torsion", "Shear + Torsion"]' in source
    assert '_render_crossbeam_uls_torsion_workspace()' in source
    assert '_render_crossbeam_uls_combined_vt_workspace()' in source
    assert "CROSSBEAM_ULS_TORSION_RESULT_KEY" in source
    assert "CROSSBEAM_ULS_TORSION_RESULT_HASH_KEY" in source
