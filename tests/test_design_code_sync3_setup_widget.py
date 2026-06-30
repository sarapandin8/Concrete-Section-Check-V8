from __future__ import annotations

from concrete_pmm_pro.core.design_code import PROJECT_CODE_AASHTO_LRFD, PROJECT_CODE_ACI318
from concrete_pmm_pro.ui.project_page import (
    _PROJECT_CODE_EDITION_WIDGET_SYNC_KEY,
    _PROJECT_DESIGN_CODE_WIDGET_SYNC_KEY,
    _ensure_project_default_state,
    _sync_setup_design_code_widget_state_before_render,
)


def test_setup_design_code_widget_change_is_promoted_before_selectbox_render() -> None:
    state = {
        "project_design_code": "ACI 318",
        "project_code_edition": "ACI 318-19",
        "design_code": "AASHTO LRFD",
        "code_edition": "AASHTO LRFD 9th Edition",
        _PROJECT_DESIGN_CODE_WIDGET_SYNC_KEY: "ACI 318",
        _PROJECT_CODE_EDITION_WIDGET_SYNC_KEY: "ACI 318-19",
    }

    _ensure_project_default_state(state)
    code, edition = _sync_setup_design_code_widget_state_before_render(
        state,
        member_type="column_pier_pmm",
    )

    assert code == PROJECT_CODE_AASHTO_LRFD
    assert edition == "AASHTO LRFD 9th Edition"
    assert state["project_design_code"] == PROJECT_CODE_AASHTO_LRFD
    assert state["design_code"] == PROJECT_CODE_AASHTO_LRFD


def test_setup_design_code_durable_key_still_overrides_stale_legacy_widget_after_navigation() -> None:
    state = {
        "project_design_code": "AASHTO LRFD",
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "design_code": "ACI 318",
        "code_edition": "ACI 318-19",
        _PROJECT_DESIGN_CODE_WIDGET_SYNC_KEY: "ACI 318",
        _PROJECT_CODE_EDITION_WIDGET_SYNC_KEY: "ACI 318-19",
    }

    _ensure_project_default_state(state)
    code, edition = _sync_setup_design_code_widget_state_before_render(
        state,
        member_type="column_pier_pmm",
    )

    assert code == PROJECT_CODE_AASHTO_LRFD
    assert edition == "AASHTO LRFD 9th Edition"
    assert state["project_design_code"] == PROJECT_CODE_AASHTO_LRFD
    assert state["design_code"] == PROJECT_CODE_AASHTO_LRFD


def test_setup_design_code_widget_change_to_aci_is_promoted_from_previous_aashto_render() -> None:
    state = {
        "project_design_code": "AASHTO LRFD",
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "design_code": "ACI 318",
        "code_edition": "ACI 318-19",
        _PROJECT_DESIGN_CODE_WIDGET_SYNC_KEY: "AASHTO LRFD",
        _PROJECT_CODE_EDITION_WIDGET_SYNC_KEY: "AASHTO LRFD 9th Edition",
    }

    _ensure_project_default_state(state)
    code, edition = _sync_setup_design_code_widget_state_before_render(
        state,
        member_type="column_pier_pmm",
    )

    assert code == PROJECT_CODE_ACI318
    assert edition == "ACI 318-19"
    assert state["project_design_code"] == PROJECT_CODE_ACI318
    assert state["design_code"] == PROJECT_CODE_ACI318
