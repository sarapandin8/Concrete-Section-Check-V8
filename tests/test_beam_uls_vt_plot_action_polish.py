from __future__ import annotations

from pathlib import Path


SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")


def test_combined_vt_plot_uses_short_legend_labels_and_governing_label() -> None:
    assert '("Stress D/C", "Stress D/C value")' in SOURCE
    assert '("Transverse D/C", "Transverse D/C value")' in SOURCE
    assert '("Long. Al D/C", "Longitudinal D/C value")' in SOURCE
    assert 'name="Limit = 1.0"' in SOURCE
    assert 'text=[f"Gov. D/C {dc:.3f}"]' in SOURCE
    assert 'name="Gov. V+T"' in SOURCE
    assert 'textposition="bottom center" if dc >= 0.85 else "top center"' in SOURCE


def test_combined_vt_required_action_points_to_source_fail() -> None:
    assert 'Resolve source Shear/Torsion FAIL before accepting V+T interaction.' in SOURCE
    assert 'Complete required V+T source data before accepting interaction.' in SOURCE


def test_combined_vt_card_shows_source_blocked_when_source_gate_blocks() -> None:
    assert 'interaction_display_status = (' in SOURCE
    assert '"SOURCE BLOCKED"' in SOURCE
    assert 'source_blocked = bool(source_gate.get("has_blocker"))' in SOURCE
