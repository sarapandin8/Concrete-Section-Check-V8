"""Project-JSON persistence for Cast-in-Place Crossbeam reinforcement.

RB-CIP1/RB-CIP2 introduced an experimental station-based longitudinal bar-run
foundation.  RB-CIP2A aligns the user workflow with the accepted Precast
Segmental Rebar pattern: Solid-only longitudinal/transverse template libraries
assigned to Cast-in-Place Section/Zones, with continuity reviewed across Zone
boundaries.  The legacy bar-run payload is preserved non-destructively but is
not silently converted into the template model.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from concrete_pmm_pro.crossbeam.cip_rebar import (
    CIP_REBAR_TOPOLOGY_SCHEMA_VERSION,
    canonical_cip_longitudinal_bar_runs,
    cip_rebar_topology_status,
)
from concrete_pmm_pro.crossbeam.cip_rebar_templates import (
    CIP_RB_PREVIEW_ZONE_KEY,
    CIP_RB_SUBVIEW_KEY,
    CIP_RB_TEMPLATE_REV_KEY,
    CIP_RB_TEMPLATE_ROWS_KEY,
    CIP_RB_ZONE_REV_KEY,
    CIP_RB_ZONE_ROWS_KEY,
    CIP_TR_TEMPLATE_REV_KEY,
    CIP_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.rebar import canonical_rebar_templates, canonical_rebar_zones
from concrete_pmm_pro.crossbeam.transverse import canonical_transverse_templates


CROSSBEAM_CIP_REBAR_METADATA_KEY = "crossbeam_cip_rebar_input_model"
CROSSBEAM_CIP_REBAR_SCHEMA_VERSION = 2

# Legacy RB-CIP1/RB-CIP2 run-state keys remain supported for non-destructive load/save.
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


def _records(value: Any) -> list[dict[str, Any]]:
    if hasattr(value, "to_dict"):
        try:
            value = value.to_dict(orient="records")
        except Exception:
            value = []
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def crossbeam_cip_rebar_metadata_from_session_state(session_state: Any) -> dict[str, Any]:
    """Return JSON-safe CIP Rebar input state without mixing Precast state."""

    model_present = any(
        _state_has(session_state, key)
        for key in (CIP_RB_TEMPLATE_ROWS_KEY, CIP_TR_TEMPLATE_ROWS_KEY, CIP_RB_ZONE_ROWS_KEY)
    )
    legacy_runs_present = _state_has(session_state, CB_RB_CIP_RUN_ROWS_KEY)
    if not model_present and not legacy_runs_present:
        return {}

    payload: dict[str, Any] = {"schema_version": CROSSBEAM_CIP_REBAR_SCHEMA_VERSION}
    if _state_has(session_state, CIP_RB_TEMPLATE_ROWS_KEY):
        payload["longitudinal_templates"] = canonical_rebar_templates(
            _records(_state_get(session_state, CIP_RB_TEMPLATE_ROWS_KEY, []))
        )
    if _state_has(session_state, CIP_TR_TEMPLATE_ROWS_KEY):
        payload["transverse_templates"] = canonical_transverse_templates(
            _records(_state_get(session_state, CIP_TR_TEMPLATE_ROWS_KEY, []))
        )
    if _state_has(session_state, CIP_RB_ZONE_ROWS_KEY):
        payload["zone_assignments"] = canonical_rebar_zones(
            _records(_state_get(session_state, CIP_RB_ZONE_ROWS_KEY, []))
        )

    preview: dict[str, str] = {}
    for name, key in (("subview", CIP_RB_SUBVIEW_KEY), ("zone_id", CIP_RB_PREVIEW_ZONE_KEY)):
        if _state_has(session_state, key):
            value = str(_state_get(session_state, key) or "").strip()
            if value:
                preview[name] = value
    if preview:
        payload["preview"] = preview

    # Preserve legacy RB-CIP2 runs but never reinterpret them as templates.
    if legacy_runs_present:
        runs = canonical_cip_longitudinal_bar_runs(_state_get(session_state, CB_RB_CIP_RUN_ROWS_KEY, []))
        if runs:
            # Keep the RB-CIP1/RB-CIP2 field for backward compatibility while
            # also marking the same rows explicitly as legacy in schema v2.
            payload["longitudinal_bar_runs"] = runs
            payload["legacy_longitudinal_bar_runs"] = runs
            payload["legacy_topology_schema_version"] = CIP_REBAR_TOPOLOGY_SCHEMA_VERSION

    payload["solver_handoff"] = "LOCKED"
    return payload


def restore_crossbeam_cip_rebar_project_state(
    project_metadata: Mapping[str, Any] | None,
    session_state: MutableMapping[str, Any],
    *,
    length_m: float,
) -> dict[str, Any] | None:
    """Restore CIP Rebar state independently from Precast Segmental Rebar state."""

    for key in (
        CIP_RB_TEMPLATE_ROWS_KEY,
        CIP_TR_TEMPLATE_ROWS_KEY,
        CIP_RB_ZONE_ROWS_KEY,
        CIP_RB_PREVIEW_ZONE_KEY,
        CIP_RB_SUBVIEW_KEY,
        CB_RB_CIP_RUN_ROWS_KEY,
        CB_RB_CIP_VALIDATION_KEY,
    ):
        session_state.pop(key, None)

    metadata = project_metadata if isinstance(project_metadata, Mapping) else {}
    raw = metadata.get(CROSSBEAM_CIP_REBAR_METADATA_KEY)
    if raw is None:
        return None

    errors: list[str] = []
    warnings: list[str] = []
    source_version = 0
    if not isinstance(raw, Mapping):
        errors.append(f"{CROSSBEAM_CIP_REBAR_METADATA_KEY} must be a JSON object.")
        raw = {}
    else:
        try:
            source_version = int(raw.get("schema_version", 0) or 0)
        except (TypeError, ValueError):
            source_version = 0

    if source_version not in {0, 1, CROSSBEAM_CIP_REBAR_SCHEMA_VERSION}:
        errors.append(
            f"Unsupported Cast-in-Place rebar schema version {source_version}; loaded data is preserved for REVIEW where possible."
        )

    long_rows = canonical_rebar_templates(_records(raw.get("longitudinal_templates")))
    trans_rows = canonical_transverse_templates(_records(raw.get("transverse_templates")))
    zone_rows = canonical_rebar_zones(_records(raw.get("zone_assignments")))
    if long_rows:
        session_state[CIP_RB_TEMPLATE_ROWS_KEY] = long_rows
    if trans_rows:
        session_state[CIP_TR_TEMPLATE_ROWS_KEY] = trans_rows
    if zone_rows:
        session_state[CIP_RB_ZONE_ROWS_KEY] = zone_rows

    preview = raw.get("preview")
    if isinstance(preview, Mapping):
        if preview.get("subview"):
            session_state[CIP_RB_SUBVIEW_KEY] = str(preview.get("subview"))
        if preview.get("zone_id"):
            session_state[CIP_RB_PREVIEW_ZONE_KEY] = str(preview.get("zone_id"))

    # Schema v1 stored only longitudinal_bar_runs.  Schema v2 may preserve them
    # under legacy_longitudinal_bar_runs.  In both cases they remain dormant.
    legacy_source = raw.get("legacy_longitudinal_bar_runs")
    if legacy_source is None:
        legacy_source = raw.get("longitudinal_bar_runs")
    runs = canonical_cip_longitudinal_bar_runs(_records(legacy_source))
    if runs:
        session_state[CB_RB_CIP_RUN_ROWS_KEY] = runs
        session_state[CB_RB_CIP_RUN_REV_KEY] = int(session_state.get(CB_RB_CIP_RUN_REV_KEY, 0) or 0) + 1
        warnings.append(
            "Legacy RB-CIP2 station-based bar-run data was preserved but not converted into the template/Section-Zone model. Review and re-enter adopted reinforcement using the aligned CIP Rebar workflow."
        )

    session_state[CIP_RB_TEMPLATE_REV_KEY] = int(session_state.get(CIP_RB_TEMPLATE_REV_KEY, 0) or 0) + 1
    session_state[CIP_TR_TEMPLATE_REV_KEY] = int(session_state.get(CIP_TR_TEMPLATE_REV_KEY, 0) or 0) + 1
    session_state[CIP_RB_ZONE_REV_KEY] = int(session_state.get(CIP_RB_ZONE_REV_KEY, 0) or 0) + 1

    if runs and not long_rows and not trans_rows and not zone_rows and not errors:
        # Preserve the accepted RB-CIP1/RB-CIP2 validation contract for old
        # projects that contain only the legacy run model.  RB-CIP2A UI still
        # treats those rows as dormant and asks the engineer to adopt the new
        # template/Zone workflow explicitly.
        validation = cip_rebar_topology_status(runs, length_m=length_m)
        validation["warnings"] = list(dict.fromkeys(list(validation.get("warnings", [])) + warnings))
        validation["errors"] = list(validation.get("errors", []))
        validation["source_schema_version"] = source_version
        validation["migrated_from_segmental"] = False
        validation["legacy_runs_preserved"] = True
    else:
        validation = {
            "status": "REVIEW REQUIRED" if errors or warnings else "LOADED",
            "errors": errors,
            "warnings": warnings,
            "source_schema_version": source_version,
            "migrated_from_segmental": False,
            "legacy_runs_preserved": bool(runs),
            "solver_handoff": "LOCKED",
        }
    if runs:
        validation["legacy_run_validation"] = cip_rebar_topology_status(runs, length_m=length_m)
    session_state[CB_RB_CIP_VALIDATION_KEY] = validation
    return validation
