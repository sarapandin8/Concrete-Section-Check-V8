"""Workflow-scoped Rebar workspace for segmental Portal Frame Crossbeams.

CROSSBEAM.RB2C replaces the selected-template form with compact editable tables.
Default and project templates use the same direct-edit workflow; project rows may
be copied or marked for guarded deletion without exposing hidden horizontal columns.
RB2D makes Template IDs engineer-editable with atomic Zone-reference updates and
adds SD40/SD50 plus 390/490 MPa dropdowns. RB2E completes the linked-grade UX by
refreshing the editor from canonical state whenever either dropdown changes, so a
single material or fy selection immediately displays the matching pair. The
unverified PT-continuity guard and all solver ownership remain unchanged. It never
routes template, zone, or preview state into existing PMM, Beam/Girder, SLS,
shear, torsion, or report solvers.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from concrete_pmm_pro.core.reinforcement_system import ordinary_rebar_enabled, prestressing_steel_enabled
from concrete_pmm_pro.core.models import Rebar
from concrete_pmm_pro.crossbeam.rebar import (
    RB_HOLLOW_MIN,
    RB_SOLID_ANCHORAGE,
    RB_SOLID_COLUMN,
    TEMPLATE_CONSTRUCTION_OPTIONS,
    TEMPLATE_LONGITUDINAL_BASIS_OPTIONS,
    TEMPLATE_ROLE_OPTIONS,
    TEMPLATE_BAR_SIZE_OPTIONS,
    TEMPLATE_LAYOUT_METHOD_OPTIONS,
    TEMPLATE_MATERIAL_OPTIONS,
    TEMPLATE_FY_OPTIONS,
    REBAR_FY_BY_MATERIAL,
    REBAR_MATERIAL_BY_FY,
    canonical_rebar_templates,
    duplicate_rebar_template,
    canonical_rebar_zones,
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
    new_rebar_template,
    segment_joint_audit_rows,
    segment_signature,
    station_rebar_audit_rows,
    template_map,
    rebar_diameter_mm,
    validate_rebar_zones,
)
from concrete_pmm_pro.crossbeam.transverse import (
    canonical_transverse_templates,
    default_crossbeam_transverse_templates,
    default_transverse_template_id,
    transverse_template_map,
)
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_DEFINITIONS_KEY,
    build_geometry_for_definition,
    canonical_section_definitions,
    definition_map,
)
from concrete_pmm_pro.geometry.rebar_layout import (
    PerimeterRebarLayoutResult,
    generate_inner_face_rebar_layout,
    generate_perimeter_rebar_layout,
)
from concrete_pmm_pro.ui.commercial import render_metric_cards, render_page_header, render_section_bar
from concrete_pmm_pro.ui.crossbeam_transverse_page import (
    CB_TR_TEMPLATE_ROWS_KEY,
    ensure_crossbeam_transverse_state,
    render_crossbeam_transverse_template_library,
    render_transverse_preview_summary,
)
from concrete_pmm_pro.ui.crossbeam_pages import FIGURE_CONFIG, crossbeam_segment_layout_from_state
from concrete_pmm_pro.visualization import create_section_preview


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
CB_RB_ZONE_PURPOSE_KEY_PREFIX = "crossbeam_rb2a_zone_purpose"
CB_RB_TEMPLATE_ACTION_KEY = "crossbeam_rb2b_template_pending_action"
CB_RB_TEMPLATE_DELETE_CONFIRM_KEY = "crossbeam_rb2b_template_delete_confirm"

RB2_SUBVIEWS = (
    ("Templates", "Longitudinal"),
    ("Transverse / Shear", "Transverse / Shear"),
    ("Segment / Zone", "Segment / Zone"),
    ("Section Rebar Preview", "Preview"),
    ("Joint & Station Audit", "Joint & Station Audit"),
)


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return [dict(row) for row in value.to_dict(orient="records")]
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    if isinstance(value, tuple):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _ensure_rb1_state(segment_rows: list[dict[str, Any]]) -> None:
    ensure_crossbeam_transverse_state()
    if CB_RB_TEMPLATE_ROWS_KEY not in st.session_state:
        st.session_state[CB_RB_TEMPLATE_ROWS_KEY] = default_crossbeam_rebar_templates()
    st.session_state.setdefault(CB_RB_TEMPLATE_REV_KEY, 0)

    if CB_RB_ZONE_ROWS_KEY not in st.session_state:
        st.session_state[CB_RB_ZONE_ROWS_KEY] = default_crossbeam_rebar_zones(
            segment_rows,
            st.session_state[CB_RB_TEMPLATE_ROWS_KEY],
            st.session_state[CB_TR_TEMPLATE_ROWS_KEY],
        )
        st.session_state[CB_RB_SEGMENT_SIGNATURE_KEY] = segment_signature(segment_rows)
    else:
        # TR1 backward-compatible migration: preserve every existing zone edit,
        # adding only a missing Transverse Template reference by segment role.
        segment_by_id = {str(row.get("Segment") or ""): row for row in segment_rows}
        migrated = []
        changed = False
        transverse_rows = canonical_transverse_templates(st.session_state.get(CB_TR_TEMPLATE_ROWS_KEY, []))
        for zone in canonical_rebar_zones(_records(st.session_state.get(CB_RB_ZONE_ROWS_KEY))):
            updated = dict(zone)
            if not str(updated.get("Transverse template") or "").strip():
                segment = segment_by_id.get(str(updated.get("Segment") or ""), {})
                role = str(segment.get("Section role") or "Solid")
                updated["Transverse template"] = default_transverse_template_id(role, transverse_rows)
                changed = True
            migrated.append(updated)
        if changed:
            st.session_state[CB_RB_ZONE_ROWS_KEY] = migrated
    st.session_state.setdefault(CB_RB_ZONE_REV_KEY, 0)


def _template_quantity_defined(template: Mapping[str, Any]) -> bool:
    return any(
        float(template.get(key, 0.0) or 0.0) > 0.0
        for key in ("Top As mm²", "Bottom As mm²", "Side As mm²", "Av/s mm²/mm")
    )


def _rebar_elevation_figure(
    segment_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
    template_rows: list[dict[str, Any]],
    length_m: float,
) -> go.Figure:
    """Return a schematic rebar continuity review figure.

    Bars are schematic template extents, not bar quantities or design output.
    Each line intentionally terminates inside its assigned zone and never
    crosses a segment joint.
    """

    fig = go.Figure()
    templates = template_map(template_rows)
    segment_by_id = {str(row.get("Segment") or ""): row for row in segment_rows}
    fills = {"Solid": "rgba(120,140,160,0.50)", "Hollow": "rgba(120,140,160,0.20)"}
    outlines = {"Solid": "#3d556b", "Hollow": "#607d94"}

    for row in segment_rows:
        start = float(row.get("x_start_m", 0.0))
        end = float(row.get("x_end_m", 0.0))
        role = str(row.get("Section role") or "Solid")
        fig.add_shape(
            type="rect",
            x0=start,
            x1=end,
            y0=0.0,
            y1=1.0,
            line={"color": outlines.get(role, outlines["Solid"]), "width": 1.1},
            fillcolor=fills.get(role, fills["Solid"]),
            layer="below",
        )
        fig.add_annotation(
            x=0.5 * (start + end),
            y=0.91,
            text=f"<b>{row.get('Segment', '')}</b><br>{role}",
            showarrow=False,
            font={"size": 10, "color": "#17324d"},
        )

    # Legend-only traces use the same visual language as actual zone lines.
    fig.add_trace(
        go.Scatter(
            x=[None, None],
            y=[None, None],
            mode="lines",
            line={"color": "#2f7d4a", "width": 3},
            name="Segment-local ordinary rebar",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None, None],
            y=[None, None],
            mode="lines",
            line={"color": "#155a9c", "width": 5},
            name="Solid CIP zone rebar",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None, None],
            y=[None, None],
            mode="lines",
            line={"color": "#b44444", "width": 1.5, "dash": "dash"},
            name="Segment joint — ordinary rebar = 0",
            hoverinfo="skip",
        )
    )

    for zone in canonical_rebar_zones(zone_rows):
        segment = segment_by_id.get(zone["Segment"], {})
        role = str(segment.get("Section role") or "Solid")
        template = templates.get(zone["Rebar template"], {})
        start = float(zone["s_start_m"])
        end = float(zone["s_end_m"])
        span = max(end - start, 0.0)
        # A visible termination gap makes the non-continuity rule unambiguous.
        gap = min(0.06, 0.025 * span) if span > 0.12 else 0.0
        x0 = start + gap
        x1 = end - gap
        color = "#2f7d4a" if role == "Hollow" else "#155a9c"
        width = 3 if role == "Hollow" else 5
        for y in (0.24, 0.76):
            fig.add_trace(
                go.Scatter(
                    x=[x0, x1],
                    y=[y, y],
                    mode="lines",
                    line={"color": color, "width": width},
                    name=f"{zone['Zone ID']} rebar",
                    showlegend=False,
                    hovertemplate=(
                        f"Zone: {zone['Zone ID']}<br>Segment: {zone['Segment']}<br>"
                        f"Template: {zone['Rebar template']}<br>"
                        f"Extent: {start:.3f}–{end:.3f} m<br>"
                        "Ordinary rebar terminates within the assigned segment/zone<extra></extra>"
                    ),
                )
            )
        fig.add_annotation(
            x=0.5 * (start + end),
            y=0.50,
            text=f"<b>{zone['Zone ID']}</b><br>{zone['Rebar template']}",
            showarrow=False,
            font={"size": 9, "color": "#16324f"},
        )
        if template and not _template_quantity_defined(template):
            fig.add_annotation(
                x=0.5 * (start + end),
                y=0.08,
                text="As / Av/s TBD",
                showarrow=False,
                font={"size": 8, "color": "#8a5b17"},
            )

    ordered = sorted(segment_rows, key=lambda row: float(row.get("x_start_m", 0.0)))
    for left, right in zip(ordered, ordered[1:]):
        station = float(left.get("x_end_m", 0.0))
        fig.add_vline(x=station, line={"color": "#b44444", "width": 1.5, "dash": "dash"})
        fig.add_annotation(
            x=station,
            y=1.08,
            text="<b>Ord. rebar = 0</b><br>PT not verified",
            showarrow=False,
            font={"size": 9, "color": "#9b2929"},
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="rgba(180,68,68,0.35)",
            borderwidth=1,
            borderpad=2,
        )

    fig.update_layout(
        title={"text": "Crossbeam Ordinary Rebar Zone and Joint-Continuity Review", "x": 0.5, "xanchor": "center"},
        height=520,
        margin={"l": 70, "r": 35, "t": 95, "b": 70},
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"family": "Arial, sans-serif", "size": 11},
        xaxis={
            "title": "Station s (m)",
            "range": [-0.015 * max(length_m, 1.0), 1.015 * max(length_m, 1.0)],
            "showgrid": True,
            "gridcolor": "#e7edf4",
            "zeroline": False,
        },
        yaxis={
            "title": "Schematic only",
            "range": [-0.05, 1.18],
            "showticklabels": False,
            "showgrid": False,
            "zeroline": False,
        },
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.17, "xanchor": "center", "x": 0.5},
        hovermode="closest",
    )
    return fig


def _render_locked_joint_rule() -> None:
    render_section_bar(
        "Locked segment-joint participation rule",
        "Ordinary reinforcement is locked to zero across every segment joint. Post-tensioning continuity is required but remains unverified until Tendon System/Profile audit is connected.",
        mark="J",
    )
    st.warning(
        "LOCKED WORKFLOW RULE — Ordinary rebar crossing every segment joint = 0 mm². "
        "Rebar may be credited only inside its assigned segment/zone. PT continuity across each joint is REQUIRED, "
        "but CROSSBEAM.RB2D does not yet verify active tendon geometry or Aps at the joint plane."
    )
    st.caption(
        "Joint shear transfer, interface behavior, opening/decompression, shear keys, anchorage zones, solid–hollow transitions, "
        "column D-regions, and tendon-continuity verification remain separate checks."
    )

def _queue_template_action(action: str, template_id: str = "") -> None:
    st.session_state[CB_RB_TEMPLATE_ACTION_KEY] = {"action": str(action), "template_id": str(template_id)}


def _apply_pending_template_action(
    rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    pending = st.session_state.pop(CB_RB_TEMPLATE_ACTION_KEY, None)
    if not isinstance(pending, Mapping):
        return rows, None
    action = str(pending.get("action") or "")
    selected_id = str(pending.get("template_id") or st.session_state.get(CB_RB_ACTIVE_TEMPLATE_KEY) or "")
    existing_ids = [str(row.get("Template ID") or "") for row in rows]
    message: str | None = None
    if action == "reset":
        rows = default_crossbeam_rebar_templates()
        st.session_state[CB_RB_ACTIVE_TEMPLATE_KEY] = str(rows[0].get("Template ID") or "")
        message = "Reset the Rebar Template Library to the three Crossbeam defaults."
    elif action == "new_hollow":
        created = new_rebar_template("Hollow", existing_ids)
        rows.append(created)
        st.session_state[CB_RB_ACTIVE_TEMPLATE_KEY] = created["Template ID"]
        message = f"Created {created['Template ID']}. Edit its name and layout below."
    elif action == "new_solid":
        created = new_rebar_template("Solid", existing_ids)
        rows.append(created)
        st.session_state[CB_RB_ACTIVE_TEMPLATE_KEY] = created["Template ID"]
        message = f"Created {created['Template ID']}. Edit its name and layout below."
    elif action == "duplicate":
        source = next((row for row in rows if str(row.get("Template ID") or "") == selected_id), None)
        if source is not None:
            created = duplicate_rebar_template(source, existing_ids)
            rows.append(created)
            st.session_state[CB_RB_ACTIVE_TEMPLATE_KEY] = created["Template ID"]
            message = f"Duplicated {selected_id} as {created['Template ID']}."
    elif action == "delete":
        used_by = sorted(
            str(zone.get("Zone ID") or "")
            for zone in canonical_rebar_zones(zone_rows)
            if str(zone.get("Rebar template") or "") == selected_id
        )
        if used_by:
            message = f"Cannot delete {selected_id}; used by zones: {', '.join(used_by)}."
        elif len(rows) <= 1:
            message = "At least one Rebar Template must remain."
        else:
            rows = [row for row in rows if str(row.get("Template ID") or "") != selected_id]
            st.session_state[CB_RB_ACTIVE_TEMPLATE_KEY] = str(rows[0].get("Template ID") or "")
            st.session_state[CB_RB_TEMPLATE_DELETE_CONFIRM_KEY] = False
            message = f"Deleted {selected_id}."
    rows = canonical_rebar_templates(rows)
    st.session_state[CB_RB_TEMPLATE_ROWS_KEY] = rows
    st.session_state[CB_RB_TEMPLATE_REV_KEY] = int(st.session_state.get(CB_RB_TEMPLATE_REV_KEY, 0)) + 1
    return rows, message


def _auto_layout_summary(template: Mapping[str, Any]) -> str:
    parts: list[str] = []
    if bool(template.get("Outer face bars")):
        outer_method = str(template.get("Outer layout method") or "By target spacing")
        outer_basis = (
            f"{int(template.get('Outer exact bar count') or 0)} bars"
            if outer_method == "By exact bar count"
            else f"@{float(template.get('Outer target spacing mm') or 0.0):.0f}"
        )
        parts.append(f"Outer {template.get('Outer bar size', '')} {outer_basis}")
    if bool(template.get("Inner face bars")):
        inner_method = str(template.get("Inner layout method") or "By target spacing")
        inner_basis = (
            f"{int(template.get('Inner exact bar count') or 0)} bars"
            if inner_method == "By exact bar count"
            else f"@{float(template.get('Inner target spacing mm') or 0.0):.0f}"
        )
        parts.append(f"Inner {template.get('Inner bar size', '')} {inner_basis}")
    return " · ".join(parts) if parts else "Layout OFF"

def _adopted_reinforcement_summary(template: Mapping[str, Any]) -> str:
    top = float(template.get("Top As mm²") or 0.0)
    bottom = float(template.get("Bottom As mm²") or 0.0)
    side = float(template.get("Side As mm²") or 0.0)
    avs = float(template.get("Av/s mm²/mm") or 0.0)
    if not any(value > 0.0 for value in (top, bottom, side, avs)):
        return "Not adopted"
    return f"T/B/S {top:.0f}/{bottom:.0f}/{side:.0f} · Av/s {avs:.4f}"


def _normalize_template_id(value: Any) -> str:
    """Return a compact engineer-editable Template ID.

    Spaces are converted to hyphens and unsupported punctuation is removed so
    the result remains safe for Zone references and future project persistence.
    """

    text = str(value or "").strip().upper()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^A-Z0-9_-]+", "", text)
    text = re.sub(r"-{2,}", "-", text).strip("-_")
    return text[:48]


def _template_identity_rows_from_editor(
    template_rows: list[dict[str, Any]],
    editor_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str], list[str]]:
    """Apply editable Template IDs and update every Zone reference atomically."""

    rows = canonical_rebar_templates(template_rows)
    zones = canonical_rebar_zones(zone_rows)
    proposed: list[dict[str, Any]] = []
    rename_map: dict[str, str] = {}
    errors: list[str] = []

    for index, source in enumerate(rows):
        item = editor_rows[index] if index < len(editor_rows) else {}
        original_id = str(item.get("_Original ID") or source.get("Template ID") or "").strip()
        if original_id != str(source.get("Template ID") or ""):
            source = next(
                (row for row in rows if str(row.get("Template ID") or "") == original_id),
                source,
            )
        new_id = _normalize_template_id(item.get("Template ID", source.get("Template ID")))
        if not new_id:
            errors.append(f"{original_id or f'Row {index + 1}'} requires a Template ID.")
            new_id = original_id
        updated = dict(source)
        updated["Template ID"] = new_id
        updated["Template name"] = str(item.get("Template name") or source.get("Template name") or new_id).strip()
        updated["Applicable role"] = str(item.get("Role") or source.get("Applicable role") or "Any")
        updated["Construction"] = str(item.get("Construction") or source.get("Construction") or "Project-defined")
        if str(updated.get("Applicable role") or "") == "Solid":
            updated["Inner face bars"] = False
        proposed.append(updated)
        if original_id and original_id != new_id:
            rename_map[original_id] = new_id

    normalized_ids = [str(row.get("Template ID") or "") for row in proposed]
    duplicates = sorted({item for item in normalized_ids if item and normalized_ids.count(item) > 1})
    if duplicates:
        errors.append("Duplicate Template IDs are not allowed: " + ", ".join(duplicates) + ".")
    if errors:
        return rows, zones, {}, errors

    updated_zones: list[dict[str, Any]] = []
    for zone in zones:
        updated = dict(zone)
        old_reference = str(updated.get("Longitudinal template") or updated.get("Rebar template") or "")
        if old_reference in rename_map:
            updated["Rebar template"] = rename_map[old_reference]
            updated["Longitudinal template"] = rename_map[old_reference]
        updated_zones.append(updated)

    return canonical_rebar_templates(proposed), canonical_rebar_zones(updated_zones), rename_map, []


def _template_material_rows_from_editor(
    template_rows: list[dict[str, Any]],
    editor_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Merge linked Material/fy dropdowns without allowing an inconsistent pair."""

    rows = canonical_rebar_templates(template_rows)
    by_id = {str(row.get("Template ID") or ""): dict(row) for row in rows}
    warnings: list[str] = []
    for item in editor_rows:
        template_id = str(item.get("Template ID") or "").strip()
        target = by_id.get(template_id)
        if target is None:
            continue
        old_material = str(target.get("Rebar material") or "SD40")
        old_fy = float(target.get("fy MPa") or 390.0)
        new_material = str(item.get("Material") or old_material).strip().upper()
        try:
            new_fy = float(item.get("fy (MPa)") or old_fy)
        except (TypeError, ValueError):
            new_fy = old_fy
        if new_material not in TEMPLATE_MATERIAL_OPTIONS:
            new_material = old_material
        new_fy = 490.0 if abs(new_fy - 490.0) < abs(new_fy - 390.0) else 390.0

        material_changed = new_material != old_material
        fy_changed = new_fy != old_fy
        if material_changed and not fy_changed:
            new_fy = REBAR_FY_BY_MATERIAL[new_material]
        elif fy_changed and not material_changed:
            new_material = REBAR_MATERIAL_BY_FY[new_fy]
        elif material_changed and fy_changed and REBAR_FY_BY_MATERIAL[new_material] != new_fy:
            warnings.append(
                f"{template_id}: Material and fy were inconsistent; adopted {new_material} with fy = "
                f"{REBAR_FY_BY_MATERIAL[new_material]:.0f} MPa."
            )
            new_fy = REBAR_FY_BY_MATERIAL[new_material]

        target["Rebar material"] = new_material
        target["fy MPa"] = new_fy
        target["Longitudinal basis"] = str(item.get("Basis") or target.get("Longitudinal basis") or "Segment-local")
        target["Active"] = bool(item.get("Active"))
        target["Credit inside segment"] = bool(item.get("Credit"))
    return canonical_rebar_templates([by_id[str(row.get("Template ID") or "")] for row in rows]), warnings


def _material_editor_sync_required(
    editor_rows: list[dict[str, Any]],
    canonical_rows: list[dict[str, Any]],
) -> bool:
    """Return True when the editor still displays a stale Material/fy pair.

    ``st.data_editor`` retains its widget-owned cell values for the current key.
    After one linked dropdown is edited, the canonical row is corrected in state,
    but the companion cell would remain visually stale until the editor receives a
    fresh key.  This predicate is used to trigger exactly one revision/rerun.
    """

    canonical_by_id = {
        str(row.get("Template ID") or ""): row
        for row in canonical_rebar_templates(canonical_rows)
    }
    for item in editor_rows:
        template_id = str(item.get("Template ID") or "").strip()
        target = canonical_by_id.get(template_id)
        if target is None:
            continue
        displayed_material = str(item.get("Material") or "").strip().upper()
        try:
            displayed_fy = float(item.get("fy (MPa)"))
        except (TypeError, ValueError):
            return True
        canonical_material = str(target.get("Rebar material") or "").strip().upper()
        canonical_fy = float(target.get("fy MPa") or 0.0)
        if displayed_material != canonical_material or abs(displayed_fy - canonical_fy) > 1.0e-9:
            return True
    return False


def _template_rows_from_editor(
    template_rows: list[dict[str, Any]],
    editor_rows: list[dict[str, Any]],
    field_map: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Merge compact editable-table values into stable Template-ID rows."""

    rows = canonical_rebar_templates(template_rows)
    by_id = {str(row.get("Template ID") or ""): dict(row) for row in rows}
    for item in editor_rows:
        template_id = str(item.get("Template ID") or "").strip()
        target = by_id.get(template_id)
        if target is None:
            continue
        for editor_field, template_field in field_map.items():
            if editor_field in item:
                target[template_field] = item.get(editor_field)
        if str(target.get("Applicable role") or "") == "Solid":
            target["Inner face bars"] = False
    return canonical_rebar_templates([by_id[str(row.get("Template ID") or "")] for row in rows])


def _template_face_layout_from_editor(
    template_rows: list[dict[str, Any]],
    editor_rows: list[dict[str, Any]],
    *,
    face: str,
) -> list[dict[str, Any]]:
    """Merge one compact Outer/Inner layout table into canonical template rows."""

    prefix = "Outer" if str(face).strip().casefold() == "outer" else "Inner"
    rows = canonical_rebar_templates(template_rows)
    by_id = {str(row.get("Template ID") or ""): dict(row) for row in rows}
    for item in editor_rows:
        template_id = str(item.get("Template ID") or "").strip()
        target = by_id.get(template_id)
        if target is None:
            continue
        if prefix == "Inner" and str(target.get("Applicable role") or "") == "Solid":
            target["Inner face bars"] = False
            continue
        method = str(item.get("Method") or target.get(f"{prefix} layout method") or "By target spacing")
        target[f"{prefix} face bars"] = bool(item.get("Use"))
        target[f"{prefix} bar size"] = str(item.get("Bar") or target.get(f"{prefix} bar size") or "DB16")
        target[f"{prefix} layout method"] = method
        target[f"{prefix} center offset mm"] = float(item.get("Offset (mm)") or 1.0)
        value = float(item.get("Target") or 0.0)
        if method == "By exact bar count":
            target[f"{prefix} exact bar count"] = max(int(round(value)), 4)
        else:
            target[f"{prefix} target spacing mm"] = max(value, 1.0)
    return canonical_rebar_templates([by_id[str(row.get("Template ID") or "")] for row in rows])


def _template_action_selection(editor_rows: list[dict[str, Any]], column: str) -> list[str]:
    return [
        str(item.get("Template ID") or "").strip()
        for item in editor_rows
        if bool(item.get(column)) and str(item.get("Template ID") or "").strip()
    ]


def _duplicate_template_ids(
    template_rows: list[dict[str, Any]],
    template_ids: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    rows = canonical_rebar_templates(template_rows)
    created_ids: list[str] = []
    existing_ids = [str(row.get("Template ID") or "") for row in rows]
    for template_id in template_ids:
        source = next((row for row in rows if str(row.get("Template ID") or "") == template_id), None)
        if source is None:
            continue
        created = duplicate_rebar_template(source, existing_ids)
        rows.append(created)
        created_ids.append(str(created.get("Template ID") or ""))
        existing_ids.append(str(created.get("Template ID") or ""))
    return canonical_rebar_templates(rows), created_ids


def _delete_template_ids(
    template_rows: list[dict[str, Any]],
    template_ids: list[str],
    zone_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Delete any unassigned templates, including defaults, while preserving references."""

    rows = canonical_rebar_templates(template_rows)
    requested = [template_id for template_id in template_ids if template_id]
    used = {
        str(zone.get("Rebar template") or ""): sorted(
            str(item.get("Zone ID") or "")
            for item in canonical_rebar_zones(zone_rows)
            if str(item.get("Rebar template") or "") == str(zone.get("Rebar template") or "")
        )
        for zone in canonical_rebar_zones(zone_rows)
    }
    errors: list[str] = []
    deletable: list[str] = []
    for template_id in requested:
        if used.get(template_id):
            errors.append(f"{template_id} is assigned to {', '.join(used[template_id])}.")
        else:
            deletable.append(template_id)
    if len(rows) - len(set(deletable)) < 1:
        errors.append("At least one Rebar Template must remain.")
        deletable = []
    if not deletable:
        return rows, [], errors
    deleted_set = set(deletable)
    remaining = [row for row in rows if str(row.get("Template ID") or "") not in deleted_set]
    return canonical_rebar_templates(remaining), sorted(deleted_set), errors


def _store_template_rows(rows: list[dict[str, Any]]) -> None:
    st.session_state[CB_RB_TEMPLATE_ROWS_KEY] = canonical_rebar_templates(rows)


def _bump_template_editor_revision() -> None:
    st.session_state[CB_RB_TEMPLATE_REV_KEY] = int(st.session_state.get(CB_RB_TEMPLATE_REV_KEY, 0)) + 1


def _render_template_library(
    template_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    st.markdown("### Rebar Template Library")
    st.caption(
        "Edit default and project templates directly in the compact tables below. Template IDs are editable; any change updates Segment / Zone references atomically."
    )

    rows = canonical_rebar_templates(template_rows)
    revision = int(st.session_state.get(CB_RB_TEMPLATE_REV_KEY, 0))

    new_cols = st.columns([0.18, 0.18, 0.64], gap="small")
    with new_cols[0]:
        if st.button("New Hollow", use_container_width=True, key=f"crossbeam_rb2c_new_hollow_{revision}"):
            created = new_rebar_template("Hollow", [str(row.get("Template ID") or "") for row in rows])
            rows.append(created)
            _store_template_rows(rows)
            _bump_template_editor_revision()
            st.rerun()
    with new_cols[1]:
        if st.button("New Solid", use_container_width=True, key=f"crossbeam_rb2c_new_solid_{revision}"):
            created = new_rebar_template("Solid", [str(row.get("Template ID") or "") for row in rows])
            rows.append(created)
            _store_template_rows(rows)
            _bump_template_editor_revision()
            st.rerun()
    with new_cols[2]:
        st.caption("Default templates are ordinary editable project rows. Deletion is blocked only when a Zone still references the Template ID.")

    st.markdown("#### Template identity and row actions")
    identity_rows = [
        {
            "_Original ID": row["Template ID"],
            "Copy": False,
            "Delete": False,
            "Template ID": row["Template ID"],
            "Template name": row["Template name"],
            "Role": row["Applicable role"],
            "Construction": row["Construction"],
        }
        for row in rows
    ]
    identity_edited = st.data_editor(
        pd.DataFrame(identity_rows),
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key=f"crossbeam_rb2c_identity_editor_{revision}",
        column_config={
            "_Original ID": None,
            "Copy": st.column_config.CheckboxColumn("Copy", width="small"),
            "Delete": st.column_config.CheckboxColumn("Delete", width="small"),
            "Template ID": st.column_config.TextColumn(
                "Template ID",
                help="Editable stable reference. Spaces are converted to hyphens; Zone assignments update automatically.",
                required=True,
                width="medium",
            ),
            "Template name": st.column_config.TextColumn("Template name", required=True, width="large"),
            "Role": st.column_config.SelectboxColumn("Role", options=list(TEMPLATE_ROLE_OPTIONS), required=True, width="small"),
            "Construction": st.column_config.SelectboxColumn("Construction", options=list(TEMPLATE_CONSTRUCTION_OPTIONS), required=True, width="medium"),
        },
    )
    identity_records = _records(identity_edited)
    previous_roles = {str(row.get("Template ID") or ""): str(row.get("Applicable role") or "") for row in rows}
    rows, updated_zones, rename_map, identity_errors = _template_identity_rows_from_editor(
        rows,
        identity_records,
        zone_rows,
    )
    if identity_errors:
        for message in identity_errors:
            st.error(message)
    else:
        if rename_map:
            active_id = str(st.session_state.get(CB_RB_ACTIVE_TEMPLATE_KEY) or "")
            if active_id in rename_map:
                st.session_state[CB_RB_ACTIVE_TEMPLATE_KEY] = rename_map[active_id]
            st.session_state[CB_RB_ZONE_ROWS_KEY] = updated_zones
            st.session_state[CB_RB_ZONE_REV_KEY] = int(st.session_state.get(CB_RB_ZONE_REV_KEY, 0)) + 1
            _store_template_rows(rows)
            _bump_template_editor_revision()
            st.session_state[CB_RB_TEMPLATE_ACTION_KEY] = {
                "action": "notice",
                "message": "Updated Template ID references: "
                + ", ".join(f"{old} → {new}" for old, new in rename_map.items())
                + ".",
            }
            st.rerun()
    _store_template_rows(rows)
    role_changed = any(
        previous_roles.get(str(row.get("Template ID") or "")) != str(row.get("Applicable role") or "")
        for row in rows
    )
    if role_changed:
        _bump_template_editor_revision()
        st.rerun()

    copy_ids = _template_action_selection(identity_records, "Copy")
    delete_ids = _template_action_selection(identity_records, "Delete")
    action_cols = st.columns([0.18, 0.18, 0.18, 0.46], gap="small")
    with action_cols[0]:
        if st.button(
            f"Duplicate checked ({len(copy_ids)})",
            use_container_width=True,
            disabled=not copy_ids,
            key=f"crossbeam_rb2c_duplicate_checked_{revision}",
        ):
            rows, created_ids = _duplicate_template_ids(rows, copy_ids)
            _store_template_rows(rows)
            _bump_template_editor_revision()
            if created_ids:
                st.session_state[CB_RB_ACTIVE_TEMPLATE_KEY] = created_ids[-1]
            st.rerun()
    with action_cols[1]:
        confirm_delete = st.checkbox(
            "Confirm delete",
            disabled=not delete_ids,
            key=f"crossbeam_rb2c_confirm_delete_{revision}",
        )
    with action_cols[2]:
        if st.button(
            f"Delete checked ({len(delete_ids)})",
            use_container_width=True,
            disabled=not delete_ids or not confirm_delete,
            key=f"crossbeam_rb2c_delete_checked_{revision}",
        ):
            remaining, deleted, errors = _delete_template_ids(rows, delete_ids, zone_rows)
            if errors:
                st.session_state[CB_RB_TEMPLATE_ACTION_KEY] = {"action": "notice", "message": " ".join(errors)}
            else:
                _store_template_rows(remaining)
                _bump_template_editor_revision()
                st.session_state[CB_RB_TEMPLATE_ACTION_KEY] = {
                    "action": "notice",
                    "message": "Deleted " + ", ".join(deleted) + ".",
                }
            st.rerun()
    with action_cols[3]:
        notice = st.session_state.pop(CB_RB_TEMPLATE_ACTION_KEY, None)
        if isinstance(notice, Mapping) and str(notice.get("action") or "") == "notice":
            message = str(notice.get("message") or "")
            if message.startswith("Deleted"):
                st.success(message)
            elif message:
                st.warning(message)
        elif delete_ids:
            st.caption("Assigned templates remain protected; reassign their Zones before deletion.")
        else:
            st.caption("Tick Copy or Delete in the table, then use the matching action button.")

    st.markdown("#### Participation and material")
    participation_rows = [
        {
            "Template ID": row["Template ID"],
            "Basis": row["Longitudinal basis"],
            "fy (MPa)": int(round(float(row["fy MPa"]))),
            "Material": row["Rebar material"],
            "Active": row["Active"],
            "Credit": row["Credit inside segment"],
        }
        for row in rows
    ]
    participation_edited = st.data_editor(
        pd.DataFrame(participation_rows),
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key=f"crossbeam_rb2c_participation_editor_{revision}",
        disabled=["Template ID"],
        column_config={
            "Template ID": st.column_config.TextColumn(width="small"),
            "Basis": st.column_config.SelectboxColumn(options=list(TEMPLATE_LONGITUDINAL_BASIS_OPTIONS), required=True, width="medium"),
            "fy (MPa)": st.column_config.SelectboxColumn(
                options=[int(value) for value in TEMPLATE_FY_OPTIONS],
                required=True,
                width="small",
            ),
            "Material": st.column_config.SelectboxColumn(
                options=list(TEMPLATE_MATERIAL_OPTIONS),
                required=True,
                width="small",
            ),
            "Active": st.column_config.CheckboxColumn(width="small"),
            "Credit": st.column_config.CheckboxColumn("Credit in zone", width="small"),
        },
    )
    participation_records = _records(participation_edited)
    rows, material_warnings = _template_material_rows_from_editor(rows, participation_records)
    _store_template_rows(rows)
    # A linked change updates canonical state immediately, then refreshes the
    # data-editor key once so the companion dropdown is visibly synchronized.
    if _material_editor_sync_required(participation_records, rows):
        _bump_template_editor_revision()
        st.rerun()
    for message in material_warnings:
        st.warning(message)

    st.markdown("#### Outer-face auto layout")
    st.caption("Target means spacing in mm for **By target spacing**, or total perimeter bar count for **By exact bar count**.")
    outer_rows = []
    for row in rows:
        method = str(row.get("Outer layout method") or "By target spacing")
        outer_rows.append(
            {
                "Template ID": row["Template ID"],
                "Use": row["Outer face bars"],
                "Bar": row["Outer bar size"],
                "Method": method,
                "Offset (mm)": row["Outer center offset mm"],
                "Target": row["Outer exact bar count"] if method == "By exact bar count" else row["Outer target spacing mm"],
            }
        )
    outer_edited = st.data_editor(
        pd.DataFrame(outer_rows),
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key=f"crossbeam_rb2c_outer_editor_{revision}",
        disabled=["Template ID"],
        column_config={
            "Template ID": st.column_config.TextColumn(width="small"),
            "Use": st.column_config.CheckboxColumn(width="small"),
            "Bar": st.column_config.SelectboxColumn(options=list(TEMPLATE_BAR_SIZE_OPTIONS), required=True, width="small"),
            "Method": st.column_config.SelectboxColumn(options=list(TEMPLATE_LAYOUT_METHOD_OPTIONS), required=True, width="medium"),
            "Offset (mm)": st.column_config.NumberColumn(min_value=1.0, step=5.0, format="%.0f", width="small"),
            "Target": st.column_config.NumberColumn(min_value=1.0, step=1.0, format="%.0f", width="small"),
        },
    )
    rows = _template_face_layout_from_editor(rows, _records(outer_edited), face="Outer")
    _store_template_rows(rows)

    hollow_rows = [row for row in rows if str(row.get("Applicable role") or "") in {"Hollow", "Any"}]
    if hollow_rows:
        st.markdown("#### Inner-face auto layout — Hollow / Any templates")
        inner_rows = []
        for row in hollow_rows:
            method = str(row.get("Inner layout method") or "By target spacing")
            inner_rows.append(
                {
                    "Template ID": row["Template ID"],
                    "Use": row["Inner face bars"],
                    "Bar": row["Inner bar size"],
                    "Method": method,
                    "Offset (mm)": row["Inner center offset mm"],
                    "Target": row["Inner exact bar count"] if method == "By exact bar count" else row["Inner target spacing mm"],
                }
            )
        inner_edited = st.data_editor(
            pd.DataFrame(inner_rows),
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key=f"crossbeam_rb2c_inner_editor_{revision}",
            disabled=["Template ID"],
            column_config={
                "Template ID": st.column_config.TextColumn(width="small"),
                "Use": st.column_config.CheckboxColumn(width="small"),
                "Bar": st.column_config.SelectboxColumn(options=list(TEMPLATE_BAR_SIZE_OPTIONS), required=True, width="small"),
                "Method": st.column_config.SelectboxColumn(options=list(TEMPLATE_LAYOUT_METHOD_OPTIONS), required=True, width="medium"),
                "Offset (mm)": st.column_config.NumberColumn(min_value=1.0, step=5.0, format="%.0f", width="small"),
                "Target": st.column_config.NumberColumn(min_value=1.0, step=1.0, format="%.0f", width="small"),
            },
        )
        rows = _template_face_layout_from_editor(rows, _records(inner_edited), face="Inner")
        _store_template_rows(rows)

    with st.expander("Adopted provided reinforcement — optional / future solver handoff", expanded=False):
        adopted_rows = [
            {
                "Template ID": row["Template ID"],
                "Top As (mm²)": row["Top As mm²"],
                "Bottom As (mm²)": row["Bottom As mm²"],
                "Side As (mm²)": row["Side As mm²"],
                "Av/s (mm²/mm)": row["Av/s mm²/mm"],
            }
            for row in rows
        ]
        adopted_edited = st.data_editor(
            pd.DataFrame(adopted_rows),
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key=f"crossbeam_rb2c_adopted_editor_{revision}",
            disabled=["Template ID"],
            column_config={
                "Template ID": st.column_config.TextColumn(width="small"),
                "Top As (mm²)": st.column_config.NumberColumn(min_value=0.0, step=100.0, format="%.0f", width="medium"),
                "Bottom As (mm²)": st.column_config.NumberColumn(min_value=0.0, step=100.0, format="%.0f", width="medium"),
                "Side As (mm²)": st.column_config.NumberColumn(min_value=0.0, step=100.0, format="%.0f", width="medium"),
                "Av/s (mm²/mm)": st.column_config.NumberColumn(min_value=0.0, step=0.01, format="%.4f", width="medium"),
            },
        )
        rows = _template_rows_from_editor(
            rows,
            _records(adopted_edited),
            {
                "Top As (mm²)": "Top As mm²",
                "Bottom As (mm²)": "Bottom As mm²",
                "Side As (mm²)": "Side As mm²",
                "Av/s (mm²/mm)": "Av/s mm²/mm",
            },
        )
        _store_template_rows(rows)

    with st.expander("Template notes and library reset", expanded=False):
        notes_rows = [{"Template ID": row["Template ID"], "Notes": row["Notes"]} for row in rows]
        notes_edited = st.data_editor(
            pd.DataFrame(notes_rows),
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key=f"crossbeam_rb2c_notes_editor_{revision}",
            disabled=["Template ID"],
            column_config={
                "Template ID": st.column_config.TextColumn(width="small"),
                "Notes": st.column_config.TextColumn(width="large"),
            },
        )
        rows = _template_rows_from_editor(rows, _records(notes_edited), {"Notes": "Notes"})
        _store_template_rows(rows)
        st.warning("Reset replaces the current project Template Library with the three editable Crossbeam defaults. Review Zone assignments afterward.")
        reset_confirmed = st.checkbox("Confirm reset of all Rebar Templates", key=f"crossbeam_rb2c_reset_confirm_{revision}")
        if st.button(
            "Reset to Crossbeam defaults",
            type="secondary",
            disabled=not reset_confirmed,
            key=f"crossbeam_rb2c_reset_templates_{revision}",
        ):
            _store_template_rows(default_crossbeam_rebar_templates())
            _bump_template_editor_revision()
            st.rerun()

    duplicate_ids = sorted(
        template_id
        for template_id in {str(row.get("Template ID") or "") for row in rows}
        if template_id and sum(str(item.get("Template ID") or "") == template_id for item in rows) > 1
    )
    duplicate_names = sorted(
        name
        for name in {str(row.get("Template name") or "") for row in rows}
        if name and sum(str(item.get("Template name") or "") == name for item in rows) > 1
    )
    if duplicate_ids:
        st.error("Duplicate Rebar Template IDs: " + ", ".join(duplicate_ids))
    if duplicate_names:
        st.warning("Duplicate Template names may be confusing in Zone assignment: " + ", ".join(duplicate_names))
    return canonical_rebar_templates(rows)

def _render_zone_assignment(
    segment_rows: list[dict[str, Any]],
    template_rows: list[dict[str, Any]],
    transverse_template_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    st.markdown("### Segment / Zone Assignment")
    st.caption(
        "Segment Layout is the geometry source of truth. Zone geometry and reinforcement assignment are separated into compact tables so every column remains visible without horizontal scrolling."
    )
    # Legacy compact-column contract retained for regression traceability:
    # "Zone", "Segment", "Start", "End", "Section", "Template"

    current_signature = segment_signature(segment_rows)
    stored_signature = st.session_state.get(CB_RB_SEGMENT_SIGNATURE_KEY)
    layout_changed = stored_signature is not None and tuple(stored_signature) != current_signature
    if layout_changed:
        st.warning(
            "Segment Layout changed after the rebar-zone map was created. Review station limits or reset the zone map; custom edits are not overwritten automatically."
        )

    if st.button("Reset rebar zones from Segment Layout", key="crossbeam_rb1_reset_zones"):
        st.session_state[CB_RB_ZONE_ROWS_KEY] = default_crossbeam_rebar_zones(
            segment_rows,
            template_rows,
            transverse_template_rows,
        )
        st.session_state[CB_RB_SEGMENT_SIGNATURE_KEY] = current_signature
        st.session_state[CB_RB_ZONE_REV_KEY] = int(st.session_state.get(CB_RB_ZONE_REV_KEY, 0)) + 1
        st.rerun()

    longitudinal_ids = list(template_map(template_rows)) or [""]
    transverse_ids = list(transverse_template_map(transverse_template_rows)) or [""]
    segment_ids = [str(row.get("Segment") or "") for row in segment_rows] or [""]
    segment_by_id = {str(row.get("Segment") or ""): row for row in segment_rows}
    old_rows = canonical_rebar_zones(zone_rows)
    old_purpose = {str(row.get("Zone ID") or ""): str(row.get("Purpose") or "") for row in old_rows}
    old_assignment = {
        str(row.get("Zone ID") or ""): {
            "Longitudinal": str(row.get("Longitudinal template") or row.get("Rebar template") or ""),
            "Transverse": str(row.get("Transverse template") or ""),
        }
        for row in old_rows
    }

    geometry_rows: list[dict[str, Any]] = []
    for row in old_rows:
        segment = segment_by_id.get(str(row.get("Segment") or ""), {})
        geometry_rows.append(
            {
                "Zone": row.get("Zone ID", ""),
                "Segment": row.get("Segment", ""),
                "Start": row.get("s_start_m", 0.0),
                "End": row.get("s_end_m", 0.0),
                "Section": f"{segment.get('Section ID', '')} · {segment.get('Section name') or segment.get('Section role', '')} · {segment.get('Section role', '')}",
            }
        )

    revision = int(st.session_state.get(CB_RB_ZONE_REV_KEY, 0))
    st.markdown("#### Zone geometry")
    geometry_edited = st.data_editor(
        pd.DataFrame(geometry_rows, columns=["Zone", "Segment", "Start", "End", "Section"]),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"crossbeam_tr1_zone_geometry_{revision}",
        disabled=["Section"],
        column_config={
            "Zone": st.column_config.TextColumn("Zone", required=True, width="small"),
            "Segment": st.column_config.SelectboxColumn("Segment", options=segment_ids, required=True, width="small"),
            "Start": st.column_config.NumberColumn("s start (m)", min_value=0.0, format="%.3f", required=True, width="small"),
            "End": st.column_config.NumberColumn("s end (m)", min_value=0.0, format="%.3f", required=True, width="small"),
            "Section": st.column_config.TextColumn("Section ID · name · role", width="large"),
        },
    )
    geometry_records = _records(geometry_edited)

    longitudinal_by_id = template_map(template_rows)
    transverse_by_id = transverse_template_map(transverse_template_rows)
    assignment_seed: list[dict[str, Any]] = []
    for item in geometry_records:
        zone_id = str(item.get("Zone") or "").strip()
        segment_id = str(item.get("Segment") or "").strip()
        segment = segment_by_id.get(segment_id, {})
        role = str(segment.get("Section role") or "")
        old = old_assignment.get(zone_id, {})
        longitudinal_id = old.get("Longitudinal") or (longitudinal_ids[0] if longitudinal_ids else "")
        transverse_id = old.get("Transverse") or (transverse_ids[0] if transverse_ids else "")
        longitudinal_role = str(longitudinal_by_id.get(longitudinal_id, {}).get("Applicable role") or "")
        transverse_role = str(transverse_by_id.get(transverse_id, {}).get("Applicable role") or "")
        compatible = (
            longitudinal_role in {role, "Any"}
            and transverse_role in {role, "Any"}
            and bool(longitudinal_id)
            and bool(transverse_id)
        )
        assignment_seed.append(
            {
                "Zone": zone_id,
                "Longitudinal template": longitudinal_id,
                "Transverse template": transverse_id,
                "Compatibility": role or "—",
                "Status": "READY" if compatible else "REVIEW",
            }
        )

    st.markdown("#### Reinforcement assignment")
    assignment_edited = st.data_editor(
        pd.DataFrame(
            assignment_seed,
            columns=["Zone", "Longitudinal template", "Transverse template", "Compatibility", "Status"],
        ),
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        key=f"crossbeam_tr1_zone_assignment_{revision}",
        disabled=["Zone", "Compatibility", "Status"],
        column_config={
            "Zone": st.column_config.TextColumn(width="small"),
            "Longitudinal template": st.column_config.SelectboxColumn(options=longitudinal_ids, required=True, width="large"),
            "Transverse template": st.column_config.SelectboxColumn(options=transverse_ids, required=True, width="large"),
            "Compatibility": st.column_config.TextColumn("Section role", width="small"),
            "Status": st.column_config.TextColumn(width="small"),
        },
    )
    assignment_records = {str(row.get("Zone") or ""): row for row in _records(assignment_edited)}

    candidate_rows: list[dict[str, Any]] = []
    for item in geometry_records:
        zone_id = str(item.get("Zone") or "").strip()
        assigned = assignment_records.get(zone_id, {})
        longitudinal_id = str(assigned.get("Longitudinal template") or "").strip()
        candidate_rows.append(
            {
                "Zone ID": zone_id,
                "Segment": str(item.get("Segment") or "").strip(),
                "s_start_m": float(item.get("Start") or 0.0),
                "s_end_m": float(item.get("End") or 0.0),
                "Rebar template": longitudinal_id,
                "Longitudinal template": longitudinal_id,
                "Transverse template": str(assigned.get("Transverse template") or "").strip(),
                "Purpose": old_purpose.get(zone_id, ""),
            }
        )
    rows, errors, warnings = validate_rebar_zones(
        candidate_rows,
        segment_rows,
        template_rows,
        transverse_template_rows,
    )

    if rows:
        zone_ids = [str(row.get("Zone ID") or "") for row in rows]
        selected_zone = st.selectbox(
            "Zone note to edit",
            options=zone_ids,
            key="crossbeam_rb2a_zone_note_selector",
            help="Purpose is edited separately so the main tables remain compact and fully visible.",
        )
        selected_row = next(row for row in rows if str(row.get("Zone ID") or "") == selected_zone)
        selected_row["Purpose"] = st.text_input(
            "Purpose / engineering note",
            value=str(selected_row.get("Purpose") or ""),
            key=f"{CB_RB_ZONE_PURPOSE_KEY_PREFIX}_{selected_zone}",
        )

    st.session_state[CB_RB_ZONE_ROWS_KEY] = rows
    if not errors:
        st.session_state[CB_RB_SEGMENT_SIGNATURE_KEY] = current_signature
    return rows, errors, warnings


def _set_rb2_subview(value: str) -> None:
    st.session_state[CB_RB_SUBVIEW_KEY] = str(value)


def _render_rb2_subnavigation() -> str:
    valid = [value for value, _label in RB2_SUBVIEWS]
    current = str(st.session_state.get(CB_RB_SUBVIEW_KEY) or valid[0])
    if current not in valid:
        current = valid[0]
        st.session_state[CB_RB_SUBVIEW_KEY] = current
    columns = st.columns(len(RB2_SUBVIEWS), gap="small")
    for column, (value, label) in zip(columns, RB2_SUBVIEWS):
        with column:
            st.button(
                label,
                use_container_width=True,
                type="primary" if value == current else "secondary",
                key=f"crossbeam_rb2_nav_{value}",
                on_click=_set_rb2_subview,
                args=(value,),
            )
    return str(st.session_state.get(CB_RB_SUBVIEW_KEY) or current)


def _result_rebars(result: PerimeterRebarLayoutResult, *, layer: str) -> list[Rebar]:
    rebars: list[Rebar] = []
    if result.table.empty:
        return rebars
    for row in result.table.to_dict(orient="records"):
        try:
            rebars.append(
                Rebar(
                    x_mm=float(row.get("x_mm", 0.0)),
                    y_mm=float(row.get("y_mm", 0.0)),
                    diameter_mm=float(row.get("Diameter_mm", 0.0)),
                    material_name=str(row.get("Material") or "SD40"),
                    label=f"{layer}: {row.get('Label', '')}",
                )
            )
        except Exception:
            continue
    return rebars


def _generated_area_mm2(rebars: list[Rebar]) -> float:
    return float(sum(bar.area_mm2 for bar in rebars))


def _section_rebar_preview_figure(
    geometry: Any,
    *,
    outer_rebars: list[Rebar],
    inner_rebars: list[Rebar],
    title: str,
    marker_mode: str = "Enhanced markers",
) -> go.Figure:
    fig = create_section_preview(geometry)
    enhanced = str(marker_mode) != "True bar diameter"
    layer_specs = [
        ("Outer-face bars", outer_rebars, "#155a9c"),
        ("Inner-face bars", inner_rebars, "#2f7d4a"),
    ]
    for layer_name, bars, color in layer_specs:
        if not bars:
            continue
        if not enhanced:
            for bar in bars:
                radius = max(float(bar.diameter_mm), 0.0) / 2.0
                fig.add_shape(
                    type="circle", xref="x", yref="y",
                    x0=bar.x_mm - radius, x1=bar.x_mm + radius,
                    y0=bar.y_mm - radius, y1=bar.y_mm + radius,
                    fillcolor=color, opacity=0.82, line={"color": "#ffffff", "width": 0.8}, layer="above",
                )
        fig.add_trace(
            go.Scatter(
                x=[bar.x_mm for bar in bars],
                y=[bar.y_mm for bar in bars],
                mode="markers",
                marker={
                    "size": 10 if enhanced else 5,
                    "color": color,
                    "opacity": 0.92 if enhanced else 0.45,
                    "line": {"color": "#ffffff", "width": 0.8},
                },
                text=[
                    f"{bar.label or layer_name}<br>x={bar.x_mm:.1f} mm<br>y={bar.y_mm:.1f} mm<br>"
                    f"D={bar.diameter_mm:.0f} mm<br>As={bar.area_mm2:.1f} mm²"
                    for bar in bars
                ],
                hoverinfo="text",
                name=layer_name,
            )
        )
    fig.update_layout(
        title={"text": title, "x": 0.5, "xanchor": "center", "font": {"size": 16, "color": "#071a33"}},
        height=500,
        margin={"l": 35, "r": 25, "t": 75, "b": 40},
    )
    return fig

def _layout_result_messages(result: PerimeterRebarLayoutResult, label: str) -> None:
    for message in result.errors:
        st.error(f"{label}: {message}")
    for message in result.warnings:
        st.warning(f"{label}: {message}")
    for message in result.info:
        st.caption(f"{label}: {message}")


def _render_section_rebar_preview(
    segment_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
    template_rows: list[dict[str, Any]],
    transverse_template_rows: list[dict[str, Any]],
) -> None:
    render_section_bar(
        "Segment-specific reinforcement preview",
        "Select one Segment/Zone, then review Longitudinal, Transverse / Shear, or Combined local reinforcement. All views terminate at segment boundaries and remain disconnected from ULS/SLS solvers.",
        mark="SEC",
    )
    if not segment_rows:
        st.warning("Create a valid Segment Layout before reviewing section reinforcement.")
        return

    segment_by_id = {str(row.get("Segment") or ""): row for row in segment_rows}
    segment_ids = list(segment_by_id)
    current_segment = str(st.session_state.get(CB_RB_PREVIEW_SEGMENT_KEY) or segment_ids[0])
    if current_segment not in segment_ids:
        st.session_state[CB_RB_PREVIEW_SEGMENT_KEY] = segment_ids[0]
    selected_segment_id = st.selectbox(
        "Segment to preview",
        options=segment_ids,
        format_func=lambda value: (
            f"{value} · {segment_by_id[value].get('Section ID', '')} · "
            f"{segment_by_id[value].get('Section name') or segment_by_id[value].get('Section role', '')}"
        ),
        key=CB_RB_PREVIEW_SEGMENT_KEY,
    )
    selected_segment = segment_by_id[selected_segment_id]
    candidate_zones = [row for row in canonical_rebar_zones(zone_rows) if row.get("Segment") == selected_segment_id]
    if not candidate_zones:
        st.error(f"{selected_segment_id} has no assigned reinforcement zone.")
        return
    zone_ids = [str(row.get("Zone ID") or "") for row in candidate_zones]
    current_zone = str(st.session_state.get(CB_RB_PREVIEW_ZONE_KEY) or zone_ids[0])
    if current_zone not in zone_ids:
        st.session_state[CB_RB_PREVIEW_ZONE_KEY] = zone_ids[0]
    selected_zone_id = st.selectbox("Zone to preview", options=zone_ids, key=CB_RB_PREVIEW_ZONE_KEY)
    selected_zone = next(row for row in candidate_zones if str(row.get("Zone ID") or "") == selected_zone_id)

    definitions = canonical_section_definitions(st.session_state.get(CB_SECLIB_DEFINITIONS_KEY, []))
    section_id = str(selected_segment.get("Section ID") or "")
    definition = definition_map(definitions).get(section_id)
    if definition is None:
        st.error(f"Section ID {section_id or '(blank)'} is unavailable. Repair the Section Builder / Segment Layout assignment.")
        return
    try:
        geometry = build_geometry_for_definition(definition)
    except Exception as exc:
        st.error(f"Unable to build {section_id}: {exc}")
        return

    role = str(definition.get("Section role") or selected_segment.get("Section role") or "Solid")
    longitudinal_id = str(selected_zone.get("Longitudinal template") or selected_zone.get("Rebar template") or "")
    longitudinal = template_map(template_rows).get(longitudinal_id)
    transverse_id = str(selected_zone.get("Transverse template") or "")
    transverse = transverse_template_map(transverse_template_rows).get(transverse_id)
    if longitudinal is None:
        st.error(f"Longitudinal template {longitudinal_id or '(blank)'} is not active or does not exist.")
        return
    if transverse is None:
        st.error(f"Transverse template {transverse_id or '(blank)'} is not active or does not exist.")
        return
    for label, template in (("Longitudinal", longitudinal), ("Transverse", transverse)):
        applicable_role = str(template.get("Applicable role") or "Any")
        if applicable_role not in {"Any", role}:
            st.error(f"{label} template {template.get('Template ID')} is for {applicable_role}, but Section ID {section_id} is {role}.")
            return

    preview_mode = st.radio(
        "Preview mode",
        options=["Longitudinal", "Transverse / Shear", "Combined review"],
        horizontal=True,
        key="crossbeam_tr1_preview_mode",
    )

    if preview_mode in {"Longitudinal", "Combined review"}:
        template = longitudinal
        material = str(template.get("Rebar material") or "SD40")
        outer_result = PerimeterRebarLayoutResult(table=pd.DataFrame())
        if bool(template.get("Outer face bars")):
            outer_size = str(template.get("Outer bar size") or "DB16")
            outer_result = generate_perimeter_rebar_layout(
                geometry, bar_size=outer_size, diameter_mm=rebar_diameter_mm(outer_size), material=material,
                edge_offset_mm=float(template.get("Outer center offset mm") or 50.0),
                target_spacing_mm=float(template.get("Outer target spacing mm") or 150.0), min_bars=4,
                exact_bar_count=(int(template.get("Outer exact bar count") or 0) if str(template.get("Outer layout method")) == "By exact bar count" else None),
                label_prefix="O",
            )
        inner_result = PerimeterRebarLayoutResult(table=pd.DataFrame())
        if role == "Hollow" and bool(template.get("Inner face bars")):
            inner_size = str(template.get("Inner bar size") or "DB16")
            inner_result = generate_inner_face_rebar_layout(
                geometry, hole_index=0, bar_size=inner_size, diameter_mm=rebar_diameter_mm(inner_size), material=material,
                edge_offset_mm=float(template.get("Inner center offset mm") or 50.0),
                target_spacing_mm=float(template.get("Inner target spacing mm") or 150.0), min_bars=4,
                exact_bar_count=(int(template.get("Inner exact bar count") or 0) if str(template.get("Inner layout method")) == "By exact bar count" else None),
                label_prefix="I",
            )
        outer_rebars = _result_rebars(outer_result, layer="Outer") if outer_result.ok else []
        inner_rebars = _result_rebars(inner_result, layer="Inner") if inner_result.ok else []
        total_rebars = outer_rebars + inner_rebars
        total_area = _generated_area_mm2(total_rebars)
        adopted = _adopted_reinforcement_summary(template)
        metric_status = "ready" if total_rebars and not outer_result.errors and not inner_result.errors else "warning"
        render_metric_cards(
            [
                {"title":"Selected section","value":section_id,"detail":f"{definition.get('Section name','')} · {role}","status":"info"},
                {"title":"Longitudinal template","value":longitudinal_id,"detail":f"{selected_zone_id} · s={float(selected_zone['s_start_m']):.3f}–{float(selected_zone['s_end_m']):.3f} m","status":"info"},
                {"title":"Auto-generated layout","value":f"{len(total_rebars)} bars","detail":f"As {total_area:,.0f} mm² · Outer {len(outer_rebars)} · Inner {len(inner_rebars)}","status":metric_status},
                {"title":"Adopted reinforcement","value":"DEFINED" if _template_quantity_defined(template) else "NOT ADOPTED","detail":adopted,"status":"ready" if _template_quantity_defined(template) else "warning"},
            ]
        )
        marker_mode = st.radio(
            "Bar display",
            options=["Enhanced markers", "True bar diameter"],
            horizontal=True,
            key=CB_RB_PREVIEW_MARKER_MODE_KEY,
            help="Enhanced markers improve visual review only. Quantities and As always use the true bar diameter.",
        )
        st.plotly_chart(
            _section_rebar_preview_figure(
                geometry,
                outer_rebars=outer_rebars,
                inner_rebars=inner_rebars,
                title=f"Longitudinal Bar-Location Preview — {selected_segment_id} / {selected_zone_id} · {section_id} · {longitudinal_id}",
                marker_mode=marker_mode,
            ),
            use_container_width=True,
            config=FIGURE_CONFIG,
        )
        st.caption("Longitudinal bar-location preview only. Transverse cages/ties and shear reinforcement are shown in the Transverse / Shear view.")
        _layout_result_messages(outer_result, "Outer layout")
        if role == "Hollow" and bool(template.get("Inner face bars")):
            _layout_result_messages(inner_result, "Inner layout")

    if preview_mode in {"Transverse / Shear", "Combined review"}:
        render_transverse_preview_summary(
            geometry,
            definition,
            transverse,
            segment_id=selected_segment_id,
            zone_id=selected_zone_id,
            start_m=float(selected_zone["s_start_m"]),
            end_m=float(selected_zone["s_end_m"]),
            segment_rows=segment_rows,
            zone_rows=zone_rows,
            transverse_template_rows=transverse_template_rows,
            figure_config=FIGURE_CONFIG,
        )

    st.warning(
        "JOINT GUARD — Longitudinal ordinary rebar crossing each segment joint is 0 mm². Transverse reinforcement is local to the selected Segment/Zone and receives no automatic joint-shear credit. PT continuity remains required but unverified."
    )


def render_crossbeam_rebar_page() -> None:
    length_m, segment_rows, segment_errors = crossbeam_segment_layout_from_state()
    _ensure_rb1_state(segment_rows)

    ordinary_enabled = ordinary_rebar_enabled(st.session_state, default=True)
    tendon_enabled = prestressing_steel_enabled(st.session_state, default=True)

    render_page_header(
        "Crossbeam Rebar",
        "Define segment-local and zone-local ordinary reinforcement, review each assigned section graphically, and guard every joint until post-tensioning continuity is explicitly verified.",
        icon="RB",
        kicker="Sections workspace",
        badge="Portal Frame Crossbeam",
        accent="green",
    )

    template_rows = canonical_rebar_templates(
        _records(st.session_state.get(CB_RB_TEMPLATE_ROWS_KEY)) or default_crossbeam_rebar_templates()
    )
    transverse_template_rows = canonical_transverse_templates(
        _records(st.session_state.get(CB_TR_TEMPLATE_ROWS_KEY)) or default_crossbeam_transverse_templates()
    )
    zone_rows = canonical_rebar_zones(
        _records(st.session_state.get(CB_RB_ZONE_ROWS_KEY))
        or default_crossbeam_rebar_zones(segment_rows, template_rows, transverse_template_rows)
    )
    active_templates = template_map(template_rows)
    active_transverse_templates = transverse_template_map(transverse_template_rows)

    render_metric_cards(
        [
            {
                "title": "Rebar model",
                "value": "Segment / zone based" if ordinary_enabled else "Disabled",
                "detail": "Independent longitudinal and transverse templates; generic global tables are not used",
                "status": "ready" if ordinary_enabled else "warning",
            },
            {
                "title": "Joint ordinary rebar",
                "value": "0 mm² — LOCKED",
                "detail": "No ordinary reinforcing bar crosses a segment joint",
                "status": "warning",
            },
            {
                "title": "PT continuity",
                "value": "REQUIRED — NOT VERIFIED" if tendon_enabled else "BLOCKED — PRESTRESS DISABLED",
                "detail": "Future Tendon System/Profile audit must verify active tendon geometry and Aps at each joint",
                "status": "warning",
            },
            {
                "title": "Solver handoff",
                "value": "NOT CONNECTED",
                "detail": "Input/review foundation only; existing solvers are unchanged",
                "status": "neutral",
            },
        ]
    )

    if segment_errors:
        st.error("Segment Layout is not ready. Correct Segment Layout before accepting rebar-zone assignments.")
        for error in segment_errors:
            st.caption(error)
    if not tendon_enabled:
        st.error("Prestressing steel is disabled. Joint continuity is BLOCKED because ordinary rebar crossing is locked to zero and PT continuity cannot be verified.")
    if not ordinary_enabled:
        st.warning("Ordinary rebar is disabled in Section Builder. Stored RB1 templates/zones are excluded from future analysis until re-enabled.")

    _render_locked_joint_rule()

    active_view = _render_rb2_subnavigation()

    if active_view == "Templates":
        template_rows = _render_template_library(template_rows, zone_rows)
        active_templates = template_map(template_rows)
        quantity_defined = sum(_template_quantity_defined(row) for row in active_templates.values())
        render_metric_cards(
            [
                {"title": "Active templates", "value": len(active_templates), "detail": "Longitudinal template IDs", "status": "info"},
                {
                    "title": "Quantities defined",
                    "value": f"{quantity_defined} / {len(active_templates)}",
                    "detail": "At least one adopted longitudinal As or Av/s value entered",
                    "status": "ready" if active_templates and quantity_defined == len(active_templates) else "warning",
                },
                {"title": "Joint crossing credit", "value": "0 mm²", "detail": "Locked independently of template inputs", "status": "warning"},
            ]
        )

    elif active_view == "Transverse / Shear":
        transverse_template_rows = render_crossbeam_transverse_template_library(
            transverse_template_rows,
            zone_rows,
        )
        active_transverse_templates = transverse_template_map(transverse_template_rows)
        render_metric_cards(
            [
                {"title":"Active transverse templates","value":len(active_transverse_templates),"detail":"Hollow web cages and Solid multi-leg ties","status":"info"},
                {"title":"Zone assignment","value":sum(bool(row.get("Transverse template")) for row in zone_rows),"detail":"Local Segment/Zone references","status":"ready" if zone_rows and all(row.get("Transverse template") for row in zone_rows) else "warning"},
                {"title":"Joint shear credit","value":"NONE","detail":"Transverse bars terminate inside each Segment/Zone","status":"warning"},
            ]
        )

    elif active_view == "Segment / Zone":
        zone_rows, errors, warnings = _render_zone_assignment(
            segment_rows,
            template_rows,
            transverse_template_rows,
            zone_rows,
        )
        render_metric_cards(
            [
                {
                    "title": "Zone layout status",
                    "value": "LAYOUT READY" if not errors and not segment_errors else "LAYOUT REQUIRED",
                    "detail": "Editable input map; not a solver result",
                    "status": "ready" if not errors and not segment_errors else "warning",
                },
                {"title": "Rebar zones", "value": len(zone_rows), "detail": "Segment-bounded station ranges", "status": "info"},
                {"title": "Segments", "value": len(segment_rows), "detail": f"Extent 0–{length_m:.3f} m", "status": "neutral"},
                {"title": "Joint rule", "value": "LOCKED", "detail": "No ordinary rebar across segment joints", "status": "warning"},
            ]
        )
        for error in errors:
            st.error(error)
        if warnings:
            st.warning(
                f"{len(warnings)} active longitudinal template(s) require adopted provided reinforcement: "
                + "; ".join(message.split(":", 1)[0] for message in warnings)
                + ". Open Longitudinal → Adopted provided reinforcement to enter project values."
            )
        st.plotly_chart(
            _rebar_elevation_figure(segment_rows, zone_rows, template_rows, length_m),
            use_container_width=True,
            config=FIGURE_CONFIG,
        )
        st.caption(
            "The rebar lines are schematic template extents only. They intentionally terminate within their assigned segment/zone. "
            "No ordinary rebar is shown or credited across a segment joint. PT continuity is required but remains unverified until Tendon Profile audit is connected."
        )

    elif active_view == "Section Rebar Preview":
        _render_section_rebar_preview(segment_rows, zone_rows, template_rows, transverse_template_rows)

    else:
        render_section_bar(
            "Joint continuity audit",
            "Every segment boundary is generated from Segment Layout and locked to zero ordinary-rebar crossing credit.",
            mark="QA",
        )
        joints = segment_joint_audit_rows(segment_rows)
        if joints:
            joint_table = [
                {
                    "Joint": row["Joint"],
                    "s (m)": row["s (m)"],
                    "Ord. rebar": row["Ordinary rebar crossing joint"],
                    "Transverse": row.get("Transverse joint shear credit", "None — local to segments"),
                    "PT continuity": row.get("Tendon continuity", "REQUIRED — NOT VERIFIED"),
                    "Status": row["Status"],
                }
                for row in joints
            ]
            st.dataframe(
                pd.DataFrame(joint_table), use_container_width=True, hide_index=True,
                column_config={
                    "Joint": st.column_config.TextColumn(width="medium"),
                    "s (m)": st.column_config.NumberColumn(format="%.3f", width="small"),
                    "Ord. rebar": st.column_config.TextColumn(width="medium"),
                    "Transverse": st.column_config.TextColumn(width="medium"),
                    "PT continuity": st.column_config.TextColumn(width="large"),
                    "Status": st.column_config.TextColumn(width="medium"),
                },
            )
        else:
            st.info("No internal segment joint exists in the current Segment Layout.")

        render_section_bar(
            "Calculated active rebar by station",
            "Compact read-only assembly preview. Interior rows show local template credit; joint rows show zero ordinary rebar and unverified PT continuity.",
            mark="s",
        )
        audit_rows = station_rebar_audit_rows(segment_rows, zone_rows, template_rows, transverse_template_rows)
        segment_by_id = {str(row.get("Segment") or ""): row for row in segment_rows}
        compact_audit = []
        for row in audit_rows:
            is_joint = str(row.get("Location type")) == "Segment joint"
            segment = segment_by_id.get(str(row.get("Segment") or ""), {})
            if is_joint:
                section_context = f"{row.get('Segment', '')} · Joint plane"
                rebar_context = "Ord. rebar 0 mm² · PT required/not verified"
            else:
                section_context = (
                    f"{row.get('Segment', '')} · {segment.get('Section ID', '')} · "
                    f"{segment.get('Section name') or row.get('Section role', '')}"
                )
                rebar_context = (
                    f"L: {row.get('Active longitudinal template', row.get('Active template', ''))} · "
                    f"T: {row.get('Active transverse template', '')}"
                )
            compact_audit.append(
                {
                    "Location": row.get("Location", ""),
                    "Type": row.get("Location type", ""),
                    "s (m)": row.get("s (m)", 0.0),
                    "Section / segment": section_context,
                    "Rebar / continuity": rebar_context,
                    "Status": row.get("Status", ""),
                }
            )
        st.dataframe(
            pd.DataFrame(compact_audit), use_container_width=True, hide_index=True,
            column_config={
                "Location": st.column_config.TextColumn(width="small"),
                "Type": st.column_config.TextColumn(width="medium"),
                "s (m)": st.column_config.NumberColumn(format="%.3f", width="small"),
                "Section / segment": st.column_config.TextColumn(width="large"),
                "Rebar / continuity": st.column_config.TextColumn(width="large"),
                "Status": st.column_config.TextColumn(width="medium"),
            },
        )
        st.info(
            "CROSSBEAM.TR1 does not modify ULS/SLS capacity, shear/torsion, Result Summary, Report/QA, or Project JSON. "
            "Longitudinal and transverse templates remain local input/review data. A future Tendon audit must verify active tendon geometry/Aps at each joint before station handoff can claim continuity."
        )
