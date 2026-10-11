"""Unchanged CSIIMPORT14 force vectors with a hypothetical QA section model."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import pandas as pd
from concrete_pmm_pro.io.girder_csi_import import read_tables, split_member_tables, prepare_csi_table
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY, activate_member
from test_igird_uls7_concurrent_vt import ready_state
from test_igird_multicase_deckuls1 import deck_state


def source_model():
    state = ready_state()
    state['section_parameters'].update(deck_state()['section_parameters'])
    for face in ('top', 'bottom'):
        for side in ('left', 'right'):
            state['section_parameters'][f'deck_long_rebar_{face}_{side}_anchored'] = True
    path = ROOT / 'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx'
    raw = read_tables(path.read_bytes(), path.name)['Bridge Object Girder Forces']
    bank = []
    for group in split_member_tables(raw, sheet_name='Bridge Object Girder Forces'):
        imported = prepare_csi_table(group.frame, sheet_name='Bridge Object Girder Forces', source_name=path.name)
        assert not imported.errors, imported.errors
        rows = imported.frame.copy()
        rows['Case Name'] = group.name+' / '+rows['Case Name']
        rows['Girder'] = group.name
        bank.append(rows)
    state[BANK_KEY] = pd.concat(bank, ignore_index=True)
    activate_member(state, 'BOBJ1 / Left Exterior Girder')
    return state
