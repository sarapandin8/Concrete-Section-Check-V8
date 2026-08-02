from __future__ import annotations

from pathlib import Path

import pytest

import app
from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.core.project import ProjectModel
from concrete_pmm_pro.io.project_io import project_to_json


APP = Path("app.py").read_text(encoding="utf-8")
GEOMETRY_NOTICE = Path(
    "concrete_pmm_pro/ui/crossbeam_project_geometry.py"
).read_text(encoding="utf-8")


class _Upload:
    def __init__(self, name: str, payload: bytes) -> None:
        self.name = name
        self._payload = payload

    def getvalue(self) -> bytes:
        return self._payload


def _relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_ui_upload1_renders_full_filename_validation_and_workflow_before_apply() -> None:
    assert "def _review_sidebar_project_upload" in APP
    assert "def _render_sidebar_project_upload_review" in APP
    assert "Project file selected" in APP
    assert "JSON validated" in APP
    assert "Workflow in file:" in APP
    assert "Ready to apply" in APP
    assert "overflow-wrap: anywhere" in APP
    assert 'disabled=review.get("project") is None' in APP


def test_ui_upload1_selection_validation_does_not_apply_or_mutate_project() -> None:
    review_start = APP.index("def _review_sidebar_project_upload")
    review_end = APP.index("def _render_sidebar_project_upload_review", review_start)
    review_source = APP[review_start:review_end]

    assert "project_from_json(pending_json)" in review_source
    assert "apply_project_to_session_state" not in review_source
    assert "st.session_state" not in review_source


def test_ui_upload1_apply_keeps_the_existing_canonical_restore_route() -> None:
    render_start = APP.index("def _render_sidebar_project_file_actions")
    render_end = APP.index("def _render_commercial_sidebar", render_start)
    render_source = APP[render_start:render_end]

    assert "Apply Loaded Project" in render_source
    assert "apply_project_to_session_state(project, st.session_state)" in render_source
    assert "project_to_json(project)" in render_source
    assert "ui_commercial4_3_sidebar_project_json_uploader" in render_source


def test_ui_upload1_uses_readable_theme_status_colors_without_styling_remove_x() -> None:
    assert ".cpmm-sidebar-project-upload-card.ready" in APP
    assert "#0f6f60" in APP
    assert ".cpmm-sidebar-project-upload-card.invalid" in APP
    assert "#9f2033" in APP
    assert ".cpmm-sidebar-blocked-notice" in APP
    assert "#fff1f3" in APP
    assert (
        'section[data-testid="stSidebar"] '
        'div[data-testid="stFileUploaderDropzone"] button {'
    ) in APP
    assert (
        'section[data-testid="stSidebar"] '
        'div[data-testid="stFileUploader"] button {'
    ) not in APP


def test_selected_file_replaces_truncated_native_pill_with_explicit_actions() -> None:
    assert 'div[data-testid="stFileUploader"] {\n  display: none !important;' in APP
    assert "Apply Loaded Project" in APP
    assert "Change File" in APP
    assert "ui_commercial4_3_sidebar_uploader_revision" in APP
    assert "_sidebar_project_load_notice" in APP
    assert "-webkit-text-fill-color:#061b35!important" in APP


def test_post_apply_notice_is_app_owned_and_readable_instead_of_native_success_alert() -> None:
    render_start = APP.index("def _render_sidebar_project_file_actions")
    render_end = APP.index("def _render_commercial_sidebar", render_start)
    render_source = APP[render_start:render_end]

    assert "cpmm-sidebar-project-loaded-card" in APP
    assert "cpmm-sidebar-project-loaded-title" in APP
    assert "cpmm-sidebar-project-loaded-name" in APP
    assert 'style="color:#0f6f60!important;-webkit-text-fill-color:#0f6f60!important;"' in render_source
    assert 'style="color:#061b35!important;-webkit-text-fill-color:#061b35!important;"' in render_source
    assert "st.success(str(load_notice))" not in render_source


@pytest.mark.parametrize(
    ("foreground", "background"),
    [
        ("#061b35", "#e7f8f3"),
        ("#0f6f60", "#e7f8f3"),
        ("#34536f", "#e7f8f3"),
        ("#9f2033", "#fff0f2"),
        ("#81172a", "#fff1f3"),
    ],
)
def test_ui_upload1_status_palette_meets_normal_text_contrast(
    foreground: str,
    background: str,
) -> None:
    assert _contrast_ratio(foreground, background) >= 4.5


def test_ui_upload1_sidebar_geometry_blocker_uses_scoped_readable_notice() -> None:
    assert 'str(key_prefix).startswith("sidebar_")' in GEOMETRY_NOTICE
    assert "cpmm-sidebar-blocked-notice" in GEOMETRY_NOTICE
    assert "unsafe_allow_html=True" in GEOMETRY_NOTICE
    assert 'st.error("PROJECT GEOMETRY INCONSISTENT — BLOCKED")' in GEOMETRY_NOTICE


@pytest.mark.parametrize(
    ("member_type", "expected_workflow"),
    [
        ("column_pier_pmm", "Column / Pier / Wall / Pylon"),
        ("beam_girder", "Bridge Beam / Girder"),
        ("building_beam_girder", "Building Beam / Girder"),
        ("portal_frame_crossbeam", "Portal Frame Crossbeam"),
    ],
)
def test_ui_upload1_reviews_every_member_workflow_without_applying(
    member_type: str,
    expected_workflow: str,
) -> None:
    project = ProjectModel(
        project_name=f"{member_type} project",
        analysis_mode_settings=AnalysisModeSettings(member_type=member_type),
    )
    payload = project_to_json(project).encode("utf-8")

    review = app._review_sidebar_project_upload(
        _Upload(f"{member_type}.json", payload)
    )

    assert review["error"] is None
    assert expected_workflow in str(review["workflow"])
    assert review["project"].project_name == f"{member_type} project"


def test_ui_upload1_rejects_invalid_json_before_apply() -> None:
    review = app._review_sidebar_project_upload(
        _Upload("broken.json", b"{not valid json")
    )

    assert review["project"] is None
    assert "Invalid project JSON" in str(review["error"])
