from pathlib import Path

from concrete_pmm_pro.crossbeam.rebar import (
    RB_HOLLOW_MIN,
    RB_SOLID_ANCHORAGE,
    canonical_rebar_templates,
    default_crossbeam_rebar_templates,
)
from concrete_pmm_pro.ui.crossbeam_rebar_page import (
    _delete_template_ids,
    _template_face_layout_from_editor,
    _template_rows_from_editor,
)


def test_rb2c_default_template_fields_are_editable_through_table_merge():
    rows = default_crossbeam_rebar_templates()
    edited = _template_rows_from_editor(
        rows,
        [
            {
                "Template ID": RB_HOLLOW_MIN,
                "Template name": "Hollow heavy web reinforcement",
                "Role": "Hollow",
                "Construction": "Project-defined",
            }
        ],
        {
            "Template name": "Template name",
            "Role": "Applicable role",
            "Construction": "Construction",
        },
    )
    row = next(item for item in edited if item["Template ID"] == RB_HOLLOW_MIN)
    assert row["Template name"] == "Hollow heavy web reinforcement"
    assert row["Construction"] == "Project-defined"


def test_rb2c_compact_target_column_updates_spacing_or_exact_count():
    rows = default_crossbeam_rebar_templates()
    rows = _template_face_layout_from_editor(
        rows,
        [
            {
                "Template ID": RB_HOLLOW_MIN,
                "Use": True,
                "Bar": "DB25",
                "Method": "By target spacing",
                "Offset (mm)": 60,
                "Target": 200,
            }
        ],
        face="Outer",
    )
    row = next(item for item in rows if item["Template ID"] == RB_HOLLOW_MIN)
    assert row["Outer bar size"] == "DB25"
    assert row["Outer target spacing mm"] == 200
    assert row["Outer center offset mm"] == 60

    rows = _template_face_layout_from_editor(
        rows,
        [
            {
                "Template ID": RB_HOLLOW_MIN,
                "Use": True,
                "Bar": "DB20",
                "Method": "By exact bar count",
                "Offset (mm)": 50,
                "Target": 28,
            }
        ],
        face="Outer",
    )
    row = next(item for item in rows if item["Template ID"] == RB_HOLLOW_MIN)
    assert row["Outer layout method"] == "By exact bar count"
    assert row["Outer exact bar count"] == 28


def test_rb2c_default_template_can_be_deleted_when_unassigned_but_reference_guard_remains():
    rows = canonical_rebar_templates(default_crossbeam_rebar_templates())
    remaining, deleted, errors = _delete_template_ids(rows, [RB_SOLID_ANCHORAGE], [],)
    assert not errors
    assert deleted == [RB_SOLID_ANCHORAGE]
    assert RB_SOLID_ANCHORAGE not in {row["Template ID"] for row in remaining}

    zones = [{"Zone ID": "Z-S1", "Segment": "S1", "s_start_m": 0, "s_end_m": 1, "Rebar template": RB_HOLLOW_MIN, "Purpose": ""}]
    remaining, deleted, errors = _delete_template_ids(rows, [RB_HOLLOW_MIN], zones)
    assert not deleted
    assert errors and "assigned" in errors[0]
    assert RB_HOLLOW_MIN in {row["Template ID"] for row in remaining}


def test_rb2c_page_replaces_large_selected_template_form_with_direct_edit_tables():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text()
    assert "Template identity and row actions" in source
    assert "Participation and material" in source
    assert "Outer-face auto layout" in source
    assert "Inner-face auto layout" in source
    assert "Adopted provided reinforcement — optional / future solver handoff" in source
    assert "Template to edit" not in source
    assert "Edit Selected Template" not in source
    assert 'expanded=True' not in source[source.index("def _render_template_library"):source.index("def _render_zone_assignment")]
