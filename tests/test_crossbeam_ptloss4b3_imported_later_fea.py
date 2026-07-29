from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from concrete_pmm_pro.crossbeam.construction_stage import CONSTRUCTION_METHOD_PRECAST
from concrete_pmm_pro.crossbeam.later_permanent_response import (
    CB_LATER_FEA_RESPONSE_TABLE_KEY,
    CB_TD_FEA_SOURCE_DECLARATION_KEY,
    CB_TD_FEA_RESPONSE_METADATA_KEY,
    TD_FEA_IMPORT_MODE_INCREMENTAL,
    resolve_imported_later_fea_response,
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


def _valid_rows() -> list[dict[str, object]]:
    return [
        {
            "Active": True,
            "Station x (m)": 1.5,
            "Case Name": "LATER-PERM",
            "Step Type": "Linear Static",
            "Step Num": 1,
            "FEA Object": "CB",
            "FEA Element": "E-L",
            "End / Side": "Right-side limit",
            "Section ID": "CB-S01",
            "P": 1000.0,
            "V2": 100.0,
            "M3": 0.0,
            "Note": "left column",
        },
        {
            "Active": True,
            "Station x (m)": 10.0,
            "Case Name": "LATER-PERM",
            "Step Type": "Linear Static",
            "Step Num": 1,
            "FEA Object": "CB",
            "FEA Element": "E-M",
            "End / Side": "Right-side limit",
            "Section ID": "CB-H01",
            "P": 1000.0,
            "V2": 0.0,
            "M3": 0.0,
            "Note": "span center",
        },
        {
            "Active": True,
            "Station x (m)": 18.5,
            "Case Name": "LATER-PERM",
            "Step Type": "Linear Static",
            "Step Num": 1,
            "FEA Object": "CB",
            "FEA Element": "E-R",
            "End / Side": "Right-side limit",
            "Section ID": "CB-H01",
            "P": 1000.0,
            "V2": -100.0,
            "M3": 0.0,
            "Note": "right column",
        },
    ]




def _valid_declaration() -> dict[str, object]:
    return {
        "import_mode": TD_FEA_IMPORT_MODE_INCREMENTAL,
        "fea_program": "CSiBridge",
        "source_case_stage": "LATER-PERM",
        "permanent_load_groups": "GIRDER_REACTION + TRACK_PLINTH",
        "unfactored_confirmed": True,
        "incremental_not_total_confirmed": True,
        "excluded_transient_confirmed": True,
        "common_activation_age_confirmed": True,
    }

def test_imported_later_fea_response_preserves_row_coupled_force_tuple() -> None:
    length, _defs, _segments, system, _settings, _es, model, profile = _sources()
    result = resolve_imported_later_fea_response(
        model=model,
        load_rows=_valid_rows(),
        profile_rows=profile,
        system_rows=system,
        source_declaration=_valid_declaration(),
    )

    assert length == pytest.approx(20.0)
    assert result["ready"] is True
    assert result["status"] == "VERIFIED IMPORTED FEA SOURCE"
    assert result["case_name"] == "LATER-PERM"
    assert result["delta_fcgp_mpa"] == pytest.approx(1000.0 * 1000.0 / 2162730.969810918)
    assert len(result["audit_rows"]) == 3
    governing = result["governing_row"]
    assert governing["P (kN; compression +)"] == pytest.approx(1000.0)
    assert governing["M3 (kN-m; sagging +)"] == pytest.approx(0.0)
    assert result["fingerprint"]


def test_imported_later_fea_response_blocks_declared_case_mismatch() -> None:
    _length, _defs, _segments, system, _settings, _es, model, profile = _sources()
    declaration = _valid_declaration()
    declaration["source_case_stage"] = "OTHER-CASE"
    result = resolve_imported_later_fea_response(
        model=model,
        load_rows=_valid_rows(),
        profile_rows=profile,
        system_rows=system,
        source_declaration=declaration,
    )

    assert result["ready"] is False
    assert any("does not match active imported Case Name" in issue for issue in result["issues"])


def test_imported_later_fea_response_blocks_mixed_cases() -> None:
    _length, _defs, _segments, system, _settings, _es, model, profile = _sources()
    rows = _valid_rows()
    rows[-1]["Case Name"] = "OTHER-CASE"
    result = resolve_imported_later_fea_response(
        model=model,
        load_rows=rows,
        profile_rows=profile,
        system_rows=system,
        source_declaration=_valid_declaration(),
    )

    assert result["ready"] is False
    assert any("exactly one adopted FEA case" in issue for issue in result["issues"])


def test_time_dependent_route_uses_imported_fea_delta_with_one_internal_solve() -> None:
    length, definitions, segments, system, settings, es, model, profile = _sources()
    baseline = run_crossbeam_lightweight_time_dependent_loss(
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
        later_permanent_load_delta_fcgp_mpa=0.0,
        inner_perimeter_factor=0.5,
        relaxation_steel_class=LOW_RELAXATION_STEEL,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
        fci_mpa=36.0,
    )
    imported = run_crossbeam_lightweight_time_dependent_loss(
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
        later_permanent_load_delta_fcgp_mpa=0.0,
        later_fea_response_rows=_valid_rows(),
        later_fea_source_declaration=_valid_declaration(),
        inner_perimeter_factor=0.5,
        relaxation_steel_class=LOW_RELAXATION_STEEL,
        ep_mpa=settings["ep_mpa"],
        eci_mpa=28200.0,
        fci_mpa=36.0,
    )

    assert imported["solve_count"] == 1
    source = imported["event_stress_source"]["later_fea_response_source"]
    assert source["ready"] is True
    assert imported["event_stress_source"]["later_permanent_load_source_mode"] == "VERIFIED IMPORTED FEA SOURCE"
    assert imported["time_dependent_loss_mpa"] > baseline["time_dependent_loss_mpa"]
    events = {row["Event"]: row for row in imported["schedule_source"]["events"]}
    assert events["Later permanent load"]["Calculation role"] == (
        "Imported incremental FEA P/V2/M3 response at tp; no internal structural solve"
    )
    assert imported["scope_guard"].startswith("PTLOSS4B3A uses one event solve")


def test_imported_source_requires_complete_declaration_when_provided() -> None:
    _length, _defs, _segments, system, _settings, _es, model, profile = _sources()
    result = resolve_imported_later_fea_response(
        model=model,
        load_rows=_valid_rows(),
        profile_rows=profile,
        system_rows=system,
        source_declaration={"fea_program": "CSiBridge"},
    )
    assert result["ready"] is False
    assert any("Permanent load groups" in issue for issue in result["issues"])
    assert any("incremental" in issue.lower() for issue in result["issues"])


def test_project_json_round_trip_preserves_crossbeam_td_fea_source_under_prestress_ownership() -> None:
    source = {
        CB_LATER_FEA_RESPONSE_TABLE_KEY: pd.DataFrame(_valid_rows()),
        CB_TD_FEA_SOURCE_DECLARATION_KEY: _valid_declaration(),
    }
    project = project_from_session_state(source)
    td_meta = project.metadata[CB_TD_FEA_RESPONSE_METADATA_KEY]
    assert td_meta["owner"] == "Sections/Prestress Loss/Time-Dependent"
    assert td_meta["rows"][0]["Case Name"] == "LATER-PERM"
    assert CB_LATER_FEA_RESPONSE_TABLE_KEY not in project.metadata.get("workflow_load_tables", {})

    restored: dict[str, object] = {}
    apply_project_to_session_state(project, restored)
    table = pd.DataFrame(restored[CB_LATER_FEA_RESPONSE_TABLE_KEY])
    assert len(table) == 3
    assert table.iloc[2]["FEA Element"] == "E-R"
    assert restored[CB_TD_FEA_SOURCE_DECLARATION_KEY]["fea_program"] == "CSiBridge"


def test_ptloss4b3_project_json_migrates_legacy_loads_owned_source() -> None:
    project = project_from_session_state({})
    metadata = dict(project.metadata)
    metadata["workflow_load_tables"] = {
        CB_LATER_FEA_RESPONSE_TABLE_KEY: _valid_rows(),
    }
    legacy_project = project.model_copy(update={"metadata": metadata})

    restored: dict[str, object] = {}
    apply_project_to_session_state(legacy_project, restored)
    assert len(pd.DataFrame(restored[CB_LATER_FEA_RESPONSE_TABLE_KEY])) == 3
    assert restored[CB_TD_FEA_SOURCE_DECLARATION_KEY]["fea_program"] == ""
    assert "MIGRATED FROM PTLOSS4B3" in restored["crossbeam_ptloss4b3a_td_fea_migration_status"]

    resaved = project_from_session_state(restored)
    assert CB_LATER_FEA_RESPONSE_TABLE_KEY not in resaved.metadata.get("workflow_load_tables", {})
    assert CB_TD_FEA_RESPONSE_METADATA_KEY in resaved.metadata


def test_crossbeam_uls_sls_tables_remain_main_loads_owned() -> None:
    source = {
        "crossbeam_uls_loads_table": pd.DataFrame([
            {"Active": True, "Station s (m)": 10.0, "Case Name": "ULS-01", "P": 1.0, "V2": 2.0, "T": 3.0, "M3": 4.0, "Note": ""}
        ]),
        "crossbeam_sls_loads_table": pd.DataFrame([
            {"Active": True, "Station s (m)": 10.0, "Case Name": "SLS-01", "Stage": "Service stage", "P": 1.0, "V2": 2.0, "T": 3.0, "M3": 4.0, "Note": ""}
        ]),
    }
    project = project_from_session_state(source)
    assert "crossbeam_uls_loads_table" in project.metadata["workflow_load_tables"]
    assert "crossbeam_sls_loads_table" in project.metadata["workflow_load_tables"]


def test_ptloss4b3a_relocates_import_out_of_main_loads_workspace() -> None:
    loads_source = Path("concrete_pmm_pro/ui/loads_page.py").read_text(encoding="utf-8")
    crossbeam_source = Path("concrete_pmm_pro/ui/crossbeam_pages.py").read_text(encoding="utf-8")
    assert "def _render_crossbeam_later_fea_response_table" not in loads_source
    assert "def _render_crossbeam_uls_sls_load_tables" in loads_source
    assert "This main Loads workspace owns Crossbeam ULS and SLS design-demand imports only" in loads_source
    assert "def _render_crossbeam_td_fea_response_import" in crossbeam_source
    assert "Construction-Stage FEA Response at tp" in crossbeam_source
    assert "What this tp import must include / exclude" in crossbeam_source
    assert "Incremental response — not total Final Stage forces" in crossbeam_source
