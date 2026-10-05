from io import BytesIO
import pandas as pd
import pytest
from concrete_pmm_pro.io.girder_csi_import import prepare_csi_table, APP_COLUMNS
from concrete_pmm_pro.io.girder_load_bank import *
from concrete_pmm_pro.io.project_io import project_from_session_state, apply_project_to_session_state


def collection():
    frames=[]
    for member in ('Left Girder','Interior Girder'):
        for case in ('ULS1','ULS2'):
            raw=pd.DataFrame([{'Girder Distance':x,'StepType':'Static','OutputCase':case,'P':-5,'V2':10+x,'V3':2,'T':3,'M2':4,'M3':100*x} for x in (0,10,20)])
            f=prepare_csi_table(raw,sheet_name=member,source_name=case+'.xlsx').frame
            f['Girder']=member
            frames.append(f)
    return pd.concat(frames,ignore_index=True)


def test_member_isolation_all_cases_and_edits():
    state={BANK_KEY:collection()}
    activate_member(state,'Left Girder')
    assert len(state['beam_uls_loads_table'])==6
    from concrete_pmm_pro.ui.analysis_page import _beam_uls_demand_dataframe_from_session
    assert len(_beam_uls_demand_dataframe_from_session(state))==6
    assert state['beam_uls_loads_table']['Case Name'].str.contains('Left Girder').all()
    state['beam_uls_loads_table'].loc[0,'Mux']=987
    save_active(state)
    activate_member(state,'Interior Girder')
    assert len(state['beam_uls_loads_table'])==6
    assert state['beam_uls_loads_table']['Case Name'].str.contains('Interior Girder').all()
    save_active(state)
    activate_member(state,'Left Girder')
    assert state['beam_uls_loads_table'].loc[0,'Mux']==987
    assert len(state[BANK_KEY])==12


def test_append_duplicate_and_replace():
    bank=collection()
    with pytest.raises(ValueError,match='Duplicate'):
        merge_bank(bank,bank,append=True)
    assert len(merge_bank(bank,bank.iloc[:3],append=False))==3
    fresh=bank.copy();fresh['Case Name']='new / '+fresh['Case Name']
    assert len(merge_bank(bank,fresh,append=True))==24


def test_json_roundtrip_restores_collection_and_active_member():
    state={BANK_KEY:collection()}
    activate_member(state,'Interior Girder')
    project=project_from_session_state(state)
    restored={ACTIVE_KEY:'wrong',BANK_KEY:collection().iloc[:1]}
    apply_project_to_session_state(project,restored)
    save_active(restored)
    assert restored[ACTIVE_KEY]=='Interior Girder'
    assert len(restored[BANK_KEY])==12
    assert len(restored['beam_uls_loads_table'])==6


