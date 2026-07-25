from __future__ import annotations

from pathlib import Path


def test_section_ui1_places_actions_with_summary_and_simplifies_rename() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")

    summary_pos = source.index('st.markdown("#### Project Section Summary")')
    selector_pos = source.index('"Selected section"', summary_pos)
    duplicate_pos = source.index('"Duplicate current"', summary_pos)
    solid_pos = source.index('"New Solid"', summary_pos)
    dataframe_pos = source.index("st.dataframe(", summary_pos)

    assert summary_pos < selector_pos < dataframe_pos
    assert summary_pos < duplicate_pos < dataframe_pos
    assert summary_pos < solid_pos < dataframe_pos
    assert '"#### Selected Section Name"' in source
    assert '"Rename section"' in source
    assert '"Optional name suggestions"' in source
    assert '"Delete or change Section ID"' in source
    assert '"#### Manage Selected Section"' not in source
