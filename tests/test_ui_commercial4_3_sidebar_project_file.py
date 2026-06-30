from __future__ import annotations

from pathlib import Path


def test_ui_commercial4_3_moves_project_file_actions_to_sidebar() -> None:
    app_source = Path("app.py").read_text(encoding="utf-8")
    project_source = Path("concrete_pmm_pro/ui/project_page.py").read_text(encoding="utf-8")

    assert "UI.COMMERCIAL4.3" in app_source
    assert "def _render_sidebar_project_file_actions" in app_source
    assert "st.sidebar.download_button" not in app_source  # actions live inside the sidebar container
    assert "Save Project JSON" in app_source
    assert "Load Project JSON" in app_source
    assert "Apply Loaded Project" in app_source
    assert "project_to_json(project)" in app_source
    assert "apply_project_to_session_state(project, st.session_state)" in app_source
    assert "_render_sidebar_active_context()" in app_source
    assert "_render_sidebar_project_file_actions()" in app_source
    assert "Project file actions moved to the sidebar Project File panel" in project_source
    assert "_render_project_file_actions(project)" not in project_source


def test_ui_commercial4_3_sidebar_status_is_not_duplicate_context() -> None:
    app_source = Path("app.py").read_text(encoding="utf-8")

    sidebar_start = app_source.index("def _render_commercial_sidebar")
    sidebar_body = app_source[sidebar_start: app_source.index("def _render_commercial_brand_header", sidebar_start)]

    assert "current_project_dirty_status" in app_source
    assert "Project Status" in sidebar_body
    assert "Affected Checks" in sidebar_body
    assert "Active Context" in app_source
    assert "Workflow" in app_source
    assert "Section" in app_source
    assert "Project File" in app_source


def test_ui_commercial4_3_2_sidebar_actions_use_blue_primary_accent() -> None:
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "UI.COMMERCIAL4.3.2" in app_source
    assert "--cpmm-action-fill: #1d6fe7" in app_source
    assert "--cpmm-action-fill-hover: #175cd3" in app_source
    assert "section[data-testid=\"stSidebar\"] div[data-testid=\"stDownloadButton\"] button" in app_source
    assert "linear-gradient(135deg, #1d6fe7, #175cd3)" in app_source
