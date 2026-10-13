import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from streamlit.testing.v1 import AppTest
script='''
import pandas as pd
from concrete_pmm_pro.ui.igird_combined_vt import check_dataframe,render_workspace
row={'Case Name':'U2A / Max','Station x (m)':2.,'Mux':100.,'Nu':0.,'Vuy':800.,'Tu':300.,'Note':''}
df=check_dataframe({},pd.DataFrame([row]),strength_route=None)
render_workspace(df,code_label='AASHTO LRFD 9th Edition')
'''
at=AppTest.from_string(script).run(timeout=30)
assert not at.exception,[e.message for e in at.exception]
assert any('blocked before calculation' in x.value for x in at.caption)
assert any('simultaneous' in x.value for x in at.warning)
print('Blocked V+T workspace AppTest PASS; no exception; source message displayed')
