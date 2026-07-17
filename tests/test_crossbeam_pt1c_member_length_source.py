from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.rebar import (
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
    segment_signature,
)
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_SEGMENT_SIGNATURE_KEY,
    CB_RB_ZONE_REV_KEY,
    CB_RB_ZONE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.section_library import (
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.tendon import (
    default_tendon_profile_points,
    default_tendon_system_rows,
)
from concrete_pmm_pro.crossbeam.transverse import (
    default_crossbeam_transverse_templates,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui.crossbeam_pages import (
    CB_CROSS_SECTION_STATION_KEY,
    CB_LENGTH_KEY,
    CB_LENGTH_POLICY_KEEP,
    CB_LENGTH_POLICY_SCALE,
    CB_PROFILE_REV_KEY,
    CB_PROFILE_ROWS_KEY,
    CB_SEGMENT_REV_KEY,
    CB_SEGMENT_ROWS_KEY,
    _apply_crossbeam_member_length_change,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _twenty_metre_state() -> dict[str, object]:
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), default_section_definitions()
    )
    tendon_ids = [row["Tendon ID"] for row in default_tendon_system_rows()]
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=tendon_ids,
        width_mm=2500.0,
        height_mm=1500.0,
    )
    zones = default_crossbeam_rebar_zones(
        segments,
        default_crossbeam_rebar_templates(),
        default_crossbeam_transverse_templates(),
    )
    return {
        CB_LENGTH_KEY: 20.0,
        CB_SEGMENT_ROWS_KEY: segments,
        CB_PROFILE_ROWS_KEY: profile,
        CB_RB_ZONE_ROWS_KEY: zones,
        CB_RB_SEGMENT_SIGNATURE_KEY: segment_signature(segments),
        CB_CROSS_SECTION_STATION_KEY: 5.0,
        CB_SEGMENT_REV_KEY: 4,
        CB_PROFILE_REV_KEY: 7,
        CB_RB_ZONE_REV_KEY: 2,
    }


def _function_source(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    node = next(
        item
        for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == function_name
    )
    return ast.get_source_segment(source, node) or ""


def test_pt1c_scale_policy_moves_all_longitudinal_station_sources_together() -> None:
    state = _twenty_metre_state()
    original_profile = deepcopy(state[CB_PROFILE_ROWS_KEY])

    notice = _apply_crossbeam_member_length_change(
        state, 30.0, CB_LENGTH_POLICY_SCALE
    )

    assert state[CB_LENGTH_KEY] == 30.0
    assert [row["x_end_m"] for row in state[CB_SEGMENT_ROWS_KEY]][-1] == 30.0
    assert {row["s (m)"] for row in state[CB_PROFILE_ROWS_KEY]} == {
        0.0,
        15.0,
        30.0,
    }
    assert {row["s/L"] for row in state[CB_PROFILE_ROWS_KEY]} == {0.0, 0.5, 1.0}
    assert [row["s_end_m"] for row in state[CB_RB_ZONE_ROWS_KEY]][-1] == 30.0
    assert state[CB_CROSS_SECTION_STATION_KEY] == 7.5
    assert state[CB_RB_SEGMENT_SIGNATURE_KEY] == segment_signature(
        state[CB_SEGMENT_ROWS_KEY]
    )
    assert state[CB_SEGMENT_REV_KEY] == 5
    assert state[CB_PROFILE_REV_KEY] == 8
    assert state[CB_RB_ZONE_REV_KEY] == 3
    assert notice["scaled"] is True
    assert notice["zone_rows"] == len(state[CB_RB_ZONE_ROWS_KEY])

    original_by_point = {
        (row["Tendon ID"], row["Point"]): row for row in original_profile
    }
    for row in state[CB_PROFILE_ROWS_KEY]:
        original = original_by_point[(row["Tendon ID"], row["Point"])]
        assert row["x lateral (mm)"] == original["x lateral (mm)"]
        assert row["dtop (mm)"] == original["dtop (mm)"]


def test_pt1c_keep_policy_changes_l_but_preserves_absolute_station_inputs() -> None:
    state = _twenty_metre_state()
    original_segments = deepcopy(state[CB_SEGMENT_ROWS_KEY])
    original_profile_stations = [
        row["s (m)"] for row in state[CB_PROFILE_ROWS_KEY]
    ]
    original_zones = deepcopy(state[CB_RB_ZONE_ROWS_KEY])

    notice = _apply_crossbeam_member_length_change(
        state, 30.0, CB_LENGTH_POLICY_KEEP
    )

    assert state[CB_LENGTH_KEY] == 30.0
    assert state[CB_SEGMENT_ROWS_KEY] == original_segments
    assert [row["s (m)"] for row in state[CB_PROFILE_ROWS_KEY]] == original_profile_stations
    assert state[CB_RB_ZONE_ROWS_KEY] == original_zones
    assert state[CB_CROSS_SECTION_STATION_KEY] == 5.0
    assert state[CB_RB_ZONE_REV_KEY] == 2
    assert notice["scaled"] is False
    assert max(row["s/L"] for row in state[CB_PROFILE_ROWS_KEY]) == pytest.approx(
        2.0 / 3.0
    )


def test_pt1c_rejects_unknown_length_change_policy() -> None:
    with pytest.raises(ValueError, match="Unsupported Crossbeam length-change policy"):
        _apply_crossbeam_member_length_change(
            _twenty_metre_state(), 25.0, "Silently guess"
        )


def test_pt1c_section_builder_is_sole_length_editor() -> None:
    page_source = (
        REPO_ROOT / "concrete_pmm_pro" / "ui" / "crossbeam_pages.py"
    ).read_text(encoding="utf-8")
    builder_source = (
        REPO_ROOT / "concrete_pmm_pro" / "ui" / "section_builder.py"
    ).read_text(encoding="utf-8")

    member_control = _function_source(
        page_source, "render_crossbeam_member_length_control"
    )
    segment_page = _function_source(
        page_source, "render_crossbeam_segment_layout_page"
    )
    tendon_page = _function_source(
        page_source, "render_crossbeam_tendon_profile_page"
    )
    builder_page = _function_source(builder_source, "render_section_builder")

    assert page_source.count('"Crossbeam total length L (m)"') == 1
    assert "st.number_input" in member_control
    assert "_render_crossbeam_member_length_reference()" in segment_page
    assert "_render_crossbeam_member_length_reference()" in tendon_page
    assert "st.number_input" not in segment_page
    assert "st.number_input" not in tendon_page
    assert "_render_crossbeam_member_geometry_workspace(settings)" in builder_page
    assert builder_page.index("_render_crossbeam_member_geometry_workspace(settings)") < (
        builder_page.index("_render_geometry_parameters_workspace")
    )
    assert "Crossbeam Member Geometry" in builder_source

