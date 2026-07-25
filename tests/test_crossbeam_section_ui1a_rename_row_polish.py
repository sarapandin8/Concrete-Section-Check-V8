from __future__ import annotations

from pathlib import Path


def _rename_block() -> str:
    root = Path(__file__).resolve().parents[1]
    source = (root / "concrete_pmm_pro" / "ui" / "crossbeam_section_library.py").read_text(encoding="utf-8")
    start = source.index("def _rename_section_name_form(")
    end = source.index("\ndef _advanced_identity_form(", start)
    return source[start:end]


def test_section_ui1a_groups_name_action_and_reference_in_compact_row() -> None:
    block = _rename_block()

    assert 'st.columns([0.78, 0.22], gap="medium")' in block
    assert 'st.columns([0.76, 0.24], gap="small")' in block
    assert 'label_visibility="collapsed"' in block
    assert 'st.caption("Stable reference")' in block
    assert 'st.write("")' not in block


def test_section_ui1b_uses_explicit_state_aware_rename_action() -> None:
    block = _rename_block()

    assert 'save_name = st.button(' in block
    assert 'type="primary"' in block
    assert 'disabled=not rename_ready' in block
    assert 'rename_ready = bool(clean_candidate)' in block
    assert 'clean_candidate != current_name' in block
    assert 'not conflicts' in block
    assert 'with st.form(' not in block
    assert 'st.form_submit_button(' not in block


def test_section_ui1b_keeps_inline_validation_and_stable_reference() -> None:
    block = _rename_block()

    assert 'st.error("Section name is required.")' in block
    assert 'Section name is already used by:' in block
    assert 'Change the section name to enable Rename section.' in block
    assert "references remain unchanged" in block
