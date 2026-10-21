"""Calculated precast stages and imported CSI Service WebTop Vert envelopes."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import pandas as pd

from concrete_pmm_pro.io.girder_deflect70 import BANK_KEY, ERROR_KEY, UNIT_TO_M, validate_bank
from concrete_pmm_pro.serviceability import girder_deflect69 as previous

VERSION = 'SLS.DEFLECT70'
SETTINGS_KEY = 'girder_deflect70_settings'
RESULT_KEY = 'girder_deflect70_result'
PROFILES = {**previous.PROFILES,
    'rail_project': 'Railway project · SLS envelope min(L/1500, 30 mm)',
    'custom': 'Project · custom SLS envelope limit'}
STAGES = ['Transfer stage', 'Construction stage', 'Service stage']


def settings(state):
    raw = state.get(SETTINGS_KEY)
    if raw is None:
        raw = {k: v for k, v in (state.get(previous.SETTINGS_KEY) or {}).items() if k != 'live_udl_kN_m'}
    normalized = previous.settings({previous.SETTINGS_KEY: raw,
        'analysis_mode_settings': state.get('analysis_mode_settings')})
    normalized.pop('live_udl_kN_m')
    return normalized


def criterion(config, span_m):
    limit, label, basis = previous.criterion(config, span_m)
    if config['profile'] == 'rail_project':
        basis = 'Project SLS envelope |WebTop Vert| criterion; confirm the railway owner specification'
    elif config['profile'] == 'custom':
        basis = 'Project-specified SLS envelope |WebTop Vert| limit'
    return limit, label, basis


def fingerprint(state):
    stage_state = dict(state)
    stage_state[previous.SETTINGS_KEY] = {**settings(state), 'live_udl_kN_m': None}
    payload = {'version': VERSION, 'calculated_stage_inputs': previous.fingerprint(stage_state),
        'settings': settings(state), 'imported_input': state.get(BANK_KEY), 'upload_error': state.get(ERROR_KEY)}
    return sha256(json.dumps(payload, sort_keys=True, default=previous._encode).encode()).hexdigest()


def current(state):
    result = state.get(RESULT_KEY)
    try:
        return result if isinstance(result, dict) and result.get('fingerprint') == fingerprint(state) else None
    except (ValueError, TypeError):
        return None


def _row(stage, girder, check, demand=np.nan, station=np.nan, limit=None, branch='', basis='', eligible=True):
    ratio = demand / limit if limit and np.isfinite(demand) else np.nan
    status = ('Preview FAIL' if ratio > 1 + 1e-8 else 'Preview PASS') if np.isfinite(ratio) and eligible else 'REVIEW'
    return {'Stage': stage, 'Girder': girder, 'Check': check, 'Branch': branch,
        'Demand (mm)': demand, 'Limit (mm)': limit, 'Utilization': ratio, 'x (m)': station,
        'Status': status, 'Basis': basis}


def calculate(state, source, span_m):
    config = settings(state)
    limit, label, basis = criterion(config, span_m)
    curves, table, audits = [], [], []
    for stage in STAGES[:2]:
        group = source.loc[source.Stage.eq(stage)]
        if group.empty:
            raise ValueError('Missing calculated ' + stage + ' source')
        data = group.loc[group.Curve.eq(group.Curve.iloc[0])].sort_values('Station x (m)').copy()
        if not np.isfinite(data[['Station x (m)', 'Deflection (mm)']].to_numpy(float)).all():
            raise ValueError('Calculated stage response must be finite')
        if data['Station x (m)'].duplicated().any() or not np.allclose(data['Station x (m)'].iloc[[0, -1]], [0, span_m], atol=1e-8):
            raise ValueError('Calculated stage response must cover the whole member from 0 to L')
        audits.append(data.copy())
        data['Girder'], data['Curve'], data['Role'] = 'Current single-girder section model', 'Calculated response', 'Calculated'
        curves.append(data)
        demand, station = previous._extreme(data)
        cap = config['transfer_limit_mm' if stage == STAGES[0] else 'construction_limit_mm']
        table.append(_row(stage, 'Current single-girder section model', 'Net elastic response', demand, station, cap,
            basis='Project |δ| stage tolerance' if cap else 'Response only; project stage tolerance not specified'))
    bank = validate_bank(state[BANK_KEY]) if state.get(BANK_KEY) is not None else None
    error = state.get(ERROR_KEY)
    service_audit = []
    # Preserve the previous valid input bank on a failed replacement, but never
    # use it as the current Service result while that replacement is unresolved.
    if bank is not None and not error:
        for sheet in bank['girders']:
            rows = []
            for item in sheet['rows']:
                x = item['Girder Distance'] * UNIT_TO_M[sheet['distance_unit']]
                y = item['WebTop Vert'] * UNIT_TO_M[sheet['vertical_unit']] * 1000
                rows.append({'Stage': STAGES[2], 'Girder': sheet['girder'], 'Curve': 'Envelope ' + item['ItemType'],
                    'Role': 'Imported SLS envelope', 'ItemType': item['ItemType'], 'Station x (m)': x,
                    'Deflection (mm)': y, 'Source row': item['source_row'],
                    'Girder Distance': item['Girder Distance'], 'Distance unit': sheet['distance_unit'],
                    'WebTop Vert': item['WebTop Vert'], 'Vertical unit': sheet['vertical_unit']})
            data = pd.DataFrame(rows)
            extent = data['Station x (m)'].agg(['min', 'max']).to_numpy()
            if not np.allclose(extent, [0, span_m], atol=max(1e-5, span_m * 1e-6), rtol=0):
                raise ValueError(f"{sheet['girder']}: imported Girder Distance must cover 0–{span_m:g} m; received {extent[0]:g}–{extent[1]:g} m. Check the current span and distance option.")
            curves.append(data)
            service_audit.append(data.copy())
            index = data['Deflection (mm)'].abs().idxmax()
            governing = data.loc[index]
            eligible = config['profile'] in {'rail_project', 'custom'}
            note = basis
            if not eligible and limit is not None:
                note += '; the exported SLS envelope has no LL-only definition, so this limit is reference-only'
            table.append(_row(STAGES[2], sheet['girder'], 'Imported SLS envelope |WebTop Vert|',
                abs(float(governing['Deflection (mm)'])), float(governing['Station x (m)']), limit,
                branch=governing.ItemType, basis=note, eligible=eligible))
    else:
        table.append(_row(STAGES[2], 'No current imported girder', 'Imported SLS envelope |WebTop Vert|', limit=limit,
            basis='Replacement upload invalid: ' + str(error) if error else 'Upload Envelope SLS Girder Deflection; no generated Service fallback'))
    table.append(_row(STAGES[2], 'Source model / full SLS scope', 'Source coverage / full deflection',
        basis='Imported SLS values are used as exported. Load-combination definitions and long-term coverage are not included in this workbook; no camber, LL, impact or creep increment is added.'))
    summary = pd.DataFrame(table)
    return {'version': VERSION, 'fingerprint': fingerprint(state), 'settings': config, 'span_m': span_m,
        'code_edition': str(state.get('project_code_edition') or state.get('code_edition') or 'Project criterion'),
        'curves': pd.concat(curves, ignore_index=True), 'summary': summary,
        'source_audit': pd.concat(audits, ignore_index=True),
        'service_audit': pd.concat(service_audit, ignore_index=True) if service_audit else pd.DataFrame(),
        'service_available': bool(service_audit), 'girders': [s['girder'] for s in bank['girders']] if service_audit else [],
        'input_source': bank if service_audit else None, 'limit_mm': limit, 'limit_label': label, 'limit_basis': basis,
        'limit_eligible': config['profile'] in {'rail_project', 'custom'},
        'status': 'Preview FAIL' if summary.Status.eq('Preview FAIL').any() else 'REVIEW REQUIRED',
        'scope': 'Calculated Transfer/Construction for one current section model; Service from imported CSI individual-girder WebTop Vert Max/Min only.',
        'full_deflection_acceptance': False}


def report_zip(result):
    buffer = BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        for name, key in [('Checks', 'summary'), ('Curves', 'curves'),
                          ('Calculated_Stage_Source', 'source_audit'), ('CSI_Service_Source', 'service_audit')]:
            archive.writestr(name + '.csv', result[key].to_csv(index=False).encode('utf-8-sig'))
        archive.writestr('Imported_Input.json', json.dumps(result['input_source'], indent=2, ensure_ascii=False))
        archive.writestr('Scope.json', json.dumps({k: result[k] for k in ['version', 'settings', 'span_m', 'girders',
            'limit_mm', 'limit_label', 'limit_basis', 'limit_eligible', 'service_available', 'status', 'scope',
            'full_deflection_acceptance']}, indent=2, ensure_ascii=False))
    return buffer.getvalue()


def summary_rows(state):
    if RESULT_KEY not in state:
        return []
    result = current(state)
    if result is None:
        return [{'Module': 'SLS Deflection', 'Check': 'Stage deflection / CSI Service envelope', 'Status': 'STALE',
            'Required Action': 'Calculate deflection / camber again in Analysis.'}]
    return [{'Module': 'SLS Deflection', 'Check': row.Check + ' · ' + row.Girder, 'Status': row.Status,
        'Code Basis': row.Basis, 'Governing Case': 'Imported SLS envelope / ' + row.Branch if row.Branch else row.Stage,
        'Station / Point': f"x={row['x (m)']:.5f} m" if pd.notna(row['x (m)']) else '-',
        'Demand': f"{row['Demand (mm)']:.3f} mm" if pd.notna(row['Demand (mm)']) else 'Unavailable',
        'Capacity / Limit': f"{row['Limit (mm)']:.3f} mm" if pd.notna(row['Limit (mm)']) else 'Review',
        'D/C / Util.': float(row.Utilization) if pd.notna(row.Utilization) else None,
        'Required Action': row.Basis, 'Source': 'Analysis → SLS Deflection / Camber · ' + VERSION}
        for _, row in result['summary'].iterrows()]
