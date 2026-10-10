"""Native CSI vectors with a hypothetical section model for chart verification.

U2A uses the archived workbook vectors unchanged. QA_LC2 scales that source
table solely to exercise LC switching; neither is the user's complete project.
"""
from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
import pandas as pd
from concrete_pmm_pro.io.girder_csi_import import prepare_csi_table, read_tables
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY, activate_member
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS
from test_igird_uls7_concurrent_vt import ready_state
from test_igird_multicase_deckuls1 import deck_state
from test_igird_uls6_torsion_general_procedure import _route


def native_model(*, second_lc=True):
    state = ready_state()
    state['section_parameters'].update(deck_state()['section_parameters'])
    for face in ('top', 'bottom'):
        state['section_parameters']['deck_long_rebar_'+face+'_left_anchored'] = True
        state['section_parameters']['deck_long_rebar_'+face+'_right_anchored'] = True
    path = Path('qa/fixtures/CSiBridge_ULS_Girder_Max_Min.xlsx')
    tables = read_tables(path.read_bytes(), path.name)
    bank = []
    for member in ('Left Exterior Girder', 'Interior Girder 2'):
        for lc, factor in ([('U2A', 1.), ('QA_LC2', .65)] if second_lc else [('U2A', 1.)]):
            raw = tables[member].copy(deep=True)
            # The fixture has a units row. Multiplication leaves that row alone.
            for column in ('P', 'V2', 'V3', 'T', 'M2', 'M3'):
                numeric = pd.to_numeric(raw[column], errors='coerce')
                for index in numeric.index[numeric.notna()]:
                    raw.at[index, column] = float(numeric.loc[index]) * factor
            imported = prepare_csi_table(raw, sheet_name=member, case_name=lc,
                source_name=path.name+' [archived QA fixture]')
            assert not imported.errors, imported.errors
            rows = imported.frame
            rows['Girder'] = member
            rows['Case Name'] = member+' / '+rows['Case Name']
            bank.append(rows)
    state[BANK_KEY] = pd.concat(bank, ignore_index=True)
    activate_member(state, 'Left Exterior Girder')
    return state


def calculate_native_model(*, second_lc=True):
    state = native_model(second_lc=second_lc)
    state[mr.CACHE_KEY] = {}
    for member, rows in mr.member_inputs(state).items():
        state[mr.CACHE_KEY][member] = {}
        for check in FRAME_KEYS:
            result = mr.calculate_member(state, rows, check_name=check, route=_route())
            assert not result.get('error'), result
            state[mr.CACHE_KEY][member][check] = {
                'input_hash': mr.result_hash(state, rows, check_name=check, route=_route()),
                'result': result}
    return state
