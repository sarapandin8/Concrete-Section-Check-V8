"""Workflow-scoped section workspaces for Portal Frame PC Crossbeam.

CROSSBEAM.UI1 separates longitudinal segment mapping, tendon system data, and
three-view tendon geometry from the shared Section Builder.  It intentionally
contains no prestress-loss, SLS, ULS, anchorage-zone, or D-region solver.

All state keys are namespaced to the crossbeam workflow.  Legacy WF1 keys are
read for one-way in-session migration so accepted WF1/WF1A projects keep their
seed data without changing Project JSON or existing workflow behavior.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from math import isfinite
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from concrete_pmm_pro.crossbeam.section_library import (
    canonical_section_definitions,
    definition_map as crossbeam_section_definition_map,
    migrate_segment_rows_to_library,
    section_property_records,
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
    default_crossbeam_tendon_rows,
)
from concrete_pmm_pro.geometry.presets import load_section_presets
from concrete_pmm_pro.geometry.summary import summarize_geometry
from concrete_pmm_pro.ui.commercial import render_metric_cards, render_page_header, render_section_bar
from concrete_pmm_pro.ui.crossbeam_section_library import ensure_crossbeam_section_library_state


# Accepted WF1/WF1A keys retained for migration compatibility.
LEGACY_LENGTH_KEY = "crossbeam_wf1_length_m"
LEGACY_SEGMENT_ROWS_KEY = "crossbeam_wf1_segment_layout_rows"
LEGACY_TENDON_COUNT_KEY = "crossbeam_wf1_tendon_count"
LEGACY_PROFILE_ROWS_KEY = "crossbeam_wf1_tendon_profile_rows"

# CROSSBEAM.UI1 keys.  These must never be reused by another workflow.
CB_LENGTH_KEY = "crossbeam_ui1_length_m"
CB_SEGMENT_ROWS_KEY = "crossbeam_ui1_segment_layout_rows"
CB_SEGMENT_REV_KEY = "crossbeam_ui1_segment_editor_revision"
CB_TENDON_COUNT_KEY = "crossbeam_ui1_tendon_count"
CB_TENDON_SYSTEM_ROWS_KEY = "crossbeam_ui1_tendon_system_rows"
CB_TENDON_SYSTEM_REV_KEY = "crossbeam_ui1_tendon_system_editor_revision"
CB_PROFILE_ROWS_KEY = "crossbeam_ui1_tendon_profile_points"
CB_PROFILE_REV_KEY = "crossbeam_ui1_tendon_profile_editor_revision"
CB_ACTIVE_TENDONS_KEY = "crossbeam_ui1_active_tendon_ids"
CB_3D_TRANSPARENT_KEY = "crossbeam_ui1_3d_transparent"
CB_UI1A_MIGRATION_KEY = "crossbeam_ui1a_segment_assignment_migrated"


FIGURE_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


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


def _default_lateral_offsets(tendon_ids: list[str], width_mm: float) -> dict[str, float]:
    count = max(len(tendon_ids), 1)
    if count == 1:
        return {tendon_ids[0]: 0.0}
    usable = max(0.55 * width_mm, 0.0)
    start = -usable / 2.0
    step = usable / float(count - 1)
    return {tendon_id: start + index * step for index, tendon_id in enumerate(tendon_ids)}


def _system_rows_from_legacy(profile_rows: list[dict[str, Any]], tendon_count: int) -> list[dict[str, Any]]:
    first_by_id: dict[str, dict[str, Any]] = {}
    for row in profile_rows:
        tendon_id = str(row.get("Tendon ID") or "").strip()
        if tendon_id and tendon_id not in first_by_id:
            first_by_id[tendon_id] = row

    ids = sorted(first_by_id, key=lambda text: (_finite_int(text.removeprefix("T"), 9999), text))
    if not ids:
        ids = [f"T{index + 1}" for index in range(max(tendon_count, 2))]

    rows: list[dict[str, Any]] = []
    for tendon_id in ids:
        source = first_by_id.get(tendon_id, {})
        rows.append(
            {
                "Tendon ID": tendon_id,
                "Type": str(source.get("Type") or DEFAULT_TENDON_TYPE),
                "Strands": max(_finite_int(source.get("Strands"), DEFAULT_STRANDS_PER_TENDON), 1),
                "Aps/strand mm²": _finite_float(source.get("Aps/strand mm²"), DEFAULT_STRAND_APS_MM2),
                "fpu MPa": _finite_float(source.get("fpu MPa"), DEFAULT_STRAND_FPU_MPA),
                "fpj/fpu": _finite_float(source.get("fpj/fpu"), DEFAULT_FPJ_RATIO),
                "Jacking end": str(source.get("Jacking end") or DEFAULT_JACKING_END).lower(),
                "Left anchorage": "s = 0",
                "Right anchorage": "s = L",
            }
        )
    return rows


def _profile_points_from_legacy(
    profile_rows: list[dict[str, Any]],
    *,
    length_m: float,
    tendon_ids: list[str],
    width_mm: float,
    height_mm: float,
) -> list[dict[str, Any]]:
    offsets = _default_lateral_offsets(tendon_ids, width_mm)
    if not profile_rows:
        profile_rows = default_crossbeam_tendon_rows(
            length_m,
            tendon_count=max(len(tendon_ids), 2),
            section_depth_mm=height_mm,
        )

    points: list[dict[str, Any]] = []
    for index, row in enumerate(profile_rows):
        tendon_id = str(row.get("Tendon ID") or f"T{index + 1}").strip()
        s_ratio = _finite_float(row.get("s/L", row.get("x/L")), 0.0)
        s_m = _finite_float(row.get("s (m)", row.get("x_m")), s_ratio * length_m)
        dtop = _finite_float(row.get("dtop (mm)", row.get("Depth from top mm")), 0.18 * height_mm)
        points.append(
            {
                "Tendon ID": tendon_id,
                "Point": str(row.get("Point") or f"P{index + 1}"),
                "s/L": s_ratio,
                "s (m)": s_m,
                "x lateral (mm)": _finite_float(row.get("x lateral (mm)"), offsets.get(tendon_id, 0.0)),
                "dtop (mm)": dtop,
                "Curve role": str(row.get("Curve role") or ("Anchorage" if abs(s_ratio) < 1e-9 or abs(s_ratio - 1.0) < 1e-9 else "Profile point")),
            }
        )
    return points


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

    if CB_TENDON_COUNT_KEY not in st.session_state:
        st.session_state[CB_TENDON_COUNT_KEY] = max(
            _finite_int(st.session_state.get(LEGACY_TENDON_COUNT_KEY), DEFAULT_TENDON_COUNT), 2
        )
    tendon_count = max(_finite_int(st.session_state.get(CB_TENDON_COUNT_KEY), DEFAULT_TENDON_COUNT), 2)

    legacy_profile = _legacy_profile_rows()
    if CB_TENDON_SYSTEM_ROWS_KEY not in st.session_state:
        st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = _system_rows_from_legacy(legacy_profile, tendon_count)
    st.session_state.setdefault(CB_TENDON_SYSTEM_REV_KEY, 0)

    system_rows = _records(st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY))
    tendon_ids = [str(row.get("Tendon ID") or "").strip() for row in system_rows]
    tendon_ids = [item for item in tendon_ids if item]
    if not tendon_ids:
        tendon_ids = [f"T{index + 1}" for index in range(tendon_count)]

    if CB_PROFILE_ROWS_KEY not in st.session_state:
        st.session_state[CB_PROFILE_ROWS_KEY] = _profile_points_from_legacy(
            legacy_profile,
            length_m=length_m,
            tendon_ids=tendon_ids,
            width_mm=context["width_mm"],
            height_mm=context["height_mm"],
        )
    st.session_state.setdefault(CB_PROFILE_REV_KEY, 0)
    st.session_state.setdefault(CB_ACTIVE_TENDONS_KEY, tendon_ids)
    st.session_state.setdefault(CB_3D_TRANSPARENT_KEY, True)


def _length_input() -> float:
    _ensure_state()
    return float(
        st.number_input(
            "Crossbeam total length L (m)",
            min_value=0.1,
            max_value=500.0,
            step=0.5,
            format="%.3f",
            key=CB_LENGTH_KEY,
            help="Station s is measured from the left anchorage at s = 0 to the right anchorage at s = L.",
        )
    )


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


def _normalize_profile_points(rows: list[dict[str, Any]], length_m: float) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        tendon_id = str(row.get("Tendon ID") or "").strip()
        ratio = _finite_float(row.get("s/L"), 0.0)
        station = _finite_float(row.get("s (m)"), ratio * length_m)
        if abs(station - ratio * length_m) > max(1e-6, length_m * 1e-6):
            ratio = station / length_m if length_m > 0 else 0.0
        normalized.append(
            {
                "Tendon ID": tendon_id,
                "Point": str(row.get("Point") or f"P{index + 1}"),
                "s/L": ratio,
                "s (m)": station,
                "x lateral (mm)": _finite_float(row.get("x lateral (mm)"), 0.0),
                "dtop (mm)": _finite_float(row.get("dtop (mm)"), 0.0),
                "Curve role": str(row.get("Curve role") or "Profile point"),
            }
        )
    normalized.sort(key=lambda row: (row["Tendon ID"], row["s (m)"], row["Point"]))
    return normalized


def _validate_profile_points(
    rows: list[dict[str, Any]],
    *,
    tendon_ids: list[str],
    length_m: float,
    width_mm: float,
    height_mm: float,
) -> list[str]:
    errors: list[str] = []
    by_id: dict[str, list[dict[str, Any]]] = {tendon_id: [] for tendon_id in tendon_ids}
    for row in rows:
        tendon_id = row["Tendon ID"]
        if tendon_id not in by_id:
            errors.append(f"Profile point references unknown Tendon ID '{tendon_id}'.")
            continue
        by_id[tendon_id].append(row)
        if not (0.0 <= row["s (m)"] <= length_m):
            errors.append(f"{tendon_id} {row['Point']}: station s must lie between 0 and L.")
        if abs(row["x lateral (mm)"]) > width_mm / 2.0:
            errors.append(f"{tendon_id} {row['Point']}: lateral x lies outside the section width.")
        if not (0.0 <= row["dtop (mm)"] <= height_mm):
            errors.append(f"{tendon_id} {row['Point']}: dtop must lie between the top and bottom surfaces.")

    tolerance = max(1e-6, length_m * 1e-6)
    for tendon_id in tendon_ids:
        points = sorted(by_id.get(tendon_id, []), key=lambda row: row["s (m)"])
        if len(points) < 2:
            errors.append(f"{tendon_id}: at least two geometry points are required.")
            continue
        if abs(points[0]["s (m)"]) > tolerance:
            errors.append(f"{tendon_id}: first point must be at the left anchorage s = 0.")
        if abs(points[-1]["s (m)"] - length_m) > tolerance:
            errors.append(f"{tendon_id}: final point must be at the right anchorage s = L.")
    return list(dict.fromkeys(errors))


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


def _plan_figure(points: list[dict[str, Any]], active_ids: list[str], segment_rows: list[dict[str, Any]], width_mm: float) -> go.Figure:
    fig = go.Figure()
    _segment_bands(fig, segment_rows)
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
    fig.update_yaxes(range=[-0.58 * width_mm, 0.58 * width_mm])
    return fig


def _profile_figure(points: list[dict[str, Any]], active_ids: list[str], segment_rows: list[dict[str, Any]], height_mm: float) -> go.Figure:
    fig = go.Figure()
    _segment_bands(fig, segment_rows)
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
    fig.add_hline(y=height_mm, line={"color": "#31465a", "width": 1.4}, annotation_text="Bottom surface")
    fig.update_layout(**_base_figure_layout("Tendon Profile — Depth Referenced from Top", "Station s (m)", "Depth from top dtop (mm)", height=500))
    fig.update_yaxes(range=[height_mm * 1.08, -height_mm * 0.08])
    return fig


def _box_mesh(
    *,
    s0: float,
    s1: float,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    name: str,
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
        opacity=opacity,
        name=name,
        showlegend=showlegend,
        hoverinfo="name",
        flatshading=True,
    )


def _three_d_figure(
    points: list[dict[str, Any]],
    active_ids: list[str],
    segment_rows: list[dict[str, Any]],
    *,
    width_mm: float,
    height_mm: float,
    context: Mapping[str, float],
    transparent: bool,
) -> go.Figure:
    fig = go.Figure()
    opacity = 0.13 if transparent else 0.42
    role_legend: set[str] = set()
    for row in segment_rows:
        role = row["Section role"]
        start = row["x_start_m"]
        end = row["x_end_m"]
        if role == "Hollow":
            tt = min(context["t_top_mm"], 0.45 * height_mm)
            tb = min(context["t_bottom_mm"], 0.45 * height_mm)
            tl = min(context["t_left_mm"], 0.45 * width_mm)
            tr = min(context["t_right_mm"], 0.45 * width_mm)
            # Four wall prisms make the void visible without boolean 3D geometry.
            wall_specs = [
                (-width_mm / 2.0, width_mm / 2.0, height_mm / 2.0 - tt, height_mm / 2.0),
                (-width_mm / 2.0, width_mm / 2.0, -height_mm / 2.0, -height_mm / 2.0 + tb),
                (-width_mm / 2.0, -width_mm / 2.0 + tl, -height_mm / 2.0 + tb, height_mm / 2.0 - tt),
                (width_mm / 2.0 - tr, width_mm / 2.0, -height_mm / 2.0 + tb, height_mm / 2.0 - tt),
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
                    y0=-height_mm / 2.0,
                    y1=height_mm / 2.0,
                    name="Solid segment",
                    opacity=opacity,
                    showlegend="Solid" not in role_legend,
                )
            )
            role_legend.add("Solid")

    for tendon_id in active_ids:
        rows = [row for row in points if row["Tendon ID"] == tendon_id]
        rows.sort(key=lambda row: row["s (m)"])
        if not rows:
            continue
        fig.add_trace(
            go.Scatter3d(
                x=[row["s (m)"] for row in rows],
                y=[row["x lateral (mm)"] for row in rows],
                z=[height_mm / 2.0 - row["dtop (mm)"] for row in rows],
                mode="lines+markers",
                line={"width": 6},
                marker={"size": 4},
                name=tendon_id,
                customdata=[[row["Point"], row["dtop (mm)"]] for row in rows],
                hovertemplate="%{fullData.name}<br>s=%{x:.3f} m<br>x=%{y:.1f} mm<br>dtop=%{customdata[1]:.1f} mm<br>%{customdata[0]}<extra></extra>",
            )
        )

    fig.update_layout(
        title={"text": "Crossbeam Tendon Isometric Review", "x": 0.5, "xanchor": "center"},
        height=650,
        margin={"l": 20, "r": 20, "t": 70, "b": 20},
        paper_bgcolor="white",
        font={"family": "Arial, sans-serif", "size": 12},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "center", "x": 0.5},
        scene={
            "xaxis": {"title": "Station s (m)", "backgroundcolor": "white", "gridcolor": "#e4eaf0"},
            "yaxis": {"title": "Lateral x (mm)", "backgroundcolor": "white", "gridcolor": "#e4eaf0"},
            "zaxis": {"title": "Vertical y (mm)", "backgroundcolor": "white", "gridcolor": "#e4eaf0"},
            "aspectmode": "manual",
            "aspectratio": {"x": 3.2, "y": 1.1, "z": 0.8},
            "camera": {"eye": {"x": 1.55, "y": 1.45, "z": 1.05}},
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
        "One row represents one complete tendon. Plan/Profile/3D geometry is edited separately in Tendon Profile.",
        mark="T",
    )

    existing_system = _records(st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY))
    current_count = max(len(existing_system), 2)
    tendon_count = int(
        st.number_input(
            "Number of tendons",
            min_value=2,
            max_value=64,
            value=current_count,
            step=1,
            key=CB_TENDON_COUNT_KEY,
            help="The crossbeam may contain more than two tendons. Anchorage heads remain at both crossbeam ends.",
        )
    )

    if st.button("Reset tendon system to default", key="crossbeam_ui1_reset_tendon_system"):
        seed_profile = default_crossbeam_tendon_rows(
            float(st.session_state.get(CB_LENGTH_KEY, DEFAULT_CROSSBEAM_LENGTH_M)),
            tendon_count=tendon_count,
            section_depth_mm=_section_context()["height_mm"],
        )
        st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = _system_rows_from_legacy(seed_profile, tendon_count)
        st.session_state[CB_TENDON_SYSTEM_REV_KEY] = int(st.session_state.get(CB_TENDON_SYSTEM_REV_KEY, 0)) + 1
        st.session_state[CB_PROFILE_ROWS_KEY] = _profile_points_from_legacy(
            seed_profile,
            length_m=float(st.session_state.get(CB_LENGTH_KEY, DEFAULT_CROSSBEAM_LENGTH_M)),
            tendon_ids=[f"T{index + 1}" for index in range(tendon_count)],
            width_mm=_section_context()["width_mm"],
            height_mm=_section_context()["height_mm"],
        )
        st.session_state[CB_PROFILE_REV_KEY] = int(st.session_state.get(CB_PROFILE_REV_KEY, 0)) + 1
        st.rerun()

    # Reconcile row count before the widget exists; never mutate its bound key afterward.
    rows = existing_system
    if tendon_count != len(rows):
        current_by_id = _system_by_id(rows)
        reconciled: list[dict[str, Any]] = []
        for index in range(tendon_count):
            tendon_id = f"T{index + 1}"
            reconciled.append(
                current_by_id.get(
                    tendon_id,
                    {
                        "Tendon ID": tendon_id,
                        "Type": DEFAULT_TENDON_TYPE,
                        "Strands": DEFAULT_STRANDS_PER_TENDON,
                        "Aps/strand mm²": DEFAULT_STRAND_APS_MM2,
                        "fpu MPa": DEFAULT_STRAND_FPU_MPA,
                        "fpj/fpu": DEFAULT_FPJ_RATIO,
                        "Jacking end": DEFAULT_JACKING_END,
                        "Left anchorage": "s = 0",
                        "Right anchorage": "s = L",
                    },
                )
            )
        rows = reconciled
        st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = rows

    revision = int(st.session_state.get(CB_TENDON_SYSTEM_REV_KEY, 0))
    edited = st.data_editor(
        pd.DataFrame(rows),
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        key=f"crossbeam_ui1_tendon_system_editor_{revision}",
        column_config={
            "Tendon ID": st.column_config.TextColumn("Tendon ID", required=True),
            "Type": st.column_config.SelectboxColumn("Type", options=list(TENDON_TYPE_OPTIONS), required=True),
            "Strands": st.column_config.NumberColumn("Strands", min_value=1, step=1, required=True),
            "Aps/strand mm²": st.column_config.NumberColumn("Aps/strand (mm²)", min_value=1.0, format="%.1f"),
            "fpu MPa": st.column_config.NumberColumn("fpu (MPa)", min_value=1.0, format="%.1f"),
            "fpj/fpu": st.column_config.NumberColumn("fpj/fpu", min_value=0.0, max_value=1.0, format="%.3f"),
            "Jacking end": st.column_config.SelectboxColumn("Jacking end", options=list(JACKING_END_OPTIONS), required=True),
            "Left anchorage": st.column_config.TextColumn("Left anchorage", disabled=True),
            "Right anchorage": st.column_config.TextColumn("Right anchorage", disabled=True),
        },
        disabled=["Left anchorage", "Right anchorage"],
    )
    system_rows = _records(edited)
    st.session_state[CB_TENDON_SYSTEM_ROWS_KEY] = system_rows

    valid_ids = [item for item in _tendon_ids(system_rows) if item]
    duplicate_ids = sorted({item for item in valid_ids if valid_ids.count(item) > 1})
    invalid_rows = [row for row in system_rows if not str(row.get("Tendon ID") or "").strip()]
    status = "READY" if not duplicate_ids and not invalid_rows else "REVIEW REQUIRED"
    status_kind = "ready" if status == "READY" else "warning"
    total_aps = sum(max(_finite_int(row.get("Strands"), 0), 0) * max(_finite_float(row.get("Aps/strand mm²"), 0.0), 0.0) for row in system_rows)
    render_metric_cards(
        [
            {"title": "Tendon system", "value": status, "detail": "Unique Tendon IDs required", "status": status_kind},
            {"title": "Tendons", "value": len(system_rows), "detail": "Complete tendon rows", "status": "info"},
            {"title": "Total Aps", "value": f"{total_aps:,.0f} mm²", "detail": "Sum of strands × Aps/strand", "status": "neutral"},
            {"title": "Default fpj", "value": f"{calculated_fpj_mpa():,.0f} MPa", "detail": "0.75 fpu; editable per tendon", "status": "info"},
        ]
    )
    if duplicate_ids:
        st.warning("Duplicate Tendon IDs: " + ", ".join(duplicate_ids))
    if invalid_rows:
        st.warning("Every tendon row requires a Tendon ID.")
    st.info(
        "Anchorage heads are modeled at both ends (s = 0 and s = L). Jacking end Left/Right/Both controls future loss distribution; both-end jacking does not double total Pj."
    )
    st.caption(
        "CROSSBEAM.UI1 geometry workspace only. ACI 423.10R loss calculations, friction parameters, anchor set, elastic shortening, time-dependent losses, and FEA handoff remain future milestones."
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
    length_m = _length_input()

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
        "Tendon Profile",
        "Edit one shared tendon geometry source and review it consistently in Plan, Profile, and 3D without running prestress-loss or strength solvers.",
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
    length_m = _length_input()
    system_rows = _records(st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY))
    tendon_ids = _tendon_ids(system_rows)
    if not tendon_ids:
        st.warning("Define the Tendon System before editing profile geometry.")
        return

    if st.button("Reset tendon geometry to three-point profiles", key="crossbeam_ui1_reset_profile"):
        seed = default_crossbeam_tendon_rows(
            length_m,
            tendon_count=len(tendon_ids),
            section_depth_mm=context["height_mm"],
        )
        st.session_state[CB_PROFILE_ROWS_KEY] = _profile_points_from_legacy(
            seed,
            length_m=length_m,
            tendon_ids=tendon_ids,
            width_mm=context["width_mm"],
            height_mm=context["height_mm"],
        )
        st.session_state[CB_PROFILE_REV_KEY] = int(st.session_state.get(CB_PROFILE_REV_KEY, 0)) + 1
        st.rerun()

    revision = int(st.session_state.get(CB_PROFILE_REV_KEY, 0))
    source_rows = _records(st.session_state.get(CB_PROFILE_ROWS_KEY))
    edited = st.data_editor(
        pd.DataFrame(source_rows),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"crossbeam_ui1_profile_editor_{revision}",
        column_config={
            "Tendon ID": st.column_config.SelectboxColumn("Tendon ID", options=tendon_ids, required=True),
            "Point": st.column_config.TextColumn("Point", required=True),
            "s/L": st.column_config.NumberColumn("s/L", min_value=0.0, max_value=1.0, format="%.4f"),
            "s (m)": st.column_config.NumberColumn("s (m)", min_value=0.0, max_value=length_m, format="%.3f", required=True),
            "x lateral (mm)": st.column_config.NumberColumn("x lateral (mm)", format="%.1f", required=True),
            "dtop (mm)": st.column_config.NumberColumn("dtop (mm)", min_value=0.0, max_value=context["height_mm"], format="%.1f", required=True),
            "Curve role": st.column_config.SelectboxColumn("Curve role", options=["Anchorage", "Profile point", "High point", "Low point", "Deviator"], required=True),
        },
    )
    raw_points = _records(edited)
    st.session_state[CB_PROFILE_ROWS_KEY] = raw_points
    points = _normalize_profile_points(raw_points, length_m)

    segment_rows, segment_errors = _validate_segments(_records(st.session_state.get(CB_SEGMENT_ROWS_KEY)), length_m)
    profile_errors = _validate_profile_points(
        points,
        tendon_ids=tendon_ids,
        length_m=length_m,
        width_mm=context["width_mm"],
        height_mm=context["height_mm"],
    )
    all_errors = segment_errors + profile_errors

    active_default = [item for item in _records(st.session_state.get(CB_TENDON_SYSTEM_ROWS_KEY)) if item]
    _ = active_default
    active_ids = st.multiselect(
        "Visible tendons",
        options=tendon_ids,
        default=[item for item in st.session_state.get(CB_ACTIVE_TENDONS_KEY, tendon_ids) if item in tendon_ids],
        key=CB_ACTIVE_TENDONS_KEY,
        help="Visibility changes review figures only; it does not exclude a tendon from the model.",
    )
    transparent = st.toggle(
        "Transparent 3D concrete",
        value=bool(st.session_state.get(CB_3D_TRANSPARENT_KEY, True)),
        key=CB_3D_TRANSPARENT_KEY,
    )

    internal_count = sum(str(row.get("Type") or "").casefold() == "internal" for row in system_rows)
    external_count = sum(str(row.get("Type") or "").casefold() == "external" for row in system_rows)
    render_metric_cards(
        [
            {
                "title": "Geometry status",
                "value": "LAYOUT READY" if not all_errors else "LAYOUT REQUIRED",
                "detail": "Plan/Profile/3D use the same point table",
                "status": "ready" if not all_errors else "warning",
            },
            {"title": "Tendons", "value": len(tendon_ids), "detail": f"Internal {internal_count} · External {external_count}", "status": "info"},
            {"title": "Profile points", "value": len(points), "detail": "Editable control points", "status": "neutral"},
            {"title": "Vertical reference", "value": "dtop", "detail": "Measured downward from top surface", "status": "info"},
        ]
    )
    if all_errors:
        with st.expander("Geometry validation issues", expanded=True):
            for error in all_errors:
                st.error(error)

    plan_tab, profile_tab, three_d_tab, audit_tab = st.tabs(["Plan", "Profile", "3D", "Calculated Audit"])
    with plan_tab:
        st.plotly_chart(
            _plan_figure(points, active_ids, segment_rows, context["width_mm"]),
            use_container_width=True,
            config=FIGURE_CONFIG,
        )
        st.caption("Plan uses station s and lateral section coordinate x. x = 0 is the crossbeam centerline.")
    with profile_tab:
        st.plotly_chart(
            _profile_figure(points, active_ids, segment_rows, context["height_mm"]),
            use_container_width=True,
            config=FIGURE_CONFIG,
        )
        st.caption("Profile uses dtop measured downward from the top surface; the vertical axis is intentionally inverted.")
    with three_d_tab:
        st.plotly_chart(
            _three_d_figure(
                points,
                active_ids,
                segment_rows,
                width_mm=context["width_mm"],
                height_mm=context["height_mm"],
                context=context,
                transparent=transparent,
            ),
            use_container_width=True,
            config=FIGURE_CONFIG,
        )
        st.caption(
            "3D is a geometry review view. Hollow segments use four wall prisms so the void remains visible; fillets, chamfers, ducts, anchor hardware, and deviator hardware are schematic in UI1."
        )
    with audit_tab:
        system_map = _system_by_id(system_rows)
        audit_rows: list[dict[str, Any]] = []
        centroid_top = context["centroid_from_top_mm"]
        for row in points:
            tendon = system_map.get(row["Tendon ID"], {})
            fpu = _finite_float(tendon.get("fpu MPa"), DEFAULT_STRAND_FPU_MPA)
            fpj_ratio = _finite_float(tendon.get("fpj/fpu"), DEFAULT_FPJ_RATIO)
            strands = _finite_int(tendon.get("Strands"), DEFAULT_STRANDS_PER_TENDON)
            aps = _finite_float(tendon.get("Aps/strand mm²"), DEFAULT_STRAND_APS_MM2)
            audit_rows.append(
                {
                    "Tendon ID": row["Tendon ID"],
                    "Point": row["Point"],
                    "s/L": round(row["s/L"], 5),
                    "s (m)": round(row["s (m)"], 4),
                    "x (mm)": round(row["x lateral (mm)"], 2),
                    "dtop (mm)": round(row["dtop (mm)"], 2),
                    "centroid from top (mm)": round(centroid_top, 2),
                    "e(s) (mm)": round(row["dtop (mm)"] - centroid_top, 2),
                    "Type": tendon.get("Type", DEFAULT_TENDON_TYPE),
                    "Jacking end": tendon.get("Jacking end", DEFAULT_JACKING_END),
                    "fpj (MPa)": round(calculated_fpj_mpa(fpu, fpj_ratio), 2),
                    "Aps total (mm²)": round(strands * aps, 2),
                }
            )
        st.dataframe(pd.DataFrame(audit_rows), use_container_width=True, hide_index=True)
        st.caption(
            "e(s) is positive when the tendon lies below the active section centroid. UI1 uses the currently selected section centroid as a preview; station-specific Section ID properties are implemented in a later station-analysis milestone."
        )

    st.warning(
        "Scope guard: these figures do not calculate friction, wobble, anchorage set, elastic shortening, creep, shrinkage, relaxation, SLS stress, ULS strength, anchorage zones, deviator forces, or solid/hollow transition D-regions."
    )
