"""Bounded bar-spacing proposals, checked by the accepted AASHTO engine.

Proposals retain all diameters, covers, materials and concurrent source vectors.
They are NOT applied inputs, not a minimum-steel optimizer, and do not replace
the current result in Summary / Report. Concrete shear and unresolved scopes
remain visible even when every known reinforcement ratio is below one.
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

from concrete_pmm_pro.analysis import slab_top65 as base, slab_aashto63 as code
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.analysis.slab_shell56 import SlabSteel, GROUPS

VERSION = 'SLAB.DESIGN66'
RESULT_KEY = 'slab_shell55_design66_result'
VIEWS = base.VIEWS
METHODS = base.METHODS
save_load_basis = base.save_load_basis
MAX_TRIALS = 4
GRID_MM = 10.
REBAR_VIEWS = [v for v in VIEWS if not v.startswith('Shear ·')]
SCOPE = ('A bar-spacing proposal for directional sectional checks only. '
    'Diameters, physical mat levels and concrete thickness are unchanged. '
    'All retained native records and available same-direction support-face '
    'samples are rechecked; exclusions and missing samples are preserved. '
    'Nxy/Mxy interaction, biaxial shear, local support paths, anchorage, fatigue '
    'and SLS remain separate. Proposed reinforcement is not applied to the model.')


def fingerprint(state):
    value = base.fingerprint(state)
    return hashlib.sha256((VERSION+str(value)).encode()).hexdigest() if value else None


def proposal_fingerprint(state):
    """Ballast / nominal UDL metadata cannot change a reinforcement proposal."""
    value = base.accepted.fingerprint(state)
    if not value:
        return None
    p = state.get('section_parameters') or {}
    payload = {'version': VERSION, 'section': value,
        'aggregate': [p.get('shear_max_aggregate_mm'), p.get('shear_aggregate_confirmed')],
        'max_trials': MAX_TRIALS, 'grid_mm': GRID_MM}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def current(state):
    saved = state.get(RESULT_KEY)
    try:
        return saved if isinstance(saved, dict) and saved.get('version') == VERSION and saved.get('fingerprint') == fingerprint(state) else None
    except (ValueError, TypeError):
        return None


def with_spacing(steel, spacing):
    spacing = np.asarray(spacing, float)
    return SlabSteel(math.pi*steel.diameter**2/4*1000/spacing,
        steel.fy.copy(), steel.centre.copy(), steel.diameter.copy(), spacing.copy(), steel.fc)


def minimum_spacing(steel, parameters):
    """Trial construction bound; an unconfirmed aggregate never earns PASS."""
    try:
        aggregate = float(parameters.get('shear_max_aggregate_mm'))
    except (TypeError, ValueError):
        aggregate = 0.
    if not math.isfinite(aggregate) or aggregate < 0:
        aggregate = 0.
    clear = np.maximum.reduce((1.5*steel.diameter, np.full(4, 1.5*aggregate), np.full(4, 38.1)))
    return np.ceil((steel.diameter+clear)/GRID_MM-1e-12)*GRID_MM


def _source_columns(frame):
    names = ['Area', 'AreaElem', 'Joint', 'OutputCase', 'CaseType', 'StepType', 'StepNum',
        'X (m)', 'Y (m)', 'Thickness (mm)', 'Record type', INCLUDED,
        'Nx', 'Ny', 'Nxy', 'Mx', 'My', 'Mxy', 'Vx', 'Vy',
        'F11', 'F22', 'F12', 'M11', 'M22', 'M12', 'V13', 'V23',
        'Direction', 'Target in accepted scope']
    return [c for c in names if c in frame]


def evaluate(accepted, steel, parameters):
    """Every candidate uses the existing equations, not scaled old capacities."""
    original = accepted['rows']
    native = original.loc[original[INCLUDED], _source_columns(original)]
    checks = code.section_checks(native, steel)
    # Preserve the accepted local-support scope. No new numeric tie value is
    # introduced inside an unresolved reaction footprint.
    for direction, *_ in code.AXES:
        mask = original.loc[native.index, direction+' local support region']
        for kind in ('shear', 'tie'):
            checks.loc[mask, direction+' '+kind+' D/C'] = np.nan
            checks.loc[mask, direction+' '+kind+' status'] = 'REVIEW'
    checked = pd.concat((native, checks), axis=1)
    faces = accepted['support_faces']
    if len(faces):
        faces = faces.loc[faces['Target in accepted scope'], _source_columns(faces)].copy()
        available = faces.loc[faces[INCLUDED]]
        derived = code.section_checks(available, steel).reindex(faces.index) if len(available) else checks.iloc[:0].reindex(faces.index)
        for _, status in VIEWS.values():
            derived.loc[~faces[INCLUDED], status] = 'REVIEW'
        faces = pd.concat((faces, derived), axis=1)
    summary = code._summary(checked)
    governors = []
    for direction, *_ in code.AXES:
        sample = faces.loc[faces.Direction.eq(direction)] if len(faces) else faces
        design = pd.concat((checked, sample), ignore_index=True) if len(sample) else checked
        labels = [prefix+direction.lower() for prefix in ('Shear · ', 'Flexural shear tie · ')]
        s = code._summary(design, labels).set_index('Check')
        for label in labels:
            summary.loc[summary.Check.eq(label), s.columns] = s.loc[label].to_numpy()
        # Retain the exact candidate governing vector for independent review.
        for label in [*labels, 'Direct N–M · '+direction.lower()]:
            source = design if label in labels else checked
            col, _ = VIEWS[label]
            known = source.loc[source[col].notna()]
            if len(known):
                row = known.loc[known[col].idxmax()]
                record = {k: row[k] for k in _source_columns(source) if k not in (INCLUDED, 'Target in accepted scope')}
                record.update(Check=label, **{'D/C': float(row[col])})
                governors.append(record)
    if accepted['incomplete']:
        summary.loc[summary.Status.eq('PASS'), 'Status'] = 'REVIEW'
    spacing = base.clear_spacing(steel, parameters)
    partial = {**accepted, 'rows': checked, 'support_faces': faces, 'steel': steel}
    mats = base.bending_envelopes(partial, spacing)
    return {'summary': summary, 'mats': mats, 'clear_spacing': spacing,
        'governors': pd.DataFrame(governors), 'native_rechecked': len(native),
        'face_rechecked': int(faces[INCLUDED].sum()) if len(faces) else 0}


def _factors(evaluation):
    factors = np.ones(4)
    mats = evaluation['mats']
    for i, row in mats.iterrows():
        for column in ('Tension-side shear tie D/C', 'Temperature D/C', 'Spacing D/C'):
            value = row[column]
            if pd.notna(value):
                factors[i] = max(factors[i], float(value))
    # Axial / bending compatibility uses both mats. Strengthening only the
    # nominal tension mat is not assumed to fix a failed N-M domain.
    summary = evaluation['summary'].set_index('Check')
    for indices, direction in [((0, 1), 'longitudinal'), ((2, 3), 'transverse')]:
        value = summary.loc['Direct N–M · '+direction, 'Max D/C']
        if pd.notna(value):
            factors[list(indices)] = np.maximum(factors[list(indices)], value)
    return factors


def propose(accepted, parameters, *, progress=None):
    start = time.monotonic()
    original = accepted['steel']
    lower = minimum_spacing(original, parameters)
    evaluation = {'summary': accepted['summary'], 'mats': accepted['mat_envelopes'],
        'clear_spacing': accepted['clear_spacing'], 'governors': pd.DataFrame(),
        'native_rechecked': 0, 'face_rechecked': 0}
    spacing = original.spacing.copy()
    history = []
    trials = 0
    while trials < MAX_TRIALS:
        factors = _factors(evaluation)
        if np.max(factors) <= 1+1e-8:
            break
        trial = spacing.copy()
        for i in range(4):
            if factors[i] > 1+1e-8:
                target = math.floor(spacing[i]/(factors[i]*1.025)/GRID_MM+1e-10)*GRID_MM
                trial[i] = min(spacing[i], max(lower[i], target))
        if np.array_equal(trial, spacing):
            break
        spacing = trial
        trials += 1
        if progress:
            progress(.78+.18*trials/MAX_TRIALS, f'Checking reinforcement proposal {trials}/{MAX_TRIALS}…')
        evaluation = evaluate(accepted, with_spacing(original, spacing), parameters)
        history.append({'Trial': trials, **{mat+' spacing (mm)': spacing[i] for i, mat in enumerate(GROUPS)},
            'Known reinforcement max D/C': float(evaluation['summary'].loc[evaluation['summary'].Check.isin(REBAR_VIEWS), 'Max D/C'].max())})
    relevant = evaluation['summary'].loc[evaluation['summary'].Check.isin(REBAR_VIEWS)]
    known_failure = relevant['Max D/C'].gt(1+1e-8).any()
    numeric_missing = relevant.loc[~relevant.Status.eq('NOT REQUIRED'), 'Max D/C'].isna().any()
    known_ok = not known_failure and not numeric_missing
    review = relevant.Status.eq('REVIEW').any() or evaluation['clear_spacing']['Clear spacing status'].eq('REVIEW').any()
    clear_fail = evaluation['clear_spacing']['Clear spacing status'].eq('FAIL').any()
    status = 'REVIEW' if review else 'PASS'
    if known_failure or clear_fail:
        status = 'NO FEASIBLE SPACING FOUND'
    mats = evaluation['mats'].copy()
    mats.insert(2, 'Current spacing (mm)', original.spacing)
    mats.insert(3, 'As current (mm²/m)', original.area)
    mats = mats.rename(columns={'Spacing (mm)': 'Proposed spacing (mm)',
        'As provided (mm²/m)': 'As proposed (mm²/m)'})
    shear = evaluation['summary'].loc[evaluation['summary'].Check.str.startswith('Shear ·')].copy()
    return {**evaluation, 'mats': mats, 'status': status, 'known_rebar_checks_satisfied': bool(known_ok and not clear_fail),
        'spacing': spacing.tolist(), 'diameter': original.diameter.tolist(),
        'changed': bool(np.any(spacing != original.spacing)), 'trials': trials,
        'history': pd.DataFrame(history), 'shear': shear,
        'concrete_shear_has_failures': bool(shear.Status.eq('FAIL').any()),
        'minimum_trial_spacing': lower.tolist(), 'seconds': time.monotonic()-start,
        'applied_to_project': False, 'full_deck_acceptance': False, 'scope': SCOPE}


def calculate(state, *, progress=None, reuse=None):
    start = time.monotonic()
    previous = state.get(RESULT_KEY)
    actual = base.current(state)
    if actual is None:
        actual = base.calculate(state, reuse=reuse,
            progress=(lambda v, text: progress(.75*v, text)) if progress else None)
    signature = proposal_fingerprint(state)
    same = (isinstance(previous, dict) and previous.get('proposal_fingerprint') == signature and
        isinstance(previous.get('reinforcement_proposal'), dict))
    proposal = previous['reinforcement_proposal'] if same else propose(actual,
        state.get('section_parameters') or {}, progress=progress)
    if progress:
        progress(1., 'Current checks and reinforcement proposal complete')
    return {**actual, 'version': VERSION, 'fingerprint': fingerprint(state), 'top65_result': actual,
        'reinforcement_proposal': proposal, 'proposal_fingerprint': signature,
        'proposal_reused': bool(same), 'design66_seconds': time.monotonic()-start}


def map_adapter(result, view):
    return base.map_adapter(result, view)


def report_zip(result, *, interface=None):
    """Actual results remain primary; proposals are clearly separate files."""
    actual = result['top65_result']
    proposal = result['reinforcement_proposal']
    buffer = BytesIO()
    with ZipFile(BytesIO(base.report_zip(actual, interface=interface))) as old, ZipFile(buffer, 'w', ZIP_DEFLATED) as new:
        for name in old.namelist():
            new.writestr('Current/'+name, old.read(name))
        for name, key in [('Four_Mats', 'mats'), ('Checked_Sections', 'summary'),
                          ('Clear_Spacing', 'clear_spacing'), ('Shear_Still_Required', 'shear'),
                          ('Exact_Governing_Vectors', 'governors'), ('Trial_History', 'history')]:
            new.writestr('Proposal/'+name+'.csv', proposal[key].to_csv(index=False).encode('utf-8-sig'))
        new.writestr('Proposal/Scope.json', json.dumps({k: proposal[k] for k in
            ('status', 'known_rebar_checks_satisfied', 'changed', 'trials', 'spacing', 'diameter',
             'native_rechecked', 'face_rechecked', 'applied_to_project', 'full_deck_acceptance', 'scope')}, indent=2))
        new.writestr('READ_ME.txt', 'SLAB.DESIGN66\nCurrent/ contains checks of the APPLIED project inputs.\n'
            'Proposal/ is a separately checked bar-spacing proposal, NOT applied reinforcement.\n'
            'Changing spacing does not increase concrete thickness or invent slab shear steel.\n'
            'Inspect remaining one-way shear and scope reviews before changing the design.\n')
    return buffer.getvalue()
