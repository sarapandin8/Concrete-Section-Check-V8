"""Workflow-scoped section workspaces for Portal Frame PC Crossbeam.

CROSSBEAM.PT1 connects longitudinal segment mapping, tendon system data, and
four-view tendon geometry to one Project-JSON source of truth.  It intentionally
contains no prestress-loss, SLS, ULS, anchorage-zone, or D-region solver.

All state keys are namespaced to the crossbeam workflow.  Legacy WF1 keys are
read for one-way in-session migration so accepted WF1/WF1A projects keep their
seed data without changing Project JSON or existing workflow behavior.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from math import isfinite
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from shapely.geometry import Point

from concrete_pmm_pro.crossbeam.section_library import (
    build_geometry_for_definition,
    canonical_section_definitions,
    definition_map as crossbeam_section_definition_map,
    migrate_segment_rows_to_library,
    section_property_records,
)
from concrete_pmm_pro.crossbeam.editor_commit import data_editor_payload_to_records
from concrete_pmm_pro.crossbeam.rebar import canonical_rebar_zones, segment_signature
from concrete_pmm_pro.crossbeam.rebar_persistence import (
    CB_RB_SEGMENT_SIGNATURE_KEY,
    CB_RB_ZONE_REV_KEY,
    CB_RB_ZONE_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.tendon import (
    DEFAULT_STRAND_SYSTEM,
    DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M,
    PROFILE_ROLE_OPTIONS,
    TENDON_PROFILE_SPAN_MODE_OPTIONS,
    TENDON_PROFILE_PRESET_OPTIONS,
    canonical_tendon_profile_points,
    canonical_tendon_system_rows,
    default_tendon_profile_points,
    normalize_tendon_profile_preset,
    normalize_tendon_profile_span_mode,
    profile_preset_point_count,
    default_tendon_system_rows,
    tendon_profile_points_for_preset,
    tendon_profile_preset_shape_preview,
    tendon_continuity_audit_rows,
    tendon_continuity_summary,
    section_context_records,
    station_section_contexts,
    tendon_station_audit_rows,
    tendon_positions_at_station,
    validate_tendon_profile,
    validate_tendon_system,
)
from concrete_pmm_pro.crossbeam.tendon_persistence import (
    CB_3D_TRANSPARENT_KEY,
    CB_ACTIVE_TENDONS_KEY,
    CB_PROFILE_REV_KEY,
    CB_PROFILE_ROWS_KEY,
    CB_TENDON_COUNT_KEY,
    CB_TENDON_SYSTEM_REV_KEY,
    CB_TENDON_SYSTEM_ROWS_KEY,
)
from concrete_pmm_pro.crossbeam.workflow import (
    DEFAULT_CROSSBEAM_LENGTH_M,
    DEFAULT_FPJ_RATIO,
    DEFAULT_JACKING_END,
    DEFAULT_STRAND_APS_MM2,
    DEFAULT_STRAND_FPU_MPA,
    DEFAULT_STRANDS_PER_TENDON,
    DEFAULT_TENDON_COUNT,
    DEFAULT_TENDON_TYPE,
    CROSSBEAM_SECTION_PRESETS,
    CROSSBEAM_SOLID_PRESET_KEY,
    CROSSBEAM_SOLID_PRESET_NAME,
    CROSSBEAM_HOLLOW_PRESET_KEY,
    CROSSBEAM_HOLLOW_PRESET_NAME,
    JACKING_END_OPTIONS,
    TENDON_TYPE_OPTIONS,
    calculated_fpj_mpa,
    default_crossbeam_segment_rows,
)
from concrete_pmm_pro.geometry.presets import load_section_presets
from concrete_pmm_pro.geometry.summary import summarize_geometry, to_shapely_polygon
from concrete_pmm_pro.ui.commercial import render_metric_cards, render_page_header, render_section_bar
from concrete_pmm_pro.ui.crossbeam_section_library import ensure_crossbeam_section_library_state
from concrete_pmm_pro.visualization.section_plot import create_section_preview


# Accepted WF1/WF1A keys retained for migration compatibility.
LEGACY_LENGTH_KEY = "crossbeam_wf1_length_m"
LEGACY_SEGMENT_ROWS_KEY = "crossbeam_wf1_segment_layout_rows"
LEGACY_TENDON_COUNT_KEY = "crossbeam_wf1_tendon_count"
LEGACY_PROFILE_ROWS_KEY = "crossbeam_wf1_tendon_profile_rows"

# CROSSBEAM.UI1 keys.  These must never be reused by another workflow.
CB_LENGTH_KEY = "crossbeam_ui1_length_m"
CB_SEGMENT_ROWS_KEY = "crossbeam_ui1_segment_layout_rows"
CB_SEGMENT_REV_KEY = "crossbeam_ui1_segment_editor_revision"
CB_UI1A_MIGRATION_KEY = "crossbeam_ui1a_segment_assignment_migrated"
CB_LENGTH_WIDGET_KEY = "crossbeam_pt1b_length_widget_m"
CB_LENGTH_WIDGET_SYNC_KEY = "crossbeam_pt1b_length_widget_synced_m"
CB_LENGTH_REPAIR_CHECK_KEY = "crossbeam_pt1b_length_repair_checked"
CB_LENGTH_REPAIR_NOTICE_KEY = "crossbeam_pt1b_length_repair_notice"
CB_LENGTH_CHANGE_POLICY_KEY = "crossbeam_pt1c_length_change_policy"
CB_LENGTH_CHANGE_NOTICE_KEY = "crossbeam_pt1c_length_change_notice"
CB_CROSS_SECTION_STATION_KEY = "crossbeam_pt1a_cross_section_station_m"
CB_CROSS_SECTION_FACE_KEY = "crossbeam_pt1a_cross_section_face"
CB_PROFILE_PRESET_KEY = "crossbeam_pt1g_profile_preset"
CB_PROFILE_PRESET_SPAN_KEY = "crossbeam_pt1h_profile_preset_span_mode"
CB_PROFILE_PRESET_OFFSET_KEY = "crossbeam_pt1g_profile_preset_offset_mm"
CB_PROFILE_PRESET_SUPPORT_WIDTH_KEY = "crossbeam_pt1j_profile_preset_support_width_m"
CB_PROFILE_PRESET_TARGETS_KEY = "crossbeam_pt1g_profile_preset_tendon_ids"
CB_PROFILE_PRESET_NOTICE_KEY = "crossbeam_pt1h_profile_preset_notice"

CB_LENGTH_POLICY_KEEP = "Keep existing stations — review required"
CB_LENGTH_POLICY_SCALE = "Scale longitudinal stations proportionally"
CB_LENGTH_CHANGE_POLICIES = (CB_LENGTH_POLICY_KEEP, CB_LENGTH_POLICY_SCALE)

CB_TENDON_REMOVE_SELECTION_KEY = "crossbeam_pt1d_remove_tendon_id"
CB_TENDON_REMOVE_PENDING_KEY = "crossbeam_pt1d_remove_pending_id"
CB_TENDON_MUTATION_NOTICE_KEY = "crossbeam_pt1d_tendon_mutation_notice"
CB_TENDON_MIN_COUNT = 3
CB_TENDON_MAX_COUNT = 64


FIGURE_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}

# CROSSBEAM.PT1E engineering-view palette.  Concrete stays deliberately
# neutral so saturated color is reserved for the tendon source-of-truth.
CROSSBEAM_3D_CONCRETE_STYLES = {
    "Solid": {
        "color": "#8EA0B2",
        "transparent_opacity": 0.14,
        "muted_opacity": 0.34,
    },
    "Hollow": {
        "color": "#C8D3DE",
        "transparent_opacity": 0.09,
        "muted_opacity": 0.22,
    },
}
CROSSBEAM_3D_OUTER_BOUNDARY_COLOR = "#334E68"
CROSSBEAM_3D_VOID_BOUNDARY_COLOR = "#6B7F93"
CROSSBEAM_3D_TENDON_COLORS = (
    "#0057B8",
    "#D95F02",
    "#00876C",
    "#7B3FC6",
    "#C2185B",
    "#8C6D1F",
    "#2F6B7C",
    "#6B4F3A",
)


def _records(value: Any) -> list[dict[str, Any]]:
    """Return a defensive list-of-records from Streamlit editor state."""

    if isinstance(value, pd.DataFrame):
        return [dict(row) for row in value.to_dict(orient="records")]
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    if isinstance(value, tuple):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _finite_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return int(default)


def _section_context() -> dict[str, float]:
    params = st.session_state.get("section_parameters")
    params = params if isinstance(params, Mapping) else {}
    geometry = st.session_state.get("section_geometry")

    width = _finite_float(params.get("width_mm"), 2500.0)
    height = _finite_float(params.get("height_mm"), 1500.0)
    centroid_from_top = height / 2.0
    if geometry is not None:
        try:
            summary = summarize_geometry(geometry)
            centroid_from_top = height - float(summary.centroid_y_from_bottom_mm)
        except Exception:
            pass

    return {
        "width_mm": max(width, 1.0),
        "height_mm": max(height, 1.0),
        "centroid_from_top_mm": centroid_from_top,
        "t_top_mm": max(_finite_float(params.get("t_top_mm"), 300.0), 1.0),
        "t_bottom_mm": max(_finite_float(params.get("t_bottom_mm"), 300.0), 1.0),
        "t_left_mm": max(_finite_float(params.get("t_left_mm"), 300.0), 1.0),
        "t_right_mm": max(_finite_float(params.get("t_right_mm"), 300.0), 1.0),
        "inner_chamfer_mm": max(_finite_float(params.get("inner_chamfer_mm"), 150.0), 0.0),
        "bottom_fillet_radius_mm": max(_finite_float(params.get("bottom_fillet_radius_mm"), 200.0), 0.0),
    }


def _legacy_profile_rows() -> list[dict[str, Any]]:
    return _records(st.session_state.get(LEGACY_PROFILE_ROWS_KEY))


def _default_profile_coordinates(
    *,
    length_m: float,
    tendon_ids: list[str],
    width_mm: float,
    height_mm: float,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
) -> dict[str, dict[str, Any]]:
    defaults = default_tendon_profile_points(
        length_m,
        tendon_ids=tendon_ids,
        width_mm=width_mm,
        height_mm=height_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
    )
    return {
        row["Tendon ID"]: row
        for row in defaults
        if row.get("Point") == "P1" and row.get("Tendon ID")
    }


def _system_rows_from_legacy(profile_rows: list[dict[str, Any]], tendon_count: int) -> list[dict[str, Any]]:
    first_by_id: dict[str, dict[str, Any]] = {}
    for row in profile_rows:
        tendon_id = str(row.get("Tendon ID") or "").strip()
        if tendon_id and tendon_id not in first_by_id:
            first_by_id[tendon_id] = row

    ids = sorted(first_by_id, key=lambda text: (_finite_int(text.removeprefix("T"), 9999), text))
    target_count = max(tendon_count, 3)
    if not ids:
        return default_tendon_system_rows(target_count)
    next_index = 1
    while len(ids) < target_count:
        candidate = f"T{next_index}"
        next_index += 1
        if candidate not in ids:
            ids.append(candidate)

    rows: list[dict[str, Any]] = []
    for tendon_id in ids:
        source = first_by_id.get(tendon_id, {})
        rows.append(
            {
                "Tendon ID": tendon_id,
                "Active": source.get("Active", True),
                "Type": str(source.get("Type") or DEFAULT_TENDON_TYPE),
                "Strands": max(_finite_int(source.get("Strands"), DEFAULT_STRANDS_PER_TENDON), 1),
                "Strand system": str(source.get("Strand system") or DEFAULT_STRAND_SYSTEM),
                "Aps/strand mm²": _finite_float(source.get("Aps/strand mm²"), DEFAULT_STRAND_APS_MM2),
                "fpu MPa": _finite_float(source.get("fpu MPa"), DEFAULT_STRAND_FPU_MPA),
                "fpj/fpu": _finite_float(source.get("fpj/fpu"), DEFAULT_FPJ_RATIO),
                "Jacking end": str(source.get("Jacking end") or DEFAULT_JACKING_END),
                "Left anchorage": "s = 0",
                "Right anchorage": "s = L",
            }
        )
    return canonical_tendon_system_rows(rows)


def _profile_points_from_legacy(
    profile_rows: list[dict[str, Any]],
    *,
    length_m: float,
    tendon_ids: list[str],
    width_mm: float,
    height_mm: float,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
) -> list[dict[str, Any]]:
    default_by_id = _default_profile_coordinates(
        length_m=length_m,
        tendon_ids=tendon_ids,
        width_mm=width_mm,
        height_mm=height_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
    )
    if not profile_rows:
        return default_tendon_profile_points(
            length_m,
            tendon_ids=tendon_ids,
            width_mm=width_mm,
            height_mm=height_mm,
            t_left_mm=t_left_mm,
            t_right_mm=t_right_mm,
        )

    points: list[dict[str, Any]] = []
    for index, row in enumerate(profile_rows):
        tendon_id = str(row.get("Tendon ID") or f"T{index + 1}").strip()
        s_ratio = _finite_float(row.get("s/L", row.get("x/L")), 0.0)
        s_m = _finite_float(row.get("s (m)", row.get("x_m")), s_ratio * length_m)
        dtop = _finite_float(row.get("dtop (mm)", row.get("Depth from top mm")), 0.18 * height_mm)
        default_coordinate = default_by_id.get(tendon_id, {})
        points.append(
            {
                "Tendon ID": tendon_id,
                "Point": str(row.get("Point") or f"P{index + 1}"),
                "s/L": s_ratio,
                "s (m)": s_m,
                "x lateral (mm)": _finite_float(row.get("x lateral (mm)"), _finite_float(default_coordinate.get("x lateral (mm)"), 0.0)),
                "dtop (mm)": dtop,
                "Curve role": str(row.get("Curve role") or ("Anchorage" if abs(s_ratio) < 1e-9 or abs(s_ratio - 1.0) < 1e-9 else "Profile point")),
            }
        )
    canonical = canonical_tendon_profile_points(points, length_m)
    represented = {row["Tendon ID"] for row in canonical}
    missing_ids = [tendon_id for tendon_id in tendon_ids if tendon_id not in represented]
    if missing_ids:
        canonical.extend(
            default_tendon_profile_points(
                length_m,
                tendon_ids=missing_ids,
                width_mm=width_mm,
                height_mm=height_mm,
                t_left_mm=t_left_mm,
                t_right_mm=t_right_mm,
            )
        )
    return canonical_tendon_profile_points(canonical, length_m)


def _crossbeam_preset_catalog() -> list[dict[str, str]]:
    """Return the two Section Builder presets available to Segment Layout.

    The catalog is defined beside the Section Builder preset keys so segment
    assignment cannot drift into arbitrary free-text section IDs.
    """

    configured_roles = {key: role for key, _name, role in CROSSBEAM_SECTION_PRESETS}
    catalog: list[dict[str, str]] = []
    try:
        for preset in load_section_presets():
            key = str(preset.get("key") or "")
            if key not in configured_roles:
                continue
            catalog.append(
                {
                    "key": key,
                    "name": str(preset.get("display_name") or key),
                    "role": configured_roles[key],
                }
            )
    except Exception:
        catalog = []

    if len(catalog) == len(CROSSBEAM_SECTION_PRESETS):
        return catalog
    return [
        {"key": key, "name": name, "role": role}
        for key, name, role in CROSSBEAM_SECTION_PRESETS
    ]


def _preset_by_name_or_key(value: Any, fallback_role: Any = None) -> dict[str, str] | None:
    text = str(value or "").strip()
    role_text = str(fallback_role or "").strip().title()
    catalog = _crossbeam_preset_catalog()
    for item in catalog:
        if text in {item["key"], item["name"]}:
            return item
    if role_text in {"Solid", "Hollow"}:
        return next((item for item in catalog if item["role"] == role_text), None)
    return None


def _crossbeam_section_definitions() -> list[dict[str, Any]]:
    return canonical_section_definitions(ensure_crossbeam_section_library_state(st.session_state))


def _crossbeam_section_definition_map() -> dict[str, dict[str, Any]]:
    return crossbeam_section_definition_map(_crossbeam_section_definitions())


def _canonical_segment_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Migrate preset-based UI1 rows to project Section ID references."""

    definitions = _crossbeam_section_definitions()
    migrated = migrate_segment_rows_to_library(rows, definitions)
    by_id = crossbeam_section_definition_map(definitions)
    canonical: list[dict[str, Any]] = []
    for index, row in enumerate(migrated):
        section_id = str(row.get("Section ID") or "").strip()
        definition = by_id.get(section_id)
        if definition is None and definitions:
            definition = definitions[index % len(definitions)]
            section_id = definition["Section ID"]
        definition = definition or {}
        canonical.append(
            {
                "Segment": str(row.get("Segment") or f"S{index + 1}"),
                "x_start_m": _finite_float(row.get("x_start_m", row.get("s_start (m)")), 0.0),
                "x_end_m": _finite_float(row.get("x_end_m", row.get("s_end (m)")), 0.0),
                "Section ID": section_id,
                "Section name": str(definition.get("Section name") or row.get("Section name") or ""),
                "Section type / preset": str(definition.get("Preset family") or row.get("Section type / preset") or ""),
                "Section preset key": str(definition.get("Preset key") or row.get("Section preset key") or ""),
                "Section role": str(definition.get("Section role") or row.get("Section role") or "Solid"),
            }
        )
    return canonical


def _segment_editor_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return editable station fields plus derived Section Library context."""

    return [
        {
            "Segment": row["Segment"],
            "x_start_m": row["x_start_m"],
            "x_end_m": row["x_end_m"],
            "Section ID": row["Section ID"],
            "Section name": row["Section name"],
            "Section role": row["Section role"],
            "Preset family": row["Section type / preset"],
        }
        for row in _canonical_segment_rows(rows)
    ]


def _rows_match_old_30m_seed(rows: list[dict[str, Any]]) -> bool:
    """Identify untouched UI1 30 m seed rows for one-time default migration."""

    if len(rows) != 6:
        return False
    expected = [0.0, 4.5, 10.5, 15.0, 19.5, 25.5, 30.0]
    canonical = sorted(_canonical_segment_rows(rows), key=lambda row: row["x_start_m"] )
    actual = [canonical[0]["x_start_m"], *[row["x_end_m"] for row in canonical]]
    return all(abs(a - b) <= 1e-6 for a, b in zip(actual, expected))


def _coherent_geometry_extent_m(
    segment_rows: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
) -> float | None:
    """Return the shared model extent when stored station geometry is coherent.

    This intentionally reads only station coordinates.  It does not migrate,
    scale, clamp, or otherwise modify any engineering row.
    """

    segments = sorted(
        [
            (
                _finite_float(row.get("x_start_m", row.get("s_start (m)")), 0.0),
                _finite_float(row.get("x_end_m", row.get("s_end (m)")), 0.0),
            )
            for row in segment_rows
        ],
        key=lambda pair: (pair[0], pair[1]),
    )
    if not segments:
        return None

    extent_m = segments[-1][1]
    tolerance = max(1e-6, abs(extent_m) * 1e-6)
    if extent_m <= 0.1 + tolerance or abs(segments[0][0]) > tolerance:
        return None
    for index, (start_m, end_m) in enumerate(segments):
        if end_m <= start_m:
            return None
        if index and abs(start_m - segments[index - 1][1]) > tolerance:
            return None

    grouped_stations: dict[str, list[float]] = {}
    for row in profile_rows:
        tendon_id = str(row.get("Tendon ID") or "").strip()
        if not tendon_id:
            return None
        station_m = _finite_float(
            row.get("s (m)", row.get("x_m")),
            _finite_float(row.get("s/L", row.get("x/L")), 0.0) * extent_m,
        )
        grouped_stations.setdefault(tendon_id, []).append(station_m)

    # Existing segment-only projects may not yet have a PT1 profile.  The
    # continuous segment range is still an unambiguous station source.
    for stations in grouped_stations.values():
        if not stations:
            return None
        if abs(min(stations)) > tolerance or abs(max(stations) - extent_m) > tolerance:
            return None
    return float(extent_m)


def _repair_stale_crossbeam_length_state(
    session_state: MutableMapping[str, Any],
) -> float | None:
    """Repair the one known 0.100 m widget sentinel from stored coordinates.

    The guard runs once per session and only when the segment/profile endpoints
    agree on a longer extent.  Coordinates and solver inputs are never moved.
    """

    if session_state.get(CB_LENGTH_REPAIR_CHECK_KEY):
        return None
    session_state[CB_LENGTH_REPAIR_CHECK_KEY] = True

    current_length_m = _finite_float(
        session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M
    )
    if abs(current_length_m - 0.1) > 1e-9:
        return None

    extent_m = _coherent_geometry_extent_m(
        _records(session_state.get(CB_SEGMENT_ROWS_KEY)),
        _records(session_state.get(CB_PROFILE_ROWS_KEY)),
    )
    if extent_m is None:
        return None

    session_state[CB_LENGTH_KEY] = extent_m
    session_state[CB_LENGTH_REPAIR_NOTICE_KEY] = (
        f"Recovered Crossbeam length L = {extent_m:.3f} m from matching stored "
        "segment/profile endpoints after a stale 0.100 m widget value. "
        "No geometry coordinates were changed."
    )
    return extent_m


def _ensure_state() -> None:
    context = _section_context()
    definitions = ensure_crossbeam_section_library_state(st.session_state)

    legacy_segments = _records(st.session_state.get(LEGACY_SEGMENT_ROWS_KEY))
    existing_segments = _records(st.session_state.get(CB_SEGMENT_ROWS_KEY))

    if CB_LENGTH_KEY not in st.session_state:
        legacy_length = _finite_float(st.session_state.get(LEGACY_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M)
        # UI1 used 30 m as its untouched seed. UI1A intentionally adopts
        # 20 m for new/default layouts while preserving genuinely edited data.
        if abs(legacy_length - 30.0) <= 1e-9 and _rows_match_old_30m_seed(legacy_segments):
            legacy_length = DEFAULT_CROSSBEAM_LENGTH_M
            legacy_segments = []
        st.session_state[CB_LENGTH_KEY] = legacy_length

    _repair_stale_crossbeam_length_state(st.session_state)

    length_m = max(_finite_float(st.session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M), 0.1)

    if CB_SEGMENT_ROWS_KEY not in st.session_state:
        seed_rows = legacy_segments or default_crossbeam_segment_rows(length_m)
        st.session_state[CB_SEGMENT_ROWS_KEY] = migrate_segment_rows_to_library(seed_rows, definitions)
    elif not st.session_state.get(CB_UI1A_MIGRATION_KEY):
        # Heal the exact UI1 seed and the observed stale 0.1 m widget state, but
        # never overwrite a custom segment layout. This runs before widgets.
        current_rows = _records(st.session_state.get(CB_SEGMENT_ROWS_KEY))
        if _rows_match_old_30m_seed(current_rows):
            st.session_state[CB_LENGTH_KEY] = DEFAULT_CROSSBEAM_LENGTH_M
            length_m = DEFAULT_CROSSBEAM_LENGTH_M
            st.session_state[CB_SEGMENT_ROWS_KEY] = migrate_segment_rows_to_library(
                default_crossbeam_segment_rows(length_m), definitions
            )
        else:
            st.session_state[CB_SEGMENT_ROWS_KEY] = _canonical_segment_rows(current_rows)
        st.session_state[CB_UI1A_MIGRATION_KEY] = True
    st.session_state.setdefault(CB_SEGMENT_REV_KEY, 0)

    legacy_profile = _legacy_profile_rows()
    if CB_TENDON_SYSTEM_ROWS_KEY not in st.session_state:
        legacy_count = max(
            _finite_int(
                st.session_state.get(LEGACY_TENDON_COUNT_KEY),
                DEFAULT_TENDON_COUNT,
            ),
            CB_TENDON_MIN_COUNT,
        )
        st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = _system_rows_from_legacy(
            legacy_profile, legacy_count
        )
    st.session_state.setdefault(CB_TENDON_SYSTEM_REV_KEY, 0)

    system_rows = canonical_tendon_system_rows(
        _records(st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY))
    )
    st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = system_rows
    # Compatibility mirror only: the table is the sole tendon-count source.
    st.session_state[CB_TENDON_COUNT_KEY] = len(system_rows)
    tendon_ids = [str(row.get("Tendon ID") or "").strip() for row in system_rows]
    tendon_ids = [item for item in tendon_ids if item]

    if CB_PROFILE_ROWS_KEY not in st.session_state:
        st.session_state[CB_PROFILE_ROWS_KEY] = _profile_points_from_legacy(
            legacy_profile,
            length_m=length_m,
            tendon_ids=tendon_ids,
            width_mm=context["width_mm"],
            height_mm=context["height_mm"],
            t_left_mm=context["t_left_mm"],
            t_right_mm=context["t_right_mm"],
        )
    else:
        st.session_state[CB_PROFILE_ROWS_KEY] = canonical_tendon_profile_points(
            _records(st.session_state.get(CB_PROFILE_ROWS_KEY)), length_m
        )
    st.session_state.setdefault(CB_PROFILE_REV_KEY, 0)
    st.session_state.setdefault(CB_ACTIVE_TENDONS_KEY, tendon_ids)
    st.session_state.setdefault(CB_3D_TRANSPARENT_KEY, True)
    if CB_CROSS_SECTION_STATION_KEY not in st.session_state:
        st.session_state[CB_CROSS_SECTION_STATION_KEY] = 0.25 * length_m
    else:
        st.session_state[CB_CROSS_SECTION_STATION_KEY] = min(
            max(_finite_float(st.session_state.get(CB_CROSS_SECTION_STATION_KEY), 0.25 * length_m), 0.0),
            length_m,
        )
    st.session_state.setdefault(CB_CROSS_SECTION_FACE_KEY, "")


def _crossbeam_member_length_m() -> float:
    _ensure_state()
    return max(
        _finite_float(st.session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M),
        0.1,
    )


def _apply_crossbeam_member_length_change(
    session_state: MutableMapping[str, Any],
    new_length_m: float,
    policy: str,
) -> dict[str, Any]:
    """Apply one explicit member-length change without touching any solver.

    ``Keep`` preserves every absolute station and lets the existing validation
    gates report mismatches. ``Scale`` changes only longitudinal station
    coordinates by ``L_new / L_old``; section geometry, tendon lateral/depth
    coordinates, material inputs, and reinforcement quantities remain intact.
    """

    old_length_m = max(
        _finite_float(session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M),
        0.1,
    )
    target_length_m = max(_finite_float(new_length_m, old_length_m), 0.1)
    if policy not in CB_LENGTH_CHANGE_POLICIES:
        raise ValueError(f"Unsupported Crossbeam length-change policy: {policy}")

    segment_rows = _records(session_state.get(CB_SEGMENT_ROWS_KEY))
    profile_rows = _records(session_state.get(CB_PROFILE_ROWS_KEY))
    zone_state_exists = CB_RB_ZONE_ROWS_KEY in session_state
    zone_rows = (
        canonical_rebar_zones(_records(session_state.get(CB_RB_ZONE_ROWS_KEY)))
        if zone_state_exists
        else []
    )
    ratio = target_length_m / old_length_m

    if policy == CB_LENGTH_POLICY_SCALE and abs(ratio - 1.0) > 1e-12:
        scaled_segments: list[dict[str, Any]] = []
        for source in segment_rows:
            row = dict(source)
            for key in ("x_start_m", "x_end_m", "s_start (m)", "s_end (m)"):
                if key in row:
                    row[key] = _finite_float(row.get(key), 0.0) * ratio
            scaled_segments.append(row)
        segment_rows = scaled_segments

        scaled_profile: list[dict[str, Any]] = []
        for source in profile_rows:
            row = dict(source)
            fallback_station_m = (
                _finite_float(row.get("s/L", row.get("x/L")), 0.0) * old_length_m
            )
            station_m = _finite_float(
                row.get("s (m)", row.get("x_m")), fallback_station_m
            )
            row["s (m)"] = station_m * ratio
            if "x_m" in row:
                row["x_m"] = station_m * ratio
            scaled_profile.append(row)
        profile_rows = scaled_profile

        scaled_zones: list[dict[str, Any]] = []
        for source in zone_rows:
            row = dict(source)
            row["s_start_m"] = _finite_float(row.get("s_start_m"), 0.0) * ratio
            row["s_end_m"] = _finite_float(row.get("s_end_m"), 0.0) * ratio
            scaled_zones.append(row)
        zone_rows = canonical_rebar_zones(scaled_zones)

    session_state[CB_LENGTH_KEY] = target_length_m
    session_state[CB_SEGMENT_ROWS_KEY] = segment_rows
    session_state[CB_PROFILE_ROWS_KEY] = canonical_tendon_profile_points(
        profile_rows, target_length_m
    )
    if (
        zone_state_exists
        and policy == CB_LENGTH_POLICY_SCALE
        and abs(ratio - 1.0) > 1e-12
    ):
        session_state[CB_RB_ZONE_ROWS_KEY] = zone_rows
        session_state[CB_RB_ZONE_REV_KEY] = int(
            session_state.get(CB_RB_ZONE_REV_KEY, 0)
        ) + 1
        if CB_RB_SEGMENT_SIGNATURE_KEY in session_state:
            session_state[CB_RB_SEGMENT_SIGNATURE_KEY] = segment_signature(
                segment_rows
            )

    current_station_m = _finite_float(
        session_state.get(CB_CROSS_SECTION_STATION_KEY),
        0.25 * old_length_m,
    )
    if policy == CB_LENGTH_POLICY_SCALE:
        current_station_m *= ratio
    session_state[CB_CROSS_SECTION_STATION_KEY] = min(
        max(current_station_m, 0.0), target_length_m
    )

    session_state[CB_SEGMENT_REV_KEY] = int(
        session_state.get(CB_SEGMENT_REV_KEY, 0)
    ) + 1
    session_state[CB_PROFILE_REV_KEY] = int(
        session_state.get(CB_PROFILE_REV_KEY, 0)
    ) + 1
    session_state[CB_LENGTH_WIDGET_SYNC_KEY] = target_length_m

    scaled = policy == CB_LENGTH_POLICY_SCALE and abs(ratio - 1.0) > 1e-12
    session_state[CB_LENGTH_CHANGE_NOTICE_KEY] = {
        "old_length_m": old_length_m,
        "new_length_m": target_length_m,
        "policy": policy,
        "scaled": scaled,
        "segment_rows": len(segment_rows),
        "profile_rows": len(profile_rows),
        "zone_rows": len(zone_rows),
    }
    return dict(session_state[CB_LENGTH_CHANGE_NOTICE_KEY])


def _commit_crossbeam_member_length_change() -> None:
    _apply_crossbeam_member_length_change(
        st.session_state,
        _finite_float(
            st.session_state.get(CB_LENGTH_WIDGET_KEY),
            st.session_state.get(CB_LENGTH_KEY, DEFAULT_CROSSBEAM_LENGTH_M),
        ),
        str(
            st.session_state.get(
                CB_LENGTH_CHANGE_POLICY_KEY, CB_LENGTH_POLICY_KEEP
            )
        ),
    )


def _cancel_crossbeam_member_length_change() -> None:
    model_length_m = max(
        _finite_float(st.session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M),
        0.1,
    )
    st.session_state[CB_LENGTH_WIDGET_KEY] = model_length_m
    st.session_state[CB_LENGTH_WIDGET_SYNC_KEY] = model_length_m


def render_crossbeam_member_length_control() -> float:
    """Render the sole editable Crossbeam member-length control.

    Section Builder owns this control. Segment Layout and Tendon Profile only
    render the read-only reference returned by ``_crossbeam_member_length_m``.
    """

    model_length_m = _crossbeam_member_length_m()
    synced_length_m = _finite_float(
        st.session_state.get(CB_LENGTH_WIDGET_SYNC_KEY), model_length_m
    )
    if (
        CB_LENGTH_WIDGET_KEY not in st.session_state
        or abs(model_length_m - synced_length_m) > 1e-9
    ):
        st.session_state[CB_LENGTH_WIDGET_KEY] = model_length_m

    repair_notice = st.session_state.pop(CB_LENGTH_REPAIR_NOTICE_KEY, None)
    if repair_notice:
        st.info(str(repair_notice))

    notice = st.session_state.pop(CB_LENGTH_CHANGE_NOTICE_KEY, None)
    if isinstance(notice, Mapping):
        old_length_m = _finite_float(notice.get("old_length_m"), model_length_m)
        new_length_m = _finite_float(notice.get("new_length_m"), model_length_m)
        if bool(notice.get("scaled")):
            st.success(
                f"Crossbeam member length changed from {old_length_m:.3f} m to "
                f"{new_length_m:.3f} m. Segment, tendon, and any existing "
                "Rebar Zone longitudinal stations were scaled proportionally "
                "by explicit selection."
            )
        else:
            st.warning(
                f"Crossbeam member length changed from {old_length_m:.3f} m to "
                f"{new_length_m:.3f} m. Existing absolute stations were kept; "
                "review Segment Layout and Tendon Profile before downstream use."
            )

    draft_length_m = float(
        st.number_input(
            "Crossbeam total length L (m)",
            min_value=0.1,
            max_value=500.0,
            step=0.5,
            format="%.3f",
            key=CB_LENGTH_WIDGET_KEY,
            help="Station s is measured from the left anchorage at s = 0 to the right anchorage at s = L.",
        )
    )
    st.caption(
        "Member-level source of truth. This value is not owned by the selected Section ID; B, H, wall thicknesses, chamfers, and fillets remain section-specific."
    )

    if abs(draft_length_m - model_length_m) <= 1e-9:
        st.caption(
            "No pending change. Segment Layout and Tendon Profile read this value and cannot edit it."
        )
        return model_length_m

    st.warning(
        f"Pending member-length change: {model_length_m:.3f} m → "
        f"{draft_length_m:.3f} m. Choose how existing longitudinal stations "
        "must be handled, then apply explicitly."
    )
    st.radio(
        "Existing station coordinates",
        CB_LENGTH_CHANGE_POLICIES,
        key=CB_LENGTH_CHANGE_POLICY_KEY,
        help=(
            "Keep preserves absolute s coordinates and activates existing review gates. "
            "Scale multiplies Segment, Tendon, and existing Rebar Zone longitudinal "
            "stations by L_new/L_old."
        ),
    )
    apply_col, cancel_col = st.columns(2)
    with apply_col:
        st.button(
            f"Apply L = {draft_length_m:.3f} m",
            key="crossbeam_pt1c_apply_member_length",
            type="primary",
            use_container_width=True,
            on_click=_commit_crossbeam_member_length_change,
        )
    with cancel_col:
        st.button(
            "Cancel pending change",
            key="crossbeam_pt1c_cancel_member_length",
            use_container_width=True,
            on_click=_cancel_crossbeam_member_length_change,
        )
    return model_length_m


def _render_crossbeam_member_length_reference() -> float:
    length_m = _crossbeam_member_length_m()
    render_metric_cards(
        [
            {
                "title": "Crossbeam member length",
                "value": f"L = {length_m:.3f} m",
                "detail": "Read-only here · edit only in Section Builder / Member Geometry",
                "status": "info",
            }
        ]
    )
    repair_notice = st.session_state.pop(CB_LENGTH_REPAIR_NOTICE_KEY, None)
    if repair_notice:
        st.info(str(repair_notice))
    return length_m


def _validate_segments(rows: list[dict[str, Any]], length_m: float) -> tuple[list[dict[str, Any]], list[str]]:
    normalized = _canonical_segment_rows(rows)
    errors: list[str] = []
    normalized.sort(key=lambda row: (row["x_start_m"], row["x_end_m"]))

    tolerance = max(1e-6, length_m * 1e-6)
    if not normalized:
        errors.append("At least one segment row is required.")
        return normalized, errors
    if abs(normalized[0]["x_start_m"]) > tolerance:
        errors.append("The first segment must start at s = 0.")
    if abs(normalized[-1]["x_end_m"] - length_m) > tolerance:
        errors.append("The final segment must end at s = L.")
    valid_ids = set(_crossbeam_section_definition_map())
    for index, row in enumerate(normalized):
        if row["x_end_m"] <= row["x_start_m"]:
            errors.append(f"{row['Segment']}: s_end must be greater than s_start.")
        if row["Section ID"] not in valid_ids:
            errors.append(f"{row['Segment']}: select a valid Crossbeam Section ID from Section Builder.")
        if index:
            previous_end = normalized[index - 1]["x_end_m"]
            if abs(row["x_start_m"] - previous_end) > tolerance:
                relation = "gap" if row["x_start_m"] > previous_end else "overlap"
                errors.append(
                    f"{normalized[index - 1]['Segment']} → {row['Segment']}: station {relation} detected."
                )
    return normalized, errors


def crossbeam_segment_layout_from_state() -> tuple[float, list[dict[str, Any]], list[str]]:
    """Return the current validated Crossbeam segment source without rendering UI.

    Workflow-scoped pages such as CROSSBEAM.RB1 use this read-only accessor so
    Segment Layout remains the single source of truth.  It does not mutate
    generic Rebar state or invoke any solver.
    """

    _ensure_state()
    length_m = max(_finite_float(st.session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M), 0.1)
    source_rows = _records(st.session_state.get(CB_SEGMENT_ROWS_KEY)) or default_crossbeam_segment_rows(length_m)
    rows, errors = _validate_segments(source_rows, length_m)
    return length_m, rows, errors


def _base_figure_layout(title: str, x_title: str, y_title: str, *, height: int = 480) -> dict[str, Any]:
    return {
        "title": {"text": title, "x": 0.5, "xanchor": "center", "font": {"size": 17}},
        "height": height,
        "margin": {"l": 72, "r": 36, "t": 70, "b": 64},
        "paper_bgcolor": "white",
        "plot_bgcolor": "white",
        "font": {"family": "Arial, sans-serif", "size": 12},
        "xaxis": {"title": x_title, "showgrid": True, "gridcolor": "#e7edf4", "zeroline": False},
        "yaxis": {"title": y_title, "showgrid": True, "gridcolor": "#e7edf4", "zeroline": False},
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
        "hovermode": "closest",
    }


def _elevation_figure(rows: list[dict[str, Any]], length_m: float) -> go.Figure:
    rows = _canonical_segment_rows(rows)
    fig = go.Figure()
    height = 1.0
    fills = {"Solid": "rgba(120,140,160,0.52)", "Hollow": "rgba(120,140,160,0.22)"}
    outlines = {"Solid": "#3d556b", "Hollow": "#607d94"}

    # Compact engineering legend.  The actual segment bodies remain layout
    # shapes so station boundaries stay exact; these traces are legend keys.
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker={"symbol": "square", "size": 14, "color": fills["Solid"], "line": {"color": outlines["Solid"], "width": 1}},
            name="Solid segment",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker={"symbol": "square", "size": 14, "color": fills["Hollow"], "line": {"color": outlines["Hollow"], "width": 1}},
            name="Hollow segment",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None, None],
            y=[None, None],
            mode="lines",
            line={"color": outlines["Hollow"], "width": 1.5, "dash": "dash"},
            name="Hidden void boundary",
            hoverinfo="skip",
        )
    )

    for row in rows:
        start = row["x_start_m"]
        end = row["x_end_m"]
        role = row["Section role"]
        preset_name = row["Section type / preset"]
        section_id = row.get("Section ID", "")
        section_name = row.get("Section name", "")
        fig.add_shape(
            type="rect",
            x0=start,
            x1=end,
            y0=0.0,
            y1=height,
            fillcolor=fills.get(role, "rgba(160,160,160,0.20)"),
            line={"color": outlines.get(role, "#555"), "width": 1.5},
            layer="below",
        )
        if role == "Hollow":
            # Elevation convention: the longitudinal void runs through the
            # complete assigned hollow segment.  Because the void is hidden
            # in elevation, show its full-length boundary with dashed lines
            # rather than a shortened solid cut-out.
            fig.add_shape(
                type="rect",
                x0=start,
                x1=end,
                y0=0.25,
                y1=0.75,
                fillcolor="rgba(0,0,0,0)",
                line={"color": outlines["Hollow"], "width": 1.4, "dash": "dash"},
                layer="below",
            )

        # Transparent hover surface keeps the visible label compact while
        # preserving the complete Section Builder preset and station audit.
        fig.add_trace(
            go.Scatter(
                x=[start, end, end, start, start],
                y=[0.0, 0.0, height, height, 0.0],
                mode="lines",
                line={"color": "rgba(0,0,0,0)", "width": 0},
                fill="toself",
                fillcolor="rgba(0,0,0,0.001)",
                hoveron="fills",
                name=f"{row['Segment']} hover",
                showlegend=False,
                hovertemplate=(
                    f"<b>{row['Segment']} · {section_id} · {role}</b><br>"
                    f"Section: {section_name}<br>"
                    f"Preset family: {preset_name}<br>"
                    f"Station: {start:.3f}–{end:.3f} m<br>"
                    f"Length: {end - start:.3f} m<extra></extra>"
                ),
            )
        )
        fig.add_annotation(
            x=(start + end) / 2.0,
            y=0.5,
            text=f"<b>{row['Segment']} · {section_id}</b><br>{role}",
            showarrow=False,
            font={"size": 11, "color": "#17324d"},
        )
        fig.add_annotation(
            x=(start + end) / 2.0,
            y=-0.12,
            text=f"{end - start:.3f} m",
            showarrow=False,
            font={"size": 10, "color": "#526577"},
        )

    for station in sorted({0.0, length_m, *[row["x_start_m"] for row in rows], *[row["x_end_m"] for row in rows]}):
        fig.add_shape(type="line", x0=station, x1=station, y0=-0.02, y1=1.04, line={"color": "#9b1c31", "width": 1})

    fig.add_trace(
        go.Scatter(
            x=[0.0, length_m],
            y=[0.5, 0.5],
            mode="markers",
            marker={"symbol": ["triangle-right", "triangle-left"], "size": 13, "color": "#1f6fb2"},
            text=["Left anchorage", "Right anchorage"],
            name="Anchorage heads",
            showlegend=False,
            hovertemplate="%{text}<extra></extra>",
        )
    )
    fig.add_annotation(
        x=0.0,
        y=0.5,
        text="<b>Left anchorage</b>",
        showarrow=True,
        arrowhead=2,
        arrowsize=0.8,
        arrowwidth=1.2,
        arrowcolor="#1f6fb2",
        ax=44,
        ay=-54,
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="#c8d6e3",
        borderwidth=1,
        font={"size": 10, "color": "#17324d"},
    )
    fig.add_annotation(
        x=length_m,
        y=0.5,
        text="<b>Right anchorage</b>",
        showarrow=True,
        arrowhead=2,
        arrowsize=0.8,
        arrowwidth=1.2,
        arrowcolor="#1f6fb2",
        ax=-44,
        ay=-54,
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="#c8d6e3",
        borderwidth=1,
        font={"size": 10, "color": "#17324d"},
    )

    fig.update_layout(**_base_figure_layout("Crossbeam Longitudinal Segment Elevation", "Station s (m)", "Section role schematic", height=510))
    fig.update_layout(
        margin={"l": 72, "r": 36, "t": 96, "b": 64},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    )
    fig.update_yaxes(range=[-0.22, 1.28], showticklabels=False, fixedrange=True)
    fig.update_xaxes(range=[-0.02 * length_m, 1.02 * length_m])
    return fig


def _tendon_ids(system_rows: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for row in system_rows:
        tendon_id = str(row.get("Tendon ID") or "").strip()
        if tendon_id and tendon_id not in ids:
            ids.append(tendon_id)
    return ids


def _system_by_id(system_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("Tendon ID") or "").strip(): row for row in system_rows if str(row.get("Tendon ID") or "").strip()}


def _editor_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _tendon_system_source_rows(fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if CB_TENDON_SYSTEM_ROWS_KEY in st.session_state:
        return canonical_tendon_system_rows(
            _records(st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY))
        )
    return canonical_tendon_system_rows(fallback_rows)


def _tendon_identity_editor_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "_Original ID": row["Tendon ID"],
            "Tendon ID": row["Tendon ID"],
            "Active": bool(row.get("Active", True)),
            "Type": row["Type"],
            "Strands": row["Strands"],
            "Jacking end": row["Jacking end"],
        }
        for row in canonical_tendon_system_rows(rows)
    ]


def _tendon_system_from_identity_editor(
    source_rows: list[dict[str, Any]],
    editor_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Merge the compact identity table and return safe atomic ID renames."""

    source = canonical_tendon_system_rows(source_rows)
    source_by_id = {row["Tendon ID"]: row for row in source if row["Tendon ID"]}
    updated: list[dict[str, Any]] = []
    original_ids: list[str] = []
    for index, item in enumerate(editor_rows):
        original_id = _editor_text(item.get("_Original ID"))
        previous = source_by_id.get(original_id)
        if previous is None and index < len(source):
            previous = source[index]
            original_id = previous["Tendon ID"]
        row = dict(previous or default_tendon_system_rows(3)[0])
        row.update(
            {
                "Tendon ID": _editor_text(item.get("Tendon ID")),
                "Active": bool(item.get("Active", True)),
                "Type": _editor_text(item.get("Type")) or DEFAULT_TENDON_TYPE,
                "Strands": _finite_int(item.get("Strands"), DEFAULT_STRANDS_PER_TENDON),
                "Jacking end": _editor_text(item.get("Jacking end")) or DEFAULT_JACKING_END,
            }
        )
        updated.append(row)
        original_ids.append(original_id)
    canonical = canonical_tendon_system_rows(updated)
    new_ids = [row["Tendon ID"] for row in canonical]
    rename_map = {
        original: new
        for original, new in zip(original_ids, new_ids)
        if original and new and original != new and new_ids.count(new) == 1
    }
    return canonical, rename_map


def _tendon_material_editor_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Tendon ID": row["Tendon ID"],
            "Strand system": row["Strand system"],
            "Aps/strand mm²": row["Aps/strand mm²"],
            "fpu MPa": row["fpu MPa"],
            "fpj/fpu": row["fpj/fpu"],
            "fpj MPa": calculated_fpj_mpa(row["fpu MPa"], row["fpj/fpu"]),
        }
        for row in canonical_tendon_system_rows(rows)
    ]


def _tendon_system_from_material_editor(
    source_rows: list[dict[str, Any]],
    editor_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {
        _editor_text(row.get("Tendon ID")): row
        for row in editor_rows
        if _editor_text(row.get("Tendon ID"))
    }
    updated: list[dict[str, Any]] = []
    for source in canonical_tendon_system_rows(source_rows):
        row = dict(source)
        edited = by_id.get(row["Tendon ID"])
        if edited is not None:
            row.update(
                {
                    "Aps/strand mm²": _finite_float(
                        edited.get("Aps/strand mm²"), DEFAULT_STRAND_APS_MM2
                    ),
                    "fpu MPa": _finite_float(
                        edited.get("fpu MPa"), DEFAULT_STRAND_FPU_MPA
                    ),
                    "fpj/fpu": _finite_float(
                        edited.get("fpj/fpu"), DEFAULT_FPJ_RATIO
                    ),
                }
            )
        updated.append(row)
    return canonical_tendon_system_rows(updated)


def _rename_tendon_profile_references(rename_map: Mapping[str, str]) -> None:
    if not rename_map:
        return
    length_m = max(
        _finite_float(st.session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M),
        0.1,
    )
    points = canonical_tendon_profile_points(
        _records(st.session_state.get(CB_PROFILE_ROWS_KEY)), length_m
    )
    for point in points:
        if point["Tendon ID"] in rename_map:
            point["Tendon ID"] = rename_map[point["Tendon ID"]]
    st.session_state[CB_PROFILE_ROWS_KEY] = canonical_tendon_profile_points(points, length_m)
    visible = [
        rename_map.get(str(value), str(value))
        for value in st.session_state.get(CB_ACTIVE_TENDONS_KEY, [])
    ]
    st.session_state[CB_ACTIVE_TENDONS_KEY] = list(dict.fromkeys(visible))
    st.session_state[CB_PROFILE_REV_KEY] = int(st.session_state.get(CB_PROFILE_REV_KEY, 0)) + 1


def _commit_tendon_identity_editor(
    editor_key: str,
    system_rows: list[dict[str, Any]],
    fallback_editor_rows: list[dict[str, Any]],
) -> None:
    source = _tendon_system_source_rows(system_rows)
    editor_rows = data_editor_payload_to_records(
        st.session_state.get(editor_key), fallback_editor_rows
    )
    updated, rename_map = _tendon_system_from_identity_editor(source, editor_rows)
    st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = updated
    if rename_map:
        _rename_tendon_profile_references(rename_map)
        st.session_state[CB_TENDON_SYSTEM_REV_KEY] = int(
            st.session_state.get(CB_TENDON_SYSTEM_REV_KEY, 0)
        ) + 1


def _commit_tendon_material_editor(
    editor_key: str,
    system_rows: list[dict[str, Any]],
    fallback_editor_rows: list[dict[str, Any]],
) -> None:
    source = _tendon_system_source_rows(system_rows)
    editor_rows = data_editor_payload_to_records(
        st.session_state.get(editor_key), fallback_editor_rows
    )
    st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = _tendon_system_from_material_editor(
        source, editor_rows
    )


def _editor_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().casefold()
    return text in {"true", "yes", "1", "on", "checked"}


def _editor_value_is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        missing = pd.isna(value)
        if isinstance(missing, bool):
            return missing
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return not value.strip()
    return False


def _profile_rows_from_editor_rows(
    editor_rows: list[dict[str, Any]],
    length_m: float,
) -> list[dict[str, Any]]:
    """Return profile rows after honoring blank dynamic rows and Delete flags."""

    usable: list[dict[str, Any]] = []
    for row in editor_rows:
        if _editor_bool(row.get("Delete row")):
            continue
        if all(
            _editor_value_is_blank(row.get(key))
            for key in (
                "Tendon ID",
                "Point",
                "s (m)",
                "x lateral (mm)",
                "dtop (mm)",
                "Curve role",
            )
        ):
            continue
        usable.append({key: value for key, value in row.items() if key != "Delete row"})
    return canonical_tendon_profile_points(usable, length_m)


def _html_escape(value: Any) -> str:
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _profile_preset_svg(
    preset: str,
    span_mode: str,
    *,
    length_m: float = DEFAULT_CROSSBEAM_LENGTH_M,
    support_width_m: float = DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M,
) -> str:
    preset = normalize_tendon_profile_preset(preset)
    span_mode = normalize_tendon_profile_span_mode(span_mode)
    points = tendon_profile_preset_shape_preview(
        preset,
        span_mode,
        length_m=length_m,
        support_width_m=support_width_m,
    )
    max_offset = max([abs(offset) for _ratio, offset, _role in points] + [1.0])
    svg_points: list[tuple[float, float, str]] = []
    for ratio, offset, role in points:
        x_value = 8.0 + 104.0 * ratio
        y_value = 22.0 + 15.0 * (offset / max_offset)
        svg_points.append((x_value, y_value, role))
    polyline = " ".join(f"{x_value:.1f},{y_value:.1f}" for x_value, y_value, _role in svg_points)
    point_nodes = "".join(
        f'<circle cx="{x_value:.1f}" cy="{y_value:.1f}" r="2.1" fill="#111827" />'
        for x_value, y_value, _role in svg_points
    )
    support_lines = ""
    if span_mode == "2 Span":
        support_lines = (
            '<line x1="60" y1="7" x2="60" y2="37" stroke="#b7c3cf" stroke-width="1" />'
        )
    return (
        '<svg viewBox="0 0 120 44" role="img" aria-label="'
        + _html_escape(f"{preset} {span_mode}")
        + '" class="pt1h-profile-svg">'
        '<rect x="4" y="6" width="112" height="32" rx="1.5" fill="#ffffff" stroke="#8fa3b7" stroke-width="1" />'
        f'{support_lines}'
        '<line x1="8" y1="22" x2="112" y2="22" stroke="#dbe3eb" stroke-width="0.8" />'
        f'<polyline points="{polyline}" fill="none" stroke="#111827" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />'
        f'{point_nodes}'
        '</svg>'
    )


def _profile_quick_start_gallery_html(
    selected_preset: str,
    *,
    length_m: float = DEFAULT_CROSSBEAM_LENGTH_M,
    support_width_m: float = DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M,
) -> str:
    selected_preset = normalize_tendon_profile_preset(selected_preset)
    single_span = TENDON_PROFILE_SPAN_MODE_OPTIONS[0]
    two_span = TENDON_PROFILE_SPAN_MODE_OPTIONS[1]
    rows = []
    for preset in TENDON_PROFILE_PRESET_OPTIONS:
        selected = preset == selected_preset
        rows.append(
            '<div class="pt1h-profile-row'
            + (" is-selected" if selected else "")
            + '">'
            '<div class="pt1h-profile-name">'
            f'<span class="pt1h-radio">{"&#9679;" if selected else "&#9675;"}</span>'
            f'<span>{_html_escape(preset)}</span>'
            '</div>'
            f'<div>{_profile_preset_svg(preset, single_span, length_m=length_m, support_width_m=support_width_m)}</div>'
            f'<div>{_profile_preset_svg(preset, two_span, length_m=length_m, support_width_m=support_width_m)}</div>'
            '</div>'
        )
    return (
        '<style>'
        '.pt1h-profile-gallery{border:1px solid #bfd3ea;border-radius:8px;background:#f8fbff;padding:10px 12px;margin:4px 0 12px 0;}'
        '.pt1h-profile-title{font-size:12px;font-weight:800;color:#16477d;margin-bottom:8px;}'
        '.pt1h-profile-header,.pt1h-profile-row{display:grid;grid-template-columns:minmax(190px,1.25fr) 132px 132px;gap:12px;align-items:center;}'
        '.pt1h-profile-header{font-size:12px;font-weight:800;color:#334155;margin-bottom:5px;padding:0 6px;}'
        '.pt1h-profile-row{border:1px solid transparent;border-radius:7px;padding:5px 6px;margin:2px 0;}'
        '.pt1h-profile-row.is-selected{background:#e8f2ff;border-color:#2d7df0;box-shadow:inset 3px 0 0 #2d7df0;}'
        '.pt1h-profile-name{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:700;color:#0f2742;}'
        '.pt1h-radio{font-size:17px;color:#2d7df0;line-height:1;}'
        '.pt1h-profile-svg{width:124px;height:46px;display:block;}'
        '@media(max-width:760px){.pt1h-profile-header,.pt1h-profile-row{grid-template-columns:1fr;}.pt1h-profile-header div:nth-child(n+2){display:none;}.pt1h-profile-svg{width:100%;max-width:210px;}}'
        '</style>'
        '<div class="pt1h-profile-gallery">'
        '<div class="pt1h-profile-title">Select A Quick Start Option</div>'
        f'<div class="pt1h-profile-header"><div></div><div>{_html_escape(single_span)}</div><div>{_html_escape(two_span)}</div></div>'
        + "".join(rows)
        + '</div>'
    )


def _commit_tendon_profile_editor(
    editor_key: str,
    fallback_editor_rows: list[dict[str, Any]],
) -> None:
    length_m = max(
        _finite_float(st.session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M),
        0.1,
    )
    editor_rows = data_editor_payload_to_records(
        st.session_state.get(editor_key), fallback_editor_rows
    )
    st.session_state[CB_PROFILE_ROWS_KEY] = _profile_rows_from_editor_rows(
        editor_rows, length_m
    )


def _apply_tendon_profile_preset(
    session_state: MutableMapping[str, Any],
    *,
    length_m: float,
    tendon_ids: list[str],
    target_tendon_ids: list[str],
    width_mm: float,
    height_mm: float,
    t_left_mm: float | None,
    t_right_mm: float | None,
    preset: str,
    span_mode: str = "Single Span",
    bend_offset_mm: float = 200.0,
    support_width_m: float = DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M,
) -> dict[str, Any]:
    preset = normalize_tendon_profile_preset(preset)
    span_mode = normalize_tendon_profile_span_mode(span_mode)
    valid_ids = [tendon_id for tendon_id in tendon_ids if tendon_id]
    valid_set = set(valid_ids)
    targets = [
        tendon_id
        for tendon_id in target_tendon_ids
        if tendon_id in valid_set
    ]
    if not targets:
        return {"action": "skipped", "profile_points": 0, "tendon_count": 0}

    length = max(_finite_float(length_m, DEFAULT_CROSSBEAM_LENGTH_M), 0.1)
    existing = canonical_tendon_profile_points(
        _records(session_state.get(CB_PROFILE_ROWS_KEY)), length
    )
    target_set = set(targets)
    preset_rows = tendon_profile_points_for_preset(
        length,
        tendon_ids=targets,
        coordinate_tendon_ids=valid_ids,
        width_mm=width_mm,
        height_mm=height_mm,
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
        preset=preset,
        span_mode=span_mode,
        bend_offset_mm=bend_offset_mm,
        support_width_m=support_width_m,
    )
    session_state[CB_PROFILE_ROWS_KEY] = canonical_tendon_profile_points(
        [row for row in existing if row["Tendon ID"] not in target_set] + preset_rows,
        length,
    )
    session_state[CB_PROFILE_REV_KEY] = int(
        session_state.get(CB_PROFILE_REV_KEY, 0)
    ) + 1
    return {
        "action": "applied",
        "preset": preset,
        "span_mode": span_mode,
        "profile_points": len(preset_rows),
        "tendon_count": len(targets),
    }


def _apply_selected_tendon_profile_preset_from_ui() -> None:
    context = _section_context()
    system_rows = _records(st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY))
    tendon_ids = _tendon_ids(system_rows)
    if not tendon_ids:
        st.session_state[CB_PROFILE_PRESET_NOTICE_KEY] = {
            "action": "skipped",
            "profile_points": 0,
            "tendon_count": 0,
        }
        return
    targets = [
        tendon_id
        for tendon_id in st.session_state.get(CB_PROFILE_PRESET_TARGETS_KEY, tendon_ids)
        if tendon_id in tendon_ids
    ] or list(tendon_ids)
    st.session_state[CB_PROFILE_PRESET_TARGETS_KEY] = targets
    preset = normalize_tendon_profile_preset(
        st.session_state.get(CB_PROFILE_PRESET_KEY)
        or TENDON_PROFILE_PRESET_OPTIONS[0]
    )
    span_mode = normalize_tendon_profile_span_mode(
        st.session_state.get(CB_PROFILE_PRESET_SPAN_KEY)
        or TENDON_PROFILE_SPAN_MODE_OPTIONS[0]
    )
    st.session_state[CB_PROFILE_PRESET_KEY] = preset
    st.session_state[CB_PROFILE_PRESET_SPAN_KEY] = span_mode
    notice = _apply_tendon_profile_preset(
        st.session_state,
        length_m=_finite_float(
            st.session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M
        ),
        tendon_ids=tendon_ids,
        target_tendon_ids=targets,
        width_mm=context["width_mm"],
        height_mm=context["height_mm"],
        t_left_mm=context["t_left_mm"],
        t_right_mm=context["t_right_mm"],
        preset=preset,
        span_mode=span_mode,
        bend_offset_mm=_finite_float(
            st.session_state.get(CB_PROFILE_PRESET_OFFSET_KEY), 200.0
        ),
        support_width_m=_finite_float(
            st.session_state.get(CB_PROFILE_PRESET_SUPPORT_WIDTH_KEY),
            DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M,
        ),
    )
    st.session_state[CB_PROFILE_PRESET_NOTICE_KEY] = notice


def _next_crossbeam_tendon_id(
    system_rows: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
) -> str:
    """Return the first unused stable T-number across system and profile rows."""

    used = {
        str(row.get("Tendon ID") or "").strip()
        for row in [*system_rows, *profile_rows]
        if str(row.get("Tendon ID") or "").strip()
    }
    for index in range(1, CB_TENDON_MAX_COUNT + 1):
        candidate = f"T{index}"
        if candidate not in used:
            return candidate
    raise ValueError("No unused Tendon ID is available within the 64-tendon limit.")


def _add_crossbeam_tendon(
    session_state: MutableMapping[str, Any],
    *,
    length_m: float,
    width_mm: float,
    height_mm: float,
    t_left_mm: float | None = None,
    t_right_mm: float | None = None,
) -> dict[str, Any]:
    """Append one complete tendon and its three default profile points."""

    system_rows = canonical_tendon_system_rows(
        _records(session_state.get(CB_TENDON_SYSTEM_ROWS_KEY))
    )
    if len(system_rows) >= CB_TENDON_MAX_COUNT:
        raise ValueError(
            f"Crossbeam Tendon System is limited to {CB_TENDON_MAX_COUNT} stored tendons."
        )

    length = max(_finite_float(length_m, DEFAULT_CROSSBEAM_LENGTH_M), 0.1)
    profile_rows = canonical_tendon_profile_points(
        _records(session_state.get(CB_PROFILE_ROWS_KEY)), length
    )
    tendon_id = _next_crossbeam_tendon_id(system_rows, profile_rows)
    new_row = dict(default_tendon_system_rows(CB_TENDON_MIN_COUNT)[0])
    new_row["Tendon ID"] = tendon_id
    system_rows = canonical_tendon_system_rows([*system_rows, new_row])

    default_points = default_tendon_profile_points(
        length,
        tendon_ids=[row["Tendon ID"] for row in system_rows if row["Tendon ID"]],
        width_mm=max(_finite_float(width_mm, 2500.0), 1.0),
        height_mm=max(_finite_float(height_mm, 1500.0), 1.0),
        t_left_mm=t_left_mm,
        t_right_mm=t_right_mm,
    )
    new_points = [row for row in default_points if row["Tendon ID"] == tendon_id]
    profile_rows = canonical_tendon_profile_points(
        [*profile_rows, *new_points], length
    )
    valid_ids = {row["Tendon ID"] for row in system_rows if row["Tendon ID"]}
    visible_ids = [
        str(value)
        for value in session_state.get(CB_ACTIVE_TENDONS_KEY, [])
        if str(value) in valid_ids
    ]
    if tendon_id not in visible_ids:
        visible_ids.append(tendon_id)

    session_state[CB_TENDON_SYSTEM_ROWS_KEY] = system_rows
    session_state[CB_PROFILE_ROWS_KEY] = profile_rows
    session_state[CB_TENDON_COUNT_KEY] = len(system_rows)
    session_state[CB_ACTIVE_TENDONS_KEY] = visible_ids
    session_state[CB_TENDON_SYSTEM_REV_KEY] = int(
        session_state.get(CB_TENDON_SYSTEM_REV_KEY, 0)
    ) + 1
    session_state[CB_PROFILE_REV_KEY] = int(
        session_state.get(CB_PROFILE_REV_KEY, 0)
    ) + 1
    notice = {
        "action": "added",
        "tendon_id": tendon_id,
        "stored_count": len(system_rows),
        "profile_points": len(new_points),
    }
    session_state[CB_TENDON_MUTATION_NOTICE_KEY] = notice
    return dict(notice)


def _remove_crossbeam_tendon(
    session_state: MutableMapping[str, Any],
    tendon_id: str,
) -> dict[str, Any]:
    """Remove exactly one stored tendon and every linked profile point."""

    system_rows = canonical_tendon_system_rows(
        _records(session_state.get(CB_TENDON_SYSTEM_ROWS_KEY))
    )
    if len(system_rows) <= CB_TENDON_MIN_COUNT:
        raise ValueError(
            f"At least {CB_TENDON_MIN_COUNT} stored tendons are required."
        )
    target = str(tendon_id or "").strip()
    matches = [row for row in system_rows if row["Tendon ID"] == target]
    if len(matches) != 1:
        raise ValueError(
            f"Removal requires one unique stored Tendon ID; found {len(matches)} row(s) for {target or 'blank ID'}."
        )

    remaining = [row for row in system_rows if row["Tendon ID"] != target]
    length = max(
        _finite_float(
            session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M
        ),
        0.1,
    )
    profile_before = canonical_tendon_profile_points(
        _records(session_state.get(CB_PROFILE_ROWS_KEY)), length
    )
    profile_after = [
        row for row in profile_before if row["Tendon ID"] != target
    ]
    valid_ids = {row["Tendon ID"] for row in remaining if row["Tendon ID"]}
    visible_ids = [
        str(value)
        for value in session_state.get(CB_ACTIVE_TENDONS_KEY, [])
        if str(value) in valid_ids
    ]

    session_state[CB_TENDON_SYSTEM_ROWS_KEY] = remaining
    session_state[CB_PROFILE_ROWS_KEY] = profile_after
    session_state[CB_TENDON_COUNT_KEY] = len(remaining)
    session_state[CB_ACTIVE_TENDONS_KEY] = visible_ids
    session_state[CB_TENDON_SYSTEM_REV_KEY] = int(
        session_state.get(CB_TENDON_SYSTEM_REV_KEY, 0)
    ) + 1
    session_state[CB_PROFILE_REV_KEY] = int(
        session_state.get(CB_PROFILE_REV_KEY, 0)
    ) + 1
    notice = {
        "action": "removed",
        "tendon_id": target,
        "stored_count": len(remaining),
        "profile_points": len(profile_before) - len(profile_after),
    }
    session_state[CB_TENDON_MUTATION_NOTICE_KEY] = notice
    return dict(notice)


def _add_crossbeam_tendon_from_ui() -> None:
    context = _section_context()
    _add_crossbeam_tendon(
        st.session_state,
        length_m=_finite_float(
            st.session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M
        ),
        width_mm=context["width_mm"],
        height_mm=context["height_mm"],
        t_left_mm=context["t_left_mm"],
        t_right_mm=context["t_right_mm"],
    )


def _request_crossbeam_tendon_removal() -> None:
    selected = str(
        st.session_state.get(CB_TENDON_REMOVE_SELECTION_KEY) or ""
    ).strip()
    if selected:
        st.session_state[CB_TENDON_REMOVE_PENDING_KEY] = selected


def _cancel_crossbeam_tendon_removal() -> None:
    st.session_state.pop(CB_TENDON_REMOVE_PENDING_KEY, None)


def _confirm_crossbeam_tendon_removal() -> None:
    target = str(
        st.session_state.get(CB_TENDON_REMOVE_PENDING_KEY) or ""
    ).strip()
    _remove_crossbeam_tendon(st.session_state, target)
    remaining_ids = _tendon_ids(
        _records(st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY))
    )
    if remaining_ids:
        st.session_state[CB_TENDON_REMOVE_SELECTION_KEY] = remaining_ids[-1]
    else:
        st.session_state.pop(CB_TENDON_REMOVE_SELECTION_KEY, None)
    st.session_state.pop(CB_TENDON_REMOVE_PENDING_KEY, None)


def _reset_crossbeam_tendon_system_from_ui() -> None:
    length_m = max(
        _finite_float(
            st.session_state.get(CB_LENGTH_KEY), DEFAULT_CROSSBEAM_LENGTH_M
        ),
        0.1,
    )
    context = _section_context()
    system_rows = default_tendon_system_rows()
    tendon_ids = [row["Tendon ID"] for row in system_rows]
    st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = system_rows
    st.session_state[CB_PROFILE_ROWS_KEY] = default_tendon_profile_points(
        length_m,
        tendon_ids=tendon_ids,
        width_mm=context["width_mm"],
        height_mm=context["height_mm"],
        t_left_mm=context["t_left_mm"],
        t_right_mm=context["t_right_mm"],
    )
    st.session_state[CB_TENDON_COUNT_KEY] = len(system_rows)
    st.session_state[CB_ACTIVE_TENDONS_KEY] = tendon_ids
    st.session_state[CB_TENDON_SYSTEM_REV_KEY] = int(
        st.session_state.get(CB_TENDON_SYSTEM_REV_KEY, 0)
    ) + 1
    st.session_state[CB_PROFILE_REV_KEY] = int(
        st.session_state.get(CB_PROFILE_REV_KEY, 0)
    ) + 1
    st.session_state[CB_TENDON_REMOVE_SELECTION_KEY] = tendon_ids[-1]
    st.session_state.pop(CB_TENDON_REMOVE_PENDING_KEY, None)
    st.session_state[CB_TENDON_MUTATION_NOTICE_KEY] = {
        "action": "reset",
        "stored_count": len(system_rows),
        "profile_points": len(tendon_ids) * 3,
    }


def _segment_bands(fig: go.Figure, segment_rows: list[dict[str, Any]]) -> None:
    fills = {"Solid": "rgba(31,119,180,0.055)", "Hollow": "rgba(255,127,14,0.055)"}
    for row in segment_rows:
        fig.add_vrect(
            x0=row["x_start_m"],
            x1=row["x_end_m"],
            fillcolor=fills.get(row["Section role"], "rgba(120,120,120,0.035)"),
            opacity=1,
            line_width=0,
            layer="below",
            annotation_text=row["Segment"],
            annotation_position="top left",
        )


def _section_parameters_by_id(
    section_definitions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("Section ID") or ""): dict(
            row.get("Parameters") if isinstance(row.get("Parameters"), Mapping) else {}
        )
        for row in canonical_section_definitions(section_definitions)
    }


def _plan_figure(
    points: list[dict[str, Any]],
    active_ids: list[str],
    segment_rows: list[dict[str, Any]],
    section_definitions: list[dict[str, Any]],
) -> go.Figure:
    fig = go.Figure()
    params_by_id = _section_parameters_by_id(section_definitions)
    widths: list[float] = []
    for row in segment_rows:
        params = params_by_id.get(str(row.get("Section ID") or ""), {})
        width = max(_finite_float(params.get("width_mm"), 2500.0), 1.0)
        widths.append(width)
        fig.add_shape(
            type="rect",
            x0=row["x_start_m"],
            x1=row["x_end_m"],
            y0=-0.5 * width,
            y1=0.5 * width,
            fillcolor="rgba(49,70,90,0.035)",
            line={"color": "#708396", "width": 1},
            layer="below",
        )
        fig.add_annotation(
            x=0.5 * (row["x_start_m"] + row["x_end_m"]),
            y=0.5 * width,
            text=f"{row['Segment']} · {row.get('Section ID', '')}",
            showarrow=False,
            yshift=10,
            font={"size": 9, "color": "#526577"},
        )
    for tendon_id in active_ids:
        rows = [row for row in points if row["Tendon ID"] == tendon_id]
        rows.sort(key=lambda row: row["s (m)"])
        if not rows:
            continue
        fig.add_trace(
            go.Scatter(
                x=[row["s (m)"] for row in rows],
                y=[row["x lateral (mm)"] for row in rows],
                mode="lines+markers",
                name=tendon_id,
                customdata=[[row["Point"], row["Curve role"]] for row in rows],
                hovertemplate="%{fullData.name}<br>s=%{x:.3f} m<br>x=%{y:.1f} mm<br>%{customdata[0]} · %{customdata[1]}<extra></extra>",
            )
        )
    fig.add_hline(y=0.0, line={"color": "#7b8794", "dash": "dot"}, annotation_text="Crossbeam CL")
    fig.update_layout(**_base_figure_layout("Tendon Plan", "Station s (m)", "Lateral position x (mm)", height=470))
    max_width = max(widths, default=2500.0)
    fig.update_yaxes(range=[-0.58 * max_width, 0.58 * max_width])
    return fig


def _profile_figure(
    points: list[dict[str, Any]],
    active_ids: list[str],
    segment_rows: list[dict[str, Any]],
    section_definitions: list[dict[str, Any]],
) -> go.Figure:
    fig = go.Figure()
    _segment_bands(fig, segment_rows)
    params_by_id = _section_parameters_by_id(section_definitions)
    centroid_by_id = {
        section_id: _finite_float(context.get("Centroid from top mm"), 0.0)
        for section_id, context in section_context_records(section_definitions).items()
    }
    heights: list[float] = []
    for index, segment in enumerate(segment_rows):
        section_id = str(segment.get("Section ID") or "")
        params = params_by_id.get(section_id, {})
        height = max(_finite_float(params.get("height_mm"), 1500.0), 1.0)
        centroid = _finite_float(centroid_by_id.get(section_id), 0.5 * height)
        heights.append(height)
        fig.add_trace(
            go.Scatter(
                x=[segment["x_start_m"], segment["x_end_m"]],
                y=[height, height],
                mode="lines",
                line={"color": "#31465a", "width": 1.4},
                name="Bottom surface by Section ID",
                legendgroup="section-bottom",
                showlegend=index == 0,
                hovertemplate=f"{segment['Segment']} · {section_id}<br>Bottom dtop={height:.1f} mm<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[segment["x_start_m"], segment["x_end_m"]],
                y=[centroid, centroid],
                mode="lines",
                line={"color": "#9b1c31", "width": 1.2, "dash": "dot"},
                name="Section centroid by Section ID",
                legendgroup="section-centroid",
                showlegend=index == 0,
                hovertemplate=f"{segment['Segment']} · {section_id}<br>Centroid dtop={centroid:.1f} mm<extra></extra>",
            )
        )
    for tendon_id in active_ids:
        rows = [row for row in points if row["Tendon ID"] == tendon_id]
        rows.sort(key=lambda row: row["s (m)"])
        if not rows:
            continue
        fig.add_trace(
            go.Scatter(
                x=[row["s (m)"] for row in rows],
                y=[row["dtop (mm)"] for row in rows],
                mode="lines+markers",
                name=tendon_id,
                customdata=[[row["Point"], row["Curve role"]] for row in rows],
                hovertemplate="%{fullData.name}<br>s=%{x:.3f} m<br>dtop=%{y:.1f} mm<br>%{customdata[0]} · %{customdata[1]}<extra></extra>",
            )
        )
    fig.add_hline(y=0.0, line={"color": "#31465a", "width": 1.4}, annotation_text="Top surface")
    fig.update_layout(**_base_figure_layout("Tendon Elevation — s–dtop from Top Surface", "Station s (m)", "Depth from top dtop (mm)", height=500))
    max_height = max(heights, default=1500.0)
    fig.update_yaxes(range=[max_height * 1.08, -max_height * 0.08])
    return fig


def _cross_section_figure(
    definition: Mapping[str, Any],
    tendon_positions: list[dict[str, Any]],
    *,
    station_m: float,
    segment_id: str,
    station_face: str,
) -> tuple[go.Figure, list[dict[str, Any]]]:
    """Return a true Section-ID cross section with interpolated tendon centers."""

    geometry = build_geometry_for_definition(definition)
    fig = create_section_preview(geometry)
    concrete = to_shapely_polygon(geometry)
    _min_x, _min_y, _max_x, top_y = concrete.bounds
    fit_rows: list[dict[str, Any]] = []
    marker_groups: dict[str, list[dict[str, Any]]] = {
        "Internal tendon — in concrete": [],
        "Internal tendon — outside/void": [],
        "External tendon": [],
    }

    for position in tendon_positions:
        section_y = top_y - _finite_float(position.get("dtop (mm)"), 0.0)
        x_mm = _finite_float(position.get("x lateral (mm)"), 0.0)
        inside = bool(concrete.covers(Point(x_mm, section_y)))
        tendon_type = str(position.get("Type") or "Internal")
        if tendon_type == "External":
            group = "External tendon"
            fit = "EXTERNAL — LOCATION SHOWN"
        elif inside:
            group = "Internal tendon — in concrete"
            fit = "IN CONCRETE"
        else:
            group = "Internal tendon — outside/void"
            fit = "OUTSIDE / VOID — REVIEW"
        item = {
            **position,
            "section y (mm)": section_y,
            "Inside concrete": inside,
            "Cross-section fit": fit,
        }
        marker_groups[group].append(item)
        fit_rows.append(item)

    styles = {
        "Internal tendon — in concrete": {"color": "#155a9c", "symbol": "circle"},
        "Internal tendon — outside/void": {"color": "#c62828", "symbol": "x"},
        "External tendon": {"color": "#d97706", "symbol": "diamond"},
    }
    for name, rows in marker_groups.items():
        if not rows:
            continue
        style = styles[name]
        fig.add_trace(
            go.Scatter(
                x=[row["x lateral (mm)"] for row in rows],
                y=[row["section y (mm)"] for row in rows],
                mode="markers+text",
                marker={
                    "size": 13,
                    "color": style["color"],
                    "symbol": style["symbol"],
                    "line": {"color": "#ffffff", "width": 1.2},
                },
                text=[row["Tendon ID"] for row in rows],
                textposition="top center",
                customdata=[
                    [
                        row["Type"],
                        row["dtop (mm)"],
                        row["Cross-section fit"],
                        row["Left point"],
                        row["Right point"],
                    ]
                    for row in rows
                ],
                hovertemplate=(
                    "%{text}<br>Type=%{customdata[0]}<br>x=%{x:.1f} mm"
                    "<br>dtop=%{customdata[1]:.1f} mm<br>%{customdata[2]}"
                    "<br>Interpolation=%{customdata[3]} → %{customdata[4]}<extra></extra>"
                ),
                name=name,
            )
        )

    for trace in fig.data:
        if str(getattr(trace, "name", "")).startswith("Hole"):
            trace.name = "Void"
    section_id = str(definition.get("Section ID") or "")
    fig.add_annotation(
        x=0.0,
        y=top_y,
        text="Top surface · dtop = 0",
        showarrow=True,
        arrowhead=2,
        ax=0,
        ay=-32,
        bgcolor="rgba(255,255,255,0.90)",
        bordercolor="#cbd5e1",
        font={"size": 10, "color": "#17324d"},
    )
    fig.update_layout(
        title={
            "text": f"Tendon Cross Section — s = {station_m:.3f} m · {segment_id} / {section_id} · {station_face}",
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 16, "color": "#071a33"},
        },
        height=610,
        margin={"l": 50, "r": 35, "t": 90, "b": 50},
    )
    fig.update_xaxes(title="Lateral x (mm)")
    fig.update_yaxes(title="Section y (mm) · tendon ordinate = top y − dtop")
    return fig, fit_rows


def _box_mesh(
    *,
    s0: float,
    s1: float,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    name: str,
    color: str,
    opacity: float,
    showlegend: bool,
) -> go.Mesh3d:
    # Coordinates: Plotly X = longitudinal s, Y = lateral x, Z = vertical y (top positive).
    xs = [s0, s0, s0, s0, s1, s1, s1, s1]
    ys = [x0, x1, x1, x0, x0, x1, x1, x0]
    zs = [y0, y0, y1, y1, y0, y0, y1, y1]
    i = [0, 0, 0, 1, 4, 4, 4, 5, 2, 3, 6, 7]
    j = [1, 2, 3, 2, 5, 6, 7, 6, 3, 0, 7, 4]
    k = [2, 3, 1, 3, 6, 7, 5, 7, 6, 7, 2, 3]
    return go.Mesh3d(
        x=xs,
        y=ys,
        z=zs,
        i=i,
        j=j,
        k=k,
        color=color,
        opacity=opacity,
        name=name,
        showlegend=showlegend,
        hovertemplate=f"{name}<extra></extra>",
        flatshading=True,
        lighting={
            "ambient": 0.92,
            "diffuse": 0.24,
            "specular": 0.02,
            "roughness": 1.0,
            "fresnel": 0.01,
        },
        lightposition={"x": 1000, "y": -1000, "z": 1800},
    )


def _append_3d_section_loop(
    x_values: list[float | None],
    y_values: list[float | None],
    z_values: list[float | None],
    *,
    station_m: float,
    lateral_left_mm: float,
    lateral_right_mm: float,
    vertical_bottom_mm: float,
    vertical_top_mm: float,
) -> None:
    """Append one closed section loop separated from the next by ``None``."""

    lateral = [
        lateral_left_mm,
        lateral_right_mm,
        lateral_right_mm,
        lateral_left_mm,
        lateral_left_mm,
    ]
    vertical = [
        vertical_top_mm,
        vertical_top_mm,
        vertical_bottom_mm,
        vertical_bottom_mm,
        vertical_top_mm,
    ]
    x_values.extend([station_m] * len(lateral) + [None])
    y_values.extend(lateral + [None])
    z_values.extend(vertical + [None])


def _stable_3d_tendon_color_map(
    points: list[dict[str, Any]],
) -> dict[str, str]:
    """Assign stable colors from the complete profile, not the visible subset."""

    tendon_ids = list(
        dict.fromkeys(
            str(row.get("Tendon ID") or "").strip()
            for row in points
            if str(row.get("Tendon ID") or "").strip()
        )
    )
    return {
        tendon_id: CROSSBEAM_3D_TENDON_COLORS[
            index % len(CROSSBEAM_3D_TENDON_COLORS)
        ]
        for index, tendon_id in enumerate(tendon_ids)
    }


def _three_d_figure(
    points: list[dict[str, Any]],
    active_ids: list[str],
    segment_rows: list[dict[str, Any]],
    *,
    section_definitions: list[dict[str, Any]],
    transparent: bool,
) -> go.Figure:
    fig = go.Figure()
    role_legend: set[str] = set()
    outer_boundary_x: list[float | None] = []
    outer_boundary_y: list[float | None] = []
    outer_boundary_z: list[float | None] = []
    void_boundary_x: list[float | None] = []
    void_boundary_y: list[float | None] = []
    void_boundary_z: list[float | None] = []
    outer_boundary_keys: set[tuple[float, float, float]] = set()
    void_boundary_keys: set[
        tuple[float, float, float, float, float, float, float]
    ] = set()
    params_by_id = _section_parameters_by_id(section_definitions)
    for row in segment_rows:
        role = row["Section role"]
        start = row["x_start_m"]
        end = row["x_end_m"]
        params = params_by_id.get(str(row.get("Section ID") or ""), {})
        width_mm = max(_finite_float(params.get("width_mm"), 2500.0), 1.0)
        height_mm = max(_finite_float(params.get("height_mm"), 1500.0), 1.0)
        style = CROSSBEAM_3D_CONCRETE_STYLES.get(
            role, CROSSBEAM_3D_CONCRETE_STYLES["Solid"]
        )
        opacity_key = "transparent_opacity" if transparent else "muted_opacity"
        opacity = float(style[opacity_key])

        for station_m in (start, end):
            outer_key = (round(station_m, 9), width_mm, height_mm)
            if outer_key not in outer_boundary_keys:
                _append_3d_section_loop(
                    outer_boundary_x,
                    outer_boundary_y,
                    outer_boundary_z,
                    station_m=station_m,
                    lateral_left_mm=-width_mm / 2.0,
                    lateral_right_mm=width_mm / 2.0,
                    vertical_bottom_mm=-height_mm,
                    vertical_top_mm=0.0,
                )
                outer_boundary_keys.add(outer_key)

        if role == "Hollow":
            tt = min(
                max(_finite_float(params.get("t_top_mm"), 300.0), 1.0),
                0.45 * height_mm,
            )
            tb = min(
                max(_finite_float(params.get("t_bottom_mm"), 300.0), 1.0),
                0.45 * height_mm,
            )
            tl = min(
                max(_finite_float(params.get("t_left_mm"), 300.0), 1.0),
                0.45 * width_mm,
            )
            tr = min(
                max(_finite_float(params.get("t_right_mm"), 300.0), 1.0),
                0.45 * width_mm,
            )
            for station_m in (start, end):
                void_key = (
                    round(station_m, 9),
                    width_mm,
                    height_mm,
                    tt,
                    tb,
                    tl,
                    tr,
                )
                if void_key not in void_boundary_keys:
                    _append_3d_section_loop(
                        void_boundary_x,
                        void_boundary_y,
                        void_boundary_z,
                        station_m=station_m,
                        lateral_left_mm=-width_mm / 2.0 + tl,
                        lateral_right_mm=width_mm / 2.0 - tr,
                        vertical_bottom_mm=-height_mm + tb,
                        vertical_top_mm=-tt,
                    )
                    void_boundary_keys.add(void_key)
            # Four wall prisms make the void visible without boolean 3D geometry.
            wall_specs = [
                (-width_mm / 2.0, width_mm / 2.0, -tt, 0.0),
                (-width_mm / 2.0, width_mm / 2.0, -height_mm, -height_mm + tb),
                (-width_mm / 2.0, -width_mm / 2.0 + tl, -height_mm + tb, -tt),
                (width_mm / 2.0 - tr, width_mm / 2.0, -height_mm + tb, -tt),
            ]
            for wall_index, (x0, x1, y0, y1) in enumerate(wall_specs):
                fig.add_trace(
                    _box_mesh(
                        s0=start,
                        s1=end,
                        x0=x0,
                        x1=x1,
                        y0=y0,
                        y1=y1,
                        name="Hollow segment",
                        color=str(style["color"]),
                        opacity=opacity,
                        showlegend="Hollow" not in role_legend and wall_index == 0,
                    )
                )
            role_legend.add("Hollow")
        else:
            fig.add_trace(
                _box_mesh(
                    s0=start,
                    s1=end,
                    x0=-width_mm / 2.0,
                    x1=width_mm / 2.0,
                    y0=-height_mm,
                    y1=0.0,
                    name="Solid segment",
                    color=str(style["color"]),
                    opacity=opacity,
                    showlegend="Solid" not in role_legend,
                )
            )
            role_legend.add("Solid")

    if outer_boundary_x:
        fig.add_trace(
            go.Scatter3d(
                x=outer_boundary_x,
                y=outer_boundary_y,
                z=outer_boundary_z,
                mode="lines",
                line={"color": CROSSBEAM_3D_OUTER_BOUNDARY_COLOR, "width": 3},
                opacity=0.82,
                name="Section boundaries",
                showlegend=False,
                hoverinfo="skip",
                connectgaps=False,
            )
        )
    if void_boundary_x:
        fig.add_trace(
            go.Scatter3d(
                x=void_boundary_x,
                y=void_boundary_y,
                z=void_boundary_z,
                mode="lines",
                line={
                    "color": CROSSBEAM_3D_VOID_BOUNDARY_COLOR,
                    "width": 2,
                    "dash": "dash",
                },
                opacity=0.78,
                name="Void boundaries",
                showlegend=False,
                hoverinfo="skip",
                connectgaps=False,
            )
        )

    tendon_colors = _stable_3d_tendon_color_map(points)
    for tendon_id in active_ids:
        rows = [row for row in points if row["Tendon ID"] == tendon_id]
        rows.sort(key=lambda row: row["s (m)"])
        if not rows:
            continue
        tendon_color = tendon_colors.get(
            tendon_id, CROSSBEAM_3D_TENDON_COLORS[0]
        )
        fig.add_trace(
            go.Scatter3d(
                x=[row["s (m)"] for row in rows],
                y=[row["x lateral (mm)"] for row in rows],
                z=[-row["dtop (mm)"] for row in rows],
                mode="lines+markers",
                line={"width": 8, "color": tendon_color},
                marker={
                    "size": 5,
                    "color": tendon_color,
                    "line": {"color": "#FFFFFF", "width": 1},
                },
                name=tendon_id,
                customdata=[[row["Point"], row["dtop (mm)"]] for row in rows],
                hovertemplate="%{fullData.name}<br>s=%{x:.3f} m<br>x=%{y:.1f} mm<br>dtop=%{customdata[1]:.1f} mm<br>%{customdata[0]}<extra></extra>",
            )
        )

    fig.update_layout(
        title={
            "text": "Crossbeam Tendon 3D Orthographic Review",
            "x": 0.5,
            "xanchor": "center",
            "y": 0.985,
            "yanchor": "top",
            "font": {"size": 17, "color": "#071A33"},
        },
        height=650,
        margin={"l": 20, "r": 20, "t": 110, "b": 20},
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"family": "Arial, sans-serif", "size": 12},
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": 0.94,
            "xanchor": "center",
            "x": 0.5,
            "bgcolor": "rgba(255,255,255,0.92)",
            "bordercolor": "#D7E0EA",
            "borderwidth": 1,
            "font": {"color": "#20364D", "size": 12},
        },
        uirevision="crossbeam-pt1e-3d-view",
        scene={
            "bgcolor": "#FBFCFE",
            "xaxis": {
                "title": "Station s (m)",
                "backgroundcolor": "#FBFCFE",
                "gridcolor": "#DCE4ED",
                "linecolor": "#8EA0B2",
                "zerolinecolor": "#B9C6D2",
                "showspikes": False,
            },
            "yaxis": {
                "title": "Lateral x (mm)",
                "backgroundcolor": "#FBFCFE",
                "gridcolor": "#DCE4ED",
                "linecolor": "#8EA0B2",
                "zerolinecolor": "#B9C6D2",
                "showspikes": False,
            },
            "zaxis": {
                "title": "Vertical y = -dtop (mm)",
                "backgroundcolor": "#FBFCFE",
                "gridcolor": "#DCE4ED",
                "linecolor": "#8EA0B2",
                "zerolinecolor": "#B9C6D2",
                "showspikes": False,
            },
            "aspectmode": "manual",
            "aspectratio": {"x": 3.2, "y": 1.1, "z": 0.8},
            "camera": {
                "eye": {"x": 1.55, "y": 1.45, "z": 1.05},
                "projection": {"type": "orthographic"},
            },
            "dragmode": "orbit",
        },
    )
    return fig


def render_crossbeam_tendon_system_page() -> None:
    _ensure_state()
    render_page_header(
        "Tendon System",
        "Define tendon material, tendon type, strand count, jacking end, and end-anchor source data without duplicating profile geometry.",
        icon="PT",
        kicker="Sections workspace",
        badge="Portal Frame Crossbeam",
        accent="purple",
    )
    render_section_bar(
        "Tendon source-of-truth",
        "One row represents one complete tendon. Compact linked tables avoid duplicate material or stressing inputs; geometry is edited only in Tendon Profile.",
        mark="T",
    )

    existing_system = canonical_tendon_system_rows(
        _records(st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY))
    )
    rows = list(existing_system)
    st.session_state[CB_TENDON_COUNT_KEY] = len(rows)
    active_count = sum(bool(row.get("Active")) for row in rows)
    minimum_status = "ready" if len(rows) >= CB_TENDON_MIN_COUNT else "warning"
    render_metric_cards(
        [
            {
                "title": "Stored tendons",
                "value": len(rows),
                "detail": "Tendon identity table rows · source of truth",
                "status": "info",
            },
            {
                "title": "Active tendons",
                "value": active_count,
                "detail": "Rows marked Active in the source table",
                "status": "ready" if active_count >= CB_TENDON_MIN_COUNT else "warning",
            },
            {
                "title": "Minimum required",
                "value": f"≥ {CB_TENDON_MIN_COUNT}",
                "detail": f"{len(rows)} currently stored",
                "status": minimum_status,
            },
            {
                "title": "Inventory limit",
                "value": CB_TENDON_MAX_COUNT,
                "detail": "Maximum stored tendon rows",
                "status": "neutral",
            },
        ]
    )
    st.caption(
        "Tendon count is derived from the Tendon identity and stressing table below; "
        "it is not an independent engineering input. Use the controlled actions to "
        "add or remove a complete tendon together with its linked Tendon Profile points."
    )

    notice = st.session_state.pop(CB_TENDON_MUTATION_NOTICE_KEY, None)
    if isinstance(notice, Mapping):
        action = str(notice.get("action") or "")
        stored_count = _finite_int(notice.get("stored_count"), len(rows))
        profile_points = _finite_int(notice.get("profile_points"), 0)
        tendon_id = str(notice.get("tendon_id") or "")
        if action == "added":
            st.success(
                f"Added {tendon_id} with {profile_points} default profile points. "
                f"{stored_count} tendons are now stored; review its geometry in Tendon Profile."
            )
        elif action == "removed":
            st.success(
                f"Removed {tendon_id} and {profile_points} linked profile points. "
                f"{stored_count} tendons remain stored."
            )
        elif action == "reset":
            st.success(
                f"Reset Tendon System to {stored_count} default tendons and "
                f"{profile_points} linked profile points."
            )

    stored_ids = [str(row.get("Tendon ID") or "").strip() for row in rows]
    unique_ids = list(dict.fromkeys(tendon_id for tendon_id in stored_ids if tendon_id))
    ids_are_removable = (
        len(unique_ids) == len(stored_ids)
        and len(rows) > CB_TENDON_MIN_COUNT
    )
    pending_id = str(
        st.session_state.get(CB_TENDON_REMOVE_PENDING_KEY) or ""
    ).strip()

    add_col, remove_select_col, remove_action_col, reset_col = st.columns(
        [1.0, 1.35, 0.95, 1.25]
    )
    with add_col:
        st.button(
            "Add tendon",
            key="crossbeam_pt1d_add_tendon",
            on_click=_add_crossbeam_tendon_from_ui,
            disabled=len(rows) >= CB_TENDON_MAX_COUNT or bool(pending_id),
            use_container_width=True,
            help="Adds one active tendon and three default Tendon Profile points.",
        )
    with remove_select_col:
        if unique_ids:
            current_selection = str(
                st.session_state.get(CB_TENDON_REMOVE_SELECTION_KEY) or ""
            )
            if current_selection not in unique_ids:
                st.session_state[CB_TENDON_REMOVE_SELECTION_KEY] = unique_ids[-1]
            st.selectbox(
                "Tendon to remove",
                options=unique_ids,
                key=CB_TENDON_REMOVE_SELECTION_KEY,
                disabled=not ids_are_removable or bool(pending_id),
                label_visibility="collapsed",
            )
        else:
            st.caption("No valid Tendon ID is available for removal.")
    with remove_action_col:
        st.button(
            "Review removal",
            key="crossbeam_pt1d_review_remove_tendon",
            on_click=_request_crossbeam_tendon_removal,
            disabled=not ids_are_removable or bool(pending_id),
            use_container_width=True,
        )
    with reset_col:
        st.button(
            "Reset to default (8)",
            key="crossbeam_ui1_reset_tendon_system",
            on_click=_reset_crossbeam_tendon_system_from_ui,
            disabled=bool(pending_id),
            use_container_width=True,
            help="Restores T1-T8 and their default web-centered profile geometry.",
        )

    if len(rows) <= CB_TENDON_MIN_COUNT:
        st.info(
            f"Removal is locked because at least {CB_TENDON_MIN_COUNT} stored tendons are required."
        )
    elif not ids_are_removable:
        st.warning(
            "Removal is locked until every stored row has one nonblank, unique Tendon ID."
        )

    if pending_id:
        if pending_id in unique_ids and ids_are_removable:
            st.warning(
                f"Confirm removal of {pending_id}. This will delete its Tendon System row "
                "and every linked Tendon Profile point."
            )
            confirm_col, cancel_col, _ = st.columns([1.0, 1.0, 2.5])
            with confirm_col:
                st.button(
                    f"Confirm remove {pending_id}",
                    key="crossbeam_pt1d_confirm_remove_tendon",
                    on_click=_confirm_crossbeam_tendon_removal,
                    type="primary",
                    use_container_width=True,
                )
            with cancel_col:
                st.button(
                    "Cancel",
                    key="crossbeam_pt1d_cancel_remove_tendon",
                    on_click=_cancel_crossbeam_tendon_removal,
                    use_container_width=True,
                )
        else:
            st.error(
                "The pending tendon can no longer be removed because the Tendon ID table changed. "
                "Cancel the removal and review the IDs."
            )
            st.button(
                "Cancel removal",
                key="crossbeam_pt1d_cancel_invalid_removal",
                on_click=_cancel_crossbeam_tendon_removal,
            )

    revision = int(st.session_state.get(CB_TENDON_SYSTEM_REV_KEY, 0))
    st.markdown("#### Tendon identity and stressing")
    identity_rows = _tendon_identity_editor_rows(rows)
    identity_editor_key = f"crossbeam_pt1_tendon_identity_editor_{revision}"
    identity_edited = st.data_editor(
        pd.DataFrame(identity_rows),
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        key=identity_editor_key,
        on_change=_commit_tendon_identity_editor,
        args=(identity_editor_key, rows, identity_rows),
        column_config={
            "_Original ID": None,
            "Tendon ID": st.column_config.TextColumn("Tendon ID", required=True),
            "Active": st.column_config.CheckboxColumn("Active"),
            "Type": st.column_config.SelectboxColumn("Type", options=list(TENDON_TYPE_OPTIONS), required=True),
            "Strands": st.column_config.NumberColumn("Strands", min_value=1, step=1, required=True),
            "Jacking end": st.column_config.SelectboxColumn("Jacking end", options=list(JACKING_END_OPTIONS), required=True),
        },
    )
    system_rows, rename_map = _tendon_system_from_identity_editor(
        rows, _records(identity_edited)
    )
    st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = system_rows
    st.session_state[CB_TENDON_COUNT_KEY] = len(system_rows)
    if rename_map:
        _rename_tendon_profile_references(rename_map)
        st.session_state[CB_TENDON_SYSTEM_REV_KEY] = revision + 1

    st.markdown("#### Prestressing steel")
    material_rows = _tendon_material_editor_rows(system_rows)
    material_editor_key = f"crossbeam_pt1_tendon_material_editor_{revision}"
    material_edited = st.data_editor(
        pd.DataFrame(material_rows),
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        key=material_editor_key,
        on_change=_commit_tendon_material_editor,
        args=(material_editor_key, system_rows, material_rows),
        disabled=["Tendon ID", "Strand system", "fpj MPa"],
        column_config={
            "Tendon ID": st.column_config.TextColumn("Tendon ID"),
            "Strand system": st.column_config.TextColumn("Strand system"),
            "Aps/strand mm²": st.column_config.NumberColumn(
                "Aps/strand (mm²)", min_value=1.0, format="%.1f", required=True
            ),
            "fpu MPa": st.column_config.NumberColumn(
                "fpu (MPa)", min_value=1.0, format="%.1f", required=True
            ),
            "fpj/fpu": st.column_config.NumberColumn(
                "fpj/fpu", min_value=0.001, max_value=1.0, format="%.3f", required=True
            ),
            "fpj MPa": st.column_config.NumberColumn("Calculated fpj (MPa)", format="%.1f"),
        },
    )
    system_rows = _tendon_system_from_material_editor(
        system_rows, _records(material_edited)
    )
    st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = system_rows
    st.session_state[CB_TENDON_COUNT_KEY] = len(system_rows)

    st.markdown("#### End anchorages")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Tendon ID": row["Tendon ID"],
                    "Left anchorage": row["Left anchorage"],
                    "Right anchorage": row["Right anchorage"],
                    "Status": "Both ends defined",
                }
                for row in system_rows
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    system_rows, system_errors, system_warnings = validate_tendon_system(system_rows)
    st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = system_rows
    st.session_state[CB_TENDON_COUNT_KEY] = len(system_rows)
    status = "SOURCE READY" if not system_errors else "REVIEW REQUIRED"
    status_kind = "ready" if not system_errors else "warning"
    active_rows = [row for row in system_rows if row["Active"]]
    total_aps = sum(
        max(_finite_int(row.get("Strands"), 0), 0)
        * max(_finite_float(row.get("Aps/strand mm²"), 0.0), 0.0)
        for row in active_rows
    )
    render_metric_cards(
        [
            {"title": "Tendon source", "value": status, "detail": "Input model only; not a design result", "status": status_kind},
            {"title": "Active tendons", "value": len(active_rows), "detail": f"{len(system_rows)} stored tendon rows", "status": "info"},
            {"title": "Active total Aps", "value": f"{total_aps:,.0f} mm²", "detail": "Strands × Aps/strand", "status": "neutral"},
            {"title": "PT continuity", "value": "CHECK IN PROFILE", "detail": "Tendon Profile · Calculated Audit", "status": "info"},
        ]
    )
    for message in system_errors:
        st.error(message)
    for message in system_warnings:
        st.warning(message)
    st.info(
        "Each tendon uses seven-wire low-relaxation strand. Anchorage heads are defined at s = 0 and s = L. Jacking end Left/Right/Both is stored for future loss distribution; both-end jacking will not double total Pj."
    )
    st.caption(
        "CROSSBEAM.PT1 input source only. ACI 423.10R loss calculations, friction parameters, anchor set, elastic shortening, time-dependent losses, and FEA handoff remain future milestones."
    )


def render_crossbeam_segment_layout_page() -> None:
    _ensure_state()
    render_page_header(
        "Crossbeam Segment Layout",
        "Assign solid and hollow section roles along station s and verify the complete crossbeam elevation before future station-based checks.",
        icon="SG",
        kicker="Sections workspace",
        badge="Portal Frame Crossbeam",
        accent="green",
    )
    render_section_bar(
        "Longitudinal section assignment",
        "The layout must cover s = 0 to s = L continuously without gaps or overlaps.",
        mark="S",
    )
    length_m = _render_crossbeam_member_length_reference()

    definitions = _crossbeam_section_definitions()
    definition_by_id = crossbeam_section_definition_map(definitions)
    section_ids = list(definition_by_id)
    if st.button("Reset segment layout to solid/hollow seed", key="crossbeam_ui1_reset_segments"):
        st.session_state[CB_SEGMENT_ROWS_KEY] = migrate_segment_rows_to_library(
            default_crossbeam_segment_rows(length_m), definitions
        )
        st.session_state[CB_SEGMENT_REV_KEY] = int(st.session_state.get(CB_SEGMENT_REV_KEY, 0)) + 1
        st.rerun()

    active_section_id = str(st.session_state.get("crossbeam_seclib1_active_section_id") or "Not selected")
    st.info(
        "Each segment is assigned to a project Section ID from the Crossbeam Section Definition Library in Section Builder. "
        f"Active Section Builder definition: {active_section_id}."
    )

    revision = int(st.session_state.get(CB_SEGMENT_REV_KEY, 0))
    source_rows = _records(st.session_state.get(CB_SEGMENT_ROWS_KEY)) or migrate_segment_rows_to_library(
        default_crossbeam_segment_rows(length_m), definitions
    )
    edited = st.data_editor(
        pd.DataFrame(_segment_editor_rows(source_rows)),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"crossbeam_ui1_segment_editor_{revision}",
        column_config={
            "Segment": st.column_config.TextColumn("Segment", required=True),
            "x_start_m": st.column_config.NumberColumn("s_start (m)", min_value=0.0, format="%.3f", required=True),
            "x_end_m": st.column_config.NumberColumn("s_end (m)", min_value=0.0, format="%.3f", required=True),
            "Section ID": st.column_config.SelectboxColumn(
                "Section ID",
                options=section_ids,
                required=True,
                help="Section IDs are created and edited in Section Builder. Different Hollow IDs may use different wall thicknesses.",
            ),
            "Section name": st.column_config.TextColumn("Section name", disabled=True),
            "Section role": st.column_config.TextColumn("Role", disabled=True),
            "Preset family": st.column_config.TextColumn("Preset family", disabled=True),
        },
        disabled=["Section name", "Section role", "Preset family"],
    )
    raw_rows = _records(edited)
    rows, errors = _validate_segments(raw_rows, length_m)
    st.session_state[CB_SEGMENT_ROWS_KEY] = rows

    solid_count = sum(row["Section role"] == "Solid" for row in rows)
    hollow_count = sum(row["Section role"] == "Hollow" for row in rows)
    section_ids_used = len({row["Section ID"] for row in rows if row.get("Section ID")})
    render_metric_cards(
        [
            {
                "title": "Layout status",
                "value": "LAYOUT READY" if not errors else "LAYOUT REQUIRED",
                "detail": f"Extent 0–{length_m:.3f} m; not a solver result",
                "status": "ready" if not errors else "warning",
            },
            {"title": "Segments", "value": len(rows), "detail": "Station ranges", "status": "info"},
            {"title": "Section IDs used", "value": section_ids_used, "detail": f"{len(definitions)} available in library", "status": "info"},
            {"title": "Solid / Hollow", "value": f"{solid_count} / {hollow_count}", "detail": "Assigned segment roles", "status": "neutral"},
        ]
    )
    if errors:
        for error in errors:
            st.error(error)

    st.plotly_chart(_elevation_figure(rows, length_m), use_container_width=True, config=FIGURE_CONFIG)
    st.caption(
        "Elevation is a Section-ID-based geometric review figure. Dashed lines show the hidden void extending from the start to the end of each hollow segment. Each Section ID owns its own dimensions and calculated gross properties in Section Builder; station solver handoff and solid-to-hollow D-region checks remain future scope."
    )


def render_crossbeam_tendon_profile_page() -> None:
    _ensure_state()
    context = _section_context()
    render_page_header(
        "Tendon Profile & Geometry Views",
        "Edit one shared tendon geometry source and review it consistently in Plan, Elevation, Cross Section, and 3D Orthographic without running prestress-loss or strength solvers.",
        icon="3D",
        kicker="Sections workspace",
        badge="Portal Frame Crossbeam",
        accent="purple",
    )
    render_section_bar(
        "Tendon geometry source-of-truth",
        "Cross-section axes remain x–y; longitudinal geometry uses station s. Tendon vertical input is always dtop measured downward from the top surface.",
        mark="P",
    )
    length_m = _render_crossbeam_member_length_reference()
    system_rows = _records(st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY))
    tendon_ids = _tendon_ids(system_rows)
    if not tendon_ids:
        st.warning("Define the Tendon System before editing profile geometry.")
        return

    st.session_state[CB_PROFILE_PRESET_KEY] = normalize_tendon_profile_preset(
        st.session_state.get(CB_PROFILE_PRESET_KEY)
        or TENDON_PROFILE_PRESET_OPTIONS[0]
    )
    st.session_state[CB_PROFILE_PRESET_SPAN_KEY] = normalize_tendon_profile_span_mode(
        st.session_state.get(CB_PROFILE_PRESET_SPAN_KEY)
        or TENDON_PROFILE_SPAN_MODE_OPTIONS[0]
    )
    current_targets = [
        tendon_id
        for tendon_id in st.session_state.get(CB_PROFILE_PRESET_TARGETS_KEY, tendon_ids)
        if tendon_id in tendon_ids
    ] or list(tendon_ids)
    st.session_state[CB_PROFILE_PRESET_TARGETS_KEY] = current_targets

    support_width_max = max(min(0.20 * length_m, 5.0), 0.10)
    support_width_value = min(
        max(
            _finite_float(
                st.session_state.get(CB_PROFILE_PRESET_SUPPORT_WIDTH_KEY),
                DEFAULT_TENDON_PROFILE_SUPPORT_WIDTH_M,
            ),
            0.10,
        ),
        support_width_max,
    )
    quick_col, span_col, offset_col, support_col, target_col, action_col = st.columns(
        [1.35, 0.85, 0.85, 0.9, 1.25, 0.8]
    )
    with quick_col:
        selected_preset = st.radio(
            "Select A Quick Start Option",
            options=list(TENDON_PROFILE_PRESET_OPTIONS),
            key=CB_PROFILE_PRESET_KEY,
            on_change=_apply_selected_tendon_profile_preset_from_ui,
            help=(
                "Changing this selection immediately rewrites the selected tendon profile rows. "
                "The generated rows remain editable s-x-dtop control points."
            ),
        )
    with span_col:
        selected_span_mode = st.radio(
            "Span type",
            options=list(TENDON_PROFILE_SPAN_MODE_OPTIONS),
            key=CB_PROFILE_PRESET_SPAN_KEY,
            on_change=_apply_selected_tendon_profile_preset_from_ui,
            help="Single Span and 2 Span use different control-point patterns for the same quick-start option. 2 Span repeats the simple-span profile across the middle support.",
        )
    with offset_col:
        default_offset = min(200.0, 0.20 * context["height_mm"])
        bend_offset = st.slider(
            "Preset bend offset (mm)",
            min_value=0.0,
            max_value=float(context["height_mm"]),
            value=float(st.session_state.get(CB_PROFILE_PRESET_OFFSET_KEY, default_offset)),
            step=25.0,
            key=CB_PROFILE_PRESET_OFFSET_KEY,
            on_change=_apply_selected_tendon_profile_preset_from_ui,
            help=(
                "Depth delta applied to bend/parabolic presets. Positive offsets move low points downward because dtop is measured from the top."
            ),
        )
    with support_col:
        support_width = st.slider(
            "Support width (m)",
            min_value=0.10,
            max_value=float(support_width_max),
            value=float(support_width_value),
            step=0.10,
            key=CB_PROFILE_PRESET_SUPPORT_WIDTH_KEY,
            on_change=_apply_selected_tendon_profile_preset_from_ui,
            help=(
                "Longitudinal column/support width used by 2 Span quick-starts. "
                "Bent profiles place three high control points across this width; "
                "parabolic profiles add dense control points across twice this width."
            ),
        )
    with target_col:
        preset_targets = st.multiselect(
            "Apply preset to tendons",
            options=tendon_ids,
            key=CB_PROFILE_PRESET_TARGETS_KEY,
            help="Only selected tendons are replaced by the preset; other tendon profile rows are preserved.",
        )
    with action_col:
        st.write("")
        st.write("")
        apply_preset = st.button(
            "Re-apply",
            key="crossbeam_pt1g_apply_profile_preset",
            use_container_width=True,
            help="Use after changing target tendons or when you want to apply the current preset again. Preset, span, offset, and support-width changes are applied immediately.",
        )
    st.markdown(
        _profile_quick_start_gallery_html(
            selected_preset,
            length_m=length_m,
            support_width_m=support_width,
        ),
        unsafe_allow_html=True,
    )
    if apply_preset:
        notice = _apply_tendon_profile_preset(
            st.session_state,
            length_m=length_m,
            tendon_ids=tendon_ids,
            target_tendon_ids=preset_targets,
            width_mm=context["width_mm"],
            height_mm=context["height_mm"],
            t_left_mm=context["t_left_mm"],
            t_right_mm=context["t_right_mm"],
            preset=selected_preset,
            span_mode=selected_span_mode,
            bend_offset_mm=bend_offset,
            support_width_m=support_width,
        )
        st.session_state[CB_PROFILE_PRESET_NOTICE_KEY] = notice

    notice = st.session_state.pop(CB_PROFILE_PRESET_NOTICE_KEY, None)
    if isinstance(notice, Mapping):
        if notice.get("action") == "applied":
            st.success(
                f"Applied {notice.get('preset', selected_preset)} / {notice.get('span_mode', selected_span_mode)} "
                f"to {notice.get('tendon_count', 0)} tendon(s), creating "
                f"{notice.get('profile_points', 0)} editable profile point row(s)."
            )
        elif notice.get("action") == "skipped":
            st.warning("Select at least one tendon before applying a profile preset.")

    preset_point_count = profile_preset_point_count(
        selected_preset,
        selected_span_mode,
        length_m=length_m,
        support_width_m=support_width,
    )
    st.caption(
        f"Preset `{selected_preset}` / `{selected_span_mode}` creates {preset_point_count} point(s) per selected tendon. "
        "Option, Span type, offset, and support-width changes rewrite the selected tendon rows immediately; target changes use Re-apply. "
        "The profile table below stays editable: add rows for extra control points, or tick Delete row to remove selected points."
    )

    if st.button("Reset tendon geometry to straight web-centered profiles", key="crossbeam_ui1_reset_profile"):
        st.session_state[CB_PROFILE_ROWS_KEY] = default_tendon_profile_points(
            length_m,
            tendon_ids=tendon_ids,
            width_mm=context["width_mm"],
            height_mm=context["height_mm"],
            t_left_mm=context["t_left_mm"],
            t_right_mm=context["t_right_mm"],
        )
        st.session_state[CB_PROFILE_REV_KEY] = int(st.session_state.get(CB_PROFILE_REV_KEY, 0)) + 1
        st.rerun()

    revision = int(st.session_state.get(CB_PROFILE_REV_KEY, 0))
    source_rows = canonical_tendon_profile_points(
        _records(st.session_state.get(CB_PROFILE_ROWS_KEY)), length_m
    )
    profile_editor_rows = [
        {
            "Delete row": False,
            "Tendon ID": row["Tendon ID"],
            "Point": row["Point"],
            "s (m)": row["s (m)"],
            "x lateral (mm)": row["x lateral (mm)"],
            "dtop (mm)": row["dtop (mm)"],
            "Curve role": row["Curve role"],
        }
        for row in source_rows
    ]
    profile_editor_key = f"crossbeam_pt1_profile_editor_{revision}"
    edited = st.data_editor(
        pd.DataFrame(profile_editor_rows),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=profile_editor_key,
        on_change=_commit_tendon_profile_editor,
        args=(profile_editor_key, profile_editor_rows),
        column_config={
            "Delete row": st.column_config.CheckboxColumn(
                "Delete row",
                help="Tick to remove this profile point on the next edit commit.",
            ),
            "Tendon ID": st.column_config.SelectboxColumn("Tendon ID", options=tendon_ids, required=True),
            "Point": st.column_config.TextColumn("Point", required=True),
            "s (m)": st.column_config.NumberColumn("s (m)", min_value=0.0, max_value=length_m, format="%.3f", required=True),
            "x lateral (mm)": st.column_config.NumberColumn("x lateral (mm)", format="%.1f", required=True),
            "dtop (mm)": st.column_config.NumberColumn("dtop (mm)", format="%.1f", required=True),
            "Curve role": st.column_config.SelectboxColumn("Curve role", options=list(PROFILE_ROLE_OPTIONS), required=True),
        },
    )
    points = _profile_rows_from_editor_rows(_records(edited), length_m)
    st.session_state[CB_PROFILE_ROWS_KEY] = points

    segment_rows, segment_errors = _validate_segments(_records(st.session_state.get(CB_SEGMENT_ROWS_KEY)), length_m)
    section_definitions = _crossbeam_section_definitions()
    system_rows, system_errors, system_warnings = validate_tendon_system(system_rows)
    points, profile_errors, profile_warnings = validate_tendon_profile(
        points,
        system_rows,
        length_m=length_m,
        segment_rows=segment_rows,
        section_definitions=section_definitions,
    )
    st.session_state[CB_PROFILE_ROWS_KEY] = points
    all_errors = list(dict.fromkeys(segment_errors + system_errors + profile_errors))
    all_warnings = list(dict.fromkeys(system_warnings + profile_warnings))
    continuity_rows = tendon_continuity_audit_rows(
        points,
        system_rows,
        length_m=length_m,
        segment_rows=segment_rows,
        section_definitions=section_definitions,
    )
    continuity_summary = tendon_continuity_summary(
        continuity_rows,
        profile_errors=all_errors,
        profile_warnings=all_warnings,
    )

    st.session_state[CB_ACTIVE_TENDONS_KEY] = [
        item
        for item in st.session_state.get(CB_ACTIVE_TENDONS_KEY, tendon_ids)
        if item in tendon_ids
    ]
    active_ids = st.multiselect(
        "Visible tendons",
        options=tendon_ids,
        key=CB_ACTIVE_TENDONS_KEY,
        help="Visibility changes review figures only; it does not exclude a tendon from the model.",
    )
    transparent = st.toggle(
        "Transparent 3D concrete",
        key=CB_3D_TRANSPARENT_KEY,
        help=(
            "Display only. ON uses a light X-ray view (Solid 14%, Hollow 9%); "
            "OFF uses muted concrete surfaces (Solid 34%, Hollow 22%). This does "
            "not change geometry, tendon inputs, validation, or analysis."
        ),
    )
    st.caption(
        "3D display only — neutral concrete colors keep the tendon paths legible. "
        "Transparency changes appearance only; it does not edit L, segment stations, "
        "or tendon coordinates."
    )

    internal_count = sum(str(row.get("Type") or "").casefold() == "internal" for row in system_rows)
    external_count = sum(str(row.get("Type") or "").casefold() == "external" for row in system_rows)
    render_metric_cards(
        [
            {
                "title": "Tendon geometry source",
                "value": "SOURCE READY" if not all_errors else "REVIEW REQUIRED",
                "detail": "Plan/Elevation/Cross Section/3D use one s–x–dtop table",
                "status": "ready" if not all_errors else "warning",
            },
            {"title": "Tendons", "value": len(tendon_ids), "detail": f"Internal {internal_count} · External {external_count}", "status": "info"},
            {"title": "Profile points", "value": len(points), "detail": "dtop measured downward from top", "status": "neutral"},
            {
                "title": "PT continuity",
                "value": str(continuity_summary["value"]),
                "detail": str(continuity_summary["detail"]),
                "status": str(continuity_summary["status"]),
            },
        ]
    )
    if all_errors or all_warnings:
        with st.expander("Geometry validation issues", expanded=True):
            for error in all_errors:
                st.error(error)
            for warning in all_warnings:
                st.warning(warning)

    plan_tab, elevation_tab, cross_section_tab, three_d_tab, audit_tab = st.tabs(
        ["Plan", "Elevation", "Cross Section", "3D Orthographic", "Calculated Audit"]
    )
    with plan_tab:
        st.plotly_chart(
            _plan_figure(points, active_ids, segment_rows, section_definitions),
            use_container_width=True,
            config=FIGURE_CONFIG,
        )
        st.caption("Plan uses station s and lateral section coordinate x. x = 0 is the crossbeam centerline.")
    with elevation_tab:
        st.plotly_chart(
            _profile_figure(points, active_ids, segment_rows, section_definitions),
            use_container_width=True,
            config=FIGURE_CONFIG,
        )
        st.caption(
            "Elevation uses station s horizontally and dtop measured downward from the top surface. Bottom and centroid lines change with the Section ID assigned to each Segment."
        )
    with cross_section_tab:
        st.markdown("#### Cross-section review station")
        station_m = float(
            st.slider(
                "Station s (m)",
                min_value=0.0,
                max_value=float(length_m),
                step=0.1,
                format="%.3f",
                key=CB_CROSS_SECTION_STATION_KEY,
                help="The section and tendon centers are read from Segment Layout and the shared s–x–dtop profile at this station.",
            )
        )
        section_contexts = station_section_contexts(
            station_m,
            segment_rows,
            section_definitions,
            length_m=length_m,
        )
        if not section_contexts:
            st.error("The selected station has no assigned Segment/Section ID.")
        else:
            face_labels = [
                f"{row.get('Segment', '')} · {row.get('Section ID', '')} · {row.get('Station face', '')}"
                for row in section_contexts
            ]
            if st.session_state.get(CB_CROSS_SECTION_FACE_KEY) not in face_labels:
                st.session_state[CB_CROSS_SECTION_FACE_KEY] = face_labels[-1]
            selected_face = st.selectbox(
                "Section face to display",
                options=face_labels,
                key=CB_CROSS_SECTION_FACE_KEY,
                help="At a Segment joint, choose either adjacent face. Away from a joint only one face applies.",
            )
            selected_index = face_labels.index(selected_face)
            selected_context = section_contexts[selected_index]
            section_id = str(selected_context.get("Section ID") or "")
            definition = crossbeam_section_definition_map(section_definitions).get(section_id)
            positions = tendon_positions_at_station(
                points,
                system_rows,
                station_m=station_m,
                length_m=length_m,
            )
            positions = [row for row in positions if row["Tendon ID"] in active_ids]
            if definition is None:
                st.error(f"Section ID {section_id or '(blank)'} does not resolve to a project section definition.")
            else:
                try:
                    section_figure, fit_rows = _cross_section_figure(
                        definition,
                        positions,
                        station_m=station_m,
                        segment_id=str(selected_context.get("Segment") or ""),
                        station_face=str(selected_context.get("Station face") or ""),
                    )
                except Exception as exc:
                    st.error(f"Unable to build Cross Section for {section_id}: {exc}")
                else:
                    internal_outside = sum(
                        row["Type"] == "Internal" and not row["Inside concrete"]
                        for row in fit_rows
                    )
                    render_metric_cards(
                        [
                            {"title": "Station", "value": f"{station_m:.3f} m", "detail": str(selected_context.get("Station face") or ""), "status": "info"},
                            {"title": "Segment", "value": str(selected_context.get("Segment") or "—"), "detail": "Segment Layout source", "status": "neutral"},
                            {"title": "Section ID", "value": section_id, "detail": str(definition.get("Section role") or ""), "status": "info"},
                            {
                                "title": "Internal tendon fit",
                                "value": "IN CONCRETE" if internal_outside == 0 else "REVIEW REQUIRED",
                                "detail": f"{internal_outside} visible internal tendon(s) outside concrete / in void",
                                "status": "ready" if internal_outside == 0 else "warning",
                            },
                        ]
                    )
                    st.plotly_chart(
                        section_figure,
                        use_container_width=True,
                        config=FIGURE_CONFIG,
                    )
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Tendon ID": row["Tendon ID"],
                                    "Type": row["Type"],
                                    "x (mm)": round(row["x lateral (mm)"], 2),
                                    "dtop (mm)": round(row["dtop (mm)"], 2),
                                    "Fit": row["Cross-section fit"],
                                    "Interpolation": row["Interpolation"],
                                }
                                for row in fit_rows
                            ]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                    if internal_outside:
                        st.warning(
                            "One or more visible Internal tendon centers lie outside the concrete polygon or inside a void at this station. Adjust x/dtop or classify the applicable tendon as External; no input is moved automatically."
                        )
                    st.caption(
                        "Cross Section uses the exact project Section ID geometry. Tendon centers are piecewise-linearly interpolated from the same s–x–dtop table; marker size is enhanced for review and is not a duct diameter."
                    )
    with three_d_tab:
        st.plotly_chart(
            _three_d_figure(
                points,
                active_ids,
                segment_rows,
                section_definitions=section_definitions,
                transparent=transparent,
            ),
            use_container_width=True,
            config=FIGURE_CONFIG,
        )
        st.caption(
            "3D uses orthographic projection so parallel member edges remain parallel. "
            "Concrete is intentionally neutral; saturated colors identify tendons, "
            "dark loops mark section boundaries, and dashed loops mark Hollow voids. "
            "Fillets, chamfers, ducts, anchor hardware, and deviator hardware remain schematic."
        )
    with audit_tab:
        audit_rows = tendon_station_audit_rows(
            points,
            system_rows,
            length_m=length_m,
            segment_rows=segment_rows,
            section_definitions=section_definitions,
        )
        st.markdown("#### Segment joint PT continuity")
        if continuity_rows:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Joint s (m)": round(row["Joint s (m)"], 4),
                            "Segment": row["Segment"],
                            "Section ID": row["Section ID"],
                            "Station face": row["Station face"],
                            "Tendon ID": row["Tendon ID"],
                            "Type": row["Type"],
                            "x (mm)": None if row["x (mm)"] is None else round(row["x (mm)"], 2),
                            "dtop (mm)": None if row["dtop (mm)"] is None else round(row["dtop (mm)"], 2),
                            "Fit": row["Fit"],
                            "Aps total (mm²)": round(row["Aps total (mm²)"], 2),
                            "fpj (MPa)": round(row["fpj (MPa)"], 2),
                            "Continuity status": row["Continuity status"],
                            "Issue": row["Issue"],
                        }
                        for row in continuity_rows
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No internal segment joint stations were found for PT continuity review.")
        st.markdown("#### Station and assigned section")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Tendon ID": row["Tendon ID"],
                        "Point": row["Point"],
                        "s (m)": round(row["s (m)"], 4),
                        "Segment": row["Segment"],
                        "Section ID": row["Section ID"],
                        "Station face": row["Station face"],
                    }
                    for row in audit_rows
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("#### Top-referenced geometry and eccentricity")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Tendon ID": row["Tendon ID"],
                        "Point": row["Point"],
                        "x (mm)": round(row["x (mm)"], 2),
                        "dtop (mm)": round(row["dtop (mm)"], 2),
                        "Centroid dtop (mm)": round(row["centroid from top (mm)"], 2),
                        "e(s) (mm)": round(row["e(s) (mm)"], 2),
                    }
                    for row in audit_rows
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("#### Tendon stressing source")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Tendon ID": row["Tendon ID"],
                        "Active": row["Active"],
                        "Type": row["Type"],
                        "Jacking end": row["Jacking end"],
                        "fpj (MPa)": round(row["fpj (MPa)"], 2),
                        "Aps total (mm²)": round(row["Aps total (mm²)"], 2),
                    }
                    for row in audit_rows
                ]
            ).drop_duplicates(),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "e(s) is positive when the tendon lies below the centroid. Each row uses the Section ID assigned at that station; a point on a segment joint expands to both adjacent section faces."
        )

    continuity_note = (
        "These figures do not calculate friction, wobble, anchorage set, elastic shortening, "
        "creep, shrinkage, relaxation, SLS stress, ULS strength, anchorage zones, deviator "
        "forces, or solid/hollow transition D-regions."
    )
    if continuity_summary["value"] == "GEOMETRY VERIFIED":
        st.success(
            "PT geometry continuity across segment joints is verified for the active tendon input rows. "
            + continuity_note
        )
    elif continuity_summary["value"] == "NO JOINTS":
        st.info("PT geometry continuity has no internal segment joints to check. " + continuity_note)
    else:
        st.warning(
            "PT geometry continuity across segment joints requires review before relying on this tendon layout. "
            + continuity_note
        )
