"""Crossbeam-only transverse/shear reinforcement input foundation.

CROSSBEAM.TR1 adds segment/zone-local transverse reinforcement templates for
Portal Frame Crossbeams.  The model is deliberately separate from the generic
Beam/Girder stirrup workflow because Crossbeam hollow sections may require
independent left/right web legs, while solid CIP regions may use multi-leg
closed ties.  This module does not calculate shear capacity and does not give
segment-joint shear-transfer credit.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite, pi
from typing import Any

TR_HOLLOW_MIN = "TR-HOLLOW-MIN"
TR_HOLLOW_END = "TR-HOLLOW-END"
TR_SOLID_COLUMN = "TR-SOLID-COLUMN"
TR_SOLID_ANCHORAGE = "TR-SOLID-ANCHORAGE"

TRANSVERSE_ROLE_OPTIONS = ("Hollow", "Solid", "Any")
TRANSVERSE_CONSTRUCTION_OPTIONS = ("Factory precast", "Cast in place", "Project-defined")
TRANSVERSE_BAR_SIZE_OPTIONS = ("DB10", "DB12", "DB16", "DB20", "DB25")
TRANSVERSE_MATERIAL_OPTIONS = ("SD40", "SD50")
TRANSVERSE_FY_OPTIONS = (390.0, 490.0)
TRANSVERSE_FY_BY_MATERIAL = {"SD40": 390.0, "SD50": 490.0}
TRANSVERSE_MATERIAL_BY_FY = {390.0: "SD40", 490.0: "SD50"}
TRANSVERSE_DIAMETER_BY_SIZE = {
    "DB10": 10.0,
    "DB12": 12.0,
    "DB16": 16.0,
    "DB20": 20.0,
    "DB25": 25.0,
}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if isfinite(result) else float(default)


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    return bool(value)


def transverse_bar_diameter_mm(bar_size: Any, default: float = 12.0) -> float:
    return float(TRANSVERSE_DIAMETER_BY_SIZE.get(str(bar_size or "").strip().upper(), default))


def transverse_bar_area_mm2(bar_size: Any) -> float:
    diameter = transverse_bar_diameter_mm(bar_size)
    return pi * diameter * diameter / 4.0


def _template_defaults(role: str, template_id: str) -> dict[str, Any]:
    role_text = str(role or "Any").strip().title()
    end_zone = str(template_id) in {TR_HOLLOW_END, TR_SOLID_ANCHORAGE}
    solid_column = str(template_id) == TR_SOLID_COLUMN
    return {
        "Rebar material": "SD40",
        "fy MPa": 390.0,
        "Bar size": "DB16" if role_text == "Solid" else "DB12",
        "Spacing mm": 100.0 if end_zone or solid_column else 200.0,
        "Left web legs": 2,
        "Right web legs": 2,
        "Effective legs": 6 if solid_column else (8 if end_zone and role_text == "Solid" else 4),
        "Closed cage": True,
        "Center offset mm": 50.0,
        "First bar offset mm": 75.0,
        "Last bar offset mm": 75.0,
    }


def default_crossbeam_transverse_templates() -> list[dict[str, Any]]:
    rows = [
        {
            "Active": True,
            "Template ID": TR_HOLLOW_MIN,
            "Template name": "Factory-cast hollow segment minimum shear reinforcement",
            "Applicable role": "Hollow",
            "Construction": "Factory precast",
            "Credit inside segment": True,
            **_template_defaults("Hollow", TR_HOLLOW_MIN),
            "Notes": "Local web reinforcement only; no automatic segment-joint shear-transfer credit.",
        },
        {
            "Active": True,
            "Template ID": TR_HOLLOW_END,
            "Template name": "Hollow segment end-zone shear reinforcement",
            "Applicable role": "Hollow",
            "Construction": "Factory precast",
            "Credit inside segment": True,
            **_template_defaults("Hollow", TR_HOLLOW_END),
            "Notes": "Dense local reinforcement near segment ends; joint shear remains a separate check.",
        },
        {
            "Active": True,
            "Template ID": TR_SOLID_COLUMN,
            "Template name": "Solid CIP column-region multi-leg ties",
            "Applicable role": "Solid",
            "Construction": "Cast in place",
            "Credit inside segment": True,
            **_template_defaults("Solid", TR_SOLID_COLUMN),
            "Notes": "Local solid-region shear reinforcement; column D-region review remains separate.",
        },
        {
            "Active": True,
            "Template ID": TR_SOLID_ANCHORAGE,
            "Template name": "Solid anchorage/end-block transverse reinforcement",
            "Applicable role": "Solid",
            "Construction": "Cast in place",
            "Credit inside segment": False,
            **_template_defaults("Solid", TR_SOLID_ANCHORAGE),
            "Notes": "Local anchorage/bursting reinforcement only; not a joint-shear certification.",
        },
    ]
    return canonical_transverse_templates(rows)


def canonical_transverse_templates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical: list[dict[str, Any]] = []
    for index, source in enumerate(rows):
        row = dict(source or {})
        template_id = str(row.get("Template ID") or f"TR-{index + 1}").strip()
        role = str(row.get("Applicable role") or "Any").strip().title()
        if role not in TRANSVERSE_ROLE_OPTIONS:
            role = "Any"
        construction = str(row.get("Construction") or "Project-defined").strip()
        if construction not in TRANSVERSE_CONSTRUCTION_OPTIONS:
            construction = "Project-defined"
        defaults = _template_defaults(role, template_id)
        bar_size = str(row.get("Bar size") or defaults["Bar size"]).strip().upper()
        if bar_size not in TRANSVERSE_BAR_SIZE_OPTIONS:
            bar_size = str(defaults["Bar size"])
        raw_material = str(row.get("Rebar material") or "").strip().upper()
        raw_fy = _float(row.get("fy MPa"), 390.0)
        if raw_material in TRANSVERSE_MATERIAL_OPTIONS:
            material = raw_material
            fy_mpa = TRANSVERSE_FY_BY_MATERIAL[material]
        else:
            fy_mpa = 490.0 if abs(raw_fy - 490.0) < abs(raw_fy - 390.0) else 390.0
            material = TRANSVERSE_MATERIAL_BY_FY[fy_mpa]
        canonical.append(
            {
                "Active": _bool(row.get("Active"), True),
                "Template ID": template_id,
                "Template name": str(row.get("Template name") or template_id).strip(),
                "Applicable role": role,
                "Construction": construction,
                "Credit inside segment": _bool(row.get("Credit inside segment"), True),
                "Rebar material": material,
                "fy MPa": fy_mpa,
                "Bar size": bar_size,
                "Spacing mm": max(_float(row.get("Spacing mm"), float(defaults["Spacing mm"])), 1.0),
                "Left web legs": max(int(round(_float(row.get("Left web legs"), float(defaults["Left web legs"])))), 1),
                "Right web legs": max(int(round(_float(row.get("Right web legs"), float(defaults["Right web legs"])))), 1),
                "Effective legs": max(int(round(_float(row.get("Effective legs"), float(defaults["Effective legs"])))), 2),
                "Closed cage": _bool(row.get("Closed cage"), True),
                "Center offset mm": max(_float(row.get("Center offset mm"), float(defaults["Center offset mm"])), 1.0),
                "First bar offset mm": max(_float(row.get("First bar offset mm"), float(defaults["First bar offset mm"])), 0.0),
                "Last bar offset mm": max(_float(row.get("Last bar offset mm"), float(defaults["Last bar offset mm"])), 0.0),
                "Notes": str(row.get("Notes") or "").strip(),
            }
        )
    return canonical


def transverse_template_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["Template ID"]): row
        for row in canonical_transverse_templates(rows)
        if row.get("Active") and str(row.get("Template ID") or "").strip()
    }


def next_transverse_template_id(role: str, existing_ids: list[str] | tuple[str, ...] | set[str]) -> str:
    prefix = "TR-H" if str(role).strip().title() == "Hollow" else "TR-S"
    used = {str(value or "").strip().upper() for value in existing_ids}
    index = 1
    while f"{prefix}{index:02d}" in used:
        index += 1
    return f"{prefix}{index:02d}"


def new_transverse_template(role: str, existing_ids: list[str] | tuple[str, ...] | set[str]) -> dict[str, Any]:
    role_text = "Hollow" if str(role).strip().title() == "Hollow" else "Solid"
    template_id = next_transverse_template_id(role_text, existing_ids)
    row = {
        "Active": True,
        "Template ID": template_id,
        "Template name": f"New {role_text.lower()} transverse template",
        "Applicable role": role_text,
        "Construction": "Factory precast" if role_text == "Hollow" else "Cast in place",
        "Credit inside segment": True,
        **_template_defaults(role_text, template_id),
        "Notes": "Project-defined local transverse reinforcement; no automatic segment-joint shear-transfer credit.",
    }
    return canonical_transverse_templates([row])[0]


def duplicate_transverse_template(
    source: Mapping[str, Any],
    existing_ids: list[str] | tuple[str, ...] | set[str],
) -> dict[str, Any]:
    role = str(source.get("Applicable role") or "Solid")
    row = dict(source)
    row["Template ID"] = next_transverse_template_id(role, existing_ids)
    row["Template name"] = f"{str(source.get('Template name') or source.get('Template ID') or 'Template')} — Copy"
    return canonical_transverse_templates([row])[0]


def default_transverse_template_id(role: str, rows: list[dict[str, Any]]) -> str:
    role_text = str(role or "Solid").strip().title()
    preferred = TR_HOLLOW_MIN if role_text == "Hollow" else TR_SOLID_COLUMN
    active = list(transverse_template_map(rows).values())
    if any(str(row.get("Template ID") or "") == preferred for row in active):
        return preferred
    compatible = [row for row in active if str(row.get("Applicable role") or "") in {role_text, "Any"}]
    candidates = compatible or active
    return str(candidates[0].get("Template ID") or "") if candidates else ""


def transverse_avs_record(template: Mapping[str, Any]) -> dict[str, Any]:
    row = canonical_transverse_templates([dict(template)])[0]
    area = transverse_bar_area_mm2(row["Bar size"])
    spacing = max(float(row["Spacing mm"]), 1.0)
    role = str(row["Applicable role"])
    if role == "Hollow":
        left = float(row["Left web legs"]) * area / spacing
        right = float(row["Right web legs"]) * area / spacing
        total = left + right
    else:
        left = 0.0
        right = 0.0
        total = float(row["Effective legs"]) * area / spacing
    return {
        "Template ID": row["Template ID"],
        "Role": role,
        "Bar": row["Bar size"],
        "Spacing mm": spacing,
        "Av,left/s mm²/mm": left,
        "Av,right/s mm²/mm": right,
        "Av,total/s mm²/mm": total,
        "Status": "INPUT READY" if row["Active"] else "INACTIVE",
    }


def transverse_set_stations(
    template: Mapping[str, Any],
    start_m: float,
    end_m: float,
    *,
    maximum_sets: int = 500,
) -> list[float]:
    row = canonical_transverse_templates([dict(template)])[0]
    start_mm = float(start_m) * 1000.0 + float(row["First bar offset mm"])
    end_mm = float(end_m) * 1000.0 - float(row["Last bar offset mm"])
    spacing = max(float(row["Spacing mm"]), 1.0)
    if end_mm < start_mm:
        return []
    count = min(int((end_mm - start_mm) // spacing) + 1, int(maximum_sets))
    return [(start_mm + index * spacing) / 1000.0 for index in range(max(count, 0))]


def validate_transverse_templates(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    canonical = canonical_transverse_templates(rows)
    errors: list[str] = []
    warnings: list[str] = []
    ids = [str(row.get("Template ID") or "").strip() for row in canonical if row.get("Active")]
    duplicates = sorted({value for value in ids if value and ids.count(value) > 1})
    if duplicates:
        errors.append("Duplicate active Transverse Template IDs: " + ", ".join(duplicates) + ".")
    if not canonical:
        errors.append("At least one Transverse / Shear Template is required.")
    for row in canonical:
        template_id = str(row.get("Template ID") or "")
        if not template_id:
            errors.append("Every Transverse Template requires a Template ID.")
            continue
        if float(row["Spacing mm"]) <= 0.0:
            errors.append(f"{template_id}: spacing must be positive.")
        if str(row["Applicable role"]) == "Hollow" and not bool(row["Closed cage"]):
            warnings.append(f"{template_id}: open web reinforcement is a detailing preview only; closed-cage/tie review remains required.")
        if float(row["First bar offset mm"]) + float(row["Last bar offset mm"]) > 2000.0:
            warnings.append(f"{template_id}: large end offsets may leave short zones without transverse sets.")
    return canonical, errors, warnings
