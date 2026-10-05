from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io.girder_load_bank import *
def test_ui_two_files_two_members_each_replace_add_switch():
    script='''
import streamlit as st
import pandas as pd
from io import BytesIO
from concrete_pmm_pro.ui.girder_csi_import import render_import, render_member_collection
class Upload:
    def __init__(self,name,case):
        self.name=name
        b=BytesIO()
        with pd.ExcelWriter(b,engine='openpyxl') as writer:
            for member in ('Left Girder','Interior Girder'):
                pd.DataFrame([{'Girder Distance':x,'StepType':'Static','OutputCase':case,'P':-5,'V2':10+x,'V3':2,'T':3,'M2':4,'M3':100*x} for x in (0,10,20)]).to_excel(writer,sheet_name=member,index=False)
        self.payload=b.getvalue()
    def getvalue(self):return self.payload
if 'qa_files' not in st.session_state:
    st.session_state['qa_files']=[Upload('ULS1.xlsx','ULS1'),Upload('ULS2.xlsx','ULS2')]
files=st.session_state['qa_files']
st.file_uploader=lambda *a,**kw:files
render_import(state_key='beam_uls_loads_table',editor_key='beam_uls_loads_editor',key_prefix='qa',force_unit='kN',moment_unit='kN-m')
render_member_collection(state_key='beam_uls_loads_table',editor_key='beam_uls_loads_editor',key_prefix='qa')
'''
    at=AppTest.from_string(script).run()
    assert not at.exception
    assert len(at.multiselect)==2
    assert all(len(m.value)==2 for m in at.multiselect)
    for c in at.checkbox:c.set_value(True)
    at.run()
    next(b for b in at.button if b.label=='Replace entire girder collection').click().run()
    assert not at.exception
    assert len(at.session_state[BANK_KEY])==12
    assert len(at.session_state['beam_uls_loads_table'])==6
    next(s for s in at.selectbox if s.label=='Girder to design').set_value('Interior Girder')
    next(b for b in at.button if b.label.startswith('Use this girder')).click().run()
    assert not at.exception
    assert at.session_state[ACTIVE_KEY]=='Interior Girder'
    assert at.session_state['beam_uls_loads_table']['Case Name'].str.contains('Interior Girder').all()
    assert next(b for b in at.button if b.label=='Add tables to girder collection').disabled
    new_file = at.session_state['qa_files'][0]
    from io import BytesIO
    import pandas as pd
    b=BytesIO()
    with pd.ExcelWriter(b,engine='openpyxl') as writer:
        for member in ('Left Girder','Interior Girder'):
            pd.DataFrame([{'Girder Distance':x,'StepType':'Static','OutputCase':'ULS3','P':-7,'V2':20+x,'V3':2,'T':3,'M2':4,'M3':200*x} for x in (0,10,20)]).to_excel(writer,sheet_name=member,index=False)
    new_file.payload=b.getvalue()
    new_file.name='ULS3.xlsx'
    at.session_state['qa_files']=[new_file]
    at.run()
    next(b for b in at.button if b.label=='Add tables to girder collection').click().run()
    assert not at.exception
    assert len(at.session_state[BANK_KEY])==18
    assert len(at.session_state['beam_uls_loads_table'])==9
    next(b for b in at.button if b.label=='Replace entire girder collection').click().run()
    assert not at.exception
    assert len(at.session_state[BANK_KEY])==6
    assert len(at.session_state['beam_uls_loads_table'])==3


test_ui_two_files_two_members_each_replace_add_switch()
print("UI acceptance passed: 2 files, 2 members, all cases, replace/switch/duplicate guard")
