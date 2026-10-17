"""Regression: commit a second cell, cumulative row edits and model replacement."""
from copy import deepcopy
import json

import pandas as pd
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis.igird_dowel_joint import DIMENSIONS
from concrete_pmm_pro.io.project_io import (
    apply_project_to_session_state, project_from_json, project_from_session_state, project_to_json,
)
from test_igird_dowel32 import SCRIPT
from test_igird_uls4_interface_integration import _state


def editor(app,prefix):
    return next(row for row in app.dataframe if str(row.key).startswith(prefix))


def commit(app,node,*,row,column,value):
    edits=deepcopy(app.session_state[node.key])
    edits['edited_rows'].setdefault(row,{})[column]=value
    app.session_state[node.key]=edits
    app.run();assert not app.exception,[e.message for e in app.exception]


def test_second_and_later_dimension_commits_keep_values_key_and_live_labels():
    app=AppTest.from_string(SCRIPT,default_timeout=60).run()
    node=editor(app,'igird_detail35_dimensions_');key=node.key
    names=['row_spacing_mm','hook_tail_mm','hook_top_depth_mm','girder_ld_available_mm']
    expected={k:None for k in names}
    for row,value in [(0,120.),(1,200.),(2,170.),(3,900.),(1,None),(1,200.)]:
        commit(app,node,row=row,column='Value mm',value=value)
        expected[names[row]]=value
        assert editor(app,'igird_detail35_dimensions_').key==key
        cfg=app.session_state['cfg']['dowel_connection']
        assert {k:cfg[k] for k in names}==expected
        assert cfg['slab_ldh_available_mm']==(350-expected['hook_top_depth_mm'] if expected['hook_top_depth_mm'] is not None else None)
        label='Not entered' if value is None else f'{value:g} mm'
        assert label in next(m.value for m in app.markdown if 'data-dowel-guide=' in m.value)
    snapshot=deepcopy(app.session_state['cfg'])
    app.run();assert not app.exception and app.session_state['cfg']==snapshot


LAYOUT='''
import json,pandas as pd,streamlit as st
from concrete_pmm_pro.ui.igird_interface_connectors import render_source
from concrete_pmm_pro.analysis.igird_interface_connectors import INDEPENDENT_DOWELS
def zone(name,a,b,s):return {'Zone':name,'x_start_m':a,'x_end_m':b,'Diameter_mm':12.,'Legs':2.,'Spacing_mm':s,'fy_MPa':390.}
if 'cfg' not in st.session_state:
    st.session_state['cfg']={'connector_source':INDEPENDENT_DOWELS,'dowel_zones':[zone('A',0.,5.,70.),zone('B',5.,20.,150.)]}
st.session_state['cfg'].update(render_source(st.session_state['cfg'],pd.DataFrame([zone('Girder',0.,20.,99.)])))
'''


def test_dynamic_layout_changes_addition_and_deletion_are_applied_once():
    app=AppTest.from_string(LAYOUT,default_timeout=60).run()
    node=editor(app,'igird_interface_dowel_layout_');key=node.key
    commit(app,node,row=0,column='Spacing_mm',value=80.)
    commit(app,node,row=1,column='Spacing_mm',value=160.)
    assert editor(app,'igird_interface_dowel_layout_').key==key
    state=deepcopy(app.session_state[key])
    state['added_rows']=[{'Zone':'C','x_start_m':20.,'x_end_m':25.,'Diameter_mm':12.,'Legs':2.,'Spacing_mm':220.,'fy_MPa':390.}]
    app.session_state[key]=state;app.run();assert not app.exception
    assert len(app.session_state['cfg']['dowel_zones'])==3
    state=deepcopy(app.session_state[key]);state['added_rows'][0]['Spacing_mm']=230.;state['deleted_rows']=[0]
    app.session_state[key]=state;app.run();assert not app.exception
    rows=app.session_state['cfg']['dowel_zones']
    assert [r['Zone'] for r in rows]==['B','C']
    assert [r['Spacing_mm'] for r in rows]==[160.,230.]
    assert editor(app,'igird_interface_dowel_layout_').key==key
    # AppTest drops unsupported editor widget payloads on a bare rerun, just
    # as leaving the UI removes a widget. Re-entry must seed accepted inputs.
    app.run();assert not app.exception and app.session_state['cfg']['dowel_zones']==rows


def test_copy_zoning_rebases_editor_and_discards_old_cell_deltas():
    app=AppTest.from_string(LAYOUT,default_timeout=60).run()
    node=editor(app,'igird_interface_dowel_layout_')
    commit(app,node,row=0,column='Spacing_mm',value=88.)
    next(b for b in app.button if b.label=='Copy current girder zoning into separate dowel layout').click().run()
    assert not app.exception
    rows=app.session_state['cfg']['dowel_zones']
    assert len(rows)==1 and rows[0]['Zone']=='Dowel / Girder' and rows[0]['Spacing_mm']==99.
    assert editor(app,'igird_interface_dowel_layout_').key!=node.key
    app.run();assert not app.exception and app.session_state['cfg']['dowel_zones']==rows


def test_external_dimensions_replace_old_edits_instead_of_reapplying_them():
    app=AppTest.from_string(SCRIPT,default_timeout=60).run()
    node=editor(app,'igird_detail35_dimensions_');commit(app,node,row=0,column='Value mm',value=120.)
    cfg=deepcopy(app.session_state['cfg']);cfg['dowel_connection']['row_spacing_mm']=90.
    app.session_state['cfg']=cfg;app.run();assert not app.exception
    assert app.session_state['cfg']['dowel_connection']['row_spacing_mm']==90.
    assert editor(app,'igird_detail35_dimensions_').key!=node.key


def test_hiding_and_reopening_input_controls_reuses_accepted_values():
    script=SCRIPT.split("st.session_state['cfg'].update",1)[0]+'''
if st.toggle('Show controls',value=True,key='show_controls'):
    st.session_state['cfg'].update(render_settings(st.session_state['cfg'],
        section_params={'Tslab_mm':350,'D1_mm':1500,'deck_long_rebar_top_cover_mm':50}))
'''
    app=AppTest.from_string(script,default_timeout=60).run()
    node=editor(app,'igird_detail35_dimensions_')
    commit(app,node,row=0,column='Value mm',value=120.)
    commit(app,node,row=1,column='Value mm',value=180.)
    saved=deepcopy(app.session_state['cfg'])
    app.toggle(key='show_controls').set_value(False).run()
    assert not app.exception
    app.toggle(key='show_controls').set_value(True).run()
    assert not app.exception and app.session_state['cfg']==saved


def test_load_json_clears_editor_state_and_does_not_persist_it():
    state=_state()
    before=project_to_json(project_from_session_state(state))
    ui={'igird_edit33_editor_input30_dimensions_':{'base':pd.DataFrame([{'Value mm':999.}]),
        'accepted':'UI-ONLY-SENTINEL','widget_key':'input30_dimensions_edit33_1'},
        'input30_dimensions_edit33_1':{'edited_rows':{0:{'Value mm':999.}}},
        'joint29_actions_edit33_1':{'edited_rows':{0:{'Source':'UI-ONLY-SENTINEL'}}},
        'igird_interface_dowel_layout_edit33_1':{'edited_rows':{}},
        'igird_edit33_dowel_detail':True}
    state.update(ui)
    after=project_to_json(project_from_session_state(state))
    assert json.loads(before)==json.loads(after) and 'UI-ONLY-SENTINEL' not in after
    restored=deepcopy(ui)
    apply_project_to_session_state(project_from_json(after),restored)
    assert not any(key in restored for key in ui)
    assert json.loads(project_to_json(project_from_session_state(restored)))['loads']==json.loads(before)['loads']
