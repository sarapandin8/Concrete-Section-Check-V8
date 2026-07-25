from __future__ import annotations

from pathlib import Path


def test_section_ui1a_groups_name_and_action_in_compact_form() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")
    start = source.index("def _rename_section_name_form(")
    end = source.index("\ndef _advanced_identity_form(", start)
    block = source[start:end]

    assert 'st.columns([0.76, 0.24], gap="medium")' in block
    assert 'st.columns([0.74, 0.26], gap="small")' in block
    assert 'with st.form(' in block
    assert 'save_name = st.form_submit_button(' in block
    assert 'label_visibility="collapsed"' in block
    assert 'st.write("")' not in block


def test_section_ui1a_keeps_identity_visible_and_validates_inline() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")
    start = source.index("def _rename_section_name_form(")
    end = source.index("\ndef _advanced_identity_form(", start)
    block = source[start:end]

    assert 'st.caption("Stable reference")' in block
    assert 'st.error("Section name is required.")' in block
    assert 'st.info("The section name is unchanged.")' in block
    assert "references remain unchanged" in block
