"""Shared full-length chart foundation for Portal Frame Crossbeam Analysis.

``CROSSBEAM.ANALYSIS1A`` introduces a solver-neutral longitudinal chart shell
that later SLS and ULS milestones reuse.  The chart shows the physical member
extent, Segment/Zone bands, internal boundaries, Column footprints and
centerlines, and the imported station-check contexts.  It deliberately does not
interpolate a certified result envelope between sparse imported stations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import plotly.graph_objects as go

from concrete_pmm_pro.crossbeam.analysis_foundation import (
    DATASET_ORDER,
    DATASET_SLS_SERVICE,
    DATASET_SLS_TRANSFER,
    DATASET_ULS_FINAL,
    FACE_LEFT,
    FACE_RIGHT,
)
from concrete_pmm_pro.visualization.plot_readability import apply_global_plot_readability


_DATASET_Y = {
    DATASET_ULS_FINAL: 3.0,
    DATASET_SLS_TRANSFER: 2.0,
    DATASET_SLS_SERVICE: 1.0,
}

_DATASET_SYMBOL = {
    DATASET_ULS_FINAL: "diamond",
    DATASET_SLS_TRANSFER: "circle",
    DATASET_SLS_SERVICE: "square",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _face_symbol(face: Any, dataset: str) -> str:
    text = _text(face)
    if text == FACE_LEFT:
        return "triangle-left"
    if text == FACE_RIGHT:
        return "triangle-right"
    return _DATASET_SYMBOL.get(dataset, "circle")


def _segment_band_fill(role: Any, index: int) -> str:
    if _text(role).casefold() == "hollow":
        return "rgba(226, 142, 46, 0.075)"
    return "rgba(42, 107, 161, 0.060)" if index % 2 == 0 else "rgba(42, 107, 161, 0.030)"


def make_crossbeam_station_coverage_figure(foundation: Mapping[str, Any]) -> go.Figure:
    """Return the reusable full-length source-coverage chart.

    The y-axis is intentionally categorical: each required Analysis dataset gets
    one horizontal track.  Future SLS/ULS figures will reuse the same structural
    landmark helpers while replacing these source markers with actual stress,
    demand, capacity, and utilization traces.
    """

    length = max(_float(foundation.get("member_length_m")), 0.0)
    segments = _rows(foundation.get("segments"))
    columns = _rows(foundation.get("columns"))
    footprints = _rows(foundation.get("column_footprints"))
    boundaries = _rows(foundation.get("internal_boundaries"))
    mapped_rows = _rows(foundation.get("mapped_rows"))

    fig = go.Figure()

    # Segment/Zone bands span the complete plot height so Section changes remain
    # visible under every future result trace.
    for index, segment in enumerate(segments):
        x0 = _float(segment.get("x_start_m"))
        x1 = _float(segment.get("x_end_m"))
        if x1 <= x0:
            continue
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor=_segment_band_fill(segment.get("Section role"), index),
            opacity=1.0,
            line_width=0,
            layer="below",
        )
        fig.add_annotation(
            x=0.5 * (x0 + x1),
            y=1.015,
            yref="paper",
            text=(
                f"{_text(segment.get('Segment'))} · {_text(segment.get('Section ID'))}"
                f" · {_text(segment.get('Section role'))}"
            ),
            showarrow=False,
            font={"size": 10},
        )

    # Column footprints use the actual dimension along the Crossbeam station
    # axis.  The centerline is shown separately so the user can distinguish the
    # structural frame joint from the physical support width.
    footprint_by_id = {
        _text(row.get("Column")): row
        for row in footprints
        if _text(row.get("Column"))
    }
    for column in columns:
        column_id = _text(column.get("Column ID"))
        station = _float(column.get("Station s (m)"))
        footprint = footprint_by_id.get(column_id, {})
        x0 = _float(footprint.get("s_left (m)"), station)
        x1 = _float(footprint.get("s_right (m)"), station)
        if x1 > x0:
            fig.add_vrect(
                x0=max(0.0, x0),
                x1=min(length, x1),
                fillcolor="rgba(71, 85, 105, 0.105)",
                opacity=1.0,
                line={"color": "rgba(71, 85, 105, 0.30)", "width": 1},
                layer="below",
            )
        fig.add_vline(
            x=station,
            line={"color": "rgba(30, 41, 59, 0.88)", "width": 1.6, "dash": "dash"},
            layer="above",
        )
        fig.add_annotation(
            x=station,
            y=1.115,
            yref="paper",
            text=f"{column_id}<br>s = {station:.3f} m",
            showarrow=False,
            font={"size": 10},
        )

    for boundary in boundaries:
        station = _float(boundary.get("Station s (m)"))
        physical = _text(boundary.get("Boundary type")) == "Physical segment joint"
        fig.add_vline(
            x=station,
            line={
                "color": "rgba(180, 83, 9, 0.82)" if physical else "rgba(51, 65, 85, 0.58)",
                "width": 1.5,
                "dash": "dashdot" if physical else "dot",
            },
            layer="above",
        )

    # Member ends are explicit structural landmarks, not merely axis limits.
    for station in (0.0, length):
        fig.add_vline(
            x=station,
            line={"color": "rgba(15, 23, 42, 0.72)", "width": 1.6},
            layer="above",
        )

    for dataset in DATASET_ORDER:
        rows = [row for row in mapped_rows if _text(row.get("Dataset")) == dataset]
        if not rows:
            continue
        x_values = [_float(row.get("Station s (m)")) for row in rows]
        y_values = [_DATASET_Y[dataset]] * len(rows)
        symbols = [_face_symbol(row.get("Station face"), dataset) for row in rows]
        customdata = [
            [
                _text(row.get("Case / Combination")),
                _text(row.get("Check Point")) or "—",
                _text(row.get("Station face")),
                _text(row.get("Segment / Zone")),
                _text(row.get("Section ID")),
                _text(row.get("Column ID")) or "—",
                _text(row.get("Context status")),
                _text(row.get("Source row")),
            ]
            for row in rows
        ]
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="markers",
                name=dataset,
                marker={
                    "symbol": symbols,
                    "size": 11,
                    "line": {"width": 1.2, "color": "rgba(15, 23, 42, 0.75)"},
                },
                customdata=customdata,
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    "Station s = %{x:.6f} m<br>"
                    "Case: %{customdata[0]}<br>"
                    "Check Point: %{customdata[1]}<br>"
                    "Face: %{customdata[2]}<br>"
                    "Segment / Zone: %{customdata[3]}<br>"
                    "Section ID: %{customdata[4]}<br>"
                    "Column: %{customdata[5]}<br>"
                    "Context: %{customdata[6]}<br>"
                    "Source row: %{customdata[7]}<extra></extra>"
                ),
            )
        )

    if not mapped_rows:
        fig.add_annotation(
            x=0.5 * length,
            y=2.0,
            text="No validated station-force contexts are available",
            showarrow=False,
            font={"size": 14},
        )

    fig.update_layout(
        title={
            "text": "Crossbeam Full-Length Station-Check Source Coverage",
            "x": 0.01,
            "xanchor": "left",
        },
        height=520,
        margin={"l": 80, "r": 30, "t": 105, "b": 70},
        hovermode="closest",
        legend={
            "orientation": "h",
            "x": 0.0,
            "y": -0.22,
            "xanchor": "left",
            "yanchor": "top",
        },
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    fig.update_xaxes(
        title="Station s (m)",
        range=[0.0, length if length > 0.0 else 1.0],
        showgrid=True,
        zeroline=False,
    )
    fig.update_yaxes(
        title="Required dataset",
        range=[0.55, 3.45],
        tickmode="array",
        tickvals=[1.0, 2.0, 3.0],
        ticktext=[DATASET_SLS_SERVICE, DATASET_SLS_TRANSFER, DATASET_ULS_FINAL],
        showgrid=True,
        zeroline=False,
    )
    apply_global_plot_readability(fig)
    return fig


# Accepted Concrete Section Pro engineering-stress chart palette.  Values match
# the Beam/Girder SLS workspace so Crossbeam does not introduce an ad-hoc style.
_ENGINEERING_STRESS_COLORS = {
    "top": "#1565c0",
    "bottom": "#64b5f6",
    "compression_limit": "#e53935",
    "tension_limit": "#ec4899",
    "zero": "#4a4a4a",
    "governing_tension": "#2e7d32",
    "governing_compression": "#00897b",
}


def _stress_face_order(face: Any) -> int:
    text = _text(face)
    if text == FACE_LEFT:
        return 0
    if text == FACE_RIGHT:
        return 2
    return 1


def _add_result_landmarks(fig: go.Figure, foundation: Mapping[str, Any]) -> None:
    """Add restrained Column footprints/centerlines and physical-joint lines."""

    length = max(_float(foundation.get("member_length_m")), 0.0)
    columns = _rows(foundation.get("columns"))
    footprints = _rows(foundation.get("column_footprints"))
    boundaries = _rows(foundation.get("internal_boundaries"))
    footprint_by_id = {
        _text(row.get("Column")): row
        for row in footprints
        if _text(row.get("Column"))
    }
    for column in columns:
        column_id = _text(column.get("Column ID"))
        station = _float(column.get("Station s (m)"))
        footprint = footprint_by_id.get(column_id, {})
        x0 = _float(footprint.get("s_left (m)"), station)
        x1 = _float(footprint.get("s_right (m)"), station)
        if x1 > x0:
            fig.add_vrect(
                x0=max(0.0, x0),
                x1=min(length, x1),
                fillcolor="rgba(71, 85, 105, 0.075)",
                opacity=1.0,
                line_width=0,
                layer="below",
            )
        fig.add_vline(
            x=station,
            line={"color": "rgba(30, 41, 59, 0.52)", "width": 1.25, "dash": "dot"},
            layer="below",
        )
        fig.add_annotation(
            x=station,
            y=1.025,
            yref="paper",
            text=column_id,
            showarrow=False,
            font={"size": 10, "color": "#334155"},
        )
    for boundary in boundaries:
        if _text(boundary.get("Boundary type")) != "Physical segment joint":
            continue
        fig.add_vline(
            x=_float(boundary.get("Station s (m)")),
            line={"color": "rgba(180, 83, 9, 0.50)", "width": 1.2, "dash": "dashdot"},
            layer="below",
        )
    for station in (0.0, length):
        fig.add_vline(
            x=station,
            line={"color": "rgba(15, 23, 42, 0.52)", "width": 1.2},
            layer="below",
        )


def make_crossbeam_transfer_stress_figure(
    foundation: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    case_name: str,
) -> go.Figure:
    """Return the full-length ACI transfer-stress chart for one imported case."""

    rows = [
        dict(row)
        for row in _rows(result.get("rows"))
        if _text(row.get("Case / Combination")) == _text(case_name)
    ]
    rows.sort(
        key=lambda row: (
            _float(row.get("Station s (m)")),
            _stress_face_order(row.get("Station face")),
            _text(row.get("Context ID")),
        )
    )
    fig = go.Figure()
    if not rows:
        return fig

    _add_result_landmarks(fig, foundation)
    x = [_float(row.get("Station s (m)")) for row in rows]
    faces = [_text(row.get("Station face")) for row in rows]
    symbols = [_face_symbol(face, DATASET_SLS_TRANSFER) for face in faces]
    customdata = [
        [
            _text(row.get("Station face")),
            _text(row.get("Segment / Zone")),
            _text(row.get("Section ID")),
            _text(row.get("Material")),
            _float(row.get("f'ci (MPa)")),
            _text(row.get("Check Point")) or "—",
        ]
        for row in rows
    ]

    def add_stress_trace(field: str, name: str, color: str) -> None:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[_float(row.get(field)) for row in rows],
                mode="lines+markers",
                name=name,
                line={"width": 3.0, "color": color},
                marker={
                    "symbol": symbols,
                    "size": 9,
                    "color": color,
                    "line": {"width": 1.0, "color": "rgba(15,23,42,0.55)"},
                },
                customdata=customdata,
                hovertemplate=(
                    f"<b>{name}</b><br>"
                    "s=%{x:.6f} m<br>stress=%{y:.3f} MPa<br>"
                    "face=%{customdata[0]}<br>segment=%{customdata[1]}<br>"
                    "section=%{customdata[2]}<br>material=%{customdata[3]}<br>"
                    "f'ci=%{customdata[4]:.3f} MPa<br>check point=%{customdata[5]}<extra></extra>"
                ),
            )
        )

    add_stress_trace("Top stress (MPa)", "Top total stress", _ENGINEERING_STRESS_COLORS["top"])
    add_stress_trace("Bottom stress (MPa)", "Bottom total stress", _ENGINEERING_STRESS_COLORS["bottom"])
    compression_limits = [_float(row.get("Compression limit (MPa)")) for row in rows]
    tension_limits = [_float(row.get("Tension limit (MPa)")) for row in rows]
    fci_values = [_float(row.get("f'ci (MPa)")) for row in rows]
    compression_formulae = [
        f"−0.60f′ci = −0.60({fci:.2f}) = −{abs(limit):.2f} MPa"
        for fci, limit in zip(fci_values, compression_limits)
    ]
    tension_formulae = [
        f"+0.25√f′ci = +0.25√({fci:.2f}) = +{limit:.2f} MPa"
        for fci, limit in zip(fci_values, tension_limits)
    ]
    fig.add_trace(
        go.Scatter(
            x=x,
            y=compression_limits,
            mode="lines",
            name="Compression limit",
            line={"width": 3.0, "dash": "dash", "color": _ENGINEERING_STRESS_COLORS["compression_limit"]},
            customdata=[[fci, formula] for fci, formula in zip(fci_values, compression_formulae)],
            hovertemplate=(
                "s=%{x:.6f} m<br>compression limit=%{y:.3f} MPa<br>"
                "f′ci=%{customdata[0]:.3f} MPa<br>%{customdata[1]}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=tension_limits,
            mode="lines",
            name="Tension limit",
            line={"width": 3.0, "dash": "dash", "color": _ENGINEERING_STRESS_COLORS["tension_limit"]},
            customdata=[[fci, formula] for fci, formula in zip(fci_values, tension_formulae)],
            hovertemplate=(
                "s=%{x:.6f} m<br>tension limit=%{y:.3f} MPa<br>"
                "f′ci=%{customdata[0]:.3f} MPa<br>%{customdata[1]}<extra></extra>"
            ),
        )
    )

    # Keep the graph decision-first: show one concise equation/substitution label
    # directly on each dashed limit line.  When f′ci varies by station, the
    # right-most local substitution is shown and the hover trace retains the
    # exact equation at every imported station.
    right_index = len(rows) - 1
    right_fci = fci_values[right_index]
    right_compression_limit = compression_limits[right_index]
    right_tension_limit = tension_limits[right_index]
    fci_varies = len({round(value, 9) for value in fci_values}) > 1
    variation_note = " · local f′ci varies" if fci_varies else ""
    annotation_common = {
        "xref": "paper",
        "yref": "y",
        "x": 0.985,
        "showarrow": False,
        "xanchor": "right",
        "bgcolor": "rgba(255,255,255,0.88)",
        "borderwidth": 0,
        "align": "right",
    }
    fig.add_annotation(
        **annotation_common,
        y=right_compression_limit,
        yshift=8,
        yanchor="bottom",
        text=(
            "Compression limit: "
            f"−0.60f′ci = −0.60({right_fci:.2f}) = −{abs(right_compression_limit):.2f} MPa"
            f"{variation_note}"
        ),
        font={"size": 10, "color": _ENGINEERING_STRESS_COLORS["compression_limit"]},
    )
    fig.add_annotation(
        **annotation_common,
        y=right_tension_limit,
        yshift=8,
        yanchor="bottom",
        text=(
            "Tension limit: "
            f"+0.25√f′ci = +0.25√({right_fci:.2f}) = +{right_tension_limit:.2f} MPa"
            f"{variation_note}"
        ),
        font={"size": 10, "color": _ENGINEERING_STRESS_COLORS["tension_limit"]},
    )
    fig.add_hline(
        y=0.0,
        line={"width": 1.3, "dash": "dot", "color": _ENGINEERING_STRESS_COLORS["zero"]},
        layer="below",
    )

    for key, label, color, position in (
        ("governing_compression", "Gov. Compression", _ENGINEERING_STRESS_COLORS["governing_compression"], "bottom center"),
        ("governing_tension", "Gov. Tension", _ENGINEERING_STRESS_COLORS["governing_tension"], "top center"),
    ):
        governing = result.get(key)
        if not isinstance(governing, Mapping) or _text(governing.get("Case / Combination")) != _text(case_name):
            continue
        fig.add_trace(
            go.Scatter(
                x=[_float(governing.get("Station s (m)"))],
                y=[_float(governing.get("Stress (MPa)"))],
                mode="markers+text",
                name=label,
                marker={"size": 15, "symbol": "circle-open", "color": color, "line": {"width": 3}},
                text=[label],
                textposition=position,
                hovertemplate=(
                    f"{label}<br>s=%{{x:.6f}} m<br>stress=%{{y:.3f}} MPa<br>"
                    f"fiber={_text(governing.get('Fiber'))}<br>"
                    f"face={_text(governing.get('Station face'))}<br>"
                    f"utilization={_float(governing.get('Utilization')):.3f}<extra></extra>"
                ),
            )
        )

    length = max(_float(foundation.get("member_length_m")), 0.0)
    fig.update_layout(
        title={
            "text": (
                "Concrete Stress — At Transfer"
                "<br><sup>ACI 318-19 §24.5.3 · compression negative / tension positive</sup>"
            ),
            "x": 0.5,
            "xanchor": "center",
        },
        height=560,
        margin={"l": 76, "r": 30, "t": 92, "b": 120},
        hovermode="closest",
        legend={
            "orientation": "h",
            "x": 0.5,
            "y": -0.24,
            "xanchor": "center",
            "yanchor": "top",
        },
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    fig.update_xaxes(
        title="Station s (m)",
        range=[0.0, length if length > 0.0 else 1.0],
        showgrid=True,
        zeroline=False,
    )
    fig.update_yaxes(
        title="Stress (MPa) — compression negative / tension positive",
        showgrid=True,
        zeroline=False,
    )
    apply_global_plot_readability(fig)
    return fig


__all__ = ["make_crossbeam_station_coverage_figure", "make_crossbeam_transfer_stress_figure"]
