from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.construction_stage import default_column_stage_rows
from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.stressing_stage_contact import (
    compression_contact_benchmark_rows,
    run_crossbeam_gravity_contact_mesh_sensitivity,
    run_crossbeam_gravity_contact_qa,
    solve_vertical_compression_contact,
)
from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    build_crossbeam_linear_stage_model,
    solve_linear_frame,
)
from concrete_pmm_pro.crossbeam.tendon import default_tendon_profile_points
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials


def _beam_model(node_count: int = 3) -> tuple[list[dict], list[dict]]:
    nodes = [
        {"id": i, "label": f"B{i}", "kind": "beam", "station_m": float(i), "x_mm": i * 1000.0, "y_mm": 0.0}
        for i in range(node_count)
    ]
    elements = [
        {
            "id": f"E{i+1}",
            "kind": "beam",
            "node_i": i,
            "node_j": i + 1,
            "station_i_m": float(i),
            "station_j_m": float(i + 1),
            "E_MPa": 30_000.0,
            "A_mm2": 100_000.0,
            "I_mm4": 8.0e9,
        }
        for i in range(node_count - 1)
    ]
    return nodes, elements


def _default_model() -> tuple[dict, list[dict], list[dict], list[dict]]:
    length_m = 20.0
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(length_m), definitions
    )
    profile = default_tendon_profile_points(
        length_m,
        tendon_ids=[f"T{i}" for i in range(1, 9)],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    columns = default_column_stage_rows(length_m)
    materials = default_concrete_materials()
    model = build_crossbeam_linear_stage_model(
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=materials,
        column_rows=columns,
        profile_rows=profile,
    )
    return model, definitions, segments, profile


def test_ptloss3b2b1_linear_kernel_accepts_vertical_only_restraints() -> None:
    nodes, elements = _beam_model(2)
    solution = solve_linear_frame(
        nodes=nodes,
        elements=elements,
        nodal_loads={1: (0.0, -1000.0, 0.0)},
        restrained_dofs=[0, 1, 3 * 1 + 1],
    )
    assert solution["status"] == "LINEAR QA READY"
    assert solution["nodes"][0]["restrained_u"] is True
    assert solution["nodes"][0]["restrained_v"] is True
    assert solution["nodes"][0]["restrained_theta"] is False
    assert solution["nodes"][1]["reaction_fy_N"] == pytest.approx(1000.0)


def test_ptloss3b2b1_contact_releases_tension_and_recloses_penetration() -> None:
    nodes, elements = _beam_model(3)
    permanent = [0, 1, 3 * 2 + 1]
    upward = solve_vertical_compression_contact(
        nodes=nodes,
        elements=elements,
        contact_node_ids=[1],
        nodal_loads={1: (0.0, 1000.0, 0.0)},
        permanent_restrained_dofs=permanent,
    )
    assert upward["ready"] is True
    assert upward["contact_rows"][0]["state"] == "OPEN"
    assert upward["contact_rows"][0]["gap_mm"] > 0.0
    assert upward["contact_rows"][0]["reaction_N"] == pytest.approx(0.0)

    downward = solve_vertical_compression_contact(
        nodes=nodes,
        elements=elements,
        contact_node_ids=[1],
        nodal_loads={1: (0.0, -1000.0, 0.0)},
        permanent_restrained_dofs=permanent,
        initial_active_contact_node_ids=[],
    )
    assert downward["ready"] is True
    assert downward["contact_rows"][0]["state"] == "ACTIVE"
    assert any(row["Re-closed"] == "1" for row in downward["iteration_rows"])
    assert downward["complementarity_status"] == "PASS"


def test_ptloss3b2b1_independent_contact_benchmarks_pass() -> None:
    rows = compression_contact_benchmark_rows()
    assert len(rows) == 4
    assert [row["Status"] for row in rows] == ["PASS"] * 4
    assert "lift-off" in rows[1]["Benchmark"]
    assert "re-closes" in rows[2]["Benchmark"]


def test_ptloss3b2b1_default_project_gravity_contact_is_balanced_and_compressive() -> None:
    model, _definitions, _segments, _profile = _default_model()
    result = run_crossbeam_gravity_contact_qa(model=model)
    assert result["ready"] is True
    assert result["status"] == "CONTACT QA READY"
    assert result["complementarity_status"] == "PASS"
    assert result["equilibrium_residual_ratio"] < 1.0e-8
    assert result["candidate_count"] == 41
    assert result["active_count"] == 41
    assert result["open_count"] == 0
    assert result["min_active_reaction_N"] > 0.0
    assert result["max_penetration_mm"] <= result["gap_tolerance_mm"]
    assert result["fcgp_status"].startswith("LOCKED")
    applied_weight = -result["solution"]["equilibrium"]["applied_fy_N"]
    total_upward = result["solution"]["equilibrium"]["reaction_fy_N"]
    assert total_upward == pytest.approx(applied_weight, rel=1.0e-12)


def test_ptloss3b2b1_contact_mesh_audit_accepts_full_contact_continuum_refinement() -> None:
    model, definitions, segments, profile = _default_model()
    assert model["ready"] is True
    result = run_crossbeam_gravity_contact_mesh_sensitivity(
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=default_column_stage_rows(20.0),
        profile_rows=profile,
        crossbeam_stressing_strength_ratio=0.80,
    )
    assert result["ready"] is True
    assert result["status"] == "QA STABLE"
    assert result["all_full_contact"] is True
    assert [row["Beam elements"] for row in result["rows"]] == [40, 80, 160]
    assert all(row["Contact status"] == "CONTACT QA READY" for row in result["rows"])
    assert result["rows"][2]["Max |M| (kN-m)"] < result["rows"][1]["Max |M| (kN-m)"]
    assert result["rows"][2]["Max |v| (mm)"] < result["rows"][1]["Max |v| (mm)"]


def test_ptloss3b2b1_ui_exposes_gravity_contact_without_releasing_fcgp() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    elastic = source.split("with elastic_shortening_tab:", 1)[1].split(
        "with time_dependent_tab:", 1
    )[0]
    assert "Compression-only falsework contact kernel — gravity-only QA" in elastic
    assert "Falsework Contact Reaction — Self-Weight Stage" in elastic
    assert "Falsework Contact Gap — Self-Weight Stage" in elastic
    assert "Compression-contact active-set, benchmark, and mesh audit" in elastic
    assert "SELF-WEIGHT ONLY" in elastic
    assert "prestress groups + f_cgp remain locked" in elastic
    contact_source = Path("concrete_pmm_pro/crossbeam/stressing_stage_contact.py").read_text(encoding="utf-8")
    assert "Gravity-only rigid vertical contact QA" in contact_source
    assert "ptloss3b2-print-table-heading" in elastic
