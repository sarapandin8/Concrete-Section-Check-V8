from __future__ import annotations

from pathlib import Path

import pandas as pd

from concrete_pmm_pro.core.concrete_materials import default_concrete_materials
from concrete_pmm_pro.crossbeam.construction_stage import (
    COLUMN_SHAPE_RECT_CHAMFER,
    canonical_column_stage_rows,
    column_loss_evaluation_regions,
    column_support_footprint_summary,
    default_column_stage_rows,
)
from concrete_pmm_pro.crossbeam.later_permanent_response import _route_candidates
from concrete_pmm_pro.crossbeam.lightweight_elastic_shortening import (
    _bonded_fcgp_route,
    _column_joint_equilibrium_audit,
)
from concrete_pmm_pro.crossbeam.section_library import default_section_definitions
from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    _manual_benchmark_model,
    build_crossbeam_linear_stage_model,
    solve_linear_frame,
)
from concrete_pmm_pro.crossbeam.tendon import default_tendon_profile_points
from concrete_pmm_pro.ui.crossbeam_pages import (
    CB_EFFECTIVE_FEA_ADOPTION_TOKEN_KEY,
    CB_EFFECTIVE_FEA_TD_ADOPTION_KEY,
    CB_PTL_LIGHTWEIGHT_ES_RESULT_KEY,
    CB_PTL_TIME_DEPENDENT_RESULT_KEY,
    _column_rows_from_batched_form,
    _ptloss3b1_column_summary_editor_rows,
    _invalidate_crossbeam_support_dependent_state,
)
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_COLUMN_ROWS_KEY
from concrete_pmm_pro.state.dirty_state import input_group_hashes
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY,
    CB_STATION_FORCE_CONTRACT_KEY,
    CB_STATION_FORCE_VALIDATION_KEY,
)


def _columns(stations: list[float]) -> list[dict]:
    return [
        {
            "Column ID": f"C{index}",
            "Station s (m)": station,
            "Height (m)": 10.0,
            "Shape": COLUMN_SHAPE_RECT_CHAMFER,
            "Btrans (mm)": 2000.0,
            "Blong (mm)": 2000.0,
            "Corner (mm)": 200.0,
            "Diameter (mm)": 2000.0,
            "f'c (MPa)": 35.0,
        }
        for index, station in enumerate(stations, start=1)
    ]


def _full_solid_segment(length_m: float) -> list[dict]:
    return [
        {
            "Segment": "S1",
            "x_start_m": 0.0,
            "x_end_m": length_m,
            "Section ID": "CB-S01",
            "Section role": "Solid",
        }
    ]


def test_supportqa1_batched_column_form_preserves_four_rows_and_sorts_once() -> None:
    fallback = _columns([1.5, 18.5])
    summary = pd.DataFrame(
        [
            {
                "_Source Index": 0,
                "Column ID": "C1",
                "Station s (m)": 1.5,
                "Column Height (m)": 10.0,
                "Shape": COLUMN_SHAPE_RECT_CHAMFER,
                "f'c (MPa)": 35.0,
            },
            {
                "_Source Index": 1,
                "Column ID": "C4",
                "Station s (m)": 18.5,
                "Column Height (m)": 10.0,
                "Shape": COLUMN_SHAPE_RECT_CHAMFER,
                "f'c (MPa)": 35.0,
            },
            {
                "_Source Index": None,
                "Column ID": "C2",
                "Station s (m)": 7.0,
                "Column Height (m)": 9.0,
                "Shape": COLUMN_SHAPE_RECT_CHAMFER,
                "f'c (MPa)": 40.0,
            },
            {
                "_Source Index": None,
                "Column ID": "C3",
                "Station s (m)": 13.0,
                "Column Height (m)": 11.0,
                "Shape": COLUMN_SHAPE_RECT_CHAMFER,
                "f'c (MPa)": 35.0,
            },
        ]
    )
    geometry = {
        COLUMN_SHAPE_RECT_CHAMFER: pd.DataFrame(
            [
                {
                    "_Source Index": 0,
                    "Column ID": "C1",
                    "Btrans (mm)": 2100.0,
                    "Blong (mm)": 2200.0,
                    "Chamfer c (mm)": 150.0,
                },
                {
                    "_Source Index": 1,
                    "Column ID": "C4",
                    "Btrans (mm)": 2300.0,
                    "Blong (mm)": 2400.0,
                    "Chamfer c (mm)": 175.0,
                },
            ]
        )
    }

    rows = _column_rows_from_batched_form(
        summary_payload=summary,
        geometry_payloads=geometry,
        fallback_rows=fallback,
        length_m=20.0,
    )

    assert [row["Column ID"] for row in rows] == ["C1", "C2", "C3", "C4"]
    assert [row["Station s (m)"] for row in rows] == [1.5, 7.0, 13.0, 18.5]
    assert rows[0]["Blong (mm)"] == 2200.0
    assert rows[-1]["Btrans (mm)"] == 2300.0


def test_supportqa1_batched_column_form_deletes_selected_source_rows() -> None:
    fallback = _columns([1.5, 7.0, 13.0, 18.5])
    summary = pd.DataFrame(
        [
            {
                "_Source Index": index,
                "Column ID": row["Column ID"],
                "Station s (m)": row["Station s (m)"],
                "Column Height (m)": row["Height (m)"],
                "Shape": row["Shape"],
                "f'c (MPa)": row["f'c (MPa)"],
            }
            for index, row in enumerate(fallback)
        ]
    )

    rows = _column_rows_from_batched_form(
        summary_payload=summary,
        geometry_payloads={},
        fallback_rows=fallback,
        length_m=20.0,
        delete_source_indices={1, 2},
    )

    assert [row["Column ID"] for row in rows] == ["C1", "C4"]
    assert [row["Station s (m)"] for row in rows] == [1.5, 18.5]


def test_supportqa1_batched_column_form_returns_empty_for_delete_all_gate() -> None:
    fallback = _columns([1.5, 18.5])
    summary = pd.DataFrame(
        [
            {
                "_Source Index": index,
                "Column ID": row["Column ID"],
                "Station s (m)": row["Station s (m)"],
                "Column Height (m)": row["Height (m)"],
                "Shape": row["Shape"],
                "f'c (MPa)": row["f'c (MPa)"],
            }
            for index, row in enumerate(fallback)
        ]
    )

    rows = _column_rows_from_batched_form(
        summary_payload=summary,
        geometry_payloads={},
        fallback_rows=fallback,
        length_m=20.0,
        delete_source_indices={0, 1},
    )

    assert rows == []


def test_supportqa1_checkbox_delete_removes_checked_rows():
    fallback = canonical_column_stage_rows(default_column_stage_rows(20.0), length_m=20.0)
    summary = _ptloss3b1_column_summary_editor_rows(fallback)
    summary[1]["Delete"] = True

    rows = _column_rows_from_batched_form(
        summary_payload=summary,
        geometry_payloads={},
        fallback_rows=fallback,
        length_m=20.0,
        delete_checked_rows=True,
    )

    assert len(rows) == len(fallback) - 1
    assert fallback[1]["Column ID"] not in {row["Column ID"] for row in rows}


def test_supportqa1_editor_is_batched_in_a_form_without_per_cell_callbacks() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    block = source.split("def render_crossbeam_construction_support_source_workspace", 1)[1].split(
        "def _editor_bool", 1
    )[0]
    assert "with st.form(" in block
    assert "Apply Column / Support Layout" in block
    assert 'CheckboxColumn(\n                        "Delete"' in block
    assert '"Delete checked row(s)"' in block
    assert "Column row(s) to delete" not in block
    assert "on_change=_commit_ptloss3b1_column_summary_editor" not in block
    assert "on_change=_commit_ptloss3b1_column_geometry_editor" not in block
    assert "typing does not rebuild" in block
    assert "enforce_support_footprint=True" in source


def test_supportqa1_four_column_solid_model_is_ready_and_uses_all_columns() -> None:
    length_m = 20.0
    definitions = default_section_definitions()
    profile = default_tendon_profile_points(
        length_m,
        tendon_ids=["T1"],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    model = build_crossbeam_linear_stage_model(
        length_m=length_m,
        segment_rows=_full_solid_segment(length_m),
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=_columns([1.5, 7.0, 13.0, 18.5]),
        profile_rows=profile,
        enforce_support_footprint=True,
    )

    assert model["ready"] is True
    assert model["support_footprint_gate"] == "ENFORCED"
    assert model["support_footprint_qa"]["ready"] is True
    assert sum(element["kind"] == "column" for element in model["elements"]) == 4
    assert [row["Column ID"] for row in model["column_sources"]] == ["C1", "C2", "C3", "C4"]


def test_supportqa1_hollow_support_footprint_hard_blocks_loss_model() -> None:
    length_m = 20.0
    definitions = default_section_definitions()
    profile = default_tendon_profile_points(
        length_m,
        tendon_ids=["T1"],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    segments = [
        {
            "Segment": "S1",
            "x_start_m": 0.0,
            "x_end_m": 10.0,
            "Section ID": "CB-S01",
            "Section role": "Solid",
        },
        {
            "Segment": "S2",
            "x_start_m": 10.0,
            "x_end_m": 20.0,
            "Section ID": "CB-H01",
            "Section role": "Hollow",
        },
    ]
    model = build_crossbeam_linear_stage_model(
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=_columns([1.5, 18.5]),
        profile_rows=profile,
        enforce_support_footprint=True,
    )

    assert model["ready"] is False
    assert model["support_footprint_qa"]["ready"] is False
    assert any("C2 support footprint" in issue for issue in model["issues"])
    assert any("Hollow" in issue for issue in model["issues"])


def test_supportqa1_bonded_route_evaluates_every_column_and_bay_governing_fcgp() -> None:
    model = {
        "length_m": 20.0,
        "column_sources": _columns([1.5, 7.0, 13.0, 18.5]),
    }
    stress_rows = []
    for index, (station, fcgp) in enumerate(
        [(0.0, 1.0), (1.5, 3.0), (4.0, 4.0), (7.0, 5.0), (10.0, 9.0), (13.0, 6.0), (16.0, 7.0), (18.5, 8.0), (20.0, 2.0)],
        start=1,
    ):
        stress_rows.append(
            {
                "s (m)": station,
                "Element": f"B{index}",
                "f_cgp (MPa; compression +)": fcgp,
                "M (kN-m; sagging +)": 0.0,
            }
        )

    route = _bonded_fcgp_route(model, stress_rows)
    roles = {row["Evaluation role"] for row in route["evaluation_rows"]}

    assert route["fcgp_mpa"] == 9.0
    assert all(
        any(role.startswith(f"Column C{index} centerline —") for role in roles)
        for index in range(1, 5)
    )
    assert "Bay C1–C2 midpoint" in roles
    assert "Bay C2–C3 governing f_cgp" in roles
    assert "Bay C3–C4 midpoint" in roles
    assert "Left overhang to C1 governing f_cgp" in roles
    assert "Right overhang from C4 governing f_cgp" in roles
    assert route["coverage"]["ready"] is True
    assert route["coverage"]["physical_locations_evaluated"] == 9
    assert route["coverage"]["physical_locations_expected"] == 9


def test_supportqa1a_four_column_joint_equilibrium_closes_at_every_centerline() -> None:
    stations = [0.0, 1.5, 7.0, 13.0, 18.5, 20.0]
    column_stations = (1.5, 7.0, 13.0, 18.5)
    model = _manual_benchmark_model(
        stations_m=stations,
        column_stations_m=column_stations,
    )
    model["column_sources"] = _columns(list(column_stations))
    loaded_node = model["beam_node_by_station"][round(7.0, 9)]
    nodal_loads = {loaded_node: (25_000.0, -100_000.0, 50_000_000.0)}
    solution = solve_linear_frame(
        nodes=model["nodes"],
        elements=model["elements"],
        nodal_loads=nodal_loads,
        fixed_node_ids=model["fixed_node_ids"],
    )

    audit = _column_joint_equilibrium_audit(
        model=model,
        solution=solution,
        explicit_nodal_loads=nodal_loads,
    )

    assert audit["ready"] is True
    assert audit["count"] == audit["pass_count"] == 4
    assert max(row["Residual ratio"] for row in audit["rows"]) <= 1.0e-8


def test_supportqa1_later_response_route_uses_actual_delta_fcgp_not_max_m3() -> None:
    model = {
        "length_m": 20.0,
        "column_sources": _columns([1.5, 10.0, 18.5]),
    }
    rows = [
        {
            "Station x (m)": 1.5,
            "Internal Element": "B1",
            "End / Side": "Interior sample",
            "M3 (kN-m; sagging +)": 1000.0,
            "Δf_cd (MPa; compression +)": 1.0,
        },
        {
            "Station x (m)": 6.0,
            "Internal Element": "B2",
            "End / Side": "Interior sample",
            "M3 (kN-m; sagging +)": 100.0,
            "Δf_cd (MPa; compression +)": 7.0,
        },
        {
            "Station x (m)": 10.0,
            "Internal Element": "B3",
            "End / Side": "Interior sample",
            "M3 (kN-m; sagging +)": 50.0,
            "Δf_cd (MPa; compression +)": 2.0,
        },
        {
            "Station x (m)": 15.0,
            "Internal Element": "B4",
            "End / Side": "Interior sample",
            "M3 (kN-m; sagging +)": 900.0,
            "Δf_cd (MPa; compression +)": 8.0,
        },
        {
            "Station x (m)": 18.5,
            "Internal Element": "B5",
            "End / Side": "Interior sample",
            "M3 (kN-m; sagging +)": 1200.0,
            "Δf_cd (MPa; compression +)": 3.0,
        },
    ]

    candidates = _route_candidates(model, rows)
    by_role = {row["Evaluation role"]: row for row in candidates}

    assert by_role["Bay C1–C2 governing Δf_cd"]["Station x (m)"] == 6.0
    assert by_role["Bay C2–C3 governing Δf_cd"]["Station x (m)"] == 15.0
    assert by_role["Bay C2–C3 governing Δf_cd"]["Δf_cd (MPa; compression +)"] == 8.0


def test_supportqa1_regions_include_every_bay_and_nonzero_overhangs() -> None:
    regions = column_loss_evaluation_regions(
        _columns([1.5, 7.0, 13.0, 18.5]),
        length_m=20.0,
    )
    assert [row["Region type"] for row in regions] == [
        "OVERHANG",
        "BAY",
        "BAY",
        "BAY",
        "OVERHANG",
    ]


def test_supportqa1_column_change_invalidates_loss_handoff_and_load_contract() -> None:
    state = {
        CB_LOSS_ES_COLUMN_ROWS_KEY: _columns([1.5, 18.5]),
        CB_PTL_LIGHTWEIGHT_ES_RESULT_KEY: {"ready": True},
        CB_PTL_TIME_DEPENDENT_RESULT_KEY: {"ready": True},
        CB_EFFECTIVE_FEA_TD_ADOPTION_KEY: True,
        CB_EFFECTIVE_FEA_ADOPTION_TOKEN_KEY: "token",
        CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY: {
            "ready": True,
            "engineer_adopted_td": True,
            "source_id": "source",
            "contract_id": "contract",
        },
        CB_STATION_FORCE_CONTRACT_KEY: {
            "model_revision": "R1",
            "prestress_source_id": "source",
            "prestress_contract_id": "contract",
            "confirmed_final_prestress_applied_once": True,
            "confirmed_external_fea_secondary": True,
            "confirmed_uls_final_stage_response_basis": True,
            "confirmed_sls_service_response_basis": True,
            "confirmed_transfer_immediate_loss_basis": True,
            "confirmed_transfer_stage_response_basis": True,
        },
        CB_STATION_FORCE_VALIDATION_KEY: {"ready": True},
    }

    _invalidate_crossbeam_support_dependent_state(
        state,
        reason="Column layout changed.",
    )

    assert state[CB_PTL_LIGHTWEIGHT_ES_RESULT_KEY] == {"ready": True}
    assert state[CB_PTL_TIME_DEPENDENT_RESULT_KEY] == {"ready": True}
    assert state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY]["ready"] is False
    assert state[CB_EFFECTIVE_FEA_TD_ADOPTION_KEY] is False
    assert CB_EFFECTIVE_FEA_ADOPTION_TOKEN_KEY not in state
    contract = state[CB_STATION_FORCE_CONTRACT_KEY]
    assert contract["model_revision"] == ""
    assert contract["prestress_source_id"] == ""
    assert contract["confirmed_external_fea_secondary"] is False
    assert state[CB_STATION_FORCE_VALIDATION_KEY]["status"] == "STALE — SUPPORT LAYOUT CHANGED"


def test_supportqa1_column_rows_change_prestress_dirty_hash() -> None:
    before = {CB_LOSS_ES_COLUMN_ROWS_KEY: _columns([1.5, 18.5])}
    after = {CB_LOSS_ES_COLUMN_ROWS_KEY: _columns([1.5, 7.0, 13.0, 18.5])}

    assert input_group_hashes(before)["Prestress"] != input_group_hashes(after)["Prestress"]


def test_supportqa1_duplicate_column_ids_block_model_readiness() -> None:
    length_m = 20.0
    definitions = default_section_definitions()
    profile = default_tendon_profile_points(
        length_m,
        tendon_ids=["T1"],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    columns = _columns([1.5, 18.5])
    columns[1]["Column ID"] = "c1"
    model = build_crossbeam_linear_stage_model(
        length_m=length_m,
        segment_rows=_full_solid_segment(length_m),
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=columns,
        profile_rows=profile,
        enforce_support_footprint=True,
    )

    assert model["ready"] is False
    assert "Column IDs must be unique." in model["issues"]


def test_supportqa1_four_column_sample_layout_reports_three_hollow_conflicts() -> None:
    segments = [
        {"Segment": "S1", "x_start_m": 0.0, "x_end_m": 3.0, "Section role": "Solid"},
        {"Segment": "S2", "x_start_m": 3.0, "x_end_m": 7.0, "Section role": "Hollow"},
        {"Segment": "S3", "x_start_m": 7.0, "x_end_m": 10.0, "Section role": "Solid"},
        {"Segment": "S4", "x_start_m": 10.0, "x_end_m": 13.0, "Section role": "Hollow"},
        {"Segment": "S5", "x_start_m": 13.0, "x_end_m": 17.0, "Section role": "Solid"},
        {"Segment": "S6", "x_start_m": 17.0, "x_end_m": 20.0, "Section role": "Hollow"},
    ]
    summary = column_support_footprint_summary(
        _columns([1.5, 10.0, 12.5, 18.5]),
        segments,
        length_m=20.0,
    )

    assert summary["ready"] is False
    assert summary["compatible_count"] == 1
    assert sum(row["Status"] == "REVIEW" for row in summary["rows"]) == 3
    assert any("S4" in issue for issue in summary["issues"])
    assert any("S6" in issue for issue in summary["issues"])
