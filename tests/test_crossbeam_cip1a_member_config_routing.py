from __future__ import annotations

import inspect
from types import SimpleNamespace

from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    CONSTRUCTION_METHOD_PRECAST,
)
from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui import crossbeam_pages, section_builder
from concrete_pmm_pro.ui.crossbeam_section_library import _applicable_section_definitions


def _state() -> dict[str, object]:
    definitions = default_section_definitions()
    return {
        crossbeam_pages.CB_LENGTH_KEY: 20.0,
        "crossbeam_seclib1_section_definitions": definitions,
        crossbeam_pages.CB_SEGMENT_ROWS_KEY: migrate_segment_rows_to_library(
            default_crossbeam_segment_rows(20.0), definitions
        ),
        crossbeam_pages.CB_SEGMENT_REV_KEY: 0,
        crossbeam_pages.CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: CONSTRUCTION_METHOD_PRECAST,
        crossbeam_pages.CB_CONSTRUCTION_METHOD_LAST_KEY: CONSTRUCTION_METHOD_PRECAST,
        crossbeam_pages.CB_CONSTRUCTION_METHOD_WIDGET_KEY: CONSTRUCTION_METHOD_CIP,
        crossbeam_pages.CB_CONSTRUCTION_METHOD_WIDGET_SYNC_KEY: CONSTRUCTION_METHOD_PRECAST,
    }


def test_construction_type_widget_commit_routes_canonical_state_and_layout(monkeypatch) -> None:
    state = _state()
    monkeypatch.setattr(crossbeam_pages, "st", SimpleNamespace(session_state=state))

    crossbeam_pages._commit_construction_method_change(20.0)

    assert state[crossbeam_pages.CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] == CONSTRUCTION_METHOD_CIP
    assert state[crossbeam_pages.CB_CONSTRUCTION_METHOD_WIDGET_SYNC_KEY] == CONSTRUCTION_METHOD_CIP
    assert len(state[crossbeam_pages.CB_SEGMENT_ROWS_KEY]) == 1
    assert state[crossbeam_pages.CB_SEGMENT_ROWS_KEY][0]["Segment"] == "Z1"
    assert state[crossbeam_pages.CB_SEGMENT_ROWS_KEY][0]["Section role"] == "Solid"
    assert state[crossbeam_pages.CB_PRECAST_SEGMENT_ROWS_KEY]


def test_construction_type_widget_resyncs_after_external_project_restore(monkeypatch) -> None:
    state = _state()
    state[crossbeam_pages.CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] = CONSTRUCTION_METHOD_CIP
    state[crossbeam_pages.CB_CONSTRUCTION_METHOD_WIDGET_KEY] = CONSTRUCTION_METHOD_PRECAST
    state[crossbeam_pages.CB_CONSTRUCTION_METHOD_WIDGET_SYNC_KEY] = CONSTRUCTION_METHOD_PRECAST
    monkeypatch.setattr(crossbeam_pages, "st", SimpleNamespace(session_state=state))

    resolved = crossbeam_pages._sync_construction_method_widget_from_source()

    assert resolved == CONSTRUCTION_METHOD_CIP
    assert state[crossbeam_pages.CB_CONSTRUCTION_METHOD_WIDGET_KEY] == CONSTRUCTION_METHOD_CIP
    assert state[crossbeam_pages.CB_CONSTRUCTION_METHOD_WIDGET_SYNC_KEY] == CONSTRUCTION_METHOD_CIP


def test_cast_in_place_section_library_exposes_solid_only_without_deleting_hollow() -> None:
    definitions = default_section_definitions()
    applicable = _applicable_section_definitions(definitions, CONSTRUCTION_METHOD_CIP)

    assert applicable
    assert all(row["Section role"] == "Solid" for row in applicable)
    assert any(row["Section role"] == "Hollow" for row in definitions)


def test_member_level_configuration_renders_before_project_section_library() -> None:
    source = inspect.getsource(section_builder.render_section_builder)
    member_index = source.index("_render_crossbeam_member_geometry_workspace(settings)")
    support_index = source.index("_render_crossbeam_construction_support_workspace(settings)")
    library_index = source.index("render_crossbeam_section_library_panel(settings)")

    assert member_index < support_index < library_index
