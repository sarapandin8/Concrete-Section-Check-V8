from __future__ import annotations

import inspect

from concrete_pmm_pro.crossbeam.section_library import default_section_definitions, migrate_segment_rows_to_library
from concrete_pmm_pro.crossbeam.tendon import (
    TENDON_PROFILE_IMPORT_REQUIRED_COLUMNS,
    default_tendon_profile_points,
    default_tendon_system_rows,
    normalize_tendon_profile_import_rows,
    tendon_profile_import_schema_rows,
    tendon_profile_import_template_rows,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.ui import crossbeam_pages


def _context():
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(20.0), definitions
    )
    system = default_tendon_system_rows()
    profile = default_tendon_profile_points(
        20.0,
        tendon_ids=[row["Tendon ID"] for row in system],
        width_mm=2500.0,
        height_mm=1500.0,
        t_left_mm=300.0,
        t_right_mm=300.0,
    )
    return system, profile, definitions, segments


def test_ptqa4_import_schema_matches_visible_profile_table_contract() -> None:
    schema = tendon_profile_import_schema_rows()

    assert [row["Column"] for row in schema] == list(TENDON_PROFILE_IMPORT_REQUIRED_COLUMNS)
    assert all(row["Required"] for row in schema)
    assert "dtop" in schema[4]["Description"]


def test_ptqa4_import_template_uses_current_profile_rows_without_internal_ratio_column() -> None:
    _system, profile, _definitions, _segments = _context()

    template_rows = tendon_profile_import_template_rows(profile, length_m=20.0)

    assert len(template_rows) == len(profile)
    assert list(template_rows[0]) == list(TENDON_PROFILE_IMPORT_REQUIRED_COLUMNS)
    assert "s/L" not in template_rows[0]
    assert template_rows[0]["Tendon ID"] == "T1"


def test_ptqa4_valid_import_preview_normalizes_and_validates_rows_without_writeback() -> None:
    system, profile, definitions, segments = _context()
    import_rows = tendon_profile_import_template_rows(profile, length_m=20.0)

    preview_rows, errors, warnings = normalize_tendon_profile_import_rows(
        import_rows,
        system,
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
    )

    assert not errors
    assert not warnings
    assert preview_rows == profile


def test_ptqa4_import_preview_reports_missing_required_columns_before_validation() -> None:
    system, _profile, definitions, segments = _context()

    preview_rows, errors, warnings = normalize_tendon_profile_import_rows(
        [{"Tendon ID": "T1", "Point": "P1", "s (m)": 0.0}],
        system,
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
    )

    assert preview_rows == []
    assert warnings == []
    assert errors == [
        "Import file is missing required column(s): x lateral (mm), dtop (mm), Curve role."
    ]


def test_ptqa4_import_preview_accepts_common_excel_column_aliases() -> None:
    system, _profile, definitions, segments = _context()
    alias_rows = [
        {
            "Tendon": "T1",
            "Point ID": "P1",
            "Station (m)": 0.0,
            "x (mm)": -1100.0,
            "Depth from top (mm)": 500.0,
            "Role": "Anchorage",
        },
        {
            "Tendon": "T1",
            "Point ID": "P2",
            "Station (m)": 10.0,
            "x (mm)": -1100.0,
            "Depth from top (mm)": 500.0,
            "Role": "Profile point",
        },
        {
            "Tendon": "T1",
            "Point ID": "P3",
            "Station (m)": 20.0,
            "x (mm)": -1100.0,
            "Depth from top (mm)": 500.0,
            "Role": "Anchorage",
        },
    ]

    preview_rows, errors, warnings = normalize_tendon_profile_import_rows(
        alias_rows,
        [system[0]],
        length_m=20.0,
        segment_rows=segments,
        section_definitions=definitions,
    )

    assert not errors
    assert not warnings
    assert [row["Point"] for row in preview_rows] == ["P1", "P2", "P3"]


def test_ptqa4_tendon_profile_page_exposes_preview_only_import_ui() -> None:
    source = inspect.getsource(crossbeam_pages.render_crossbeam_tendon_profile_page)
    helper_source = inspect.getsource(crossbeam_pages._render_tendon_profile_import_foundation)

    assert "_render_tendon_profile_import_foundation" in source
    assert "st.download_button" in helper_source
    assert "st.file_uploader" in helper_source
    assert "Preview only" in helper_source
    assert "CB_PROFILE_ROWS_KEY" not in helper_source
