"""Input30: real import path, source identity, roundtrip and uncluttered UI."""
from copy import deepcopy
from io import BytesIO
import json
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.io import csi_component_sources as components
from concrete_pmm_pro.io.girder_csi_import import source_info
from concrete_pmm_pro.io.project_io import project_from_json, project_to_json, project_from_session_state, apply_project_to_session_state
from concrete_pmm_pro.ui import girder_csi_import as importer
from concrete_pmm_pro.ui import analysis_page as ap
from concrete_pmm_pro.ui.igird_composite_inputs import effective_config, input_plan
from concrete_pmm_pro.analysis import igird_dowel_joint as joint
from test_igird_equilibrium27 import tables
from test_igird_dowel28 import settings, zone
from test_igird_joint29 import cfg, action
from test_igird_uls4_interface_integration import _state


class File:
    def __init__(self, payload, name="components.xlsx"):
        self.payload, self.name = payload, name

    def getvalue(self):
        return self.payload


def workbook(data):
    out=BytesIO()
    with pd.ExcelWriter(out,engine="openpyxl") as writer:
        for name, frame in data.items():frame.to_excel(writer,sheet_name=name,index=False)
    return out.getvalue()


def capture(data=None, **contract):
    payload=workbook(data if data is not None else tables())
    return components.capture(payload,"components.xlsx",source_mode="static",
        concurrency_confirmed=True,evidence="Known static fixture",**contract)


def test_named_girder_sheets_use_the_normal_import_and_preserve_all_six_actions():
    data=tables();data['Entire Bridge Section']=data['Interior Girder 1'].copy()
    file=File(workbook(data))
    frame, errors=importer._native_preview([file],source_mode="static",concurrency_confirmed=True,evidence="static")
    assert not errors and len(frame)==9 and set(frame.Girder)=={'Interior Girder 1'}
    original=data['Interior Girder 1'].iloc[1:]
    for csi, app in {'P':'Nu','V2':'Vuy','V3':'Vux','T':'Tu','M2':'Muy','M3':'Mux'}.items():
        assert frame[app].tolist()==pytest.approx(original[csi].astype(float).tolist())
    assert all(source_info(row)['sheet']=='Interior Girder 1' for row in frame.to_dict('records'))


def test_ambiguous_sheet_name_stays_in_the_explicit_mapping_route():
    data={'Unidentified section':tables()['Interior Girder 1']}
    assert importer._native_preview([File(workbook(data))]) is None


def test_a_bad_girder_sheet_blocks_the_atomic_load_import():
    data=tables();data['Interior Girder 1'].loc[1,'P']='missing force'
    frame,errors=importer._native_preview([File(workbook(data))])
    assert errors
    assert any('fill distance and all six' in error for error in errors)


def test_a_recognized_girder_sheet_with_a_broken_header_cannot_silently_disappear():
    data=tables();data['Interior Girder 2']=data['Interior Girder 1'].drop(columns=['P'])
    frame,errors=importer._native_preview([File(workbook(data))])
    assert errors and any('Interior Girder 2' in message and 'headers' in message for message in errors)


def test_a_broken_component_header_leaves_the_component_collection_incomplete():
    data=tables();data['Interior Beam 1']=data['Interior Beam 1'].drop(columns=['P'])
    source=capture(data)
    assert source['records']==[] and source['errors']


def test_all_component_inputs_keep_raw_fields_and_units_without_fitted_origins():
    source=capture();assert not source['errors'] and len(source['records'])==27
    assert {row['component'] for row in source['records']}=={'girder','beam','slab'}
    beam=next(row for row in source['records'] if row['component']=='beam')
    info=source_info(beam)
    assert info['raw_fields']['P']==20 and info['units']['P']=='kN'
    assert beam['Nu']==20 and info['source_sha256']==source['sha256']
    assert not any('offset' in k.casefold() or 'resistance' in k.casefold() for k in source)
    serialized=json.dumps(source,allow_nan=False)
    assert 'Capacity factor' not in serialized and 'C_component-C_G' not in serialized


def test_bad_component_units_never_create_a_partial_component_collection():
    data=tables();data['Interior Beam 1'].loc[0,'T']='unknown'
    source=capture(data)
    assert source['errors'] and source['records']==[]
    assert components.overview(components.collection([source]))[0]['Input state']=='Source incomplete'


def test_girder_only_files_need_no_component_inputs():
    source=capture({'Interior Girder 1':tables()['Interior Girder 1']})
    assert source['records']==[] and not source['errors']
    assert components.collection([source])['sources']==[]


def test_component_envelopes_stay_unpaired_despite_correspondence_declaration():
    source=components.capture(workbook(tables(envelope=True)),"U2A.xlsx",source_mode='correspondence',
        concurrency_confirmed=True,evidence='Girder row declaration only')
    view=components.overview(components.collection([source]))
    assert len(view)==1 and view[0]['Complete components']
    assert view[0]['Input state']=='State pairing required'


def test_matching_active_source_requires_the_exact_file_bytes_and_copy_is_independent():
    source=capture();bundle=components.collection([source,source])
    active=pd.DataFrame(source['records'])
    row=components.overview(bundle,active_loads=active)[0]
    assert row['Matches active Loads file'] and row['Input state']=='Single-state source'
    source['records'][0]['Nu']=123456
    assert bundle['sources'][0]['records'][0]['Nu']!=123456
    other=capture(tables(case='SDL'))
    assert not components.overview(bundle,active_loads=other['records'])[0]['Matches active Loads file']


def test_the_latest_explicit_contract_replaces_the_same_file_input_without_duplicate_rows():
    source=capture();updated=deepcopy(source)
    updated['errors']=['Latest read invalid; no old source may be substituted'];updated['records']=[]
    out=components.collection([source,updated])
    assert len(out['sources'])==1 and out['sources'][0]['records']==[]
    assert components.overview(out)[0]['Input state']=='Source incomplete'


def test_malformed_old_source_schema_does_not_claim_available_components():
    assert components.saved({'project_metadata':{components.KEY:{'version':'old','sources':[{'bad':True}]}}})['sources']==[]


def test_existing_cover_is_reused_and_missing_actual_bar_geometry_is_never_guessed():
    original={joint.KEY:cfg(**{key:None for key in joint.DIMENSIONS})}
    before=deepcopy(original)
    out=effective_config(original,{'Tslab_mm':350,'D1_mm':1500,'deck_long_rebar_top_cover_mm':50})
    assert out['cover_required_mm']==50 and original==before
    assert all(out[k] is None for k in joint.DIMENSIONS if k!='cover_required_mm')
    original[joint.KEY]['cover_required_mm']=60
    assert effective_config(original,{'deck_long_rebar_top_cover_mm':50})['cover_required_mm']==60


def test_complete_input_presence_never_becomes_composite_design_acceptance():
    conf=settings([zone()]);conf[joint.KEY]=cfg(action_rows=[action()])
    plan=input_plan(conf,params={'D1_mm':1500,'B1_mm':600,'T2_mm':200,'Be_mm':1200,'Tslab_mm':350})
    assert not plan['missing'] and plan['design_status']=='REVIEW'
    assert plan['reused'][0]['Value']=='1500 / 600 / 200 mm'
    assert not any('Tn' in key or 'capacity' in key for key in plan)


def test_unknown_zones_and_joint_forces_are_reported_as_missing_not_zero():
    conf=settings([zone(x_start_m=None,x_end_m=None)]);conf[joint.KEY]=cfg(action_rows=[])
    plan=input_plan(conf,params={})
    assert any('start / end' in row['Input'] for row in plan['missing'])
    assert any(row['Step']=='Recover interface force state' for row in plan['pending'])
    assert not any(row['Input']=='Joint force state' for row in plan['missing'])
    assert conf[joint.KEY]['action_rows']==[]


def test_manual_joint_force_editor_is_not_created_in_the_default_view_and_inputs_survive_reruns():
    conf=settings();conf[joint.KEY]=cfg(action_rows=[action(mx_kNm_per_m=None)])
    script="""
import streamlit as st
from concrete_pmm_pro.ui.igird_dowel_joint import render_settings
if 'cfg' not in st.session_state: st.session_state['cfg']=CONF
out=render_settings(st.session_state['cfg'],section_params={'Tslab_mm':350,'deck_long_rebar_top_cover_mm':50})
st.session_state['cfg'].update(out)
""".replace('CONF',repr(conf))
    app=AppTest.from_string(script,default_timeout=60).run()
    assert not app.exception and not app.checkbox
    assert not any('joint29_actions_' in str(node.key) for node in app.dataframe)
    saved=deepcopy(app.session_state['cfg'])
    assert saved[joint.KEY]['action_rows'][0]['mx_kNm_per_m'] is None
    app.run();assert not app.exception and app.session_state['cfg']==saved
    next(toggle for toggle in app.toggle if toggle.label=='Edit joint forces manually').set_value(True).run()
    assert not app.exception
    assert any('joint29_actions_' in str(node.key) for node in app.dataframe)


def test_captured_component_inputs_roundtrip_but_solver_witnesses_do_not():
    state=_state();state['project_metadata']={components.KEY:components.collection([capture()])}
    state['igird_joint29_mechanism_review']={'sentinel':'DO NOT SAVE SOLVER RESULT'}
    original=deepcopy(state['project_metadata'][components.KEY])
    payload=project_to_json(project_from_session_state(state))
    assert 'DO NOT SAVE SOLVER RESULT' not in payload
    restored={};apply_project_to_session_state(project_from_json(payload),restored)
    assert components.saved(restored)==original


def test_reimport_replaces_component_inputs_and_append_retains_distinct_sources():
    file=File(workbook(tables()))
    frame,errors=importer._native_preview([file],source_mode='static',concurrency_confirmed=True,evidence='static')
    assert not errors
    old=capture(tables(case='OLD'))
    state={'project_metadata':{components.KEY:components.collection([old])}}
    before=deepcopy(frame)
    with patch.object(importer.st,'session_state',state):
        replace=importer._capture_component_inputs([file],frame,append=False)
        appended=importer._capture_component_inputs([file],frame,append=True)
    assert len(replace['sources'])==1 and len(appended['sources'])==2
    assert replace['sources'][0]['sha256']!=old['sha256']
    pd.testing.assert_frame_equal(frame,before)


def test_replacing_with_a_girder_only_file_clears_previous_component_inputs():
    file=File(workbook({'Interior Girder 1':tables()['Interior Girder 1']}),'girder_only.xlsx')
    frame,errors=importer._native_preview([file]);assert not errors
    state={'project_metadata':{components.KEY:components.collection([capture()])}}
    with patch.object(importer.st,'session_state',state):
        out=importer._capture_component_inputs([file],frame,append=False)
    assert out['sources']==[]


def test_component_input_changes_hide_stale_joint_results_without_running_a_solver():
    conf=settings();conf[joint.KEY]=cfg()
    script="""
import streamlit as st
from concrete_pmm_pro.ui.igird_dowel_joint import render_analysis
def calculate():
    st.session_state['runs']=st.session_state.get('runs',0)+1
    return {'requirements':[],'missing_actions':True,'rows':[],'traces':[]}
render_analysis(CONF,fingerprint='same Girder loads',calculate=calculate,state=st.session_state)
""".replace('CONF',repr(conf))
    app=AppTest.from_string(script,default_timeout=60).run()
    app.button[0].click().run();assert app.session_state['runs']==1
    app.session_state['project_metadata']={components.KEY:components.collection([capture()])}
    app.run()
    assert not app.exception and app.session_state['runs']==1
    assert any('not calculated' in element.value for element in app.info)
