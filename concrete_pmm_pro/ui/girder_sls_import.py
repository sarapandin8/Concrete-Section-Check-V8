"""Simple SLS import UI: upload, import, select girder, open analysis."""
import pandas as pd
import streamlit as st
from concrete_pmm_pro.io.girder_sls_import import (
    BANK_KEY,STAGES,FORCE_CONTENTS,parse_files,members,active_member,
    activate_member,replace_stage,
)
UPLOAD_LABEL = 'Upload CSiBridge SLS girder forces'

def _sync():
    from concrete_pmm_pro.ui.loads_page import _sync_workflow_load_tables_metadata
    _sync_workflow_load_tables_metadata()

def _open_analysis(stage):
    st.session_state['_nav_active_workspace'] = 'Analysis'
    st.session_state['_nav_analysis_subpage'] = 'SLS / Stress & Cracking'
    bank = pd.DataFrame(st.session_state.get(BANK_KEY,[]))
    choices = list(bank['Stage'].unique()) if 'Stage' in bank else []
    st.session_state['_igird_sls23_review_stage'] = stage if stage in choices else (choices[0] if choices else stage)

def render_member_collection(*, key_prefix='loads', show_open=False, stage='Service stage'):
    bank = pd.DataFrame(st.session_state.get(BANK_KEY,[]))
    choices = members(bank)
    if not choices:
        return
    current = active_member(st.session_state)
    key = f'{key_prefix}_sls_girder'
    if st.session_state.get(key) != current:
        st.session_state[key] = current
    def change():
        activate_member(st.session_state,st.session_state[key])
        _sync()
    st.selectbox('SLS girder',choices,key=key,on_change=change)
    st.caption('SLS collection is separate from ULS. Analysis uses the selected SLS girder and load case.')
    if show_open:
        st.dataframe(bank.groupby(['Girder','Stage'],sort=False).size().rename('Rows').reset_index(),hide_index=True,width='stretch')
        st.button('Open SLS analysis',key='sls23_open_analysis',on_click=_open_analysis,args=(stage,),type='primary')

def render_import(*, force_unit='kN', moment_unit='kN-m'):
    st.markdown('#### Import SLS loads')
    st.caption('Upload Bridge Object Girder Forces from CSiBridge, then press Import SLS loads. Each source row stays in its own case and station.')
    if BANK_KEY in st.session_state and st.session_state.get('_igird_sls23_import_receipt'):
        st.success(st.session_state['_igird_sls23_import_receipt'])
    files = st.file_uploader(UPLOAD_LABEL,type=['xlsx','csv'],accept_multiple_files=True,key='igird_sls23_files')
    stage, content = STAGES[0], 'total_external'
    with st.expander('More SLS import options',expanded=False):
        stage = st.selectbox('SLS stage',STAGES,key='igird_sls23_import_stage')
        content = st.selectbox('Load content',list(FORCE_CONTENTS),format_func=FORCE_CONTENTS.get,key='igird_sls23_force_content')
        st.caption('Change load content only if this export contains prestress already, or contains LL+IM only. This setting describes included actions.')
    st.caption('Default: Service stage · Total external SLS loads · App adds effective prestress. Imported total loads receive no additional automatic DL/SDL.')
    if files:
        frame, errors = parse_files(files,stage=stage,force_content=content)
        supported = force_unit == 'kN' and moment_unit == 'kN-m'
        if not supported:
            errors.append('Set Loads units to kN and kN-m before importing the normalized CSI SLS vectors.')
        for error in errors:
            st.error(error)
        if not errors:
            st.info(f'Ready: {len(frame)} source rows · {len(members(frame))} girders · {stage}')
        if st.button('Import SLS loads',type='primary',disabled=bool(errors) or frame.empty,key='igird_sls23_import'):
            replace_stage(st.session_state,frame,stage=stage)
            _sync()
            st.session_state['_igird_sls23_import_receipt'] = f'Imported {len(frame)} SLS source rows for {len(members(frame))} girders. Select the SLS girder, then open analysis.'
            st.rerun()
        with st.expander('SLS force preview',expanded=False):
            st.dataframe(frame.drop(columns=['Note']),hide_index=True,width='stretch')
            st.caption('Mapping: N = -P (compression positive), Mx = M3, My = M2, Vy = V2, Vx = V3, T = T. Raw CSI signs, units, case, cut, and source row remain in Note.')
    render_member_collection(show_open=True,stage=stage)
