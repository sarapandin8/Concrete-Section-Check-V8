from __future__ import annotations

import math

import pytest

from concrete_pmm_pro.analysis.crossbeam_uls_shear import (
    CROSSBEAM_ULS_SHEAR_RESULT_HASH_KEY,
    CROSSBEAM_ULS_SHEAR_RESULT_KEY,
    _aci_prestressed_vc_n,
    _interpolate_support_demand,
    _minimum_av_per_s,
    _spacing_limits_mm,
    build_crossbeam_uls_shear_preparation,
    run_crossbeam_uls_shear,
)
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials
from concrete_pmm_pro.crossbeam.construction_stage import default_column_stage_rows
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
    migrate_segment_rows_to_library,
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
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows


def _ready_state(*, include_guard_rows: bool = True) -> dict[str, object]:
    length_m = 20.0
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(default_crossbeam_segment_rows(length_m), definitions)
    solid_id = str(definitions[0]["Section ID"])
    for segment in segments:
        segment["Section ID"] = solid_id
        segment["Section role"] = "Solid"

    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse)

    tendons = default_tendon_system_rows(3)
    for tendon in tendons:
        tendon["Bond state"] = TENDON_BOND_STATE_BONDED
    tendon_ids = [str(tendon["Tendon ID"]) for tendon in tendons]
    profile = default_tendon_profile_points(
        length_m,
        tendon_ids=tendon_ids,
        width_mm=2500.0,
        height_mm=1500.0,
    )
    link = {
        "ready": True,
        "source_id": "analysis2-ready-source",
        "contract_id": "analysis2-ready-contract",
        "average_total_loss_percent": 20.0,
        "effective_prestress_ratio_percent": 80.0,
        "average_effective_stress_mpa": 1300.0,
    }
    loads = []
    base_rows = [
        (0.0, 600.0, 0.0),
        (0.5, 550.0, 100.0),
        (1.5, 500.0, 200.0),
        (2.5, 450.0, 300.0),
        (5.0, 320.0, 2200.0),
        (9.0, 80.0, 4800.0),
        (11.0, -80.0, 4800.0),
        (15.0, -300.0, 2200.0),
        (17.5, -450.0, 300.0),
        (18.5, -500.0, 200.0),
        (19.5, -550.0, 100.0),
        (20.0, -600.0, 0.0),
    ]
    for station, shear, moment in base_rows:
        loads.append(
            {
                "Active": True,
                "Station s (m)": station,
                "Check Point": "",
                "Case Name": "ULS-01",
                "P": 5000.0,
                "V2": shear,
                "T": 45.0,
                "M3": moment,
                "Note": "support-face/h2 source row",
            }
        )
    if include_guard_rows:
        loads.append(
            {
                "Active": True,
                "Station s (m)": 10.0,
                "Check Point": "Joint",
                "Case Name": "ULS-01",
                "P": 5000.0,
                "V2": 0.0,
                "T": 50.0,
                "M3": 5000.0,
                "Note": "physical joint row",
            }
        )
    return {
        "crossbeam_ui1_length_m": length_m,
        "crossbeam_ui1_segment_layout_rows": segments,
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        CB_RB_TEMPLATE_ROWS_KEY: longitudinal,
        CB_RB_ZONE_ROWS_KEY: zones,
        CB_TR_TEMPLATE_ROWS_KEY: transverse,
        CB_TENDON_SYSTEM_ROWS_KEY: tendons,
        CB_PROFILE_ROWS_KEY: profile,
        CROSSBEAM_COLUMN_ROWS_KEY: default_column_stage_rows(length_m),
        CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY: link,
        CB_STATION_FORCE_CONTRACT_KEY: default_station_force_contract(
            effective_prestress_link=link
        ),
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: "Precast Segmental",
        "concrete_materials": default_concrete_materials(),
        "load_cases": [],
        "crossbeam_uls_loads_table": loads,
    }


def test_preparation_generates_conservative_column_face_and_h2_rows() -> None:
    state = _ready_state()
    preparation = build_crossbeam_uls_shear_preparation(state)

    assert preparation.ready, preparation.errors
    assert len(preparation.derived_support_rows) == 6
    assert len(preparation.rows) == 13

    interior = next(row for row in preparation.rows if row.station_m == pytest.approx(5.0))
    assert interior.source_p_kn == pytest.approx(5000.0)
    assert interior.source_v2_kn == pytest.approx(320.0)
    assert interior.source_t_knm == pytest.approx(45.0)
    assert interior.source_m3_knm == pytest.approx(2200.0)
    assert interior.location_type == "SEGMENT / ZONE INTERIOR"

    joint = next(row for row in preparation.rows if row.location_type == "PHYSICAL SEGMENT JOINT")
    assert joint.station_m == pytest.approx(10.0)
    assert joint.transverse_template is None

    support_rows = [
        row for row in preparation.rows
        if row.location_type in {"COLUMN FACE", "ACI h/2 CRITICAL SECTION"}
    ]
    assert len(support_rows) == 6
    assert all(row.transverse_template is not None for row in support_rows)
    assert not any(row.location_type == "COLUMN / SUPPORT D-REGION" for row in preparation.rows)

    c1_right_face = next(row for row in support_rows if row.check_point == "C1-R Face")
    c1_right_h2 = next(row for row in support_rows if row.check_point == "C1-R h/2")
    assert c1_right_face.station_m == pytest.approx(2.5)
    assert c1_right_face.source_v2_kn == pytest.approx(450.0)
    assert c1_right_h2.station_m == pytest.approx(3.25)
    assert c1_right_h2.source_v2_kn == pytest.approx(411.0)

    rebuilt = build_crossbeam_uls_shear_preparation(state)
    assert rebuilt.fingerprint == preparation.fingerprint
    assert [row.source_signature for row in rebuilt.rows] == [
        row.source_signature for row in preparation.rows
    ]


def test_run_checks_support_faces_and_h2_without_d_region_status_penalty() -> None:
    preparation = build_crossbeam_uls_shear_preparation(_ready_state())
    result = run_crossbeam_uls_shear(preparation)

    assert result["status"] == "REVIEW"  # physical segment joint remains a separate scope guard
    assert result["support_checks"] == 6
    assert result["station_checks"] == 13

    interior = next(row for row in result["rows"] if row["Station s (m)"] == pytest.approx(5.0))
    assert interior["Strength status"] == "PASS"
    assert interior["φ"] == pytest.approx(0.75)
    assert interior["φVn kN"] > 0.0
    assert interior["D/C value"] == pytest.approx(abs(interior["V2 kN"]) / interior["φVn kN"])

    support_rows = [
        row for row in result["rows"]
        if row["Location type"] in {"COLUMN FACE", "ACI h/2 CRITICAL SECTION"}
    ]
    assert len(support_rows) == 6
    assert all(row["Status"] == "PASS" for row in support_rows)
    assert all(math.isfinite(float(row["φVn kN"])) for row in support_rows)
    assert not any(row["Location type"] == "COLUMN / SUPPORT D-REGION" for row in result["rows"])

    joint = next(row for row in result["rows"] if row["Location type"] == "PHYSICAL SEGMENT JOINT")
    assert joint["Status"] == "REVIEW"
    assert joint["Capacity"] == "Joint shear transfer not checked"
    assert result["governing_row"]["Location type"] == "PHYSICAL SEGMENT JOINT"


def test_interior_and_support_checks_can_close_with_pass_without_double_counting_prestress() -> None:
    state = _ready_state(include_guard_rows=False)
    preparation = build_crossbeam_uls_shear_preparation(state)
    assert preparation.ready, preparation.errors

    result = run_crossbeam_uls_shear(preparation)
    assert result["status"] == "PASS"
    assert result["support_checks"] == 6
    assert all(row["Status"] == "PASS" for row in result["rows"])
    interior = next(row for row in result["rows"] if row["Station s (m)"] == pytest.approx(5.0))
    assert interior["P kN"] == pytest.approx(5000.0)
    assert interior["V2 kN"] == pytest.approx(320.0)
    assert "imported FEA demand remains unchanged" in interior["Notes"]


def test_missing_applied_column_layout_blocks_support_d_region_identification() -> None:
    state = _ready_state(include_guard_rows=False)
    state.pop(CROSSBEAM_COLUMN_ROWS_KEY)
    preparation = build_crossbeam_uls_shear_preparation(state)

    assert preparation.ready is False
    assert any("Column / Support Layout is missing" in message for message in preparation.errors)


def test_effective_prestress_applicability_gate_returns_review_not_false_pass() -> None:
    state = _ready_state(include_guard_rows=False)
    link = dict(state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY])
    link["average_effective_stress_mpa"] = 50.0
    state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY] = link
    state[CB_STATION_FORCE_CONTRACT_KEY] = default_station_force_contract(
        effective_prestress_link=link
    )

    preparation = build_crossbeam_uls_shear_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_shear(preparation)
    row = result["rows"][0]

    assert result["status"] == "REVIEW"
    assert row["Status"] == "REVIEW"
    assert math.isnan(float(row["φVn kN"]))
    assert "< 0.400" in row["Notes"]
    assert "refined Vci/Vcw" in row["Notes"]


def test_required_shear_reinforcement_without_sectional_credit_fails() -> None:
    state = _ready_state(include_guard_rows=False)
    next(row for row in state["crossbeam_uls_loads_table"] if row["Station s (m)"] == 5.0)["V2"] = 100_000.0
    for template in state[CB_TR_TEMPLATE_ROWS_KEY]:
        template["Credit inside segment"] = False

    preparation = build_crossbeam_uls_shear_preparation(state)
    assert preparation.ready, preparation.errors
    result = run_crossbeam_uls_shear(preparation)
    row = next(item for item in result["rows"] if item["Station s (m)"] == pytest.approx(5.0))

    assert result["status"] == "FAIL"
    assert row["Detailing status"] == "FAIL"
    assert "no sectional Av/s credit" in row["Notes"]


def test_zero_m3_evaluates_both_tension_faces_and_reports_governing_trial() -> None:
    state = _ready_state(include_guard_rows=False)
    next(row for row in state["crossbeam_uls_loads_table"] if row["Station s (m)"] == 5.0)["M3"] = 0.0

    preparation = build_crossbeam_uls_shear_preparation(state)
    assert preparation.ready, preparation.errors
    row = next(
        item for item in run_crossbeam_uls_shear(preparation)["rows"]
        if item["Station s (m)"] == pytest.approx(5.0)
    )

    assert "Zero M3" in row["Bending direction"]
    assert "both sagging and hogging" in row["Notes"]
    assert row["d mm"] >= 0.8 * row["h mm"]


def test_aci_vc_helper_matches_table_22_5_6_2_least_and_lower_bound() -> None:
    result = _aci_prestressed_vc_n(
        sqrt_fc_mpa_sqrt=math.sqrt(45.0),
        bw_mm=1000.0,
        d_mm=1200.0,
        dp_mm=1100.0,
        vu_n=800_000.0,
        mu_nmm=2_400_000_000.0,
    )
    sqrt_fc = math.sqrt(45.0)
    expected_a = (0.05 * sqrt_fc + 4.8 * 800_000.0 * 1100.0 / 2_400_000_000.0) * 1000.0 * 1200.0
    expected_b = (0.05 * sqrt_fc + 4.8) * 1000.0 * 1200.0
    expected_c = 0.42 * sqrt_fc * 1000.0 * 1200.0
    expected_lower = 0.17 * sqrt_fc * 1000.0 * 1200.0
    expected = max(min(expected_a, expected_b, expected_c), expected_lower)

    assert result["Vc_a_N"] == pytest.approx(expected_a)
    assert result["Vc_b_N"] == pytest.approx(expected_b)
    assert result["Vc_c_N"] == pytest.approx(expected_c)
    assert result["Vc_lower_N"] == pytest.approx(expected_lower)
    assert result["Vc_N"] == pytest.approx(expected)



def test_aci_minimum_web_reinforcement_uses_prestress_lesser_of_gate() -> None:
    fc = 45.0
    bw = 1000.0
    fyt = 390.0
    d = 1200.0
    aps_fpu = 12_000_000.0
    required, basis, base, prestress_specific = _minimum_av_per_s(
        fc_mpa=fc,
        bw_mm=bw,
        fyt_mpa=fyt,
        d_mm=d,
        aps_fpu_n=aps_fpu,
        prestress_dominant=True,
    )
    expected_base = max(0.062 * math.sqrt(fc) * bw / fyt, 0.35 * bw / fyt)
    expected_specific = aps_fpu / (80.0 * fyt * d) * math.sqrt(d / bw)

    assert base == pytest.approx(expected_base)
    assert prestress_specific == pytest.approx(expected_specific)
    assert required == pytest.approx(min(expected_base, expected_specific))
    assert "lesser-of" in basis


def test_aci_prestressed_spacing_limits_cover_both_required_vs_branches() -> None:
    low = _spacing_limits_mm(
        h_mm=1500.0,
        vs_required_n=100_000.0,
        fc_mpa=45.0,
        bw_mm=1000.0,
        d_mm=1200.0,
    )
    high = _spacing_limits_mm(
        h_mm=1500.0,
        vs_required_n=10_000_000.0,
        fc_mpa=45.0,
        bw_mm=1000.0,
        d_mm=1200.0,
    )

    assert low[0] == pytest.approx(600.0)
    assert low[1] == pytest.approx(600.0)
    assert "≤" in low[2]
    assert high[0] == pytest.approx(300.0)
    assert high[1] == pytest.approx(300.0)
    assert ">" in high[2]


def test_high_strength_vc_sqrt_limit_depends_on_minimum_web_reinforcement() -> None:
    state = _ready_state(include_guard_rows=False)
    state["concrete_materials"] = [
        material.model_copy(update={"fc_MPa": 80.0})
        if material.name == "C45_PRECAST"
        else material
        for material in state["concrete_materials"]
    ]

    credited = run_crossbeam_uls_shear(
        build_crossbeam_uls_shear_preparation(state)
    )["rows"][0]
    assert credited["√f'c actual"] == pytest.approx(math.sqrt(80.0))
    assert credited["√f'c used for Vc"] == pytest.approx(math.sqrt(80.0))

    for template in state[CB_TR_TEMPLATE_ROWS_KEY]:
        template["Credit inside segment"] = False
    uncredited = run_crossbeam_uls_shear(
        build_crossbeam_uls_shear_preparation(state)
    )["rows"][0]
    assert uncredited["√f'c actual"] == pytest.approx(math.sqrt(80.0))
    assert uncredited["√f'c used for Vc"] == pytest.approx(8.3)


def test_transverse_yield_strength_is_capped_at_420_mpa_for_shear() -> None:
    state = _ready_state(include_guard_rows=False)
    for template in state[CB_TR_TEMPLATE_ROWS_KEY]:
        template["Rebar material"] = "SD50"
        template["fy MPa"] = 490.0

    row = run_crossbeam_uls_shear(
        build_crossbeam_uls_shear_preparation(state)
    )["rows"][0]
    assert row["fyt input MPa"] == pytest.approx(490.0)
    assert row["fyt design MPa"] == pytest.approx(420.0)
    assert "capped at 420 MPa" in row["Notes"]

def test_analysis_page_exposes_crossbeam_flexure_and_shear_lazy_tabs() -> None:
    source = open("concrete_pmm_pro/ui/analysis_page.py", encoding="utf-8").read()
    block = source[source.index("def render_analysis_uls_pmm"):source.index("def render_analysis_sls_stress")]
    assert '"Flexure", "Shear"' in block
    assert "_render_crossbeam_uls_flexure_workspace()" in block
    assert "_render_crossbeam_uls_shear_workspace()" in block
    assert "crossbeam_uls_lazy_check" in block


def test_shear_cache_keys_are_crossbeam_namespaced() -> None:
    assert CROSSBEAM_ULS_SHEAR_RESULT_KEY.startswith("crossbeam_")
    assert CROSSBEAM_ULS_SHEAR_RESULT_HASH_KEY.startswith("crossbeam_")


def test_missing_exact_column_face_rows_use_one_sided_interpolation_and_limited_extrapolation() -> None:
    state = _ready_state(include_guard_rows=False)
    columns = default_column_stage_rows(20.0)
    columns[0]["Station s (m)"] = 2.75
    columns[1]["Station s (m)"] = 17.25
    state[CROSSBEAM_COLUMN_ROWS_KEY] = columns
    state["crossbeam_uls_loads_table"] = [
        {
            "Active": True,
            "Station s (m)": float(station),
            "Check Point": "",
            "Case Name": "ULS-01",
            "P": 5000.0,
            "V2": 2000.0 - 125.0 * float(station),
            "T": 40.0 + float(station),
            "M3": 500.0 * float(station),
            "Note": "2 m station grid",
        }
        for station in range(0, 21, 2)
    ]

    preparation = build_crossbeam_uls_shear_preparation(state)

    assert preparation.ready, preparation.errors
    assert len(preparation.derived_support_rows) == 8
    by_check = {str(row["Check Point"]): row for row in preparation.derived_support_rows}
    assert by_check["C1-L Face"]["__Demand source"] == "INTERPOLATED"
    assert by_check["C1-L Face"]["__Source station 1 (m)"] == pytest.approx(0.0)
    assert by_check["C1-L Face"]["__Source station 2 (m)"] == pytest.approx(2.0)
    assert by_check["C1-R Face"]["__Demand source"] == "EXTRAPOLATED"
    assert by_check["C1-R Face"]["__Extrapolation ratio"] == pytest.approx(0.125)
    assert by_check["C2-L Face"]["__Demand source"] == "EXTRAPOLATED"
    assert by_check["C2-L Face"]["__Extrapolation ratio"] == pytest.approx(0.125)
    assert by_check["C2-R Face"]["__Demand source"] == "INTERPOLATED"

    result = run_crossbeam_uls_shear(preparation)
    face = next(row for row in result["rows"] if row["Check Point"] == "C1-R Face")
    assert face["Demand source"] == "EXTRAPOLATED"
    assert face["Source station 1 (m)"] == pytest.approx(4.0)
    assert face["Source station 2 (m)"] == pytest.approx(6.0)
    assert face["Extrapolation ratio"] == pytest.approx(0.125)


def test_support_face_extrapolation_beyond_25_percent_blocks() -> None:
    state = _ready_state(include_guard_rows=False)
    columns = default_column_stage_rows(20.0)
    columns[0]["Station s (m)"] = 2.75
    columns[1]["Station s (m)"] = 17.25
    state[CROSSBEAM_COLUMN_ROWS_KEY] = columns
    state["crossbeam_uls_loads_table"] = [
        {
            "Active": True,
            "Station s (m)": float(station),
            "Check Point": "",
            "Case Name": "ULS-01",
            "P": 5000.0,
            "V2": 1000.0 - 20.0 * float(station),
            "T": 50.0,
            "M3": 100.0 * float(station),
            "Note": "sparse one-sided grid",
        }
        for station in (0, 2, 6, 8, 12, 14, 18, 20)
    ]

    preparation = build_crossbeam_uls_shear_preparation(state)

    assert preparation.ready is False
    assert any("exceeding the 25% safety limit" in message for message in preparation.errors)


def test_support_recovery_never_uses_rows_across_column_centerline() -> None:
    rows = [
        {"Active": True, "Station s (m)": 2.0, "Case Name": "ULS-01", "P": 1.0, "V2": 2.0, "T": 3.0, "M3": 4.0},
        {"Active": True, "Station s (m)": 4.0, "Case Name": "ULS-01", "P": 5.0, "V2": 6.0, "T": 7.0, "M3": 8.0},
    ]
    demand, error, _note = _interpolate_support_demand(
        case_rows=rows,
        target_m=3.75,
        support_center_m=2.75,
        side="right",
        support_footprints=[{"Center s (m)": 2.75}],
        tolerance=1.0e-7,
        station_label="Column Face",
    )

    assert demand is None
    assert error is not None
    assert "at least two active row-coupled" in error


def test_crossbeam_shear_chart_breaks_support_regions_and_dedupes_capacity_legends() -> None:
    import pandas as pd

    from concrete_pmm_pro.ui.analysis_page import (
        _crossbeam_shear_chart_rows,
        _crossbeam_shear_demand_plot_rows,
        _make_crossbeam_uls_shear_figure,
    )

    preparation = build_crossbeam_uls_shear_preparation(_ready_state(include_guard_rows=False))
    result = run_crossbeam_uls_shear(preparation)
    result_df = pd.DataFrame(result["rows"])
    capacity_df = _crossbeam_shear_chart_rows(result_df)
    demand_df = _crossbeam_shear_demand_plot_rows(result_df)
    guard_df = result_df[result_df["Location type"].astype(str) == "PHYSICAL SEGMENT JOINT"]
    support_df = result_df[
        result_df["Location type"].isin(["COLUMN FACE", "ACI h/2 CRITICAL SECTION"])
    ]

    figure = _make_crossbeam_uls_shear_figure(
        demand_df,
        capacity_df,
        guard_df,
        support_df,
        result["support_footprints"],
    )

    visible_legend_names = [trace.name for trace in figure.data if trace.showlegend is not False]
    assert visible_legend_names.count("±φVn") == 1
    assert visible_legend_names.count("±φVc") == 1
    assert "-φVn" not in visible_legend_names
    assert "Column Face check" in visible_legend_names
    assert "ACI h/2 check" in visible_legend_names

    demand_trace = next(trace for trace in figure.data if trace.name == "Demand Vu — ULS-01")
    assert None in list(demand_trace.x)
    assert None in list(demand_trace.y)
    assert sum(shape.type == "rect" for shape in figure.layout.shapes) == 2
    assert "support footprints omitted" in str(figure.layout.title.text)


def test_sectional_result_is_reported_independently_from_physical_joint_review() -> None:
    preparation = build_crossbeam_uls_shear_preparation(_ready_state())
    result = run_crossbeam_uls_shear(preparation)

    assert result["status"] == "REVIEW"
    assert result["sectional_status"] == "PASS"
    assert result["joint_review_count"] == 1
    assert result["sectional_checks"] == 12
    assert result["generated_support_checks"] == 6
    assert result["support_checks"] == 6
    assert result["support_joint_reviews"] == 0

    overall_governing = result["governing_row"]
    sectional_governing = result["sectional_governing_row"]
    assert overall_governing["Location type"] == "PHYSICAL SEGMENT JOINT"
    assert sectional_governing["Location type"] != "PHYSICAL SEGMENT JOINT"
    assert math.isfinite(float(sectional_governing["Governing D/C value"]))


def test_physical_joint_chart_uses_compact_marker_legend_not_vertical_text() -> None:
    import pandas as pd

    from concrete_pmm_pro.ui.analysis_page import (
        _crossbeam_shear_chart_rows,
        _crossbeam_shear_demand_plot_rows,
        _make_crossbeam_uls_shear_figure,
    )

    preparation = build_crossbeam_uls_shear_preparation(_ready_state())
    result = run_crossbeam_uls_shear(preparation)
    result_df = pd.DataFrame(result["rows"])
    capacity_df = _crossbeam_shear_chart_rows(result_df)
    demand_df = _crossbeam_shear_demand_plot_rows(result_df)
    guard_df = result_df[result_df["Location type"].astype(str) == "PHYSICAL SEGMENT JOINT"]
    support_df = result_df[
        result_df["Location type"].isin(["COLUMN FACE", "ACI h/2 CRITICAL SECTION"])
    ]

    figure = _make_crossbeam_uls_shear_figure(
        demand_df,
        capacity_df,
        guard_df,
        support_df,
        result["support_footprints"],
    )

    visible_legend_names = [trace.name for trace in figure.data if trace.showlegend is not False]
    assert "Physical joint — REVIEW" in visible_legend_names
    assert all(
        str(getattr(annotation, "text", "")) != "Physical joint — REVIEW"
        for annotation in list(figure.layout.annotations or [])
    )


def test_analysis2d_ui_copy_separates_sectional_result_from_joint_scope() -> None:
    from pathlib import Path

    source = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")
    start = source.index("def _render_crossbeam_uls_shear_workspace")
    end = source.index("def _crossbeam_transfer_demand_dataframe", start)
    workspace = source[start:end]

    assert '"title": "Sectional shear"' in workspace
    assert '"title": "Governing sectional D/C"' in workspace
    assert '"title": "Physical joint check"' in workspace
    assert '"title": "Axis mapping"' not in workspace
    assert "Column Face / h/2 checks" in workspace
    assert "stations inside applied Column / Support footprints are retained as REVIEW scope guards" not in workspace
