"""Cast-in-Place Crossbeam reinforcement template/zone model.

CROSSBEAM.RB-CIP2A aligns the Cast-in-Place Rebar workspace with the accepted
Precast Segmental interaction pattern while keeping a separate canonical state.
CROSSBEAM.RB-CIP2B locks Section/Zone template assignment as the single adopted
reinforcement source for Cast-in-Place.  A separate per-template ``Credit in
zone`` switch is intentionally not part of CIP semantics.

CROSSBEAM.RB-CIP3A adds conservative transition classification at adjacent CIP
Zone boundaries. CROSSBEAM.RB-CIP3B recognizes valid auto-layout definitions as
complete quantity sources, keeps adopted As optional, and improves transition review clarity.  It distinguishes matched layouts, exact-count bar additions,
exact-count bar reductions, and unresolved layout changes without certifying
bar identity, development, splice, termination, or anchorage.

CIP uses Solid-only longitudinal/transverse templates assigned to Section/Zones.
Zone boundaries are property boundaries, not physical joints, so longitudinal
continuity is reviewed across adjacent Zones rather than forced to zero.

This module is solver-neutral.  It does not grant ULS/SLS/PMM/shear/torsion
credit and does not certify development length, splice, curtailment, anchorage,
or exact bar-to-bar continuity.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import pi
from typing import Any

from concrete_pmm_pro.crossbeam.rebar import (
    RB_SOLID_COLUMN,
    REBAR_DIAMETER_BY_SIZE,
    TEMPLATE_BAR_SIZE_OPTIONS,
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


def cip_longitudinal_quantity_definition(template: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical quantity-definition status for one CIP template.

    Section/Zone template assignment is the adoption decision.  A valid
    auto-layout definition (bar size plus exact count or target spacing) is a
    complete reinforcement quantity source; engineers are not required to
    duplicate the same intent in the optional adopted-As fields.  Exact-count
    layouts can resolve total perimeter-bar area directly.  Target-spacing
    layouts remain geometry-derived because the generated count depends on the
    assigned Solid section perimeter.

    This status is input/QA metadata only and does not enable solver credit.
    """

    row = dict(template or {})
    adopted = tuple(
        max(_float(row.get(field), 0.0), 0.0)
        for field in ("Top As mm²", "Bottom As mm²", "Side As mm²")
    )
    adopted_total = sum(adopted)
    if adopted_total > 0.0:
        return {
            "Complete": True,
            "Source": "ADOPTED AS OVERRIDE",
            "Definition": f"Top/Bottom/Side adopted As total = {adopted_total:.1f} mm²",
            "Derived bar count": None,
            "Derived As mm²": adopted_total,
            "Geometry derived": False,
            "Issue": "",
        }

    if not bool(row.get("Active")):
        return {
            "Complete": False,
            "Source": "INACTIVE",
            "Definition": "Assigned template is inactive",
            "Derived bar count": None,
            "Derived As mm²": None,
            "Geometry derived": False,
            "Issue": "assigned longitudinal template is inactive",
        }
    if not bool(row.get("Outer face bars")):
        return {
            "Complete": False,
            "Source": "NO OUTER LAYOUT",
            "Definition": "Outer-face longitudinal layout is disabled",
            "Derived bar count": None,
            "Derived As mm²": None,
            "Geometry derived": False,
            "Issue": "outer-face longitudinal layout is disabled and no adopted As override is defined",
        }

    bar_size = _text(row.get("Outer bar size")).upper()
    if bar_size not in TEMPLATE_BAR_SIZE_OPTIONS or bar_size not in REBAR_DIAMETER_BY_SIZE:
        return {
            "Complete": False,
            "Source": "INVALID BAR",
            "Definition": f"Unsupported outer bar size: {bar_size or '(blank)'}",
            "Derived bar count": None,
            "Derived As mm²": None,
            "Geometry derived": False,
            "Issue": "outer-face bar size is not supported",
        }

    method = _text(row.get("Outer layout method"))
    diameter = float(REBAR_DIAMETER_BY_SIZE[bar_size])
    one_bar_area = pi * diameter * diameter / 4.0
    if method == "By exact bar count":
        count = int(_float(row.get("Outer exact bar count"), 0.0))
        if count <= 0:
            return {
                "Complete": False,
                "Source": "EXACT COUNT",
                "Definition": f"{bar_size}; exact bar count is not positive",
                "Derived bar count": None,
                "Derived As mm²": None,
                "Geometry derived": False,
                "Issue": "exact outer bar count must be positive",
            }
        area = count * one_bar_area
        return {
            "Complete": True,
            "Source": "EXACT BAR COUNT",
            "Definition": f"{count}-{bar_size}; derived total perimeter As = {area:.1f} mm²",
            "Derived bar count": count,
            "Derived As mm²": area,
            "Geometry derived": False,
            "Issue": "",
        }

    if method == "By target spacing":
        spacing = _float(row.get("Outer target spacing mm"), 0.0)
        if spacing <= 0.0:
            return {
                "Complete": False,
                "Source": "TARGET SPACING",
                "Definition": f"{bar_size}; target spacing is not positive",
                "Derived bar count": None,
                "Derived As mm²": None,
                "Geometry derived": True,
                "Issue": "target outer-bar spacing must be positive",
            }
        return {
            "Complete": True,
            "Source": "TARGET SPACING",
            "Definition": f"{bar_size} at target spacing {spacing:.1f} mm; count and As resolve from assigned Section geometry",
            "Derived bar count": None,
            "Derived As mm²": None,
            "Geometry derived": True,
            "Issue": "",
        }

    return {
        "Complete": False,
        "Source": "INVALID METHOD",
        "Definition": f"Unsupported outer layout method: {method or '(blank)'}",
        "Derived bar count": None,
        "Derived As mm²": None,
        "Geometry derived": False,
        "Issue": "outer-face layout method is not supported",
    }


def cip_assigned_longitudinal_quantity_rows(
    *,
    layout_rows: list[dict[str, Any]],
    longitudinal_templates: list[dict[str, Any]],
    zone_assignments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return one quantity-source row per assigned active CIP template."""

    layout = _layout_map(layout_rows)
    zones = {str(row.get("Zone ID") or ""): row for row in canonical_rebar_zones(zone_assignments)}
    templates = template_map(longitudinal_templates)
    assigned_ids = []
    for zone_id in layout:
        zone = zones.get(zone_id, {})
        template_id = _text(zone.get("Longitudinal template") or zone.get("Rebar template"))
        if template_id and template_id not in assigned_ids:
            assigned_ids.append(template_id)

    output: list[dict[str, Any]] = []
    for template_id in assigned_ids:
        template = templates.get(template_id)
        if template is None:
            output.append(
                {
                    "Template ID": template_id,
                    "Complete": False,
                    "Source": "MISSING TEMPLATE",
                    "Definition": "Assigned template does not resolve to an active Solid template",
                    "Derived bar count": None,
                    "Derived As mm²": None,
                    "Geometry derived": False,
                    "Issue": "assigned template does not resolve to an active Solid template",
                }
            )
            continue
        output.append({"Template ID": template_id, **cip_longitudinal_quantity_definition(template)})
    return output


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

    # Section/Zone assignment is the canonical adopted reinforcement source in
    # Cast-in-Place.  Only templates actually assigned to active Zones affect
    # completeness; dormant/unassigned library templates do not create noise.
    for quantity in cip_assigned_longitudinal_quantity_rows(
        layout_rows=layout_rows,
        longitudinal_templates=long_rows,
        zone_assignments=zones,
    ):
        if not bool(quantity.get("Complete")):
            warnings.append(
                f"{quantity.get('Template ID')}: longitudinal quantity definition is incomplete — {quantity.get('Issue')}."
            )

    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def cip_adopted_zone_reinforcement_rows(
    *,
    layout_rows: list[dict[str, Any]],
    longitudinal_templates: list[dict[str, Any]],
    transverse_templates: list[dict[str, Any]],
    zone_assignments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve the adopted CIP reinforcement source for each active Zone.

    The Section/Zone assignment itself is the engineering adoption decision.
    Legacy template metadata such as ``Credit inside segment`` is deliberately
    ignored here; there is no second design-credit switch in Cast-in-Place.

    This resolver is still solver-neutral.  It exposes the validated source
    mapping future solver handoff must consume, but it does not activate solver
    credit in RB-CIP2B.
    """

    zones = {str(row.get("Zone ID") or ""): row for row in canonical_rebar_zones(zone_assignments)}
    long_map = template_map(longitudinal_templates)
    trans_map = transverse_template_map(transverse_templates)
    output: list[dict[str, Any]] = []
    for index, layout in enumerate(sorted(layout_rows, key=lambda row: _float(row.get("x_start_m"), 0.0))):
        zone_id = _text(layout.get("Segment")) or f"Z{index + 1}"
        assignment = zones.get(zone_id, {})
        long_id = _text(assignment.get("Longitudinal template") or assignment.get("Rebar template"))
        trans_id = _text(assignment.get("Transverse template"))
        long_row = long_map.get(long_id)
        trans_row = trans_map.get(trans_id)
        issues: list[str] = []
        if long_row is None:
            issues.append("Longitudinal template is not assigned to an active Solid template")
        if trans_row is None:
            issues.append("Transverse template is not assigned to an active Solid template")
        output.append(
            {
                "Zone ID": zone_id,
                "s_start_m": _float(layout.get("x_start_m"), 0.0),
                "s_end_m": _float(layout.get("x_end_m"), 0.0),
                "Section ID": _text(layout.get("Section ID")),
                "Longitudinal template": long_id,
                "Transverse template": trans_id,
                "Longitudinal source": dict(long_row) if long_row is not None else None,
                "Transverse source": dict(trans_row) if trans_row is not None else None,
                "Adoption basis": "Section / Zone assignment",
                "Status": "ADOPTED SOURCE" if not issues else "REVIEW REQUIRED",
                "Issues": issues,
            }
        )
    return output


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
    )


def _adopted_as_vector(template: Mapping[str, Any]) -> tuple[float, float, float]:
    return tuple(
        round(_float(template.get(field), 0.0), 6)
        for field in ("Top As mm²", "Bottom As mm²", "Side As mm²")
    )


def _transition_identity_signature(template: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return bar-family attributes required for adopted-As comparison."""

    return (
        bool(template.get("Active")),
        bool(template.get("Outer face bars")),
        _text(template.get("Outer bar size")),
        _text(template.get("Rebar material")),
        round(_float(template.get("fy MPa"), 0.0), 6),
        round(_float(template.get("Outer center offset mm"), 0.0), 6),
    )


def _transition_core_signature(template: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return attributes that must match before quantity-only comparison.

    A quantity increase/reduction is identified only when the adjacent layouts
    use the same bar family, material, face participation, layout method, and
    center offset.  Otherwise the transition remains a general layout change.
    """

    return (
        bool(template.get("Active")),
        bool(template.get("Outer face bars")),
        _text(template.get("Outer bar size")),
        _text(template.get("Rebar material")),
        round(_float(template.get("fy MPa"), 0.0), 6),
        _text(template.get("Outer layout method")),
        round(_float(template.get("Outer center offset mm"), 0.0), 6),
    )


def _classify_cip_longitudinal_transition(
    left_template: Mapping[str, Any],
    right_template: Mapping[str, Any],
) -> tuple[str, str, str]:
    """Classify one adjacent-Zone longitudinal transition conservatively.

    Returns ``(status, quantity_change, interpretation)``.  The classification
    is topology/reference QA only; it never certifies exact bar identity,
    development, splice, termination, or anchorage.
    """

    if _longitudinal_signature(left_template) == _longitudinal_signature(right_template):
        return (
            "MATCHED LAYOUT",
            "No template-level change",
            "Adjacent Zone layouts match; bars may remain continuous. Exact bar identity and development/splice/termination remain separate QA.",
        )

    left_as = _adopted_as_vector(left_template)
    right_as = _adopted_as_vector(right_template)
    left_as_total = sum(left_as)
    right_as_total = sum(right_as)
    if left_as_total > 0.0 or right_as_total > 0.0:
        if left_as_total <= 0.0 or right_as_total <= 0.0:
            return (
                "REVIEW REQUIRED",
                "Adopted As is incomplete on one side",
                "Both adjacent assigned templates need adopted longitudinal As before an increase/reduction can be classified safely.",
            )
        if _transition_identity_signature(left_template) != _transition_identity_signature(right_template):
            return (
                "REVIEW REQUIRED",
                "Bar family changes with adopted As",
                "Bar size, material, face participation, or center offset changes; adopted As alone cannot establish continuing-bar identity.",
            )
        increases = all(r >= l - 1e-6 for l, r in zip(left_as, right_as)) and any(
            r > l + 1e-6 for l, r in zip(left_as, right_as)
        )
        reductions = all(r <= l + 1e-6 for l, r in zip(left_as, right_as)) and any(
            r < l - 1e-6 for l, r in zip(left_as, right_as)
        )
        delta_total = right_as_total - left_as_total
        if increases:
            return (
                "BAR ADDITION",
                f"Adopted As increases by {delta_total:.1f} mm²",
                "The right Zone requires additional adopted longitudinal reinforcement. Identify continuous bars and develop/anchor added bars before solver credit.",
            )
        if reductions:
            return (
                "BAR REDUCTION",
                f"Adopted As reduces by {abs(delta_total):.1f} mm²",
                "The right Zone uses less adopted longitudinal reinforcement. Define intentional cut-off/continuation and verify development before solver credit.",
            )
        return (
            "REVIEW REQUIRED",
            "Adopted As distribution changes",
            "Top/bottom/side adopted reinforcement changes in different directions; explicit bar continuity mapping is required.",
        )

    if _transition_core_signature(left_template) == _transition_core_signature(right_template):
        method = _text(left_template.get("Outer layout method"))
        if method == "By exact bar count":
            left_count = int(left_template.get("Outer exact bar count") or 0)
            right_count = int(right_template.get("Outer exact bar count") or 0)
            delta = right_count - left_count
            if delta > 0:
                return (
                    "BAR ADDITION",
                    f"+{delta} perimeter bar(s)",
                    "The right Zone specifies more bars of the same size/material/layout basis. Exact continuing-bar identity and development/anchorage remain unverified.",
                )
            if delta < 0:
                return (
                    "BAR REDUCTION",
                    f"{abs(delta)} fewer perimeter bar(s)",
                    "The right Zone specifies fewer bars of the same size/material/layout basis. Intentional cut-off and development remain unverified.",
                )
        elif method == "By target spacing":
            left_spacing = _float(left_template.get("Outer target spacing mm"), 0.0)
            right_spacing = _float(right_template.get("Outer target spacing mm"), 0.0)
            if abs(left_spacing - right_spacing) > 1e-6:
                direction = "denser" if right_spacing < left_spacing else "wider"
                return (
                    "REVIEW REQUIRED",
                    f"Target spacing changes {left_spacing:.1f} → {right_spacing:.1f} mm",
                    f"The right Zone uses {direction} target spacing. Actual bar addition/reduction depends on section geometry and is not inferred at template level.",
                )

    return (
        "REVIEW REQUIRED",
        "Layout attributes change",
        "Bar size, material, layout method, offset, or participation changes across this property boundary; explicit continuity mapping is required.",
    )


def cip_continuity_audit_rows(
    layout_rows: list[dict[str, Any]],
    zone_assignments: list[dict[str, Any]],
    longitudinal_templates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return conservative transition QA rows at each CIP Zone boundary.

    The audit classifies ``MATCHED LAYOUT``, ``BAR ADDITION``, ``BAR REDUCTION``,
    or ``REVIEW REQUIRED``.  These are topology/reference classifications only,
    never development/splice/termination or code-compliance certification.
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
            legacy_status = status
            quantity_change = "Not available"
            interpretation = "Missing active longitudinal template assignment."
        elif (
            _longitudinal_signature(left_template) == _longitudinal_signature(right_template)
            and _text(left.get("Section ID")) != _text(right.get("Section ID"))
        ):
            # Preserve the RB-CIP2A template-signature Status field for
            # backward compatibility, while the production Transition field
            # applies the safer geometry-aware review classification.
            legacy_status = "MATCHED LAYOUT"
            status = "REVIEW REQUIRED"
            quantity_change = "Section geometry changes"
            interpretation = (
                "The same template is assigned across different Section IDs. Generated bar count/coordinates and exact continuity must be reviewed for the geometry transition."
            )
        else:
            status, quantity_change, interpretation = _classify_cip_longitudinal_transition(
                left_template, right_template
            )
            legacy_status = status
        output.append(
            {
                "Boundary": f"{left_id} / {right_id}",
                "s (m)": _float(left.get("x_end_m"), 0.0),
                "Left template": left_tid or "—",
                "Right template": right_tid or "—",
                "Status": legacy_status,
                "Transition": status,
                "Quantity change": quantity_change,
                "Continuity interpretation": interpretation,
                "Required review": interpretation,
            }
        )
    return output
