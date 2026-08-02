from __future__ import annotations

from copy import deepcopy

from concrete_pmm_pro.crossbeam.station_force_contract import (
    CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY,
    CB_STATION_FORCE_CONTRACT_KEY,
    CB_STATION_FORCE_VALIDATION_KEY,
    canonical_station_force_contract,
)
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state,
    project_from_session_state,
)
from concrete_pmm_pro.state.dirty_state import (
    mark_analysis_current,
    update_dirty_state_from_session,
)


def _ready_link() -> dict[str, object]:
    return {
        "ready": True,
        "source_id": "7c1ca3ebc192",
        "contract_id": "loss-contract-17",
        "source_fingerprint": "7c1ca3ebc192-full-fingerprint",
        "application_route": "DIRECT_EFFECTIVE_FORCE",
        "engineer_adopted_td": True,
        "average_total_loss_percent": 17.286,
        "effective_prestress_ratio_percent": 82.714,
        "average_effective_stress_mpa": 1_260.0,
        "average_effective_force_kn": 18_500.0,
    }


def _stale_contract() -> dict[str, object]:
    return {
        "adopted_total_loss_percent": 0.0,
        "effective_prestress_ratio_percent": 100.0,
        "prestress_source_id": "",
        "prestress_contract_id": "",
    }


def test_ready_effective_prestress_link_is_authoritative_over_stale_contract() -> None:
    contract = canonical_station_force_contract(
        _stale_contract(), effective_prestress_link=_ready_link()
    )

    assert contract["adopted_total_loss_percent"] == 17.286
    assert contract["effective_prestress_ratio_percent"] == 82.714
    assert contract["prestress_source_id"] == "7c1ca3ebc192"
    assert contract["prestress_contract_id"] == "loss-contract-17"


def test_nonready_link_does_not_overwrite_engineer_contract_values() -> None:
    contract = canonical_station_force_contract(
        {
            "adopted_total_loss_percent": 16.5,
            "prestress_source_id": "manual-source",
            "prestress_contract_id": "manual-contract",
        },
        effective_prestress_link={
            **_ready_link(),
            "ready": False,
            "average_total_loss_percent": 0.0,
            "effective_prestress_ratio_percent": 100.0,
        },
    )

    assert contract["adopted_total_loss_percent"] == 16.5
    assert contract["effective_prestress_ratio_percent"] == 83.5
    assert contract["prestress_source_id"] == "manual-source"
    assert contract["prestress_contract_id"] == "manual-contract"


def test_project_apply_clears_load_widget_transport_then_restores_canonical_contract() -> None:
    project = project_from_session_state(
        {
            "project_name": "Crossbeam load-sync regression",
            CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY: _ready_link(),
            CB_STATION_FORCE_CONTRACT_KEY: _stale_contract(),
        }
    )
    # Simulate an older saved JSON whose contract and ready link disagree.
    metadata = deepcopy(project.metadata)
    metadata[CB_STATION_FORCE_CONTRACT_KEY] = _stale_contract()
    project = project.model_copy(update={"metadata": metadata})
    restored: dict[str, object] = {
        "crossbeam_loads1b_adopted_total_loss_percent": 0.0,
        "crossbeam_loads1b_prestress_source_id": "",
        "crossbeam_loads1b_prestress_contract_id": "",
        "crossbeam_loads1b_source_force_unit": "N",
        "crossbeam_loads1b_contract_seed": "previous-project",
        CB_STATION_FORCE_VALIDATION_KEY: {"ready": False, "status": "STALE"},
    }

    apply_project_to_session_state(project, restored)

    assert not any(key.startswith("crossbeam_loads1b_") for key in restored)
    assert CB_STATION_FORCE_VALIDATION_KEY not in restored
    contract = restored[CB_STATION_FORCE_CONTRACT_KEY]
    assert contract["adopted_total_loss_percent"] == 17.286
    assert contract["effective_prestress_ratio_percent"] == 82.714
    assert contract["prestress_source_id"] == "7c1ca3ebc192"
    assert contract["prestress_contract_id"] == "loss-contract-17"


def test_station_force_contract_and_effective_link_are_load_dirty_state_inputs() -> None:
    state: dict[str, object] = {
        CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY: _ready_link(),
        CB_STATION_FORCE_CONTRACT_KEY: canonical_station_force_contract(
            _stale_contract(), effective_prestress_link=_ready_link()
        ),
    }
    update_dirty_state_from_session(state)
    mark_analysis_current(state, workspace="Analysis / Crossbeam")

    state[CB_STATION_FORCE_CONTRACT_KEY] = {
        **state[CB_STATION_FORCE_CONTRACT_KEY],
        "model_revision": "CB-FINAL-R04",
    }
    contract_status = update_dirty_state_from_session(state)

    assert contract_status.analysis_status == "Out of date"
    assert "Loads" in contract_status.changed_groups

    mark_analysis_current(state, workspace="Analysis / Crossbeam")
    state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY] = {
        **state[CB_EFFECTIVE_PRESTRESS_LOADS_LINK_KEY],
        "average_total_loss_percent": 18.0,
        "effective_prestress_ratio_percent": 82.0,
    }
    link_status = update_dirty_state_from_session(state)

    assert link_status.analysis_status == "Out of date"
    assert "Loads" in link_status.changed_groups
