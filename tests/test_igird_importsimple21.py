"""Simple import: one source choice + explicit import, no mandatory free text."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
try:
    from streamlit.testing.v1 import AppTest
except (ImportError, TypeError):
    AppTest = None
from concrete_pmm_pro.ui.girder_csi_import import UPLOAD_LABEL,_source_declaration,_native_preview,saved_source_readiness
from concrete_pmm_pro.io.girder_csi_import import source_info
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
FILE=Path(__file__).resolve().parents[1]/'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx'
class Upload(BytesIO):
    def __init__(self,data=None,name='native.xlsx'):super().__init__(FILE.read_bytes() if data is None else data);self.name=name
SCRIPT='''
import streamlit as st
from concrete_pmm_pro.ui.girder_csi_import import render_import
page=st.radio('Page',['Loads','Analysis'])
if page=='Loads':
 render_import(state_key='beam_uls_loads_table',editor_key='ed',key_prefix='qa',force_unit='kN',moment_unit='kN-m')
'''
def run(at):
    at.run(timeout=30);assert not at.exception,[e.message for e in at.exception]
def kind(at):return pd.DataFrame(at.session_state[BANK_KEY]).apply(lambda r:source_info(r)['kind'],axis=1)
def source(at):return next(x for x in at.radio if x.label=='Force source')
def button(at):return next(x for x in at.button if x.label=='Import loads')
def uploader(files):return lambda label,*a,**k:files if label==UPLOAD_LABEL else None
@pytest.mark.parametrize('mode',['correspondence','static','unverified'])
def test_declaration_records_source_choice(mode):
    returned,confirmed,basis=_source_declaration(mode)
    assert returned==mode and confirmed==(mode!='unverified')
    assert ('Engineer declaration' in basis) if confirmed else basis==''
@pytest.mark.skipif(AppTest is None, reason='Run with real Streamlit preloaded for UI verification')
def test_correspondence_simple_path_and_navigation():
    files=[Upload()]
    with patch('streamlit.file_uploader',side_effect=uploader(files)):
        at=AppTest.from_string(SCRIPT);run(at)
        assert BANK_KEY not in at.session_state
        assert not at.text_input
        assert [x.label for x in at.checkbox]==['Advanced import settings']
        assert source(at).value=='Envelope / unverified'
        source(at).set_value('CSI Correspondence');run(at)
        assert BANK_KEY not in at.session_state # dropdown never commits
        assert not button(at).disabled
        button(at).click();run(at)
        assert kind(at).eq('CONCURRENT').all() and len(kind(at))==640
        saved=deepcopy(at.session_state[BANK_KEY])
        assert all('Engineer declaration' in source_info(r)['evidence'] for _,r in saved.iterrows())
        source(at).set_value('Envelope / unverified');run(at)
        pd.testing.assert_frame_equal(at.session_state[BANK_KEY],saved)
        source(at).set_value('CSI Correspondence');run(at)
        at.radio[0].set_value('Analysis');run(at)
        at.radio[0].set_value('Loads');run(at)
        assert source(at).value=='CSI Correspondence' and kind(at).eq('CONCURRENT').all()
        next(x for x in at.checkbox if x.label=='Advanced import settings').check();run(at)
        assert not any(x.label.startswith(('I confirm','All tables')) for x in at.checkbox)
        assert not any('Source basis' in x.label for x in at.text_input)
        next(x for x in at.checkbox if x.label=='Advanced import settings').uncheck();run(at)
        assert kind(at).eq('CONCURRENT').all()
        pd.testing.assert_frame_equal(at.session_state[BANK_KEY],saved)
@pytest.mark.skipif(AppTest is None, reason='Run with real Streamlit preloaded for UI verification')
def test_envelope_import_still_blocked():
    with patch('streamlit.file_uploader',side_effect=uploader([Upload()])):
        at=AppTest.from_string(SCRIPT);run(at);button(at).click();run(at)
        assert kind(at).eq('ENVELOPE').all()
        readiness=saved_source_readiness(at.session_state[BANK_KEY])
        assert readiness['Source-blocked rows'].sum()==640
        assert readiness['Concurrent rows ready for V+T'].sum()==0
@pytest.mark.skipif(AppTest is None, reason='Run with real Streamlit preloaded for UI verification')
def test_new_file_bytes_do_not_inherit_choice_or_silently_replace():
    files=[Upload()]
    with patch('streamlit.file_uploader',side_effect=uploader(files)):
        at=AppTest.from_string(SCRIPT);run(at);source(at).set_value('CSI Correspondence');run(at);button(at).click();run(at)
        saved=deepcopy(at.session_state[BANK_KEY])
        files[0]=Upload(FILE.read_bytes()+b'new revision')
        run(at)
        assert source(at).value=='Envelope / unverified'
        pd.testing.assert_frame_equal(at.session_state[BANK_KEY],saved)
def test_static_max_min_does_not_promote_to_concurrent():
    mode,confirmed,evidence=_source_declaration('static')
    frame,issues=_native_preview([Upload()],source_mode=mode,concurrency_confirmed=confirmed,evidence=evidence)
    assert not issues
    assert frame.apply(lambda r:source_info(r)['kind'],axis=1).eq('ENVELOPE').all()
@pytest.mark.skipif(AppTest is None, reason='Run with real Streamlit preloaded for UI verification')
def test_unsupported_units_disable_import_without_touching_saved_loads():
    with patch('streamlit.file_uploader',side_effect=uploader([Upload()])):
        at=AppTest.from_string(SCRIPT.replace("force_unit='kN'","force_unit='N'"));run(at)
        assert button(at).disabled and BANK_KEY not in at.session_state
        assert at.error
