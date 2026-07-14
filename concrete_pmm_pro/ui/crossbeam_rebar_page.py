"""Workflow-scoped Rebar workspace for segmental Portal Frame Crossbeams.

CROSSBEAM.RB1 is an input/traceability milestone only.  It never routes the
new template or zone state into existing PMM, Beam/Girder, SLS, shear, torsion,
or report solvers.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from concrete_pmm_pro.core.reinforcement_system import ordinary_rebar_enabled, prestressing_steel_enabled
from concrete_pmm_pro.crossbeam.rebar import (
    RB_HOLLOW_MIN,
    RB_SOLID_ANCHORAGE,
    RB_SOLID_COLUMN,
    TEMPLATE_CONSTRUCTION_OPTIONS,
    TEMPLATE_LONGITUDINAL_BASIS_OPTIONS,
    TEMPLATE_ROLE_OPTIONS,
    canonical_rebar_templates,
    canonical_rebar_zones,
    default_crossbeam_rebar_templates,
    default_crossbeam_rebar_zones,
    segment_joint_audit_rows,
    segment_signature,
    station_rebar_audit_rows,
    template_map,
    validate_rebar_zones,
)
from concrete_pmm_pro.ui.commercial import render_metric_cards, render_page_header, render_section_bar
from concrete_pmm_pro.ui.crossbeam_pages import FIGURE_CONFIG, crossbeam_segment_layout_from_state


CB_RB_TEMPLATE_ROWS_KEY = "crossbeam_rb1_template_rows"
CB_RB_TEMPLATE_REV_KEY = "crossbeam_rb1_template_editor_revision"
CB_RB_ZONE_ROWS_KEY = "crossbeam_rb1_zone_assignment_rows"
CB_RB_ZONE_REV_KEY = "crossbeam_rb1_zone_editor_revision"
CB_RB_SEGMENT_SIGNATURE_KEY = "crossbeam_rb1_segment_signature"


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
            text="<b>Ord. rebar = 0</b><br>Tendons only",
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
        "No ordinary reinforcing bar crosses any segment joint; post-tensioning tendons provide all global continuity across the joint plane.",
        mark="J",
    )
    st.warning(
        "LOCKED WORKFLOW RULE — Ordinary rebar crossing every segment joint = 0 mm². "
        "This is not user-editable. Rebar may be credited only within its assigned segment/zone; tendons are the only global flexural continuity system across joints."
    )
    st.caption(
        "Joint shear transfer, interface behavior, opening/decompression, shear keys, anchorage zones, solid–hollow transitions, and column D-regions remain separate future checks."
    )


def _render_template_library(template_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    st.markdown("### Rebar Template Library")
    st.caption(
        "Define actual provided reinforcement for factory-cast hollow segments and cast-in-place solid zones. "
        "Template quantities are local to the assigned zone and are never continued across a segment joint."
    )
    if st.button("Reset Crossbeam rebar templates", key="crossbeam_rb1_reset_templates"):
        st.session_state[CB_RB_TEMPLATE_ROWS_KEY] = default_crossbeam_rebar_templates()
        st.session_state[CB_RB_TEMPLATE_REV_KEY] = int(st.session_state.get(CB_RB_TEMPLATE_REV_KEY, 0)) + 1
        st.rerun()

    revision = int(st.session_state.get(CB_RB_TEMPLATE_REV_KEY, 0))
    edited = st.data_editor(
        pd.DataFrame(template_rows),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"crossbeam_rb1_template_editor_{revision}",
        column_config={
            "Active": st.column_config.CheckboxColumn("Active", default=True),
            "Template ID": st.column_config.TextColumn("Template ID", required=True),
            "Template name": st.column_config.TextColumn("Template name", required=True),
            "Applicable role": st.column_config.SelectboxColumn("Applicable role", options=list(TEMPLATE_ROLE_OPTIONS), required=True),
            "Construction": st.column_config.SelectboxColumn("Construction", options=list(TEMPLATE_CONSTRUCTION_OPTIONS), required=True),
            "Longitudinal basis": st.column_config.SelectboxColumn(
                "Longitudinal basis", options=list(TEMPLATE_LONGITUDINAL_BASIS_OPTIONS), required=True
            ),
            "Credit inside segment": st.column_config.CheckboxColumn(
                "Credit inside zone", help="Future station solver may credit this template inside the assigned zone only."
            ),
            "Top As mm²": st.column_config.NumberColumn("Top As (mm²)", min_value=0.0, format="%.1f"),
            "Bottom As mm²": st.column_config.NumberColumn("Bottom As (mm²)", min_value=0.0, format="%.1f"),
            "Side As mm²": st.column_config.NumberColumn("Side As (mm²)", min_value=0.0, format="%.1f"),
            "Av/s mm²/mm": st.column_config.NumberColumn("Av/s (mm²/mm)", min_value=0.0, format="%.4f"),
            "fy MPa": st.column_config.NumberColumn("fy (MPa)", min_value=0.0, format="%.1f"),
            "Notes": st.column_config.TextColumn("Notes"),
        },
    )
    rows = canonical_rebar_templates(_records(edited))
    st.session_state[CB_RB_TEMPLATE_ROWS_KEY] = rows
    duplicate_ids = sorted(
        template_id
        for template_id in {str(row.get("Template ID") or "") for row in rows}
        if template_id and sum(str(item.get("Template ID") or "") == template_id for item in rows) > 1
    )
    if duplicate_ids:
        st.error("Duplicate Rebar Template IDs: " + ", ".join(duplicate_ids))
    st.info(
        f"{RB_HOLLOW_MIN} is intended for factory-cast hollow-segment minimum/detailing steel. "
        f"{RB_SOLID_COLUMN} is intended for cast-in-place solid column regions. "
        f"{RB_SOLID_ANCHORAGE} remains local anchorage/D-region reinforcement and is not globally credited by RB1."
    )
    return rows


def _render_zone_assignment(
    segment_rows: list[dict[str, Any]],
    template_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    st.markdown("### Segment / Zone Assignment")
    st.caption(
        "Segment Layout is the geometry source of truth. One segment may be split into multiple rebar zones, but every zone must remain within that segment."
    )

    current_signature = segment_signature(segment_rows)
    stored_signature = st.session_state.get(CB_RB_SEGMENT_SIGNATURE_KEY)
    layout_changed = stored_signature is not None and tuple(stored_signature) != current_signature
    if layout_changed:
        st.warning(
            "Segment Layout has changed since the current rebar-zone map was created. Review the station limits or reset the zone map; custom edits are not overwritten automatically."
        )

    if st.button("Reset rebar zones from Segment Layout", key="crossbeam_rb1_reset_zones"):
        st.session_state[CB_RB_ZONE_ROWS_KEY] = default_crossbeam_rebar_zones(segment_rows)
        st.session_state[CB_RB_SEGMENT_SIGNATURE_KEY] = current_signature
        st.session_state[CB_RB_ZONE_REV_KEY] = int(st.session_state.get(CB_RB_ZONE_REV_KEY, 0)) + 1
        st.rerun()

    template_ids = list(template_map(template_rows)) or [""]
    segment_ids = [str(row.get("Segment") or "") for row in segment_rows] or [""]
    revision = int(st.session_state.get(CB_RB_ZONE_REV_KEY, 0))
    edited = st.data_editor(
        pd.DataFrame(canonical_rebar_zones(zone_rows)),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"crossbeam_rb1_zone_editor_{revision}",
        column_config={
            "Zone ID": st.column_config.TextColumn("Zone ID", required=True),
            "Segment": st.column_config.SelectboxColumn("Segment", options=segment_ids, required=True),
            "s_start_m": st.column_config.NumberColumn("s_start (m)", min_value=0.0, format="%.3f", required=True),
            "s_end_m": st.column_config.NumberColumn("s_end (m)", min_value=0.0, format="%.3f", required=True),
            "Rebar template": st.column_config.SelectboxColumn("Rebar template", options=template_ids, required=True),
            "Purpose": st.column_config.TextColumn("Purpose"),
        },
    )
    rows, errors, warnings = validate_rebar_zones(_records(edited), segment_rows, template_rows)
    st.session_state[CB_RB_ZONE_ROWS_KEY] = rows
    if not errors:
        st.session_state[CB_RB_SEGMENT_SIGNATURE_KEY] = current_signature
    return rows, errors, warnings


def render_crossbeam_rebar_page() -> None:
    length_m, segment_rows, segment_errors = crossbeam_segment_layout_from_state()
    _ensure_rb1_state(segment_rows)

    ordinary_enabled = ordinary_rebar_enabled(st.session_state, default=True)
    tendon_enabled = prestressing_steel_enabled(st.session_state, default=True)

    render_page_header(
        "Crossbeam Rebar",
        "Define segment-local and zone-local ordinary reinforcement without crediting any ordinary bar across post-tensioned segment joints.",
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
                "title": "Ordinary rebar system",
                "value": "Enabled" if ordinary_enabled else "Disabled",
                "detail": "Section Builder system gate; RB1 inputs remain stored",
                "status": "ready" if ordinary_enabled else "warning",
            },
            {
                "title": "Assignment mode",
                "value": "Segment / zone based",
                "detail": "Generic global rebar table is not used by Crossbeam RB1",
                "status": "info",
            },
            {
                "title": "Segment joints",
                "value": "TENDONS ONLY",
                "detail": "Ordinary rebar crossing every joint = 0 mm² (locked)",
                "status": "warning",
            },
            {
                "title": "Solver handoff",
                "value": "NOT CONNECTED",
                "detail": "Input foundation only; existing solvers are unchanged",
                "status": "neutral",
            },
        ]
    )

    if segment_errors:
        st.error("Segment Layout is not ready. Correct Segment Layout before accepting rebar-zone assignments.")
        for error in segment_errors:
            st.caption(error)
    if not tendon_enabled:
        st.error("Prestressing steel is disabled, but accepted Crossbeam joint continuity requires tendons across every segment joint.")
    if not ordinary_enabled:
        st.warning("Ordinary rebar is disabled in Section Builder. Stored RB1 templates/zones are excluded from future analysis until re-enabled.")

    _render_locked_joint_rule()

    template_tab, zone_tab, audit_tab = st.tabs(["Rebar Template Library", "Segment / Zone Assignment", "Joint & Station Audit"])

    with template_tab:
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

    with zone_tab:
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
        for warning in warnings:
            st.warning(warning)
        st.plotly_chart(
            _rebar_elevation_figure(segment_rows, zone_rows, template_rows, length_m),
            use_container_width=True,
            config=FIGURE_CONFIG,
        )
        st.caption(
            "The rebar lines are schematic template extents only. They intentionally terminate within their assigned segment/zone. "
            "No ordinary rebar is shown or credited across a segment joint; tendon geometry remains owned by Tendon Profile."
        )

    with audit_tab:
        render_section_bar(
            "Joint continuity audit",
            "Every segment boundary is generated from Segment Layout and locked to zero ordinary-rebar crossing credit.",
            mark="QA",
        )
        joints = segment_joint_audit_rows(segment_rows)
        if joints:
            st.dataframe(pd.DataFrame(joints), use_container_width=True, hide_index=True)
        else:
            st.info("No internal segment joint exists in the current Segment Layout.")

        render_section_bar(
            "Calculated active rebar by station",
            "Read-only assembly preview. Interior rows show the assigned local template; joint rows show tendon-only continuity.",
            mark="s",
        )
        audit_rows = station_rebar_audit_rows(segment_rows, zone_rows, template_rows)
        st.dataframe(pd.DataFrame(audit_rows), use_container_width=True, hide_index=True)
        st.info(
            "CROSSBEAM.RB1 does not modify ULS/SLS capacity, shear/torsion, Result Summary, Report/QA, or Project JSON. "
            "Future CROSSBEAM.ULS1 must consume this station assembly explicitly and must preserve zero ordinary-rebar participation at joint planes."
        )
