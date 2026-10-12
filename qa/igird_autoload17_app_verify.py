"""Actual app automatic import and member-specific calculation acceptance."""
import argparse
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import pickle
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pandas as pd
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json,project_to_json,project_from_session_state
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY,ACTIVE_KEY
from concrete_pmm_pro.io.girder_csi_import import read_tables,source_info,FORCE_MAP
from concrete_pmm_pro.ui import analysis_page as ap,igird_member_results as mr
from concrete_pmm_pro.ui.girder_csi_import import UPLOAD_LABEL
parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--seed',required=True);args=parser.parse_args()
state={};apply_project_to_session_state(project_from_json(Path(args.project).read_text()),state)
state['_nav_active_workspace']='Loads'
assert not Path(args.seed).resolve().is_relative_to(ROOT)
Path(args.seed).parent.mkdir(parents=True,exist_ok=True);Path(args.seed).write_bytes(pickle.dumps(state))
class Upload(BytesIO):
    def __init__(self,data,name):super().__init__(data);self.name=name
fixture=ROOT/'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx'
files=[Upload(fixture.read_bytes(),'ULS_Girder Force uploaded to app.xlsx')]
at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=120)
for k,v in state.items():at.session_state[k]=deepcopy(v)
at.session_state[mr.CACHE_KEY]={'old':{}}
at.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY]={'old':{}}
def uploader(label,*a,**kw):return files if label==UPLOAD_LABEL else ([] if kw.get('accept_multiple_files') else None)
def run():
    at.run(timeout=120)
    assert not at.exception,[e.message for e in at.exception]
def bank_values():
    frame=at.session_state[BANK_KEY].copy()
    for c in ['Station x (m)','Mux','Vuy','Tu','Muy','Vux','Nu']:frame[c]=pd.to_numeric(frame[c]).astype(float)
    return frame.sort_values(['Girder','Case Name','Station x (m)']).reset_index(drop=True)
records={}
with patch('streamlit.file_uploader',side_effect=uploader),patch.object(mr,'calculate_member',wraps=mr.calculate_member) as calculator:
    run()
    bank=deepcopy(bank_values())
    assert len(bank)==640 and bank.Girder.nunique()==2 and bank.Nu.ne(0).all()
    for _,r in bank.iterrows():
        info=source_info(r)
        assert r.Girder==info['bridge_object']+' / '+info['girder']
        assert all(float(r[target])==float(info['raw_fields'][source]) for source,target in FORCE_MAP.items())
        assert info['kind']=='ENVELOPE'
    assert not any(b.label in ['Replace entire girder collection','Add tables to girder collection','Use this girder — all imported load cases'] for b in at.button)
    assert any('Last successful import' in s.value for s in at.success)
    assert mr.CACHE_KEY not in at.session_state.filtered_state
    assert ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY not in at.session_state.filtered_state
    assert at.session_state['section_parameters']==state['section_parameters']
    assert calculator.call_count==0
    records.update({'automatic_import_no_apply_click':True,'640_rows_two_girders_exact':True,
        'all_six_force_components_and_raw_P_retained':True,'old_uls_results_cleared':True,'section_unchanged':True})
    # Ordinary reruns must preserve manual load edits and cannot reapply a file.
    active=at.session_state['beam_uls_loads_table'].copy()
    original=float(active.iloc[0].Nu);active.loc[active.index[0],'Nu']=original+1
    at.session_state['beam_uls_loads_table']=active
    run();assert float(at.session_state['beam_uls_loads_table'].iloc[0].Nu)==original+1
    active=at.session_state['beam_uls_loads_table'].copy();active.loc[active.index[0],'Nu']=original
    at.session_state['beam_uls_loads_table']=active;run()
    records['same_upload_rerun_preserves_load_edits']=True
    # Selecting a member is immediate; another assignment button is unnecessary.
    for member in ['BOBJ1 / Interior Girder 2','BOBJ1 / Left Exterior Girder']:
        next(s for s in at.selectbox if s.label=='Girder shown in the load table').set_value(member);run()
        assert at.session_state[ACTIVE_KEY]==member
        assert len(at.session_state['beam_uls_loads_table'])==320
        assert all(source_info(r)['girder']==member.split(' / ',1)[1] for _,r in at.session_state['beam_uls_loads_table'].iterrows())
    records['member_switch_no_assignment_button']=True
    restored={};apply_project_to_session_state(project_from_json(project_to_json(project_from_session_state(at.session_state.filtered_state))),restored)
    assert sorted(restored[BANK_KEY].Note)==sorted(bank.Note)
    records['project_roundtrip_sources_retained']=True
    # Invalid new upload is atomic and leaves the good collection untouched.
    before=deepcopy(bank_values())
    raw=read_tables(fixture.read_bytes(),fixture.name)['Bridge Object Girder Forces']
    raw.iloc[1,raw.columns.get_loc('P')]='bad'
    files[:]=[Upload(raw.to_csv(index=False).encode(),'invalid.csv')]
    run();assert at.error;pd.testing.assert_frame_equal(bank_values(),before)
    assert any('previous ULS loads' in e.value for e in at.error)
    records['invalid_upload_preserves_previous_loads']=True
    # New valid content commits without a button; existing source values remain exact.
    raw=read_tables(fixture.read_bytes(),fixture.name)['Bridge Object Girder Forces']
    files[:]=[Upload(raw.to_csv(index=False).encode(),'native.csv')]
    run();assert any('native.csv' in s.value for s in at.success)
    assert len(bank_values())==640
    records['new_valid_file_replaces_collection_automatically']=True
    files.clear();run();assert len(bank_values())==640
    records['removing_upload_keeps_stored_loads']=True
    assert calculator.call_count==0
    # Calculate once, independently for each physical member.
    at.session_state['_nav_active_workspace']='Analysis';run()
    next(r for r in at.radio if r.label=='ULS check to calculate').set_value('Shear + Torsion');run()
    assert calculator.call_count==0
    next(b for b in at.button if b.label.startswith('Calculate Shear + Torsion — all')).click();run()
    assert calculator.call_count==2
    expected=mr.member_inputs(at.session_state.filtered_state)
    summaries=[]
    for member,entry in at.session_state[mr.CACHE_KEY].items():
        result=entry['Shear + Torsion']['result'];assert not result.get('error'),result.get('error')
        frame=result['combined_vt_df'];rows=expected[member]
        assert len(frame)==320
        for _,r in frame.iterrows():
            source=rows[rows['Case Name'].eq(r.Case)&rows['Station x (m)'].eq(float(r['Governing x'].replace(' m','')))].iloc[0]
            for key,col in [('Source Mux kN-m','Mux'),('Source Vuy kN','Vuy'),('Source Tu kN-m','Tu'),('Source Nu kN','Nu')]:
                assert float(r[key])==float(source[col]),(member,key)
            assert source_info(source)['girder']==member.split(' / ',1)[1]
        summaries.append({'member':member,'rows':len(frame),'cases':frame.Case.nunique(),
            'statuses':frame.Status.value_counts().to_dict(),'maximum_numeric_dc':float(frame['Overall D/C value'].max())})
    records['production_calculations_use_own_girder_sources']=summaries
    records['manual_calculator_calls']=2
out=ROOT/'qa/evidence/igird_autoload17';out.mkdir(parents=True,exist_ok=True)
(out/'app_checks.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records,indent=2),flush=True)
