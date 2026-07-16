"""Crossbeam-only transverse/shear reinforcement UI for TR1 through RB2G.

The page intentionally remains solver-neutral.  It stores editable local
transverse templates, computes traceable Av/s previews, and draws schematic
cross-section/elevation reinforcement without giving segment-joint shear credit.
RB2G shares geometry-aware 25 mm-bend centerlines between the transverse-only
and combined section previews. RB2G2 draws Hollow reinforcement as two closed
web loops, four flange U-bars, and four straight chamfer bars. RB-PERSIST1 keeps
the editable template library in the versioned Crossbeam Project-JSON model.
RB-EDIT1 commits the first data-editor patch for identity, material, topology,
placement, and notes tables without requiring the engineer to enter it twice.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from concrete_pmm_pro.crossbeam.editor_commit import data_editor_payload_to_records
from concrete_pmm_pro.crossbeam.rebar import canonical_rebar_zones
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_ZONE_REV_KEY,
    CB_RB_ZONE_ROWS_KEY,
    CB_TR_PREVIEW_MODE_KEY,
    CB_TR_TEMPLATE_REV_KEY,
    CB_TR_TEMPLATE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.transverse import (
    TRANSVERSE_BAR_SIZE_OPTIONS,
    TRANSVERSE_CONSTRUCTION_OPTIONS,
    TRANSVERSE_FY_BY_MATERIAL,
    TRANSVERSE_FY_OPTIONS,
    TRANSVERSE_MATERIAL_BY_FY,
    TRANSVERSE_MATERIAL_OPTIONS,
    TRANSVERSE_ROLE_OPTIONS,
    TransverseCageGeometry,
    build_transverse_cage_geometry,
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

CB_TR_ACTION_NOTICE_KEY = "crossbeam_tr1_action_notice"


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


def _transverse_source_rows(fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if CB_TR_TEMPLATE_ROWS_KEY in st.session_state:
        return canonical_transverse_templates(_records(st.session_state.get(CB_TR_TEMPLATE_ROWS_KEY)))
    return canonical_transverse_templates(fallback_rows)


def _commit_transverse_identity_editor(
    editor_key: str,
    template_rows: list[dict[str, Any]],
    fallback_editor_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
) -> None:
    """Commit the first transverse identity edit and rename Zone references."""

    source = _transverse_source_rows(template_rows)
    zones = canonical_rebar_zones(
        _records(st.session_state.get(CB_RB_ZONE_ROWS_KEY, zone_rows))
    )
    editor_rows = data_editor_payload_to_records(
        st.session_state.get(editor_key),
        fallback_editor_rows,
    )
    role_by_id = {
        str(row.get("Template ID") or ""): str(row.get("Applicable role") or "")
        for row in source
    }
    updated, updated_zones, rename_map, errors = _identity_merge(source, editor_rows, zones)
    if errors:
        return
    role_changed = any(
        role_by_id.get(str(row.get("_Original ID") or "")) != str(row.get("Role") or "")
        for row in editor_rows
        if str(row.get("_Original ID") or "") in role_by_id
    )
    _store(updated)
    if rename_map:
        st.session_state[CB_RB_ZONE_ROWS_KEY] = updated_zones
        st.session_state[CB_RB_ZONE_REV_KEY] = int(st.session_state.get(CB_RB_ZONE_REV_KEY, 0)) + 1
        st.session_state[CB_TR_ACTION_NOTICE_KEY] = "Updated Transverse Template references: " + ", ".join(
            f"{old} → {new}" for old, new in rename_map.items()
        ) + "."
    if rename_map or role_changed:
        _bump_revision()


def _commit_transverse_material_editor(
    editor_key: str,
    template_rows: list[dict[str, Any]],
    fallback_editor_rows: list[dict[str, Any]],
) -> None:
    """Commit first transverse Material/fy, Active, and Credit edits."""

    source = _transverse_source_rows(template_rows)
    editor_rows = data_editor_payload_to_records(
        st.session_state.get(editor_key),
        fallback_editor_rows,
    )
    updated, sync_required = _material_merge(source, editor_rows)
    _store(updated)
    if sync_required:
        _bump_revision()


def _commit_transverse_fields_editor(
    editor_key: str,
    template_rows: list[dict[str, Any]],
    fallback_editor_rows: list[dict[str, Any]],
    field_map: Mapping[str, str],
) -> None:
    """Commit the first topology, placement, or notes-table edit."""

    source = _transverse_source_rows(template_rows)
    editor_rows = data_editor_payload_to_records(
        st.session_state.get(editor_key),
        fallback_editor_rows,
    )
    _store(_merge_fields(source, editor_rows, field_map))


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
        st.caption(
            "Hollow templates define credited left/right web legs and display the accepted closed-loop/U-bar/chamfer-bar topology; "
            "Solid templates define effective multi-leg ties. IDs are editable and Zone references update automatically."
        )

    st.markdown("#### Template identity and row actions")
    identity_rows = [
        {
            "_Original ID": row["Template ID"], "Copy": False, "Delete": False,
            "Template ID": row["Template ID"], "Template name": row["Template name"],
            "Role": row["Applicable role"], "Construction": row["Construction"],
        }
        for row in rows
    ]
    identity_editor_key = f"crossbeam_tr1_identity_{revision}"
    edited = st.data_editor(
        pd.DataFrame(identity_rows), use_container_width=True, hide_index=True, num_rows="fixed",
        key=identity_editor_key,
        on_change=_commit_transverse_identity_editor,
        args=(identity_editor_key, rows, identity_rows, zone_rows),
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
    material_editor_key = f"crossbeam_tr1_material_{revision}"
    material_edited = st.data_editor(
        pd.DataFrame(material_rows), use_container_width=True, hide_index=True, num_rows="fixed",
        key=material_editor_key,
        on_change=_commit_transverse_material_editor,
        args=(material_editor_key, rows, material_rows),
        disabled=["Template ID"],
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
        st.markdown("#### Hollow web-leg credit and detailing topology")
        hollow_editor_rows = [
            {"Template ID": row["Template ID"], "Bar": row["Bar size"], "Spacing (mm)": row["Spacing mm"], "Left legs": row["Left web legs"], "Right legs": row["Right web legs"], "Closed cage": row["Closed cage"]}
            for row in hollow_rows
        ]
        hollow_field_map = {"Bar":"Bar size", "Spacing (mm)":"Spacing mm", "Left legs":"Left web legs", "Right legs":"Right web legs", "Closed cage":"Closed cage"}
        hollow_editor_key = f"crossbeam_tr1_hollow_{revision}"
        hollow_editor = st.data_editor(
            pd.DataFrame(hollow_editor_rows),
            use_container_width=True, hide_index=True, num_rows="fixed",
            key=hollow_editor_key,
            on_change=_commit_transverse_fields_editor,
            args=(hollow_editor_key, rows, hollow_editor_rows, hollow_field_map),
            disabled=["Template ID"],
            column_config={
                "Template ID": st.column_config.TextColumn(width="medium"),
                "Bar": st.column_config.SelectboxColumn(options=list(TRANSVERSE_BAR_SIZE_OPTIONS), required=True, width="small"),
                "Spacing (mm)": st.column_config.NumberColumn(min_value=25.0, step=25.0, format="%.0f", width="small"),
                "Left legs": st.column_config.NumberColumn(min_value=1, step=1, format="%d", width="small"),
                "Right legs": st.column_config.NumberColumn(min_value=1, step=1, format="%d", width="small"),
                "Closed cage": st.column_config.CheckboxColumn(width="small"),
            },
        )
        rows = _merge_fields(rows, _records(hollow_editor), hollow_field_map); _store(rows)

    solid_rows = [row for row in rows if str(row.get("Applicable role") or "") == "Solid"]
    if solid_rows:
        st.markdown("#### Solid multi-leg ties")
        solid_editor_rows = [
            {"Template ID": row["Template ID"], "Bar": row["Bar size"], "Spacing (mm)": row["Spacing mm"], "Effective legs": row["Effective legs"], "Closed tie": row["Closed cage"]}
            for row in solid_rows
        ]
        solid_field_map = {"Bar":"Bar size", "Spacing (mm)":"Spacing mm", "Effective legs":"Effective legs", "Closed tie":"Closed cage"}
        solid_editor_key = f"crossbeam_tr1_solid_{revision}"
        solid_editor = st.data_editor(
            pd.DataFrame(solid_editor_rows),
            use_container_width=True, hide_index=True, num_rows="fixed",
            key=solid_editor_key,
            on_change=_commit_transverse_fields_editor,
            args=(solid_editor_key, rows, solid_editor_rows, solid_field_map),
            disabled=["Template ID"],
            column_config={
                "Template ID": st.column_config.TextColumn(width="medium"),
                "Bar": st.column_config.SelectboxColumn(options=list(TRANSVERSE_BAR_SIZE_OPTIONS), required=True, width="small"),
                "Spacing (mm)": st.column_config.NumberColumn(min_value=25.0, step=25.0, format="%.0f", width="small"),
                "Effective legs": st.column_config.NumberColumn(min_value=2, step=1, format="%d", width="small"),
                "Closed tie": st.column_config.CheckboxColumn(width="small"),
            },
        )
        rows = _merge_fields(rows, _records(solid_editor), solid_field_map); _store(rows)

    st.markdown("#### Placement within each zone")
    placement_editor_rows = [
        {"Template ID": row["Template ID"], "Center offset (mm)": row["Center offset mm"], "First offset (mm)": row["First bar offset mm"], "Last offset (mm)": row["Last bar offset mm"], "Status": "LOCAL ONLY"}
        for row in rows
    ]
    placement_field_map = {"Center offset (mm)":"Center offset mm", "First offset (mm)":"First bar offset mm", "Last offset (mm)":"Last bar offset mm"}
    placement_editor_key = f"crossbeam_tr1_placement_{revision}"
    placement_editor = st.data_editor(
        pd.DataFrame(placement_editor_rows),
        use_container_width=True, hide_index=True, num_rows="fixed",
        key=placement_editor_key,
        on_change=_commit_transverse_fields_editor,
        args=(placement_editor_key, rows, placement_editor_rows, placement_field_map),
        disabled=["Template ID","Status"],
        column_config={
            "Template ID": st.column_config.TextColumn(width="medium"),
            "Center offset (mm)": st.column_config.NumberColumn(min_value=1.0, step=5.0, format="%.0f", width="small"),
            "First offset (mm)": st.column_config.NumberColumn(min_value=0.0, step=25.0, format="%.0f", width="small"),
            "Last offset (mm)": st.column_config.NumberColumn(min_value=0.0, step=25.0, format="%.0f", width="small"),
            "Status": st.column_config.TextColumn(width="small"),
        },
    )
    rows = _merge_fields(rows, _records(placement_editor), placement_field_map); _store(rows)

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
        notes_rows = [{"Template ID":row["Template ID"], "Notes":row["Notes"]} for row in rows]
        notes_field_map = {"Notes":"Notes"}
        notes_editor_key = f"crossbeam_tr1_notes_{revision}"
        notes = st.data_editor(
            pd.DataFrame(notes_rows), use_container_width=True, hide_index=True, num_rows="fixed",
            key=notes_editor_key,
            on_change=_commit_transverse_fields_editor,
            args=(notes_editor_key, rows, notes_rows, notes_field_map),
            disabled=["Template ID"],
            column_config={"Template ID":st.column_config.TextColumn(width="medium"), "Notes":st.column_config.TextColumn(width="large")},
        )
        rows = _merge_fields(rows, _records(notes), notes_field_map); _store(rows)
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
    cages = build_transverse_cage_geometry(geometry, definition, template)
    add_transverse_cage_traces(fig, cages)
    if cages.errors:
        fig.add_annotation(
            x=0.5,
            y=0.02,
            xref="paper",
            yref="paper",
            text="<b>REVIEW REQUIRED</b> — transverse cage geometry conflicts with the selected section",
            showarrow=False,
            font={"size": 11, "color": "#9b2929"},
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="rgba(155,41,41,0.45)",
            borderwidth=1,
            borderpad=4,
        )
    fig.update_layout(title={"text":title,"x":0.5,"xanchor":"center"}, height=480, margin={"l":35,"r":25,"t":70,"b":40})
    return fig


def add_transverse_cage_traces(
    fig: go.Figure,
    cages: TransverseCageGeometry,
    *,
    legend_name: str | None = None,
    color: str = "#d97706",
) -> None:
    """Add physical transverse-bar centerlines after concrete."""

    first_trace = True
    kind_names = {
        "closed_loop": "Closed loop",
        "u_bar": "U-bar",
        "straight_bar": "Straight chamfer bar",
    }
    for path in cages.paths:
        x = [point[0] for point in path.points]
        y = [point[1] for point in path.points]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                line={"color": color, "width": 3},
                name=(legend_name or path.label) if first_trace else path.label,
                showlegend=first_trace,
                hovertemplate=(
                    f"<b>{path.label}</b><br>Type={kind_names.get(path.kind, path.kind)}<br>"
                    f"Center offset={cages.center_offset_mm:.1f} mm<br>"
                    f"Preview bend radius={cages.bend_radius_mm:.1f} mm<extra></extra>"
                ),
            )
        )
        first_trace = False
        x0, x1, y0, y1 = path.envelope
        internal_legs = max(int(path.effective_legs) - 2, 0) if path.is_closed_loop else 0
        for index in range(internal_legs):
            x_leg = x0 + (index + 1) * (x1 - x0) / (internal_legs + 1)
            fig.add_trace(
                go.Scatter(
                    x=[x_leg, x_leg],
                    y=[y0, y1],
                    mode="lines",
                    line={"color": color, "width": 2.2},
                    name=f"{path.label} effective leg",
                    showlegend=False,
                    hoverinfo="skip",
                )
            )


def transverse_elevation_figure(
    template: Mapping[str, Any],
    *,
    start_m: float,
    end_m: float,
    segment_id: str,
    zone_id: str,
) -> go.Figure:
    """Backward-compatible selected-Zone elevation retained from TR1."""

    row = canonical_transverse_templates([dict(template)])[0]
    stations = transverse_set_stations(row, start_m, end_m)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[None, None],
            y=[None, None],
            mode="lines",
            line={"color": "#d97706", "width": 2},
            name="Transverse set",
            hoverinfo="skip",
        )
    )
    for station in stations:
        fig.add_trace(
            go.Scatter(
                x=[station, station],
                y=[0.08, 0.92],
                mode="lines",
                line={"color": "#d97706", "width": 1.8},
                showlegend=False,
                hovertemplate=f"<b>{zone_id}</b><br>{row['Template ID']}<br>s={station:.3f} m<extra></extra>",
            )
        )
    fig.add_shape(
        type="rect",
        x0=float(start_m),
        x1=float(end_m),
        y0=0.0,
        y1=1.0,
        fillcolor="rgba(120,140,160,0.18)",
        line={"color": "#607d94", "width": 1.4},
        layer="below",
    )
    fig.update_layout(
        title={"text": f"Transverse Reinforcement Elevation — {segment_id} / {zone_id}", "x": 0.5, "xanchor": "center"},
        height=300,
        margin={"l": 65, "r": 30, "t": 70, "b": 55},
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis={"title": "Station s (m)", "range": [float(start_m), float(end_m)], "gridcolor": "#e7edf4"},
        yaxis={"title": "Selected Zone", "range": [-0.1, 1.1], "showticklabels": False, "showgrid": False},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    )
    return fig


def transverse_full_elevation_figure(
    segment_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
    transverse_template_rows: list[dict[str, Any]],
    *,
    selected_zone_id: str = "",
) -> go.Figure:
    segments = sorted(segment_rows, key=lambda item: float(item.get("x_start_m") or 0.0))
    zones = canonical_rebar_zones(zone_rows)
    template_by_id = transverse_template_map(transverse_template_rows)
    length_m = max((float(row.get("x_end_m") or 0.0) for row in segments), default=0.0)

    fig = go.Figure()
    height = 1.0
    fills = {"Solid": "rgba(120,140,160,0.52)", "Hollow": "rgba(120,140,160,0.22)"}
    outlines = {"Solid": "#3d556b", "Hollow": "#607d94"}
    selected_zone_fill = "rgba(31,111,178,0.10)"
    selected_zone_outline = "#1f6fb2"
    transverse_line = "#d97706"
    transverse_line_muted = "rgba(217,119,6,0.65)"

    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker={"symbol":"square","size":14,"color":fills["Solid"],"line":{"color":outlines["Solid"],"width":1}}, name="Solid segment", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker={"symbol":"square","size":14,"color":fills["Hollow"],"line":{"color":outlines["Hollow"],"width":1}}, name="Hollow segment", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[None,None], y=[None,None], mode="lines", line={"color":outlines["Hollow"],"width":1.5,"dash":"dash"}, name="Hidden void boundary", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[None,None], y=[None,None], mode="lines", line={"color":transverse_line,"width":2}, name="Transverse set", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[None,None], y=[None,None], mode="lines", line={"color":selected_zone_outline,"width":5}, name="Selected zone", hoverinfo="skip"))

    segment_by_id = {str(row.get("Segment") or ""): row for row in segments}
    for row in segments:
        start = float(row.get("x_start_m") or 0.0)
        end = float(row.get("x_end_m") or start)
        role = str(row.get("Section role") or "Solid")
        section_id = str(row.get("Section ID") or "")
        section_name = str(row.get("Section name") or "")
        fig.add_shape(type="rect", x0=start, x1=end, y0=0.0, y1=height, fillcolor=fills.get(role, "rgba(160,160,160,0.20)"), line={"color": outlines.get(role, "#555"), "width": 1.5}, layer="below")
        if role == "Hollow":
            fig.add_shape(type="rect", x0=start, x1=end, y0=0.25, y1=0.75, fillcolor="rgba(0,0,0,0)", line={"color": outlines["Hollow"], "width": 1.4, "dash": "dash"}, layer="below")
        fig.add_annotation(x=(start+end)/2.0, y=0.53, text=f"<b>{row.get('Segment','')} · {section_id}</b><br>{role}", showarrow=False, font={"size":11, "color":"#17324d"})
        fig.add_annotation(x=(start+end)/2.0, y=-0.12, text=f"{end-start:.3f} m", showarrow=False, font={"size":10, "color":"#526577"})
        fig.add_trace(go.Scatter(x=[start, end, end, start, start], y=[0.0,0.0,height,height,0.0], mode="lines", line={"color": "rgba(0,0,0,0)", "width": 0}, fill="toself", fillcolor="rgba(0,0,0,0.001)", hoveron="fills", name=f"{row.get('Segment','')} hover", showlegend=False, hovertemplate=(f"<b>{row.get('Segment','')} · {section_id} · {role}</b><br>Section: {section_name}<br>Station: {start:.3f}–{end:.3f} m<br>Length: {end-start:.3f} m<extra></extra>")))

    zone_sorted = sorted(zones, key=lambda item: (float(item.get("s_start_m") or 0.0), float(item.get("s_end_m") or 0.0), str(item.get("Zone ID") or "")))
    for zone in zone_sorted:
        zone_id = str(zone.get("Zone ID") or "")
        template_id = str(zone.get("Transverse template") or "")
        template = template_by_id.get(template_id)
        if template is None:
            continue
        start_m = float(zone.get("s_start_m") or 0.0)
        end_m = float(zone.get("s_end_m") or start_m)
        segment_id = str(zone.get("Segment") or "")
        stations = transverse_set_stations(template, start_m, end_m)
        is_selected = zone_id == selected_zone_id
        line_color = transverse_line if is_selected else transverse_line_muted
        line_width = 2.2 if is_selected else 1.5
        if is_selected:
            fig.add_shape(type="rect", x0=start_m, x1=end_m, y0=-0.02, y1=1.02, fillcolor=selected_zone_fill, line={"color": selected_zone_outline, "width": 1.4}, layer="below")
        hover_text = (
            f"<b>{zone_id} · {segment_id}</b><br>"
            f"Template: {template_id}<br>"
            f"Bar / spacing: {template.get('Bar size','')} @ {float(template.get('Spacing mm') or 0.0):.0f} mm<br>"
            f"Zone: {start_m:.3f}–{end_m:.3f} m<br>"
            f"Offsets: {float(template.get('First bar offset mm') or 0.0):.0f}/{float(template.get('Last bar offset mm') or 0.0):.0f} mm<br>"
            f"Sets in zone: {len(stations)}<extra></extra>"
        )
        fig.add_trace(go.Scatter(x=[start_m, end_m, end_m, start_m, start_m], y=[0.0,0.0,height,height,0.0], mode="lines", line={"color":"rgba(0,0,0,0)", "width":0}, fill="toself", fillcolor="rgba(0,0,0,0.001)", hoveron="fills", name=f"{zone_id} hover", showlegend=False, hovertemplate=hover_text))
        for station in stations:
            fig.add_trace(go.Scatter(x=[station, station], y=[0.08, 0.92], mode="lines", line={"color": line_color, "width": line_width}, showlegend=False, hovertemplate=(f"<b>{zone_id}</b><br>{template_id}<br>s={station:.3f} m<extra></extra>")))

    for station in sorted({0.0, length_m, *[float(row.get("x_start_m") or 0.0) for row in segments], *[float(row.get("x_end_m") or 0.0) for row in segments]}):
        fig.add_shape(type="line", x0=station, x1=station, y0=-0.02, y1=1.04, line={"color":"#9b1c31","width":1})

    fig.add_trace(go.Scatter(x=[0.0, length_m], y=[0.5, 0.5], mode="markers", marker={"symbol": ["triangle-right", "triangle-left"], "size": 13, "color": "#1f6fb2"}, text=["Left anchorage", "Right anchorage"], name="Anchorage heads", showlegend=False, hovertemplate="%{text}<extra></extra>"))
    if length_m > 0:
        fig.add_annotation(x=0.0, y=0.5, text="<b>Left anchorage</b>", showarrow=True, arrowhead=2, arrowsize=0.8, arrowwidth=1.2, arrowcolor="#1f6fb2", ax=44, ay=-54, bgcolor="rgba(255,255,255,0.92)", bordercolor="#c8d6e3", borderwidth=1, font={"size": 10, "color": "#17324d"})
        fig.add_annotation(x=length_m, y=0.5, text="<b>Right anchorage</b>", showarrow=True, arrowhead=2, arrowsize=0.8, arrowwidth=1.2, arrowcolor="#1f6fb2", ax=-44, ay=-54, bgcolor="rgba(255,255,255,0.92)", bordercolor="#c8d6e3", borderwidth=1, font={"size": 10, "color": "#17324d"})

    fig.update_layout(
        title={"text":"Crossbeam Transverse Reinforcement Elevation", "x":0.5, "xanchor":"center"},
        height=380,
        margin={"l":72, "r":36, "t":96, "b":64},
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis={"title":"Station s (m)", "range":[-0.02*max(length_m,1.0), 1.02*max(length_m,1.0)], "gridcolor":"#e7edf4"},
        yaxis={"title":"Transverse set schematic", "range":[-0.22, 1.28], "showticklabels":False, "showgrid":True, "gridcolor":"#e7edf4"},
        legend={"orientation":"h", "yanchor":"bottom", "y":1.02, "xanchor":"center", "x":0.5},
        hovermode="closest",
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
    segment_rows: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
    transverse_template_rows: list[dict[str, Any]],
    figure_config: Mapping[str, Any],
) -> None:
    row = canonical_transverse_templates([dict(template)])[0]
    cages = build_transverse_cage_geometry(geometry, definition, row)
    avs = transverse_avs_record(row)
    stations = transverse_set_stations(row, start_m, end_m)
    hollow = str(definition.get("Section role")) == "Hollow"
    render_metric_cards([
        {"title":"Transverse template","value":row["Template ID"],"detail":f"{row['Bar size']} @ {row['Spacing mm']:.0f} mm","status":"info"},
        {
            "title":"Hollow topology" if hollow else "Effective legs",
            "value":f"{len(cages.closed_loops)} loops · {len(cages.u_bars)} U · {len(cages.straight_bars)} diagonal" if hollow else row["Effective legs"],
            "detail":f"Credited web legs L/R {row['Left web legs']}/{row['Right web legs']}" if hollow else "Solid multi-leg tie",
            "status":"info",
        },
        {"title":"Av,total / s","value":f"{avs['Av,total/s mm²/mm']:.4f} mm²/mm","detail":"Web-leg input only — no φVn calculation","status":"warning"},
        {"title":"Sets in zone","value":len(stations),"detail":f"Offsets {row['First bar offset mm']:.0f}/{row['Last bar offset mm']:.0f} mm","status":"ready" if stations else "warning"},
    ])
    st.plotly_chart(transverse_cross_section_figure(geometry, definition, row, title=f"Transverse Cage Preview — {segment_id} / {zone_id} · {row['Template ID']}"), use_container_width=True, config=dict(figure_config))
    if str(definition.get("Section role")) == "Hollow":
        st.caption(
            "Hollow transverse detailing topology: 2 complete closed web loops + 4 flange U-bars "
            "(Outer/Inner, Top/Bottom) + 4 straight bars parallel to the void chamfers. "
            "The 25 mm bend radius is a preview value; longitudinal bars are omitted in this view."
        )
    else:
        st.caption(
            "Solid transverse closed-tie schematic with 25 mm preview bend fillets following the outer bottom fillets. "
            "Longitudinal bars are omitted in this view."
        )
    for message in cages.errors:
        st.error(f"REVIEW REQUIRED — {message}")
    for message in cages.warnings:
        st.caption(message)
    st.caption(
        "Av/s remains based only on the template's effective web legs. The flange U-bars and chamfer bars receive no "
        "automatic capacity credit. No ACI minimum transverse reinforcement, φVn, torsion, confinement, "
        "anchorage/development, or D-region result is implied."
    )
    st.plotly_chart(
        transverse_full_elevation_figure(
            segment_rows,
            zone_rows,
            transverse_template_rows,
            selected_zone_id=zone_id,
        ),
        use_container_width=True,
        config=dict(figure_config),
    )
    st.caption("Full-length transverse reinforcement elevation. Segment boundaries, Solid/Hollow regions, and transverse sets are plotted across the entire crossbeam using each Zone's actual template spacing and first/last offsets; the selected Zone is highlighted.")
    st.warning("JOINT SHEAR GUARD — Transverse reinforcement remains local to each Segment/Zone and receives no automatic segment-joint shear-transfer credit. Shear keys, interface behavior, tendon clamping, decompression/opening, and joint shear remain separate future checks.")
