from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.crossbeam.section_library import (
    DEFAULT_HOLLOW_SECTION_ID,
    DEFAULT_SOLID_SECTION_ID,
    default_section_definitions,
    rename_definition,
)
from concrete_pmm_pro.ui.crossbeam_section_library import (
    _project_section_summary_rows,
    _section_dimension_summary,
)


def test_summary_rows_show_every_project_section_geometry_and_usage() -> None:
    definitions = default_section_definitions()
    rows = _project_section_summary_rows(
        definitions,
        {DEFAULT_HOLLOW_SECTION_ID: ["S1", "S2"]},
        DEFAULT_HOLLOW_SECTION_ID,
    )

    assert [row["Section ID"] for row in rows] == [DEFAULT_SOLID_SECTION_ID, DEFAULT_HOLLOW_SECTION_ID]
    hollow = next(row for row in rows if row["Section ID"] == DEFAULT_HOLLOW_SECTION_ID)
    assert hollow["Active"] == "●"
    assert hollow["Family"] == "Hollow"
    assert hollow["B × H"] == "2500 × 1500 mm"
    assert "tt/tb = 300/350 mm" in hollow["Geometry summary"]
    assert "tl/tr = 300/300 mm" in hollow["Geometry summary"]
    assert hollow["Segments using"] == "S1, S2"
    assert hollow["Status"] in {"READY", "REVIEW"}


def test_solid_dimension_summary_remains_compact() -> None:
    solid = default_section_definitions()[0]
    size, detail = _section_dimension_summary(solid)

    assert size == "2500 × 1500 mm"
    assert detail == "Bottom fillet R = 200 mm"


def test_user_facing_name_can_change_without_changing_stable_section_id() -> None:
    definitions = default_section_definitions()
    renamed = rename_definition(
        definitions,
        DEFAULT_HOLLOW_SECTION_ID,
        new_section_id=DEFAULT_HOLLOW_SECTION_ID,
        new_section_name="Hollow heavy web",
    )

    row = next(item for item in renamed if item["Section ID"] == DEFAULT_HOLLOW_SECTION_ID)
    assert row["Section name"] == "Hollow heavy web"
    assert row["Section ID"] == DEFAULT_HOLLOW_SECTION_ID


def test_seclib1b_surfaces_summary_rename_delete_and_keeps_id_advanced() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")

    assert '"#### Project Section Summary"' in source
    assert '"#### Manage Selected Section"' in source
    assert '"Save name"' in source
    assert '"Delete selected section"' in source
    assert '"Advanced Section ID management"' in source
    assert "assigned sections cannot be removed" in source
    assert "CB_SECLIB_PENDING_ACTIVE_ID_KEY" in source
