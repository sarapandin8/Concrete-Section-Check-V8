"""Full app.py: commit correspondence, close Advanced, navigate and reload."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from streamlit.testing.v1 import AppTest
import pandas as pd
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
from concrete_pmm_pro.io.girder_csi_import import source_info
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
from concrete_pmm_pro.ui.girder_csi_import import UPLOAD_LABEL
from concrete_pmm_pro.ui.igird_member_results import member_inputs
from concrete_pmm_pro.ui.igird_combined_vt import concurrent_source_allowed
state={}
apply_project_to_session_state(project_from_json(Path('qa/evidence/igird_vtqa1/hypothetical_verified_input_qa.json').read_text()),state)
state['_nav_active_workspace']='Loads';state['bridge_beam_uls_station_loads_advanced_import']=True
class Upload(BytesIO):
 def __init__(self):
  super().__init__((ROOT/'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx').read_bytes());self.name='native.xlsx'
def upload(label,*args,**kwargs):return [Upload()] if label==UPLOAD_LABEL else ([] if kwargs.get('accept_multiple_files') else None)
at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60)
for k,v in state.items():at.session_state[k]=deepcopy(v)
def run():at.run(timeout=60);assert not at.exception,[e.message for e in at.exception]
def box(label):return next(x for x in at.checkbox if x.label.startswith(label))
def count():
 bank=pd.DataFrame(at.session_state[BANK_KEY]);assert len(bank)==640
 return int(bank.apply(lambda r:concurrent_source_allowed(source_info(r)),axis=1).sum())
with patch('streamlit.file_uploader',side_effect=upload):
 run();box('I confirm member').check();run()
 next(x for x in at.selectbox if x.label=='Force-vector source').select('CSI Correspondence');run()
 assert next(x for x in at.button if x.label=='Replace entire girder collection').disabled
 box('I confirm each').check();run()
 next(x for x in at.text_input if x.label.startswith('Source basis')).set_value('User verified CSI Correspondence');run()
 box('All tables').check();run()
 next(x for x in at.button if x.label=='Replace entire girder collection').click();run()
 assert count()==640
 bank=pd.DataFrame(at.session_state[BANK_KEY]).copy(deep=True)
 box('Advanced import settings').uncheck();run();assert count()==640
 at.session_state['_nav_active_workspace']='Analysis';run();assert count()==640
 inputs=member_inputs(at.session_state.filtered_state)
 assert sum(len(rows) for rows in inputs.values())==640
 assert all(rows.apply(lambda r:concurrent_source_allowed(source_info(r)),axis=1).all() for rows in inputs.values())
 at.session_state['_nav_active_workspace']='Loads';run();assert count()==640
 def canonical(frame):
  frame=frame.copy()
  for key in ['Station x (m)','Mux','Nu','Vuy','Tu','Muy','Vux']:
   frame[key]=pd.to_numeric(frame[key]).astype(float)
  return frame.sort_values(['Girder','Case Name','Station x (m)']).reset_index(drop=True)
 pd.testing.assert_frame_equal(canonical(pd.DataFrame(at.session_state[BANK_KEY])),canonical(bank),check_dtype=False)
 assert any('saved source contract is concurrent' in x.value for x in at.success)
print('Full app.py PASS: 640 concurrent rows survive commit, closing Advanced and Analysis/Loads navigation; source readiness displayed; zero exceptions')
