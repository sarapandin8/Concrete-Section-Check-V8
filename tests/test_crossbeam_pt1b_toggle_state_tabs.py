from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui.crossbeam_pages import (
    CB_LENGTH_KEY,
    CB_LENGTH_REPAIR_NOTICE_KEY,
    CB_LENGTH_WIDGET_KEY,
    CB_PROFILE_ROWS_KEY,
    CB_SEGMENT_ROWS_KEY,
    _coherent_geometry_extent_m,
    _repair_stale_crossbeam_length_state,
)


def _twenty_metre_geometry() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), definitions
    )
    tendon_ids = [row["Tendon ID"] for row in default_tendon_system_rows()]
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=tendon_ids,
        width_mm=2500.0,
        height_mm=1500.0,
    )
    return segments, profile


def test_pt1b_recovers_only_stale_minimum_length_from_matching_geometry() -> None:
    segments, profile = _twenty_metre_geometry()
    original_segments = deepcopy(segments)
    original_profile = deepcopy(profile)
    state: dict[str, object] = {
        CB_LENGTH_KEY: 0.1,
        CB_SEGMENT_ROWS_KEY: segments,
        CB_PROFILE_ROWS_KEY: profile,
    }

    repaired = _repair_stale_crossbeam_length_state(state)

    assert repaired == 20.0
    assert state[CB_LENGTH_KEY] == 20.0
    assert "No geometry coordinates were changed" in str(
        state[CB_LENGTH_REPAIR_NOTICE_KEY]
    )
    assert segments == original_segments
    assert profile == original_profile
    assert _repair_stale_crossbeam_length_state(state) is None


def test_pt1b_does_not_infer_length_when_profile_endpoint_disagrees() -> None:
    segments, profile = _twenty_metre_geometry()
    profile[-1]["s (m)"] = 19.5
    state: dict[str, object] = {
        CB_LENGTH_KEY: 0.1,
        CB_SEGMENT_ROWS_KEY: segments,
        CB_PROFILE_ROWS_KEY: profile,
    }

    assert _coherent_geometry_extent_m(segments, profile) is None
    assert _repair_stale_crossbeam_length_state(state) is None
    assert state[CB_LENGTH_KEY] == 0.1


def test_pt1b_uses_separate_transient_length_widget_and_react_aria_tab_theme() -> None:
    page_source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(
        encoding="utf-8"
    )
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert f"key={CB_LENGTH_WIDGET_KEY}" not in page_source
    assert "key=CB_LENGTH_WIDGET_KEY" in page_source
    assert "the sole editable Crossbeam member-length control" in page_source
    assert "3D display only" in page_source
    assert '"not change geometry, tendon inputs, validation, or analysis."' in page_source
    assert 'div[data-testid="stTabs"] [role="tab"]' in app_source
    assert 'div[data-testid="stTabs"] div[data-testid="stTab"]' in app_source
    assert '[data-selected="true"]' in app_source
