from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from concrete_pmm_pro.ui import project_page


def test_workflow_dropdown_callback_commits_selected_mode_before_rerun(monkeypatch) -> None:
    widget_key = "project_analysis_mode_member_type_label"
    note_key = "project_analysis_mode_note"
    sync_key = "project_analysis_mode_member_type_sync"
    state: dict[str, object] = {
        widget_key: "Portal Frame Crossbeam — Prestressed Concrete",
        note_key: "",
        sync_key: "column_pier_pmm",
        "analysis_mode_settings": AnalysisModeSettings(member_type="column_pier_pmm"),
    }
    monkeypatch.setattr(project_page, "st", SimpleNamespace(session_state=state))

    project_page._commit_analysis_mode_member_type(widget_key, note_key, sync_key)

    assert state["analysis_mode_settings"] == AnalysisModeSettings(
        member_type="portal_frame_crossbeam"
    )
    assert state[sync_key] == "portal_frame_crossbeam"


def test_workflow_dropdown_declares_pre_rerun_commit_callback() -> None:
    path = Path(project_page.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    matching_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "selectbox" or not node.args:
            continue
        if isinstance(node.args[0], ast.Constant) and node.args[0].value == "Change active member workflow":
            matching_calls.append(node)

    assert len(matching_calls) == 1
    keyword_names = {keyword.arg for keyword in matching_calls[0].keywords}
    assert "on_change" in keyword_names
    assert "args" in keyword_names


def test_transverse_placement_inputs_are_split_by_coordinate_direction() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "concrete_pmm_pro" / "ui" / "crossbeam_transverse_page.py"
    ).read_text(encoding="utf-8")

    assert 'st.markdown("#### Cross-section cage placement")' in source
    assert 'st.markdown("#### Longitudinal placement within each zone")' in source
    assert '"Cage centerline offset (mm)": "Center offset mm"' in source
    assert '"First set from Zone start (mm)": "First bar offset mm"' in source
    assert '"Minimum clearance to Zone end (mm)": "Last bar offset mm"' in source
    assert 'st.markdown("#### Placement within each zone")' not in source
