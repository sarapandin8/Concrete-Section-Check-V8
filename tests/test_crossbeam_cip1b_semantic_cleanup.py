from __future__ import annotations

from pathlib import Path

from concrete_pmm_pro.crossbeam.construction_stage import default_column_stage_rows


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cip1b_default_columns_are_inboard_from_physical_member_ends() -> None:
    rows = default_column_stage_rows(20.0)
    assert [row["Station s (m)"] for row in rows] == [1.5, 18.5]
    assert all(row["Blong (mm)"] == 2000.0 for row in rows)


def test_cip1b_section_library_hides_hollow_button_in_cip_branch_and_uses_zone_semantics() -> None:
    source = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")
    assert "if not cip_mode and hollow_col is not None" in source
    assert 'assignment_noun = "Zones" if cip_mode else "Segments"' in source
    assert '"detail": "Zone references" if cip_mode else "Segment references"' in source
    assert '"Zones using" if cip_mode else "Segments using"' in source


def test_cip1b_section_builder_uses_cip_semantics_without_auto_changing_material() -> None:
    source = (REPO_ROOT / "concrete_pmm_pro" / "ui" / "section_builder.py").read_text(encoding="utf-8")
    assert 'property_heading = "Gross Concrete Section Properties" if _crossbeam_cip_mode() else "Precast Gross Section Properties"' in source
    assert "MATERIAL SOURCE REVIEW — Construction Type is Cast-in-Place" in source
    assert '"Cast-in-Place mode permits Portal Frame Crossbeam Solid presets only.' in source
    assert 'layout_label = "Section / Zone Layout" if _crossbeam_cip_mode() else "Segment Layout"' in source
    assert 'Crossbeam length L is the physical end-to-end member length' in source
