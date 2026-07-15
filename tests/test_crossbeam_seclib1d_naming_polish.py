from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.crossbeam.section_library import default_section_definitions
from concrete_pmm_pro.ui.crossbeam_section_library import (
    CUSTOM_SECTION_NAME_OPTION,
    _conflicting_section_name_ids,
    _matching_name_suggestion,
    _project_section_summary_rows,
    _section_name_suggestions,
    _style_project_section_summary,
)


def test_role_based_name_suggestions_remain_optional() -> None:
    hollow = _section_name_suggestions("Hollow")
    solid = _section_name_suggestions("Solid")

    assert "Hollow typical" in hollow
    assert "Hollow heavy web" in hollow
    assert "Hollow near column" in hollow
    assert "Solid column region" in solid
    assert "Solid anchorage block" in solid
    assert hollow[-1] == CUSTOM_SECTION_NAME_OPTION
    assert solid[-1] == CUSTOM_SECTION_NAME_OPTION


def test_custom_names_are_preserved_and_known_names_match_suggestions() -> None:
    suggestions = _section_name_suggestions("Hollow")

    assert _matching_name_suggestion("Hollow heavy web", suggestions) == "Hollow heavy web"
    assert _matching_name_suggestion("Project-specific H-03", suggestions) == CUSTOM_SECTION_NAME_OPTION


def test_duplicate_user_facing_names_are_detected_without_changing_ids() -> None:
    definitions = default_section_definitions()
    definitions.append(
        {
            **definitions[1],
            "Section ID": "CB-H02",
            "Section name": "Hollow heavy web",
        }
    )

    assert _conflicting_section_name_ids(definitions, "CB-H01", "Hollow heavy web") == ["CB-H02"]
    assert _conflicting_section_name_ids(definitions, "CB-H01", "Hollow typical") == []


def test_summary_uses_row_highlight_instead_of_redundant_active_column() -> None:
    definitions = default_section_definitions()
    rows = _project_section_summary_rows(definitions, {}, "CB-H01")
    styled = _style_project_section_summary(rows, "CB-H01")

    assert "Active" not in styled.data.columns
    assert list(styled.data["Section ID"]) == ["CB-S01", "CB-H01"]


def test_seclib1d_surfaces_quick_names_active_badge_and_table_highlight() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")

    assert '"Suggested section role / name"' in source
    assert '"Custom project name"' in source
    assert '"Save name"' in source
    assert '"Quick section switch"' in source
    assert '"**ACTIVE PROJECT SECTION**' in source
    assert "_style_project_section_summary(summary_rows, active_id)" in source
    assert "Section name is already used by" in source
