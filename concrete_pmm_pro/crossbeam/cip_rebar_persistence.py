"""Project-JSON persistence for Cast-in-Place Crossbeam continuous rebar topology.

``CROSSBEAM.RB-CIP1`` keeps this model deliberately separate from the accepted
Precast Segmental reinforcement block.  No Segmental template/zone data is
reinterpreted as Cast-in-Place bar runs, and loading a project never invents
continuous bars from legacy Segmental reinforcement.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from concrete_pmm_pro.crossbeam.cip_rebar import (
    CIP_REBAR_TOPOLOGY_SCHEMA_VERSION,
    canonical_cip_longitudinal_bar_runs,
    cip_rebar_topology_status,
)


CROSSBEAM_CIP_REBAR_METADATA_KEY = "crossbeam_cip_rebar_input_model"
CROSSBEAM_CIP_REBAR_SCHEMA_VERSION = 1

CB_RB_CIP_RUN_ROWS_KEY = "crossbeam_rb_cip1_longitudinal_run_rows"
CB_RB_CIP_RUN_REV_KEY = "crossbeam_rb_cip1_longitudinal_run_revision"
CB_RB_CIP_VALIDATION_KEY = "crossbeam_rb_cip1_validation"


def _state_has(session_state: Any, key: str) -> bool:
    if hasattr(session_state, "__contains__"):
        try:
            return key in session_state
        except Exception:
            pass
    return hasattr(session_state, key)


def _state_get(session_state: Any, key: str, default: Any = None) -> Any:
    if hasattr(session_state, "get"):
        return session_state.get(key, default)
    return getattr(session_state, key, default)


def crossbeam_cip_rebar_metadata_from_session_state(session_state: Any) -> dict[str, Any]:
    """Return JSON-safe CIP topology only when a project actually has run data."""

    if not _state_has(session_state, CB_RB_CIP_RUN_ROWS_KEY):
        return {}
    runs = canonical_cip_longitudinal_bar_runs(_state_get(session_state, CB_RB_CIP_RUN_ROWS_KEY, []))
    if not runs:
        return {}
    return {
        "schema_version": CROSSBEAM_CIP_REBAR_SCHEMA_VERSION,
        "topology_schema_version": CIP_REBAR_TOPOLOGY_SCHEMA_VERSION,
        "longitudinal_bar_runs": runs,
        "solver_handoff": "LOCKED",
    }


def restore_crossbeam_cip_rebar_project_state(
    project_metadata: Mapping[str, Any] | None,
    session_state: MutableMapping[str, Any],
    *,
    length_m: float,
) -> dict[str, Any] | None:
    """Restore CIP runs independently; never migrate Segmental data into them."""

    session_state.pop(CB_RB_CIP_RUN_ROWS_KEY, None)
    session_state.pop(CB_RB_CIP_VALIDATION_KEY, None)

    metadata = project_metadata if isinstance(project_metadata, Mapping) else {}
    raw = metadata.get(CROSSBEAM_CIP_REBAR_METADATA_KEY)
    if raw is None:
        return None

    errors: list[str] = []
    if not isinstance(raw, Mapping):
        runs: list[dict[str, Any]] = []
        errors.append(f"{CROSSBEAM_CIP_REBAR_METADATA_KEY} must be a JSON object.")
        source_version = 0
    else:
        try:
            source_version = int(raw.get("schema_version", 0) or 0)
        except (TypeError, ValueError):
            source_version = 0
        runs = canonical_cip_longitudinal_bar_runs(raw.get("longitudinal_bar_runs") or [])
        if source_version not in {0, CROSSBEAM_CIP_REBAR_SCHEMA_VERSION}:
            errors.append(
                f"Unsupported Cast-in-Place rebar schema version {source_version}; loaded data is preserved for REVIEW."
            )

    session_state[CB_RB_CIP_RUN_ROWS_KEY] = runs
    session_state[CB_RB_CIP_RUN_REV_KEY] = int(session_state.get(CB_RB_CIP_RUN_REV_KEY, 0) or 0) + 1
    validation = cip_rebar_topology_status(runs, length_m=length_m)
    if errors:
        validation["errors"] = list(dict.fromkeys(errors + list(validation.get("errors", []))))
        validation["status"] = "REVIEW REQUIRED"
    validation["source_schema_version"] = source_version
    validation["migrated_from_segmental"] = False
    session_state[CB_RB_CIP_VALIDATION_KEY] = validation
    return validation
