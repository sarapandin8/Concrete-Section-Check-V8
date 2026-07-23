"""Project-JSON persistence for Crossbeam reinforcement input state.

``CROSSBEAM.RB-PERSIST1`` keeps the longitudinal/transverse template libraries,
Segment/Zone assignments, and stable preview selections together as one
solver-neutral input model.  This module deliberately knows nothing about
Streamlit widgets or analysis-result caches.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from concrete_pmm_pro.crossbeam.rebar import (
    RB_HOLLOW_MIN,
    RB_SOLID_COLUMN,
    canonical_rebar_templates,
    canonical_rebar_zones,
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
    segment_signature,
    template_map,
    validate_rebar_zones,
)
from concrete_pmm_pro.crossbeam.transverse import (
    canonical_transverse_templates,
    default_crossbeam_transverse_templates,
    default_transverse_template_id,
    transverse_template_map,
    validate_transverse_templates,
)


CROSSBEAM_REBAR_METADATA_KEY = "crossbeam_rebar_input_model"
CROSSBEAM_REBAR_SCHEMA_VERSION = 1

CB_RB_TEMPLATE_ROWS_KEY = "crossbeam_rb1_template_rows"
CB_RB_TEMPLATE_REV_KEY = "crossbeam_rb1_template_editor_revision"
CB_RB_ZONE_ROWS_KEY = "crossbeam_rb1_zone_assignment_rows"
CB_RB_ZONE_REV_KEY = "crossbeam_rb1_zone_editor_revision"
CB_RB_SEGMENT_SIGNATURE_KEY = "crossbeam_rb1_segment_signature"
CB_RB_SUBVIEW_KEY = "crossbeam_rb2_subview"
CB_RB_PREVIEW_SEGMENT_KEY = "crossbeam_rb2_preview_segment"
CB_RB_PREVIEW_ZONE_KEY = "crossbeam_rb2_preview_zone"
CB_RB_ACTIVE_TEMPLATE_KEY = "crossbeam_rb2a_active_template"
CB_RB_PREVIEW_MARKER_MODE_KEY = "crossbeam_rb2a_preview_marker_mode"

CB_TR_TEMPLATE_ROWS_KEY = "crossbeam_tr1_template_rows"
CB_TR_TEMPLATE_REV_KEY = "crossbeam_tr1_template_editor_revision"
CB_TR_PREVIEW_MODE_KEY = "crossbeam_tr1_preview_mode"

CB_RB_PROJECT_LOAD_VALIDATION_KEY = "crossbeam_rb_persist1_load_validation"
CB_RB_MIG1_ROLE_REPAIR_DONE_KEY = "crossbeam_rb_mig1_role_repair_done"

RB_SUBVIEW_OPTIONS = {
    "Templates",
    "Transverse / Shear",
    "Segment / Zone",
    "Section Rebar Preview",
    "Joint & Station Audit",
}
RB_PREVIEW_MODE_OPTIONS = {"Longitudinal", "Transverse / Shear", "Combined review"}
RB_MARKER_MODE_OPTIONS = {"Enhanced markers", "True bar diameter"}

_LONGITUDINAL_KEYS = (
    "longitudinal_templates",
    "longitudinal_template_library",
    "rebar_templates",
    CB_RB_TEMPLATE_ROWS_KEY,
)
_TRANSVERSE_KEYS = (
    "transverse_templates",
    "transverse_template_library",
    CB_TR_TEMPLATE_ROWS_KEY,
)
_ZONE_KEYS = (
    "zone_assignments",
    "segment_zone_assignments",
    "zones",
    CB_RB_ZONE_ROWS_KEY,
)
_LEGACY_BLOCK_KEYS = (
    "crossbeam_rebar_inputs",
    "crossbeam_rebar_model",
    "crossbeam_rebar",
)

# These keys may occur at metadata root in experimental/older project files.
# Current saves remove them after writing the versioned block above.
CROSSBEAM_REBAR_LEGACY_METADATA_KEYS = (
    CB_RB_TEMPLATE_ROWS_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_RB_SUBVIEW_KEY,
    CB_RB_PREVIEW_SEGMENT_KEY,
    CB_RB_PREVIEW_ZONE_KEY,
    CB_RB_ACTIVE_TEMPLATE_KEY,
    CB_RB_PREVIEW_MARKER_MODE_KEY,
    CB_TR_PREVIEW_MODE_KEY,
    *_LEGACY_BLOCK_KEYS,
)

_PREVIEW_FIELDS = {
    "subview": CB_RB_SUBVIEW_KEY,
    "segment_id": CB_RB_PREVIEW_SEGMENT_KEY,
    "zone_id": CB_RB_PREVIEW_ZONE_KEY,
    "active_longitudinal_template_id": CB_RB_ACTIVE_TEMPLATE_KEY,
    "preview_mode": CB_TR_PREVIEW_MODE_KEY,
    "marker_mode": CB_RB_PREVIEW_MARKER_MODE_KEY,
}


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


def _first_present(source: Mapping[str, Any], keys: tuple[str, ...]) -> tuple[bool, Any, str | None]:
    for key in keys:
        if key in source:
            return True, source.get(key), key
    return False, None, None


def _deduplicated(messages: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for message in messages:
        text = str(message or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def crossbeam_rebar_metadata_from_session_state(session_state: Any) -> dict[str, Any]:
    """Return a JSON-safe, input-only Crossbeam reinforcement block."""

    input_keys = (CB_RB_TEMPLATE_ROWS_KEY, CB_TR_TEMPLATE_ROWS_KEY, CB_RB_ZONE_ROWS_KEY)
    if not any(_state_has(session_state, key) for key in input_keys):
        return {}

    payload: dict[str, Any] = {"schema_version": CROSSBEAM_REBAR_SCHEMA_VERSION}
    if _state_has(session_state, CB_RB_TEMPLATE_ROWS_KEY):
        payload["longitudinal_templates"] = canonical_rebar_templates(
            _records(_state_get(session_state, CB_RB_TEMPLATE_ROWS_KEY))
        )
    if _state_has(session_state, CB_TR_TEMPLATE_ROWS_KEY):
        payload["transverse_templates"] = canonical_transverse_templates(
            _records(_state_get(session_state, CB_TR_TEMPLATE_ROWS_KEY))
        )
    if _state_has(session_state, CB_RB_ZONE_ROWS_KEY):
        payload["zone_assignments"] = canonical_rebar_zones(
            _records(_state_get(session_state, CB_RB_ZONE_ROWS_KEY))
        )

    preview: dict[str, str] = {}
    for metadata_name, state_key in _PREVIEW_FIELDS.items():
        if not _state_has(session_state, state_key):
            continue
        value = str(_state_get(session_state, state_key) or "").strip()
        if value:
            preview[metadata_name] = value
    if preview:
        payload["preview"] = preview
    return payload


def _canonical_project_block(raw: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    try:
        source_version = int(raw.get("schema_version", 0) or 0)
    except (TypeError, ValueError):
        source_version = 0
    migrated = source_version != CROSSBEAM_REBAR_SCHEMA_VERSION
    block: dict[str, Any] = {"schema_version": CROSSBEAM_REBAR_SCHEMA_VERSION}

    longitudinal_found, longitudinal_value, longitudinal_key = _first_present(raw, _LONGITUDINAL_KEYS)
    transverse_found, transverse_value, transverse_key = _first_present(raw, _TRANSVERSE_KEYS)
    zones_found, zones_value, zones_key = _first_present(raw, _ZONE_KEYS)

    libraries = raw.get("template_libraries")
    if isinstance(libraries, Mapping):
        if not longitudinal_found:
            longitudinal_found, longitudinal_value, longitudinal_key = _first_present(
                libraries, ("longitudinal", "longitudinal_templates", "rebar")
            )
        if not transverse_found:
            transverse_found, transverse_value, transverse_key = _first_present(
                libraries, ("transverse", "transverse_templates", "shear")
            )
        if longitudinal_found or transverse_found:
            migrated = True

    if longitudinal_found:
        block["longitudinal_templates"] = canonical_rebar_templates(_records(longitudinal_value))
        migrated = migrated or longitudinal_key != "longitudinal_templates"
    if transverse_found:
        block["transverse_templates"] = canonical_transverse_templates(_records(transverse_value))
        migrated = migrated or transverse_key != "transverse_templates"
    if zones_found:
        block["zone_assignments"] = canonical_rebar_zones(_records(zones_value))
        migrated = migrated or zones_key != "zone_assignments"

    preview_source = raw.get("preview")
    preview: dict[str, str] = {}
    if isinstance(preview_source, Mapping):
        for metadata_name in _PREVIEW_FIELDS:
            value = str(preview_source.get(metadata_name) or "").strip()
            if value:
                preview[metadata_name] = value
    for metadata_name, state_key in _PREVIEW_FIELDS.items():
        if metadata_name in preview or state_key not in raw:
            continue
        value = str(raw.get(state_key) or "").strip()
        if value:
            preview[metadata_name] = value
            migrated = True
    if preview:
        block["preview"] = preview
    return block, migrated


def crossbeam_rebar_metadata_from_project(
    metadata: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, bool, list[str]]:
    """Find and migrate a current or legacy Crossbeam reinforcement block."""

    source = metadata if isinstance(metadata, Mapping) else {}
    if CROSSBEAM_REBAR_METADATA_KEY in source:
        raw = source.get(CROSSBEAM_REBAR_METADATA_KEY)
        if not isinstance(raw, Mapping):
            return (
                {"schema_version": CROSSBEAM_REBAR_SCHEMA_VERSION},
                True,
                [f"{CROSSBEAM_REBAR_METADATA_KEY} must be a JSON object."],
            )
        block, migrated = _canonical_project_block(raw)
        return block, migrated, []

    for key in _LEGACY_BLOCK_KEYS:
        raw = source.get(key)
        if isinstance(raw, Mapping):
            block, _migrated = _canonical_project_block(raw)
            return block, True, [f"Migrated legacy Crossbeam reinforcement block '{key}'."]

    if any(key in source for key in (CB_RB_TEMPLATE_ROWS_KEY, CB_TR_TEMPLATE_ROWS_KEY, CB_RB_ZONE_ROWS_KEY)):
        block, _migrated = _canonical_project_block(source)
        return block, True, ["Migrated legacy flat Crossbeam reinforcement metadata."]

    crossbeam_inputs = source.get("crossbeam_input_model")
    if isinstance(crossbeam_inputs, Mapping) and any(
        key in crossbeam_inputs for key in (*_LONGITUDINAL_KEYS, *_TRANSVERSE_KEYS, *_ZONE_KEYS)
    ):
        block, _migrated = _canonical_project_block(crossbeam_inputs)
        return block, True, ["Migrated reinforcement data nested in the legacy Crossbeam input block."]
    return None, False, []


def _segment_role(segment: Mapping[str, Any]) -> str:
    role = str(segment.get("Section role") or "Solid").strip().title()
    return role if role in {"Solid", "Hollow"} else "Solid"


def _default_longitudinal_template_id_for_role(
    role: str,
    longitudinal_templates: list[dict[str, Any]],
) -> str:
    """Return a role-compatible longitudinal template without unsafe fallback.

    Legacy migration may encounter stale Zone assignments created before the
    current Segment Layout/Section Library role was available.  Preserve any
    already-compatible assignment.  When repair is required, prefer the
    accepted default template for the resolved Segment role, otherwise use the
    first active role-compatible project template.  Never fall back to an
    incompatible template merely because it is the first active row.
    """

    role_text = str(role or "Solid").strip().title()
    if role_text not in {"Solid", "Hollow"}:
        role_text = "Solid"
    active = list(template_map(longitudinal_templates).values())
    preferred = RB_HOLLOW_MIN if role_text == "Hollow" else RB_SOLID_COLUMN
    if any(str(row.get("Template ID") or "") == preferred for row in active):
        return preferred
    compatible = [
        row
        for row in active
        if str(row.get("Applicable role") or "Any").strip().title() in {role_text, "Any"}
    ]
    return str(compatible[0].get("Template ID") or "") if compatible else ""


def repair_migrated_zone_template_compatibility(
    zones: list[dict[str, Any]],
    segment_rows: list[dict[str, Any]],
    longitudinal_templates: list[dict[str, Any]],
    transverse_templates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    """Repair only incompatible legacy/migrated Zone-template references.

    The current Segment Layout + Section Library is the geometry source of
    truth.  Compatible custom legacy assignments are preserved byte-for-byte at
    the template-ID level; only missing/incompatible references are remapped.
    If no compatible project template exists, the original reference is left in
    place so validation reports REVIEW instead of silently substituting an
    incompatible fallback.
    """

    segment_by_id = {
        str(row.get("Segment") or "").strip(): row for row in _records(segment_rows)
    }
    longitudinal_map = template_map(longitudinal_templates)
    transverse_map = transverse_template_map(transverse_templates)
    repaired: list[dict[str, Any]] = []
    longitudinal_repairs = 0
    transverse_repairs = 0

    for source in canonical_rebar_zones(zones):
        row = dict(source)
        segment = segment_by_id.get(str(row.get("Segment") or "").strip(), {})
        role = _segment_role(segment)

        longitudinal_id = str(
            row.get("Longitudinal template") or row.get("Rebar template") or ""
        ).strip()
        longitudinal = longitudinal_map.get(longitudinal_id)
        longitudinal_role = (
            str(longitudinal.get("Applicable role") or "Any").strip().title()
            if longitudinal
            else ""
        )
        if longitudinal is None or longitudinal_role not in {role, "Any"}:
            replacement = _default_longitudinal_template_id_for_role(
                role, longitudinal_templates
            )
            if replacement:
                row["Rebar template"] = replacement
                row["Longitudinal template"] = replacement
                longitudinal_repairs += 1

        transverse_id = str(row.get("Transverse template") or "").strip()
        transverse = transverse_map.get(transverse_id)
        transverse_role = (
            str(transverse.get("Applicable role") or "Any").strip().title()
            if transverse
            else ""
        )
        if transverse is None or transverse_role not in {role, "Any"}:
            replacement = default_transverse_template_id(role, transverse_templates)
            replacement_row = transverse_map.get(replacement)
            replacement_role = (
                str(replacement_row.get("Applicable role") or "Any").strip().title()
                if replacement_row
                else ""
            )
            if replacement and replacement_role in {role, "Any"}:
                row["Transverse template"] = replacement
                transverse_repairs += 1

        repaired.append(row)

    return canonical_rebar_zones(repaired), longitudinal_repairs, transverse_repairs


def _fill_legacy_transverse_references(
    zones: list[dict[str, Any]],
    segment_rows: list[dict[str, Any]],
    transverse_templates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    segment_by_id = {str(row.get("Segment") or "").strip(): row for row in segment_rows}
    updated: list[dict[str, Any]] = []
    count = 0
    for source in canonical_rebar_zones(zones):
        row = dict(source)
        if not str(row.get("Transverse template") or "").strip():
            segment = segment_by_id.get(str(row.get("Segment") or ""), {})
            row["Transverse template"] = default_transverse_template_id(
                _segment_role(segment), transverse_templates
            )
            count += 1
        updated.append(row)
    return canonical_rebar_zones(updated), count


def validate_loaded_crossbeam_rebar_state(
    longitudinal_templates: list[dict[str, Any]],
    transverse_templates: list[dict[str, Any]],
    zone_assignments: list[dict[str, Any]],
    segment_rows: list[dict[str, Any]],
    *,
    load_errors: list[str] | None = None,
) -> dict[str, Any]:
    """Validate every loaded Segment and active Template reference."""

    longitudinal = canonical_rebar_templates(longitudinal_templates)
    transverse = canonical_transverse_templates(transverse_templates)
    zones = canonical_rebar_zones(zone_assignments)
    segments = _records(segment_rows)

    longitudinal_ids = set(template_map(longitudinal))
    transverse_ids = set(transverse_template_map(transverse))
    segment_ids = {
        str(row.get("Segment") or "").strip()
        for row in segments
        if str(row.get("Segment") or "").strip()
    }
    reference_errors: list[str] = []
    for zone in zones:
        zone_id = str(zone.get("Zone ID") or "(unnamed zone)")
        segment_id = str(zone.get("Segment") or "")
        longitudinal_id = str(zone.get("Longitudinal template") or zone.get("Rebar template") or "")
        transverse_id = str(zone.get("Transverse template") or "")
        if segment_id not in segment_ids:
            reference_errors.append(f"{zone_id}: Segment reference '{segment_id or '(blank)'}' does not resolve.")
        if longitudinal_id not in longitudinal_ids:
            reference_errors.append(
                f"{zone_id}: longitudinal Template ID '{longitudinal_id or '(blank)'}' does not resolve to an active template."
            )
        if transverse_id not in transverse_ids:
            reference_errors.append(
                f"{zone_id}: transverse Template ID '{transverse_id or '(blank)'}' does not resolve to an active template."
            )

    _transverse_rows, transverse_errors, transverse_warnings = validate_transverse_templates(transverse)
    _zone_rows, zone_errors, zone_warnings = validate_rebar_zones(
        zones,
        segments,
        longitudinal,
        transverse,
    )
    errors = _deduplicated(list(load_errors or []) + reference_errors + transverse_errors + zone_errors)
    warnings = _deduplicated(transverse_warnings + zone_warnings)
    return {
        "schema_version": CROSSBEAM_REBAR_SCHEMA_VERSION,
        "status": "READY" if not errors else "REVIEW REQUIRED",
        "references_resolved": not reference_errors,
        "errors": errors,
        "warnings": warnings,
        "longitudinal_template_count": len(longitudinal),
        "transverse_template_count": len(transverse),
        "zone_count": len(zones),
    }


def _restore_preview(
    preview: Mapping[str, Any],
    session_state: MutableMapping[str, Any],
    segment_rows: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    longitudinal_templates: list[dict[str, Any]],
) -> None:
    segment_ids = {str(row.get("Segment") or "") for row in segment_rows}
    zone_by_id = {str(row.get("Zone ID") or ""): row for row in zones}
    longitudinal_ids = set(template_map(longitudinal_templates))

    subview = str(preview.get("subview") or "")
    if subview in RB_SUBVIEW_OPTIONS:
        session_state[CB_RB_SUBVIEW_KEY] = subview
    preview_mode = str(preview.get("preview_mode") or "")
    if preview_mode in RB_PREVIEW_MODE_OPTIONS:
        session_state[CB_TR_PREVIEW_MODE_KEY] = preview_mode
    marker_mode = str(preview.get("marker_mode") or "")
    if marker_mode in RB_MARKER_MODE_OPTIONS:
        session_state[CB_RB_PREVIEW_MARKER_MODE_KEY] = marker_mode

    segment_id = str(preview.get("segment_id") or "")
    if segment_id in segment_ids:
        session_state[CB_RB_PREVIEW_SEGMENT_KEY] = segment_id
    zone_id = str(preview.get("zone_id") or "")
    zone = zone_by_id.get(zone_id)
    if zone is not None and (not segment_id or str(zone.get("Segment") or "") == segment_id):
        session_state[CB_RB_PREVIEW_ZONE_KEY] = zone_id
    template_id = str(preview.get("active_longitudinal_template_id") or "")
    if template_id in longitudinal_ids:
        session_state[CB_RB_ACTIVE_TEMPLATE_KEY] = template_id


def restore_crossbeam_rebar_project_state(
    project_metadata: Mapping[str, Any] | None,
    session_state: MutableMapping[str, Any],
    segment_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Restore Crossbeam inputs, migrate older files, and validate references."""

    segments = _records(segment_rows)
    block, migrated, migration_notes = crossbeam_rebar_metadata_from_project(project_metadata)

    for key in (
        CB_RB_TEMPLATE_ROWS_KEY,
        CB_TR_TEMPLATE_ROWS_KEY,
        CB_RB_ZONE_ROWS_KEY,
        CB_RB_SEGMENT_SIGNATURE_KEY,
        CB_RB_SUBVIEW_KEY,
        CB_RB_PREVIEW_SEGMENT_KEY,
        CB_RB_PREVIEW_ZONE_KEY,
        CB_RB_ACTIVE_TEMPLATE_KEY,
        CB_RB_PREVIEW_MARKER_MODE_KEY,
        CB_TR_PREVIEW_MODE_KEY,
    ):
        session_state.pop(key, None)
    session_state.pop(CB_RB_MIG1_ROLE_REPAIR_DONE_KEY, None)

    if block is None and not segments:
        session_state.pop(CB_RB_PROJECT_LOAD_VALIDATION_KEY, None)
        return None

    if block is None:
        migrated = True
        block = {"schema_version": CROSSBEAM_REBAR_SCHEMA_VERSION}
        migration_notes.append(
            "Older project had no Crossbeam reinforcement block; default input libraries and Zone assignments were generated from Segment Layout."
        )

    if "longitudinal_templates" in block:
        longitudinal = canonical_rebar_templates(_records(block.get("longitudinal_templates")))
    else:
        longitudinal = default_crossbeam_rebar_templates()
        migrated = True
        migration_notes.append("Added the default longitudinal template library.")

    if "transverse_templates" in block:
        transverse = canonical_transverse_templates(_records(block.get("transverse_templates")))
    else:
        transverse = default_crossbeam_transverse_templates()
        migrated = True
        migration_notes.append("Added the default transverse template library.")

    if "zone_assignments" in block:
        zones = canonical_rebar_zones(_records(block.get("zone_assignments")))
    else:
        zones = default_crossbeam_rebar_zones(segments, longitudinal, transverse) if segments else []
        migrated = True
        migration_notes.append("Generated Segment/Zone assignments from Segment Layout.")

    if migrated:
        zones, filled_count = _fill_legacy_transverse_references(zones, segments, transverse)
        if filled_count:
            migration_notes.append(
                f"Added {filled_count} missing Transverse Template reference(s) using each Segment role."
            )
        zones, longitudinal_repairs, transverse_repairs = repair_migrated_zone_template_compatibility(
            zones,
            segments,
            longitudinal,
            transverse,
        )
        if longitudinal_repairs:
            migration_notes.append(
                f"Repaired {longitudinal_repairs} legacy longitudinal Zone assignment(s) to match the current Segment Solid/Hollow role."
            )
        if transverse_repairs:
            migration_notes.append(
                f"Repaired {transverse_repairs} legacy transverse Zone assignment(s) to match the current Segment Solid/Hollow role."
            )

    session_state[CB_RB_TEMPLATE_ROWS_KEY] = longitudinal
    session_state[CB_TR_TEMPLATE_ROWS_KEY] = transverse
    session_state[CB_RB_ZONE_ROWS_KEY] = zones
    session_state[CB_RB_TEMPLATE_REV_KEY] = int(session_state.get(CB_RB_TEMPLATE_REV_KEY, 0) or 0) + 1
    session_state[CB_TR_TEMPLATE_REV_KEY] = int(session_state.get(CB_TR_TEMPLATE_REV_KEY, 0) or 0) + 1
    session_state[CB_RB_ZONE_REV_KEY] = int(session_state.get(CB_RB_ZONE_REV_KEY, 0) or 0) + 1
    if segments:
        session_state[CB_RB_SEGMENT_SIGNATURE_KEY] = segment_signature(segments)

    preview = block.get("preview")
    if isinstance(preview, Mapping):
        _restore_preview(preview, session_state, segments, zones, longitudinal)

    validation = validate_loaded_crossbeam_rebar_state(
        longitudinal,
        transverse,
        zones,
        segments,
        load_errors=[note for note in migration_notes if "must be a JSON object" in note],
    )
    validation["migrated"] = bool(migrated)
    validation["migration_notes"] = _deduplicated(migration_notes)
    session_state[CB_RB_PROJECT_LOAD_VALIDATION_KEY] = validation
    return validation
