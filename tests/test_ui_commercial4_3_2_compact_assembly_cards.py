from __future__ import annotations

from pathlib import Path


def test_ui_commercial4_3_2_compacts_assembly_summary_cards() -> None:
    source = Path("concrete_pmm_pro/ui/section_builder.py").read_text(encoding="utf-8")

    assert "UI.COMMERCIAL4.3.2: compact engineering summary cards" in source
    assert "def _compact_summary_card_html" in source
    assert "cpmm-assembly-summary-card" in source
    assert 'st.metric("Assembly units"' not in source
    assert 'st.metric("Lifting a"' not in source
    assert 'st.metric("Wet slab case"' not in source
    assert 'st.metric("Lifting basis"' not in source
    assert '_compact_summary_card_html("Assembly units", "2 webs + CIP slab")' in source
    assert '_compact_summary_card_html("Lifting basis", "Individual precast unit", "not bridge assembly", accent="green")' in source
