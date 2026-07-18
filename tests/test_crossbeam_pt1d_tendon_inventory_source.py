from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import (
    CB_ACTIVE_TENDONS_KEY,
    CB_PROFILE_REV_KEY,
    CB_PROFILE_ROWS_KEY,
    CB_TENDON_COUNT_KEY,
    CB_TENDON_PROJECT_LOAD_VALIDATION_KEY,
    CB_TENDON_SYSTEM_REV_KEY,
    CB_TENDON_SYSTEM_ROWS_KEY,
    CROSSBEAM_TENDON_METADATA_KEY,
    CROSSBEAM_TENDON_SCHEMA_VERSION,
    restore_crossbeam_tendon_project_state,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui.crossbeam_pages import (
    CB_LENGTH_KEY,
    CB_TENDON_MAX_COUNT,
    CB_TENDON_MIN_COUNT,
    _add_crossbeam_tendon,
    _remove_crossbeam_tendon,
    render_crossbeam_tendon_system_page,
)


def _state(tendon_count: int = 8) -> dict[str, object]:
    system = default_tendon_system_rows(tendon_count)
    tendon_ids = [str(row["Tendon ID"]) for row in system]
    return {
        CB_LENGTH_KEY: 20.0,
        CB_TENDON_COUNT_KEY: len(system),
        CB_TENDON_SYSTEM_ROWS_KEY: system,
        CB_PROFILE_ROWS_KEY: default_tendon_profile_points(
            20.0,
            tendon_ids=tendon_ids,
            width_mm=2500.0,
            height_mm=1500.0,
        ),
        CB_ACTIVE_TENDONS_KEY: tendon_ids,
        CB_TENDON_SYSTEM_REV_KEY: 2,
        CB_PROFILE_REV_KEY: 7,
    }


def test_pt1d_add_appends_one_complete_tendon_and_three_linked_points() -> None:
    state = _state()
    original_system = deepcopy(state[CB_TENDON_SYSTEM_ROWS_KEY])
    original_profile = deepcopy(state[CB_PROFILE_ROWS_KEY])

    notice = _add_crossbeam_tendon(
        state,
        length_m=20.0,
        width_mm=2500.0,
        height_mm=1500.0,
    )

    assert notice == {
        "action": "added",
        "tendon_id": "T9",
        "stored_count": 9,
        "profile_points": 3,
    }
    assert state[CB_TENDON_COUNT_KEY] == 9
    assert len(state[CB_TENDON_SYSTEM_ROWS_KEY]) == 9
    assert state[CB_TENDON_SYSTEM_ROWS_KEY][:8] == original_system
    assert state[CB_TENDON_SYSTEM_ROWS_KEY][-1]["Tendon ID"] == "T9"
    assert state[CB_TENDON_SYSTEM_ROWS_KEY][-1]["Active"] is True
    assert len(state[CB_PROFILE_ROWS_KEY]) == len(original_profile) + 3
    assert len(
        [row for row in state[CB_PROFILE_ROWS_KEY] if row["Tendon ID"] == "T9"]
    ) == 3
    assert "T9" in state[CB_ACTIVE_TENDONS_KEY]
    assert state[CB_TENDON_SYSTEM_REV_KEY] == 3
    assert state[CB_PROFILE_REV_KEY] == 8


def test_pt1d_add_does_not_reuse_an_orphaned_profile_tendon_id() -> None:
    state = _state()
    state[CB_PROFILE_ROWS_KEY] = [
        *state[CB_PROFILE_ROWS_KEY],
        *default_tendon_profile_points(
            20.0,
            tendon_ids=["T9"],
            width_mm=2500.0,
            height_mm=1500.0,
        ),
    ]

    notice = _add_crossbeam_tendon(
        state,
        length_m=20.0,
        width_mm=2500.0,
        height_mm=1500.0,
    )

    assert notice["tendon_id"] == "T10"
    assert state[CB_TENDON_SYSTEM_ROWS_KEY][-1]["Tendon ID"] == "T10"


def test_pt1d_remove_deletes_one_tendon_and_all_linked_profile_points() -> None:
    state = _state(4)

    notice = _remove_crossbeam_tendon(state, "T4")

    assert notice == {
        "action": "removed",
        "tendon_id": "T4",
        "stored_count": 3,
        "profile_points": 3,
    }
    assert state[CB_TENDON_COUNT_KEY] == 3
    assert [row["Tendon ID"] for row in state[CB_TENDON_SYSTEM_ROWS_KEY]] == [
        "T1",
        "T2",
        "T3",
    ]
    assert all(row["Tendon ID"] != "T4" for row in state[CB_PROFILE_ROWS_KEY])
    assert state[CB_ACTIVE_TENDONS_KEY] == ["T1", "T2", "T3"]
    assert state[CB_TENDON_SYSTEM_REV_KEY] == 3
    assert state[CB_PROFILE_REV_KEY] == 8


def test_pt1d_remove_preserves_minimum_three_tendons() -> None:
    state = _state(CB_TENDON_MIN_COUNT)
    before = deepcopy(state)

    with pytest.raises(ValueError, match="At least 3 stored tendons"):
        _remove_crossbeam_tendon(state, "T3")

    assert state == before


def test_pt1d_remove_refuses_ambiguous_duplicate_id() -> None:
    state = _state()
    state[CB_TENDON_SYSTEM_ROWS_KEY][3]["Tendon ID"] = "T3"
    before = deepcopy(state)

    with pytest.raises(ValueError, match="one unique stored Tendon ID"):
        _remove_crossbeam_tendon(state, "T3")

    assert state == before


def test_pt1d_add_preserves_inventory_limit() -> None:
    state = _state(CB_TENDON_MAX_COUNT)
    before = deepcopy(state)

    with pytest.raises(ValueError, match="limited to 64 stored tendons"):
        _add_crossbeam_tendon(
            state,
            length_m=20.0,
            width_mm=2500.0,
            height_mm=1500.0,
        )

    assert state == before


def test_pt1d_tendon_system_page_has_no_independent_count_editor() -> None:
    source = inspect.getsource(render_crossbeam_tendon_system_page)

    assert '"Number of tendons"' not in source
    assert "st.number_input" not in source
    assert '"Stored tendons"' in source
    assert '"Active tendons"' in source
    assert '"Add tendon"' in source
    assert '"Review removal"' in source
    assert "_confirm_crossbeam_tendon_removal" in source
    assert "st.session_state[CB_TENDON_COUNT_KEY] = len(rows)" in source


def test_pt1d_project_restore_derives_count_from_incomplete_stored_rows() -> None:
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), definitions
    )
    incomplete_system = default_tendon_system_rows(3)[:2]
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=["T1", "T2"],
        width_mm=2500.0,
        height_mm=1500.0,
    )
    metadata = {
        CROSSBEAM_TENDON_METADATA_KEY: {
            "schema_version": CROSSBEAM_TENDON_SCHEMA_VERSION,
            "tendon_system": incomplete_system,
            "profile_points": profile,
        }
    }
    restored: dict[str, object] = {}

    validation = restore_crossbeam_tendon_project_state(
        metadata,
        restored,
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
    )

    assert len(restored[CB_TENDON_SYSTEM_ROWS_KEY]) == 2
    assert restored[CB_TENDON_COUNT_KEY] == 2
    assert validation is restored[CB_TENDON_PROJECT_LOAD_VALIDATION_KEY]
    assert validation["tendon_count"] == 2
    assert validation["status"] == "REVIEW REQUIRED"
    assert any("more than two tendon rows" in item for item in validation["errors"])
