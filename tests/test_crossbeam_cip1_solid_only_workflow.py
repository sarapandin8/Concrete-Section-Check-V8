from __future__ import annotations

from types import SimpleNamespace

from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    CONSTRUCTION_METHOD_PRECAST,
)
from concrete_pmm_pro.crossbeam.section_library import default_section_definitions, migrate_segment_rows_to_library
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json, project_from_session_state, project_to_json
from concrete_pmm_pro.ui import crossbeam_pages


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
    }


def test_switching_to_cip_preserves_precast_and_seeds_one_full_length_solid_zone(monkeypatch) -> None:
    state = _state()
    monkeypatch.setattr(crossbeam_pages, "st", SimpleNamespace(session_state=state))

    original = list(state[crossbeam_pages.CB_SEGMENT_ROWS_KEY])
    state[crossbeam_pages.CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] = CONSTRUCTION_METHOD_CIP
    method = crossbeam_pages._sync_layout_state_for_construction_method(20.0)

    assert method == CONSTRUCTION_METHOD_CIP
    assert state[crossbeam_pages.CB_PRECAST_SEGMENT_ROWS_KEY] == original
    rows = state[crossbeam_pages.CB_SEGMENT_ROWS_KEY]
    assert len(rows) == 1
    assert rows[0]["Segment"] == "Z1"
    assert rows[0]["x_start_m"] == 0.0
    assert rows[0]["x_end_m"] == 20.0
    assert rows[0]["Section role"] == "Solid"


def test_switching_back_restores_original_precast_layout(monkeypatch) -> None:
    state = _state()
    monkeypatch.setattr(crossbeam_pages, "st", SimpleNamespace(session_state=state))
    original = list(state[crossbeam_pages.CB_SEGMENT_ROWS_KEY])

    state[crossbeam_pages.CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] = CONSTRUCTION_METHOD_CIP
    crossbeam_pages._sync_layout_state_for_construction_method(20.0)
    state[crossbeam_pages.CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] = CONSTRUCTION_METHOD_PRECAST
    crossbeam_pages._sync_layout_state_for_construction_method(20.0)

    assert state[crossbeam_pages.CB_SEGMENT_ROWS_KEY] == original


def test_cip_elevation_hides_hollow_legend_and_uses_zone_title() -> None:
    definitions = default_section_definitions()
    rows = crossbeam_pages._default_cip_zone_rows(20.0, definitions)
    fig = crossbeam_pages._elevation_figure(rows, 20.0, [], cast_in_place=True)

    names = [str(trace.name) for trace in fig.data]
    assert "Solid section zone" in names
    assert "Hollow segment" not in names
    assert "Hidden void boundary" not in names
    assert "Section / Zone Elevation" in str(fig.layout.title.text)


def test_project_json_round_trip_preserves_both_construction_layouts() -> None:
    state = _state()
    definitions = state["crossbeam_seclib1_section_definitions"]
    state[crossbeam_pages.CB_PRECAST_SEGMENT_ROWS_KEY] = list(state[crossbeam_pages.CB_SEGMENT_ROWS_KEY])
    state[crossbeam_pages.CB_CIP_ZONE_ROWS_KEY] = crossbeam_pages._default_cip_zone_rows(20.0, definitions)
    state[crossbeam_pages.CB_CONSTRUCTION_METHOD_LAST_KEY] = CONSTRUCTION_METHOD_CIP

    restored: dict[str, object] = {}
    project = project_from_session_state(state)
    apply_project_to_session_state(project_from_json(project_to_json(project)), restored)

    assert restored[crossbeam_pages.CB_PRECAST_SEGMENT_ROWS_KEY] == state[crossbeam_pages.CB_PRECAST_SEGMENT_ROWS_KEY]
    assert restored[crossbeam_pages.CB_CIP_ZONE_ROWS_KEY] == state[crossbeam_pages.CB_CIP_ZONE_ROWS_KEY]
    assert restored[crossbeam_pages.CB_CONSTRUCTION_METHOD_LAST_KEY] == CONSTRUCTION_METHOD_CIP


def test_member_length_scale_updates_both_preserved_layout_namespaces() -> None:
    state = _state()
    definitions = state["crossbeam_seclib1_section_definitions"]
    state[crossbeam_pages.CB_PRECAST_SEGMENT_ROWS_KEY] = list(state[crossbeam_pages.CB_SEGMENT_ROWS_KEY])
    state[crossbeam_pages.CB_CIP_ZONE_ROWS_KEY] = crossbeam_pages._default_cip_zone_rows(20.0, definitions)
    state[crossbeam_pages.CB_PROFILE_ROWS_KEY] = []

    crossbeam_pages._apply_crossbeam_member_length_change(
        state,
        30.0,
        crossbeam_pages.CB_LENGTH_POLICY_SCALE,
    )

    assert state[crossbeam_pages.CB_PRECAST_SEGMENT_ROWS_KEY][-1]["x_end_m"] == 30.0
    assert state[crossbeam_pages.CB_CIP_ZONE_ROWS_KEY][0]["x_end_m"] == 30.0
