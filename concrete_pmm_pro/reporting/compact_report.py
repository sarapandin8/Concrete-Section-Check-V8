"""Presentation only: governing source rows, counts, and compact input text.

Never synthesize a combination by taking independent column maxima. Selected
rows always retain their original corresponding actions and source identity.
"""
import pandas as pd


def compact_rows(data):
    """Reduce long check/action tables, preserving every case/status group.

    Other tables are left intact. Counts are explicit; full rows remain in the
    source evidence download. No positional first-N truncation is permitted.
    """
    if len(data) <= 12:
        return data, ''
    names = {c: str(c).lower() for c in data.columns}
    metrics = [c for c,n in names.items() if any(s in n for s in ('utilization', 'd/c'))]
    actions = [c for c in data.columns if c in ('Mux','Muy','Vuy','Vux','Tu','Nu','N','Mx','My','T')]
    if not metrics and not actions:
        return data, ''
    groups = [c for c,n in names.items() if n in (
        'case','case name','outputcase','stage','girder','member','check','point','status','steptype','step')]
    # Use positional indexing so duplicate source indexes cannot select the wrong row.
    view = data.reset_index(drop=True)
    selected, summaries = set(), []
    grouped = view.groupby(groups, dropna=False, sort=False, observed=True) if groups else [((), view)]
    for key, rows in grouped:
        local = {int(rows.index[0])}
        for column in metrics or actions:
            numeric = pd.to_numeric(rows[column], errors='coerce')
            if numeric.notna().any():
                local.add(int(numeric.idxmax()))
                # Signed demand extremes retain both signs and their full corresponding rows.
                if not metrics:
                    local.add(int(numeric.idxmin()))
        selected.update(local)
        if any(n == 'status' for n in names.values()):
            key = key if isinstance(key, tuple) else (key,)
            label = ', '.join(f'{c}={v}' for c,v in zip(groups,key))
            summaries.append(f'{label}: {len(rows):,} source rows')
    if len(selected) >= len(data):
        return data, ''
    result = data.iloc[sorted(selected)].copy(deep=False)
    note = (f'Governing rows: {len(result):,} of {len(data):,}. Each case/stage/status group is retained; '
            'values in a row come from the same source record. Full station records are available '
            'in the optional source evidence download.')
    if summaries:
        note += ' ' + '; '.join(summaries) + '.'
    return result, note


def is_parameter_table(data):
    return list(data.columns) == ['Parameter','Value']


def grouped_bar_trace(data):
    """Collapse only identical bar properties, explicitly retaining all bar IDs."""
    if 'Bar' not in data or len(data) < 8:
        return data
    columns = [c for c in data.columns if c != 'Bar']
    try:
        rows = []
        for _, group in data.groupby(columns, dropna=False, sort=False, observed=True):
            row = group.iloc[0].to_dict()
            row['Bar'] = ', '.join(str(v) for v in group['Bar'])
            rows.append(row)
        return pd.DataFrame(rows, columns=data.columns)
    except (TypeError, ValueError):
        return data
