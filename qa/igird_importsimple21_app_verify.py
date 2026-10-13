"""Full app.py: upload -> force source -> import, no mandatory text/checkbox."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from streamlit.testing.v1 import AppTest
import pandas as pd
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json,project_to_json,project_from_session_state
from concrete_pmm_pro.io.girder_csi_import import source_info
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
from concrete_pmm_pro.ui.girder_csi_import import UPLOAD_LABEL
from concrete_pmm_pro.ui.igird_member_results import member_inputs
from concrete_pmm_pro.ui.igird_combined_vt import concurrent_source_allowed
state={}
apply_project_to_session_state(project_from_json(Path('qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()),state)
state['_nav_active_workspace']='Loads'
class Upload(BytesIO):
 def __init__(self):
  super().__init__((ROOT/'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx').read_bytes());self.name='native.xlsx'
def upload(label,*args,**kwargs):return [Upload()] if label==UPLOAD_LABEL else ([] if kwargs.get('accept_multiple_files') else None)
at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60)
for k,v in state.items():at.session_state[k]=deepcopy(v)
def run():at.run(timeout=60);assert not at.exception,[e.message for e in at.exception]
def count():
 bank=pd.DataFrame(at.session_state[BANK_KEY]);assert len(bank)==640
 return int(bank.apply(lambda r:concurrent_source_allowed(source_info(r)),axis=1).sum())
def canonical(frame):
 frame=frame.copy()
 for key in ['Station x (m)','Mux','Nu','Vuy','Tu','Muy','Vux']:
  frame[key]=pd.to_numeric(frame[key]).astype(float)
 return frame.sort_values(['Girder','Case Name','Station x (m)']).reset_index(drop=True)
with patch('streamlit.file_uploader',side_effect=upload):
 run()
 assert not any(x.label.startswith(('I confirm each','All tables','I confirm member')) for x in at.checkbox)
 assert not any('Source basis' in x.label for x in at.text_input)
 assert not any(x.label=='Replace entire girder collection' for x in at.button)
 next(x for x in at.radio if x.label=='Force source').set_value('CSI Correspondence');run()
 button=next(x for x in at.button if x.label=='Import loads');assert not button.disabled
 button.click();run();assert count()==640
 bank=pd.DataFrame(at.session_state[BANK_KEY]).copy(deep=True)
 at.session_state['_nav_active_workspace']='Analysis';run();assert count()==640
 inputs=member_inputs(at.session_state.filtered_state)
 assert all(rows.apply(lambda r:concurrent_source_allowed(source_info(r)),axis=1).all() for rows in inputs.values())
 at.session_state['_nav_active_workspace']='Loads';run();assert count()==640
 assert next(x for x in at.radio if x.label=='Force source').value=='CSI Correspondence'
 next(x for x in at.checkbox if x.label=='Advanced import settings').check();run()
 assert not any('Source basis' in x.label for x in at.text_input)
 next(x for x in at.checkbox if x.label=='Advanced import settings').uncheck();run()
 pd.testing.assert_frame_equal(canonical(pd.DataFrame(at.session_state[BANK_KEY])),canonical(bank),check_dtype=False)
 saved=project_to_json(project_from_session_state(at.session_state.filtered_state));restored={}
 apply_project_to_session_state(project_from_json(saved),restored)
 assert pd.DataFrame(restored[BANK_KEY]).apply(lambda r:concurrent_source_allowed(source_info(r)),axis=1).all()
print('Full app.py PASS: simple import, 2 girders / 640 declared concurrent rows, no mandatory free text or confirmation checkboxes, navigation and JSON roundtrip preserve forces and source metadata; zero exceptions')
