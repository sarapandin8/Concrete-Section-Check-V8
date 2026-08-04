from __future__ import annotations

import math

from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_TR_TEMPLATE_ROWS_KEY,
    CROSSBEAM_REBAR_METADATA_KEY,
    CROSSBEAM_REBAR_SCHEMA_VERSION,
    crossbeam_rebar_metadata_from_session_state,
    restore_crossbeam_rebar_project_state,
)
from concrete_pmm_pro.crossbeam.transverse import (
    TR_HOLLOW_MIN,
    TR_SOLID_COLUMN,
    build_outer_torsion_cage_geometry,
    default_crossbeam_transverse_templates,
    transverse_torsion_cage_record,
)
from concrete_pmm_pro.crossbeam.section_library import (
    build_geometry_for_definition,
    default_section_definitions,
    definition_map,
)


def _template(template_id: str) -> dict:
    return next(
        row for row in default_crossbeam_transverse_templates()
        if row["Template ID"] == template_id
    )


def test_legacy_hollow_template_does_not_receive_silent_torsion_cage_credit() -> None:
    hollow = _template(TR_HOLLOW_MIN)
    record = transverse_torsion_cage_record(hollow)
    assert record["Status"] == "LAYOUT REQUIRED"
    assert record["Adopted"] is False
    assert math.isnan(float(record["At/s mm²/mm"]))


def test_user_defined_hollow_outer_cage_reports_at_source() -> None:
    hollow = _template(TR_HOLLOW_MIN)
    hollow.update(
        {
            "Use outer torsion cage": True,
            "Torsion cage bar size": "DB12",
            "Torsion cage spacing mm": 200.0,
            "Torsion cage center offset mm": 60.0,
            "Torsion cage relationship": "Additional outer cage",
            "Torsion cage closure": "Verified closed loop",
        }
    )
    record = transverse_torsion_cage_record(hollow)
    assert record["Status"] == "USER DEFINED"
    assert record["Adopted"] is True
    assert record["At/s mm²/mm"] > 0.0
    assert record["2At/s mm²/mm"] == 2.0 * record["At/s mm²/mm"]

    definitions = definition_map(default_section_definitions())
    geometry = build_geometry_for_definition(definitions["CB-H01"])
    cage = build_outer_torsion_cage_geometry(geometry, hollow)
    assert cage.ok
    assert len(cage.closed_loops) == 1
    assert cage.closed_loops[0].label == "User-defined outer torsion cage"


def test_shared_solid_cage_requires_exact_shear_source_match() -> None:
    solid = _template(TR_SOLID_COLUMN)
    matched = transverse_torsion_cage_record(solid)
    assert matched["Status"] == "MATCH"
    assert matched["Adopted"] is True

    solid["Torsion cage spacing mm"] = float(solid["Spacing mm"]) + 25.0
    mismatch = transverse_torsion_cage_record(solid)
    assert mismatch["Status"] == "MISMATCH"
    assert mismatch["Adopted"] is False


def test_project_json_round_trip_persists_outer_torsion_cage_fields() -> None:
    rows = default_crossbeam_transverse_templates()
    hollow = next(row for row in rows if row["Template ID"] == TR_HOLLOW_MIN)
    hollow.update(
        {
            "Use outer torsion cage": True,
            "Torsion cage bar size": "DB16",
            "Torsion cage spacing mm": 150.0,
            "Torsion cage center offset mm": 65.0,
            "Torsion cage relationship": "Additional outer cage",
            "Torsion cage closure": "Verified closed loop",
        }
    )
    state = {CB_TR_TEMPLATE_ROWS_KEY: rows}
    block = crossbeam_rebar_metadata_from_session_state(state)
    assert block["schema_version"] == CROSSBEAM_REBAR_SCHEMA_VERSION

    restored: dict = {}
    restore_crossbeam_rebar_project_state(
        {CROSSBEAM_REBAR_METADATA_KEY: block}, restored, segment_rows=[]
    )
    restored_hollow = next(
        row for row in restored[CB_TR_TEMPLATE_ROWS_KEY]
        if row["Template ID"] == TR_HOLLOW_MIN
    )
    assert restored_hollow["Use outer torsion cage"] is True
    assert restored_hollow["Torsion cage bar size"] == "DB16"
    assert restored_hollow["Torsion cage spacing mm"] == 150.0
    assert restored_hollow["Torsion cage center offset mm"] == 65.0
    assert restored_hollow["Torsion cage closure"] == "Verified closed loop"
