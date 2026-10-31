from pathlib import Path
from unittest.mock import patch
from collections import Counter
import pickle,time,json,resource,logging,argparse
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.ui import bg40_report,igird_uls_report
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--state',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
for name in ('streamlit.runtime.scriptrunner_utils.script_run_context','streamlit.runtime.memory_media_file_storage','streamlit.runtime.media_file_manager','streamlit.deprecation_util','streamlit.dataframe_util'):logging.getLogger(name).setLevel(logging.ERROR)
with args.state.open('rb') as f:state,_=pickle.load(f)
app=AppTest.from_file(str(args.source/'app.py'),default_timeout=180)
for k,v in state.items():app.session_state[k]=v
app.session_state['_nav_active_workspace']='Report / QA'
counts=Counter()
def wrap(fn,label):
 def call(*a,**kw):
  counts[label]+=1;return fn(*a,**kw)
 return call
start=time.perf_counter()
with patch.object(bg40_report,'build_workflow_report',wrap(bg40_report.build_workflow_report,'report_builds')),patch.object(bg40_report,'source_signature',wrap(bg40_report.source_signature,'artifact_signature_scans')),patch.object(igird_uls_report,'make_package_figure',wrap(igird_uls_report.make_package_figure,'uls_chart_builds')):
 app.run(timeout=180)
result={'elapsed_seconds':round(time.perf_counter()-start,3),'peak_rss_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),'calls':dict(counts),'exceptions':[e.message for e in app.exception],'dataframes':len(app.dataframe),'plotly_charts':len(app.get('plotly_chart')),'download_buttons':len(app.get('download_button')),'selectboxes':len(app.selectbox)}
args.output.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
