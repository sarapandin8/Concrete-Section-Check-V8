"""Workflow-scoped Rebar workspace for segmental Portal Frame Crossbeams.

CROSSBEAM.RB2 adds segment-specific Solid/Hollow section rebar previews and a
separated button subnavigation layer on top of the RB1 input foundation.  It
never routes the new template, zone, or generated preview state into existing
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
        "Template quantities and auto-layout controls are local to the assigned zone and are never continued across a segment joint."
    )
    if st.button("Reset Crossbeam rebar templates", key="crossbeam_rb1_reset_templates"):
        st.session_state[CB_RB_TEMPLATE_ROWS_KEY] = default_crossbeam_rebar_templates()
        st.session_state[CB_RB_TEMPLATE_REV_KEY] = int(st.session_state.get(CB_RB_TEMPLATE_REV_KEY, 0)) + 1
        st.rerun()

    revision = int(st.session_state.get(CB_RB_TEMPLATE_REV_KEY, 0))
    identity_columns = [
        "Active",
        "Template ID",
        "Template name",
        "Applicable role",
        "Construction",
        "Longitudinal basis",
        "Credit inside segment",
        "fy MPa",
        "Notes",
    ]
    edited_identity = st.data_editor(
        pd.DataFrame(template_rows)[identity_columns],
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"crossbeam_rb2_template_identity_editor_{revision}",
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
            "fy MPa": st.column_config.NumberColumn("fy (MPa)", min_value=0.0, format="%.1f"),
            "Notes": st.column_config.TextColumn("Notes"),
        },
    )
    identity_rows = _records(edited_identity)
    old_by_id = {str(row.get("Template ID") or ""): dict(row) for row in canonical_rebar_templates(template_rows)}
    rows: list[dict[str, Any]] = []
    for item in identity_rows:
        template_id = str(item.get("Template ID") or "").strip()
        merged = dict(old_by_id.get(template_id, {}))
        merged.update(item)
        rows.append(merged)
    rows = canonical_rebar_templates(rows)

    with st.expander("Auto section-layout controls", expanded=True):
        st.caption(
            "Outer-face bars follow the inward concrete perimeter. Hollow sections may also generate a separate inner-face layout around the void. "
            "These generated bars are a detailing preview only and do not populate the solver or the provided-As fields."
        )
        layout_columns = [
            "Template ID",
            "Rebar material",
            "Outer face bars",
            "Outer bar size",
            "Outer center offset mm",
            "Outer target spacing mm",
            "Inner face bars",
            "Inner bar size",
            "Inner center offset mm",
            "Inner target spacing mm",
        ]
        edited_layout = st.data_editor(
            pd.DataFrame([{column: row.get(column) for column in layout_columns} for row in rows], columns=layout_columns),
            use_container_width=True,
            hide_index=True,
            disabled=["Template ID"],
            key=f"crossbeam_rb2_template_layout_editor_{revision}",
            column_config={
                "Template ID": st.column_config.TextColumn("Template ID"),
                "Rebar material": st.column_config.TextColumn("Material"),
                "Outer face bars": st.column_config.CheckboxColumn("Outer faces"),
                "Outer bar size": st.column_config.SelectboxColumn(
                    "Outer bar", options=list(TEMPLATE_BAR_SIZE_OPTIONS), required=True
                ),
                "Outer center offset mm": st.column_config.NumberColumn(
                    "Outer offset (mm)", min_value=1.0, format="%.1f"
                ),
                "Outer target spacing mm": st.column_config.NumberColumn(
                    "Outer spacing (mm)", min_value=1.0, format="%.1f"
                ),
                "Inner face bars": st.column_config.CheckboxColumn(
                    "Inner faces", help="Used only when the selected Section ID contains a void."
                ),
                "Inner bar size": st.column_config.SelectboxColumn(
                    "Inner bar", options=list(TEMPLATE_BAR_SIZE_OPTIONS), required=True
                ),
                "Inner center offset mm": st.column_config.NumberColumn(
                    "Inner offset (mm)", min_value=1.0, format="%.1f"
                ),
                "Inner target spacing mm": st.column_config.NumberColumn(
                    "Inner spacing (mm)", min_value=1.0, format="%.1f"
                ),
            },
        )
        layout_by_id = {str(item.get("Template ID") or ""): item for item in _records(edited_layout)}
        for row in rows:
            row.update(layout_by_id.get(str(row.get("Template ID") or ""), {}))
        rows = canonical_rebar_templates(rows)

    with st.expander("Provided reinforcement quantities", expanded=False):
        st.caption(
            "Enter actual project reinforcement when known. These quantities remain separate from the generated preview and will only be used by a future station-based solver after explicit handoff."
        )
        quantity_columns = ["Template ID", "Top As mm²", "Bottom As mm²", "Side As mm²", "Av/s mm²/mm"]
        edited_quantities = st.data_editor(
            pd.DataFrame(
                [{column: row.get(column) for column in quantity_columns} for row in rows],
                columns=quantity_columns,
            ),
            use_container_width=True,
            hide_index=True,
            disabled=["Template ID"],
            key=f"crossbeam_rb2_template_quantity_editor_{revision}",
            column_config={
                "Template ID": st.column_config.TextColumn("Template ID"),
                "Top As mm²": st.column_config.NumberColumn("Top As (mm²)", min_value=0.0, format="%.1f"),
                "Bottom As mm²": st.column_config.NumberColumn("Bottom As (mm²)", min_value=0.0, format="%.1f"),
                "Side As mm²": st.column_config.NumberColumn("Side As (mm²)", min_value=0.0, format="%.1f"),
                "Av/s mm²/mm": st.column_config.NumberColumn("Av/s (mm²/mm)", min_value=0.0, format="%.4f"),
            },
        )
        quantity_by_id = {str(item.get("Template ID") or ""): item for item in _records(edited_quantities)}
        for row in rows:
            row.update(quantity_by_id.get(str(row.get("Template ID") or ""), {}))
        rows = canonical_rebar_templates(rows)

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
) -> go.Figure:
    fig = create_section_preview(geometry)
    layer_specs = [
        ("Outer-face bars", outer_rebars, "#155a9c"),
        ("Inner-face bars", inner_rebars, "#2f7d4a"),
    ]
    for layer_name, bars, color in layer_specs:
        if not bars:
            continue
        for bar in bars:
            radius = max(float(bar.diameter_mm), 0.0) / 2.0
            fig.add_shape(
                type="circle",
                xref="x",
                yref="y",
                x0=bar.x_mm - radius,
                x1=bar.x_mm + radius,
                y0=bar.y_mm - radius,
                y1=bar.y_mm + radius,
                fillcolor=color,
                opacity=0.82,
                line={"color": "#ffffff", "width": 0.8},
                layer="above",
            )
        fig.add_trace(
            go.Scatter(
                x=[bar.x_mm for bar in bars],
                y=[bar.y_mm for bar in bars],
                mode="markers",
                marker={"size": 5, "color": color, "opacity": 0.5, "line": {"color": "#ffffff", "width": 0.5}},
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
        height=600,
        margin={"l": 35, "r": 25, "t": 80, "b": 45},
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
        "Select a segment and zone to review the actual Section ID with its assigned template. Solid sections use an outer perimeter; hollow sections may show both outer and inner-face bars.",
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
            f"Section ID {section_id or '(blank)'} is not available in Crossbeam Project Sections. "
            "Return to Section Builder or Segment Layout and repair the assignment."
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
            geometry,
            bar_size=outer_size,
            diameter_mm=rebar_diameter_mm(outer_size),
            material=material,
            edge_offset_mm=float(template.get("Outer center offset mm") or 50.0),
            target_spacing_mm=float(template.get("Outer target spacing mm") or 150.0),
            min_bars=4,
            label_prefix="O",
        )
    inner_result = PerimeterRebarLayoutResult(table=pd.DataFrame())
    if role == "Hollow" and bool(template.get("Inner face bars")):
        inner_size = str(template.get("Inner bar size") or "DB16")
        inner_result = generate_inner_face_rebar_layout(
            geometry,
            hole_index=0,
            bar_size=inner_size,
            diameter_mm=rebar_diameter_mm(inner_size),
            material=material,
            edge_offset_mm=float(template.get("Inner center offset mm") or 50.0),
            target_spacing_mm=float(template.get("Inner target spacing mm") or 150.0),
            min_bars=4,
            label_prefix="I",
        )

    outer_rebars = _result_rebars(outer_result, layer="Outer") if outer_result.ok else []
    inner_rebars = _result_rebars(inner_result, layer="Inner") if inner_result.ok else []
    total_rebars = outer_rebars + inner_rebars
    total_area = _generated_area_mm2(total_rebars)
    metric_status = "ready" if total_rebars and not outer_result.errors and not inner_result.errors else "warning"
    render_metric_cards(
        [
            {
                "title": "Selected section",
                "value": section_id,
                "detail": f"{definition.get('Section name', '')} · {role}",
                "status": "info",
            },
            {
                "title": "Assigned template",
                "value": template_id,
                "detail": f"{selected_zone_id} · s = {float(selected_zone['s_start_m']):.3f}–{float(selected_zone['s_end_m']):.3f} m",
                "status": "info",
            },
            {
                "title": "Generated bars",
                "value": len(total_rebars),
                "detail": f"Outer {len(outer_rebars)} · Inner {len(inner_rebars)}",
                "status": metric_status,
            },
            {
                "title": "Generated As",
                "value": f"{total_area:,.0f} mm²",
                "detail": "Preview only — not solver handoff",
                "status": "neutral",
            },
        ]
    )

    figure_title = f"{selected_segment_id} / {selected_zone_id} — {section_id} · {template_id}"
    st.plotly_chart(
        _section_rebar_preview_figure(
            geometry,
            outer_rebars=outer_rebars,
            inner_rebars=inner_rebars,
            title=figure_title,
        ),
        use_container_width=True,
        config=FIGURE_CONFIG,
    )
    st.caption(
        "Auto-generated bar circles are drawn at true section scale. Outer-face bars follow the inward concrete perimeter; "
        "inner-face bars are offset outward from the void into the concrete wall. This is an editable detailing preview, not a code-minimum design or ULS/SLS solver result."
    )
    _layout_result_messages(outer_result, "Outer layout")
    if role == "Hollow" and bool(template.get("Inner face bars")):
        _layout_result_messages(inner_result, "Inner layout")

    summary_rows: list[dict[str, Any]] = []
    for layer, bars, result in (
        ("Outer faces", outer_rebars, outer_result),
        ("Inner faces", inner_rebars, inner_result),
    ):
        if not bars and result.table.empty:
            continue
        summary_rows.append(
            {
                "Layer": layer,
                "Bars": len(bars),
                "Bar size": str(template.get("Outer bar size") if layer == "Outer faces" else template.get("Inner bar size")),
                "Generated As mm²": _generated_area_mm2(bars),
                "Max spacing mm": result.actual_spacing_mm,
                "Status": "PREVIEW READY" if result.ok else "REVIEW REQUIRED",
            }
        )
    if summary_rows:
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
    st.info(
        "LOCKED JOINT RULE remains unchanged: this section preview applies only inside the selected segment/zone. "
        "At both ends of the segment, ordinary-rebar crossing credit is 0 mm² and post-tensioning tendons provide global continuity."
    )


def render_crossbeam_rebar_page() -> None:
    length_m, segment_rows, segment_errors = crossbeam_segment_layout_from_state()
    _ensure_rb1_state(segment_rows)

    ordinary_enabled = ordinary_rebar_enabled(st.session_state, default=True)
    tendon_enabled = prestressing_steel_enabled(st.session_state, default=True)

    render_page_header(
        "Crossbeam Rebar",
        "Define segment-local and zone-local ordinary reinforcement, review each assigned section graphically, and preserve tendon-only continuity across every post-tensioned segment joint.",
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
                "detail": "Generic global rebar table is not used by Crossbeam RB2",
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
            "CROSSBEAM.RB2 does not modify ULS/SLS capacity, shear/torsion, Result Summary, Report/QA, or Project JSON. "
            "Future CROSSBEAM.ULS1 must consume this station assembly explicitly and must preserve zero ordinary-rebar participation at joint planes."
        )
