from __future__ import annotations

from types import SimpleNamespace

from concrete_pmm_pro.crossbeam.rebar import (
    RB_HOLLOW_MIN,
    RB_SOLID_COLUMN,
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_MIG1_ROLE_REPAIR_DONE_KEY,
    CB_RB_PROJECT_LOAD_VALIDATION_KEY,
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_REV_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
    validate_loaded_crossbeam_rebar_state,
)
from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.transverse import (
    TR_HOLLOW_MIN,
    default_crossbeam_transverse_templates,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui import crossbeam_rebar_page


def test_page_entry_reconciles_migrated_assignments_against_current_segment_roles(monkeypatch) -> None:
    definitions = default_section_definitions()
    current_segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), definitions
    )
    stale_solid_segments = [dict(row, **{"Section role": "Solid"}) for row in current_segments]
    longitudinal = default_crossbeam_rebar_templates()
    transverse = default_crossbeam_transverse_templates()
    stale_zones = default_crossbeam_rebar_zones(
        stale_solid_segments, longitudinal, transverse
    )

    stale_validation = validate_loaded_crossbeam_rebar_state(
        longitudinal, transverse, stale_zones, stale_solid_segments
    )
    assert stale_validation["status"] == "READY"
    stale_validation["migrated"] = True
    stale_validation["migration_notes"] = ["Legacy migration ran before final Segment roles resolved."]

    state = {
        CB_RB_TEMPLATE_ROWS_KEY: longitudinal,
        CB_TR_TEMPLATE_ROWS_KEY: transverse,
        CB_RB_ZONE_ROWS_KEY: stale_zones,
        CB_RB_ZONE_REV_KEY: 0,
        CB_RB_PROJECT_LOAD_VALIDATION_KEY: stale_validation,
    }
    monkeypatch.setattr(crossbeam_rebar_page, "st", SimpleNamespace(session_state=state))

    crossbeam_rebar_page._reconcile_migrated_rebar_assignments_once(current_segments)

    zones = {str(row["Segment"]): row for row in state[CB_RB_ZONE_ROWS_KEY]}
    for segment in current_segments:
        segment_id = str(segment["Segment"])
        if str(segment["Section role"]) == "Hollow":
            assert zones[segment_id]["Longitudinal template"] == RB_HOLLOW_MIN
            assert zones[segment_id]["Transverse template"] == TR_HOLLOW_MIN
        else:
            assert zones[segment_id]["Longitudinal template"] == RB_SOLID_COLUMN

    validation = state[CB_RB_PROJECT_LOAD_VALIDATION_KEY]
    assert validation["status"] == "READY"
    assert validation["references_resolved"] is True
    assert validation["migrated"] is True
    assert state[CB_RB_MIG1_ROLE_REPAIR_DONE_KEY] is True
    assert state[CB_RB_ZONE_REV_KEY] == 1
    assert any("Reconciled" in note for note in validation["migration_notes"])

    snapshot = list(state[CB_RB_ZONE_ROWS_KEY])
    crossbeam_rebar_page._reconcile_migrated_rebar_assignments_once(current_segments)
    assert state[CB_RB_ZONE_ROWS_KEY] == snapshot
    assert state[CB_RB_ZONE_REV_KEY] == 1
