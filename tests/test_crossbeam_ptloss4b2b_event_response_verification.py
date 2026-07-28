from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.construction_stage import CONSTRUCTION_METHOD_PRECAST
from concrete_pmm_pro.crossbeam.event_stage_stress import (
    run_crossbeam_event_stage_stress_sources,
)
from concrete_pmm_pro.crossbeam.time_dependent_loss import (
    LOW_RELAXATION_STEEL,
    run_crossbeam_lightweight_time_dependent_loss,
)
from tests.test_crossbeam_ptloss4a_time_dependent import _sources


def test_falsework_release_response_is_verified_even_when_governing_fcgp_is_unchanged() -> None:
    (
        length_m,
        definitions,
        segments,
        system,
        settings,
        es,
        model,
        profile,
    ) = _sources()

    result = run_crossbeam_event_stage_stress_sources(
        model=model,
        lightweight_es_result=es,
        profile_rows=profile,
        system_rows=system,
        later_permanent_load_delta_fcgp_mpa=0.0,
    )

    assert result["ready"] is True
    assert result["status"] == "EVENT STRESS SOURCES VERIFIED"
    verification = result["response_verification"]
    assert verification["ready"] is True
    assert verification["response_changed"] is True
    assert verification["governing_fcgp_changed"] is False
    assert (
        verification["status"]
        == "RESPONSE EFFECT VERIFIED — GOVERNING f_cgp UNCHANGED"
    )
    assert verification["fingerprints_differ"] is True
    assert verification["initial_response_fingerprint"] != verification[
        "released_response_fingerprint"
    ]
    deltas = verification["max_response_deltas"]
    assert deltas["moment_kNm"] > 1000.0
    assert deltas["shear_kN"] > 1000.0
    assert deltas["vertical_displacement_mm"] > 1.0
    assert deltas["fcgp_mpa"] > 0.5
    assert deltas["governing_fcgp_mpa"] == pytest.approx(0.0, abs=1.0e-9)
    assert len(result["stress_audit_rows"]) == 3
    assert result["stress_audit_rows"][0]["Limit side"] == "Right-side limit"
    assert result["stress_audit_rows"][1]["Element"] == "B38"
    assert any("same representative limit row remains governing" in note for note in verification["notes"])

    td = run_crossbeam_lightweight_time_dependent_loss(
        lightweight_es_result=es,
        length_m=length_m,
        segment_rows=segments,
        section_definitions=definitions,
        system_rows=system,
        construction_method=CONSTRUCTION_METHOD_PRECAST,
        rh_percent=75.0,
        load_age_days=28.0,
        curing_end_age_days=7.0,
        final_age_days=18250.0,
        grout_age_days=28.0,
        falsework_removal_age_days=35.0,
        permanent_load_age_days=90.0,
        linear_stage_model=model,
        profile_rows=profile,
        later_permanent_load_delta_fcgp_mpa=0.0,
        inner_perimeter_factor=0.5,
        relaxation_steel_class=LOW_RELAXATION_STEEL,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
        fci_mpa=36.0,
    )
    events = {row["Event"]: row for row in td["schedule_source"]["events"]}
    assert events["Falsework removal"]["Calculation role"] == (
        "Event structural solve; temporary vertical contact removed"
    )
    assert events["Later permanent load"]["Calculation role"] == (
        "Engineer-entered Δfcd source; Loads-workspace handoff not yet connected"
    )


def test_active_falsework_with_identical_released_response_is_source_review(monkeypatch) -> None:
    (
        _length_m,
        _definitions,
        _segments,
        system,
        _settings,
        es,
        model,
        profile,
    ) = _sources()

    stored_solution = dict(es["contact_result"]["solution"])

    def _return_stored_contact_solution(**_kwargs):
        return stored_solution

    monkeypatch.setattr(
        "concrete_pmm_pro.crossbeam.event_stage_stress.solve_linear_frame",
        _return_stored_contact_solution,
    )
    result = run_crossbeam_event_stage_stress_sources(
        model=model,
        lightweight_es_result=es,
        profile_rows=profile,
        system_rows=system,
        later_permanent_load_delta_fcgp_mpa=0.0,
    )

    assert result["ready"] is False
    verification = result["response_verification"]
    assert verification["ready"] is False
    assert verification["response_changed"] is False
    assert verification["contact_carried_force"] is True
    assert verification["fingerprints_differ"] is False
    assert (
        verification["status"]
        == "EVENT EFFECT NEGLIGIBLE — VERIFY RESPONSE SOURCE"
    )
    assert any("EVENT EFFECT NEGLIGIBLE" in issue for issue in result["issues"])


def test_ptloss4b2b_ui_exposes_event_source_components_and_response_fingerprints() -> None:
    source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    block = source.split("with time_dependent_tab:", 1)[1].split("with audit_tab:", 1)[0]
    assert "PTLOSS4B2B1 keeps the route event-based and lightweight" in block
    assert "Event-stage governing concrete-stress source" in block
    assert "Falsework-removal response-source verification" in block
    assert "N/A (MPa)" in block
    assert "-M·y/I (MPa)" in block
    assert "Limit side" in block
    assert "Response fingerprints" in block
    assert "EVENT EFFECT NEGLIGIBLE" not in block  # status is data-driven, not hard-coded UI output
    assert "PTLOSS4B2B1 does not assemble Pe/Pe_eff" in block
    assert "ptloss4b2b-event-audit-anchor" in block
