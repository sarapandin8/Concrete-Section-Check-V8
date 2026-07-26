from pathlib import Path


def _source() -> str:
    return Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")


def test_ptloss3b2a3_resets_inactive_legacy_eci_override_to_stage_source():
    source = _source()
    assert "inactive QA override must not retain the legacy 31,500 MPa seed" in source
    assert "st.session_state[CB_LOSS_ES_ECI_OVERRIDE_MPA_KEY] = float(material_eci)" in source


def test_ptloss3b2a3_exposes_active_model_symmetry_and_bond_state_guards():
    source = _source()
    assert '"title": "Active-model symmetry"' in source
    assert '"title": "Tendon bond-state source"' in source
    assert "Internal/External identifies tendon location" in source


def test_ptloss3b2a3_explains_moment_steps_and_removes_stale_ui_labels():
    source = _source()
    assert "Apparent steps can occur at concentrated tendon-equivalent couples" in source
    assert "Moment-jump / response-event audit" in source
    assert "PTLOSS3B2A1 reaction, column-action, and tendon-load audit" not in source
    assert "Run PTLOSS3B2A1 mesh-sensitivity diagnostic" not in source
