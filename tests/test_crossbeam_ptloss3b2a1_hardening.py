from __future__ import annotations

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
    build_crossbeam_linear_stage_model,
    frame_rigid_offset_matrix,
    linear_stage_stiffness_source_rows,
    prestress_equivalent_nodal_loads,
    ptloss3b2a1_benchmark_rows,
    run_crossbeam_linear_mesh_sensitivity,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials
from concrete_pmm_pro.core.models import ConcreteMaterial


def _sources() -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
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
    system = default_tendon_system_rows(8)
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
    return definitions, segments, profile, system, post_anchor


def test_ptloss3b2a1_uses_crossbeam_stressing_stage_eci_and_separate_column_ec() -> None:
    definitions, segments, profile, _, _ = _sources()
    model = build_crossbeam_linear_stage_model(
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=default_column_stage_rows(20.0),
        profile_rows=profile,
        crossbeam_stressing_strength_ratio=0.80,
    )
    assert model["ready"] is True
    for source in model["section_sources"].values():
        assert source["fc_28_mpa"] == pytest.approx(45.0)
        assert source["fci_mpa"] == pytest.approx(36.0)
        assert source["Eci_MPa"] == pytest.approx(28_200.0)
        assert source["Ec_28_MPa"] == pytest.approx(4700.0 * 45.0**0.5)
        assert source["E_MPa"] == pytest.approx(28_200.0)
    for source in model["column_sources"]:
        assert source["fc_stage_mpa"] == pytest.approx(35.0)
        assert source["E_stage_MPa"] == pytest.approx(4700.0 * 35.0**0.5)


def test_ptloss3b2a1_scales_manual_material_ec_to_stressing_strength() -> None:
    definitions, segments, profile, _, _ = _sources()
    manual = ConcreteMaterial(
        name="C45_PRECAST",
        fc_MPa=45.0,
        Ec_method="Manual",
        Ec_MPa=33_000.0,
    )
    model = build_crossbeam_linear_stage_model(
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=[manual],
        column_rows=default_column_stage_rows(20.0),
        profile_rows=profile,
        crossbeam_stressing_strength_ratio=0.80,
    )
    expected = 33_000.0 * 0.80**0.5
    assert model["ready"] is True
    for source in model["section_sources"].values():
        assert source["Eci_MPa"] == pytest.approx(expected)
        assert "Manual Ec" in source["modulus_source"]


def test_ptloss3b2a1_resolves_multiple_centroids_with_exact_rigid_offsets() -> None:
    definitions, segments, profile, _, _ = _sources()
    model = build_crossbeam_linear_stage_model(
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=default_column_stage_rows(20.0),
        profile_rows=profile,
    )
    reference = model["reference_axis"]
    assert reference["status"] == "READY"
    assert reference["centroid_spread_mm"] > 1.0
    offsets = {
        source["centroid_offset_from_reference_mm"]
        for source in model["section_sources"].values()
    }
    assert len(offsets) == 2
    assert any(abs(value) > 1.0 for value in offsets)
    beam_elements = [
        element for element in model["elements"] if element["kind"] == "beam"
    ]
    assert any(abs(element["offset_i_y_mm"]) > 1.0 for element in beam_elements)
    assert all(
        element["offset_i_y_mm"] == pytest.approx(element["offset_j_y_mm"])
        for element in beam_elements
    )


def test_ptloss3b2a1_rigid_offset_matrix_maps_reference_rotation_exactly() -> None:
    matrix = frame_rigid_offset_matrix(
        offset_i_y_mm=-200.0,
        offset_j_y_mm=150.0,
    )
    reference = [1.0, 2.0, 0.01, 3.0, 4.0, -0.02]
    centroid = matrix @ reference
    assert centroid[0] == pytest.approx(1.0 - (-200.0) * 0.01)
    assert centroid[1] == pytest.approx(2.0)
    assert centroid[2] == pytest.approx(0.01)
    assert centroid[3] == pytest.approx(3.0 - 150.0 * (-0.02))
    assert centroid[4] == pytest.approx(4.0)
    assert centroid[5] == pytest.approx(-0.02)


def test_ptloss3b2a1_primary_pe_reference_is_local_section_sign_audit() -> None:
    model = {
        "ready": True,
        "length_m": 10.0,
        "stations_m": [0.0, 10.0],
        "nodes": [
            {"id": 0, "x_mm": 0.0, "y_mm": 0.0},
            {"id": 1, "x_mm": 10_000.0, "y_mm": 0.0},
        ],
        "beam_node_by_station": {0.0: 0, 10.0: 1},
        "ranges": [
            {"Region": "Z1", "start_m": 0.0, "end_m": 10.0, "section_id": "S1"}
        ],
        "section_sources": {"S1": {"centroid_from_top_mm": 750.0}},
        "reference_axis": {"reference_centroid_from_top_mm": 750.0},
    }
    source = prestress_equivalent_nodal_loads(
        model=model,
        profile_rows=[
            {"Tendon ID": "T1", "s (m)": 0.0, "dtop (mm)": 950.0},
            {"Tendon ID": "T1", "s (m)": 10.0, "dtop (mm)": 950.0},
        ],
        anchorage_station_rows=[
            {
                "Tendon ID": "T1",
                "Active": True,
                "s (m)": station,
                "P after anchorage set (kN)": 1000.0,
            }
            for station in (0.0, 10.0)
        ],
    )
    assert source["ready"] is True
    for row in source["primary_reference_rows"]:
        assert row["Primary P·e moment (kN-m; sagging +)"] == pytest.approx(-200.0)
    audit = source["audit_rows"][0]
    assert audit["e_i below local centroid (mm)"] == pytest.approx(200.0)
    assert audit["y_i from reference (mm; up +)"] == pytest.approx(-200.0)


def test_ptloss3b2a1_independent_benchmarks_pass() -> None:
    rows = ptloss3b2a1_benchmark_rows()
    assert [row["Status"] for row in rows] == ["PASS", "PASS", "PASS"]
    assert "P·e" in rows[1]["Expected"]
    assert "symmetry residual" in rows[2]["Observed"]


def test_ptloss3b2a1_mesh_sensitivity_is_stable_for_default_model() -> None:
    definitions, segments, profile, _, post_anchor = _sources()
    result = run_crossbeam_linear_mesh_sensitivity(
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=default_column_stage_rows(20.0),
        profile_rows=profile,
        anchorage_station_rows=post_anchor,
        crossbeam_stressing_strength_ratio=0.80,
    )
    assert result["ready"] is True
    assert result["status"] == "QA STABLE"
    assert [row["Beam elements"] for row in result["rows"]] == [40, 80, 160]
    assert result["max_fine_mesh_delta_percent"] < 1.0


def test_ptloss3b2a1_stiffness_audit_exposes_ea_ei_axis_and_offsets() -> None:
    definitions, segments, profile, _, _ = _sources()
    model = build_crossbeam_linear_stage_model(
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
        concrete_materials=default_concrete_materials(),
        column_rows=default_column_stage_rows(20.0),
        profile_rows=profile,
    )
    rows = linear_stage_stiffness_source_rows(model)
    assert rows
    assert any(row["Member"] == "Crossbeam" for row in rows)
    assert any(row["Member"] == "Column" for row in rows)
    assert all(row["EA (N)"] > 0.0 and row["EI⊥s (N-mm²)"] > 0.0 for row in rows)
    assert any("I⊥s" in row["Source / axis"] for row in rows if row["Member"] == "Column")


def test_ptloss3b2a1_ui_separates_axial_shear_and_adds_print_guard() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    elastic = source.split("with elastic_shortening_tab:", 1)[1].split(
        "with time_dependent_tab:", 1
    )[0]
    assert "Crossbeam Axial Force —" in elastic
    assert "Crossbeam Shear Force —" in elastic
    assert "Crossbeam Axial / Shear —" not in elastic
    assert "Primary Prestress P·e Reference" in elastic
    assert "Stage stiffness, reference-axis, and benchmark audit" in elastic
    assert "Run linear-response mesh-sensitivity diagnostic" in elastic
    assert "@media print" in elastic and "break-inside: avoid" in elastic
