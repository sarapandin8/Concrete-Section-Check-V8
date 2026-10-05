from streamlit.testing.v1 import AppTest
import json

script='''
import sys
sys.path.insert(0, 'tests')
import streamlit as st
from test_igird_membercharts3 import model
from test_igird_uls6_torsion_general_procedure import _route
from concrete_pmm_pro.io.girder_load_bank import activate_member
from concrete_pmm_pro.ui import igird_member_results as mr
if 'qa_initialized' not in st.session_state:
    st.session_state.update(model())
    activate_member(st.session_state, 'Exterior Girder')
    st.session_state['qa_initialized']=True
    st.session_state['qa_calls']=0
if not hasattr(mr, '_qa_original'):
    mr._qa_original=mr.calculate_member

def counted(*args,**kwargs):
    st.session_state['qa_calls']+=1
    return mr._qa_original(*args,**kwargs)
mr.calculate_member=counted
check=st.radio('QA check', ['Flexure','Shear','Torsion','Shear + Torsion'],key='qa_check')
mr.render_collection(check_name=check,route=_route(),code_label='AASHTO LRFD 9th Edition')
'''
at=AppTest.from_string(script,default_timeout=60).run()
assert not at.exception
assert at.session_state['qa_calls']==0
for check in ['Flexure','Shear','Torsion','Shear + Torsion']:
    at.radio(key='qa_check').set_value(check).run()
    assert not at.exception
    next(b for b in at.button if b.label.startswith('Calculate '+check+' — all')).click().run()
    assert not at.exception,[e.message for e in at.exception]
    plots=at.get('plotly_chart')
    assert len(plots)>=2
    titles=[json.loads(p.proto.spec)['layout']['title']['text'] for p in plots]
    assert any('Girder: Exterior Girder' in t for t in titles),titles
    assert any('Girder: Interior Girder 2' in t for t in titles),titles
    calls=at.session_state['qa_calls']
    at.run()
    assert not at.exception
    assert at.session_state['qa_calls']==calls
    if check in {'Shear','Torsion'}:
        views=[r for r in at.radio if r.label=='Chart view']
        assert len(views)==2
        for r in views:r.set_value('Selected case — demand / capacity')
        at.run()
        assert not at.exception
        assert len(at.selectbox)==2
        assert at.session_state['qa_calls']==calls
calls=at.session_state['qa_calls']
bank=at.session_state['igird_uls_member_bank'].copy()
bank.loc[bank['Girder'].eq('Interior Girder 2'),'Mux']=999
at.session_state['igird_uls_member_bank']=bank
at.run()
assert not at.exception
assert at.session_state['qa_calls']==calls
assert any('STALE' in w.value and 'Interior Girder 2' in w.value for w in at.warning)
assert all('Interior Girder 2' not in json.loads(p.proto.spec)['layout']['title']['text'] for p in at.get('plotly_chart'))
print('AppTest passed: all four checks, two named girder graphs each, separate case selectors, no solver calls on redraw.')
