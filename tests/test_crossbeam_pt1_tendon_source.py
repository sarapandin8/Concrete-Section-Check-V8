from __future__ import annotations

from copy import deepcopy

from concrete_pmm_pro.crossbeam.section_library import (
    DEFAULT_HOLLOW_SECTION_ID,
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.tendon import (
    canonical_tendon_system_rows,
    default_tendon_profile_points,
    default_tendon_system_rows,
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
    assert len(rows) == 4
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
    system = default_tendon_system_rows(4)
    ids = [row["Tendon ID"] for row in system]
    points = default_tendon_profile_points(
        20.0,
        tendon_ids=ids,
        width_mm=2500.0,
        height_mm=1500.0,
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
    assert len(normalized) == 12
    assert {row["s (m)"] for row in normalized} == {0.0, 10.0, 20.0}
    assert all("x lateral (mm)" in row and "dtop (mm)" in row for row in normalized)


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
