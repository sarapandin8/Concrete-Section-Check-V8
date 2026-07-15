"""Workflow-scoped Rebar workspace for segmental Portal Frame Crossbeams.

CROSSBEAM.RB2A hardens the RB2 review workspace with compact no-scroll tables,
selected-template editing, separate auto-generated versus adopted reinforcement,
enhanced/true-scale bar display modes, and an explicit unverified PT-continuity
guard. It never routes the new template, zone, or preview state into existing
PMM, Beam/Girder, SLS, shear, torsion, or report solvers.
"""

from __future__ import annotations

from collections.abc import Mapping
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
    canonical_rebar_templates,
    canonical_rebar_zones,
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
    segment_joint_audit_rows,
    segment_signature,
    station_rebar_audit_rows,
    template_map,
    rebar_diameter_mm,
    validate_rebar_zones,
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

RB2_SUBVIEWS = (
    ("Templates", "Templates"),
    ("Segment / Zone", "Segment / Zone"),
    ("Section Rebar Preview", "Section Rebar Preview"),
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
    if CB_RB_TEMPLATE_ROWS_KEY not in st.session_state:
        st.session_state[CB_RB_TEMPLATE_ROWS_KEY] = default_crossbeam_rebar_templates()
    st.session_state.setdefault(CB_RB_TEMPLATE_REV_KEY, 0)

    if CB_RB_ZONE_ROWS_KEY not in st.session_state:
        st.session_state[CB_RB_ZONE_ROWS_KEY] = default_crossbeam_rebar_zones(segment_rows)
        st.session_state[CB_RB_SEGMENT_SIGNATURE_KEY] = segment_signature(segment_rows)
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
        "but CROSSBEAM.RB2A does not yet verify active tendon geometry or Aps at the joint plane."
    )
    st.caption(
        "Joint shear transfer, interface behavior, opening/decompression, shear keys, anchorage zones, solid–hollow transitions, "
        "column D-regions, and tendon-continuity verification remain separate checks."
    )

def _auto_layout_summary(template: Mapping[str, Any]) -> str:
    parts: list[str] = []
    if bool(template.get("Outer face bars")):
        parts.append(
            f"Outer {template.get('Outer bar size', '')}@{float(template.get('Outer target spacing mm') or 0.0):.0f}"
        )
    if bool(template.get("Inner face bars")):
        parts.append(
            f"Inner {template.get('Inner bar size', '')}@{float(template.get('Inner target spacing mm') or 0.0):.0f}"
        )
    return " · ".join(parts) if parts else "Layout OFF"


def _adopted_reinforcement_summary(template: Mapping[str, Any]) -> str:
    top = float(template.get("Top As mm²") or 0.0)
    bottom = float(template.get("Bottom As mm²") or 0.0)
    side = float(template.get("Side As mm²") or 0.0)
    avs = float(template.get("Av/s mm²/mm") or 0.0)
    if not any(value > 0.0 for value in (top, bottom, side, avs)):
        return "Not adopted"
    return f"T/B/S {top:.0f}/{bottom:.0f}/{side:.0f} · Av/s {avs:.4f}"


def _render_template_library(template_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    st.markdown("### Rebar Template Library")
    st.caption(
        "Select one template and edit it below. The summary table is intentionally compact so every column remains visible without horizontal scrolling."
    )
    if st.button("Reset Crossbeam rebar templates", key="crossbeam_rb1_reset_templates"):
        st.session_state[CB_RB_TEMPLATE_ROWS_KEY] = default_crossbeam_rebar_templates()
        st.session_state[CB_RB_TEMPLATE_REV_KEY] = int(st.session_state.get(CB_RB_TEMPLATE_REV_KEY, 0)) + 1
        st.session_state.pop(CB_RB_ACTIVE_TEMPLATE_KEY, None)
        st.rerun()

    rows = canonical_rebar_templates(template_rows)
    template_ids = [str(row.get("Template ID") or "") for row in rows]
    if not template_ids:
        st.warning("No Crossbeam Rebar Template is available. Reset the template library.")
        return rows
    current = str(st.session_state.get(CB_RB_ACTIVE_TEMPLATE_KEY) or template_ids[0])
    if current not in template_ids:
        st.session_state[CB_RB_ACTIVE_TEMPLATE_KEY] = template_ids[0]
    selected_id = st.selectbox(
        "Template to edit",
        options=template_ids,
        format_func=lambda value: f"{value} · {next((row.get('Template name', '') for row in rows if row.get('Template ID') == value), '')}",
        key=CB_RB_ACTIVE_TEMPLATE_KEY,
    )

    summary_rows = [
        {
            "Template": row["Template ID"],
            "Role": row["Applicable role"],
            "Construction": row["Construction"],
            "Auto layout": _auto_layout_summary(row),
            "Adopted reinforcement": _adopted_reinforcement_summary(row),
            "Status": "READY" if row.get("Active") else "INACTIVE",
        }
        for row in rows
    ]
    st.dataframe(
        pd.DataFrame(summary_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Template": st.column_config.TextColumn(width="small"),
            "Role": st.column_config.TextColumn(width="small"),
            "Construction": st.column_config.TextColumn(width="medium"),
            "Auto layout": st.column_config.TextColumn(width="medium"),
            "Adopted reinforcement": st.column_config.TextColumn(width="medium"),
            "Status": st.column_config.TextColumn(width="small"),
        },
    )

    index = template_ids.index(selected_id)
    selected = dict(rows[index])
    st.markdown(f"#### Edit Selected Template — `{selected_id}`")
    st.caption(str(selected.get("Template name") or selected_id))

    identity_1, identity_2, identity_3 = st.columns([0.46, 0.24, 0.30], gap="medium")
    with identity_1:
        selected["Template name"] = st.text_input(
            "Template name",
            value=str(selected.get("Template name") or ""),
            key=f"crossbeam_rb2a_template_name_{selected_id}",
        )
    with identity_2:
        selected["Applicable role"] = st.selectbox(
            "Applicable role",
            options=list(TEMPLATE_ROLE_OPTIONS),
            index=list(TEMPLATE_ROLE_OPTIONS).index(str(selected.get("Applicable role") or "Any")),
            key=f"crossbeam_rb2a_template_role_{selected_id}",
        )
    with identity_3:
        selected["Construction"] = st.selectbox(
            "Construction",
            options=list(TEMPLATE_CONSTRUCTION_OPTIONS),
            index=list(TEMPLATE_CONSTRUCTION_OPTIONS).index(str(selected.get("Construction") or "Project-defined")),
            key=f"crossbeam_rb2a_template_construction_{selected_id}",
        )

    identity_4, identity_5, identity_6, identity_7 = st.columns(4, gap="medium")
    with identity_4:
        selected["Longitudinal basis"] = st.selectbox(
            "Longitudinal basis",
            options=list(TEMPLATE_LONGITUDINAL_BASIS_OPTIONS),
            index=list(TEMPLATE_LONGITUDINAL_BASIS_OPTIONS).index(str(selected.get("Longitudinal basis") or "Segment-local")),
            key=f"crossbeam_rb2a_template_basis_{selected_id}",
        )
    with identity_5:
        selected["fy MPa"] = st.number_input(
            "fy (MPa)", min_value=0.0, value=float(selected.get("fy MPa") or 390.0), step=10.0,
            key=f"crossbeam_rb2a_template_fy_{selected_id}",
        )
    with identity_6:
        selected["Rebar material"] = st.text_input(
            "Material", value=str(selected.get("Rebar material") or "SD40"),
            key=f"crossbeam_rb2a_template_material_{selected_id}",
        )
    with identity_7:
        selected["Active"] = st.toggle(
            "Active", value=bool(selected.get("Active")), key=f"crossbeam_rb2a_template_active_{selected_id}"
        )
        selected["Credit inside segment"] = st.toggle(
            "Credit inside zone", value=bool(selected.get("Credit inside segment")),
            key=f"crossbeam_rb2a_template_credit_{selected_id}",
        )

    with st.expander("Auto-generated section layout", expanded=True):
        st.caption(
            "These controls generate the graphical longitudinal-bar layout. Generated As remains a preview and is not the adopted solver reinforcement."
        )
        outer_cols = st.columns([0.18, 0.22, 0.30, 0.30], gap="medium")
        with outer_cols[0]:
            selected["Outer face bars"] = st.toggle(
                "Outer faces", value=bool(selected.get("Outer face bars")), key=f"crossbeam_rb2a_outer_on_{selected_id}"
            )
        with outer_cols[1]:
            selected["Outer bar size"] = st.selectbox(
                "Outer bar", options=list(TEMPLATE_BAR_SIZE_OPTIONS),
                index=list(TEMPLATE_BAR_SIZE_OPTIONS).index(str(selected.get("Outer bar size") or "DB16")),
                key=f"crossbeam_rb2a_outer_bar_{selected_id}",
            )
        with outer_cols[2]:
            selected["Outer center offset mm"] = st.number_input(
                "Outer center offset (mm)", min_value=1.0, value=float(selected.get("Outer center offset mm") or 50.0),
                step=5.0, key=f"crossbeam_rb2a_outer_offset_{selected_id}",
            )
        with outer_cols[3]:
            selected["Outer target spacing mm"] = st.number_input(
                "Outer target spacing (mm)", min_value=1.0, value=float(selected.get("Outer target spacing mm") or 150.0),
                step=10.0, key=f"crossbeam_rb2a_outer_spacing_{selected_id}",
            )

        inner_cols = st.columns([0.18, 0.22, 0.30, 0.30], gap="medium")
        with inner_cols[0]:
            selected["Inner face bars"] = st.toggle(
                "Inner faces", value=bool(selected.get("Inner face bars")),
                disabled=str(selected.get("Applicable role")) == "Solid",
                key=f"crossbeam_rb2a_inner_on_{selected_id}",
            )
        with inner_cols[1]:
            selected["Inner bar size"] = st.selectbox(
                "Inner bar", options=list(TEMPLATE_BAR_SIZE_OPTIONS),
                index=list(TEMPLATE_BAR_SIZE_OPTIONS).index(str(selected.get("Inner bar size") or "DB16")),
                key=f"crossbeam_rb2a_inner_bar_{selected_id}",
            )
        with inner_cols[2]:
            selected["Inner center offset mm"] = st.number_input(
                "Inner center offset (mm)", min_value=1.0, value=float(selected.get("Inner center offset mm") or 50.0),
                step=5.0, key=f"crossbeam_rb2a_inner_offset_{selected_id}",
            )
        with inner_cols[3]:
            selected["Inner target spacing mm"] = st.number_input(
                "Inner target spacing (mm)", min_value=1.0, value=float(selected.get("Inner target spacing mm") or 150.0),
                step=10.0, key=f"crossbeam_rb2a_inner_spacing_{selected_id}",
            )

    with st.expander("Adopted provided reinforcement", expanded=False):
        st.caption(
            "Enter actual project reinforcement only. These adopted quantities stay separate from the auto-generated graphical layout until an explicit future solver handoff."
        )
        qcols = st.columns(4, gap="medium")
        labels = (("Top As mm²", "Top As (mm²)", "%.1f"), ("Bottom As mm²", "Bottom As (mm²)", "%.1f"),
                  ("Side As mm²", "Side As (mm²)", "%.1f"), ("Av/s mm²/mm", "Av/s (mm²/mm)", "%.4f"))
        for col, (field, label, _fmt) in zip(qcols, labels):
            with col:
                step = 0.01 if field == "Av/s mm²/mm" else 100.0
                selected[field] = st.number_input(
                    label, min_value=0.0, value=float(selected.get(field) or 0.0), step=step,
                    key=f"crossbeam_rb2a_{field}_{selected_id}",
                )

    selected["Notes"] = st.text_area(
        "Template notes", value=str(selected.get("Notes") or ""), height=80, key=f"crossbeam_rb2a_template_notes_{selected_id}"
    )
    rows[index] = canonical_rebar_templates([selected])[0]
    st.session_state[CB_RB_TEMPLATE_ROWS_KEY] = rows

    duplicate_ids = sorted(
        template_id for template_id in set(template_ids) if template_id and template_ids.count(template_id) > 1
    )
    if duplicate_ids:
        st.error("Duplicate Rebar Template IDs: " + ", ".join(duplicate_ids))
    st.info(
        f"{RB_HOLLOW_MIN}: factory-cast Hollow minimum/detailing steel · "
        f"{RB_SOLID_COLUMN}: cast-in-place Solid column-region steel · "
        f"{RB_SOLID_ANCHORAGE}: local anchorage/D-region steel, not global section-strength credit."
    )
    return rows

def _render_zone_assignment(
    segment_rows: list[dict[str, Any]],
    template_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    st.markdown("### Segment / Zone Assignment")
    st.caption(
        "Segment Layout is the geometry source of truth. The compact editor keeps all six columns visible; Section context is derived automatically."
    )

    current_signature = segment_signature(segment_rows)
    stored_signature = st.session_state.get(CB_RB_SEGMENT_SIGNATURE_KEY)
    layout_changed = stored_signature is not None and tuple(stored_signature) != current_signature
    if layout_changed:
        st.warning(
            "Segment Layout changed after the rebar-zone map was created. Review station limits or reset the zone map; custom edits are not overwritten automatically."
        )

    if st.button("Reset rebar zones from Segment Layout", key="crossbeam_rb1_reset_zones"):
        st.session_state[CB_RB_ZONE_ROWS_KEY] = default_crossbeam_rebar_zones(segment_rows)
        st.session_state[CB_RB_SEGMENT_SIGNATURE_KEY] = current_signature
        st.session_state[CB_RB_ZONE_REV_KEY] = int(st.session_state.get(CB_RB_ZONE_REV_KEY, 0)) + 1
        st.rerun()

    template_ids = list(template_map(template_rows)) or [""]
    segment_ids = [str(row.get("Segment") or "") for row in segment_rows] or [""]
    segment_by_id = {str(row.get("Segment") or ""): row for row in segment_rows}
    old_purpose = {str(row.get("Zone ID") or ""): str(row.get("Purpose") or "") for row in canonical_rebar_zones(zone_rows)}
    compact_rows = []
    for row in canonical_rebar_zones(zone_rows):
        segment = segment_by_id.get(str(row.get("Segment") or ""), {})
        compact_rows.append(
            {
                "Zone": row.get("Zone ID", ""),
                "Segment": row.get("Segment", ""),
                "Start": row.get("s_start_m", 0.0),
                "End": row.get("s_end_m", 0.0),
                "Section": f"{segment.get('Section ID', '')} · {segment.get('Section name') or segment.get('Section role', '')} · {segment.get('Section role', '')}",
                "Template": row.get("Rebar template", ""),
            }
        )

    revision = int(st.session_state.get(CB_RB_ZONE_REV_KEY, 0))
    edited = st.data_editor(
        pd.DataFrame(compact_rows, columns=["Zone", "Segment", "Start", "End", "Section", "Template"]),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"crossbeam_rb2a_zone_editor_{revision}",
        disabled=["Section"],
        column_config={
            "Zone": st.column_config.TextColumn("Zone", required=True, width="small"),
            "Segment": st.column_config.SelectboxColumn("Segment", options=segment_ids, required=True, width="small"),
            "Start": st.column_config.NumberColumn("s start (m)", min_value=0.0, format="%.3f", required=True, width="small"),
            "End": st.column_config.NumberColumn("s end (m)", min_value=0.0, format="%.3f", required=True, width="small"),
            "Section": st.column_config.TextColumn("Section ID · name · role", width="large"),
            "Template": st.column_config.SelectboxColumn("Template", options=template_ids, required=True, width="medium"),
        },
    )
    candidate_rows: list[dict[str, Any]] = []
    for item in _records(edited):
        zone_id = str(item.get("Zone") or "").strip()
        candidate_rows.append(
            {
                "Zone ID": zone_id,
                "Segment": str(item.get("Segment") or "").strip(),
                "s_start_m": float(item.get("Start") or 0.0),
                "s_end_m": float(item.get("End") or 0.0),
                "Rebar template": str(item.get("Template") or "").strip(),
                "Purpose": old_purpose.get(zone_id, ""),
            }
        )
    rows, errors, warnings = validate_rebar_zones(candidate_rows, segment_rows, template_rows)

    if rows:
        zone_ids = [str(row.get("Zone ID") or "") for row in rows]
        selected_zone = st.selectbox(
            "Zone note to edit",
            options=zone_ids,
            key="crossbeam_rb2a_zone_note_selector",
            help="Purpose is edited separately so the main six-column table always fits the page width.",
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
) -> None:
    render_section_bar(
        "Segment-specific section rebar preview",
        "Review longitudinal bar locations for the selected Segment/Zone. Transverse reinforcement is summarized separately and is not drawn in this figure.",
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
        st.error(f"{selected_segment_id} has no assigned rebar zone.")
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
        st.error(
            f"Section ID {section_id or '(blank)'} is unavailable. Return to Section Builder or Segment Layout and repair the assignment."
        )
        return
    template_id = str(selected_zone.get("Rebar template") or "")
    template = template_map(template_rows).get(template_id)
    if template is None:
        st.error(f"Rebar template {template_id or '(blank)'} is not active or does not exist.")
        return
    role = str(definition.get("Section role") or selected_segment.get("Section role") or "Solid")
    applicable_role = str(template.get("Applicable role") or "Any")
    if applicable_role not in {"Any", role}:
        st.error(f"Template {template_id} is for {applicable_role}, but Section ID {section_id} is {role}.")
        return

    try:
        geometry = build_geometry_for_definition(definition)
    except Exception as exc:
        st.error(f"Unable to build {section_id}: {exc}")
        return

    material = str(template.get("Rebar material") or "SD40")
    outer_result = PerimeterRebarLayoutResult(table=pd.DataFrame())
    if bool(template.get("Outer face bars")):
        outer_size = str(template.get("Outer bar size") or "DB16")
        outer_result = generate_perimeter_rebar_layout(
            geometry, bar_size=outer_size, diameter_mm=rebar_diameter_mm(outer_size), material=material,
            edge_offset_mm=float(template.get("Outer center offset mm") or 50.0),
            target_spacing_mm=float(template.get("Outer target spacing mm") or 150.0), min_bars=4, label_prefix="O",
        )
    inner_result = PerimeterRebarLayoutResult(table=pd.DataFrame())
    if role == "Hollow" and bool(template.get("Inner face bars")):
        inner_size = str(template.get("Inner bar size") or "DB16")
        inner_result = generate_inner_face_rebar_layout(
            geometry, hole_index=0, bar_size=inner_size, diameter_mm=rebar_diameter_mm(inner_size), material=material,
            edge_offset_mm=float(template.get("Inner center offset mm") or 50.0),
            target_spacing_mm=float(template.get("Inner target spacing mm") or 150.0), min_bars=4, label_prefix="I",
        )

    outer_rebars = _result_rebars(outer_result, layer="Outer") if outer_result.ok else []
    inner_rebars = _result_rebars(inner_result, layer="Inner") if inner_result.ok else []
    total_rebars = outer_rebars + inner_rebars
    total_area = _generated_area_mm2(total_rebars)
    adopted = _adopted_reinforcement_summary(template)
    metric_status = "ready" if total_rebars and not outer_result.errors and not inner_result.errors else "warning"
    render_metric_cards(
        [
            {"title": "Selected section", "value": section_id, "detail": f"{definition.get('Section name', '')} · {role}", "status": "info"},
            {"title": "Assigned template", "value": template_id, "detail": f"{selected_zone_id} · s={float(selected_zone['s_start_m']):.3f}–{float(selected_zone['s_end_m']):.3f} m", "status": "info"},
            {"title": "Auto-generated layout", "value": f"{len(total_rebars)} bars", "detail": f"As {total_area:,.0f} mm² · Outer {len(outer_rebars)} · Inner {len(inner_rebars)}", "status": metric_status},
            {"title": "Adopted reinforcement", "value": "DEFINED" if _template_quantity_defined(template) else "NOT ADOPTED", "detail": adopted, "status": "ready" if _template_quantity_defined(template) else "warning"},
        ]
    )

    marker_mode = st.radio(
        "Bar display",
        options=["Enhanced markers", "True bar diameter"],
        horizontal=True,
        key=CB_RB_PREVIEW_MARKER_MODE_KEY,
        help="Enhanced markers improve visual review only. All bar quantities and As calculations always use the true bar diameter.",
    )
    figure_title = f"Longitudinal Bar-Location Preview — {selected_segment_id} / {selected_zone_id} · {section_id} · {template_id}"
    st.plotly_chart(
        _section_rebar_preview_figure(
            geometry, outer_rebars=outer_rebars, inner_rebars=inner_rebars, title=figure_title, marker_mode=marker_mode
        ),
        use_container_width=True, config=FIGURE_CONFIG,
    )
    st.caption(
        "Outer-face bars follow the inward concrete perimeter; inner-face bars are offset from the void into the concrete wall. "
        "This is a longitudinal-bar detailing preview, not a code-minimum design or ULS/SLS solver result."
    )
    _layout_result_messages(outer_result, "Outer layout")
    if role == "Hollow" and bool(template.get("Inner face bars")):
        _layout_result_messages(inner_result, "Inner layout")

    summary_rows: list[dict[str, Any]] = []
    for layer, bars, result in (("Outer", outer_rebars, outer_result), ("Inner", inner_rebars, inner_result)):
        if not bars and result.table.empty:
            continue
        summary_rows.append(
            {
                "Layer": layer,
                "Bars": len(bars),
                "Size": str(template.get("Outer bar size") if layer == "Outer" else template.get("Inner bar size")),
                "Auto As (mm²)": _generated_area_mm2(bars),
                "Max spacing (mm)": result.actual_spacing_mm,
                "Status": "PREVIEW READY" if result.ok else "REVIEW REQUIRED",
            }
        )
    if summary_rows:
        st.dataframe(
            pd.DataFrame(summary_rows), use_container_width=True, hide_index=True,
            column_config={
                "Layer": st.column_config.TextColumn(width="small"),
                "Bars": st.column_config.NumberColumn(width="small"),
                "Size": st.column_config.TextColumn(width="small"),
                "Auto As (mm²)": st.column_config.NumberColumn(format="%.1f", width="medium"),
                "Max spacing (mm)": st.column_config.NumberColumn(format="%.1f", width="medium"),
                "Status": st.column_config.TextColumn(width="medium"),
            },
        )
    st.warning(
        "JOINT GUARD — This preview applies only inside the selected Segment/Zone. Ordinary rebar crossing each segment joint is 0 mm². "
        "PT continuity is required but has not yet been verified from Tendon System/Profile."
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
    zone_rows = canonical_rebar_zones(
        _records(st.session_state.get(CB_RB_ZONE_ROWS_KEY)) or default_crossbeam_rebar_zones(segment_rows)
    )
    active_templates = template_map(template_rows)

    render_metric_cards(
        [
            {
                "title": "Rebar model",
                "value": "Segment / zone based" if ordinary_enabled else "Disabled",
                "detail": "Crossbeam-local templates; generic global rebar table is not used",
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
        template_rows = _render_template_library(template_rows)
        active_templates = template_map(template_rows)
        quantity_defined = sum(_template_quantity_defined(row) for row in active_templates.values())
        render_metric_cards(
            [
                {"title": "Active templates", "value": len(active_templates), "detail": "Crossbeam-only template IDs", "status": "info"},
                {
                    "title": "Quantities defined",
                    "value": f"{quantity_defined} / {len(active_templates)}",
                    "detail": "At least one As or Av/s value entered",
                    "status": "ready" if active_templates and quantity_defined == len(active_templates) else "warning",
                },
                {"title": "Joint crossing credit", "value": "0 mm²", "detail": "Locked independently of template inputs", "status": "warning"},
            ]
        )

    elif active_view == "Segment / Zone":
        zone_rows, errors, warnings = _render_zone_assignment(segment_rows, template_rows, zone_rows)
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
                f"{len(warnings)} active template(s) require adopted provided reinforcement: "
                + "; ".join(message.split(":", 1)[0] for message in warnings)
                + ". Open Templates → Adopted provided reinforcement to enter project values."
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
        _render_section_rebar_preview(segment_rows, zone_rows, template_rows)

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
        audit_rows = station_rebar_audit_rows(segment_rows, zone_rows, template_rows)
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
                rebar_context = f"{row.get('Active template', '')} · {row.get('Ordinary rebar credited locally', '')}"
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
            "CROSSBEAM.RB2A does not modify ULS/SLS capacity, shear/torsion, Result Summary, Report/QA, or Project JSON. "
            "A future Tendon audit must verify active tendon geometry/Aps at each joint before ULS station handoff can claim continuity."
        )
