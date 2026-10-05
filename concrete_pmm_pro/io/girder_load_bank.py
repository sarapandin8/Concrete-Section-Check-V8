"""Input-only member collection; solvers continue to consume one member's rows."""
import pandas as pd
from concrete_pmm_pro.io.girder_csi_import import APP_COLUMNS

BANK_KEY = 'igird_uls_member_bank'
ACTIVE_KEY = 'igird_active_member'
SELECTION_KEY = 'igird_uls_member_selection'


def members(bank):
    return list(dict.fromkeys(bank['Girder'].astype(str))) if 'Girder' in bank else []


def merge_bank(current, imported, *, append):
    bank = pd.concat([current, imported], ignore_index=True) if append else imported.copy(deep=True)
    keys = bank[['Girder', 'Case Name', 'Station x (m)']].copy()
    for name in ('Girder', 'Case Name'):
        keys[name] = keys[name].astype(str).str.strip().str.casefold()
    keys['Station x (m)'] = pd.to_numeric(keys['Station x (m)'], errors='raise')
    if keys.duplicated().any():
        raise ValueError('Duplicate girder / case / station. This table is already stored; replace the collection or provide a distinct source case.')
    return bank.reset_index(drop=True)


def save_active(state, *, state_key='beam_uls_loads_table'):
    bank = pd.DataFrame(state.get(BANK_KEY, []))
    selection = pd.DataFrame(state.get(SELECTION_KEY, []))
    active = state.get(ACTIVE_KEY)
    if not active and not selection.empty:
        active = str(selection.iloc[0]['Girder'])
        state[ACTIVE_KEY] = active
    if active not in members(bank) or state_key not in state:
        return
    rows = pd.DataFrame(state[state_key], columns=APP_COLUMNS).copy()
    rows['Girder'] = active
    state[BANK_KEY] = pd.concat([bank[bank['Girder'].astype(str) != active], rows], ignore_index=True)
    state[SELECTION_KEY] = pd.DataFrame([{'Girder': active}])


def activate_member(state, member, *, state_key='beam_uls_loads_table', editor_key='beam_uls_loads_editor'):
    bank = pd.DataFrame(state.get(BANK_KEY, []))
    if member not in members(bank):
        raise ValueError('Selected girder is not in the imported collection.')
    state[state_key] = bank.loc[bank['Girder'].astype(str) == member, APP_COLUMNS].copy().reset_index(drop=True)
    state[ACTIVE_KEY] = member
    state[SELECTION_KEY] = pd.DataFrame([{'Girder': member}])
    state.pop(editor_key, None)
