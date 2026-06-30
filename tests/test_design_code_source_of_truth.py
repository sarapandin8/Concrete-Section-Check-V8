from __future__ import annotations

import json
import re
from pathlib import Path

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.design_code import (
    PROJECT_CODE_AASHTO_LRFD,
    PROJECT_CODE_ACI318,
    default_code_edition_for,
    girder_sls_code_for_project_code,
    normalize_project_code_edition,
    normalize_project_design_code,
    project_code_capability_cards,
    project_code_edition_from_session,
    project_design_code_from_session,
    sync_project_design_code_to_session,
    workflow_project_code_edition_from_session,
    workflow_project_code_label_from_session,
    workflow_project_design_code_from_session,
)
from concrete_pmm_pro.core.project import ProjectModel
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_session_state, project_to_json
from concrete_pmm_pro.ui.project_page import _project_design_code_cards

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
ANALYSIS_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "analysis_page.py").read_text(encoding="utf-8")
PRESTRESS_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "prestress_page.py").read_text(encoding="utf-8")
PROJECT_SOURCE = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "project_page.py").read_text(encoding="utf-8")


def test_project_design_code_normalization_and_girder_profile_mapping() -> None:
    assert normalize_project_design_code("AASHTO LRFD Bridge") == PROJECT_CODE_AASHTO_LRFD
    assert normalize_project_design_code("ACI318") == PROJECT_CODE_ACI318
    assert girder_sls_code_for_project_code("AASHTO LRFD") == "AASHTO LRFD Bridge"
    assert girder_sls_code_for_project_code("ACI 318") == "ACI 318"
    assert default_code_edition_for("AASHTO") == "AASHTO LRFD 9th Edition"
    assert normalize_project_code_edition("AASHTO LRFD", "bad edition") == "AASHTO LRFD 9th Edition"


def test_project_model_and_io_preserve_code_and_edition() -> None:
    project = ProjectModel(code="AASHTO LRFD Bridge", code_edition="AASHTO LRFD 9th Edition")
    assert project.code == PROJECT_CODE_AASHTO_LRFD
    assert project.code_edition == "AASHTO LRFD 9th Edition"

    parsed = json.loads(project_to_json(project))
    assert parsed["code"] == PROJECT_CODE_AASHTO_LRFD
    assert parsed["code_edition"] == "AASHTO LRFD 9th Edition"

    session: dict[str, object] = {"design_code": "AASHTO LRFD", "code_edition": "AASHTO LRFD 9th Edition"}
    saved = project_from_session_state(session)
    assert saved.code == PROJECT_CODE_AASHTO_LRFD
    assert saved.code_edition == "AASHTO LRFD 9th Edition"

    restored: dict[str, object] = {}
    apply_project_to_session_state(saved, restored)
    assert restored["design_code"] == PROJECT_CODE_AASHTO_LRFD
    assert restored["code_edition"] == "AASHTO LRFD 9th Edition"



def test_design_code_state1_durable_key_survives_navigation_after_setup_widget_unmount() -> None:
    # Streamlit can remove widget-owned keys (design_code/code_edition) when
    # Setup is no longer rendered.  Analysis must still read the durable project
    # keys created by the Setup selector.
    analysis_state = {
        "project_design_code": "AASHTO LRFD",
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "analysis_mode_settings": AnalysisModeSettings(member_type="column_pier_pmm"),
    }

    assert project_design_code_from_session(analysis_state) == PROJECT_CODE_AASHTO_LRFD
    assert project_code_edition_from_session(analysis_state) == "AASHTO LRFD 9th Edition"
    assert workflow_project_design_code_from_session(analysis_state) == PROJECT_CODE_AASHTO_LRFD
    assert workflow_project_code_edition_from_session(analysis_state) == "AASHTO LRFD 9th Edition"


def test_design_code_state1_durable_key_wins_over_stale_setup_widget_key() -> None:
    # This mirrors the observed bug: Setup visually selected AASHTO, but Analysis
    # still saw a stale legacy/widget ACI key.  Durable project code must win.
    state = {
        "project_design_code": "AASHTO LRFD",
        "project_code_edition": "AASHTO LRFD 9th Edition",
        "design_code": "ACI 318",
        "code_edition": "ACI 318-19",
        "analysis_mode_settings": AnalysisModeSettings(member_type="column_pier_pmm"),
    }

    assert workflow_project_design_code_from_session(state) == PROJECT_CODE_AASHTO_LRFD
    assert workflow_project_code_edition_from_session(state) == "AASHTO LRFD 9th Edition"
    saved = project_from_session_state(state)
    assert saved.code == PROJECT_CODE_AASHTO_LRFD
    assert saved.code_edition == "AASHTO LRFD 9th Edition"


def test_design_code_state1_setup_sync_writes_durable_and_legacy_before_widget_creation() -> None:
    state = {"analysis_mode_settings": AnalysisModeSettings(member_type="column_pier_pmm")}
    code, edition = sync_project_design_code_to_session(
        state,
        member_type="column_pier_pmm",
        selected_code="AASHTO LRFD",
        selected_edition="AASHTO LRFD 9th Edition",
    )

    assert code == PROJECT_CODE_AASHTO_LRFD
    assert edition == "AASHTO LRFD 9th Edition"
    assert state["project_design_code"] == PROJECT_CODE_AASHTO_LRFD
    assert state["project_code_edition"] == "AASHTO LRFD 9th Edition"
    assert state["design_code"] == PROJECT_CODE_AASHTO_LRFD
    assert state["code_edition"] == "AASHTO LRFD 9th Edition"

def test_project_design_code_cards_flag_aashto_pmm_as_available_review() -> None:
    cards = _project_design_code_cards(
        ProjectModel(code="AASHTO LRFD", code_edition="AASHTO LRFD 9th Edition"),
        AnalysisModeSettings(member_type="column_pier_pmm"),
    )
    by_title = {card.title: card for card in cards}

    assert by_title["Design Code"].value == PROJECT_CODE_AASHTO_LRFD
    assert by_title["Column/Pier PMM"].value == "AVAILABLE / REVIEW"
    assert by_title["Column/Pier PMM"].status == "ready"


def test_code_capability_helper_exposes_aashto_pmm_with_remaining_guards() -> None:
    cards = project_code_capability_cards("AASHTO LRFD", "column_pier_pmm")
    by_title = {card["title"]: card for card in cards}

    assert by_title["Column/Pier PMM"]["value"] == "AVAILABLE / REVIEW"
    assert "B-region axial-flexure" in by_title["Column/Pier PMM"]["detail"]
    assert "shear" in by_title["Column/Pier PMM"]["detail"]


def test_code_setup1_source_files_have_project_code_guardrails() -> None:
    assert "Project-level source of truth" in PROJECT_SOURCE
    assert "Project Design Code / Capability Guard" in PROJECT_SOURCE
    assert "Project code profile" in ANALYSIS_SOURCE
    assert "project-code preview stress-limit profile" in ANALYSIS_SOURCE
    assert "Workflow-enforced from active Analysis Mode" in ANALYSIS_SOURCE
    assert "_girder_sls_project_design_code_from_session" in ANALYSIS_SOURCE
    assert "Project Design Code is AASHTO LRFD" in ANALYSIS_SOURCE
    assert "AASHTO LRFD 9th PMM" in ANALYSIS_SOURCE
    assert "Prestress loss code basis" in PRESTRESS_SOURCE
    assert "Prestress loss basis differs from Project Design Code" in PRESTRESS_SOURCE
    assert "ACI 318 / PCI-style approximate loss basis selected" in PRESTRESS_SOURCE


def test_workflow_type2_filters_project_design_code_by_workflow() -> None:
    bridge = ProjectModel(
        code="ACI 318",
        code_edition="ACI 318-19",
        analysis_mode_settings=AnalysisModeSettings(member_type="beam_girder"),
    )
    assert bridge.code == PROJECT_CODE_AASHTO_LRFD
    assert bridge.code_edition == "AASHTO LRFD 9th Edition"

    building = ProjectModel(
        code="AASHTO LRFD",
        code_edition="AASHTO LRFD 9th Edition",
        analysis_mode_settings=AnalysisModeSettings(member_type="building_beam_girder"),
    )
    assert building.code == PROJECT_CODE_ACI318
    assert building.code_edition == "ACI 318-19"

    column = ProjectModel(
        code="AASHTO LRFD",
        code_edition="AASHTO LRFD 9th Edition",
        analysis_mode_settings=AnalysisModeSettings(member_type="column_pier_pmm"),
    )
    assert column.code == PROJECT_CODE_AASHTO_LRFD


def test_project_page_source_has_workflow_aware_design_code_routing() -> None:
    assert "allowed_project_design_codes_for_workflow" in PROJECT_SOURCE
    assert "Bridge Beam/Girder is AASHTO LRFD only" in PROJECT_SOURCE
    assert "Building Beam/Girder is ACI 318 only" in PROJECT_SOURCE
    assert 'if analysis_mode.member_type == "beam_girder"' in PROJECT_SOURCE
    assert 'elif analysis_mode.member_type == "building_beam_girder"' in PROJECT_SOURCE


def test_design_code_route1_chrome_and_analysis_use_workflow_compatible_code_when_session_is_stale() -> None:
    stale_bridge_session = {
        "design_code": "ACI 318",
        "code_edition": "ACI 318-19",
        "analysis_mode_settings": AnalysisModeSettings(member_type="beam_girder"),
    }
    assert workflow_project_design_code_from_session(stale_bridge_session) == PROJECT_CODE_AASHTO_LRFD
    assert workflow_project_code_edition_from_session(stale_bridge_session) == "AASHTO LRFD 9th Edition"
    assert workflow_project_code_label_from_session(stale_bridge_session) == "AASHTO LRFD 9th Edition"

    stale_building_session = {
        "design_code": "AASHTO LRFD",
        "code_edition": "AASHTO LRFD 9th Edition",
        "analysis_mode_settings": {"member_type": "building_beam_girder"},
    }
    assert workflow_project_design_code_from_session(stale_building_session) == PROJECT_CODE_ACI318
    assert workflow_project_code_edition_from_session(stale_building_session) == "ACI 318-19"


def test_design_code_route1_source_uses_workflow_compatible_code_in_global_chrome_and_analysis_cards() -> None:
    assert "workflow_project_code_label_from_session" in APP_SOURCE
    assert "workflow_project_design_code_from_session" in ANALYSIS_SOURCE
    assert "workflow_project_design_code_from_session" in PRESTRESS_SOURCE
    assert 'return workflow_project_code_label_from_session(st.session_state)' in APP_SOURCE
    assert 'code = workflow_project_design_code_from_session(st.session_state)' in ANALYSIS_SOURCE
    assert 'return workflow_project_design_code_from_session(st.session_state)' in PRESTRESS_SOURCE


def test_design_code_route2_column_pier_preserves_selected_aashto_in_analysis_guards() -> None:
    column_aashto_session = {
        "design_code": "AASHTO LRFD",
        "code_edition": "AASHTO LRFD 9th Edition",
        "analysis_mode_settings": AnalysisModeSettings(member_type="column_pier_pmm"),
    }
    assert workflow_project_design_code_from_session(column_aashto_session) == PROJECT_CODE_AASHTO_LRFD
    assert workflow_project_code_edition_from_session(column_aashto_session) == "AASHTO LRFD 9th Edition"

    assert "workflow_project_code_edition_from_session" in ANALYSIS_SOURCE
    assert "code = workflow_project_design_code_from_session(st.session_state)" in ANALYSIS_SOURCE
    assert "AASHTO LRFD 9th Section 5.7 simplified shear route" in ANALYSIS_SOURCE
    assert "PMM, simplified shear, and scoped torsion routes are AASHTO-based" in ANALYSIS_SOURCE
    assert "AASHTO.COL.VT1" in ANALYSIS_SOURCE
    assert "AASHTO LRFD 9th Section 5.7.3.6 scoped nonprestressed V+T gate" in ANALYSIS_SOURCE


def test_design_code_route2_analysis_page_no_longer_reads_raw_project_code_for_column_pier_cards() -> None:
    guarded_region = ANALYSIS_SOURCE[
        ANALYSIS_SOURCE.index("def _project_design_code_status_cards"):
        ANALYSIS_SOURCE.index("def _render_analysis_summary_strip", ANALYSIS_SOURCE.index("def _project_design_code_status_cards"))
    ]
    assert not re.search(r"(?<!workflow_)project_design_code_from_session\\(st\\.session_state\\)", guarded_region)
    assert not re.search(r"(?<!workflow_)project_code_edition_from_session\\(st\\.session_state\\)", guarded_region)
    assert "workflow_project_design_code_from_session(st.session_state)" in guarded_region
    assert "workflow_project_code_edition_from_session(st.session_state)" in guarded_region
