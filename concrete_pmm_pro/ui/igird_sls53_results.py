"""Explicit, input-bound I-girder SLS results using the existing stress engine.

Only calculate() calls the station engine. Review controls and downstream
reports consume this runtime snapshot; no results are added to project JSON.
"""
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
import hashlib
import json
import math

import numpy as np
import pandas as pd

VERSION = 'IGIRDER.SLS53'
RUNTIME_KEY = '_igird_sls53_runtime'
HANDOFF_KEY = 'result_summary_beam_girder_sls_input_signature53'
INPUT_KEYS = (
    'section_preset_key', 'section_geometry', 'section_parameters',
    'concrete_material', 'concrete_materials', 'rebar_material', 'prestress_material',
    'rebars', 'prestress_elements', 'analysis_mode_settings', 'serviceability_settings',
    'girder_strand_layout_table', 'girder_prestress_system_settings',
    'girder_prestress_force_states_table', 'girder_prestress_code_loss_settings',
    'beam_girder_system_settings', 'beam_girder_sls_auto_load_settings',
    'beam_sls_loads_table', 'project_design_code', 'project_code_edition',
    'design_code', 'code_edition', 'section_has_prestressing_steel',
    'igird_sls_member_selection', 'igird_sls_active_member',
    'girder_code_loss_fci_mpa',
)
INPUT_PREFIXES = (
    'girder_tension_limit_', 'girder_sls_diagram_limit_profile_key_',
    'section_assembly_', 'girder_prestress_loss_',
)


def _plain(value):
    """Serialize every table cell, never a truncated DataFrame repr."""
    if isinstance(value, pd.DataFrame):
        return {'columns': list(value.columns), 'rows': _plain(value.to_dict('records'))}
    if hasattr(value, 'model_dump'):
        return _plain(value.model_dump(mode='json'))
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.generic):
        return _plain(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is pd.NA:
        return '<NA>'
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def fingerprint(state):
    keys = set(INPUT_KEYS) | {str(k) for k in state if str(k).startswith(INPUT_PREFIXES)}
    data = {k: state.get(k) for k in sorted(keys)}
    meta = state.get('project_metadata') or {}
    if isinstance(meta, Mapping):
        data['csi_reference'] = meta.get('csi_girder_force_reference')
    encoded = json.dumps(_plain(data), sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False)
    return hashlib.sha256((VERSION + encoded).encode()).hexdigest()


def handoff_is_current(state):
    """Read-only guard, also safe to call from Summary / Report without solvers."""
    signature = state.get(HANDOFF_KEY)
    return signature is None or signature == fingerprint(state)


def clear_handoff(state):
    for key in list(state):
        if str(key).startswith('result_summary_beam_girder_sls_'):
            state.pop(key, None)


def current(state):
    result = state.get(RUNTIME_KEY)
    return result if isinstance(result, dict) and result.get('signature') == fingerprint(state) else None


def ratio(value):
    if str(value) == '∞':
        return math.inf
    try:
        result = float(value)
        return result if not math.isnan(result) else -math.inf
    except (TypeError, ValueError):
        return -math.inf


def controlling(rows):
    if not rows:
        return None
    # Native component tables round displayed D/C. Keep an actual FAIL ahead
    # of a rounded 1.000 PASS when selecting the governing case/material.
    return max(rows, key=lambda r: (ratio(r.get('Utilization')),
               'FAIL' in str(r.get('Status')), str(r.get('Status')) == 'REVIEW'))


def overall_status(rows):
    if any('FAIL' in str(r.get('Status')) for r in rows):
        return 'Preview FAIL'
    if not rows or any(str(r.get('Status')) == 'REVIEW' for r in rows):
        return 'REVIEW'
    return 'Preview PASS'


def validate_source(rows, span):
    for i, row in enumerate(rows, 1):
        for field in ('Station x (m)', 'N', 'Mx'):
            value = row.get(field)
            try:
                valid = not isinstance(value, bool) and math.isfinite(float(value))
            except (TypeError, ValueError):
                valid = False
            if not valid:
                raise ValueError(f'SLS row {i}: {field} must be a finite number. Missing forces are not zero.')
        if not -1e-7 <= float(row['Station x (m)']) <= span + 1e-7:
            raise ValueError(f'SLS row {i}: station is outside the 0–{span:g} m span.')


def prepare():
    """Resolve existing defaults/profile gates before binding a result to inputs."""
    from . import analysis_page as ap
    state = ap.st.session_state
    span = ap._girder_sls_span_length_from_session([])
    specs = ap._beam_sls_stage_tab_specs()
    for _, stage, _ in specs:
        ap._girder_stage_limit_profile_for_diagram(stage)
    mode = ap._analysis_mode_from_session()
    bases = ap.build_girder_service_stress_basis_options(
        state.get('section_geometry'), state.get('section_parameters'), member_type=mode.member_type)
    return span, specs, bases


def _component_checks(split, case, stage, beam_limits, deck_fc, profile):
    from . import analysis_page as ap
    native = ap._final_service_component_decision_rows(
        split, beam_limits=beam_limits, deck_fc_MPa=deck_fc)
    rows = []
    for row in native.to_dict('records'):
        status = str(row['Check status'])
        component = row['Concrete component']
        points = split.loc[split['Concrete component'] == component]
        idx = points['Total stress (MPa)'].idxmin() if row['Demand'] == 'Compression' else points['Total stress (MPa)'].idxmax()
        point = points.loc[idx]
        comp, tens, _ = ap._component_stress_limits(points, component,
            beam_limits=beam_limits, deck_fc_MPa=deck_fc)
        # Retain full native stress precision for ranking/markers. Rounding is
        # presentation only and must not choose the wrong near-limit case.
        row.update({'Station x (m)': float(point['Station x (m)']),
            'Actual stress (MPa)': float(point['Total stress (MPa)']),
            'Limit stress (MPa)': -comp if row['Demand'] == 'Compression' else tens,
            'Utilization': ap._girder_sls_demand_utilization(float(point['Total stress (MPa)']),
                comp if row['Demand'] == 'Compression' else tens,
                demand_type=row['Demand'].lower())})
        rows.append({**row, 'Stage': stage, 'Case Name': case,
            'Status': 'Preview ' + status if status in ('PASS', 'FAIL') else 'REVIEW',
            'Controls': row['Demand'], 'Limit profile': row['Limit basis'],
            'Limit profile key': str(getattr(profile, 'limit_profile_key', '')),
            'Limit profile source': row['Limit basis'], 'Basis': 'Staged composite · material specific'})
    return rows


def calculate():
    from . import analysis_page as ap
    from concrete_pmm_pro.io.girder_sls_import import active_member
    state = ap.st.session_state
    clear_handoff(state)
    state.pop(RUNTIME_KEY, None)
    span, specs, bases = prepare()
    if not getattr(bases, 'bases', None):
        raise ValueError('No valid section basis. Review Sections before calculating SLS.')
    loads = ap._beam_sls_load_rows_from_session_state()
    validate_source(loads, span)
    allowed_stages = {stage for _, stage, _ in specs}
    if any(row.get('Stage') not in allowed_stages for row in loads):
        raise ValueError('An active SLS row has no recognized stage. Review Loads before calculating.')
    stages, summaries, all_checks = {}, [], []
    for _, stage, _ in specs:
        source = ap._beam_sls_rows_for_stage(loads, stage)
        prepared = ap._girder_sls_stage_rows_with_auto_station_grid(stage, source, span)
        raw = ap._girder_full_length_sls_stage_rows(stage_label=stage, load_rows=prepared,
            basis_options=bases, basis_names=list(bases.bases), span_length_m=span)
        if raw.empty:
            raise ValueError(stage + ': no valid station results.')
        required = ['Station x (m)', 'Top total (MPa)', 'Bottom total (MPa)']
        if not np.isfinite(raw[required].apply(pd.to_numeric, errors='coerce').to_numpy()).all():
            raise ValueError(stage + ': non-finite stress results; no decision is published.')
        comp, tens, profile_label = ap._girder_sls_diagram_limit_summary(stage)
        if not all(math.isfinite(float(v)) and float(v) >= 0 for v in (comp, tens)):
            raise ValueError(stage + ': stress limits are unavailable.')
        profile = ap._girder_stage_limit_profile_for_diagram(stage)
        deck_fc = ap._final_service_deck_fc_from_session()
        split = ap._final_service_composite_split_rows(raw, bases) if stage == 'Service stage' else pd.DataFrame()
        if not split.empty and not np.isfinite(pd.to_numeric(split['Total stress (MPa)'], errors='coerce')).all():
            raise ValueError(stage + ': component stresses are unavailable.')
        checks, case_results, notes = [], {}, []
        for case, frame in raw.groupby('Case Name', sort=False):
            frame = frame.reset_index(drop=True)
            split_case = split.loc[split['Case Name'] == case].reset_index(drop=True) if not split.empty else pd.DataFrame()
            if not split_case.empty:
                case_checks = _component_checks(split_case, case, stage, (comp, tens), deck_fc, profile)
            else:
                case_checks = [{'Stage': stage, 'Controls': row['Demand'], **row}
                    for row in ap._girder_sls4b_governing_demand_rows(frame, stage)]
                status, _, _ = ap._girder_full_length_preview_status(frame, stage)
                if status == 'REVIEW':
                    for row in case_checks:
                        if 'FAIL' not in row['Status']:
                            row['Status'] = 'REVIEW'
            issues = list(dict.fromkeys(text for text in
                frame.get('Reference review', pd.Series(dtype=str)).fillna('').astype(str).str.strip()
                if text))
            if frame['Active PS groups'].astype(str).str.startswith('Prestress unavailable:').any():
                issues.append('Prestress evaluation unavailable; review Prestress inputs.')
            if (state.get('section_has_prestressing_steel') and state.get('girder_strand_layout_table') is None
                    and not frame['SLS force content'].eq('total_with_prestress').all()):
                issues.append('Prestress station layout is missing; review Prestress inputs.')
            if not split_case.empty and ap._analysis_float_or_zero((state.get('section_parameters') or {}).get('deck_fc_MPa')) <= 0:
                issues.append('Slab concrete strength is missing; the existing fallback requires review.')
            x = frame['Station x (m)']
            if float(x.min()) > 1e-7 or float(x.max()) < span - 1e-7:
                issues.append('Source stations do not cover both ends; graph values are not extrapolated.')
            if issues:
                for row in case_checks:
                    if 'FAIL' not in row['Status']:
                        row['Status'] = 'REVIEW'
                    row['Review notes'] = ' '.join(issues)
            tx, ty, _ = ap._girder_sls_tension_limit_trace_for_graph(stage, frame)
            limits = {'Precast beam': {'compression': comp, 'x': tx, 'tension': ty, 'label': profile_label}}
            if not split_case.empty:
                for component in ('Precast beam', 'CIP / topping'):
                    c, t, label = ap._component_stress_limits(split_case, component,
                        beam_limits=(comp, tens), deck_fc_MPa=deck_fc)
                    limits[component] = {'compression': c, 'x': [0., span], 'tension': [t, t], 'label': label}
            case_results[str(case)] = {'raw': frame, 'split': split_case,
                'checks': case_checks, 'limits': limits, 'issues': issues}
            checks.extend(case_checks)
            notes.extend(issues)
        governing = controlling(checks)
        summary = {**(governing or {}), 'Stage': stage, 'Status': overall_status(checks),
            'Cases checked': len(case_results), 'Source scope': 'Selected SLS girder · all calculated cases'}
        summaries.append(summary)
        all_checks.extend(checks)
        stages[stage] = {'cases': case_results, 'checks': checks, 'summary': summary,
            'issues': list(dict.fromkeys(notes)), 'profile': profile_label}
    member = active_member(state) or 'Current girder'
    for row in summaries + all_checks:
        row['Girder'] = member
    result = {'version': VERSION, 'member': member, 'span_m': span, 'stages': stages,
        'summary': summaries, 'checks': all_checks,
        'code_label': ap.workflow_project_code_label_from_session(state)}
    result['signature'] = fingerprint(state)
    state[RUNTIME_KEY] = result
    publish(state, result)
    return result


def publish(state, result):
    if result['signature'] != fingerprint(state):
        clear_handoff(state)
        return
    prefix = 'result_summary_beam_girder_sls_'
    state[prefix+'stage_summary_df'] = pd.DataFrame(result['summary'])
    state[prefix+'stage_summary_rows'] = [dict(r) for r in result['summary']]
    state[prefix+'demand_detail_df'] = pd.DataFrame(result['checks'])
    state[prefix+'code_label'] = result['code_label']
    state[prefix+'cache_hash'] = str(state.get('analysis_input_hash') or state.get('project_input_hash') or '')
    state[HANDOFF_KEY] = result['signature']
