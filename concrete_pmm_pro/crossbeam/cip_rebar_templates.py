"""Cast-in-Place Crossbeam reinforcement template/zone model.

CROSSBEAM.RB-CIP2A aligns the Cast-in-Place Rebar workspace with the accepted
Precast Segmental interaction pattern while keeping a separate canonical state.
CIP uses Solid-only longitudinal/transverse templates assigned to Section/Zones.
Zone boundaries are property boundaries, not physical joints, so longitudinal
continuity is reviewed across adjacent Zones rather than forced to zero.

This module is solver-neutral.  It does not grant ULS/SLS/PMM/shear/torsion
credit and does not certify development length, splice, curtailment, anchorage,
or exact bar-to-bar continuity.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from concrete_pmm_pro.crossbeam.rebar import (
    RB_SOLID_COLUMN,
    canonical_rebar_templates,
    canonical_rebar_zones,
    default_crossbeam_rebar_templates,
    template_map,
)
from concrete_pmm_pro.crossbeam.transverse import (
    TR_SOLID_COLUMN,
    canonical_transverse_templates,
    default_crossbeam_transverse_templates,
    transverse_template_map,
)

CIP_RB_TEMPLATE_ROWS_KEY = "crossbeam_rb_cip2a_longitudinal_template_rows"
CIP_TR_TEMPLATE_ROWS_KEY = "crossbeam_rb_cip2a_transverse_template_rows"
CIP_RB_ZONE_ROWS_KEY = "crossbeam_rb_cip2a_zone_assignment_rows"
CIP_RB_TEMPLATE_REV_KEY = "crossbeam_rb_cip2a_longitudinal_template_revision"
CIP_TR_TEMPLATE_REV_KEY = "crossbeam_rb_cip2a_transverse_template_revision"
CIP_RB_ZONE_REV_KEY = "crossbeam_rb_cip2a_zone_assignment_revision"
CIP_RB_SUBVIEW_KEY = "crossbeam_rb_cip2a_subview"
CIP_RB_PREVIEW_ZONE_KEY = "crossbeam_rb_cip2a_preview_zone"
CIP_RB_REVIEW_STATION_KEY = "crossbeam_rb_cip2a_review_station_m"

CIP_RB_SUBVIEWS = (
    "Longitudinal",
    "Transverse / Shear",
    "Section / Zone",
    "Preview",
    "Continuity & Station Audit",
)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _text(value: Any) -> str:
    return str(value or "").strip()


def default_cip_longitudinal_templates() -> list[dict[str, Any]]:
    """Return Solid-only copies of the accepted Crossbeam template family."""

    rows = [
        dict(row)
        for row in default_crossbeam_rebar_templates()
        if str(row.get("Applicable role") or "") == "Solid"
    ]
    for row in rows:
        row["Construction"] = "Cast in place"
        row["Longitudinal basis"] = "Zone-local"
        if str(row.get("Template ID") or "") == RB_SOLID_COLUMN:
            row["Template name"] = "Cast-in-place solid zone reinforcement"
        note = _text(row.get("Notes"))
        row["Notes"] = (
            note.replace("segment joint", "Section/Zone boundary")
            + " Zone assignment defines the local arrangement; Zone boundaries do not automatically terminate longitudinal bars."
        ).strip()
    return canonical_rebar_templates(rows)


def default_cip_transverse_templates() -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in default_crossbeam_transverse_templates()
        if str(row.get("Applicable role") or "") == "Solid"
    ]
    for row in rows:
        row["Construction"] = "Cast in place"
        note = _text(row.get("Notes"))
        row["Notes"] = (
            note + " Section/Zone boundaries are not physical construction joints."
        ).strip()
    return canonical_transverse_templates(rows)


def default_cip_zone_assignments(
    layout_rows: list[dict[str, Any]],
    longitudinal_templates: list[dict[str, Any]] | None = None,
    transverse_templates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return one rebar assignment per current CIP Section/Zone.

    The layout row identifier is preserved directly (normally Z1, Z2, ...).
    No physical-joint semantics are introduced.
    """

    long_map = template_map(longitudinal_templates or default_cip_longitudinal_templates())
    trans_map = transverse_template_map(transverse_templates or default_cip_transverse_templates())
    preferred_long = RB_SOLID_COLUMN if RB_SOLID_COLUMN in long_map else next(iter(long_map), "")
    preferred_trans = TR_SOLID_COLUMN if TR_SOLID_COLUMN in trans_map else next(iter(trans_map), "")
    output: list[dict[str, Any]] = []
    for index, row in enumerate(sorted(layout_rows, key=lambda item: _float(item.get("x_start_m"), 0.0))):
        zone_id = _text(row.get("Segment")) or f"Z{index + 1}"
        output.append(
            {
                "Zone ID": zone_id,
                "Segment": zone_id,
                "s_start_m": _float(row.get("x_start_m"), 0.0),
                "s_end_m": _float(row.get("x_end_m"), 0.0),
                "Rebar template": preferred_long,
                "Longitudinal template": preferred_long,
                "Transverse template": preferred_trans,
                "Purpose": "Cast-in-Place Section/Zone reinforcement",
            }
        )
    return canonical_rebar_zones(output)


def _layout_map(layout_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("Segment")): row
        for row in layout_rows
        if _text(row.get("Segment"))
    }


def reconcile_cip_zone_assignments(
    assignments: list[dict[str, Any]],
    layout_rows: list[dict[str, Any]],
    longitudinal_templates: list[dict[str, Any]],
    transverse_templates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reconcile layout changes without replacing valid engineering assignments.

    Existing assignments are preserved by Zone ID.  New Zones receive safe
    default template references.  Removed Zones disappear from the active map.
    """

    current = {str(row.get("Zone ID") or ""): row for row in canonical_rebar_zones(assignments)}
    defaults = {
        str(row.get("Zone ID") or ""): row
        for row in default_cip_zone_assignments(layout_rows, longitudinal_templates, transverse_templates)
    }
    output: list[dict[str, Any]] = []
    active_ids: set[str] = set()
    for index, layout in enumerate(sorted(layout_rows, key=lambda item: _float(item.get("x_start_m"), 0.0))):
        zone_id = _text(layout.get("Segment")) or f"Z{index + 1}"
        active_ids.add(zone_id)
        row = dict(current.get(zone_id) or defaults.get(zone_id) or {})
        row["Zone ID"] = zone_id
        row["Segment"] = zone_id
        row["s_start_m"] = _float(layout.get("x_start_m"), 0.0)
        row["s_end_m"] = _float(layout.get("x_end_m"), 0.0)
        output.append(row)
    # Preserve dormant engineering assignments when the active CIP layout is
    # edited or a Zone is temporarily removed. They are not active/credited,
    # but Project JSON round-trips them non-destructively for later restoration.
    for zone_id, row in current.items():
        if zone_id and zone_id not in active_ids:
            output.append(dict(row))
    return canonical_rebar_zones(output)


def validate_cip_template_model(
    *,
    layout_rows: list[dict[str, Any]],
    longitudinal_templates: list[dict[str, Any]],
    transverse_templates: list[dict[str, Any]],
    zone_assignments: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Validate the solver-neutral CIP template/Zone input model."""

    errors: list[str] = []
    warnings: list[str] = []
    long_rows = canonical_rebar_templates(longitudinal_templates)
    trans_rows = canonical_transverse_templates(transverse_templates)
    long_map = template_map(long_rows)
    trans_map = transverse_template_map(trans_rows)
    zones = canonical_rebar_zones(zone_assignments)
    layout = _layout_map(layout_rows)

    for row in long_rows:
        if str(row.get("Applicable role") or "") not in {"Solid", "Any"}:
            errors.append(f"{row.get('Template ID')}: Hollow longitudinal templates are not applicable to Cast-in-Place Crossbeams.")
    for row in trans_rows:
        if str(row.get("Applicable role") or "") not in {"Solid", "Any"}:
            errors.append(f"{row.get('Template ID')}: Hollow transverse templates are not applicable to Cast-in-Place Crossbeams.")

    zone_by_id = {str(row.get("Zone ID") or ""): row for row in zones}
    for layout_id, layout_row in layout.items():
        zone = zone_by_id.get(layout_id)
        if zone is None:
            errors.append(f"{layout_id}: no Cast-in-Place rebar template assignment is defined.")
            continue
        if str(zone.get("Longitudinal template") or "") not in long_map:
            errors.append(f"{layout_id}: select an active Solid longitudinal Rebar Template.")
        if str(zone.get("Transverse template") or "") not in trans_map:
            errors.append(f"{layout_id}: select an active Solid Transverse / Shear Template.")
        start = _float(layout_row.get("x_start_m"), 0.0)
        end = _float(layout_row.get("x_end_m"), 0.0)
        if abs(_float(zone.get("s_start_m"), 0.0) - start) > 1e-6 or abs(_float(zone.get("s_end_m"), 0.0) - end) > 1e-6:
            errors.append(f"{layout_id}: rebar assignment station extent is out of sync with Section / Zone Layout.")

    unknown = [zone_id for zone_id in zone_by_id if zone_id not in layout]
    if unknown:
        warnings.append("Dormant CIP rebar assignments are not active in the current Section / Zone Layout: " + ", ".join(sorted(unknown)) + ".")

    for row in long_rows:
        if not bool(row.get("Active")):
            continue
        if not any(float(row.get(field) or 0.0) > 0.0 for field in ("Top As mm²", "Bottom As mm²", "Side As mm²")):
            warnings.append(
                f"{row.get('Template ID')}: adopted provided longitudinal As is not defined; auto-layout remains preview-only and receives no solver credit."
            )

    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def _longitudinal_signature(template: Mapping[str, Any]) -> tuple[Any, ...]:
    method = _text(template.get("Outer layout method"))
    quantity = (
        int(template.get("Outer exact bar count") or 0)
        if method == "By exact bar count"
        else round(_float(template.get("Outer target spacing mm"), 0.0), 6)
    )
    return (
        bool(template.get("Active")),
        bool(template.get("Outer face bars")),
        _text(template.get("Outer bar size")),
        _text(template.get("Rebar material")),
        round(_float(template.get("fy MPa"), 0.0), 6),
        method,
        quantity,
        round(_float(template.get("Outer center offset mm"), 0.0), 6),
        round(_float(template.get("Top As mm²"), 0.0), 6),
        round(_float(template.get("Bottom As mm²"), 0.0), 6),
        round(_float(template.get("Side As mm²"), 0.0), 6),
        bool(template.get("Credit inside segment")),
    )


def cip_continuity_audit_rows(
    layout_rows: list[dict[str, Any]],
    zone_assignments: list[dict[str, Any]],
    longitudinal_templates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return conservative continuity review rows at each CIP Zone boundary.

    Matching adjacent template signatures are reported as ``MATCHED LAYOUT`` —
    not as certified bar continuity.  Any change remains ``REVIEW REQUIRED``.
    """

    zones = {str(row.get("Zone ID") or ""): row for row in canonical_rebar_zones(zone_assignments)}
    templates = template_map(longitudinal_templates)
    ordered = sorted(layout_rows, key=lambda row: _float(row.get("x_start_m"), 0.0))
    output: list[dict[str, Any]] = []
    for left, right in zip(ordered, ordered[1:]):
        left_id = _text(left.get("Segment"))
        right_id = _text(right.get("Segment"))
        left_zone = zones.get(left_id, {})
        right_zone = zones.get(right_id, {})
        left_tid = _text(left_zone.get("Longitudinal template"))
        right_tid = _text(right_zone.get("Longitudinal template"))
        left_template = templates.get(left_tid)
        right_template = templates.get(right_tid)
        if left_template is None or right_template is None:
            status = "REVIEW REQUIRED"
            interpretation = "Missing active longitudinal template assignment"
        elif _longitudinal_signature(left_template) == _longitudinal_signature(right_template):
            status = "MATCHED LAYOUT"
            interpretation = "Adjacent Zone layouts match; bars may remain continuous. Development/splice/termination QA is still required."
        else:
            status = "REVIEW REQUIRED"
            interpretation = "Longitudinal arrangement changes across this property boundary; determine continuous bars and intentional additions/terminations."
        output.append(
            {
                "Boundary": f"{left_id} / {right_id}",
                "s (m)": _float(left.get("x_end_m"), 0.0),
                "Left template": left_tid or "—",
                "Right template": right_tid or "—",
                "Status": status,
                "Continuity interpretation": interpretation,
            }
        )
    return output
