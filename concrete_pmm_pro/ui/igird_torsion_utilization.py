"""Plot cached station strength ratios separately from original design checks.

No calculation, result mutation, interpolation of missing values or acceptance
decision belongs here. The ratio uses the actual Tu and phiTn from one stored
case/station calculation, including qualified below-threshold stations.
"""
from __future__ import annotations

import math
import pandas as pd
import plotly.graph_objects as go

from concrete_pmm_pro.ui.igird_case_review import (
    component_values, controlling_result, eligible_rows, ratio_text,
)


def _text(value):
    return '' if value is None or value is pd.NA or pd.isna(value) else str(value)


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float('nan')


def _station(row, column):
    return _number(_text(row.get(column)).replace(' m', ''))


def _key(case, x):
    # Stored Governing x uses the production formatter's three decimals. More
    # than one source at this precision is ambiguous, never silently merged.
    return (_text(case), f'{x:.3f}') if math.isfinite(x) else None


def _index(frame, case_column, x_column):
    groups = {}
    if not isinstance(frame, pd.DataFrame):
        return groups
    for _, row in frame.iterrows():
        key = _key(row.get(case_column), _station(row, x_column))
        if key is not None:
            groups.setdefault(key, []).append(row)
    return groups


def _design_envelope(frame):
    from concrete_pmm_pro.ui.igird_vt_workspace import utilization_envelope
    rows = eligible_rows(frame, 'Torsion')
    components = {}
    for index, (label, values) in enumerate(component_values(rows, 'Torsion')):
        column = f'__original_component_{index}'
        rows[column] = values
        components[label] = column
    return utilization_envelope(rows, components)


def utilization_audit(active_df, frame, diagram, *, span_m, source_context_df=None):
    """Validate each actual source/stored-resistance pair, retaining every case.

    CSI shared endpoints use only the already accepted physical endpoint rule.
    A threshold is never substituted for phiTn. Missing Tu is never zero.
    """
    from concrete_pmm_pro.visualization.igird_uls_chart_display import native_csi_diagram_rows
    demands = native_csi_diagram_rows(active_df, member_length_m=span_m,
                                    source_context_df=source_context_df)
    sources = _index(demands, 'Case Name', 'Station x (m)')
    capacities = _index(diagram, 'Case', 'Governing x')
    decisions = _index(frame, 'Case', 'Governing x')
    records = []
    for key, source in ((key, row) for key, rows in sources.items() for row in rows):
        source_rows = sources[key]
        stored = capacities.get(key, [])
        capacity = stored[0] if len(stored) == 1 else pd.Series(dtype=object)
        design = decisions.get(key, [])
        original = controlling_result(pd.DataFrame(design), 'Torsion')
        tu = _number(source.get('Tu'))
        cached_tu = _number(capacity.get('Demand kN-m'))
        tn = _number(capacity.get('φTn kN-m'))
        reason = ''
        if len(source_rows) != 1:
            reason = 'Ambiguous original case/station actions at stored station precision.'
        elif len(stored) != 1:
            reason = 'Cached station resistance is missing.' if not stored else 'Ambiguous cached case/station resistance.'
        elif not math.isfinite(tu):
            reason = 'Original Tu is unavailable; missing demand is not zero.'
        elif not math.isfinite(cached_tu) or not math.isclose(tu, cached_tu, rel_tol=1e-9, abs_tol=1e-8):
            reason = 'Cached Tu does not match the actual same-case/station action.'
        elif not math.isfinite(tn) or tn <= 0:
            reason = 'Stored phiTn must be finite and positive; the investigation threshold is not resistance.'
        else:
            expected = {'Diagram source case': source.get('__Source case', key[0]),
                        'Diagram source sheet': source.get('__Source sheet', ''),
                        'Diagram source row': source.get('__Source row', '')}
            for field, value in expected.items():
                actual = _text(capacity.get(field))
                if actual and actual != _text(value):
                    reason = f'{field} does not match the qualified original source.'
                    break
        ratio = abs(tu) / tn if not reason else float('nan')
        if not reason and not math.isfinite(ratio):
            reason = 'The stored force/resistance pair does not give a finite strength utilization.'
            ratio = float('nan')
        records.append({'Station x (m)': _station(source, 'Station x (m)'),
            'Case': key[0], 'Strength utilization |Tu|/phiTn': ratio,
            'Availability': 'UNAVAILABLE' if reason else 'AVAILABLE',
            'Tu kN-m': tu, 'Stored Tu kN-m': cached_tu, 'phiTn kN-m': tn,
            'Original maximum check D/C': original['ratio'] if original['basis'] == 'D/C' else float('nan'),
            'Original controlling component': original['component'] if original['basis'] == 'D/C' else 'No numeric design/check D/C',
            'Original row status': '; '.join(dict.fromkeys(_text(r.get('Status')) for r in design)),
            'Threshold status': '; '.join(dict.fromkeys(_text(r.get('Threshold status')) for r in design)),
            'Original source row count': len(source_rows), 'Cached resistance row count': len(stored),
            'Diagram evaluation status': _text(capacity.get('Diagram evaluation status')),
            'Explanation': reason or 'Actual stored station Tu / phiTn; plotting quantity only. Original threshold, design checks and source gates remain unchanged.',
            **{field: _text(capacity.get(field)) for field in (
                'Source file', 'Source sheet', 'Source Excel row', 'Source coupling',
                'Diagram source case', 'Diagram source sheet', 'Diagram source row', 'Diagram source type')}})
    audit = pd.DataFrame(records)
    if not audit.empty:
        audit['Curve gap'] = audit.groupby('Station x (m)')['Strength utilization |Tu|/phiTn'].transform('count').eq(0)
        audit = audit.sort_values(['Station x (m)', 'Case'], kind='stable').reset_index(drop=True)
    return audit


def _records(frame):
    if frame.empty:
        return []
    data = frame.astype(object).where(frame.notna(), None)
    return [{key: ('∞' if isinstance(value, (int, float)) and value == float('inf') else value)
             for key, value in row.items()} for row in data.to_dict('records')]


def make_torsion_utilization_figure(active_df, frame, *, diagram, code_label,
                                    span_m, source_context_df=None, member_name='', case=None):
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.visualization.igird_uls_chart_display import (
        add_igird_report_note, mark_unavailable_capacity,
    )
    audit = utilization_audit(active_df, frame, diagram, span_m=span_m,
                             source_context_df=source_context_df)
    strength = []
    if not audit.empty:
        for x, rows in audit.groupby('Station x (m)', sort=True):
            numeric = rows.loc[rows['Availability'].eq('AVAILABLE')]
            chosen = numeric.loc[numeric['Strength utilization |Tu|/phiTn'].idxmax()] if not numeric.empty else rows.iloc[0]
            strength.append({'x_m': float(x), 'Ratio': chosen['Strength utilization |Tu|/phiTn'],
                'Case': chosen['Case'], 'Tu': chosen['Tu kN-m'], 'phiTn': chosen['phiTn kN-m'],
                'Threshold status': chosen['Threshold status'],
                'Unavailable case rows': int(rows['Availability'].eq('UNAVAILABLE').sum())})
    strength = pd.DataFrame(strength)
    design = _design_envelope(frame)
    case_count = active_df['Case Name'].dropna().nunique()
    scope = ' · all load cases: max paired station ratio' if case_count > 1 else ''
    title = f'Torsion — utilization<br><sup>{code_label} · stored transverse strength ratio and original design checks{scope}</sup>'
    fig = ap._make_beam_uls_demand_figure(active_df, column='Tu', title=title,
                                         y_label='Utilization / original check D/C')
    fig.data = ()
    fig.update_layout(title_text=title, annotations=[])
    known = [r for r in strength.get('Ratio', []) if math.isfinite(r)]
    known += [r for r in design.get('D/C', []) if math.isfinite(r)]
    ceiling = max([1., *known]) * 1.16
    if not strength.empty:
        fig.add_trace(go.Scatter(x=strength['x_m'].tolist(), y=strength['Ratio'].tolist(),
            mode='lines+markers', name='Strength |Tu|/φTn', connectgaps=False,
            line={'color': '#1f77b4', 'width': 2.6}, marker={'size': 5},
            customdata=[[r['Case'], r['Tu'], r['phiTn'], r['Threshold status'], r['Unavailable case rows']]
                        for _, r in strength.iterrows()],
            hovertemplate='x=%{x:.3f} m<br>Stored strength utilization=%{y:.3f}<br>Tu=%{customdata[1]:.4f} kN·m; φTn=%{customdata[2]:.4f} kN·m<br>%{customdata[3]}<br>%{customdata[0]}<br>Unavailable case rows: %{customdata[4]}<extra></extra>'))
    if not design.empty:
        # Discrete markers preserve the original maximum check D/C. No line
        # suggests that omitted below-threshold design decisions were filled.
        fig.add_trace(go.Scatter(x=design['x_m'].tolist(),
            y=[ceiling if math.isinf(v) else v for v in design['D/C']], mode='markers',
            name='Original max check D/C', cliponaxis=False,
            marker={'size': 8, 'symbol': 'circle-open', 'color': '#0f172a'},
            customdata=[[r['Case'], r['Component'], ratio_text(r['D/C']), r['Status']]
                        for _, r in design.iterrows()],
            hovertemplate='x=%{x:.3f} m<br>Original design/check D/C=%{customdata[2]}<br>%{customdata[1]} · %{customdata[3]}<br>%{customdata[0]}<extra></extra>'))
        infinite = design.loc[design['D/C'].map(math.isinf)]
        for _, row in infinite.iterrows():
            fig.add_annotation(x=row['x_m'], y=ceiling, text='∞', showarrow=False, yshift=12)
    control = controlling_result(frame, 'Torsion')
    location = (control['row'] or {}).get('Governing x', '—')
    if control['basis'] == 'D/C' and math.isfinite(_station(control['row'], 'Governing x')):
        fig.add_trace(go.Scatter(x=[_station(control['row'], 'Governing x')],
            y=[ceiling if math.isinf(control['ratio']) else control['ratio']], mode='markers',
            name='Governing original check', showlegend=False, cliponaxis=False,
            marker={'size': 10, 'symbol': 'diamond', 'color': '#0f172a'},
            customdata=[[_text(control['row'].get('Case')), control['component'], ratio_text(control['ratio'])]],
            hovertemplate='Original control=%{customdata[2]}<br>%{customdata[1]}<br>%{customdata[0]}<extra></extra>'))
    fig.add_trace(go.Scatter(x=[0., span_m], y=[1., 1.], mode='lines', name='Limit = 1.0',
                             line=dict(ap._BEAM_ULS_CHECK_LINE_STYLE)))
    fig.update_yaxes(range=[0., ceiling * 1.08])
    fig.update_xaxes(range=[0., span_m])
    if not audit.empty:
        missing = audit.loc[audit['Curve gap']].rename(columns={
            'Station x (m)': '__x_m', 'Strength utilization |Tu|/phiTn': '__ratio', 'Explanation': 'Notes'})
        mark_unavailable_capacity(fig, missing, metric='__ratio', label='Stored strength utilization')
    fig.update_layout(meta={**dict(fig.layout.meta or {}),
        'torsion_utilization_audit': _records(audit), 'torsion_strength_envelope': _records(strength),
        'torsion_utilization_case_count': int(case_count),
        'torsion_utilization_basis': 'Actual same-case/station |Tu| / stored phiTn; original max check D/C is separate'})
    unavailable = int(audit['Availability'].eq('UNAVAILABLE').sum()) if not audit.empty else 0
    add_igird_report_note(fig, [
        'Blue: stored |Tu|/φTn, including qualified below-threshold / zero-Tu stations. Open markers: original maximum design/check D/C.',
        f"Original control ({control['basis']}): {ratio_text(control['ratio'])} @ {location}; {control['failed_rows']} FAIL, {control['review_rows']} REVIEW. Unavailable strength case/stations: {unavailable}.",
        'Ratios use paired actual station actions and resistance. Strength utilization does not clear threshold, detailing or source gates; × marks unavailable values.'])
    if member_name:
        from concrete_pmm_pro.ui.igird_member_results import titled_figure
        fig = titled_figure(fig, member_name, case_name=case)
    return fig


def render_utilization_audit(fig, *, key_prefix=''):
    import streamlit as st
    from concrete_pmm_pro.ui.result_table_display import result_table_for_display
    records = (fig.layout.meta or {}).get('torsion_utilization_audit', [])
    if not records:
        st.warning('No stored station force/resistance pairs are available for this utilization view.')
        return
    audit = pd.DataFrame(records)
    missing = audit.loc[audit['Availability'].eq('UNAVAILABLE')]
    if not missing.empty:
        st.warning(f'{len(missing)} case/station strength ratio(s) unavailable. Another case supplying a plotted value does not resolve these rows; see the station audit.')
    with st.expander('Torsion utilization — stored station ratios / original decisions', expanded=False):
        st.caption('The blue ratio uses actual same-case/station Tu and stored phiTn. The original maximum design/check D/C remains omitted where the original screen did not require a check. Missing resistance is not filled; all cases and source identities are retained in the CSV.')
        columns = ['Station x (m)', 'Case', 'Strength utilization |Tu|/phiTn',
            'Tu kN-m', 'phiTn kN-m', 'Original maximum check D/C', 'Original controlling component',
            'Original row status', 'Threshold status', 'Availability', 'Curve gap', 'Explanation']
        st.dataframe(result_table_for_display(audit[columns]), hide_index=True, use_container_width=True)
        st.download_button('Download torsion utilization station audit (CSV)',
            data=audit.to_csv(index=False).encode('utf-8-sig'), file_name='igird_torsion_utilization_audit.csv',
            mime='text/csv', on_click='ignore', key='igird_utilization_export_'+key_prefix)
