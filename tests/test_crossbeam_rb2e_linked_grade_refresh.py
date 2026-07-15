from pathlib import Path

from concrete_pmm_pro.crossbeam.rebar import RB_HOLLOW_MIN, default_crossbeam_rebar_templates
from concrete_pmm_pro.ui.crossbeam_rebar_page import (
    _material_editor_sync_required,
    _template_material_rows_from_editor,
)


def _editor_row(*, material: str, fy: int):
    return {
        "Template ID": RB_HOLLOW_MIN,
        "Basis": "Segment-local",
        "fy (MPa)": fy,
        "Material": material,
        "Active": True,
        "Credit": True,
    }


def test_rb2e_fy_change_requires_one_visual_refresh_and_resolves_material():
    rows = default_crossbeam_rebar_templates()
    editor_rows = [_editor_row(material="SD40", fy=490)]
    updated, warnings = _template_material_rows_from_editor(rows, editor_rows)
    assert not warnings
    target = next(row for row in updated if row["Template ID"] == RB_HOLLOW_MIN)
    assert target["Rebar material"] == "SD50"
    assert target["fy MPa"] == 490.0
    assert _material_editor_sync_required(editor_rows, updated)
    assert not _material_editor_sync_required([_editor_row(material="SD50", fy=490)], updated)


def test_rb2e_material_change_requires_one_visual_refresh_and_resolves_fy():
    rows = default_crossbeam_rebar_templates()
    editor_rows = [_editor_row(material="SD50", fy=390)]
    updated, warnings = _template_material_rows_from_editor(rows, editor_rows)
    assert not warnings
    target = next(row for row in updated if row["Template ID"] == RB_HOLLOW_MIN)
    assert target["Rebar material"] == "SD50"
    assert target["fy MPa"] == 490.0
    assert _material_editor_sync_required(editor_rows, updated)
    assert not _material_editor_sync_required([_editor_row(material="SD50", fy=490)], updated)


def test_rb2e_render_path_bumps_revision_and_reruns_only_when_pair_is_stale():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text()
    assert "if _material_editor_sync_required(participation_records, rows):" in source
    assert "_bump_template_editor_revision()" in source
    assert "st.rerun()" in source
