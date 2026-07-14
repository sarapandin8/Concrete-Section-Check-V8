"""Streamlit ownership for the Crossbeam section-instance library."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

import pandas as pd
import streamlit as st

from concrete_pmm_pro.core.analysis_modes import is_portal_frame_crossbeam_workflow
from concrete_pmm_pro.crossbeam.section_library import (
    CB_SECLIB_ACTIVE_ID_KEY,
    CB_SECLIB_DEFINITIONS_KEY,
    CB_SECLIB_LOADED_ID_KEY,
    CB_SECLIB_MIGRATION_KEY,
    CB_SECLIB_REVISION_KEY,
    CROSSBEAM_HOLLOW_PRESET_KEY,
    CROSSBEAM_SOLID_PRESET_KEY,
    add_default_definition,
    canonical_section_definition,
    canonical_section_definitions,
    default_section_definitions,
    definition_map,
    duplicate_definition,
    migrate_segment_rows_to_library,
    preset_display_name,
    rename_definition,
    replace_section_id_in_segments,
    section_ids_used_by_segments,
    section_property_records,
    validate_section_definitions,
)
from concrete_pmm_pro.ui.commercial import render_metric_cards, render_section_bar

SECTION_PARAMETERS_PRESET_KEY = "section_parameters_preset_key"
CB_SEGMENT_ROWS_KEY = "crossbeam_ui1_segment_layout_rows"
CB_SEGMENT_REV_KEY = "crossbeam_ui1_segment_editor_revision"
CB_SECLIB_PENDING_ACTIVE_ID_KEY = "crossbeam_seclib1_pending_active_section_id"
CB_SECLIB_NOTICE_KEY = "crossbeam_seclib1_notice"


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return [dict(row) for row in value.to_dict(orient="records")]
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _current_material_name(session_state: Mapping[str, Any]) -> str:
    return str(
        session_state.get("active_concrete_material_name")
        or session_state.get("primary_concrete_material_name")
        or "C45_PRECAST"
    )


def _set_builder_widget_state(session_state: MutableMapping[str, Any], definition: Mapping[str, Any]) -> None:
    row = canonical_section_definition(definition)
    preset_key = row["Preset key"]
    session_state["section_preset_selector_key"] = preset_key
    session_state["section_preset_key"] = preset_key
    session_state["section_preset_name"] = row["Preset family"]
    session_state["section_parameters"] = dict(row["Parameters"])
    session_state[SECTION_PARAMETERS_PRESET_KEY] = preset_key
    for name, value in row["Parameters"].items():
        session_state[f"{preset_key}_{name}"] = value
    material = str(row.get("Material") or "").strip()
    if material:
        session_state["active_concrete_material_name"] = material
        session_state["primary_concrete_material_name"] = material
    session_state[CB_SECLIB_LOADED_ID_KEY] = row["Section ID"]


def _stage_definition_selection(
    session_state: MutableMapping[str, Any],
    definitions: list[dict[str, Any]],
    active_id: str,
    *,
    notice: str = "",
) -> None:
    """Stage a library update without mutating a rendered widget key.

    Streamlit forbids writing to the session-state key owned by a selectbox
    after that widget has been instantiated in the current run.  Library
    actions therefore store a *pending* active Section ID and rerun.  The
    pending selection is applied by ``prepare_crossbeam_section_library_for_builder``
    before any Section Builder widgets are rendered on the next run.
    """

    session_state[CB_SECLIB_DEFINITIONS_KEY] = canonical_section_definitions(definitions)
    session_state[CB_SECLIB_REVISION_KEY] = int(session_state.get(CB_SECLIB_REVISION_KEY, 0) or 0) + 1
    session_state[CB_SECLIB_PENDING_ACTIVE_ID_KEY] = str(active_id)
    session_state.pop(CB_SECLIB_LOADED_ID_KEY, None)
    if notice:
        session_state[CB_SECLIB_NOTICE_KEY] = notice


def _apply_pending_definition_selection(
    session_state: MutableMapping[str, Any],
    definitions: list[dict[str, Any]],
) -> bool:
    """Apply a staged active definition before widget instantiation."""

    pending_id = str(session_state.pop(CB_SECLIB_PENDING_ACTIVE_ID_KEY, "") or "")
    if not pending_id:
        return False
    definition = definition_map(definitions).get(pending_id)
    if definition is None:
        return False
    session_state[CB_SECLIB_ACTIVE_ID_KEY] = pending_id
    _set_builder_widget_state(session_state, definition)
    return True


def ensure_crossbeam_section_library_state(session_state: MutableMapping[str, Any] | None = None) -> list[dict[str, Any]]:
    state = session_state if session_state is not None else st.session_state
    definitions = canonical_section_definitions(state.get(CB_SECLIB_DEFINITIONS_KEY))
    if not definitions:
        definitions = default_section_definitions(
            active_preset_key=str(state.get("section_preset_key") or ""),
            active_parameters=state.get("section_parameters") if isinstance(state.get("section_parameters"), Mapping) else {},
            material_name=_current_material_name(state),
        )
        state[CB_SECLIB_DEFINITIONS_KEY] = definitions

    ids = [row["Section ID"] for row in definitions]
    active_id = str(state.get(CB_SECLIB_ACTIVE_ID_KEY) or "")
    if active_id not in ids:
        preset_key = str(state.get("section_preset_key") or "")
        matching = next((row["Section ID"] for row in definitions if row["Preset key"] == preset_key), ids[0])
        state[CB_SECLIB_ACTIVE_ID_KEY] = matching
        active_id = matching

    if not state.get(CB_SECLIB_MIGRATION_KEY):
        segments = _records(state.get(CB_SEGMENT_ROWS_KEY))
        if segments:
            state[CB_SEGMENT_ROWS_KEY] = migrate_segment_rows_to_library(segments, definitions)
            state[CB_SEGMENT_REV_KEY] = int(state.get(CB_SEGMENT_REV_KEY, 0) or 0) + 1
        state[CB_SECLIB_MIGRATION_KEY] = True
    state.setdefault(CB_SECLIB_REVISION_KEY, 0)
    return definitions


def sync_active_definition_from_current_builder(session_state: MutableMapping[str, Any] | None = None) -> None:
    state = session_state if session_state is not None else st.session_state
    definitions = ensure_crossbeam_section_library_state(state)
    active_id = str(state.get(CB_SECLIB_ACTIVE_ID_KEY) or "")
    preset_key = str(state.get("section_preset_key") or "")
    params = state.get("section_parameters")
    if active_id not in definition_map(definitions) or not preset_key or not isinstance(params, Mapping):
        return
    updated: list[dict[str, Any]] = []
    for definition in definitions:
        if definition["Section ID"] != active_id:
            updated.append(definition)
            continue
        updated.append(
            canonical_section_definition(
                {
                    **definition,
                    "Preset key": preset_key,
                    "Material": _current_material_name(state),
                    "Parameters": dict(params),
                }
            )
        )
    state[CB_SECLIB_DEFINITIONS_KEY] = updated


def prepare_crossbeam_section_library_for_builder(settings: Any) -> None:
    if not is_portal_frame_crossbeam_workflow(settings):
        return
    definitions = ensure_crossbeam_section_library_state(st.session_state)
    if _apply_pending_definition_selection(st.session_state, definitions):
        return
    active_id = str(st.session_state.get(CB_SECLIB_ACTIVE_ID_KEY) or "")
    loaded_id = str(st.session_state.get(CB_SECLIB_LOADED_ID_KEY) or "")
    if loaded_id == active_id:
        # Capture the prior rerun's durable Builder values before rendering the
        # library table. The post-render hook captures the current rerun too.
        sync_active_definition_from_current_builder(st.session_state)
        return
    definition = definition_map(definitions).get(active_id)
    if definition is not None:
        _set_builder_widget_state(st.session_state, definition)


def _active_section_changed() -> None:
    definitions = ensure_crossbeam_section_library_state(st.session_state)
    active_id = str(st.session_state.get(CB_SECLIB_ACTIVE_ID_KEY) or "")
    definition = definition_map(definitions).get(active_id)
    if definition is not None:
        _set_builder_widget_state(st.session_state, definition)


def _set_definitions(definitions: list[dict[str, Any]], active_id: str, *, notice: str = "") -> None:
    _stage_definition_selection(
        st.session_state,
        definitions,
        active_id,
        notice=notice,
    )


def _section_dimension_summary(definition: Mapping[str, Any]) -> tuple[str, str]:
    """Return compact dimensions and geometry details for the visible summary table."""

    row = canonical_section_definition(definition)
    params = row["Parameters"]
    width = float(params.get("width_mm", 0.0) or 0.0)
    height = float(params.get("height_mm", 0.0) or 0.0)
    size = f"{width:.0f} × {height:.0f} mm"
    radius = float(params.get("bottom_fillet_radius_mm", 0.0) or 0.0)
    if row["Section role"] == "Hollow":
        top = float(params.get("t_top_mm", 0.0) or 0.0)
        bottom = float(params.get("t_bottom_mm", 0.0) or 0.0)
        left = float(params.get("t_left_mm", 0.0) or 0.0)
        right = float(params.get("t_right_mm", 0.0) or 0.0)
        chamfer = float(params.get("inner_chamfer_mm", 0.0) or 0.0)
        detail = (
            f"tt/tb = {top:.0f}/{bottom:.0f} mm · "
            f"tl/tr = {left:.0f}/{right:.0f} mm · R = {radius:.0f} mm · C = {chamfer:.0f} mm"
        )
    else:
        detail = f"Bottom fillet R = {radius:.0f} mm"
    return size, detail


def _project_section_summary_rows(
    definitions: list[dict[str, Any]],
    usage: Mapping[str, list[str]],
    active_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in section_property_records(definitions):
        section_id = str(record["Section ID"])
        size, geometry = _section_dimension_summary(record)
        segments = list(usage.get(section_id, []))
        rows.append(
            {
                "Active": "●" if section_id == active_id else "",
                "Section ID": section_id,
                "Section name": record["Section name"],
                "Family": record["Section role"],
                "B × H": size,
                "Geometry summary": geometry,
                "Area mm²": record["Area mm²"],
                "Centroid from top mm": record["Centroid from top mm"],
                "Ix mm⁴": record["Ix mm4"],
                "Iy mm⁴": record["Iy mm4"],
                "Segments using": ", ".join(segments) if segments else "—",
                "Status": record["Status"],
            }
        )
    return rows


def _rename_section_name_form(definitions: list[dict[str, Any]], active_id: str) -> None:
    active = definition_map(definitions)[active_id]
    with st.form(f"crossbeam_seclib1b_name_{active_id}", border=False):
        name_col, action_col = st.columns([0.78, 0.22], gap="small")
        with name_col:
            proposed_name = st.text_input(
                "Section name",
                value=active["Section name"],
                key=f"crossbeam_seclib1b_name_input_{active_id}",
                help="A user-facing project name. Section ID remains stable for Segment Layout and Project JSON references.",
            )
        with action_col:
            st.write("")
            save_name = st.form_submit_button("Save name", use_container_width=True, type="primary")
    if not save_name:
        return
    try:
        renamed = rename_definition(
            definitions,
            active_id,
            new_section_id=active_id,
            new_section_name=proposed_name,
        )
    except (ValueError, KeyError) as exc:
        st.error(str(exc))
        return
    _set_definitions(renamed, active_id, notice=f"Renamed {active_id} to {str(proposed_name).strip()}.")
    st.rerun()


def _advanced_identity_form(definitions: list[dict[str, Any]], active_id: str) -> None:
    """Allow deliberate Section-ID changes while updating every segment reference."""

    active = definition_map(definitions)[active_id]
    with st.form(f"crossbeam_seclib1b_identity_{active_id}", border=False):
        id_col, action_col = st.columns([0.78, 0.22], gap="small")
        with id_col:
            proposed_id = st.text_input(
                "Section ID",
                value=active_id,
                key=f"crossbeam_seclib1b_id_input_{active_id}",
                help="Advanced operation. Changing this ID also updates Segment Layout references.",
            )
        with action_col:
            st.write("")
            apply_id = st.form_submit_button("Update ID", use_container_width=True)
    if not apply_id:
        return
    try:
        renamed = rename_definition(
            definitions,
            active_id,
            new_section_id=proposed_id,
            new_section_name=active["Section name"],
        )
    except (ValueError, KeyError) as exc:
        st.error(str(exc))
        return
    new_id = str(proposed_id).strip()
    if new_id != active_id:
        st.session_state[CB_SEGMENT_ROWS_KEY] = replace_section_id_in_segments(
            _records(st.session_state.get(CB_SEGMENT_ROWS_KEY)), active_id, new_id
        )
        st.session_state[CB_SEGMENT_REV_KEY] = int(st.session_state.get(CB_SEGMENT_REV_KEY, 0) or 0) + 1
    _set_definitions(renamed, new_id, notice=f"Updated Section ID {active_id} → {new_id}.")
    st.rerun()


def _delete_current_section_control(
    definitions: list[dict[str, Any]],
    active_id: str,
    assigned_segments: list[str],
) -> None:
    delete_disabled = bool(assigned_segments) or len(definitions) <= 1
    if assigned_segments:
        reason = f"Cannot delete {active_id}; it is used by segments: {', '.join(assigned_segments)}. Reassign those segments first."
    elif len(definitions) <= 1:
        reason = "At least one Crossbeam project section must remain."
    else:
        reason = "This section is not assigned to any segment and may be deleted."

    st.caption(reason)
    confirm = st.checkbox(
        f"Confirm deletion of {active_id}",
        key=f"crossbeam_seclib1b_confirm_delete_{active_id}",
        disabled=delete_disabled,
    )
    if st.button(
        "Delete selected section",
        key=f"crossbeam_seclib1b_delete_{active_id}",
        use_container_width=True,
        disabled=delete_disabled or not confirm,
        help=reason,
    ):
        updated = [row for row in definitions if row["Section ID"] != active_id]
        next_id = updated[0]["Section ID"]
        _set_definitions(updated, next_id, notice=f"Deleted {active_id}; now editing {next_id}.")
        st.rerun()


def render_crossbeam_section_library_panel(settings: Any) -> None:
    if not is_portal_frame_crossbeam_workflow(settings):
        return
    definitions = ensure_crossbeam_section_library_state(st.session_state)
    definitions, errors, warnings = validate_section_definitions(definitions)
    st.session_state[CB_SECLIB_DEFINITIONS_KEY] = definitions
    ids = [row["Section ID"] for row in definitions]
    active_id = str(st.session_state.get(CB_SECLIB_ACTIVE_ID_KEY) or ids[0])
    if active_id not in ids:
        active_id = ids[0]
        st.session_state[CB_SECLIB_ACTIVE_ID_KEY] = active_id

    render_section_bar(
        "Crossbeam Project Sections",
        "Select the project section to edit. For another web/flange thickness, duplicate the current section, edit the dimensions below, then assign the new Section ID in Segment Layout.",
        mark="SL",
    )

    notice = str(st.session_state.pop(CB_SECLIB_NOTICE_KEY, "") or "")
    if notice:
        st.success(notice)

    usage = section_ids_used_by_segments(_records(st.session_state.get(CB_SEGMENT_ROWS_KEY)))
    section_map = definition_map(definitions)

    select_col, duplicate_col, hollow_col, solid_col = st.columns([0.43, 0.19, 0.19, 0.19], gap="small")
    with select_col:
        selected_active_id = st.selectbox(
            "Section to edit",
            options=ids,
            format_func=lambda section_id: f"{section_id} · {section_map[section_id]['Section name']}",
            key=CB_SECLIB_ACTIVE_ID_KEY,
            on_change=_active_section_changed,
            help="Geometry and material controls below edit only this project Section ID.",
        )
    active_id = str(selected_active_id)
    active = section_map[active_id]

    with duplicate_col:
        st.write("")
        if st.button(
            "Duplicate current",
            key="crossbeam_seclib1_duplicate",
            use_container_width=True,
            type="primary",
            help="Recommended for creating another Hollow/Solid section with different dimensions.",
        ):
            updated, new_id = duplicate_definition(definitions, active_id)
            _set_definitions(
                updated,
                new_id,
                notice=f"Created {new_id} from {active_id}. Edit its dimensions below.",
            )
            st.rerun()
    with hollow_col:
        st.write("")
        if st.button("New Hollow", key="crossbeam_seclib1_add_hollow", use_container_width=True):
            updated, new_id = add_default_definition(
                definitions,
                CROSSBEAM_HOLLOW_PRESET_KEY,
                _current_material_name(st.session_state),
            )
            _set_definitions(
                updated,
                new_id,
                notice=f"Created {new_id} — Hollow section. Edit its wall thicknesses below.",
            )
            st.rerun()
    with solid_col:
        st.write("")
        if st.button("New Solid", key="crossbeam_seclib1_add_solid", use_container_width=True):
            updated, new_id = add_default_definition(
                definitions,
                CROSSBEAM_SOLID_PRESET_KEY,
                _current_material_name(st.session_state),
            )
            _set_definitions(
                updated,
                new_id,
                notice=f"Created {new_id} — Solid section. Edit its dimensions below.",
            )
            st.rerun()

    assigned_segments = usage.get(active_id, [])
    assigned_text = ", ".join(assigned_segments) if assigned_segments else "Not assigned yet"
    st.caption(
        f"Editing **{active_id} · {active['Section name']}** · {active['Section role']} · "
        f"Used by segments: **{assigned_text}**"
    )
    st.info(
        "Fast workflow: select a section → **Duplicate current** → rename it below → change the geometry → assign the Section ID in **Segment Layout**. "
        "The preset family is fixed for each Section ID to prevent accidental topology changes."
    )

    for error in errors:
        st.error(error)
    for warning in warnings:
        st.warning(warning)

    property_rows = section_property_records(definitions)
    ready_count = sum(record["Status"] in {"READY", "REVIEW"} for record in property_rows)
    render_metric_cards(
        [
            {
                "title": "Project sections",
                "value": len(definitions),
                "detail": "Section IDs available",
                "status": "info",
            },
            {
                "title": "Solid / Hollow",
                "value": f"{sum(row['Section role'] == 'Solid' for row in definitions)} / {sum(row['Section role'] == 'Hollow' for row in definitions)}",
                "detail": "Geometry-family count",
                "status": "neutral",
            },
            {
                "title": "Geometry ready",
                "value": f"{ready_count} / {len(definitions)}",
                "detail": "Calculated gross properties",
                "status": "ready" if ready_count == len(definitions) and not errors else "warning",
            },
            {
                "title": "Assignments",
                "value": sum(len(items) for items in usage.values()),
                "detail": "Segment references",
                "status": "info",
            },
        ]
    )

    st.markdown("#### Project Section Summary")
    st.caption(
        "Visible inventory of every Solid/Hollow project section, its key dimensions, calculated gross properties, and Segment Layout usage."
    )
    summary_rows = _project_section_summary_rows(definitions, usage, active_id)
    st.dataframe(
        pd.DataFrame(summary_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Area mm²": st.column_config.NumberColumn(format="%.1f"),
            "Centroid from top mm": st.column_config.NumberColumn(format="%.2f"),
            "Ix mm⁴": st.column_config.NumberColumn(format="%.3e"),
            "Iy mm⁴": st.column_config.NumberColumn(format="%.3e"),
        },
    )

    st.markdown("#### Manage Selected Section")
    manage_name_col, manage_delete_col = st.columns([0.68, 0.32], gap="medium")
    with manage_name_col:
        st.caption(f"Stable Section ID: **{active_id}** · Edit the user-facing name without breaking Segment Layout references.")
        _rename_section_name_form(definitions, active_id)
    with manage_delete_col:
        st.caption("Deletion is guarded: assigned sections cannot be removed.")
        _delete_current_section_control(definitions, active_id, assigned_segments)

    with st.expander("Advanced Section ID management", expanded=False):
        st.warning(
            "Changing a Section ID updates every current Segment Layout reference. Use this only when the project naming convention requires it."
        )
        _advanced_identity_form(definitions, active_id)


def sync_crossbeam_section_library_after_builder(
    settings: Any,
    *,
    preset: Mapping[str, Any],
    params: Mapping[str, Any],
    material_assignment: Mapping[str, Any],
) -> None:
    if not is_portal_frame_crossbeam_workflow(settings):
        return
    definitions = ensure_crossbeam_section_library_state(st.session_state)
    active_id = str(st.session_state.get(CB_SECLIB_ACTIVE_ID_KEY) or "")
    updated: list[dict[str, Any]] = []
    for definition in definitions:
        if definition["Section ID"] != active_id:
            updated.append(definition)
            continue
        updated.append(
            canonical_section_definition(
                {
                    **definition,
                    "Preset key": str(preset.get("key") or definition["Preset key"]),
                    "Material": str(material_assignment.get("primary_material_name") or _current_material_name(st.session_state)),
                    "Parameters": dict(params),
                }
            )
        )
    st.session_state[CB_SECLIB_DEFINITIONS_KEY] = updated
    st.session_state[CB_SECLIB_LOADED_ID_KEY] = active_id
