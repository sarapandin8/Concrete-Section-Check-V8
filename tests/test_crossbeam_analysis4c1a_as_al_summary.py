from __future__ import annotations

from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "concrete_pmm_pro"
    / "ui"
    / "crossbeam_rebar_page.py"
).read_text(encoding="utf-8")


def test_combined_reinforcement_preview_reports_physical_flexure_as() -> None:
    assert '"title":"Longitudinal flexure — As"' in SOURCE
    assert "PHYSICAL ORDINARY BARS" in SOURCE
    assert "FLEXURE SOURCE: INCLUDED; station development / physical-joint gate applies in Analysis" in SOURCE


def test_torsion_al_is_explained_as_subset_not_duplicate_steel() -> None:
    assert "INCLUDED AS Aℓ SUBSET OF As" in SOURCE
    assert "RETAINED IN As / EXCLUDED FROM Aℓ" in SOURCE
    assert "Aℓ is not additional duplicate steel" in SOURCE


def test_summary_card_order_is_av_at_as_al() -> None:
    start = SOURCE.index('"title":"Shear reinforcement — Av"')
    at = SOURCE.index('"title":"Outer torsion cage — At"', start)
    as_ = SOURCE.index('"title":"Longitudinal flexure — As"', at)
    al = SOURCE.index('"title":"Longitudinal torsion — Aℓ"', as_)
    assert start < at < as_ < al
