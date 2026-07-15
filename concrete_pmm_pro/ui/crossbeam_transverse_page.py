"""Crossbeam-only transverse/shear reinforcement UI for CROSSBEAM.TR1.

The page intentionally remains solver-neutral.  It stores editable local
transverse templates, computes traceable Av/s previews, and draws schematic
cross-section/elevation reinforcement without giving segment-joint shear credit.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from concrete_pmm_pro.crossbeam.rebar import canonical_rebar_zones
from concrete_pmm_pro.crossbeam.transverse import (
    TRANSVERSE_BAR_SIZE_OPTIONS,
    TRANSVERSE_CONSTRUCTION_OPTIONS,
    TRANSVERSE_FY_BY_MATERIAL,
    TRANSVERSE_FY_OPTIONS,
    TRANSVERSE_MATERIAL_BY_FY,
    TRANSVERSE_MATERIAL_OPTIONS,
    TRANSVERSE_ROLE_OPTIONS,
    canonical_transverse_templates,
    default_crossbeam_transverse_templates,
    duplicate_transverse_template,
    new_transverse_template,
    transverse_avs_record,
    transverse_set_stations,
    transverse_template_map,
    validate_transverse_templates,
)
from concrete_pmm_pro.ui.commercial import render_metric_cards, render_section_bar
from concrete_pmm_pro.visualization import create_section_preview

CB_TR_TEMPLATE_ROWS_KEY = "crossbeam_tr1_template_rows"
CB_TR_TEMPLATE_REV_KEY = "crossbeam_tr1_template_editor_revision"
CB_TR_ACTION_NOTICE_KEY = "crossbeam_tr1_action_notice"
CB_TR_PREVIEW_MODE_KEY = "crossbeam_tr1_preview_mode"


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return [dict(row) for row in value.to_dict(orient="records")]
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def ensure_crossbeam_transverse_state() -> list[dict[str, Any]]:
    if CB_TR_TEMPLATE_ROWS_KEY not in st.session_state:
        st.session_state[CB_TR_TEMPLATE_ROWS_KEY] = default_crossbeam_transverse_templates()
    st.session_state.setdefault(CB_TR_TEMPLATE_REV_KEY, 0)
    rows = canonical_transverse_templates(_records(st.session_state.get(CB_TR_TEMPLATE_ROWS_KEY)))
    if not rows:
        rows = default_crossbeam_transverse_templates()
    st.session_state[CB_TR_TEMPLATE_ROWS_KEY] = rows
    return rows


def _store(rows: list[dict[str, Any]]) -> None:
    st.session_state[CB_TR_TEMPLATE_ROWS_KEY] = canonical_transverse_templates(rows)


def _bump_revision() -> None:
    st.session_state[CB_TR_TEMPLATE_REV_KEY] = int(st.session_state.get(CB_TR_TEMPLATE_REV_KEY, 0)) + 1


def _normalize_template_id(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^A-Z0-9_-]+", "", text)
    text = re.sub(r"-{2,}", "-", text).strip("-_")
    return text[:48]


def _identity_merge(
    rows: list[dict[str, Any]],
    editor_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str], list[str]]:
    source_rows = canonical_transverse_templates(rows)
    by_id = {str(row.get("Template ID") or ""): dict(row) for row in source_rows}
    proposed: list[dict[str, Any]] = []
    rename_map: dict[str, str] = {}
    errors: list[str] = []
    for index, item in enumerate(editor_rows):
        old_id = str(item.get("_Original ID") or "").strip()
        source = by_id.get(old_id) or (source_rows[index] if index < len(source_rows) else {})
        new_id = _normalize_template_id(item.get("Template ID") or old_id)
        if not new_id:
            errors.append(f"{old_id or f'Row {index + 1}'} requires a Template ID.")
            new_id = old_id
        updated = dict(source)
        updated["Template ID"] = new_id
        updated["Template name"] = str(item.get("Template name") or source.get("Template name") or new_id).strip()
        updated["Applicable role"] = str(item.get("Role") or source.get("Applicable role") or "Any")
        updated["Construction"] = str(item.get("Construction") or source.get("Construction") or "Project-defined")
        proposed.append(updated)
        if old_id and new_id != old_id:
            rename_map[old_id] = new_id
    ids = [str(row.get("Template ID") or "") for row in proposed]
    duplicates = sorted({value for value in ids if value and ids.count(value) > 1})
    if duplicates:
        errors.append("Duplicate Transverse Template IDs are not allowed: " + ", ".join(duplicates) + ".")
    if errors:
        return source_rows, canonical_rebar_zones(zone_rows), {}, errors
    zones = []
    for zone in canonical_rebar_zones(zone_rows):
        updated = dict(zone)
        old_ref = str(updated.get("Transverse template") or "")
        if old_ref in rename_map:
            updated["Transverse template"] = rename_map[old_ref]
        zones.append(updated)
    return canonical_transverse_templates(proposed), zones, rename_map, []


def _material_merge(rows: list[dict[str, Any]], editor_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    canonical = canonical_transverse_templates(rows)
    by_id = {str(row.get("Template ID") or ""): dict(row) for row in canonical}
    sync_required = False
    for item in editor_rows:
        template_id = str(item.get("Template ID") or "")
        target = by_id.get(template_id)
        if target is None:
            continue
        old_material = str(target.get("Rebar material") or "SD40")
        old_fy = float(target.get("fy MPa") or 390.0)
        new_material = str(item.get("Material") or old_material).upper()
        try:
            new_fy = float(item.get("fy (MPa)") or old_fy)
        except (TypeError, ValueError):
            new_fy = old_fy
        if new_material not in TRANSVERSE_MATERIAL_OPTIONS:
            new_material = old_material
        new_fy = 490.0 if abs(new_fy - 490.0) < abs(new_fy - 390.0) else 390.0
        material_changed = new_material != old_material
        fy_changed = new_fy != old_fy
        if material_changed and not fy_changed:
            new_fy = TRANSVERSE_FY_BY_MATERIAL[new_material]
        elif fy_changed and not material_changed:
            new_material = TRANSVERSE_MATERIAL_BY_FY[new_fy]
        elif TRANSVERSE_FY_BY_MATERIAL[new_material] != new_fy:
            new_fy = TRANSVERSE_FY_BY_MATERIAL[new_material]
        target["Rebar material"] = new_material
        target["fy MPa"] = new_fy
        target["Active"] = bool(item.get("Active"))
        target["Credit inside segment"] = bool(item.get("Credit"))
        if str(item.get("Material") or "").upper() != new_material or float(item.get("fy (MPa)") or 0.0) != new_fy:
            sync_required = True
    return canonical_transverse_templates([by_id[str(row.get("Template ID") or "")] for row in canonical]), sync_required


def _merge_fields(rows: list[dict[str, Any]], editor_rows: list[dict[str, Any]], field_map: Mapping[str, str]) -> list[dict[str, Any]]:
    canonical = canonical_transverse_templates(rows)
    by_id = {str(row.get("Template ID") or ""): dict(row) for row in canonical}
    for item in editor_rows:
        template_id = str(item.get("Template ID") or "")
        target = by_id.get(template_id)
        if target is None:
            continue
        for editor_name, canonical_name in field_map.items():
            if editor_name in item:
                target[canonical_name] = item.get(editor_name)
    return canonical_transverse_templates([by_id[str(row.get("Template ID") or "")] for row in canonical])


def _selected_ids(editor_rows: list[dict[str, Any]], column: str) -> list[str]:
    return [
        str(row.get("Template ID") or "")
        for row in editor_rows
        if bool(row.get(column)) and str(row.get("Template ID") or "")
    ]


def _duplicate(rows: list[dict[str, Any]], ids: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    canonical = canonical_transverse_templates(rows)
    existing = [str(row.get("Template ID") or "") for row in canonical]
    created: list[str] = []
    for template_id in ids:
        source = next((row for row in canonical if str(row.get("Template ID") or "") == template_id), None)
        if source is None:
            continue
        clone = duplicate_transverse_template(source, existing)
        canonical.append(clone)
        created.append(str(clone.get("Template ID") or ""))
        existing.append(str(clone.get("Template ID") or ""))
    return canonical_transverse_templates(canonical), created


def _delete(
    rows: list[dict[str, Any]],
    ids: list[str],
    zone_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    canonical = canonical_transverse_templates(rows)
    used_by: dict[str, list[str]] = {}
    for zone in canonical_rebar_zones(zone_rows):
        template_id = str(zone.get("Transverse template") or "")
        used_by.setdefault(template_id, []).append(str(zone.get("Zone ID") or ""))
    errors: list[str] = []
    deletable: list[str] = []
    for template_id in ids:
        if used_by.get(template_id):
            errors.append(f"{template_id} is assigned to {', '.join(sorted(used_by[template_id]))}.")
        else:
            deletable.append(template_id)
    if len(canonical) - len(set(deletable)) < 1:
        errors.append("At least one Transverse Template must remain.")
        deletable = []
    deleted = sorted(set(deletable))
    return [row for row in canonical if str(row.get("Template ID") or "") not in set(deleted)], deleted, errors


def render_crossbeam_transverse_template_library(
    template_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    st.markdown("### Transverse / Shear Template Library")
    st.caption(
        "Define local stirrup/tie layouts independently from longitudinal reinforcement. Every compact table fits the page width; no transverse template gives automatic segment-joint shear-transfer credit."
    )
    rows = canonical_transverse_templates(template_rows)
    revision = int(st.session_state.get(CB_TR_TEMPLATE_REV_KEY, 0))

    cols = st.columns([0.16, 0.16, 0.68], gap="small")
    with cols[0]:
        if st.button("New Hollow", use_container_width=True, key=f"crossbeam_tr1_new_hollow_{revision}"):
            rows.append(new_transverse_template("Hollow", [str(row.get("Template ID") or "") for row in rows]))
            _store(rows); _bump_revision(); st.rerun()
    with cols[1]:
        if st.button("New Solid", use_container_width=True, key=f"crossbeam_tr1_new_solid_{revision}"):
            rows.append(new_transverse_template("Solid", [str(row.get("Template ID") or "") for row in rows]))
            _store(rows); _bump_revision(); st.rerun()
    with cols[2]:
        st.caption("Hollow templates define left/right web legs; Solid templates define effective multi-leg ties. IDs are editable and Zone references update automatically.")

    st.markdown("#### Template identity and row actions")
    identity_rows = [
        {
            "_Original ID": row["Template ID"], "Copy": False, "Delete": False,
            "Template ID": row["Template ID"], "Template name": row["Template name"],
            "Role": row["Applicable role"], "Construction": row["Construction"],
        }
        for row in rows
    ]
    edited = st.data_editor(
        pd.DataFrame(identity_rows), use_container_width=True, hide_index=True, num_rows="fixed",
        key=f"crossbeam_tr1_identity_{revision}",
        column_config={
            "_Original ID": None,
            "Copy": st.column_config.CheckboxColumn(width="small"),
            "Delete": st.column_config.CheckboxColumn(width="small"),
            "Template ID": st.column_config.TextColumn(required=True, width="medium"),
            "Template name": st.column_config.TextColumn(required=True, width="large"),
            "Role": st.column_config.SelectboxColumn(options=list(TRANSVERSE_ROLE_OPTIONS), required=True, width="small"),
            "Construction": st.column_config.SelectboxColumn(options=list(TRANSVERSE_CONSTRUCTION_OPTIONS), required=True, width="medium"),
        },
    )
    identity_records = _records(edited)
    rows, updated_zones, rename_map, errors = _identity_merge(rows, identity_records, zone_rows)
    if errors:
        for message in errors: st.error(message)
    elif rename_map:
        st.session_state["crossbeam_rb1_zone_assignment_rows"] = updated_zones
        st.session_state["crossbeam_rb1_zone_editor_revision"] = int(st.session_state.get("crossbeam_rb1_zone_editor_revision", 0)) + 1
        _store(rows); _bump_revision()
        st.session_state[CB_TR_ACTION_NOTICE_KEY] = "Updated Transverse Template references: " + ", ".join(f"{a} → {b}" for a,b in rename_map.items()) + "."
        st.rerun()
    _store(rows)

    copy_ids = _selected_ids(identity_records, "Copy")
    delete_ids = _selected_ids(identity_records, "Delete")
    actions = st.columns([0.18, 0.18, 0.18, 0.46], gap="small")
    with actions[0]:
        if st.button(f"Duplicate checked ({len(copy_ids)})", use_container_width=True, disabled=not copy_ids, key=f"crossbeam_tr1_dup_{revision}"):
            rows, created = _duplicate(rows, copy_ids); _store(rows); _bump_revision()
            st.session_state[CB_TR_ACTION_NOTICE_KEY] = "Created " + ", ".join(created) + "."
            st.rerun()
    with actions[1]:
        confirm = st.checkbox("Confirm delete", disabled=not delete_ids, key=f"crossbeam_tr1_confirm_{revision}")
    with actions[2]:
        if st.button(f"Delete checked ({len(delete_ids)})", use_container_width=True, disabled=not delete_ids or not confirm, key=f"crossbeam_tr1_delete_{revision}"):
            rows, deleted, delete_errors = _delete(rows, delete_ids, zone_rows)
            if delete_errors:
                st.session_state[CB_TR_ACTION_NOTICE_KEY] = " ".join(delete_errors)
            else:
                _store(rows); _bump_revision(); st.session_state[CB_TR_ACTION_NOTICE_KEY] = "Deleted " + ", ".join(deleted) + "."
            st.rerun()
    with actions[3]:
        notice = st.session_state.pop(CB_TR_ACTION_NOTICE_KEY, "")
        if notice:
            (st.success if notice.startswith(("Created", "Deleted", "Updated")) else st.warning)(notice)
        else:
            st.caption("Assigned transverse templates remain protected until their Zones are reassigned.")

    st.markdown("#### Participation and material")
    material_rows = [
        {"Template ID": row["Template ID"], "fy (MPa)": int(round(float(row["fy MPa"]))), "Material": row["Rebar material"], "Active": row["Active"], "Credit": row["Credit inside segment"]}
        for row in rows
    ]
    material_edited = st.data_editor(
        pd.DataFrame(material_rows), use_container_width=True, hide_index=True, num_rows="fixed",
        key=f"crossbeam_tr1_material_{revision}", disabled=["Template ID"],
        column_config={
            "Template ID": st.column_config.TextColumn(width="medium"),
            "fy (MPa)": st.column_config.SelectboxColumn(options=[390,490], required=True, width="small"),
            "Material": st.column_config.SelectboxColumn(options=list(TRANSVERSE_MATERIAL_OPTIONS), required=True, width="small"),
            "Active": st.column_config.CheckboxColumn(width="small"),
            "Credit": st.column_config.CheckboxColumn("Credit in zone", width="small"),
        },
    )
    material_records = _records(material_edited)
    rows, sync_required = _material_merge(rows, material_records); _store(rows)
    if sync_required:
        _bump_revision(); st.rerun()

    hollow_rows = [row for row in rows if str(row.get("Applicable role") or "") in {"Hollow", "Any"}]
    if hollow_rows:
        st.markdown("#### Hollow web reinforcement")
        hollow_editor = st.data_editor(
            pd.DataFrame([
                {"Template ID": row["Template ID"], "Bar": row["Bar size"], "Spacing (mm)": row["Spacing mm"], "Left legs": row["Left web legs"], "Right legs": row["Right web legs"], "Closed cage": row["Closed cage"]}
                for row in hollow_rows
            ]),
            use_container_width=True, hide_index=True, num_rows="fixed", key=f"crossbeam_tr1_hollow_{revision}", disabled=["Template ID"],
            column_config={
                "Template ID": st.column_config.TextColumn(width="medium"),
                "Bar": st.column_config.SelectboxColumn(options=list(TRANSVERSE_BAR_SIZE_OPTIONS), required=True, width="small"),
                "Spacing (mm)": st.column_config.NumberColumn(min_value=25.0, step=25.0, format="%.0f", width="small"),
                "Left legs": st.column_config.NumberColumn(min_value=1, step=1, format="%d", width="small"),
                "Right legs": st.column_config.NumberColumn(min_value=1, step=1, format="%d", width="small"),
                "Closed cage": st.column_config.CheckboxColumn(width="small"),
            },
        )
        rows = _merge_fields(rows, _records(hollow_editor), {"Bar":"Bar size", "Spacing (mm)":"Spacing mm", "Left legs":"Left web legs", "Right legs":"Right web legs", "Closed cage":"Closed cage"}); _store(rows)

    solid_rows = [row for row in rows if str(row.get("Applicable role") or "") == "Solid"]
    if solid_rows:
        st.markdown("#### Solid multi-leg ties")
        solid_editor = st.data_editor(
            pd.DataFrame([
                {"Template ID": row["Template ID"], "Bar": row["Bar size"], "Spacing (mm)": row["Spacing mm"], "Effective legs": row["Effective legs"], "Closed tie": row["Closed cage"]}
                for row in solid_rows
            ]),
            use_container_width=True, hide_index=True, num_rows="fixed", key=f"crossbeam_tr1_solid_{revision}", disabled=["Template ID"],
            column_config={
                "Template ID": st.column_config.TextColumn(width="medium"),
                "Bar": st.column_config.SelectboxColumn(options=list(TRANSVERSE_BAR_SIZE_OPTIONS), required=True, width="small"),
                "Spacing (mm)": st.column_config.NumberColumn(min_value=25.0, step=25.0, format="%.0f", width="small"),
                "Effective legs": st.column_config.NumberColumn(min_value=2, step=1, format="%d", width="small"),
                "Closed tie": st.column_config.CheckboxColumn(width="small"),
            },
        )
        rows = _merge_fields(rows, _records(solid_editor), {"Bar":"Bar size", "Spacing (mm)":"Spacing mm", "Effective legs":"Effective legs", "Closed tie":"Closed cage"}); _store(rows)

    st.markdown("#### Placement within each zone")
    placement_editor = st.data_editor(
        pd.DataFrame([
            {"Template ID": row["Template ID"], "Center offset (mm)": row["Center offset mm"], "First offset (mm)": row["First bar offset mm"], "Last offset (mm)": row["Last bar offset mm"], "Status": "LOCAL ONLY"}
            for row in rows
        ]),
        use_container_width=True, hide_index=True, num_rows="fixed", key=f"crossbeam_tr1_placement_{revision}", disabled=["Template ID","Status"],
        column_config={
            "Template ID": st.column_config.TextColumn(width="medium"),
            "Center offset (mm)": st.column_config.NumberColumn(min_value=1.0, step=5.0, format="%.0f", width="small"),
            "First offset (mm)": st.column_config.NumberColumn(min_value=0.0, step=25.0, format="%.0f", width="small"),
            "Last offset (mm)": st.column_config.NumberColumn(min_value=0.0, step=25.0, format="%.0f", width="small"),
            "Status": st.column_config.TextColumn(width="small"),
        },
    )
    rows = _merge_fields(rows, _records(placement_editor), {"Center offset (mm)":"Center offset mm", "First offset (mm)":"First bar offset mm", "Last offset (mm)":"Last bar offset mm"}); _store(rows)

    st.markdown("#### Av/s input preview")
    avs = [transverse_avs_record(row) for row in rows]
    st.dataframe(
        pd.DataFrame([
            {"Template ID": row["Template ID"], "Bar @ spacing": f"{row['Bar']} @ {row['Spacing mm']:.0f}", "Av,L/s": row["Av,left/s mm²/mm"], "Av,R/s": row["Av,right/s mm²/mm"], "Av,total/s": row["Av,total/s mm²/mm"]}
            for row in avs
        ]),
        use_container_width=True, hide_index=True,
        column_config={
            "Template ID": st.column_config.TextColumn(width="medium"),
            "Bar @ spacing": st.column_config.TextColumn(width="medium"),
            "Av,L/s": st.column_config.NumberColumn(format="%.4f", width="small"),
            "Av,R/s": st.column_config.NumberColumn(format="%.4f", width="small"),
            "Av,total/s": st.column_config.NumberColumn(format="%.4f", width="small"),
        },
    )

    with st.expander("Template notes and reset", expanded=False):
        notes = st.data_editor(
            pd.DataFrame([{"Template ID":row["Template ID"], "Notes":row["Notes"]} for row in rows]), use_container_width=True, hide_index=True, num_rows="fixed",
            key=f"crossbeam_tr1_notes_{revision}", disabled=["Template ID"],
            column_config={"Template ID":st.column_config.TextColumn(width="medium"), "Notes":st.column_config.TextColumn(width="large")},
        )
        rows = _merge_fields(rows, _records(notes), {"Notes":"Notes"}); _store(rows)
        confirm_reset = st.checkbox("Confirm reset of all Transverse Templates", key=f"crossbeam_tr1_reset_confirm_{revision}")
        if st.button("Reset to Crossbeam transverse defaults", disabled=not confirm_reset, key=f"crossbeam_tr1_reset_{revision}"):
            _store(default_crossbeam_transverse_templates()); _bump_revision(); st.rerun()

    rows, errors, warnings = validate_transverse_templates(rows)
    for message in errors: st.error(message)
    for message in warnings: st.warning(message)
    return rows


def transverse_cross_section_figure(
    geometry: Any,
    definition: Mapping[str, Any],
    template: Mapping[str, Any],
    *,
    title: str,
) -> go.Figure:
    fig = create_section_preview(geometry)
    row = canonical_transverse_templates([dict(template)])[0]
    role = str(definition.get("Section role") or row.get("Applicable role") or "Solid")
    params = dict(definition.get("Parameters") or {})
    outer = list(getattr(geometry, "outer_polygon", []) or [])
    min_x = min(float(pt.x) for pt in outer); max_x = max(float(pt.x) for pt in outer)
    min_y = min(float(pt.y) for pt in outer); max_y = max(float(pt.y) for pt in outer)
    offset = float(row.get("Center offset mm") or 50.0)
    color = "#d97706"

    def add_line(x: list[float], y: list[float], name: str, showlegend: bool = False, dash: str | None = None) -> None:
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line={"color":color,"width":3, **({"dash":dash} if dash else {})}, name=name, showlegend=showlegend, hoverinfo="skip"))

    if role == "Hollow" and getattr(geometry, "holes", []):
        hole = list(geometry.holes[0])
        hmin_x = min(float(pt.x) for pt in hole); hmax_x = max(float(pt.x) for pt in hole)
        hmin_y = min(float(pt.y) for pt in hole); hmax_y = max(float(pt.y) for pt in hole)
        cages = [
            (min_x+offset, hmin_x-offset, min_y+offset, max_y-offset, int(row["Left web legs"]), "Left-web cage"),
            (hmax_x+offset, max_x-offset, min_y+offset, max_y-offset, int(row["Right web legs"]), "Right-web cage"),
        ]
        for x0,x1,y0,y1,legs,label in cages:
            if x1 <= x0 or y1 <= y0: continue
            add_line([x0,x1,x1,x0,x0],[y0,y0,y1,y1,y0], label, showlegend=(label=="Left-web cage"))
            for index in range(max(legs,1)):
                x = x0 if legs <= 1 else x0 + index*(x1-x0)/(legs-1)
                add_line([x,x],[y0,y1], f"{label} effective leg")
    else:
        x0,x1=min_x+offset,max_x-offset; y0,y1=min_y+offset,max_y-offset
        add_line([x0,x1,x1,x0,x0],[y0,y0,y1,y1,y0], "Closed tie", showlegend=True)
        legs=max(int(row.get("Effective legs") or 2),2)
        for index in range(legs):
            x=x0 + index*(x1-x0)/(legs-1)
            add_line([x,x],[y0,y1], "Effective leg")
    fig.update_layout(title={"text":title,"x":0.5,"xanchor":"center"}, height=480, margin={"l":35,"r":25,"t":70,"b":40})
    return fig


def transverse_elevation_figure(
    template: Mapping[str, Any],
    *,
    start_m: float,
    end_m: float,
    segment_id: str,
    zone_id: str,
) -> go.Figure:
    row = canonical_transverse_templates([dict(template)])[0]
    stations = transverse_set_stations(row, start_m, end_m)
    fig = go.Figure()
    fig.add_shape(type="rect", x0=start_m, x1=end_m, y0=0.0, y1=1.0, line={"color":"#526b82","width":1.2}, fillcolor="rgba(120,140,160,0.22)")
    for station in stations:
        fig.add_trace(go.Scatter(x=[station,station], y=[0.08,0.92], mode="lines", line={"color":"#d97706","width":2}, showlegend=False, hovertemplate=f"s={station:.3f} m<extra></extra>"))
    fig.add_vline(x=start_m, line={"color":"#b44444","width":1.5,"dash":"dash"})
    fig.add_vline(x=end_m, line={"color":"#b44444","width":1.5,"dash":"dash"})
    fig.add_trace(go.Scatter(x=[None,None],y=[None,None],mode="lines",line={"color":"#d97706","width":2},name="Transverse set",hoverinfo="skip"))
    fig.update_layout(
        title={"text":f"Transverse Reinforcement Elevation — {segment_id} / {zone_id}","x":0.5,"xanchor":"center"},
        height=320, margin={"l":55,"r":25,"t":70,"b":55}, paper_bgcolor="white", plot_bgcolor="white",
        xaxis={"title":"Station s (m)","range":[start_m-0.02*max(end_m-start_m,1),end_m+0.02*max(end_m-start_m,1)],"gridcolor":"#e7edf4"},
        yaxis={"title":"Schematic","range":[-0.05,1.05],"showticklabels":False,"showgrid":False},
        legend={"orientation":"h","yanchor":"bottom","y":1.02,"xanchor":"center","x":0.5},
    )
    return fig


def render_transverse_preview_summary(
    geometry: Any,
    definition: Mapping[str, Any],
    template: Mapping[str, Any],
    *,
    segment_id: str,
    zone_id: str,
    start_m: float,
    end_m: float,
    figure_config: Mapping[str, Any],
) -> None:
    row = canonical_transverse_templates([dict(template)])[0]
    avs = transverse_avs_record(row)
    stations = transverse_set_stations(row, start_m, end_m)
    render_metric_cards([
        {"title":"Transverse template","value":row["Template ID"],"detail":f"{row['Bar size']} @ {row['Spacing mm']:.0f} mm","status":"info"},
        {"title":"Effective legs","value":f"L/R {row['Left web legs']}/{row['Right web legs']}" if str(definition.get('Section role'))=='Hollow' else row['Effective legs'],"detail":"Hollow webs" if str(definition.get('Section role'))=='Hollow' else "Solid multi-leg tie","status":"info"},
        {"title":"Av,total / s","value":f"{avs['Av,total/s mm²/mm']:.4f} mm²/mm","detail":"Input preview — no φVn calculation","status":"warning"},
        {"title":"Sets in zone","value":len(stations),"detail":f"Offsets {row['First bar offset mm']:.0f}/{row['Last bar offset mm']:.0f} mm","status":"ready" if stations else "warning"},
    ])
    st.plotly_chart(transverse_cross_section_figure(geometry, definition, row, title=f"Transverse Cage Preview — {segment_id} / {zone_id} · {row['Template ID']}"), use_container_width=True, config=dict(figure_config))
    st.caption("Cross-section transverse cage/tie schematic. Longitudinal bars are omitted in this view; no code-minimum, φVn, torsion, confinement, or D-region result is implied.")
    st.plotly_chart(transverse_elevation_figure(row, start_m=start_m, end_m=end_m, segment_id=segment_id, zone_id=zone_id), use_container_width=True, config=dict(figure_config))
    st.warning("JOINT SHEAR GUARD — Transverse reinforcement terminates within the selected Segment/Zone and receives no automatic segment-joint shear-transfer credit. Shear keys, interface behavior, tendon clamping, decompression/opening, and joint shear remain separate future checks.")
