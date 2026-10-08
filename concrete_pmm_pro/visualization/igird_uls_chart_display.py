"""Presentation helpers for multi-row CSI I-Girder charts; never alter check tables."""
from __future__ import annotations

import math
import re
from html import escape

import pandas as pd


def native_csi_diagram_rows(active_df: pd.DataFrame, *, member_length_m: float | None,
                            source_context_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Use a unique physical end row shared by native CSI occurrence sets.

    Occurrence sets are row ordering, not independent FEA cases. Only the
    physical 0/L endpoints of the same verified sheet/case/Max-or-Min family
    may be shared. No interior station is filled and no force is extrapolated.
    The copy retains the originating row identity; it is never an import or
    design-check table.
    """
    from concrete_pmm_pro.io.girder_csi_import import VERSION, SOURCE_TAG, source_info
    frame = active_df.copy(deep=True)
    context = source_context_df if isinstance(source_context_df, pd.DataFrame) else active_df
    required_fields = ('schema', 'sheet', 'case', 'step', 'distance_column', 'kind')
    source_fields = required_fields + ('source_file','step_number','control')

    def info(row):
        if not isinstance(row.get('Note'), str) or SOURCE_TAG not in row['Note']:
            return None
        metadata = source_info(row)
        if not isinstance(metadata, dict):
            return None
        if (metadata.get('schema') not in {VERSION,'IGIRDER.CSIIMPORT2.auto-detect-v2'} or metadata.get('kind') != 'ENVELOPE'
                or metadata.get('step') not in {'Max', 'Min'}
                or any(not metadata.get(key) for key in required_fields)
                or not isinstance(metadata.get('row'), int)):
            return None
        return metadata

    records = []
    for _, row in frame.iterrows():
        metadata = info(row) or {}
        record = row.to_dict()
        record.update({'__Source case': str(row.get('Case Name') or '-'),
            '__Source sheet': metadata.get('sheet', ''), '__Source row': metadata.get('row', ''),
            '__Shared CSI endpoint': False})
        records.append(record)
    if not records:
        return frame
    try:
        span = float(member_length_m)
    except (TypeError, ValueError):
        span = float('nan')
    if not math.isfinite(span) or span <= 0 or 'Station x (m)' not in context:
        return pd.DataFrame(records)
    source_rows = [(row, info(row)) for _, row in context.iterrows()
        if pd.notna(row.get('Active', True)) and bool(row.get('Active', True))]
    force_columns = ('Mux', 'Vuy', 'Tu', 'Muy', 'Vux', 'Nu')
    for case, group in frame.groupby('Case Name', sort=False):
        metadata = [info(row) for _, row in group.iterrows()]
        if any(item is None for item in metadata):
            continue
        families = {tuple(item.get(key,'') for key in source_fields) for item in metadata}
        if len(families) != 1:
            continue
        family = next(iter(families))
        stations = pd.to_numeric(group['Station x (m)'], errors='coerce')
        for x in (0.0, span):
            # An existing unavailable endpoint must remain unavailable.
            if stations.sub(x).abs().le(1e-8).any():
                continue
            candidates = []
            for row, item in source_rows:
                if item is None or tuple(item.get(key,'') for key in source_fields) != family:
                    continue
                try:
                    at_end = abs(float(row['Station x (m)']) - x) <= 1e-8
                except (TypeError, ValueError):
                    at_end = False
                if at_end:
                    candidates.append((row, item))
            # Multiple end rows do not establish a common endpoint for a
            # missing occurrence. Do not choose a bound or hide a conflict.
            if len(candidates) != 1:
                continue
            row, item = candidates[0]
            try:
                finite = all(math.isfinite(float(row[key])) for key in force_columns)
            except (KeyError, TypeError, ValueError):
                finite = False
            if not finite:
                continue
            record = row.to_dict()
            record.update({'Case Name': case, '__Source case': str(row['Case Name']),
                '__Source sheet': item['sheet'], '__Source row': item['row'],
                '__Shared CSI endpoint': True})
            records.append(record)
    return pd.DataFrame(records).sort_values(['Case Name', 'Station x (m)'], kind='stable').reset_index(drop=True)


def mark_unavailable_capacity(fig, frame: pd.DataFrame, *, metric: str,
                              label: str, x_column: str = '__x_m') -> None:
    """Mark missing resistance at the chart foot, never at a numeric capacity."""
    if frame is None or frame.empty or metric not in frame or x_column not in frame:
        return
    missing = frame.loc[~pd.to_numeric(frame[metric], errors='coerce').map(
        lambda value: pd.notna(value) and math.isfinite(float(value)))]
    rows = []
    for x, group in missing.groupby(x_column, sort=True):
        if not math.isfinite(float(x)):
            continue
        reasons = list(dict.fromkeys(str(v) for v in group.get('Notes', pd.Series(dtype=object)).dropna()))
        cases = list(dict.fromkeys(str(v) for v in group.get('Case', pd.Series(dtype=object)).dropna()))
        reason = '\n'.join(reasons) or 'Resistance source unavailable; see the station audit.'
        rows.append({'x_m': float(x), 'quantity': label, 'cases': cases, 'reason': reason})
        fig.add_annotation(x=float(x), y=0.025, xref='x', yref='paper', text='×', showarrow=False,
            font={'size': 17, 'color': '#64748b'},
            hovertext=f'{label} unavailable at x={float(x):.3f} m<br>'+'<br>'.join(cases)+'<br>'+reason)
    meta = dict(fig.layout.meta or {})
    meta['unavailable_capacity'] = rows
    fig.update_layout(meta=meta)


def mark_overview_gap_status(fig, audit: pd.DataFrame) -> None:
    """Use shared chart-foot status markers, independent of the numeric y-axis."""
    stations = []
    if audit is not None and not audit.empty:
        for x, group in audit.loc[audit['Curve gap']].groupby('Station x (m)', sort=True):
            kinds = set(group['Classification'])
            kind = ('UNAVAILABLE' if 'UNAVAILABLE' in kinds else
                    next(iter(kinds)) if len(kinds) == 1 else 'NOT REQUIRED')
            cases = list(dict.fromkeys(group['Case']))
            statuses = list(dict.fromkeys(group['Stored row status']))
            reasons = list(dict.fromkeys(group['Explanation']))
            stations.append({'x_m': float(x), 'classification': kind,
                'cases': cases, 'stored_statuses': statuses, 'reasons': reasons})
            detail = '<br>'.join(escape(str(value)) for value in [*cases, *statuses, *reasons])
            fig.add_annotation(x=float(x), y=0.025, xref='x', yref='paper',
                text='×' if kind == 'UNAVAILABLE' else '○', showarrow=False,
                font={'size': 17, 'color': '#64748b' if kind == 'UNAVAILABLE' else '#16a34a'},
                hovertext=f'{kind} at x={float(x):.3f} m<br>Status marker only; no numerical D/C is plotted.<br>'+detail)
    meta = dict(fig.layout.meta or {})
    meta['overview_gap_stations'] = stations
    fig.update_layout(meta=meta)


def add_igird_report_note(fig, lines) -> None:
    """Keep explanatory text inside the exported image, outside numeric axes."""
    lines = list(lines)
    fig.add_annotation(name='igird_report_note', x=.5, y=-.47,
        xref='paper', yref='paper', xanchor='center', yanchor='top',
        text='<br>'.join(escape(str(line)) for line in lines), showarrow=False,
        align='center', font={'size':12, 'color':'#475569'})
    fig.update_layout(meta={**dict(fig.layout.meta or {}), 'igird_report_note':lines})
    apply_igird_report_layout(fig)


def apply_igird_report_layout(fig) -> None:
    """Preserve room for report notes after browser/static style application."""
    lines = (fig.layout.meta or {}).get('igird_report_note')
    if lines:
        fig.update_layout(margin={'t':max(int(fig.layout.margin.t or 0),140),
                                  'b':max(int(fig.layout.margin.b or 0),176)},
                          legend={'y':-.27})


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
    compact_csi_demand_labels(fig, component='Mux', unit='kN-m')


def compact_csi_demand_labels(fig, *, component: str, unit: str) -> None:
    """Short source labels with unchanged native force coordinates and full hover."""
    labels = {}
    native = []
    for trace in fig.data:
        name = str(trace.name or '')
        if not name.startswith('Demand '+component) or '—' not in name:
            continue
        case = name.split('—', 1)[1].strip()
        match = re.search(r'/\s*(Max|Min)\s*/\s*set\s+(\d+)\s*$', case)
        if match:
            label = f'{component} {match.group(1)} {match.group(2)}'
            labels[label] = labels.get(label, 0) + 1
            native.append((trace, case, match.group(1), match.group(2), label))
    for index, (trace, case, step, occurrence, label) in enumerate(native, 1):
        trace.name = label if labels[label] == 1 else f'{component} {step} C{index}'
        trace.legendgroup = 'igird_demand_' + case
        if trace.customdata is not None and len(trace.customdata) and len(trace.customdata[0]) >= 5:
            source_hover = '<br>Diagram: %{customdata[0]}<br>Source: %{customdata[1]}<br>%{customdata[2]} · Excel row %{customdata[3]}<br>%{customdata[4]}'
        else:
            trace.customdata = [[case] for _ in trace.x]
            source_hover = '<br>%{customdata[0]}'
        trace.hovertemplate = 'x=%{x:.3f} m<br>'+component+'=%{y:.3f} '+unit+source_hover+'<extra></extra>'
        # All demand remains blue; the lower bound uses a dotted pattern.
        trace.line.dash = 'solid' if step == 'Max' else 'dot'
        trace.marker.symbol = 'circle' if occurrence == '1' else 'diamond'


def compact_reference_paths(fig, families: dict[str, str]) -> None:
    """One legend per quantity; drop exact finite copies, retain distinct/gapped paths.

    Positive and negative references share a legend but retain their original
    coordinates. Unlike a scalar envelope, this keeps every different case's
    resistance/threshold path and its source identity.
    """
    seen_points = set()
    legend_seen = set()
    kept = []
    for trace in fig.data:
        original = str(trace.name or '')
        if original not in families:
            kept.append(trace)
            continue
        family = families[original]
        try:
            coordinates = tuple((float(x), float(y)) for x, y in zip(trace.x, trace.y))
            finite = bool(coordinates) and all(math.isfinite(x) and math.isfinite(y) for x, y in coordinates)
        except (TypeError, ValueError):
            coordinates, finite = (), False
        signature = (family, coordinates)
        if finite and signature in seen_points:
            continue
        if finite:
            seen_points.add(signature)
        trace.name = family
        trace.legendgroup = 'igird_reference_'+family
        trace.showlegend = family not in legend_seen
        trace.connectgaps = False
        legend_seen.add(family)
        kept.append(trace)
    fig.data = tuple(kept)


def polish_shear_legend(fig) -> None:
    """Compact demand sources and resistance legends without changing checks."""
    compact_csi_demand_labels(fig, component='Vuy', unit='kN')
    compact_reference_paths(fig, {'φVn':'±φVn', '-φVn':'±φVn', 'φVc':'φVc'})
    for trace in fig.data:
        if trace.name == 'Governing demand':
            trace.name, trace.showlegend = 'Gov. Vu', False
        elif trace.name == 'Governing shear check':
            trace.name = 'Gov. shear'
        elif trace.name == 'Critical section for shear loading':
            trace.name = 'Critical x'


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
