from pathlib import Path


def _source() -> str:
    return Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")


def test_ptloss3b2a3_resets_inactive_legacy_eci_override_to_stage_source():
    source = _source()
    assert "_sync_es_override_preview_value" in source
    assert "Disabled override fields are read-only previews of the source-derived value" in source
    assert "source_value=material_eci" in source
    assert "the field displays the current stage-derived Eci" in source


def test_ptloss3b2a3_exposes_bond_state_guard_and_lightweight_runtime_status():
    source = _source()
    assert '"title": "Final bond-system source"' in source
    assert "Internal/External location remains a separate source" in source
    assert '"title": "Runtime mode"' in source
    assert '"value": "ON DEMAND"' in source

def test_ptloss3b2a3_moves_detailed_response_events_out_of_normal_runtime():
    source = _source()
    assert "Advanced Construction-Stage QA — optional and computationally heavy" in source
    assert "Automated pytest regression suite; not rerun in the user session." in source
    assert "PTLOSS3B2A1 reaction, column-action, and tendon-load audit" not in source
    assert "Run PTLOSS3B2A1 mesh-sensitivity diagnostic" not in source

