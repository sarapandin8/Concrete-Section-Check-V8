from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.anchorage_set import (
    anchorage_set_end_rows,
    anchorage_set_station_rows,
)
from concrete_pmm_pro.crossbeam.construction_stage import (
    default_column_stage_rows,
    temporary_support_source,
)
from concrete_pmm_pro.crossbeam.elastic_shortening import (
    symmetric_stressing_group_rows,
)
from concrete_pmm_pro.crossbeam.prestress_loss import (
    aashto_friction_wobble_station_rows,
    default_crossbeam_prestress_loss_settings,
)
from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.stressing_stage_frame import (
    build_crossbeam_linear_stage_model,
)
from concrete_pmm_pro.crossbeam.stressing_stage_sequence import (
    incremental_contact_benchmark_rows,
    run_crossbeam_incremental_contact_mesh_sensitivity,
    run_crossbeam_incremental_contact_qa,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials


def _default_sources() -> tuple[dict, list[dict], list[dict], list[dict]]:
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
        external_inadvertent_angle_rad=settings[
            "external_inadvertent_angle_rad"
        ],
    )
    ends = anchorage_set_end_rows(
        friction,
        length_m=length_m,
        anchor_set_mm=settings["anchorage_set_mm"],
        ep_mpa=settings["ep_mpa"],
    )
    post_anchor = anchorage_set_station_rows(
        friction, ends, length_m=length_m
    )
    model = build_crossbeam_linear_stage_model(
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=default_column_stage_rows(length_m),
        profile_rows=profile,
    )
    groups = symmetric_stressing_group_rows(
        profile, system, length_m=length_m
    )
    return model, profile, post_anchor, groups


def test_ptloss3b2b2_default_project_runs_gravity_plus_four_cumulative_groups() -> None:
    model, profile, post_anchor, groups = _default_sources()
    result = run_crossbeam_incremental_contact_qa(
        model=model,
        profile_rows=profile,
        anchorage_station_rows=post_anchor,
        group_rows=groups,
        pair_sequence=["G1", "G2", "G3", "G4"],
    )
    assert result["ready"] is True
    assert result["status"] == "INCREMENTAL CONTACT QA READY"
    assert result["stage_count"] == 5
    assert [row["Stage"] for row in result["stage_rows"]] == [
        "G0",
        "G1",
        "G2",
        "G3",
        "G4",
    ]
    assert result["stage_rows"][0]["Open nodes"] == 0
    assert any(row["Open nodes"] > 0 for row in result["stage_rows"][1:])
    assert result["final_stage"]["contact_result"]["complementarity_status"] == "PASS"
    assert result["final_stage"]["contact_result"]["equilibrium_residual_ratio"] < 1.0e-8
    assert result["final_consistency"]["status"] == "PASS"
    assert result["fcgp_status"].startswith("LOCKED")
    assert result["elastic_shortening_status"].startswith("LOCKED")


def test_ptloss3b2b2_group_sources_use_only_the_pair_tendons_and_post_anchor_force() -> None:
    model, profile, post_anchor, groups = _default_sources()
    result = run_crossbeam_incremental_contact_qa(
        model=model,
        profile_rows=profile,
        anchorage_station_rows=post_anchor,
        group_rows=groups,
        pair_sequence=["G1", "G2", "G3", "G4"],
    )
    assert result["group_source_rows"][0]["Tendons"] == "T1 + T5"
    assert result["group_source_rows"][0]["Post-anchor tendon count"] == 2
    assert result["group_source_rows"][0]["Load source"] == "LOAD SOURCE READY"
    assert result["stages"][1]["cumulative_tendon_count"] == 2
    assert result["stages"][-1]["cumulative_tendon_count"] == 8


def test_ptloss3b2b2_sequence_changes_intermediate_path_but_not_final_cumulative_solution() -> None:
    model, profile, post_anchor, groups = _default_sources()
    forward = run_crossbeam_incremental_contact_qa(
        model=model,
        profile_rows=profile,
        anchorage_station_rows=post_anchor,
        group_rows=groups,
        pair_sequence=["G1", "G2", "G3", "G4"],
    )
    reverse = run_crossbeam_incremental_contact_qa(
        model=model,
        profile_rows=profile,
        anchorage_station_rows=post_anchor,
        group_rows=groups,
        pair_sequence=["G4", "G3", "G2", "G1"],
    )
    assert forward["ready"] and reverse["ready"]
    assert forward["stages"][1]["tendons"] != reverse["stages"][1]["tendons"]
    assert forward["final_consistency"]["ready"] is True
    assert reverse["final_consistency"]["ready"] is True
    assert forward["final_stage"]["contact_result"]["active_node_ids"] == reverse["final_stage"]["contact_result"]["active_node_ids"]
    assert forward["final_stage"]["contact_result"]["total_contact_reaction_N"] == pytest.approx(
        reverse["final_stage"]["contact_result"]["total_contact_reaction_N"],
        rel=1.0e-12,
    )


def test_ptloss3b2b2_blocks_incomplete_pair_assignment() -> None:
    model, profile, post_anchor, groups = _default_sources()
    broken_groups = [dict(row) for row in groups]
    broken_groups[-1]["Status"] = "REVIEW REQUIRED"
    broken_groups[-1]["Issue"] = "synthetic missing pair"
    result = run_crossbeam_incremental_contact_qa(
        model=model,
        profile_rows=profile,
        anchorage_station_rows=post_anchor,
        group_rows=broken_groups,
        pair_sequence=["G1", "G2", "G3", "G4"],
    )
    assert result["ready"] is False
    assert result["status"] == "SOURCE BLOCKED"
    assert result["stages"] == []


def test_ptloss3b2b2_independent_incremental_benchmarks_pass() -> None:
    rows = incremental_contact_benchmark_rows()
    assert len(rows) == 4
    assert [row["Status"] for row in rows] == ["PASS"] * 4
    assert "uplift" in rows[0]["Benchmark"]
    assert "one-shot" in rows[-1]["Benchmark"]




def test_ptloss3b2b2_incremental_contact_mesh_global_response_is_stable() -> None:
    model, profile, post_anchor, groups = _default_sources()
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), definitions
    )
    result = run_crossbeam_incremental_contact_mesh_sensitivity(
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=default_column_stage_rows(20.0),
        profile_rows=profile,
        anchorage_station_rows=post_anchor,
        group_rows=groups,
        pair_sequence=["G1", "G2", "G3", "G4"],
        crossbeam_stressing_strength_ratio=0.80,
    )
    assert model["ready"] is True
    assert result["ready"] is True
    assert result["status"] == "QA STABLE"
    assert [row["Beam elements"] for row in result["rows"]] == [40, 80, 160]
    assert result["max_last_global_delta_percent"] <= 1.0
    assert result["contact_boundary_resolution_m"] == pytest.approx(0.0625)
    assert result["last_open_length_delta_percent"] > 1.0
    assert "informational" in result["criterion"]

def test_ptloss3b2b2_ui_exposes_incremental_contact_and_keeps_fcgp_locked() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(
        encoding="utf-8"
    )
    elastic = source.split("with elastic_shortening_tab:", 1)[1].split(
        "with time_dependent_tab:", 1
    )[0]
    assert "Incremental tendon-group contact stages — post-anchor QA" in elastic
    assert "G0 → " in elastic
    assert "Prestress-induced lift-off" in elastic
    assert "Final cumulative consistency" in elastic
    assert "Stage mesh sensitivity" in elastic
    assert "Current-input incremental contact mesh sensitivity" in elastic
    assert "Selected incremental-stage structural response" in elastic
    assert "Incremental contact source, active-set, and consistency audit" in elastic
    assert "P AFTER ANCHORAGE SET" in elastic
    assert "f_cgp + ES force feedback remain locked" in elastic
    assert "incremental_contact_chunk_size = 14" in elastic

    support = temporary_support_source(20.0)
    assert "incremental post-anchor tendon-group QA" in support["note"]
    assert "Source-derived f_cgp and Elastic Shortening remain locked" in support["note"]
