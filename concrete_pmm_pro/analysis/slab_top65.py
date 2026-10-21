"""Top-slab ULS workspace over the accepted AASHTO sectional engine.

The four native CSI export sets remain the only analysis inputs. Load-basis
metadata never scales, disperses, translates or otherwise modifies an action.
Directional N-M checks are section checks using both physical mats, not a
claim of a complete shell Nxy/Mxy/Vx/Vy interaction solution.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
import math
import time
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import pandas as pd

from concrete_pmm_pro.analysis import slab_shear64 as accepted
from concrete_pmm_pro.analysis import slab_aashto63 as sections
from concrete_pmm_pro.analysis import slab_shell56 as inputs
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.io.slab_shell_import import current_package

VERSION = 'SLAB.TOP65'
RESULT_KEY = 'slab_shell55_top65_result'
CONFIG_KEY = 'slab_top65_load_basis'
METHODS = {'imported': 'Imported CSI shell results',
           'equivalent_udl': 'Equivalent train UDL in CSI'}
VIEWS = accepted.VIEWS
DEFAULT_BASIS = {'version': 1, 'method': 'imported', 'ballast_mm': 300.,
    'track_width_m': 2., 'nominal_pressure_kpa': 75., 'source_signature': []}


def load_basis(state):
    """Input-only provenance; defaults are editable project assumptions."""
    stored = (state.get('project_metadata') or {}).get(CONFIG_KEY, {})
    if not isinstance(stored, dict):
        raise ValueError('Top slab load basis must be an input object')
    out = {**DEFAULT_BASIS, **stored}
    if out['method'] not in METHODS:
        raise ValueError('Select a supported CSI load model')
    for key, allow_zero in (('ballast_mm', True), ('track_width_m', False),
                             ('nominal_pressure_kpa', False)):
        try:
            value = float(out[key])
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid top slab input: '+key) from exc
        if not math.isfinite(value) or value < 0 or (not allow_zero and value == 0):
            raise ValueError('Top slab input must be finite and '+
                ('nonnegative: ' if allow_zero else 'positive: ')+key)
        out[key] = value
    signature = out.get('source_signature', [])
    if not isinstance(signature, (list, tuple)) or not all(isinstance(s, str) for s in signature):
        raise ValueError('Invalid top slab source signature')
    return {k: (sorted(signature) if k == 'source_signature' else out[k]) for k in DEFAULT_BASIS}


def save_load_basis(state, values):
    metadata = dict(state.get('project_metadata') or {})
    stored = metadata.get(CONFIG_KEY, {})
    candidate = {**DEFAULT_BASIS, **(stored if isinstance(stored, dict) else {}), **values}
    package = current_package(state)
    candidate['source_signature'] = list(package.signature) if package else []
    checked = load_basis({'project_metadata': {CONFIG_KEY: candidate}})
    metadata[CONFIG_KEY] = checked
    state['project_metadata'] = metadata
    return checked


def basis_status(state, basis=None):
    basis = basis or load_basis(state)
    package = current_package(state)
    if not basis['source_signature']:
        return 'NOT RECORDED'
    return ('SOURCE MATCHED' if package is not None and
        sorted(package.signature) == basis['source_signature'] else 'SOURCE CHANGED')


def fingerprint(state):
    base = accepted.fingerprint(state)
    if base is None:
        return None
    parameters = state.get('section_parameters') or {}
    return hashlib.sha256(json.dumps({'version': VERSION, 'base': base,
        'clear_spacing_inputs': {k: parameters.get(k) for k in
            ('shear_max_aggregate_mm', 'shear_aggregate_confirmed')},
        'load_basis': load_basis(state)}, sort_keys=True).encode()).hexdigest()


def current(state):
    saved = state.get(RESULT_KEY)
    try:
        valid = (isinstance(saved, dict) and saved.get('version') == VERSION and
                 saved.get('fingerprint') == fingerprint(state))
    except (ValueError, TypeError):
        valid = False
    return saved if valid else None


def clear_spacing(steel, parameters):
    """5.10.3.1.1: cast-in-place parallel bars; no bundled/lap credit.

    The aggregate value is read from the existing project input. An unconfirmed
    value is displayed as a trial, not used to certify the aggregate branch.
    A failure of the diameter / 1.5-in absolute bound is a known failure.
    """
    raw = parameters.get('shear_max_aggregate_mm')
    try:
        aggregate = float(raw)
    except (ValueError, TypeError):
        aggregate = math.nan
    known = bool(parameters.get('shear_aggregate_confirmed', False)) and math.isfinite(aggregate) and aggregate >= 0
    output = []
    for i, mat in enumerate(inputs.GROUPS):
        available = float(steel.spacing[i]-steel.diameter[i])
        lower = max(1.5*steel.diameter[i], 1.5*25.4)
        trial = max(lower, 1.5*aggregate) if math.isfinite(aggregate) and aggregate >= 0 else math.nan
        ratio = (trial if known else lower)/available if available > 0 else math.inf
        status = 'FAIL' if ratio > 1+1e-8 else 'PASS' if known else 'REVIEW'
        output.append({'Mat': mat, 'Clear spacing (mm)': available,
            'Required absolute minimum (mm)': lower,
            'Aggregate input (mm)': aggregate,
            'Required trial minimum (mm)': trial,
            'Clear spacing D/C': ratio if known or status == 'FAIL' else math.nan,
            'Clear spacing status': status,
            'Basis': '5.10.3.1.1 · existing confirmed aggregate' if known else
                '5.10.3.1.1 · aggregate branch unconfirmed; trial only'})
    return pd.DataFrame(output)


def _maximum(frame, column):
    if frame.empty or column not in frame or not frame[column].notna().any():
        return math.nan, None
    row = frame.loc[frame[column].idxmax()]
    return float(row[column]), row


def bending_envelopes(result, spacing):
    """Four readable envelopes; every governing vector is one actual row.

    N-M uses both mats. Top/bottom below identify bending sign, not separate
    fictitious capacities. Axial-dominant tension is included in both envelopes.
    Support-face samples contribute only to the matching directional shear tie.
    """
    rows = result['rows'].loc[result['rows'][INCLUDED]]
    steel = result['steel']
    output = []
    for i, mat in enumerate(inputs.GROUPS):
        direction = 'Longitudinal' if i < 2 else 'Transverse'
        face = 'Top' if i % 2 == 0 else 'Bottom'
        moment, axial = rows[direction+' Mu (kN·m/m)'], rows[direction+' Nu (kN/m)']
        both = axial > 6*abs(moment)*1000/rows['Thickness (mm)']+1e-9
        columns = ['OutputCase', 'StepType', 'X (m)', 'Y (m)', 'AreaElem', 'Joint',
            direction+' N–M D/C', direction+' N–M status',
            direction+' flexural minimum D/C', direction+' flexural minimum status']
        active = rows.loc[(moment <= 1e-12 if face == 'Top' else moment >= -1e-12) | both, columns]
        nm, governor = _maximum(active, direction+' N–M D/C')
        minimum, _ = _maximum(active, direction+' flexural minimum D/C')
        tie_columns = [direction+' tension mat', direction+' tie D/C', direction+' tie status']
        tie_rows = rows[tie_columns]
        faces = result['support_faces']
        if len(faces):
            tie_rows = pd.concat((tie_rows, faces.loc[faces['Target in accepted scope'] & faces.Direction.eq(direction), tie_columns]), ignore_index=True)
        ties = tie_rows.loc[tie_rows[direction+' tension mat'].eq(face)]
        tie, _ = _maximum(ties, direction+' tie D/C')
        temp = float(rows[mat+' temperature D/C'].max())
        maximum_spacing = float(rows[mat+' spacing D/C'].max())
        clear = spacing.iloc[i]
        missing = (len(active) > 0 and (active[direction+' N–M status'].eq('REVIEW').any() or
                   active[direction+' flexural minimum status'].eq('REVIEW').any()))
        missing |= len(ties) > 0 and ties[direction+' tie status'].eq('REVIEW').any()
        missing |= clear['Clear spacing status'] == 'REVIEW' or result['incomplete']
        finite = [x for x in (nm, minimum, tie, temp, maximum_spacing, clear['Clear spacing D/C']) if math.isfinite(x)]
        failing = (max(finite, default=0.) > 1+1e-8 or clear['Clear spacing status'] == 'FAIL')
        output.append({'Mat': mat, 'Bar (mm)': steel.diameter[i], 'Spacing (mm)': steel.spacing[i],
            'As provided (mm²/m)': steel.area[i], 'Clear cover (mm)': steel.centre[i]-steel.diameter[i]/2,
            'Section N–M D/C': nm, 'Tension-side shear tie D/C': tie,
            'Flexural minimum sufficient D/C': minimum, 'Temperature D/C': temp,
            'Spacing D/C': maximum_spacing, 'Clear spacing D/C': clear['Clear spacing D/C'],
            'Known checks': 'FAIL' if failing else 'REVIEW' if missing else 'PASS',
            'N–M case': governor.OutputCase if governor is not None else '',
            'N–M step': governor.StepType if governor is not None else '',
            'X (m)': governor['X (m)'] if governor is not None else math.nan,
            'Y (m)': governor['Y (m)'] if governor is not None else math.nan,
            'AreaElem': governor.AreaElem if governor is not None else '',
            'Joint': governor.Joint if governor is not None else '',
            'Envelope': 'Negative / top bending; axial-dominant tension included' if face == 'Top' else
                        'Positive / bottom bending; axial-dominant tension included'})
    return pd.DataFrame(output)


def required_actions(result):
    actions = []
    for _, row in result['summary'].iterrows():
        if row.Status == 'FAIL':
            kind = 'Review slab depth / concrete / load model; Vs=0 for in-plane mesh.' if row.Check.startswith('Shear ·') else (
                'Review the matching tension mat and anchorage; do not add both mats as one tie.' if row.Check.startswith('Flexural shear tie') else
                'Review the governing section and the existing four reinforcement mats.')
            actions.append({'Priority': 1, 'Check': row.Check, 'Status': 'FAIL',
                'D/C': row['Max D/C'], 'Action': kind})
    if result['punching']['status'] == 'FAIL':
        actions.append({'Priority': 1, 'Check': 'Punching shear', 'Status': 'FAIL', 'D/C': math.nan,
            'Action': 'Review the explicitly defined loaded area and its governing perimeter.'})
    if result['clear_spacing']['Clear spacing status'].eq('FAIL').any():
        actions.append({'Priority': 1, 'Check': 'Minimum clear spacing', 'Status': 'FAIL', 'D/C': math.nan,
            'Action': 'Increase parallel bar spacing or revise bar diameter / aggregate.'})
    if result['load_basis_status'] == 'SOURCE CHANGED':
        actions.append({'Priority': 2, 'Check': 'CSI load basis', 'Status': 'REVIEW', 'D/C': math.nan,
            'Action': 'Record the load basis for this newly imported CSI export set.'})
    return pd.DataFrame(actions, columns=['Priority', 'Check', 'Status', 'D/C', 'Action'])


def calculate(state, *, progress=None, reuse=None):
    start = time.monotonic()
    basis = load_basis(state)
    candidate = (reuse or {}).get('shear_result', reuse)
    valid = isinstance(candidate, dict) and candidate.get('version') == accepted.VERSION and candidate.get('fingerprint') == accepted.fingerprint(state)
    result = candidate if valid else accepted.calculate(state, progress=progress, reuse=sections.current(state))
    spacing = clear_spacing(result['steel'], state.get('section_parameters') or {})
    mats = bending_envelopes(result, spacing)
    coverage = result['code_coverage'].copy()
    mask = coverage.Check.eq('Two-way / punching shear')
    coverage.loc[mask, 'Coverage'] = result['punching']['status']
    coverage.loc[mask, 'Basis / remaining action'] = 'Explicit isolated loaded areas only; a continuous train UDL does not define a local wheel footprint.'
    coverage = pd.concat((coverage, pd.DataFrame([{'Check': 'Parallel-bar clear spacing',
        'Article': '5.10.3.1.1', 'Coverage': 'CALCULATED' if spacing['Clear spacing status'].eq('PASS').all() else 'REVIEW / FAIL',
        'Basis / remaining action': 'Cast-in-place bars: max(1.5db, 1.5ag, 1.5 in); existing aggregate input, no new bar table.'}])), ignore_index=True)
    fail = (result['component_status'] == 'FAIL' or result['punching']['status'] == 'FAIL' or
            spacing['Clear spacing status'].eq('FAIL').any())
    out = {**result, 'version': VERSION, 'fingerprint': fingerprint(state), 'shear_result': result,
        'load_basis': basis, 'load_basis_status': basis_status(state, basis),
        'clear_spacing': spacing, 'mat_envelopes': mats, 'code_coverage': coverage,
        'component_status': 'FAIL' if fail else 'REVIEW' if mats['Known checks'].eq('REVIEW').any() or result['component_status'] == 'REVIEW' else 'PASS',
        'status': 'FAIL' if fail else 'REVIEW REQUIRED', 'top65_seconds': time.monotonic()-start,
        'actions_multiplier': 1., 'ballast_in_resistance': False, 'accepted_result_reused': bool(valid)}
    out['required_actions'] = required_actions(out)
    return out


def map_adapter(result, view):
    return accepted.map_adapter(result, view)


def report_zip(result, *, interface=None):
    """Read-only compact report; no source parsing or solver invocation."""
    buffer = BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        frames = {'Check_Summary': result['summary'], 'Four_Mat_Envelopes': result['mat_envelopes'],
            'Reinforcement_Details': result['reinforcement_summary'], 'Clear_Spacing': result['clear_spacing'],
            'Source_Coverage': result['coverage'], 'Exclusion_Counts': result['exclusion_counts'],
            'Code_Coverage': result['code_coverage'], 'Required_Actions': result['required_actions'], 'Shell_Axes': result['axes']}
        if 'local_transfer_review' in result:
            frames['Local_Transfer_Review'] = result['local_transfer_review']
        if interface is not None:
            frames['Linked_Interface'] = interface['rows']
        for name, frame in frames.items():
            archive.writestr(name+'.csv', frame.to_csv(index=False).encode('utf-8-sig'))
        provenance = {'version': VERSION, 'code': result['code'], 'fingerprint': result['fingerprint'],
            'component_status': result['component_status'], 'deck_status': result['status'],
            'full_deck_acceptance': False, 'load_basis': result['load_basis'],
            'load_basis_status': result['load_basis_status'], 'source_actions_multiplier': 1.,
            'ballast_in_resistance': False, 'scope': result['scope']}
        archive.writestr('Provenance.json', json.dumps(provenance, indent=2, ensure_ascii=False))
        archive.writestr('READ_ME.txt', 'AASHTO LRFD Ninth Edition (2020).\n'
            'The imported shell actions are already factored; multiplier=1.0.\n'
            'Ballast and equivalent train pressure are analysis provenance only.\n'
            'Each N-M envelope uses both mats and a single concurrent source vector.\n'
            'Top/bottom identify bending sign; axial-dominant tension is in both.\n'
            'Minimum/spacing/shear-tie checks are separate; their capacities are not added.\n'
            'Agreed connection, bearing-end and one-pass peak exclusions remain.\n'
            'Nxy/Mxy interaction, local D-regions, available anchorage, fatigue and SLS\n'
            'require their applicable separate checks. No full-deck certificate is issued.\n')
    return buffer.getvalue()
