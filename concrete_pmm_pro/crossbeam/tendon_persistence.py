"""Project-JSON persistence for Crossbeam tendon input state.

``CROSSBEAM.PT1`` stores only engineer-entered tendon-system and top-referenced
profile inputs.  The block is workflow-scoped and deliberately excludes loss,
stress, strength, continuity, anchorage-zone, and analysis-result data.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from concrete_pmm_pro.crossbeam.tendon import (
    canonical_tendon_profile_points,
    canonical_tendon_system_rows,
    default_tendon_profile_points,
    default_tendon_system_rows,
    section_context_records,
    validate_tendon_profile,
    validate_tendon_system,
)


CROSSBEAM_TENDON_METADATA_KEY = "crossbeam_tendon_input_model"
CROSSBEAM_TENDON_SCHEMA_VERSION = 1

CB_TENDON_COUNT_KEY = "crossbeam_ui1_tendon_count"
CB_TENDON_SYSTEM_ROWS_KEY = "crossbeam_ui1_tendon_system_rows"
CB_TENDON_SYSTEM_REV_KEY = "crossbeam_ui1_tendon_system_editor_revision"
CB_PROFILE_ROWS_KEY = "crossbeam_ui1_tendon_profile_points"
CB_PROFILE_REV_KEY = "crossbeam_ui1_tendon_profile_editor_revision"
CB_ACTIVE_TENDONS_KEY = "crossbeam_ui1_active_tendon_ids"
CB_3D_TRANSPARENT_KEY = "crossbeam_ui1_3d_transparent"
CB_TENDON_PROJECT_LOAD_VALIDATION_KEY = "crossbeam_pt1_project_load_validation"

_SYSTEM_KEYS = (
    "tendon_system",
    "tendon_system_rows",
    "tendons",
    CB_TENDON_SYSTEM_ROWS_KEY,
)
_PROFILE_KEYS = (
    "profile_points",
    "tendon_profile_points",
    "tendon_profile_rows",
    CB_PROFILE_ROWS_KEY,
)
_LEGACY_BLOCK_KEYS = (
    "crossbeam_tendon_inputs",
    "crossbeam_tendon_model",
    "crossbeam_tendons",
)

CROSSBEAM_TENDON_LEGACY_METADATA_KEYS = (
    CB_TENDON_COUNT_KEY,
    CB_TENDON_SYSTEM_ROWS_KEY,
    CB_PROFILE_ROWS_KEY,
    CB_ACTIVE_TENDONS_KEY,
    CB_3D_TRANSPARENT_KEY,
    *_LEGACY_BLOCK_KEYS,
)


def _state_get(session_state: Any, key: str, default: Any = None) -> Any:
    if hasattr(session_state, "get"):
        return session_state.get(key, default)
    return getattr(session_state, key, default)


def _state_has(session_state: Any, key: str) -> bool:
    if hasattr(session_state, "__contains__"):
        try:
            return key in session_state
        except Exception:
            pass
    return hasattr(session_state, key)


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            rows = value.to_dict(orient="records")
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
        except (TypeError, ValueError):
            pass
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _first_present(source: Mapping[str, Any], keys: tuple[str, ...]) -> tuple[bool, Any, str | None]:
    for key in keys:
        if key in source:
            return True, source.get(key), key
    return False, None, None


def _deduplicated(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(str(message).strip() for message in messages if str(message).strip()))


def crossbeam_tendon_metadata_from_session_state(session_state: Any) -> dict[str, Any]:
    """Return a JSON-safe, input-only PT1 block."""

    if not any(
        _state_has(session_state, key)
        for key in (CB_TENDON_SYSTEM_ROWS_KEY, CB_PROFILE_ROWS_KEY)
    ):
        return {}

    length_m = max(_float(_state_get(session_state, "crossbeam_ui1_length_m", 20.0), 20.0), 0.1)
    payload: dict[str, Any] = {
        "schema_version": CROSSBEAM_TENDON_SCHEMA_VERSION,
        "tendon_system": canonical_tendon_system_rows(
            _records(_state_get(session_state, CB_TENDON_SYSTEM_ROWS_KEY, []))
        ),
        "profile_points": canonical_tendon_profile_points(
            _records(_state_get(session_state, CB_PROFILE_ROWS_KEY, [])),
            length_m,
        ),
    }
    active_ids = [
        str(value).strip()
        for value in (_state_get(session_state, CB_ACTIVE_TENDONS_KEY, []) or [])
        if str(value).strip()
    ]
    preview: dict[str, Any] = {}
    if active_ids:
        preview["visible_tendon_ids"] = active_ids
    if _state_has(session_state, CB_3D_TRANSPARENT_KEY):
        preview["transparent_3d"] = bool(_state_get(session_state, CB_3D_TRANSPARENT_KEY, True))
    if preview:
        payload["preview"] = preview
    return payload


def _canonical_project_block(raw: Mapping[str, Any], *, length_m: float) -> tuple[dict[str, Any], bool]:
    try:
        source_version = int(raw.get("schema_version", 0) or 0)
    except (TypeError, ValueError):
        source_version = 0
    migrated = source_version != CROSSBEAM_TENDON_SCHEMA_VERSION
    block: dict[str, Any] = {"schema_version": CROSSBEAM_TENDON_SCHEMA_VERSION}

    system_found, system_value, system_key = _first_present(raw, _SYSTEM_KEYS)
    profile_found, profile_value, profile_key = _first_present(raw, _PROFILE_KEYS)
    if system_found:
        block["tendon_system"] = canonical_tendon_system_rows(_records(system_value))
        migrated = migrated or system_key != "tendon_system"
    if profile_found:
        block["profile_points"] = canonical_tendon_profile_points(_records(profile_value), length_m)
        migrated = migrated or profile_key != "profile_points"

    preview_source = raw.get("preview")
    preview: dict[str, Any] = {}
    if isinstance(preview_source, Mapping):
        ids = preview_source.get("visible_tendon_ids")
        if isinstance(ids, (list, tuple)):
            preview["visible_tendon_ids"] = [str(value).strip() for value in ids if str(value).strip()]
        if "transparent_3d" in preview_source:
            preview["transparent_3d"] = bool(preview_source.get("transparent_3d"))
    if "visible_tendon_ids" not in preview and CB_ACTIVE_TENDONS_KEY in raw:
        ids = raw.get(CB_ACTIVE_TENDONS_KEY)
        if isinstance(ids, (list, tuple)):
            preview["visible_tendon_ids"] = [str(value).strip() for value in ids if str(value).strip()]
            migrated = True
    if "transparent_3d" not in preview and CB_3D_TRANSPARENT_KEY in raw:
        preview["transparent_3d"] = bool(raw.get(CB_3D_TRANSPARENT_KEY))
        migrated = True
    if preview:
        block["preview"] = preview
    return block, migrated


def crossbeam_tendon_metadata_from_project(
    metadata: Mapping[str, Any] | None,
    *,
    length_m: float,
) -> tuple[dict[str, Any] | None, bool, list[str]]:
    """Find and migrate a current or legacy Crossbeam tendon block."""

    source = metadata if isinstance(metadata, Mapping) else {}
    if CROSSBEAM_TENDON_METADATA_KEY in source:
        raw = source.get(CROSSBEAM_TENDON_METADATA_KEY)
        if not isinstance(raw, Mapping):
            return (
                {"schema_version": CROSSBEAM_TENDON_SCHEMA_VERSION},
                True,
                [f"{CROSSBEAM_TENDON_METADATA_KEY} must be a JSON object."],
            )
        block, migrated = _canonical_project_block(raw, length_m=length_m)
        return block, migrated, []

    for key in _LEGACY_BLOCK_KEYS:
        raw = source.get(key)
        if isinstance(raw, Mapping):
            block, _ = _canonical_project_block(raw, length_m=length_m)
            return block, True, [f"Migrated legacy Crossbeam tendon block '{key}'."]

    if any(key in source for key in (CB_TENDON_SYSTEM_ROWS_KEY, CB_PROFILE_ROWS_KEY)):
        block, _ = _canonical_project_block(source, length_m=length_m)
        return block, True, ["Migrated legacy flat Crossbeam tendon metadata."]

    crossbeam_inputs = source.get("crossbeam_input_model")
    if isinstance(crossbeam_inputs, Mapping) and any(
        key in crossbeam_inputs for key in (*_SYSTEM_KEYS, *_PROFILE_KEYS)
    ):
        block, _ = _canonical_project_block(crossbeam_inputs, length_m=length_m)
        return block, True, ["Migrated tendon data nested in the legacy Crossbeam input block."]
    return None, False, []


def validate_loaded_crossbeam_tendon_state(
    tendon_system: Any,
    profile_points: Any,
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
    load_errors: list[str] | None = None,
) -> dict[str, Any]:
    system, system_errors, system_warnings = validate_tendon_system(tendon_system)
    points, profile_errors, profile_warnings = validate_tendon_profile(
        profile_points,
        system,
        length_m=length_m,
        segment_rows=segment_rows,
        section_definitions=section_definitions,
    )
    errors = _deduplicated(list(load_errors or []) + system_errors + profile_errors)
    warnings = _deduplicated(system_warnings + profile_warnings)
    reference_errors = [message for message in errors if "unknown Tendon ID" in message]
    return {
        "schema_version": CROSSBEAM_TENDON_SCHEMA_VERSION,
        "status": "SOURCE READY" if not errors else "REVIEW REQUIRED",
        "references_resolved": not reference_errors,
        "errors": errors,
        "warnings": warnings,
        "tendon_count": len(system),
        "active_tendon_count": sum(bool(row.get("Active")) for row in system),
        "profile_point_count": len(points),
        "pt_continuity": "REQUIRED — NOT VERIFIED",
    }


def restore_crossbeam_tendon_project_state(
    project_metadata: Mapping[str, Any] | None,
    session_state: MutableMapping[str, Any],
    *,
    length_m: float,
    segment_rows: Any,
    section_definitions: Any,
) -> dict[str, Any] | None:
    """Restore PT1 inputs, seed older Crossbeam projects, and validate references."""

    length = max(_float(length_m, 20.0), 0.1)
    segments = _records(segment_rows)
    definitions = _records(section_definitions)
    block, migrated, migration_notes = crossbeam_tendon_metadata_from_project(
        project_metadata,
        length_m=length,
    )

    for key in (
        CB_TENDON_COUNT_KEY,
        CB_TENDON_SYSTEM_ROWS_KEY,
        CB_PROFILE_ROWS_KEY,
        CB_ACTIVE_TENDONS_KEY,
        CB_3D_TRANSPARENT_KEY,
    ):
        session_state.pop(key, None)

    if block is None and not segments:
        session_state.pop(CB_TENDON_PROJECT_LOAD_VALIDATION_KEY, None)
        return None
    if block is None:
        block = {"schema_version": CROSSBEAM_TENDON_SCHEMA_VERSION}
        migrated = True
        migration_notes.append(
            "Older project had no Crossbeam tendon block; default Tendon System and top-referenced profile points were generated."
        )

    if "tendon_system" in block:
        system = canonical_tendon_system_rows(block.get("tendon_system"))
    else:
        system = default_tendon_system_rows()
        migrated = True
        migration_notes.append("Added the default four-tendon system.")

    tendon_ids = [row["Tendon ID"] for row in system if row.get("Tendon ID")]
    if "profile_points" in block:
        points = canonical_tendon_profile_points(block.get("profile_points"), length)
    else:
        contexts = list(section_context_records(definitions).values())
        width = max((_float(row.get("Width mm"), 0.0) for row in contexts), default=2500.0)
        height = max((_float(row.get("Height mm"), 0.0) for row in contexts), default=1500.0)
        points = default_tendon_profile_points(
            length,
            tendon_ids=tendon_ids,
            width_mm=width or 2500.0,
            height_mm=height or 1500.0,
        )
        migrated = True
        migration_notes.append("Added default three-point top-referenced profiles for every tendon.")

    session_state[CB_TENDON_SYSTEM_ROWS_KEY] = system
    session_state[CB_PROFILE_ROWS_KEY] = points
    # Compatibility mirror only. The stored tendon-system rows are the source
    # of truth, including for incomplete projects that require review.
    session_state[CB_TENDON_COUNT_KEY] = len(system)
    session_state[CB_TENDON_SYSTEM_REV_KEY] = int(
        session_state.get(CB_TENDON_SYSTEM_REV_KEY, 0) or 0
    ) + 1
    session_state[CB_PROFILE_REV_KEY] = int(session_state.get(CB_PROFILE_REV_KEY, 0) or 0) + 1

    valid_ids = {row["Tendon ID"] for row in system if row.get("Tendon ID")}
    preview = block.get("preview")
    if isinstance(preview, Mapping):
        visible = [
            str(value).strip()
            for value in (preview.get("visible_tendon_ids") or [])
            if str(value).strip() in valid_ids
        ]
        session_state[CB_ACTIVE_TENDONS_KEY] = visible or [
            row["Tendon ID"] for row in system if row.get("Active") and row.get("Tendon ID")
        ]
        session_state[CB_3D_TRANSPARENT_KEY] = bool(preview.get("transparent_3d", True))
    else:
        session_state[CB_ACTIVE_TENDONS_KEY] = [
            row["Tendon ID"] for row in system if row.get("Active") and row.get("Tendon ID")
        ]
        session_state[CB_3D_TRANSPARENT_KEY] = True

    validation = validate_loaded_crossbeam_tendon_state(
        system,
        points,
        length_m=length,
        segment_rows=segments,
        section_definitions=definitions,
        load_errors=[note for note in migration_notes if "must be a JSON object" in note],
    )
    validation["migrated"] = bool(migrated)
    validation["migration_notes"] = _deduplicated(migration_notes)
    session_state[CB_TENDON_PROJECT_LOAD_VALIDATION_KEY] = validation
    return validation
