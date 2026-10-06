"""Read-only case filtering and traceable controlling ratios from stored rows.

Numerical control and unresolved acceptance gates are reported separately.
No demand envelopes, solver calls, input changes, or result-cache writes.
"""
from __future__ import annotations

import math
import pandas as pd

FRAME_KEYS = {'Flexure': 'flexure_preview_df', 'Shear': 'shear_check_df',
              'Torsion': 'torsion_check_df', 'Shear + Torsion': 'combined_vt_df'}
COMPONENTS = {
    'Flexure': {'Flexure': ('Utilization value', 'D/C value')},
    'Shear': {'Shear strength': ('Strength D/C value', 'D/C value'),
              'Shear detailing': ('Detailing D/C value',),
              'Minimum Av/s': ('Av/s min D/C',), 'Shear spacing': ('Spacing D/C',),
              'Vn upper limit': ('Vn limit D/C',)},
    'Torsion': {'Torsion transverse strength': ('D/C value', 'At D/C'),
                'Torsion longitudinal steel': ('Al utilization',),
                'Torsion detailing': ('Detailing D/C value',),
                'Torsion spacing': ('Spacing D/C',)},
    'Shear + Torsion': {'Veff / concrete stress': ('Stress D/C value',),
                        'Combined transverse': ('Transverse D/C value',),
                        'Combined longitudinal': ('Longitudinal D/C value',),
                        'Spacing': ('Spacing D/C',),
                        'Combined overall': ('Overall D/C value',)},
}
AUTO_CASE = 'Automatic — controlling load case'
ALL_CASES = 'All load cases'


def filter_case(frame, case, *, column='Case'):
    if frame is None:
        return None
    if case is None:
        return frame.copy(deep=True)
    if column not in frame:
        return frame.iloc[:0].copy()
    return frame.loc[frame[column].astype(str).eq(case)].copy(deep=True)


def eligible_rows(frame, check_name):
    if frame is None or frame.empty:
        return pd.DataFrame()
    if check_name == 'Shear':
        from concrete_pmm_pro.ui.analysis_page import _beam_uls_shear_design_rows_for_governing
        return _beam_uls_shear_design_rows_for_governing(frame).reset_index(drop=True)
    rows = frame.copy()
    kind = rows.get('Station type', pd.Series('', index=rows.index)).astype(str)
    status = rows.get('Status', pd.Series('', index=rows.index)).astype(str)
    rows = rows.loc[~kind.str.contains('BOUNDARY', case=False, na=False)
                    & ~status.isin(['DIAGRAM BOUNDARY', 'BOUNDARY SKIPPED', 'NOT APPLICABLE'])]
    return rows.reset_index(drop=True)


def component_values(rows, check_name):
    """Numeric component ratios shared by case ranking and overview charts."""
    for component, columns in COMPONENTS[check_name].items():
        values = pd.Series(float('nan'), index=rows.index)
        for column in columns:
            if column in rows:
                values = values.fillna(pd.to_numeric(rows[column], errors='coerce'))
        yield component, values


def _candidates(rows, check_name):
    candidates = []
    for component, values in component_values(rows, check_name):
        for pos in values.index[values.notna() & values.ge(0)]:
            candidates.append((float(values.loc[pos]), component, int(pos), 'D/C'))
    # Investigation is a fallback only; do not compare threshold ratios with
    # actual torsion strength/detailing D/C as if they were the same check.
    if not candidates and check_name == 'Torsion':
        for pos, row in rows.iterrows():
            try:
                demand = abs(float(row.get('Abs demand kN-m', row.get('Demand kN-m'))))
                threshold = float(row.get('Threshold kN-m'))
            except (TypeError, ValueError):
                continue
            if math.isfinite(demand) and math.isfinite(threshold) and threshold > 0:
                candidates.append((demand / threshold, 'Torsion investigation', int(pos), 'INVESTIGATION ONLY'))
    return candidates


def review_counts(rows):
    failed = pd.Series(False, index=rows.index)
    unresolved = pd.Series(False, index=rows.index)
    for column in rows:
        if column == 'Status' or column.endswith('status') or column.endswith('Status'):
            status = rows[column].astype(str).str.upper()
            failed |= status.eq('FAIL') | status.eq('NO EQUILIBRIUM')
            unresolved |= (status.str.contains('REVIEW|REQUIRED|NOT READY|INCOMPLETE|BLOCKED|UNSUPPORTED|PARTIAL', na=False)
                           & ~status.isin(['NOT REQUIRED', 'NOT APPLICABLE', 'DESIGN REQUIRED']))
    if 'Source coupling' in rows:
        unresolved |= rows['Source coupling'].astype(str).str.contains('ENVELOPE|UNVERIFIED', na=False)
    return int(failed.sum()), int(unresolved.sum())


def _selection(rows, candidates):
    ratio, component, pos, basis = max(candidates, key=lambda item: item[0])
    tied = []
    for value, _, position, _ in candidates:
        if value == ratio or math.isclose(value, ratio, rel_tol=1e-9, abs_tol=1e-12):
            case = str(rows.iloc[position].get('Case', '-'))
            if case not in tied:
                tied.append(case)
    return {'row': rows.iloc[pos].to_dict(), 'ratio': ratio, 'component': component,
            'basis': basis, 'tied_cases': tied}


def controlling_result(frame, check_name):
    rows = eligible_rows(frame, check_name)
    failed, unresolved = review_counts(rows)
    result = {'row': None, 'ratio': float('nan'), 'component': 'Source review',
              'basis': 'NO NUMERIC D/C', 'tied_cases': [], 'failed_rows': failed,
              'review_rows': unresolved}
    candidates = _candidates(rows, check_name)
    if candidates:
        result.update(_selection(rows, candidates))
    elif not rows.empty:
        # If no numeric resistance exists, show a pending source row rather
        # than inventing a governing strength case from the largest force.
        priority = {'FAIL': 6, 'NO EQUILIBRIUM': 6, 'SOURCE BLOCKED': 5,
                    'LAYOUT REQUIRED': 4, 'DATA REQUIRED': 4, 'REVIEW': 3,
                    'NOT READY': 3, 'PASS': 1, 'NO DEMAND': 0}
        statuses = rows.get('Status', pd.Series('', index=rows.index)).astype(str)
        pos = int(statuses.map(lambda s: priority.get(s, 2)).argmax())
        result['row'] = rows.iloc[pos].to_dict()
    return result


def ratio_text(value):
    if math.isnan(value):
        return 'Unavailable'
    return '∞' if math.isinf(value) else f'{value:.3f}'


def summary_record(control):
    row = control['row'] or {}
    return {'Controlling load case': str(row.get('Case', '-')),
            'Station': str(row.get('Governing x', '-')),
            'Component': control['component'], 'D/C or ratio': ratio_text(control['ratio']),
            'Basis': control['basis'], 'Stored row status': str(row.get('Status', 'REVIEW')),
            'Failed rows': control['failed_rows'], 'Rows requiring review': control['review_rows'],
            'Tied cases': '; '.join(control['tied_cases']),
            **{key: str(row.get(key, '-')) for key in
               ('Source file', 'Source sheet', 'Source Excel row', 'Source ItemType', 'Source coupling')}}


def case_ranking(frame, check_name):
    rows = eligible_rows(frame, check_name)
    if rows.empty or 'Case' not in rows:
        return pd.DataFrame()
    records = []
    for case, group in rows.groupby('Case', sort=False):
        control = controlling_result(group, check_name)
        records.append({**summary_record(control), '_ratio': control['ratio'],
                        '_basis': {'D/C': 0, 'INVESTIGATION ONLY': 1, 'NO NUMERIC D/C': 2}[control['basis']]})
    # Investigation thresholds and strength ratios have different meanings.
    # Keep each basis together rather than mixing their numerical magnitudes.
    return pd.DataFrame(records).sort_values(['_basis', '_ratio'], ascending=[True, False],
        kind='stable', na_position='last').drop(columns=['_basis', '_ratio'])


def component_controls(frame, check_name):
    rows = eligible_rows(frame, check_name)
    candidates = _candidates(rows, check_name)
    records = []
    for component in dict.fromkeys(item[1] for item in candidates):
        control = _selection(rows, [item for item in candidates if item[1] == component])
        control.update(failed_rows=0, review_rows=0)
        records.append(summary_record(control))
    # Failure/review counts belong to the whole member or load case. A
    # component's representative row is not a count of its acceptance gates.
    return pd.DataFrame(records).drop(columns=['Failed rows', 'Rows requiring review'], errors='ignore')
