from pathlib import Path

from concrete_pmm_pro.crossbeam.rebar import (
    RB_HOLLOW_MIN,
    RB_SOLID_COLUMN,
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
)
from concrete_pmm_pro.ui.crossbeam_rebar_page import (
    _normalize_template_id,
    _template_identity_rows_from_editor,
    _template_material_rows_from_editor,
)


def _segments():
    return [
        {
            "Segment": "S1",
            "x_start_m": 0.0,
            "x_end_m": 3.0,
            "Section role": "Hollow",
        },
        {
            "Segment": "S2",
            "x_start_m": 3.0,
            "x_end_m": 7.0,
            "Section role": "Solid",
        },
    ]


def test_rb2d_template_id_edit_updates_zone_reference_atomically():
    rows = default_crossbeam_rebar_templates()
    zones = default_crossbeam_rebar_zones(_segments(), rows)
    edited = []
    for row in rows:
        new_id = "RB-HOLLOW-HEAVY" if row["Template ID"] == RB_HOLLOW_MIN else row["Template ID"]
        edited.append(
            {
                "_Original ID": row["Template ID"],
                "Template ID": new_id,
                "Template name": row["Template name"],
                "Role": row["Applicable role"],
                "Construction": row["Construction"],
            }
        )

    updated_rows, updated_zones, rename_map, errors = _template_identity_rows_from_editor(rows, edited, zones)

    assert not errors
    assert rename_map == {RB_HOLLOW_MIN: "RB-HOLLOW-HEAVY"}
    assert "RB-HOLLOW-HEAVY" in {row["Template ID"] for row in updated_rows}
    assert updated_zones[0]["Rebar template"] == "RB-HOLLOW-HEAVY"
    assert updated_zones[1]["Rebar template"] == RB_SOLID_COLUMN


def test_rb2d_template_id_normalizes_spaces_and_rejects_duplicates():
    assert _normalize_template_id(" rb hollow heavy web ") == "RB-HOLLOW-HEAVY-WEB"
    rows = default_crossbeam_rebar_templates()
    zones = default_crossbeam_rebar_zones(_segments(), rows)
    edited = []
    for index, row in enumerate(rows):
        edited.append(
            {
                "_Original ID": row["Template ID"],
                "Template ID": "RB-DUPLICATE" if index < 2 else row["Template ID"],
                "Template name": row["Template name"],
                "Role": row["Applicable role"],
                "Construction": row["Construction"],
            }
        )
    updated_rows, updated_zones, rename_map, errors = _template_identity_rows_from_editor(rows, edited, zones)
    assert errors and "Duplicate Template IDs" in errors[0]
    assert not rename_map
    assert {row["Template ID"] for row in updated_rows} == {row["Template ID"] for row in rows}
    assert updated_zones == zones


def test_rb2d_material_and_fy_dropdowns_are_linked_both_directions():
    rows = default_crossbeam_rebar_templates()
    edited = [
        {
            "Template ID": RB_HOLLOW_MIN,
            "Basis": "Segment-local",
            "fy (MPa)": 390,
            "Material": "SD50",
            "Active": True,
            "Credit": True,
        }
    ]
    updated, warnings = _template_material_rows_from_editor(rows, edited)
    hollow = next(row for row in updated if row["Template ID"] == RB_HOLLOW_MIN)
    assert not warnings
    assert hollow["Rebar material"] == "SD50"
    assert hollow["fy MPa"] == 490.0

    edited = [
        {
            "Template ID": RB_HOLLOW_MIN,
            "Basis": "Segment-local",
            "fy (MPa)": 390,
            "Material": "SD50",
            "Active": True,
            "Credit": True,
        }
    ]
    # Starting from SD50/490, changing fy alone back to 390 must also restore SD40.
    updated, warnings = _template_material_rows_from_editor(updated, edited)
    hollow = next(row for row in updated if row["Template ID"] == RB_HOLLOW_MIN)
    assert not warnings
    assert hollow["Rebar material"] == "SD40"
    assert hollow["fy MPa"] == 390.0


def test_rb2d_zone_reset_uses_renamed_compatible_template_ids():
    rows = default_crossbeam_rebar_templates()
    for row in rows:
        if row["Template ID"] == RB_HOLLOW_MIN:
            row["Template ID"] = "RB-H-TYPICAL"
        elif row["Template ID"] == RB_SOLID_COLUMN:
            row["Template ID"] = "RB-S-COLUMN"
    zones = default_crossbeam_rebar_zones(_segments(), rows)
    assert zones[0]["Rebar template"] == "RB-H-TYPICAL"
    assert zones[1]["Rebar template"] == "RB-S-COLUMN"


def test_rb2d_page_exposes_editable_ids_and_dropdown_material_pair():
    source = Path("concrete_pmm_pro/ui/crossbeam_rebar_page.py").read_text()
    library = source[source.index("def _render_template_library"):source.index("def _render_zone_assignment")]
    assert '"_Original ID": None' in library
    assert 'Template IDs are editable' in library
    assert '"fy (MPa)": st.column_config.SelectboxColumn' in library
    assert '"Material": st.column_config.SelectboxColumn' in library
    assert 'disabled=["Template ID"]' in library  # Other compact tables keep IDs read-only after identity edit.
