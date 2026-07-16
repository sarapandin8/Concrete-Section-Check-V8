"""Crossbeam-only rebar data foundation for segmental post-tensioned members.

CROSSBEAM.RB1 introduced workflow-scoped template/zone inputs and the accepted
construction rule that no ordinary rebar crosses a segment joint.  RB2 adds
template-level outer/inner-face auto-layout controls and graphical section
preview data while remaining intentionally disconnected from every ULS/SLS
solver. RB2A preserves the locked zero ordinary-rebar crossing rule while
explicitly treating post-tensioning continuity as required but not verified
until the Tendon System/Profile audit is connected. RB2B adds project-template
management and spacing-or-exact-count layout controls. RB2C moves all ordinary
template inputs into compact editable tables and allows every default/project row
to be edited with guarded deletion. RB2D adds engineer-editable Template IDs with
atomic Zone-reference updates, plus linked SD40/SD50 and 390/490 MPa dropdown
pairs. CROSSBEAM.TR1 extends the same segment/zone map with an independent
Transverse / Shear Template reference while retaining ``Rebar template`` as a
backward-compatible longitudinal alias. Solver ownership remains unchanged.
CROSSBEAM.RB2G1 derives active-Zone longitudinal preview centers from the
transverse cage offset plus the transverse and longitudinal bar radii.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from concrete_pmm_pro.crossbeam.transverse import (
    canonical_transverse_templates,
    default_crossbeam_transverse_templates,
    default_transverse_template_id,
    transverse_template_map,
)

RB_HOLLOW_MIN = "RB-HOLLOW-MIN"
RB_SOLID_COLUMN = "RB-SOLID-COLUMN"
RB_SOLID_ANCHORAGE = "RB-SOLID-ANCHORAGE"

TEMPLATE_ROLE_OPTIONS = ("Hollow", "Solid", "Any")
TEMPLATE_CONSTRUCTION_OPTIONS = ("Factory precast", "Cast in place", "Project-defined")
TEMPLATE_LONGITUDINAL_BASIS_OPTIONS = ("Segment-local", "Zone-local")
TEMPLATE_BAR_SIZE_OPTIONS = ("DB10", "DB12", "DB16", "DB20", "DB25", "DB28", "DB32")
TEMPLATE_LAYOUT_METHOD_OPTIONS = ("By target spacing", "By exact bar count")
TEMPLATE_MATERIAL_OPTIONS = ("SD40", "SD50")
TEMPLATE_FY_OPTIONS = (390.0, 490.0)
REBAR_FY_BY_MATERIAL = {"SD40": 390.0, "SD50": 490.0}
REBAR_MATERIAL_BY_FY = {390.0: "SD40", 490.0: "SD50"}
REBAR_DIAMETER_BY_SIZE = {
    "DB10": 10.0,
    "DB12": 12.0,
    "DB16": 16.0,
    "DB20": 20.0,
    "DB25": 25.0,
    "DB28": 28.0,
    "DB32": 32.0,
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


def rebar_diameter_mm(bar_size: Any, default: float = 16.0) -> float:
    """Return the nominal diameter for a supported deformed-bar label."""

    return float(REBAR_DIAMETER_BY_SIZE.get(str(bar_size or "").strip().upper(), default))


def cage_relative_longitudinal_center_offset_mm(
    transverse_center_offset_mm: float,
    transverse_diameter_mm: float,
    longitudinal_diameter_mm: float,
) -> float:
    """Return the longitudinal center offset required behind a transverse bar.

    In section view, a longitudinal bar tied directly inside a transverse cage
    has center-to-center distance ``Dt/2 + Dl/2`` from the cage centerline.
    The concrete-edge offset is therefore the transverse center offset plus the
    two radii.  This preview rule is zone-dependent because bar sizes may vary.
    """

    transverse_offset = float(transverse_center_offset_mm)
    transverse_diameter = float(transverse_diameter_mm)
    longitudinal_diameter = float(longitudinal_diameter_mm)
    if transverse_offset <= 0.0:
        raise ValueError("Transverse center offset must be positive.")
    if transverse_diameter <= 0.0 or longitudinal_diameter <= 0.0:
        raise ValueError("Transverse and longitudinal bar diameters must be positive.")
    return transverse_offset + 0.5 * transverse_diameter + 0.5 * longitudinal_diameter


def _layout_defaults(role: str, template_id: str) -> dict[str, Any]:
    role_text = str(role or "Any").title()
    solid_column = str(template_id) == RB_SOLID_COLUMN
    outer_size = "DB20" if solid_column else "DB16"
    return {
        "Rebar material": "SD40",
        "Outer face bars": True,
        "Outer bar size": outer_size,
        "Outer center offset mm": 50.0,
        "Outer layout method": "By target spacing",
        "Outer target spacing mm": 150.0,
        "Outer exact bar count": 24,
        "Inner face bars": role_text == "Hollow",
        "Inner bar size": "DB16",
        "Inner center offset mm": 50.0,
        "Inner layout method": "By target spacing",
        "Inner target spacing mm": 150.0,
        "Inner exact bar count": 16,
    }


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
            **_layout_defaults("Hollow", RB_HOLLOW_MIN),
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
            **_layout_defaults("Solid", RB_SOLID_COLUMN),
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
            **_layout_defaults("Solid", RB_SOLID_ANCHORAGE),
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
        layout_defaults = _layout_defaults(role, template_id)
        outer_size = str(row.get("Outer bar size") or layout_defaults["Outer bar size"]).strip().upper()
        if outer_size not in TEMPLATE_BAR_SIZE_OPTIONS:
            outer_size = str(layout_defaults["Outer bar size"])
        inner_size = str(row.get("Inner bar size") or layout_defaults["Inner bar size"]).strip().upper()
        if inner_size not in TEMPLATE_BAR_SIZE_OPTIONS:
            inner_size = str(layout_defaults["Inner bar size"])
        outer_method = str(row.get("Outer layout method") or layout_defaults["Outer layout method"]).strip()
        if outer_method not in TEMPLATE_LAYOUT_METHOD_OPTIONS:
            outer_method = "By target spacing"
        inner_method = str(row.get("Inner layout method") or layout_defaults["Inner layout method"]).strip()
        if inner_method not in TEMPLATE_LAYOUT_METHOD_OPTIONS:
            inner_method = "By target spacing"
        raw_material = str(row.get("Rebar material") or "").strip().upper()
        raw_fy = _float(row.get("fy MPa"), 390.0)
        if raw_material in TEMPLATE_MATERIAL_OPTIONS:
            material = raw_material
            fy_mpa = REBAR_FY_BY_MATERIAL[material]
        else:
            fy_mpa = 490.0 if abs(raw_fy - 490.0) < abs(raw_fy - 390.0) else 390.0
            material = REBAR_MATERIAL_BY_FY[fy_mpa]
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
                "fy MPa": fy_mpa,
                "Rebar material": material,
                "Outer face bars": _bool(row.get("Outer face bars"), bool(layout_defaults["Outer face bars"])),
                "Outer bar size": outer_size,
                "Outer layout method": outer_method,
                "Outer center offset mm": max(
                    _float(row.get("Outer center offset mm"), float(layout_defaults["Outer center offset mm"])), 1.0
                ),
                "Outer target spacing mm": max(
                    _float(row.get("Outer target spacing mm"), float(layout_defaults["Outer target spacing mm"])), 1.0
                ),
                "Outer exact bar count": max(int(_float(row.get("Outer exact bar count"), float(layout_defaults["Outer exact bar count"]))), 4),
                "Inner face bars": _bool(row.get("Inner face bars"), bool(layout_defaults["Inner face bars"])),
                "Inner bar size": inner_size,
                "Inner layout method": inner_method,
                "Inner center offset mm": max(
                    _float(row.get("Inner center offset mm"), float(layout_defaults["Inner center offset mm"])), 1.0
                ),
                "Inner target spacing mm": max(
                    _float(row.get("Inner target spacing mm"), float(layout_defaults["Inner target spacing mm"])), 1.0
                ),
                "Inner exact bar count": max(int(_float(row.get("Inner exact bar count"), float(layout_defaults["Inner exact bar count"]))), 4),
                "Notes": str(row.get("Notes") or "").strip(),
            }
        )
    return canonical


def next_rebar_template_id(role: str, existing_ids: list[str] | tuple[str, ...] | set[str]) -> str:
    """Return a stable project template ID without changing existing references."""

    prefix = "RB-H" if str(role).strip().title() == "Hollow" else "RB-S"
    used = {str(value or "").strip().upper() for value in existing_ids}
    index = 1
    while f"{prefix}{index:02d}" in used:
        index += 1
    return f"{prefix}{index:02d}"


def new_rebar_template(role: str, existing_ids: list[str] | tuple[str, ...] | set[str]) -> dict[str, Any]:
    """Create one canonical user template for the selected section family."""

    role_text = "Hollow" if str(role).strip().title() == "Hollow" else "Solid"
    template_id = next_rebar_template_id(role_text, existing_ids)
    construction = "Factory precast" if role_text == "Hollow" else "Cast in place"
    basis = "Segment-local" if role_text == "Hollow" else "Zone-local"
    row = {
        "Active": True,
        "Template ID": template_id,
        "Template name": f"New {role_text.lower()} reinforcement template",
        "Applicable role": role_text,
        "Construction": construction,
        "Longitudinal basis": basis,
        "Credit inside segment": True,
        "Top As mm²": 0.0,
        "Bottom As mm²": 0.0,
        "Side As mm²": 0.0,
        "Av/s mm²/mm": 0.0,
        "fy MPa": 390.0,
        **_layout_defaults(role_text, template_id),
        "Notes": "Project-defined segment/zone reinforcement; ordinary rebar never crosses a segment joint.",
    }
    return canonical_rebar_templates([row])[0]


def duplicate_rebar_template(source: Mapping[str, Any], existing_ids: list[str] | tuple[str, ...] | set[str]) -> dict[str, Any]:
    """Duplicate a template with a new stable ID and user-facing copy name."""

    role = str(source.get("Applicable role") or "Solid")
    row = dict(source)
    row["Template ID"] = next_rebar_template_id(role, existing_ids)
    row["Template name"] = f"{str(source.get('Template name') or source.get('Template ID') or 'Template')} — Copy"
    return canonical_rebar_templates([row])[0]


def template_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["Template ID"]): row
        for row in canonical_rebar_templates(rows)
        if row.get("Active") and str(row.get("Template ID") or "").strip()
    }


def _segment_role(row: Mapping[str, Any]) -> str:
    role = str(row.get("Section role") or "").strip().title()
    return role if role in {"Solid", "Hollow"} else "Solid"


def default_crossbeam_rebar_zones(
    segment_rows: list[dict[str, Any]],
    template_rows: list[dict[str, Any]] | None = None,
    transverse_template_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return one default zone per segment with independent L/T templates.

    ``Rebar template`` is retained as a backward-compatible alias for the
    longitudinal template used by RB1/RB2 tests and older project sessions.
    """

    templates = canonical_rebar_templates(template_rows or default_crossbeam_rebar_templates())
    active = [row for row in templates if bool(row.get("Active"))]
    transverse_rows = canonical_transverse_templates(
        transverse_template_rows or default_crossbeam_transverse_templates()
    )

    def _template_for(role: str) -> str:
        preferred = RB_HOLLOW_MIN if role == "Hollow" else RB_SOLID_COLUMN
        if any(str(row.get("Template ID") or "") == preferred for row in active):
            return preferred
        compatible = [
            row for row in active
            if str(row.get("Applicable role") or "") in {role, "Any"}
        ]
        candidates = compatible or active
        return str(candidates[0].get("Template ID") or "") if candidates else ""

    zones: list[dict[str, Any]] = []
    for index, segment in enumerate(sorted(segment_rows, key=lambda item: _float(item.get("x_start_m"), 0.0))):
        role = _segment_role(segment)
        segment_id = str(segment.get("Segment") or f"S{index + 1}").strip()
        longitudinal_id = _template_for(role)
        zones.append(
            {
                "Zone ID": f"Z-{segment_id}",
                "Segment": segment_id,
                "s_start_m": _float(segment.get("x_start_m"), 0.0),
                "s_end_m": _float(segment.get("x_end_m"), 0.0),
                "Rebar template": longitudinal_id,
                "Longitudinal template": longitudinal_id,
                "Transverse template": default_transverse_template_id(role, transverse_rows),
                "Purpose": "Minimum/detailing reinforcement" if role == "Hollow" else "Solid CIP column-region reinforcement",
            }
        )
    return zones


def canonical_rebar_zones(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical: list[dict[str, Any]] = []
    for index, source in enumerate(rows):
        row = dict(source or {})
        longitudinal = str(
            row.get("Longitudinal template")
            or row.get("Rebar template")
            or ""
        ).strip()
        canonical.append(
            {
                "Zone ID": str(row.get("Zone ID") or f"Z{index + 1}").strip(),
                "Segment": str(row.get("Segment") or "").strip(),
                "s_start_m": _float(row.get("s_start_m", row.get("s_start (m)")), 0.0),
                "s_end_m": _float(row.get("s_end_m", row.get("s_end (m)")), 0.0),
                "Rebar template": longitudinal,
                "Longitudinal template": longitudinal,
                "Transverse template": str(row.get("Transverse template") or "").strip(),
                "Purpose": str(row.get("Purpose") or "").strip(),
            }
        )
    return canonical


def validate_rebar_zones(
    zones: list[dict[str, Any]],
    segment_rows: list[dict[str, Any]],
    template_rows: list[dict[str, Any]],
    transverse_template_rows: list[dict[str, Any]] | None = None,
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
    transverse_templates = transverse_template_map(
        canonical_transverse_templates(transverse_template_rows or [])
    ) if transverse_template_rows is not None else {}
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
        if transverse_template_rows is not None:
            transverse_id = str(zone.get("Transverse template") or "")
            transverse = transverse_templates.get(transverse_id)
            if transverse is None:
                errors.append(f"{zone_id}: select an active Transverse / Shear Template.")
            else:
                transverse_role = str(transverse.get("Applicable role") or "Any")
                if transverse_role not in {"Any", segment["role"]}:
                    errors.append(
                        f"{zone_id}: transverse template {transverse_id} is for {transverse_role}, "
                        f"but {zone['Segment']} is {segment['role']}."
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
    """Return locked ordinary-rebar and guarded tendon-continuity rows.

    Ordinary reinforcement crossing every segment joint is fixed at zero.
    Post-tensioning continuity is an engineering requirement, but RB2D does not
    claim that tendon geometry or active tendon area has already been verified
    across each joint.
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
                "Transverse joint shear credit": "None — local to segments",
                "Global continuity system": "PT continuity required — not verified",
                "Tendon continuity": "REQUIRED — NOT VERIFIED",
                "Status": "REVIEW REQUIRED",
            }
        )
    return joints


def station_rebar_audit_rows(
    segment_rows: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    templates: list[dict[str, Any]],
    transverse_templates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    template_by_id = template_map(templates)
    transverse_by_id = transverse_template_map(
        canonical_transverse_templates(transverse_templates or [])
    )
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
                "Active longitudinal template": zone.get("Longitudinal template", zone["Rebar template"]),
                "Active transverse template": zone.get("Transverse template", ""),
                "Transverse reinforcement credited locally": (
                    "Yes — future shear input"
                    if transverse_by_id.get(str(zone.get("Transverse template") or ""), {}).get("Credit inside segment")
                    else "No — local/detailing only"
                ),
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
            "Tendon continuity": "REQUIRED — NOT VERIFIED",
            "Status": "REVIEW REQUIRED",
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
