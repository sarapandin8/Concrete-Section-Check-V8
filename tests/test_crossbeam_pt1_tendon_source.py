from __future__ import annotations

from copy import deepcopy

import pytest

from concrete_pmm_pro.crossbeam.section_library import (
    DEFAULT_HOLLOW_SECTION_ID,
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.tendon import (
    TENDON_PROFILE_PRESET_OPTIONS,
    TENDON_PROFILE_SPAN_MODE_OPTIONS,
    canonical_tendon_system_rows,
    default_tendon_profile_points,
    default_tendon_system_rows,
    normalize_tendon_profile_preset,
    normalize_tendon_profile_span_mode,
    profile_preset_point_count,
    tendon_profile_points_for_preset,
    tendon_positions_at_station,
    tendon_station_audit_rows,
    validate_tendon_profile,
    validate_tendon_system,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows


def _geometry_context():
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), definitions
    )
    return definitions, segments


def test_pt1_default_system_has_more_than_two_complete_tendons() -> None:
    rows, errors, warnings = validate_tendon_system(default_tendon_system_rows())

    assert not errors
    assert not warnings
    assert len(rows) == 8
    assert all(row["Active"] for row in rows)
    assert {row["Type"] for row in rows} == {"Internal"}
    assert {row["Jacking end"] for row in rows} == {"Both"}
    assert {row["Strand system"] for row in rows} == {"Seven-wire low-relaxation strand"}
    assert {row["fpu MPa"] for row in rows} == {1860.0}
    assert {row["Aps/strand mm²"] for row in rows} == {140.0}
    assert {row["fpj/fpu"] for row in rows} == {0.75}
    assert {row["Left anchorage"] for row in rows} == {"s = 0"}
    assert {row["Right anchorage"] for row in rows} == {"s = L"}


def test_pt1_profile_is_one_source_for_plan_profile_and_3d_coordinates() -> None:
    system = default_tendon_system_rows()
    ids = [row["Tendon ID"] for row in system]
    points = default_tendon_profile_points(
        20.0,
        tendon_ids=ids,
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    definitions, segments = _geometry_context()

    normalized, errors, warnings = validate_tendon_profile(
        points,
        system,
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
    )

    assert not errors
    assert not warnings
    assert len(normalized) == 24
    assert {row["s (m)"] for row in normalized} == {0.0, 10.0, 20.0}
    assert all("x lateral (mm)" in row and "dtop (mm)" in row for row in normalized)


def test_pt1f_default_profile_places_four_tendons_in_each_web_at_constant_depths() -> None:
    system = default_tendon_system_rows()
    tendon_ids = [row["Tendon ID"] for row in system]

    points = default_tendon_profile_points(
        20.0,
        tendon_ids=tendon_ids,
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    p1_by_id = {
        row["Tendon ID"]: row
        for row in points
        if row["Point"] == "P1"
    }

    assert tendon_ids == [f"T{index}" for index in range(1, 9)]
    assert {p1_by_id[f"T{index}"]["x lateral (mm)"] for index in range(1, 5)} == {-1100.0}
    assert {p1_by_id[f"T{index}"]["x lateral (mm)"] for index in range(5, 9)} == {1100.0}
    assert [p1_by_id[f"T{index}"]["dtop (mm)"] for index in range(1, 5)] == pytest.approx(
        [500.0, 733.333, 966.667, 1200.0]
    )
    assert [p1_by_id[f"T{index}"]["dtop (mm)"] for index in range(5, 9)] == pytest.approx(
        [500.0, 733.333, 966.667, 1200.0]
    )
    for tendon_id in tendon_ids:
        rows = [row for row in points if row["Tendon ID"] == tendon_id]
        assert {row["x lateral (mm)"] for row in rows} == {p1_by_id[tendon_id]["x lateral (mm)"]}
        assert {row["dtop (mm)"] for row in rows} == {p1_by_id[tendon_id]["dtop (mm)"]}


def test_pt1a_cross_section_station_uses_piecewise_linear_shared_profile() -> None:
    system = default_tendon_system_rows()
    points = default_tendon_profile_points(
        20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )

    positions = tendon_positions_at_station(
        points,
        system,
        station_m=5.0,
        length_m=20.0,
    )

    assert len(positions) == 8
    assert {row["Interpolation"] for row in positions} == {"Piecewise linear"}
    assert {row["Left point"] for row in positions} == {"P1"}
    assert {row["Right point"] for row in positions} == {"P2"}
    assert sorted({round(row["dtop (mm)"], 3) for row in positions}) == pytest.approx(
        [500.0, 733.333, 966.667, 1200.0]
    )
    assert {row["x lateral (mm)"] for row in positions} == {-1100.0, 1100.0}
    assert all(row["s (m)"] == 5.0 and row["s/L"] == 0.25 for row in positions)


def test_pt1g_parabolic_preset_seeds_multiple_editable_points_per_tendon() -> None:
    system = default_tendon_system_rows()
    tendon_ids = [row["Tendon ID"] for row in system[:2]]

    points = tendon_profile_points_for_preset(
        20.0,
        tendon_ids=tendon_ids,
        coordinate_tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
        preset="Parabolic low-point",
        bend_offset_mm=200.0,
    )
    definitions, segments = _geometry_context()
    normalized, errors, warnings = validate_tendon_profile(
        points,
        system[:2],
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
    )
    t1_rows = [row for row in normalized if row["Tendon ID"] == "T1"]

    assert not errors
    assert not warnings
    assert profile_preset_point_count("Parabolic low-point") == 5
    assert len(normalized) == 10
    assert [row["s (m)"] for row in t1_rows] == [0.0, 5.0, 10.0, 15.0, 20.0]
    assert [row["Point"] for row in t1_rows] == ["P1", "P2", "P3", "P4", "P5"]
    assert t1_rows[2]["Curve role"] == "Low point"
    assert t1_rows[2]["dtop (mm)"] == pytest.approx(700.0)


def test_pt1i_quick_start_catalog_is_curated_and_renamed_without_numbers() -> None:
    assert TENDON_PROFILE_PRESET_OPTIONS == (
        "Straight Tendon",
        "Straight Tendon With Bends",
        "Parabolic Tendon",
    )
    assert TENDON_PROFILE_SPAN_MODE_OPTIONS == ("Single Span", "2 Span")
    assert normalize_tendon_profile_preset("Straight Tendon 2") == "Straight Tendon"
    assert (
        normalize_tendon_profile_preset("Straight Tendon With Bends 4")
        == "Straight Tendon With Bends"
    )
    assert normalize_tendon_profile_preset("Parabolic Tendon 3") == "Parabolic Tendon"
    assert normalize_tendon_profile_span_mode("Multiple Span") == "2 Span"


def test_pt1h_reference_quick_start_catalog_supports_single_and_multiple_span_shapes() -> None:
    system = default_tendon_system_rows()
    tendon_ids = [row["Tendon ID"] for row in system]

    single = tendon_profile_points_for_preset(
        20.0,
        tendon_ids=["T1"],
        coordinate_tendon_ids=tendon_ids,
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
        preset="Straight Tendon With Bends",
        span_mode="Single Span",
        bend_offset_mm=200.0,
    )
    multiple = tendon_profile_points_for_preset(
        20.0,
        tendon_ids=["T1"],
        coordinate_tendon_ids=tendon_ids,
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
        preset="Straight Tendon With Bends",
        span_mode="2 Span",
        bend_offset_mm=200.0,
    )

    assert [row["s (m)"] for row in single] == [0.0, 5.0, 15.0, 20.0]
    assert [row["s (m)"] for row in multiple] == [
        0.0,
        2.5,
        7.5,
        10.0,
        12.5,
        17.5,
        20.0,
    ]
    assert {row["x lateral (mm)"] for row in multiple} == {-1100.0}
    assert any(
        row["Curve role"] == "High point" and row["s (m)"] == 10.0
        for row in multiple
    )
    assert profile_preset_point_count("Straight Tendon With Bends", "2 Span") == 7


def test_pt1i_parabolic_two_span_repeats_simple_span_across_middle_support() -> None:
    system = default_tendon_system_rows()
    tendon_ids = [row["Tendon ID"] for row in system]

    rows = tendon_profile_points_for_preset(
        20.0,
        tendon_ids=["T1"],
        coordinate_tendon_ids=tendon_ids,
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
        preset="Parabolic Tendon",
        span_mode="2 Span",
        bend_offset_mm=200.0,
    )

    assert [row["s (m)"] for row in rows] == [
        0.0,
        2.5,
        5.0,
        7.5,
        10.0,
        12.5,
        15.0,
        17.5,
        20.0,
    ]
    assert rows[4]["Curve role"] == "High point"
    assert rows[4]["dtop (mm)"] == pytest.approx(500.0)
    assert [rows[2]["Curve role"], rows[6]["Curve role"]] == ["Low point", "Low point"]
    assert [rows[2]["dtop (mm)"], rows[6]["dtop (mm)"]] == pytest.approx([700.0, 700.0])


def test_pt1_internal_profile_uses_station_section_envelope_but_external_can_leave_it() -> None:
    definitions, segments = _geometry_context()
    system = default_tendon_system_rows(3)
    points = default_tendon_profile_points(
        20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
    )
    for point in points:
        if point["Tendon ID"] == "T1":
            point["x lateral (mm)"] = 5000.0

    _normalized, internal_errors, _warnings = validate_tendon_profile(
        points,
        system,
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
    )
    assert any("T1" in message and "outside Section ID" in message for message in internal_errors)

    external_system = deepcopy(system)
    external_system[0]["Type"] = "External"
    _normalized, external_errors, _warnings = validate_tendon_profile(
        points,
        external_system,
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
    )
    assert not any("T1" in message and "outside Section ID" in message for message in external_errors)


def test_pt1_station_audit_uses_both_assigned_section_centroids_at_joint() -> None:
    definitions, segments = _geometry_context()
    for definition in definitions:
        if definition["Section ID"] == DEFAULT_HOLLOW_SECTION_ID:
            definition["Parameters"]["height_mm"] = 1800.0
    system = canonical_tendon_system_rows(default_tendon_system_rows(3))
    points = default_tendon_profile_points(
        20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
    )

    audit = tendon_station_audit_rows(
        points,
        system,
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
    )
    joint_rows = [
        row
        for row in audit
        if row["Tendon ID"] == "T1" and row["Point"] == "P2" and row["s (m)"] == 10.0
    ]

    assert len(joint_rows) == 2
    assert {row["Segment"] for row in joint_rows} == {"S3", "S4"}
    assert len({round(row["centroid from top (mm)"], 3) for row in joint_rows}) == 2
    assert all(row["e(s) (mm)"] == row["dtop (mm)"] - row["centroid from top (mm)"] for row in joint_rows)
