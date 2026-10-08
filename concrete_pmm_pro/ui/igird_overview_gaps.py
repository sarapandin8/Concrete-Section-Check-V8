"""Explain missing overview ratios from stored rows without creating results."""
from __future__ import annotations

import math
import pandas as pd


def _text(value):
    if value is None or value is pd.NA:
        return ''
    if isinstance(value, float) and math.isnan(value):
        return ''
    return str(value).strip()


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float('nan')
    return number if math.isfinite(number) else float('nan')


def missing_ratio_audit(frame, envelope, components, *, check_name, active_df,
                        demand_tolerance):
    """Distinguish a stored threshold screen from an unavailable calculation.

    A numeric ratio supplied by another case at the same station remains
    plotted. The omitted case still appears in the audit. A zero-demand label
    additionally requires a finite, near-zero original action, because an old
    NO DEMAND row by itself does not distinguish zero Tu from missing Tu.
    """
    if frame is None or frame.empty or envelope.empty:
        return pd.DataFrame()
    data = frame.copy(deep=True)
    data['__gap_x'] = pd.to_numeric(data['Governing x'].astype(str).str.replace(' m', '', regex=False), errors='coerce')
    available = pd.Series(False, index=data.index)
    for column in components.values():
        values = pd.to_numeric(data[column], errors='coerce')
        available |= values.notna() & values.ge(0)
    gap_x = set(envelope.loc[envelope['D/C'].isna(), 'x_m'])
    original_tu = {}
    if check_name == 'Torsion' and active_df is not None and {'Case Name', 'Station x (m)', 'Tu'}.issubset(active_df):
        for _, source in active_df.iterrows():
            key = (_text(source.get('Case Name')), _number(source.get('Station x (m)')))
            original_tu.setdefault(key, []).append(_number(source.get('Tu')))
    records = []
    for _, row in data.loc[~available & data['__gap_x'].notna()].iterrows():
        x = float(row['__gap_x'])
        case = _text(row.get('Case'))
        threshold_status = _text(row.get('Threshold status'))
        status = _text(row.get('Status'))
        demand = _number(row.get('Demand kN-m'))
        magnitude = _number(row.get('Abs demand kN-m'))
        if not math.isfinite(magnitude) and math.isfinite(demand):
            magnitude = abs(demand)
        threshold = _number(row.get('Threshold kN-m'))
        classification = 'UNAVAILABLE'
        capacity = _text(row.get('Capacity'))
        notes = _text(row.get('Notes'))
        explanation = '; '.join(value for value in (capacity if capacity != '-' else '', notes) if value)
        if not explanation:
            explanation = 'No nonnegative numeric check ratio is stored; review the recorded source/status fields.'
        if (check_name == 'Torsion' and threshold_status == 'BELOW THRESHOLD'
                and math.isfinite(magnitude) and magnitude >= 0
                and math.isfinite(threshold) and threshold > 0
                and magnitude <= threshold + 1.0e-9):
            classification = 'BELOW THRESHOLD'
            explanation = (f'Stored threshold screen: |Tu|={magnitude:.3f} <= {threshold:.3f} kN-m. '
                           'Strength/detailing D/C is omitted by this screen; the stored row status and other acceptance gates remain unchanged.')
        elif check_name == 'Torsion' and _text(row.get('Transverse status')) == 'NO DEMAND':
            source_values = original_tu.get((case, x), [])
            if source_values and all(math.isfinite(v) and abs(v) <= demand_tolerance for v in source_values):
                classification = 'NO DEMAND'
                explanation = 'The original station Tu is finite and zero within the existing demand tolerance. No numeric torsion D/C is stored; other acceptance gates remain unchanged.'
            else:
                explanation = 'The stored NO DEMAND label has no verified finite zero Tu in the original active rows. Review the source action; missing Tu is not accepted as zero.'
        records.append({'Station x (m)': x, 'Classification': classification,
            'Curve gap': x in gap_x, 'Case': case, 'Stored row status': status,
            'Threshold status': threshold_status, 'Tu kN-m': demand,
            'Threshold kN-m': threshold, 'Explanation': explanation,
            **{key: _text(row.get(key)) for key in ('Source file', 'Source sheet', 'Source Excel row', 'Source coupling')}})
    return pd.DataFrame(records)


def render_gap_audit(fig, *, check_name, key_prefix=''):
    """Read-only UI for the audit already attached to the overview figure."""
    import streamlit as st
    from concrete_pmm_pro.ui.result_table_display import result_table_for_display
    meta = dict(fig.layout.meta or {})
    records = meta.get('overview_missing_ratio_audit', [])
    if not records:
        return
    audit = pd.DataFrame(records)
    stations = meta.get('overview_gap_stations', [])
    if stations:
        counts = {kind: sum(row['classification'] == kind for row in stations)
                  for kind in ('BELOW THRESHOLD', 'NO DEMAND', 'NOT REQUIRED', 'UNAVAILABLE')}
        summary = ', '.join(f'{count} {kind.lower()}' for kind, count in counts.items() if count)
        st.caption('Missing-ratio stations: '+summary+'. Circle at the chart foot: threshold screen / verified zero Tu. Cross: numerical result unavailable. These status markers are not D/C=0 or an overall PASS.')
    unavailable = audit.loc[audit['Classification'].eq('UNAVAILABLE')]
    if not unavailable.empty:
        xs = sorted(unavailable['Station x (m)'].unique())
        positions = ', '.join(f'{x:.3f}' for x in xs[:10]) + (' ...' if len(xs) > 10 else '')
        st.warning(f'Numerical {check_name} check unavailable for {len(unavailable)} stored case/station row(s), x={positions} m. Review the recorded statuses and source reasons below; another case supplying a plotted value does not resolve these rows.')
    if check_name == 'Torsion':
        st.caption('For the stored full-span Tu and phiTn diagram, select Selected case — demand / capacity above. Below-threshold / zero-Tu stations may have separately calculated diagram resistance; it does not replace the original design decision.')
    with st.expander('Missing-ratio stations / gap reasons', expanded=False):
        st.caption('Every omitted case/station is retained. Curve gap=False means another checked case supplies the plotted station ratio. Source file/sheet/row and full explanations are included in the CSV.')
        columns = ['Station x (m)', 'Classification', 'Curve gap', 'Stored row status',
                   'Threshold status', 'Tu kN-m', 'Threshold kN-m', 'Explanation', 'Case']
        st.dataframe(result_table_for_display(audit[columns]), hide_index=True, use_container_width=True)
        st.download_button('Download missing-ratio station audit (CSV)',
            data=audit.to_csv(index=False).encode('utf-8-sig'),
            file_name='igird_'+check_name.lower().replace(' + ', '_')+'_missing_ratios.csv',
            mime='text/csv', on_click='ignore', key='igird_gap_export_'+key_prefix+check_name)
