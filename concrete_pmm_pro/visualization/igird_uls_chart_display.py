"""Presentation helpers for multi-row CSI I-Girder charts; never alter check tables."""
from __future__ import annotations

import math
import re

import pandas as pd


def interface_station_envelope(result_df: pd.DataFrame) -> pd.DataFrame:
    """Display scalar max demand/min resistance; keep the controlling source case.

    This is a plotting view only. D/C and acceptance remain those of each
    original check row, not ratios of independently enveloped quantities.
    """
    frame = result_df.copy(deep=True)
    for field in ('Station x (m)', 'vui (MPa)', 'phi vni (MPa)'):
        frame[field] = pd.to_numeric(frame[field], errors='coerce')
    rows = []
    for x, group in frame.groupby('Station x (m)', sort=True):
        if not math.isfinite(float(x)):
            continue
        row = {'Station x (m)': float(x), 'Source rows': len(group)}
        for field, pick, case_field in (
            ('vui (MPa)', 'max', 'Demand source case'),
            ('phi vni (MPa)', 'min', 'Resistance source case'),
        ):
            finite = group.loc[group[field].map(lambda v: pd.notna(v) and math.isfinite(float(v)))]
            if finite.empty:
                row[field], row[case_field] = float('nan'), 'UNAVAILABLE'
            else:
                value = finite[field].max() if pick == 'max' else finite[field].min()
                original = finite.loc[finite[field].eq(value)].iloc[0]
                row[field], row[case_field] = float(value), str(original.get('Case') or '-')
        rows.append(row)
    return pd.DataFrame(rows, columns=['Station x (m)', 'vui (MPa)', 'phi vni (MPa)',
        'Demand source case', 'Resistance source case', 'Source rows'])


def compact_csi_flexure_demand_labels(fig) -> None:
    """Keep Max/Min and occurrence visible instead of truncating their shared prefix."""
    labels = {}
    native = []
    for trace in fig.data:
        name = str(trace.name or '')
        if not name.startswith('Demand Mux') or '—' not in name:
            continue
        case = name.split('—', 1)[1].strip()
        match = re.search(r'/\s*(Max|Min)\s*/\s*set\s+(\d+)\s*$', case)
        if match:
            label = f'Mux {match.group(1)} {match.group(2)}'
            labels[label] = labels.get(label, 0) + 1
            native.append((trace, case, match.group(1), match.group(2), label))
    for index, (trace, case, step, occurrence, label) in enumerate(native, 1):
        trace.name = label if labels[label] == 1 else f'Mux {step} C{index}'
        trace.legendgroup = 'igird_demand_' + case
        trace.customdata = [[case] for _ in trace.x]
        trace.hovertemplate = 'x=%{x:.3f} m<br>Mux=%{y:.3f} kN-m<br>%{customdata[0]}<extra></extra>'
        # All demand remains blue; the lower bound uses a dotted pattern.
        trace.line.dash = 'solid' if step == 'Max' else 'dot'
        trace.marker.symbol = 'circle' if occurrence == '1' else 'diamond'


def deduplicate_coincident_flexure_capacity(fig) -> None:
    """Drop only curves proven to coincide with one covering original curve.

    Different capacities and any missing-equilibrium gaps remain in the figure.
    The common resistance legend entry is shown once even when curves differ.
    """
    traces = [trace for trace in fig.data if str(trace.name or '') == 'φMn']
    if not traces:
        return

    def points(trace):
        output = {}
        for x, y in zip(trace.x, trace.y):
            try:
                x, y = float(x), float(y)
            except (TypeError, ValueError):
                return None
            if not math.isfinite(x) or not math.isfinite(y):
                return None
            if x in output and output[x] != y:
                return None
            output[x] = y
        return output

    anchor = max(traces, key=lambda trace: len(trace.x))
    anchor_points = points(anchor)
    can_merge = bool(anchor_points)
    for trace in traces:
        coordinates = points(trace)
        if coordinates is None or anchor_points is None or any(
            x not in anchor_points or anchor_points[x] != y for x, y in coordinates.items()
        ):
            can_merge = False
            break
    if can_merge and len(traces) > 1:
        fig.data = tuple(trace for trace in fig.data if str(trace.name or '') != 'φMn' or trace is anchor)
        traces = [anchor]
    for index, trace in enumerate(traces):
        trace.legendgroup = 'igird_phi_mn'
        trace.showlegend = index == 0
