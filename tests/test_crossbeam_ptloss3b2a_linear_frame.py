from __future__ import annotations

import math
from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.anchorage_set import (
    anchorage_set_end_rows,
    anchorage_set_station_rows,
)
from concrete_pmm_pro.crossbeam.construction_stage import default_column_stage_rows
from concrete_pmm_pro.crossbeam.prestress_loss import (
    aashto_friction_wobble_station_rows,
    default_crossbeam_prestress_loss_settings,
)
from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    PTLOSS3B2A_PRESTRESS_CASE,
    PTLOSS3B2A_SELF_WEIGHT_CASE,
    build_crossbeam_linear_stage_model,
    frame_uniform_local_y_load,
    linear_stage_case_summary_rows,
    prestress_equivalent_nodal_loads,
    run_crossbeam_linear_stage_response,
    solve_linear_frame,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials


def test_ptloss3b2a_cantilever_kernel_matches_closed_form_tip_response() -> None:
    e_mpa = 30_000.0
    inertia_mm4 = 1.0e9
    area_mm2 = 1.0e5
    length_mm = 1_000.0
    tip_load_n = 1_000.0
    solution = solve_linear_frame(
        nodes=[
            {"id": 0, "x_mm": 0.0, "y_mm": 0.0},
            {"id": 1, "x_mm": length_mm, "y_mm": 0.0},
        ],
        elements=[
            {
                "id": "E1",
                "kind": "beam",
                "node_i": 0,
                "node_j": 1,
                "E_MPa": e_mpa,
                "A_mm2": area_mm2,
                "I_mm4": inertia_mm4,
            }
        ],
        nodal_loads={1: (0.0, -tip_load_n, 0.0)},
        fixed_node_ids=[0],
    )
    assert solution["status"] == "LINEAR QA READY"
    tip = solution["nodes"][1]
    assert tip["v_mm"] == pytest.approx(
        -tip_load_n * length_mm**3 / (3.0 * e_mpa * inertia_mm4),
        abs=1.0e-12,
    )
    assert tip["theta_rad"] == pytest.approx(
        -tip_load_n * length_mm**2 / (2.0 * e_mpa * inertia_mm4),
        abs=1.0e-12,
    )
    assert solution["nodes"][0]["reaction_fy_N"] == pytest.approx(tip_load_n)
    assert solution["nodes"][0]["reaction_moment_Nmm"] == pytest.approx(
        tip_load_n * length_mm
    )
    assert solution["equilibrium"]["max_residual_ratio"] < 1.0e-12


def test_ptloss3b2a_fixed_fixed_uniform_load_matches_classical_end_actions() -> None:
    length_mm = 10_000.0
    q_down_n_per_mm = -2.0
    solution = solve_linear_frame(
        nodes=[
            {"id": 0, "x_mm": 0.0, "y_mm": 0.0},
            {"id": 1, "x_mm": length_mm, "y_mm": 0.0},
        ],
        elements=[
            {
                "id": "E1",
                "kind": "beam",
                "node_i": 0,
                "node_j": 1,
                "E_MPa": 30_000.0,
                "A_mm2": 1.0e6,
                "I_mm4": 2.0e11,
            }
        ],
        uniform_local_y_by_element={"E1": q_down_n_per_mm},
        fixed_node_ids=[0, 1],
    )
    end = solution["elements"][0]["end_action_local"]
    w = abs(q_down_n_per_mm)
    assert end[1] == pytest.approx(w * length_mm / 2.0)
    assert end[4] == pytest.approx(w * length_mm / 2.0)
    assert end[2] == pytest.approx(w * length_mm**2 / 12.0)
    assert end[5] == pytest.approx(-w * length_mm**2 / 12.0)
    assert solution["equilibrium"]["max_residual_ratio"] < 1.0e-12


def _manual_tendon_model() -> dict:
    stations = [0.0, 5.0, 10.0]
    nodes = [
        {
            "id": index,
            "label": f"B@{station:.3f}",
            "kind": "beam",
            "station_m": station,
            "x_mm": station * 1000.0,
            "y_mm": 0.0,
        }
        for index, station in enumerate(stations)
    ]
    return {
        "ready": True,
        "length_m": 10.0,
        "stations_m": stations,
        "nodes": nodes,
        "beam_node_by_station": {station: index for index, station in enumerate(stations)},
        "ranges": [
            {"Region": "Z1", "start_m": 0.0, "end_m": 10.0, "section_id": "S1"}
        ],
        "section_sources": {
            "S1": {"centroid_from_top_mm": 750.0}
        },
    }


def test_ptloss3b2a_constant_tendon_equivalent_loads_are_globally_self_equilibrating() -> None:
    model = _manual_tendon_model()
    profile = [
        {"Tendon ID": "T1", "Point": "P1", "s (m)": 0.0, "dtop (mm)": 750.0},
        {"Tendon ID": "T1", "Point": "P2", "s (m)": 5.0, "dtop (mm)": 1000.0},
        {"Tendon ID": "T1", "Point": "P3", "s (m)": 10.0, "dtop (mm)": 750.0},
    ]
    force = [
        {"Tendon ID": "T1", "Active": True, "s (m)": station, "P after anchorage set (kN)": 1000.0}
        for station in (0.0, 5.0, 10.0)
    ]
    source = prestress_equivalent_nodal_loads(
        model=model,
        profile_rows=profile,
        anchorage_station_rows=force,
    )
    assert source["ready"] is True
    fx = sum(values[0] for values in source["nodal_loads"].values())
    fy = sum(values[1] for values in source["nodal_loads"].values())
    moment = 0.0
    for node_id, values in source["nodal_loads"].items():
        node = model["nodes"][node_id]
        moment += values[2] + node["x_mm"] * values[1] - node["y_mm"] * values[0]
    assert fx == pytest.approx(0.0, abs=1.0e-6)
    assert fy == pytest.approx(0.0, abs=1.0e-6)
    assert moment == pytest.approx(0.0, abs=1.0e-3)


def _default_response_sources() -> tuple[dict, list[dict], list[dict]]:
    length_m = 20.0
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(length_m), definitions
    )
    system = default_tendon_system_rows(8)
    profile = default_tendon_profile_points(
        length_m,
        tendon_ids=[f"T{i}" for i in range(1, 9)],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    settings = default_crossbeam_prestress_loss_settings()
    friction = aashto_friction_wobble_station_rows(
        profile,
        system,
        length_m=length_m,
        internal_mu=settings["internal_mu"],
        internal_k_per_m=settings["internal_k_per_m"],
        external_deviator_mu=settings["external_deviator_mu"],
        external_inadvertent_angle_rad=settings["external_inadvertent_angle_rad"],
    )
    ends = anchorage_set_end_rows(
        friction,
        length_m=length_m,
        anchor_set_mm=settings["anchorage_set_mm"],
        ep_mpa=settings["ep_mpa"],
    )
    post_anchor = anchorage_set_station_rows(friction, ends, length_m=length_m)
    model = build_crossbeam_linear_stage_model(
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=default_column_stage_rows(length_m),
        profile_rows=profile,
    )
    return model, profile, post_anchor


def test_ptloss3b2a_default_crossbeam_builds_piecewise_frame_and_balances_all_cases() -> None:
    model, profile, post_anchor = _default_response_sources()
    assert model["ready"] is True
    assert sum(element["kind"] == "column" for element in model["elements"]) == 2
    assert sum(element["kind"] == "beam" for element in model["elements"]) >= 40
    result = run_crossbeam_linear_stage_response(
        model=model,
        profile_rows=profile,
        anchorage_station_rows=post_anchor,
    )
    assert result["ready"] is True
    assert result["fcgp_status"].startswith("LOCKED")
    assert "EXCLUDED" in result["temporary_support_status"]
    for solution in result["cases"].values():
        assert solution["status"] == "LINEAR QA READY"
        assert solution["equilibrium"]["max_residual_ratio"] < 1.0e-8
        assert solution["beam_response_rows"]
    rows = linear_stage_case_summary_rows(result)
    prestress_row = next(row for row in rows if row["Load case"] == PTLOSS3B2A_PRESTRESS_CASE)
    self_weight_row = next(row for row in rows if row["Load case"] == PTLOSS3B2A_SELF_WEIGHT_CASE)
    assert prestress_row["Max |N| (kN)"] > 1_000.0
    assert self_weight_row["Applied Fy (kN)"] < 0.0


def test_ptloss3b2a_uses_post_anchorage_force_values_not_fpj_restart() -> None:
    model = _manual_tendon_model()
    profile = [
        {"Tendon ID": "T1", "Point": "P1", "s (m)": 0.0, "dtop (mm)": 750.0},
        {"Tendon ID": "T1", "Point": "P2", "s (m)": 10.0, "dtop (mm)": 750.0},
    ]
    post_anchor = [
        {
            "Tendon ID": "T1",
            "Active": True,
            "s (m)": 0.0,
            "fpj (MPa)": 1395.0,
            "Pj (kN)": 3710.7,
            "P after anchorage set (kN)": 1000.0,
        },
        {
            "Tendon ID": "T1",
            "Active": True,
            "s (m)": 10.0,
            "fpj (MPa)": 1395.0,
            "Pj (kN)": 3710.7,
            "P after anchorage set (kN)": 1000.0,
        },
    ]
    source = prestress_equivalent_nodal_loads(
        model=model,
        profile_rows=profile,
        anchorage_station_rows=post_anchor,
    )
    first = source["audit_rows"][0]
    assert first["P_i (kN)"] == pytest.approx(1000.0)
    assert first["P_j (kN)"] == pytest.approx(1000.0)
    assert not math.isclose(first["P_i (kN)"], 3710.7)


def test_ptloss3b2a_ui_exposes_linear_qa_and_keeps_contact_fcgp_locked() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    elastic_block = source.split("with elastic_shortening_tab:", maxsplit=1)[1].split(
        "with time_dependent_tab:", maxsplit=1
    )[0]
    assert "PTLOSS3B2A1 — Stage-Modulus / Rigid-Offset Linear Response QA" in elastic_block
    assert "P after Anchorage Set + adopted tendon profile" in elastic_block
    assert "LINEAR QA / CONTACT LOCKED" in elastic_block
    assert "Continuous falsework contact is intentionally excluded" in elastic_block
    assert "f_cgp handoff" in elastic_block and '"value": "LOCKED"' in elastic_block
    assert "do not feed f_cgp, Elastic Shortening, Pe/Pe_eff, Result Summary, or Report/QA" in elastic_block
    assert "no fpj restart" in elastic_block
