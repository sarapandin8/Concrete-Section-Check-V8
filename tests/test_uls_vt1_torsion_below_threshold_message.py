from __future__ import annotations

from pathlib import Path


SOURCE = Path("concrete_pmm_pro/ui/analysis_page.py").read_text(encoding="utf-8")


def test_torsion_below_threshold_message_does_not_warn_for_longitudinal_al() -> None:
    assert 'torsion_status_label == "BELOW THRESHOLD" or torsion_threshold_label == "BELOW THRESHOLD"' in SOURCE
    assert "longitudinal Al is not required for this torsion gate" in SOURCE
    assert "Review φTn/threshold and detailing notes before final member acceptance." in SOURCE


def test_generic_torsion_demand_warning_still_exists_for_required_torsion_design() -> None:
    assert "Torsion demand is present. Review φTn, threshold, longitudinal Al, and detailing output before issuing final member acceptance." in SOURCE
    assert 'elif torsion_has_demand:' in SOURCE
