from __future__ import annotations

import pandas as pd
import pytest

from concrete_pmm_pro.crossbeam.construction_stage import CONSTRUCTION_METHOD_PRECAST
from concrete_pmm_pro.crossbeam.later_permanent_response import (
    CB_LATER_FEA_RESPONSE_TABLE_KEY,
    CB_TD_PERMANENT_EVENT_SCHEDULE_KEY,
    CB_TD_FEA_RESPONSE_METADATA_KEY,
    resolve_imported_permanent_load_events,
    td_permanent_event_schedule_status,
)
from concrete_pmm_pro.crossbeam.time_dependent_loss import (
    LOW_RELAXATION_STEEL,
    run_crossbeam_lightweight_time_dependent_loss,
)
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_session_state
from tests.test_crossbeam_ptloss4a_time_dependent import _sources
from tests.test_crossbeam_ptloss4b3_imported_later_fea import _valid_rows


def _multi_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for case, scale in (("GIRDER_INC", 1.0), ("TRACK_INC", 0.5)):
        for source in _valid_rows():
            row = dict(source)
            row["Active"] = False  # PTLOSS4B3B maps rows automatically by Case Name.
            row["Case Name"] = case
            row["P"] = float(row["P"]) * scale
            row["V2"] = float(row["V2"]) * scale
            row["M3"] = float(row["M3"]) * scale
            rows.append(row)
    return rows


def _schedule() -> list[dict[str, object]]:
    return [
        {
            "Adopt": True,
            "Event ID": "PL1",
            "Permanent load group": "Beam / Girder permanent load — CIP / PC / Steel",
            "Activation age (days)": 60.0,
            "Case Name": "GIRDER_INC",
        },
        {
            "Adopt": True,
            "Event ID": "PL5",
            "Permanent load group": "SDL track work / Utility",
            "Activation age (days)": 180.0,
            "Case Name": "TRACK_INC",
        },
    ]


def test_multi_event_schedule_accepts_separate_activation_ages_and_cases() -> None:
    status = td_permanent_event_schedule_status(
        _schedule(),
        falsework_removal_age_days=35.0,
        final_age_days=18250.0,
        imported_case_names=["GIRDER_INC", "TRACK_INC"],
    )
    assert status["ready"] is True
    assert status["adopted_count"] == 2
    assert [row["Activation age (days)"] for row in status["adopted_rows"]] == [60.0, 180.0]


def test_multi_event_resolver_maps_all_rows_by_case_without_row_active_clicks() -> None:
    _length, _definitions, _segments, system, _settings, _es, model, profile = _sources()
    result = resolve_imported_permanent_load_events(
        model=model,
        load_rows=_multi_rows(),
        event_schedule=_schedule(),
        profile_rows=profile,
        system_rows=system,
        falsework_removal_age_days=35.0,
        final_age_days=18250.0,
    )
    assert result["ready"] is True
    assert result["status"] == "MULTI-EVENT FEA SOURCES VERIFIED"
    assert result["active_count"] == 2
    assert len(result["cumulative_points"]) == 2
    first = result["cumulative_points"][0]
    second = result["cumulative_points"][1]
    assert second["Cumulative Δf_cd (MPa)"] > first["Cumulative Δf_cd (MPa)"] > 0.0
    assert result["fingerprint"]


def test_multi_event_time_step_adds_one_interval_per_distinct_activation_age() -> None:
    length, definitions, segments, system, settings, es, model, profile = _sources()
    result = run_crossbeam_lightweight_time_dependent_loss(
        lightweight_es_result=es,
        length_m=length,
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
        later_fea_response_rows=_multi_rows(),
        permanent_load_event_schedule=_schedule(),
        inner_perimeter_factor=0.5,
        relaxation_steel_class=LOW_RELAXATION_STEEL,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
        fci_mpa=36.0,
    )
    assert result["ready"] is True
    assert result["solve_count"] == 1
    assert result["schedule_time_step"]["interval_count"] == 4
    assert [row["t end (days)"] for row in result["schedule_time_step"]["rows"]] == [35.0, 60.0, 180.0, 18250.0]
    event_source = result["event_stress_source"]
    assert event_source["later_permanent_load_source_mode"] == "VERIFIED MULTI-EVENT IMPORTED FEA SOURCE"
    assert len(event_source["cumulative_fcgp_by_event"]) == 2


def test_multi_event_schedule_blocks_obvious_nonpermanent_case_names() -> None:
    schedule = _schedule()
    schedule[0]["Case Name"] = "ULS_STRENGTH_I"
    status = td_permanent_event_schedule_status(
        schedule,
        falsework_removal_age_days=35.0,
        final_age_days=18250.0,
        imported_case_names=["ULS_STRENGTH_I", "TRACK_INC"],
    )
    assert status["ready"] is False
    assert any("excluded response token" in issue for issue in status["issues"])


def test_project_json_round_trip_preserves_multi_event_schedule() -> None:
    source = {
        CB_LATER_FEA_RESPONSE_TABLE_KEY: pd.DataFrame(_multi_rows()),
        CB_TD_PERMANENT_EVENT_SCHEDULE_KEY: pd.DataFrame(_schedule()),
    }
    project = project_from_session_state(source)
    metadata = project.metadata[CB_TD_FEA_RESPONSE_METADATA_KEY]
    assert metadata["schema_version"] == 2
    assert len(metadata["permanent_event_schedule"]) == 2

    restored: dict[str, object] = {}
    apply_project_to_session_state(project, restored)
    restored_schedule = restored[CB_TD_PERMANENT_EVENT_SCHEDULE_KEY]
    assert list(restored_schedule["Case Name"]) == ["GIRDER_INC", "TRACK_INC"]


def test_no_later_permanent_events_remains_a_valid_schedule() -> None:
    length, definitions, segments, system, settings, es, model, profile = _sources()
    empty_schedule = [
        {
            "Adopt": False,
            "Event ID": "PL1",
            "Permanent load group": "Beam / Girder permanent load — CIP / PC / Steel",
            "Activation age (days)": "",
            "Case Name": "",
        }
    ]
    result = run_crossbeam_lightweight_time_dependent_loss(
        lightweight_es_result=es,
        length_m=length,
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
        later_fea_response_rows=[],
        permanent_load_event_schedule=empty_schedule,
        inner_perimeter_factor=0.5,
        relaxation_steel_class=LOW_RELAXATION_STEEL,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
        fci_mpa=36.0,
    )
    assert result["ready"] is True
    assert result["solve_count"] == 1
    assert result["schedule_time_step"]["interval_count"] == 2
    assert result["event_stress_source"]["later_permanent_load_source_mode"] == "NO LATER PERMANENT EVENTS"
    assert result["creep_loss_mpa"] == pytest.approx(78.3698, abs=5.0e-3)
    assert result["shrinkage_loss_mpa"] == pytest.approx(40.8906, abs=5.0e-3)
    assert result["relaxation_loss_mpa"] == pytest.approx(7.8887, abs=5.0e-3)
    assert result["time_dependent_loss_mpa"] == pytest.approx(127.1491, abs=1.0e-2)


def test_earlier_permanent_event_increases_creep_duration_vs_same_total_load_applied_later() -> None:
    length, definitions, segments, system, settings, es, model, profile = _sources()
    split_rows = _multi_rows()
    combined_rows: list[dict[str, object]] = []
    for source in _valid_rows():
        row = dict(source)
        row["Active"] = False
        row["Case Name"] = "COMBINED_LATE_INC"
        row["P"] = float(row["P"]) * 1.5
        row["V2"] = float(row["V2"]) * 1.5
        row["M3"] = float(row["M3"]) * 1.5
        combined_rows.append(row)
    combined_schedule = [
        {
            "Adopt": True,
            "Event ID": "PLX",
            "Permanent load group": "Other permanent load",
            "Activation age (days)": 180.0,
            "Case Name": "COMBINED_LATE_INC",
        }
    ]

    common = dict(
        lightweight_es_result=es,
        length_m=length,
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
        inner_perimeter_factor=0.5,
        relaxation_steel_class=LOW_RELAXATION_STEEL,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
        fci_mpa=36.0,
    )
    split = run_crossbeam_lightweight_time_dependent_loss(
        **common,
        later_fea_response_rows=split_rows,
        permanent_load_event_schedule=_schedule(),
    )
    combined = run_crossbeam_lightweight_time_dependent_loss(
        **common,
        later_fea_response_rows=combined_rows,
        permanent_load_event_schedule=combined_schedule,
    )
    assert split["event_stress_source"]["later_permanent_load_delta_fcgp_mpa"] == pytest.approx(
        combined["event_stress_source"]["later_permanent_load_delta_fcgp_mpa"]
    )
    assert split["creep_loss_mpa"] > combined["creep_loss_mpa"]
