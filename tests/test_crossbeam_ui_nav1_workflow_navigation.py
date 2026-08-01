from __future__ import annotations

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.project import ProjectModel
from concrete_pmm_pro.io.project_io import apply_project_to_session_state
from concrete_pmm_pro.ui.navigation import (
    ANALYSIS_SUBPAGES,
    analysis_subpages_for_session,
    resolve_analysis_mode_settings,
)


SLS_STRESS = "SLS / Stress & Cracking"


def test_crossbeam_object_state_keeps_sls_stress_available_after_rerun() -> None:
    state: dict[str, object] = {
        "analysis_mode_settings": AnalysisModeSettings(member_type="portal_frame_crossbeam"),
        "_nav_analysis_subpage": SLS_STRESS,
    }

    first = analysis_subpages_for_session(state)
    second = analysis_subpages_for_session(state)

    assert first == list(ANALYSIS_SUBPAGES)
    assert second == first
    assert state["_nav_analysis_subpage"] == SLS_STRESS


def test_crossbeam_dict_state_keeps_sls_stress_available() -> None:
    state: dict[str, object] = {
        "analysis_mode_settings": {"member_type": "portal_frame_crossbeam"},
        "_nav_analysis_subpage": SLS_STRESS,
    }

    assert SLS_STRESS in analysis_subpages_for_session(state)
    assert resolve_analysis_mode_settings(state).member_type == "portal_frame_crossbeam"


def test_missing_canonical_mode_recovers_crossbeam_from_project_selector_sync() -> None:
    state: dict[str, object] = {
        "project_analysis_mode_member_type_sync": "portal_frame_crossbeam",
        "project_analysis_mode_member_type_label": "Portal Frame Crossbeam — Prestressed Concrete",
        "_nav_analysis_subpage": SLS_STRESS,
    }

    assert SLS_STRESS in analysis_subpages_for_session(state)
    assert state["analysis_mode_settings"] == AnalysisModeSettings(member_type="portal_frame_crossbeam")


def test_canonical_mode_wins_over_stale_selector_fallback() -> None:
    state: dict[str, object] = {
        "analysis_mode_settings": AnalysisModeSettings(member_type="column_pier_pmm"),
        "project_analysis_mode_member_type_sync": "portal_frame_crossbeam",
        "project_analysis_mode_member_type_label": "Portal Frame Crossbeam — Prestressed Concrete",
    }

    assert analysis_subpages_for_session(state) == ["ULS Strength"]
    assert resolve_analysis_mode_settings(state).member_type == "column_pier_pmm"


def test_project_json_restore_routes_from_restored_canonical_crossbeam_mode() -> None:
    state: dict[str, object] = {
        "project_analysis_mode_member_type_sync": "column_pier_pmm",
        "project_analysis_mode_member_type_label": "Column / Pier / Wall / Pylon — RC / Prestressed Member",
    }
    project = ProjectModel(
        project_name="NAV1 restore",
        analysis_mode_settings=AnalysisModeSettings(member_type="portal_frame_crossbeam"),
    )

    apply_project_to_session_state(project, state)

    assert resolve_analysis_mode_settings(state).member_type == "portal_frame_crossbeam"
    assert SLS_STRESS in analysis_subpages_for_session(state)


def test_column_pier_never_exposes_sls_subpages() -> None:
    state = {"analysis_mode_settings": {"member_type": "column_pier_pmm"}}

    assert analysis_subpages_for_session(state) == ["ULS Strength"]


def test_navigation_resolution_does_not_mutate_engineering_result_or_input_keys() -> None:
    state: dict[str, object] = {
        "project_analysis_mode_member_type_sync": "portal_frame_crossbeam",
        "_nav_analysis_subpage": SLS_STRESS,
        "crossbeam_sls1a_transfer_result": {"status": "FAIL"},
        "crossbeam_sls_loads_table": [{"P": 5000.0, "M3": 0.0}],
    }
    result_before = state["crossbeam_sls1a_transfer_result"]
    loads_before = state["crossbeam_sls_loads_table"]

    analysis_subpages_for_session(state)

    assert state["crossbeam_sls1a_transfer_result"] is result_before
    assert state["crossbeam_sls_loads_table"] is loads_before
