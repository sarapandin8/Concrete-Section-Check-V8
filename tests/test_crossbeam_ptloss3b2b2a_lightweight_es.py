from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.anchorage_set import (
    anchorage_set_end_rows,
    anchorage_set_station_rows,
)
from concrete_pmm_pro.crossbeam.construction_stage import default_column_stage_rows
from concrete_pmm_pro.crossbeam.elastic_shortening import symmetric_stressing_group_rows
from concrete_pmm_pro.crossbeam.lightweight_elastic_shortening import (
    LIGHTWEIGHT_ES_METHOD,
    run_crossbeam_lightweight_elastic_shortening,
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
from concrete_pmm_pro.crossbeam.tendon import (
    TENDON_BOND_STATE_BONDED,
    TENDON_BOND_STATE_UNBONDED,
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials


def _sources(bond_state: str | None) -> tuple[dict, list[dict], list[dict], list[dict], list[dict], dict]:
    length_m = 20.0
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(length_m), definitions
    )
    system = default_tendon_system_rows(8)
    if bond_state is not None:
        for row in system:
            row["Bond state"] = bond_state
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
    return model, profile, system, post_anchor, groups, settings


def test_lightweight_bonded_route_runs_one_cumulative_solve_and_releases_es_estimate() -> None:
    model, profile, system, post_anchor, groups, settings = _sources(
        TENDON_BOND_STATE_BONDED
    )
    result = run_crossbeam_lightweight_elastic_shortening(
        model=model,
        profile_rows=profile,
        system_rows=system,
        anchorage_station_rows=post_anchor,
        ordered_group_rows=groups,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
    )
    assert result["ready"] is True
    assert result["status"] == "DESIGN ESTIMATE READY"
    assert result["method"] == LIGHTWEIGHT_ES_METHOD
    assert result["solve_count"] == 1
    assert result["contact_result"]["complementarity_status"] == "PASS"
    assert result["contact_result"]["active_count"] == 10
    assert result["contact_result"]["open_count"] == 31
    assert result["fcgp_route"]["route"].startswith("BONDED")
    assert result["fcgp_mpa"] == pytest.approx(12.8363886688, rel=1.0e-9)
    assert result["es_summary"]["average_loss_mpa"] == pytest.approx(
        33.2858482769, rel=1.0e-9
    )
    assert result["es_summary"]["max_sequence_loss_mpa"] == pytest.approx(
        66.5716965537, rel=1.0e-9
    )
    joint_audit = result["column_joint_equilibrium"]
    assert joint_audit["ready"] is True
    assert joint_audit["pass_count"] == joint_audit["count"] == 2
    assert max(row["Residual ratio"] for row in joint_audit["rows"]) <= 1.0e-8
    column_rows = [
        row
        for row in result["fcgp_route"]["evaluation_rows"]
        if row.get("Evaluation class") == "COLUMN"
    ]
    assert {row["Limit side"] for row in column_rows} == {
        "LEFT LIMIT (s−)",
        "RIGHT LIMIT (s+)",
    }
    assert any(
        row.get("P after ES (kN)") is not None
        for row in result["after_es_station_rows"]
    )


def test_lightweight_unbonded_route_uses_member_length_average() -> None:
    model, profile, system, post_anchor, groups, settings = _sources(
        TENDON_BOND_STATE_UNBONDED
    )
    result = run_crossbeam_lightweight_elastic_shortening(
        model=model,
        profile_rows=profile,
        system_rows=system,
        anchorage_station_rows=post_anchor,
        ordered_group_rows=groups,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
    )
    assert result["ready"] is True
    assert result["fcgp_route"]["route"].startswith("UNBONDED")
    assert result["fcgp_mpa"] > 0.0
    assert len(result["fcgp_route"]["evaluation_rows"]) > 10


def test_lightweight_route_blocks_unspecified_final_bond_system_without_solving() -> None:
    model, profile, system, post_anchor, groups, settings = _sources(None)
    result = run_crossbeam_lightweight_elastic_shortening(
        model=model,
        profile_rows=profile,
        system_rows=system,
        anchorage_station_rows=post_anchor,
        ordered_group_rows=groups,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
    )
    assert result["ready"] is False
    assert result["status"] == "SOURCE BLOCKED"
    assert result["solve_count"] == 0
    assert any("Final bond system is not specified" in issue for issue in result["issues"])


def test_lightweight_ui_is_explicitly_on_demand_and_advanced_qa_is_not_automatic() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(
        encoding="utf-8"
    )
    elastic = source.split("with elastic_shortening_tab:", 1)[1].split(
        "with time_dependent_tab:", 1
    )[0]
    assert "Lightweight Elastic Shortening design estimate" in elastic
    assert "Run Lightweight ES Analysis" in elastic
    assert "no FEA solve when opening the page" in elastic
    assert "single cumulative AASHTO design route" in elastic
    assert "Actual structural solves" in elastic
    assert "Column-joint equilibrium" in elastic
    assert "LEFT LIMIT (s−) and RIGHT LIMIT (s+)" in elastic
    assert "Support footprints" in elastic
    assert "Evaluation coverage" in elastic
    assert "Run Advanced Construction-Stage QA" in elastic
    assert "never runs automatically" in elastic
    assert elastic.index("run_crossbeam_lightweight_elastic_shortening") > elastic.index(
        "if run_lightweight:"
    )
    assert elastic.index("run_crossbeam_incremental_contact_mesh_sensitivity") > elastic.index(
        "if run_advanced:"
    )
