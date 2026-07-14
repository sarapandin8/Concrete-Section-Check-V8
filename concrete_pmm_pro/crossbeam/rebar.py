"""Crossbeam-only rebar data foundation for segmental post-tensioned members.

CROSSBEAM.RB1 intentionally does not connect ordinary reinforcement to any
ULS/SLS solver.  It defines workflow-scoped template/zone inputs and enforces
the accepted construction rule that no ordinary rebar crosses a segment joint;
global continuity at every joint is provided by post-tensioning tendons only.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

RB_HOLLOW_MIN = "RB-HOLLOW-MIN"
RB_SOLID_COLUMN = "RB-SOLID-COLUMN"
RB_SOLID_ANCHORAGE = "RB-SOLID-ANCHORAGE"

TEMPLATE_ROLE_OPTIONS = ("Hollow", "Solid", "Any")
TEMPLATE_CONSTRUCTION_OPTIONS = ("Factory precast", "Cast in place", "Project-defined")
TEMPLATE_LONGITUDINAL_BASIS_OPTIONS = ("Segment-local", "Zone-local")


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


def default_crossbeam_rebar_templates() -> list[dict[str, Any]]:
    """Return first-release Crossbeam rebar templates.

    Quantities start at zero by design: RB1 is a traceable input foundation and
    must not imply that code-minimum or project reinforcement has already been
    designed.  The engineer enters actual provided reinforcement later.
    """

    return [
        {
            "Active": True,
            "Template ID": RB_HOLLOW_MIN,
            "Template name": "Factory-cast hollow segment minimum reinforcement",
            "Applicable role": "Hollow",
            "Construction": "Factory precast",
            "Longitudinal basis": "Segment-local",
            "Credit inside segment": True,
            "Top As mm²": 0.0,
            "Bottom As mm²": 0.0,
            "Side As mm²": 0.0,
            "Av/s mm²/mm": 0.0,
            "fy MPa": 390.0,
            "Notes": "Enter actual minimum/detailing reinforcement; no ordinary bar crosses either segment joint.",
        },
        {
            "Active": True,
            "Template ID": RB_SOLID_COLUMN,
            "Template name": "Cast-in-place solid column-region reinforcement",
            "Applicable role": "Solid",
            "Construction": "Cast in place",
            "Longitudinal basis": "Zone-local",
            "Credit inside segment": True,
            "Top As mm²": 0.0,
            "Bottom As mm²": 0.0,
            "Side As mm²": 0.0,
            "Av/s mm²/mm": 0.0,
            "fy MPa": 390.0,
            "Notes": "Define actual CIP reinforcement within the solid zone; column-joint and D-region review remain separate.",
        },
        {
            "Active": True,
            "Template ID": RB_SOLID_ANCHORAGE,
            "Template name": "Anchorage/end-block local reinforcement",
            "Applicable role": "Solid",
            "Construction": "Cast in place",
            "Longitudinal basis": "Zone-local",
            "Credit inside segment": False,
            "Top As mm²": 0.0,
            "Bottom As mm²": 0.0,
            "Side As mm²": 0.0,
            "Av/s mm²/mm": 0.0,
            "fy MPa": 390.0,
            "Notes": "Local anchorage/bursting reinforcement only; not credited by RB1 for global section strength.",
        },
    ]


def canonical_rebar_templates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical: list[dict[str, Any]] = []
    for index, source in enumerate(rows):
        row = dict(source or {})
        template_id = str(row.get("Template ID") or f"RB-{index + 1}").strip()
        role = str(row.get("Applicable role") or "Any").strip().title()
        if role not in TEMPLATE_ROLE_OPTIONS:
            role = "Any"
        construction = str(row.get("Construction") or "Project-defined").strip()
        if construction not in TEMPLATE_CONSTRUCTION_OPTIONS:
            construction = "Project-defined"
        basis = str(row.get("Longitudinal basis") or "Segment-local").strip()
        if basis not in TEMPLATE_LONGITUDINAL_BASIS_OPTIONS:
            basis = "Segment-local"
        canonical.append(
            {
                "Active": _bool(row.get("Active"), True),
                "Template ID": template_id,
                "Template name": str(row.get("Template name") or template_id).strip(),
                "Applicable role": role,
                "Construction": construction,
                "Longitudinal basis": basis,
                "Credit inside segment": _bool(row.get("Credit inside segment"), True),
                "Top As mm²": max(_float(row.get("Top As mm²"), 0.0), 0.0),
                "Bottom As mm²": max(_float(row.get("Bottom As mm²"), 0.0), 0.0),
                "Side As mm²": max(_float(row.get("Side As mm²"), 0.0), 0.0),
                "Av/s mm²/mm": max(_float(row.get("Av/s mm²/mm"), 0.0), 0.0),
                "fy MPa": max(_float(row.get("fy MPa"), 390.0), 0.0),
                "Notes": str(row.get("Notes") or "").strip(),
            }
        )
    return canonical


def template_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["Template ID"]): row
        for row in canonical_rebar_templates(rows)
        if row.get("Active") and str(row.get("Template ID") or "").strip()
    }


def _segment_role(row: Mapping[str, Any]) -> str:
    role = str(row.get("Section role") or "").strip().title()
    return role if role in {"Solid", "Hollow"} else "Solid"


def default_crossbeam_rebar_zones(segment_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for index, segment in enumerate(sorted(segment_rows, key=lambda item: _float(item.get("x_start_m"), 0.0))):
        role = _segment_role(segment)
        segment_id = str(segment.get("Segment") or f"S{index + 1}").strip()
        zones.append(
            {
                "Zone ID": f"Z-{segment_id}",
                "Segment": segment_id,
                "s_start_m": _float(segment.get("x_start_m"), 0.0),
                "s_end_m": _float(segment.get("x_end_m"), 0.0),
                "Rebar template": RB_HOLLOW_MIN if role == "Hollow" else RB_SOLID_COLUMN,
                "Purpose": "Minimum/detailing reinforcement" if role == "Hollow" else "Solid CIP column-region reinforcement",
            }
        )
    return zones


def canonical_rebar_zones(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical: list[dict[str, Any]] = []
    for index, source in enumerate(rows):
        row = dict(source or {})
        canonical.append(
            {
                "Zone ID": str(row.get("Zone ID") or f"Z{index + 1}").strip(),
                "Segment": str(row.get("Segment") or "").strip(),
                "s_start_m": _float(row.get("s_start_m", row.get("s_start (m)")), 0.0),
                "s_end_m": _float(row.get("s_end_m", row.get("s_end (m)")), 0.0),
                "Rebar template": str(row.get("Rebar template") or "").strip(),
                "Purpose": str(row.get("Purpose") or "").strip(),
            }
        )
    return canonical


def validate_rebar_zones(
    zones: list[dict[str, Any]],
    segment_rows: list[dict[str, Any]],
    template_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Validate full segment coverage without changing the locked joint rule."""

    normalized = canonical_rebar_zones(zones)
    segments = {
        str(row.get("Segment") or "").strip(): {
            "start": _float(row.get("x_start_m"), 0.0),
            "end": _float(row.get("x_end_m"), 0.0),
            "role": _segment_role(row),
        }
        for row in segment_rows
        if str(row.get("Segment") or "").strip()
    }
    canonical_templates = canonical_rebar_templates(template_rows)
    templates = template_map(canonical_templates)
    errors: list[str] = []
    warnings: list[str] = []
    active_template_ids = [str(row.get("Template ID") or "").strip() for row in canonical_templates if row.get("Active")]
    duplicate_template_ids = sorted({item for item in active_template_ids if item and active_template_ids.count(item) > 1})
    for template_id in duplicate_template_ids:
        errors.append(f"Duplicate active Rebar Template ID: {template_id}.")
    if any(not item for item in active_template_ids):
        errors.append("Every active Rebar Template requires a Template ID.")
    seen_zone_ids: set[str] = set()

    for zone in normalized:
        zone_id = zone["Zone ID"]
        if not zone_id:
            errors.append("Every rebar zone requires a Zone ID.")
        elif zone_id in seen_zone_ids:
            errors.append(f"Duplicate rebar Zone ID: {zone_id}.")
        seen_zone_ids.add(zone_id)

        segment = segments.get(zone["Segment"])
        if segment is None:
            errors.append(f"{zone_id}: select a valid Segment from Segment Layout.")
            continue
        if zone["s_end_m"] <= zone["s_start_m"]:
            errors.append(f"{zone_id}: s_end must be greater than s_start.")
        tolerance = max(1e-6, abs(segment["end"] - segment["start"]) * 1e-6)
        if zone["s_start_m"] < segment["start"] - tolerance or zone["s_end_m"] > segment["end"] + tolerance:
            errors.append(
                f"{zone_id}: zone must remain inside {zone['Segment']} ({segment['start']:.3f}–{segment['end']:.3f} m)."
            )
        template = templates.get(zone["Rebar template"])
        if template is None:
            errors.append(f"{zone_id}: select an active Rebar Template.")
            continue
        applicable_role = str(template.get("Applicable role") or "Any")
        if applicable_role not in {"Any", segment["role"]}:
            errors.append(
                f"{zone_id}: template {zone['Rebar template']} is for {applicable_role}, but {zone['Segment']} is {segment['role']}."
            )

    for segment_id, segment in segments.items():
        rows = sorted(
            [row for row in normalized if row["Segment"] == segment_id],
            key=lambda item: (item["s_start_m"], item["s_end_m"]),
        )
        tolerance = max(1e-6, abs(segment["end"] - segment["start"]) * 1e-6)
        if not rows:
            errors.append(f"{segment_id}: no Rebar Template zone is assigned.")
            continue
        if abs(rows[0]["s_start_m"] - segment["start"]) > tolerance:
            errors.append(f"{segment_id}: first rebar zone must start at the segment start.")
        if abs(rows[-1]["s_end_m"] - segment["end"]) > tolerance:
            errors.append(f"{segment_id}: final rebar zone must end at the segment end.")
        for previous, current in zip(rows, rows[1:]):
            delta = current["s_start_m"] - previous["s_end_m"]
            if abs(delta) > tolerance:
                errors.append(f"{segment_id}: rebar-zone {'gap' if delta > 0 else 'overlap'} detected.")

    for template_id, template in templates.items():
        quantities = (
            _float(template.get("Top As mm²")),
            _float(template.get("Bottom As mm²")),
            _float(template.get("Side As mm²")),
            _float(template.get("Av/s mm²/mm")),
        )
        if not any(value > 0.0 for value in quantities):
            warnings.append(f"{template_id}: actual provided reinforcement quantities are not defined yet.")

    return normalized, errors, warnings


def segment_joint_audit_rows(segment_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return locked joint-participation rows.

    Ordinary reinforcement crossing every segment joint is fixed at zero.  This
    is not a user-selectable assumption for the accepted Crossbeam workflow.
    """

    ordered = sorted(segment_rows, key=lambda item: _float(item.get("x_start_m"), 0.0))
    joints: list[dict[str, Any]] = []
    for left, right in zip(ordered, ordered[1:]):
        station = _float(left.get("x_end_m"), 0.0)
        joints.append(
            {
                "Joint": f"{left.get('Segment', '')} / {right.get('Segment', '')}",
                "s (m)": station,
                "Ordinary rebar crossing joint": "0 mm² (LOCKED)",
                "Ordinary rebar strength credit": "None",
                "Global continuity system": "Post-tensioning tendons only",
                "Status": "LOCKED",
            }
        )
    return joints


def station_rebar_audit_rows(
    segment_rows: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    templates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    template_by_id = template_map(templates)
    segment_by_id = {str(row.get("Segment") or ""): row for row in segment_rows}
    audit: list[dict[str, Any]] = []
    for zone in sorted(canonical_rebar_zones(zones), key=lambda item: (item["s_start_m"], item["s_end_m"])):
        template = template_by_id.get(zone["Rebar template"], {})
        segment = segment_by_id.get(zone["Segment"], {})
        role = _segment_role(segment)
        credit = bool(template.get("Credit inside segment"))
        audit.append(
            {
                "Location": zone["Zone ID"],
                "Location type": "Solid CIP region" if role == "Solid" else "Precast segment interior",
                "s (m)": 0.5 * (zone["s_start_m"] + zone["s_end_m"]),
                "Segment": zone["Segment"],
                "Section role": role,
                "Active template": zone["Rebar template"],
                "Ordinary rebar credited locally": "Yes — future solver input" if credit else "No — local/detailing only",
                "Ordinary rebar across joints": "0 mm²",
                "Status": "INPUT FOUNDATION",
            }
        )
    audit.extend(
        {
            "Location": row["Joint"],
            "Location type": "Segment joint",
            "s (m)": row["s (m)"],
            "Segment": row["Joint"],
            "Section role": "Joint plane",
            "Active template": "None across joint",
            "Ordinary rebar credited locally": "No",
            "Ordinary rebar across joints": "0 mm² (LOCKED)",
            "Status": "TENDONS ONLY",
        }
        for row in segment_joint_audit_rows(segment_rows)
    )
    return sorted(audit, key=lambda item: (float(item["s (m)"]), item["Location type"] != "Segment joint"))


def segment_signature(segment_rows: list[dict[str, Any]]) -> tuple[tuple[str, float, float, str], ...]:
    return tuple(
        (
            str(row.get("Segment") or ""),
            round(_float(row.get("x_start_m"), 0.0), 6),
            round(_float(row.get("x_end_m"), 0.0), 6),
            _segment_role(row),
        )
        for row in sorted(segment_rows, key=lambda item: _float(item.get("x_start_m"), 0.0))
    )
