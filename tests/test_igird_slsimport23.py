"""Native simultaneous SLS vectors, load assembly, member state and simple UI."""
from copy import deepcopy
from io import BytesIO,StringIO
from pathlib import Path
from unittest.mock import patch
import csv,json
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io import girder_sls_import as sls
from concrete_pmm_pro.io.girder_csi_import import source_info,read_tables,split_member_tables,prepare_csi_table
from concrete_pmm_pro.io.project_io import project_from_json,project_from_session_state,project_to_json,apply_project_to_session_state
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.girder_sls_import import UPLOAD_LABEL
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=json.loads((ROOT/'qa/fixtures/CSiBridge_SLS_Girder_Forces_SLSIMPORT23.json').read_text())
class Upload(BytesIO):
    def __init__(self, rows=None):
        out=StringIO();csv.writer(out).writerows(rows or FIXTURE['rows'])
        super().__init__(out.getvalue().encode('utf-8-sig'));self.name='native_sls.csv'
def imported(**kwargs):
    frame,errors=sls.parse_files([Upload()],**kwargs);assert not errors,errors;return frame
def seed():
    state={};apply_project_to_session_state(project_from_json((ROOT/'qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()),state);return state
def run(at):
    at.run(timeout=40);assert not at.exception,[e.message for e in at.exception]
def btn(at,label='Import SLS loads'):return next(x for x in at.button if x.label==label)
SCRIPT='''
import streamlit as st
from concrete_pmm_pro.ui.girder_sls_import import render_import
page=st.radio('Page',['Loads','Analysis'])
if page=='Loads': render_import()
'''

def test_preserves_all_physical_vectors_and_source_identity():
    frame=imported();assert len(frame)==240 and frame.Girder.nunique()==2
    seen=[]
    for _,row in frame.iterrows():
        s=source_info(row);raw=s['raw_fields'];seen.append(s)
        for source,target in sls.FORCE_MAP.items():
            assert row[target]==pytest.approx(float(raw[source])*(-1 if source=='P' else 1))
        assert row['Station x (m)']==pytest.approx(float(raw['Distance']))
        assert s['kind']=='CONCURRENT' and s['concurrency_confirmed']
        assert s['case']==raw['OutputCase'] and s['location_type']==raw['LocType']
        assert s['source_sha256'] and s['sls_import_version']==sls.VERSION
    assert pd.Series([s['step'] for s in seen]).value_counts().to_dict()=={'Max':80,'Min':80,'Static':80}
    assert {s['case'] for s in seen}=={'S1A','S1C'}
    assert sum(s['raw_fields']['StepType'] is None for s in seen)==80
    assert {s['location_type'] for s in seen}=={'Before','After'}
    assert not frame[['Girder','Stage','Case Name','Station x (m)']].duplicated().any()

def test_blank_static_step_is_sls_only_uls_gate_is_unchanged():
    tables=read_tables(Upload().getvalue(),'native_sls.csv');name,table=next(iter(tables.items()))
    member=split_member_tables(table,sheet_name=name)[0]
    result=prepare_csi_table(member.frame,sheet_name=name)
    assert any('missing StepType' in e for e in result.errors)
    result=prepare_csi_table(member.frame,sheet_name=name,allow_blank_step=True)
    assert not result.errors and len(result.frame)==120

def test_declared_non_si_units_convert_whole_vector_once():
    rows=deepcopy(FIXTURE['rows']);header=rows[1]
    rows[2][header.index('Distance')]='mm'
    for field in ['P','V2','V3']:rows[2][header.index(field)]='N'
    for field in ['T','M2','M3']:rows[2][header.index(field)]='N-mm'
    for row in rows[3:]:
        for field in ['Distance','P','V2','V3']:row[header.index(field)]=float(row[header.index(field)])*1000
        for field in ['T','M2','M3']:row[header.index(field)]=float(row[header.index(field)])*1e6
    converted,errors=sls.parse_files([Upload(rows)]);assert not errors
    pd.testing.assert_frame_equal(converted[['Station x (m)','N','Mx','My','Vy','Vx','T']],imported()[['Station x (m)','N','Mx','My','Vy','Vx','T']],check_exact=False,rtol=1e-12)

def test_invalid_or_duplicate_upload_cannot_mutate_saved_inputs():
    state=seed();sls.replace_stage(state,imported(),stage='Service stage');saved=deepcopy(state[sls.BANK_KEY])
    _,errors=sls.parse_files([Upload(),Upload()]);assert any('duplicate file' in e for e in errors)
    rows=deepcopy(FIXTURE['rows']);rows[3][rows[1].index('T')]='broken'
    _,errors=sls.parse_files([Upload(rows)]);assert errors
    bad=imported();bad=pd.concat([bad,bad.iloc[[0]]],ignore_index=True)
    with pytest.raises(ValueError):sls.replace_stage(state,bad,stage='Service stage')
    pd.testing.assert_frame_equal(state[sls.BANK_KEY],saved)

def test_member_edits_json_legacy_restore_and_uls_isolation():
    state=seed();uls=deepcopy(state['beam_uls_loads_table']);sls.replace_stage(state,imported(),stage='Service stage')
    first,second=sls.members(state[sls.BANK_KEY]);state[sls.TABLE_KEY].loc[state[sls.TABLE_KEY]['Stage']=='Service stage','Mx']=123.456
    sls.activate_member(state,second);assert not state[sls.TABLE_KEY].loc[state[sls.TABLE_KEY]['Stage']=='Service stage','Mx'].eq(123.456).all()
    restored={};apply_project_to_session_state(project_from_json(project_to_json(project_from_session_state(state))),restored)
    assert sls.active_member(restored)==second and len(restored[sls.BANK_KEY])==240
    sls.activate_member(restored,first);assert restored[sls.TABLE_KEY].loc[restored[sls.TABLE_KEY]['Stage']=='Service stage','Mx'].eq(123.456).all()
    pd.testing.assert_frame_equal(pd.DataFrame(state['beam_uls_loads_table']),pd.DataFrame(uls))
    old=project_from_session_state({});apply_project_to_session_state(old,restored)
    assert sls.BANK_KEY not in restored and sls.SELECTION_KEY not in restored
    assert sls.TABLE_KEY not in restored or not any(sls.contract(r) for _,r in pd.DataFrame(restored[sls.TABLE_KEY]).iterrows())

def test_importing_another_stage_retains_service_bank():
    state={};service=imported();sls.replace_stage(state,service,stage='Service stage')
    construction=imported(stage='Construction stage');sls.replace_stage(state,construction,stage='Construction stage')
    assert len(state[sls.BANK_KEY])==480
    actual=state[sls.BANK_KEY].loc[state[sls.BANK_KEY].Stage=='Service stage'].reset_index(drop=True)
    cols=['Girder','Case Name','Station x (m)'];pd.testing.assert_frame_equal(actual.sort_values(cols).reset_index(drop=True),service.sort_values(cols).reset_index(drop=True),check_dtype=False)

def test_total_rows_no_generated_stations_dead_load_or_prestress_duplication():
    state=seed();source=imported();member=sls.members(source)[0]
    row=source.loc[(source.Girder==member)].iloc[(source.loc[source.Girder==member,'Station x (m)']-10).abs().argmin()].to_dict()
    bases=ap.build_girder_service_stress_basis_options(state['section_geometry'],state['section_parameters'],member_type='beam_girder')
    names=list(bases.bases)
    with patch.object(ap.st,'session_state',state):
        assert ap._girder_sls_stage_rows_with_auto_station_grid('Service stage',[row],20)==[row]
        df=ap._girder_full_length_sls_stage_rows(stage_label='Service stage',load_rows=[row],basis_options=bases,basis_names=names,span_length_m=20)
        assert len(df)==1 and df.iloc[0]['N (kN)']==row['N'] and df.iloc[0]['Mx (kN-m)']==row['Mx']
        assert df['Auto Mx (kN-m)'].eq(0).all() and df['Auto Vy (kN)'].eq(0).all() and df['Auto load w (kN/m)'].eq(0).all()
        split=ap._final_service_composite_split_rows(df,bases);assert not split.empty and split['Locked-in Mx (kN-m)'].eq(0).all()
        assert len(ap._make_girder_full_length_sls_figure(df,stage_label='Service stage').data)>0
        inclusive=source.iloc[[0]].copy();s=source_info(inclusive.iloc[0]);s['sls_force_content']='total_with_prestress';inclusive.loc[inclusive.index[0],'Note']='CSP_CSI_SOURCE='+json.dumps(s)
        df2=ap._girder_full_length_sls_stage_rows(stage_label='Service stage',load_rows=inclusive.to_dict('records'),basis_options=bases,basis_names=names,span_length_m=20)
        assert df2['Pe stage (kN)'].eq(0).all() and df2['Top PS (MPa)'].eq(0).all()
        legacy={**row,'Note':'','Mx':25}
        df3=ap._girder_full_length_sls_stage_rows(stage_label='Service stage',load_rows=[legacy],basis_options=bases,basis_names=names,span_length_m=20)
        assert df3['Auto Mx (kN-m)'].max()>0 and df3['Mx (kN-m)'].max()>25

def test_simple_ui_no_confirm_member_switch_and_open_analysis():
    files=[Upload()]
    with patch('streamlit.file_uploader',side_effect=lambda label,*a,**k:files if label==UPLOAD_LABEL else None):
        at=AppTest.from_string(SCRIPT);run(at)
        assert not at.checkbox and not at.text_input and sls.BANK_KEY not in at.session_state
        assert not btn(at).disabled;btn(at).click();run(at)
        assert len(at.session_state[sls.BANK_KEY])==240
        choice=next(x for x in at.selectbox if x.label=='SLS girder');second=choice.options[1];choice.set_value(second);run(at)
        assert sls.active_member(at.session_state.filtered_state)==second
        saved=deepcopy(at.session_state[sls.BANK_KEY]);btn(at,'Open SLS analysis').click();run(at)
        assert at.session_state['_nav_active_workspace']=='Analysis' and at.session_state['_igird_sls23_review_stage']=='Service stage'
        at.radio[0].set_value('Analysis');run(at);at.radio[0].set_value('Loads');run(at)
        pd.testing.assert_frame_equal(at.session_state[sls.BANK_KEY],saved)
        assert not at.checkbox and not at.text_input

def test_ui_invalid_data_and_noncanonical_app_units_disable_import():
    rows=deepcopy(FIXTURE['rows']);rows[3][rows[1].index('P')]='bad'
    with patch('streamlit.file_uploader',return_value=[Upload(rows)]):
        at=AppTest.from_string(SCRIPT);run(at);assert btn(at).disabled and at.error and sls.BANK_KEY not in at.session_state
    with patch('streamlit.file_uploader',return_value=[Upload()]):
        at=AppTest.from_string(SCRIPT.replace('render_import()','render_import(force_unit="N")'));run(at)
        assert btn(at).disabled and at.error and not at.checkbox and sls.BANK_KEY not in at.session_state
