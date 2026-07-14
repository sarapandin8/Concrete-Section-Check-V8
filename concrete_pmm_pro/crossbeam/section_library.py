"""Crossbeam section-instance library and segment-assignment helpers.

CROSSBEAM.SECLIB1 separates reusable geometry *families* (presets) from the
actual project section definitions assigned along the crossbeam.  A project can
therefore contain several hollow sections with different top/bottom flange and
left/right web thicknesses without adding hard-coded global presets.

This module is deliberately solver-neutral.  It creates and validates section
geometry/properties for review and future station routing, but it does not feed
ULS/SLS calculations in this milestone.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.workflow import (
    CROSSBEAM_HOLLOW_PRESET_KEY,
    CROSSBEAM_HOLLOW_PRESET_NAME,
    CROSSBEAM_SECTION_PRESETS,
    CROSSBEAM_SOLID_PRESET_KEY,
    CROSSBEAM_SOLID_PRESET_NAME,
)
from concrete_pmm_pro.geometry import default_registry
from concrete_pmm_pro.geometry.presets import load_section_presets, preset_by_key
from concrete_pmm_pro.geometry.summary import summarize_geometry
from concrete_pmm_pro.geometry.validation import validate_section_geometry

SECLIB_SCHEMA_VERSION = 1
SECLIB_METADATA_KEY = "crossbeam_input_model"

CB_SECLIB_DEFINITIONS_KEY = "crossbeam_seclib1_definitions"
CB_SECLIB_ACTIVE_ID_KEY = "crossbeam_seclib1_active_section_id"
CB_SECLIB_REVISION_KEY = "crossbeam_seclib1_revision"
CB_SECLIB_LOADED_ID_KEY = "crossbeam_seclib1_loaded_builder_section_id"
CB_SECLIB_MIGRATION_KEY = "crossbeam_seclib1_migrated"

DEFAULT_SOLID_SECTION_ID = "CB-S01"
DEFAULT_HOLLOW_SECTION_ID = "CB-H01"


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _preset_catalog() -> dict[str, dict[str, Any]]:
    allowed = {key: (name, role) for key, name, role in CROSSBEAM_SECTION_PRESETS}
    result: dict[str, dict[str, Any]] = {}
    try:
        presets = load_section_presets()
    except Exception:
        presets = []
    for preset in presets:
        key = str(preset.get("key") or "")
        if key in allowed:
            result[key] = dict(preset)
    for key, (name, role) in allowed.items():
        if key not in result:
            result[key] = {
                "key": key,
                "display_name": name,
                "category": "Portal Frame Crossbeam",
                "parameters": [],
                "generator": key,
                "dimensions_generator": f"{key}_dimensions",
            }
        result[key]["crossbeam_role"] = role
    return result


def crossbeam_preset_catalog() -> list[dict[str, Any]]:
    """Return Crossbeam geometry-family metadata in stable Solid/Hollow order."""

    catalog = _preset_catalog()
    return [catalog[key] for key, _name, _role in CROSSBEAM_SECTION_PRESETS]


def preset_role(preset_key: str) -> str:
    if str(preset_key) == CROSSBEAM_HOLLOW_PRESET_KEY:
        return "Hollow"
    return "Solid"


def preset_display_name(preset_key: str) -> str:
    if str(preset_key) == CROSSBEAM_HOLLOW_PRESET_KEY:
        return CROSSBEAM_HOLLOW_PRESET_NAME
    return CROSSBEAM_SOLID_PRESET_NAME


def preset_default_parameters(preset_key: str) -> dict[str, float]:
    """Return only geometry parameters and their configured defaults."""

    try:
        preset = preset_by_key(str(preset_key))
    except Exception:
        preset = _preset_catalog()[str(preset_key)]
    params: dict[str, float] = {}
    for parameter in preset.get("parameters", []):
        if str(parameter.get("type", "number")) != "number":
            continue
        name = str(parameter.get("name") or "")
        if not name:
            continue
        params[name] = _float(parameter.get("default", parameter.get("min", 0.0)), 0.0)
    return params


def geometry_parameter_names(preset_key: str) -> list[str]:
    try:
        preset = preset_by_key(str(preset_key))
    except Exception:
        preset = _preset_catalog()[str(preset_key)]
    return [
        str(parameter.get("name"))
        for parameter in preset.get("parameters", [])
        if parameter.get("name") and str(parameter.get("type", "number")) == "number"
    ]


def canonical_parameters(preset_key: str, parameters: Mapping[str, Any] | None) -> dict[str, float]:
    defaults = preset_default_parameters(preset_key)
    source = parameters if isinstance(parameters, Mapping) else {}
    result: dict[str, float] = {}
    for name in geometry_parameter_names(preset_key):
        result[name] = _float(source.get(name), defaults.get(name, 0.0))
    return result


def canonical_section_definition(value: Mapping[str, Any], index: int = 0) -> dict[str, Any]:
    preset_key = str(value.get("Preset key") or value.get("preset_key") or CROSSBEAM_SOLID_PRESET_KEY)
    if preset_key not in {CROSSBEAM_SOLID_PRESET_KEY, CROSSBEAM_HOLLOW_PRESET_KEY}:
        preset_key = CROSSBEAM_SOLID_PRESET_KEY
    role = preset_role(preset_key)
    default_prefix = "CB-H" if role == "Hollow" else "CB-S"
    section_id = str(value.get("Section ID") or value.get("section_id") or f"{default_prefix}{index + 1:02d}").strip()
    section_name = str(value.get("Section name") or value.get("section_name") or f"{role} section {index + 1}").strip()
    material_name = str(value.get("Material") or value.get("material_name") or "C45_PRECAST").strip()
    parameters = canonical_parameters(preset_key, value.get("Parameters") or value.get("parameters"))
    return {
        "Section ID": section_id,
        "Section name": section_name,
        "Preset key": preset_key,
        "Preset family": preset_display_name(preset_key),
        "Section role": role,
        "Material": material_name,
        "Parameters": parameters,
    }


def canonical_section_definitions(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            continue
        row = canonical_section_definition(value, index)
        section_id = row["Section ID"]
        if not section_id or section_id in seen:
            continue
        seen.add(section_id)
        result.append(row)
    return result


def default_section_definitions(
    *,
    active_preset_key: str | None = None,
    active_parameters: Mapping[str, Any] | None = None,
    material_name: str = "C45_PRECAST",
) -> list[dict[str, Any]]:
    """Seed one Solid and one Hollow instance, preserving active Builder data."""

    active_key = str(active_preset_key or "")
    solid_params = preset_default_parameters(CROSSBEAM_SOLID_PRESET_KEY)
    hollow_params = preset_default_parameters(CROSSBEAM_HOLLOW_PRESET_KEY)
    if active_key == CROSSBEAM_SOLID_PRESET_KEY:
        solid_params = canonical_parameters(active_key, active_parameters)
    elif active_key == CROSSBEAM_HOLLOW_PRESET_KEY:
        hollow_params = canonical_parameters(active_key, active_parameters)
    return [
        canonical_section_definition(
            {
                "Section ID": DEFAULT_SOLID_SECTION_ID,
                "Section name": "Solid column region",
                "Preset key": CROSSBEAM_SOLID_PRESET_KEY,
                "Material": material_name,
                "Parameters": solid_params,
            },
            0,
        ),
        canonical_section_definition(
            {
                "Section ID": DEFAULT_HOLLOW_SECTION_ID,
                "Section name": "Hollow typical",
                "Preset key": CROSSBEAM_HOLLOW_PRESET_KEY,
                "Material": material_name,
                "Parameters": hollow_params,
            },
            1,
        ),
    ]


def definition_map(values: Any) -> dict[str, dict[str, Any]]:
    return {row["Section ID"]: row for row in canonical_section_definitions(values)}


def section_ids_for_role(values: Any, role: str) -> list[str]:
    target = str(role or "").strip().title()
    return [row["Section ID"] for row in canonical_section_definitions(values) if row["Section role"] == target]


def default_section_id_for_role(values: Any, role: str) -> str | None:
    ids = section_ids_for_role(values, role)
    return ids[0] if ids else None


def unique_section_id(values: Any, role: str) -> str:
    existing = set(definition_map(values))
    prefix = "CB-H" if str(role).title() == "Hollow" else "CB-S"
    index = 1
    while f"{prefix}{index:02d}" in existing:
        index += 1
    return f"{prefix}{index:02d}"


def duplicate_definition(values: Any, section_id: str) -> tuple[list[dict[str, Any]], str]:
    definitions = canonical_section_definitions(values)
    source = definition_map(definitions).get(str(section_id))
    if source is None:
        raise KeyError(f"Section definition not found: {section_id}")
    clone = deepcopy(source)
    new_id = unique_section_id(definitions, clone["Section role"])
    clone["Section ID"] = new_id
    clone["Section name"] = f"{clone['Section name']} copy"
    definitions.append(clone)
    return definitions, new_id


def add_default_definition(values: Any, preset_key: str, material_name: str = "C45_PRECAST") -> tuple[list[dict[str, Any]], str]:
    definitions = canonical_section_definitions(values)
    role = preset_role(preset_key)
    new_id = unique_section_id(definitions, role)
    number = len(section_ids_for_role(definitions, role)) + 1
    definitions.append(
        canonical_section_definition(
            {
                "Section ID": new_id,
                "Section name": f"{role} section {number}",
                "Preset key": preset_key,
                "Material": material_name,
                "Parameters": preset_default_parameters(preset_key),
            },
            len(definitions),
        )
    )
    return definitions, new_id


def rename_definition(
    values: Any,
    old_section_id: str,
    *,
    new_section_id: str,
    new_section_name: str,
) -> list[dict[str, Any]]:
    definitions = canonical_section_definitions(values)
    old_id = str(old_section_id).strip()
    new_id = str(new_section_id).strip()
    new_name = str(new_section_name).strip()
    if not new_id:
        raise ValueError("Section ID is required.")
    if new_id != old_id and new_id in definition_map(definitions):
        raise ValueError(f"Section ID already exists: {new_id}")
    found = False
    for row in definitions:
        if row["Section ID"] == old_id:
            row["Section ID"] = new_id
            row["Section name"] = new_name or new_id
            found = True
            break
    if not found:
        raise KeyError(f"Section definition not found: {old_id}")
    return definitions


def build_geometry_for_definition(value: Mapping[str, Any]) -> Any:
    definition = canonical_section_definition(value)
    preset = preset_by_key(definition["Preset key"])
    params = canonical_parameters(definition["Preset key"], definition["Parameters"])
    geometry_params = {name: params[name] for name in geometry_parameter_names(definition["Preset key"])}
    return default_registry.geometry(str(preset["generator"]))(
        **geometry_params,
        name=f"{definition['Section ID']} — {definition['Section name']}",
    )


def section_property_record(value: Mapping[str, Any]) -> dict[str, Any]:
    definition = canonical_section_definition(value)
    base = {
        **definition,
        "Area mm²": None,
        "Centroid from top mm": None,
        "Ix mm4": None,
        "Iy mm4": None,
        "Z top mm3": None,
        "Z bottom mm3": None,
        "Status": "NOT READY",
        "Errors": [],
        "Warnings": [],
    }
    try:
        geometry = build_geometry_for_definition(definition)
        validation = validate_section_geometry(geometry)
        base["Errors"] = list(validation.errors)
        base["Warnings"] = list(validation.warnings)
        if not validation.is_valid:
            return base
        summary = summarize_geometry(geometry)
        height = definition["Parameters"].get("height_mm", 0.0)
        base.update(
            {
                "Area mm²": float(summary.area_mm2),
                "Centroid from top mm": float(height) - float(summary.centroid_y_from_bottom_mm),
                "Ix mm4": float(summary.ix_nmm4) if summary.ix_nmm4 is not None else None,
                "Iy mm4": float(summary.iy_nmm4) if summary.iy_nmm4 is not None else None,
                "Z top mm3": float(summary.z_top_mm3) if summary.z_top_mm3 is not None else None,
                "Z bottom mm3": float(summary.z_bottom_mm3) if summary.z_bottom_mm3 is not None else None,
                "Status": "READY" if not validation.warnings else "REVIEW",
            }
        )
    except Exception as exc:
        base["Errors"] = [str(exc)]
    return base


def section_property_records(values: Any) -> list[dict[str, Any]]:
    return [section_property_record(row) for row in canonical_section_definitions(values)]


def validate_section_definitions(values: Any) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    definitions = canonical_section_definitions(values)
    errors: list[str] = []
    warnings: list[str] = []
    raw_ids = [str(row.get("Section ID") or "").strip() for row in values if isinstance(row, Mapping)] if isinstance(values, list) else []
    duplicates = sorted({item for item in raw_ids if item and raw_ids.count(item) > 1})
    for item in duplicates:
        errors.append(f"Duplicate Section ID: {item}.")
    if not definitions:
        errors.append("At least one Crossbeam section definition is required.")
    roles = {row["Section role"] for row in definitions}
    for role in ("Solid", "Hollow"):
        if role not in roles:
            warnings.append(f"No {role} section definition is available.")
    for record in section_property_records(definitions):
        for message in record["Errors"]:
            errors.append(f"{record['Section ID']}: {message}")
        for message in record["Warnings"]:
            warnings.append(f"{record['Section ID']}: {message}")
    return definitions, errors, warnings


def section_ids_used_by_segments(segment_rows: Any) -> dict[str, list[str]]:
    usage: dict[str, list[str]] = {}
    if not isinstance(segment_rows, (list, tuple)):
        return usage
    for row in segment_rows:
        if not isinstance(row, Mapping):
            continue
        section_id = str(row.get("Section ID") or "").strip()
        segment = str(row.get("Segment") or "").strip()
        if section_id:
            usage.setdefault(section_id, []).append(segment or "Unnamed segment")
    return usage


def replace_section_id_in_segments(segment_rows: Any, old_id: str, new_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not isinstance(segment_rows, (list, tuple)):
        return result
    for source in segment_rows:
        if not isinstance(source, Mapping):
            continue
        row = dict(source)
        if str(row.get("Section ID") or "").strip() == str(old_id).strip():
            row["Section ID"] = str(new_id).strip()
        result.append(row)
    return result


def migrate_segment_rows_to_library(segment_rows: Any, definitions: Any) -> list[dict[str, Any]]:
    """Replace legacy preset keys/names with project Section IDs.

    Existing station boundaries and segment names are preserved.  Legacy rows
    are mapped to the first definition of the matching Solid/Hollow family.
    """

    definition_rows = canonical_section_definitions(definitions)
    by_id = definition_map(definition_rows)
    by_preset: dict[str, str] = {}
    by_role: dict[str, str] = {}
    for definition in definition_rows:
        by_preset.setdefault(definition["Preset key"], definition["Section ID"])
        by_role.setdefault(definition["Section role"], definition["Section ID"])

    rows: list[dict[str, Any]] = []
    if not isinstance(segment_rows, (list, tuple)):
        return rows
    for index, source in enumerate(segment_rows):
        if not isinstance(source, Mapping):
            continue
        row = dict(source)
        raw_id = str(row.get("Section ID") or "").strip()
        preset_key = str(row.get("Section preset key") or "").strip()
        preset_name = str(row.get("Section type / preset") or "").strip()
        role = str(row.get("Section role") or "").strip().title()
        if raw_id in by_id:
            section_id = raw_id
        elif raw_id in {CROSSBEAM_SOLID_PRESET_KEY, CROSSBEAM_HOLLOW_PRESET_KEY}:
            section_id = by_preset.get(raw_id)
        elif preset_key in by_preset:
            section_id = by_preset[preset_key]
        elif preset_name == CROSSBEAM_HOLLOW_PRESET_NAME:
            section_id = by_role.get("Hollow")
        elif preset_name == CROSSBEAM_SOLID_PRESET_NAME:
            section_id = by_role.get("Solid")
        elif role in by_role:
            section_id = by_role[role]
        else:
            section_id = definition_rows[index % len(definition_rows)]["Section ID"] if definition_rows else ""
        definition = by_id.get(str(section_id), {})
        row.update(
            {
                "Section ID": str(section_id or ""),
                "Section name": str(definition.get("Section name") or ""),
                "Section preset key": str(definition.get("Preset key") or preset_key),
                "Section type / preset": str(definition.get("Preset family") or preset_name),
                "Section role": str(definition.get("Section role") or role or "Solid"),
            }
        )
        rows.append(row)
    return rows
