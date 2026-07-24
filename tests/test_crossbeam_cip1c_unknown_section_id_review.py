from __future__ import annotations

from types import SimpleNamespace

from concrete_pmm_pro.crossbeam.construction_stage import CONSTRUCTION_METHOD_CIP
from concrete_pmm_pro.crossbeam.prestress_loss import CB_LOSS_ES_CONSTRUCTION_METHOD_KEY
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_DEFINITIONS_KEY,
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)
from concrete_pmm_pro.ui import crossbeam_pages


UNKNOWN_SECTION_ID = "CB-MISSING"


def _unknown_zone() -> list[dict[str, object]]:
    return [
        {
            "Segment": "Z1",
            "x_start_m": 0.0,
            "x_end_m": 20.0,
            "Section ID": UNKNOWN_SECTION_ID,
            "Section name": "Stale project label",
            "Section role": "Solid",
            "Section preset key": "",
            "Section type / preset": "",
        }
    ]


def test_explicit_unknown_section_id_is_not_replaced_by_role_or_row_position() -> None:
    definitions = default_section_definitions()

    migrated = migrate_segment_rows_to_library(
        _unknown_zone(),
        definitions,
        preserve_explicit_unknown_ids=True,
    )

    assert migrated[0]["Section ID"] == UNKNOWN_SECTION_ID


def test_layout_validation_preserves_unknown_section_id_and_requires_review(monkeypatch) -> None:
    definitions = default_section_definitions()
    state = {
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        crossbeam_pages.CB_LENGTH_KEY: 20.0,
        crossbeam_pages.CB_SEGMENT_ROWS_KEY: _unknown_zone(),
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: CONSTRUCTION_METHOD_CIP,
        crossbeam_pages.CB_CONSTRUCTION_METHOD_LAST_KEY: CONSTRUCTION_METHOD_CIP,
    }
    monkeypatch.setattr(crossbeam_pages, "st", SimpleNamespace(session_state=state))

    normalized, errors = crossbeam_pages._validate_segments(_unknown_zone(), 20.0)

    assert normalized[0]["Section ID"] == UNKNOWN_SECTION_ID
    assert any("valid Crossbeam Section ID" in error for error in errors)


def test_project_json_round_trip_keeps_unknown_id_for_post_load_review() -> None:
    definitions = default_section_definitions()
    state = {
        "project_name": "CIP1C unknown Section ID QA",
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        crossbeam_pages.CB_LENGTH_KEY: 20.0,
        crossbeam_pages.CB_SEGMENT_ROWS_KEY: _unknown_zone(),
        crossbeam_pages.CB_CIP_ZONE_ROWS_KEY: _unknown_zone(),
        crossbeam_pages.CB_PRECAST_SEGMENT_ROWS_KEY: [],
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: CONSTRUCTION_METHOD_CIP,
        crossbeam_pages.CB_CONSTRUCTION_METHOD_LAST_KEY: CONSTRUCTION_METHOD_CIP,
    }

    restored: dict[str, object] = {}
    project = project_from_session_state(state)
    apply_project_to_session_state(project_from_json(project_to_json(project)), restored)

    assert restored[crossbeam_pages.CB_SEGMENT_ROWS_KEY][0]["Section ID"] == UNKNOWN_SECTION_ID
    assert restored[crossbeam_pages.CB_CIP_ZONE_ROWS_KEY][0]["Section ID"] == UNKNOWN_SECTION_ID
