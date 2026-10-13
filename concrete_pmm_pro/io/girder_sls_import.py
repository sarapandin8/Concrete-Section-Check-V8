"""Input-only CSiBridge SLS correspondence collection, separate from ULS."""
from __future__ import annotations
import hashlib
import json
from zipfile import BadZipFile
import pandas as pd
from concrete_pmm_pro.io.girder_csi_import import (
    SOURCE_TAG, read_tables, split_member_tables, prepare_csi_table,
    is_csi_table, is_native_bridge_table, source_info,
)
VERSION = 'IGIRDER.SLSIMPORT23'
BANK_KEY = 'igird_sls_member_bank'
SELECTION_KEY = 'igird_sls_member_selection'
ACTIVE_KEY = 'igird_sls_active_member'
TABLE_KEY = 'beam_sls_loads_table'
COLUMNS = ['Active','Station x (m)','Case Name','Stage','Load Component','Section Basis',
           'N','Mx','My','Vy','Vx','T','Note']
STAGES = ['Service stage','Transfer stage','Construction stage']
FORCE_CONTENTS = {
    'total_external': 'Total SLS external loads; app adds prestress',
    'total_with_prestress': 'Total SLS loads including CSI prestress',
    'incremental': 'LL+IM only; app adds dead loads and prestress',
}
FORCE_MAP = {'P':'N','M3':'Mx','M2':'My','V2':'Vy','V3':'Vx','T':'T'}

def contract(row):
    source = source_info(row)
    return source if isinstance(source,dict) and source.get('sls_import_version') == VERSION and source.get('sls_force_content') in FORCE_CONTENTS else None

def parse_files(files, *, stage='Service stage', basis=None, force_content='total_external'):
    """Validate all files before commit; preserve every six-component source row.

    Concurrency is the user's declared Correspondence source, not a conclusion
    derived from Max/Min labels. Blank StepType is allowed for static SLS combos.
    """
    if stage not in STAGES or force_content not in FORCE_CONTENTS:
        raise ValueError('Unsupported SLS stage or load content.')
    basis = basis or ('Composite transformed' if stage == 'Service stage' else 'Precast gross')
    parts, errors, hashes = [], [], set()
    for upload in files:
        name = str(upload.name)
        payload = upload.getvalue()
        digest = hashlib.sha256(payload).hexdigest()
        if digest in hashes:
            errors.append(f'{name}: duplicate file bytes; choose the file once.')
            continue
        hashes.add(digest)
        try:
            tables = read_tables(payload,name)
            candidates = {n:f for n,f in tables.items() if is_native_bridge_table(f) or ('girder' in n.casefold() and is_csi_table(f))}
            if not candidates:
                errors.append(f'{name}: no Bridge Object Girder Forces table found.')
            for sheet, frame in candidates.items():
                for member in split_member_tables(frame,sheet_name=sheet):
                    result = prepare_csi_table(member.frame,sheet_name=sheet,source_name=name,
                        source_mode='correspondence',concurrency_confirmed=True,
                        evidence='Engineer declaration: supplied CSiBridge Correspondence rows contain simultaneous actions in each load case.',
                        allow_blank_step=True)
                    errors.extend(result.errors)
                    for _, row in result.frame.iterrows():
                        source = source_info(row)
                        source.update(sls_import_version=VERSION,sls_force_content=force_content,
                            sls_stage=stage,sls_force_map=FORCE_MAP,
                            sls_axial_conversion='N = -P; SLS axial compression is positive')
                        parts.append({'Girder':member.name,'Active':True,'Station x (m)':row['Station x (m)'],
                            'Case Name':row['Case Name'],'Stage':stage,
                            'Load Component':'Total SLS resultant' if force_content != 'incremental' else 'User-defined',
                            'Section Basis':basis,'N':-row['Nu'],'Mx':row['Mux'],'My':row['Muy'],
                            'Vy':row['Vuy'],'Vx':row['Vux'],'T':row['Tu'],
                            'Note':SOURCE_TAG+json.dumps(source,ensure_ascii=False,separators=(',',':'))})
        except (ValueError,TypeError,KeyError,OSError,BadZipFile) as exc:
            errors.append(f'{name}: {exc}')
    result = pd.DataFrame(parts,columns=['Girder',*COLUMNS])
    if not result.empty:
        try:
            _validate_bank(result)
        except ValueError as exc:
            errors.append(str(exc))
    return result,errors

def members(bank):
    frame = pd.DataFrame(bank)
    return list(dict.fromkeys(frame['Girder'].astype(str))) if 'Girder' in frame else []

def active_member(state):
    bank_members = members(state.get(BANK_KEY,[]))
    selection = pd.DataFrame(state.get(SELECTION_KEY,[]))
    member = str(selection.iloc[0]['Girder']) if not selection.empty and 'Girder' in selection else state.get(ACTIVE_KEY)
    return member if member in bank_members else (bank_members[0] if bank_members else None)

def invalidate_views(state):
    for key in list(state):
        if str(key).startswith('result_summary_beam_girder_sls_'):
            state.pop(key,None)

def _validate_bank(bank):
    if bank.empty:
        raise ValueError('No valid SLS force rows to import.')
    keys = bank[['Girder','Stage','Case Name','Station x (m)']].copy()
    for col in ['Girder','Stage','Case Name']:
        keys[col] = keys[col].astype(str).str.strip().str.casefold()
    keys['Station x (m)'] = pd.to_numeric(keys['Station x (m)'],errors='raise')
    if keys.duplicated().any():
        raise ValueError('Duplicate SLS girder / stage / case / station; import a source file once.')

def save_active(state):
    bank = pd.DataFrame(state.get(BANK_KEY,[]))
    member = active_member(state)
    if member is None or TABLE_KEY not in state:
        return
    stages = set(bank.loc[bank['Girder'].astype(str)==member,'Stage'].astype(str))
    table = pd.DataFrame(state[TABLE_KEY],columns=COLUMNS)
    rows = table.loc[table['Stage'].astype(str).isin(stages)].copy()
    rows['Girder'] = member
    state[BANK_KEY] = pd.concat([bank[bank['Girder'].astype(str)!=member],rows[['Girder',*COLUMNS]]],ignore_index=True)
    state[SELECTION_KEY] = pd.DataFrame([{'Girder':member}])
    state[ACTIVE_KEY] = member

def activate_member(state, member, *, save_previous=True):
    bank = pd.DataFrame(state.get(BANK_KEY,[]))
    if member not in members(bank):
        raise ValueError('Selected SLS girder is not in the imported collection.')
    if save_previous:
        save_active(state)
        bank = pd.DataFrame(state[BANK_KEY])
    old = pd.DataFrame(state.get(TABLE_KEY,[]),columns=COLUMNS)
    owned_stages = set(bank['Stage'].astype(str))
    retained = old.loc[~old['Stage'].astype(str).isin(owned_stages)]
    selected = bank.loc[bank['Girder'].astype(str)==member,COLUMNS]
    state[TABLE_KEY] = pd.concat([retained,selected],ignore_index=True)
    state[ACTIVE_KEY] = member
    state[SELECTION_KEY] = pd.DataFrame([{'Girder':member}])
    for key in list(state):
        if str(key).startswith('beam_sls_') and str(key).endswith('_loads_editor'):
            state.pop(key,None)
    invalidate_views(state)

def replace_stage(state, imported, *, stage):
    """Atomic replacement of the uploaded stage; retain other imported stages."""
    incoming = pd.DataFrame(imported).copy(deep=True)
    _validate_bank(incoming)
    if set(incoming['Stage'].astype(str)) != {stage}:
        raise ValueError('SLS stage does not match the import destination.')
    # Validate the proposed state before any user inputs are mutated.
    shadow = {k:state[k] for k in (BANK_KEY,SELECTION_KEY,ACTIVE_KEY,TABLE_KEY) if k in state}
    save_active(shadow)
    previous = pd.DataFrame(shadow.get(BANK_KEY,[]),columns=['Girder',*COLUMNS])
    combined = pd.concat([previous.loc[previous['Stage'].astype(str)!=stage],incoming],ignore_index=True)
    _validate_bank(combined)
    shadow[BANK_KEY] = combined
    activate_member(shadow,members(incoming)[0],save_previous=False)
    for key in (BANK_KEY,SELECTION_KEY,ACTIVE_KEY,TABLE_KEY):
        state[key] = shadow[key]
    for key in list(state):
        if str(key).startswith('beam_sls_') and str(key).endswith('_loads_editor'):
            state.pop(key,None)
    invalidate_views(state)
