from pathlib import Path


def _elastic_source() -> str:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(
        encoding="utf-8"
    )
    return source.split("with elastic_shortening_tab:", 1)[1].split(
        "with time_dependent_tab:", 1
    )[0]


def test_lightweight_status_copy_matches_released_on_demand_route() -> None:
    elastic = _elastic_source()
    assert "SOURCE READY — RUN ON DEMAND" in elastic
    assert "not run · available after Lightweight ES Analysis" in elastic
    assert 'displayed_component_status = "SOURCE INPUT REQUIRED"' in elastic
    assert 'displayed_component_detail = "Final tendon bond system"' in elastic
    assert 'displayed_component_status = "READY TO RUN"' in elastic
    assert 'displayed_component_status = "RERUN REQUIRED"' in elastic
    assert 'displayed_component_status = "ES ESTIMATE CURRENT"' in elastic
    assert "sequence diagnostic not released" not in elastic


def test_advanced_qa_requires_explicit_heavy_run_confirmation() -> None:
    elastic = _elastic_source()
    assert "I understand that Advanced QA is optional, computationally heavy" in elastic
    assert "Run Advanced Construction-Stage QA — computationally heavy" in elastic
    assert "advanced_evidence_status == \"CURRENT\"" in elastic
    assert "or not advanced_confirmed" in elastic
    assert "may be slow or trigger cloud throttling" in elastic
    assert elastic.index("run_crossbeam_incremental_contact_mesh_sensitivity") > elastic.index(
        "if run_advanced:"
    )
