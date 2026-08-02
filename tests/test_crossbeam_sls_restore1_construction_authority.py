from __future__ import annotations

from copy import deepcopy

from concrete_pmm_pro.analysis.crossbeam_sls_transfer import (
    build_crossbeam_transfer_stress_preparation,
)
from concrete_pmm_pro.core.concrete_materials import default_concrete_materials
from concrete_pmm_pro.crossbeam.construction_stage import (
    CONSTRUCTION_METHOD_CIP,
    CONSTRUCTION_METHOD_PRECAST,
)
from concrete_pmm_pro.crossbeam.prestress_loss import (
    CB_LOSS_ES_CONSTRUCTION_METHOD_KEY,
    CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY,
    CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY,
)
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_ACTIVE_ID_KEY,
    CB_SECLIB_DEFINITIONS_KEY,
    SECLIB_METADATA_KEY,
    default_section_definitions,
    migrate_segment_rows_to_library,
)
from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_STATION_FORCE_CONTRACT_KEY,
    default_station_force_contract,
)
from concrete_pmm_pro.crossbeam.workflow import default_crossbeam_segment_rows
from concrete_pmm_pro.io.project_io import (
    CROSSBEAM_CONSTRUCTION_METHOD_LAST_STATE_KEY,
    apply_project_to_session_state,
    project_from_json,
    project_from_session_state,
    project_to_json,
)


def _transfer_row(station_m: float) -> dict[str, object]:
    return {
        "Active": True,
        "Station s (m)": station_m,
        "Check Point": "",
        "Case Name": "TR-CIP",
        "Stage": "Transfer stage",
        "P": 3000.0,
        "V2": 0.0,
        "T": 0.0,
        "M3": 0.0,
        "Note": "external FEA Transfer response",
    }


def _cip_source_state() -> dict[str, object]:
    length_m = 20.0
    definitions = default_section_definitions()
    segments = migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(length_m), definitions
    )
    solid_id = str(definitions[0]["Section ID"])
    for row in segments:
        row["Section ID"] = solid_id
        row["Section role"] = "Solid"
    contract = default_station_force_contract()
    contract["adopted_total_loss_percent"] = 17.286
    contract["effective_prestress_ratio_percent"] = 82.714
    return {
        "project_name": "Legacy CIP SLS restore regression",
        "crossbeam_ui1_length_m": length_m,
        "crossbeam_ui1_segment_layout_rows": segments,
        "crossbeam_cip1_cast_in_place_zone_rows": deepcopy(segments),
        CROSSBEAM_CONSTRUCTION_METHOD_LAST_STATE_KEY: CONSTRUCTION_METHOD_CIP,
        CB_LOSS_ES_CONSTRUCTION_METHOD_KEY: CONSTRUCTION_METHOD_CIP,
        CB_LOSS_ES_STRESSING_STRENGTH_RATIO_KEY: 0.80,
        CB_SECLIB_DEFINITIONS_KEY: definitions,
        CB_SECLIB_ACTIVE_ID_KEY: solid_id,
        "concrete_materials": default_concrete_materials(),
        CB_STATION_FORCE_CONTRACT_KEY: contract,
        "crossbeam_sls_loads_table": [
            _transfer_row(station) for station in range(0, 21, 2)
        ],
    }


def _project_with_stale_loss_method(*, legacy_member_key: bool) -> object:
    project = project_from_json(
        project_to_json(project_from_session_state(_cip_source_state()))
    )
    metadata = project.metadata
    member = dict(metadata[SECLIB_METADATA_KEY])
    assert member["construction_method"] == CONSTRUCTION_METHOD_CIP
    if legacy_member_key:
        member.pop("construction_method", None)
    member["construction_method_last"] = CONSTRUCTION_METHOD_CIP
    metadata[SECLIB_METADATA_KEY] = member
    loss = dict(metadata[CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY])
    loss["es_construction_method"] = CONSTRUCTION_METHOD_PRECAST
    metadata[CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY] = loss
    return project


def test_project_save_places_construction_type_with_member_geometry() -> None:
    project = project_from_session_state(_cip_source_state())

    assert (
        project.metadata[SECLIB_METADATA_KEY]["construction_method"]
        == CONSTRUCTION_METHOD_CIP
    )


def test_explicit_member_construction_type_wins_over_stale_loss_copy() -> None:
    restored: dict[str, object] = {}
    apply_project_to_session_state(
        _project_with_stale_loss_method(legacy_member_key=False), restored
    )

    preparation = build_crossbeam_transfer_stress_preparation(restored)
    assert restored[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] == CONSTRUCTION_METHOD_CIP
    assert preparation.construction_method == CONSTRUCTION_METHOD_CIP
    assert preparation.joint_stations_m == ()
    assert preparation.ready, preparation.errors


def test_legacy_member_last_key_migrates_without_inventing_precast_joint_gate() -> None:
    restored: dict[str, object] = {}
    apply_project_to_session_state(
        _project_with_stale_loss_method(legacy_member_key=True), restored
    )

    preparation = build_crossbeam_transfer_stress_preparation(restored)
    assert restored[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] == CONSTRUCTION_METHOD_CIP
    assert restored[CROSSBEAM_CONSTRUCTION_METHOD_LAST_STATE_KEY] == CONSTRUCTION_METHOD_CIP
    assert preparation.joint_stations_m == ()
    assert preparation.ready, preparation.errors


def test_true_precast_project_still_requires_physical_joint_coverage() -> None:
    state = _cip_source_state()
    state[CB_LOSS_ES_CONSTRUCTION_METHOD_KEY] = CONSTRUCTION_METHOD_PRECAST
    state[CROSSBEAM_CONSTRUCTION_METHOD_LAST_STATE_KEY] = CONSTRUCTION_METHOD_PRECAST
    project = project_from_json(project_to_json(project_from_session_state(state)))
    restored: dict[str, object] = {}
    apply_project_to_session_state(project, restored)

    preparation = build_crossbeam_transfer_stress_preparation(restored)
    assert preparation.construction_method == CONSTRUCTION_METHOD_PRECAST
    assert preparation.joint_stations_m
    assert preparation.ready is False
    assert any("physical joint" in error for error in preparation.errors)
