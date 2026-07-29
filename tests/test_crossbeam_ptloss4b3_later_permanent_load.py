from __future__ import annotations

from pathlib import Path

import pytest

from concrete_pmm_pro.crossbeam.construction_stage import CONSTRUCTION_METHOD_PRECAST
from concrete_pmm_pro.crossbeam.event_stage_stress import (
    run_crossbeam_event_stage_stress_sources,
)
from concrete_pmm_pro.crossbeam.later_permanent_load import (
    CB_LATER_PERMANENT_LOAD_TABLE_KEY,
    POINT_LOAD,
    UNIFORM_LINE_LOAD,
    later_permanent_load_source,
)
from concrete_pmm_pro.crossbeam.time_dependent_loss import (
    LOW_RELAXATION_STEEL,
    run_crossbeam_lightweight_time_dependent_loss,
)
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state,
    project_from_session_state,
)
from tests.test_crossbeam_ptloss4a_time_dependent import _sources


def _verified_rows() -> list[dict[str, object]]:
    return [
        {
            "Active": True,
            "Load ID": "LP-L",
            "Load Type": POINT_LOAD,
            "Station s (m)": 1.5,
            "End station s (m)": "",
            "Magnitude": 500.0,
            "Note": "Left permanent girder reaction",
        },
        {
            "Active": True,
            "Load ID": "LP-R",
            "Load Type": POINT_LOAD,
            "Station s (m)": 18.5,
            "End station s (m)": "",
            "Magnitude": 500.0,
            "Note": "Right permanent girder reaction",
        },
        {
            "Active": True,
            "Load ID": "LP-UDL",
            "Load Type": UNIFORM_LINE_LOAD,
            "Station s (m)": 3.0,
            "End station s (m)": 17.0,
            "Magnitude": 20.0,
            "Note": "Later permanent line load",
        },
    ]


def test_verified_later_load_source_closes_force_and_preserves_exact_frame_routing() -> None:
    *_unused, model, _profile = _sources()

    source = later_permanent_load_source(model=model, load_rows=_verified_rows())

    assert source["ready"] is True
    assert source["status"] == "VERIFIED LOAD SOURCE READY"
    assert source["active_count"] == 3
    assert source["valid_count"] == 3
    assert source["total_downward_load_kN"] == pytest.approx(1280.0)
    assert source["equivalent_frame_downward_kN"] == pytest.approx(1280.0)
    assert source["vertical_force_residual_kN"] == pytest.approx(0.0, abs=1.0e-10)
    assert len(source["equivalent_nodal_rows"]) == 2
    assert len(source["uniform_element_rows"]) == 28
    assert set(source["uniform_local_y_by_element"].values()) == {-20.0}
    assert source["fingerprint"]


def test_nonmesh_load_station_is_review_not_silently_smeared() -> None:
    *_unused, model, _profile = _sources()
    rows = _verified_rows()
    rows[0]["Station s (m)"] = 1.234

    source = later_permanent_load_source(model=model, load_rows=rows)

    assert source["ready"] is False
    assert source["status"] == "REVIEW REQUIRED"
    assert any("analysis mesh station" in issue for issue in source["issues"])
    assert any("nearest is 1.000000 m" in issue for issue in source["issues"])


def test_invalid_active_later_load_blocks_event_instead_of_falling_back_to_manual_delta() -> None:
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
    rows = _verified_rows()
    rows[0]["Station s (m)"] = 1.234

    result = run_crossbeam_event_stage_stress_sources(
        model=model,
        lightweight_es_result=es,
        profile_rows=profile,
        system_rows=system,
        later_permanent_load_delta_fcgp_mpa=9.9,
        later_permanent_load_rows=rows,
    )

    assert result["ready"] is False
    assert result["solve_count"] == 1
    assert result["later_load_source_verified"] is False
    assert any("analysis mesh station" in issue for issue in result["issues"])
    assert result["stress_audit_rows"][-1]["f_cgp (MPa; compression +)"] == pytest.approx(
        result["falsework_removed_fcgp_mpa"] + 9.9
    )
    # The fallback value is visible for diagnosis, but the result is blocked and cannot be adopted.
    assert result["status"] == "REVIEW REQUIRED"


def test_verified_later_load_runs_second_event_solve_and_ignores_manual_delta() -> None:
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

    result = run_crossbeam_event_stage_stress_sources(
        model=model,
        lightweight_es_result=es,
        profile_rows=profile,
        system_rows=system,
        later_permanent_load_delta_fcgp_mpa=9.9,
        later_permanent_load_rows=_verified_rows(),
    )

    assert result["ready"] is True
    assert result["solve_count"] == 2
    assert result["later_load_source_verified"] is True
    assert result["later_load_source_mode"] == "VERIFIED LOADS WORKSPACE EVENT SOLVE"
    assert result["later_permanent_load_delta_fcgp_mpa"] != pytest.approx(9.9)
    assert result["stress_audit_rows"][-1]["Engineer Δf_cd (MPa)"] == pytest.approx(0.0)
    assert result["stress_audit_rows"][-1]["Δf_cd source"] == (
        "VERIFIED LOADS WORKSPACE EVENT SOLVE"
    )
    verification = result["later_load_response_verification"]
    assert verification["ready"] is True
    assert verification["response_changed"] is True
    assert verification["fingerprints_differ"] is True
    assert verification["max_response_deltas"]["moment_kNm"] > 100.0
    assert verification["max_response_deltas"]["vertical_displacement_mm"] > 0.1
    assert verification["max_response_deltas"]["fcgp_mpa"] > 0.05


def test_time_dependent_route_uses_verified_later_load_source_and_two_event_solves() -> None:
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

    result = run_crossbeam_lightweight_time_dependent_loss(
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
        later_permanent_load_delta_fcgp_mpa=9.9,
        later_permanent_load_rows=_verified_rows(),
        inner_perimeter_factor=0.5,
        relaxation_steel_class=LOW_RELAXATION_STEEL,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
        fci_mpa=36.0,
    )

    assert result["ready"] is True
    assert result["adoptable"] is False
    assert result["solve_count"] == 2
    assert result["status"] == (
        "EVENT-BASED TIME-STEP QA READY — LATER LOAD VERIFIED · FINAL ADOPTION BLOCKED"
    )
    assert result["event_stress_source"]["later_load_source_verified"] is True
    events = {row["Event"]: row for row in result["schedule_source"]["events"]}
    assert events["Later permanent load"]["Calculation role"] == (
        "Verified Loads-workspace cumulative event solve; response-derived Δfcd"
    )
    assert "two cumulative event solves" in result["route_note"]
    assert "Pe/Pe_eff" in result["scope_guard"]


def test_project_json_round_trip_preserves_crossbeam_later_load_rows() -> None:
    session_state = {CB_LATER_PERMANENT_LOAD_TABLE_KEY: _verified_rows()}

    project = project_from_session_state(session_state)
    restored: dict[str, object] = {}
    apply_project_to_session_state(project, restored)

    saved_rows = project.metadata["workflow_load_tables"][
        CB_LATER_PERMANENT_LOAD_TABLE_KEY
    ]
    assert len(saved_rows) == 3
    assert saved_rows[2]["Load ID"] == "LP-UDL"
    restored_table = restored[CB_LATER_PERMANENT_LOAD_TABLE_KEY]
    assert restored_table.iloc[0]["Magnitude"] == pytest.approx(500.0)
    assert restored_table.iloc[2]["Load Type"] == UNIFORM_LINE_LOAD


def test_ptloss4b3_ui_routes_crossbeam_loads_and_exposes_event_audit() -> None:
    loads_source = Path("concrete_pmm_pro/ui/loads_page.py").read_text(encoding="utf-8")
    crossbeam_source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(
        encoding="utf-8"
    )

    assert 'if settings.member_type == "portal_frame_crossbeam"' in loads_source
    assert "Portal Frame Crossbeam — Later Permanent Load Event" in loads_source
    assert "0 structural solves" in loads_source
    assert "must coincide with the accepted 0.5 m frame mesh" in loads_source
    assert "PTLOSS4B3 adds one cumulative released-frame solve" in crossbeam_source
    assert "Later permanent-load source — Loads workspace" in crossbeam_source
    assert "Uniform line loads assigned to frame elements" in crossbeam_source
    assert "Later permanent-load response-source verification" in crossbeam_source
    assert "Frame-load closure residual (kN)" in crossbeam_source
