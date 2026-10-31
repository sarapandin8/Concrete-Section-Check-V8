"""Run the native ALL82 download test with idle/reopen runtime assertions."""
from pathlib import Path
from collections import Counter
from unittest.mock import patch
import json,resource,runpy,sys,time
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.ui import bg40_report as ui
from concrete_pmm_pro.reporting import bg40_word

ROOT=Path(__file__).resolve().parents[1]
counts=Counter();runs=[];last=[]
def counted(fn,label):
    def call(*args,**kwargs):
        counts[label]+=1
        return fn(*args,**kwargs)
    return call
native_run=AppTest.run

def observed_run(app,*args,**kwargs):
    before=dict(counts);start=time.perf_counter()
    result=native_run(app,*args,**kwargs)
    delta={key:counts[key]-before.get(key,0) for key in counts}
    entry={'seconds':round(time.perf_counter()-start,3),'calls':delta,
        'plotly_charts':len(app.get('plotly_chart')),'dataframes':len(app.dataframe),
        'exceptions':[e.message for e in app.exception]}
    if not runs:
        assert not delta.get('report_builds') and not delta.get('png_renders')
        assert not app.dataframe and not app.get('plotly_chart')
    runs.append(entry);last[:]=[app]
    return result

with patch.object(ui,'build_workflow_report',counted(ui.build_workflow_report,'report_builds')), \
     patch.object(ui,'build_complete_artifact',counted(ui.build_complete_artifact,'word_exports')), \
     patch.object(bg40_word,'plotly_figure_to_png_bytes',counted(bg40_word.plotly_figure_to_png_bytes,'png_renders')), \
     patch.object(AppTest,'run',observed_run):
    runpy.run_path(str(ROOT/'qa/report_all82_ui_export.py'),run_name='__main__')
    for _ in range(3):
        before=dict(counts)
        last[0].run(timeout=600)
        assert dict(counts)==before,'Reopening Report/QA must not rebuild documents or PNGs'
        assert not last[0].exception
        assert any(d.key=='bg40_80_download' for d in last[0].get('download_button'))
assert counts['report_builds']==counts['word_exports']==1
out=Path(sys.argv[sys.argv.index('--out')+1]);path=out/'UI_Export_Validation.json'
validation=json.loads(path.read_text())
validation['runtime83']={'runs':runs,'total_builds':dict(counts),
    'parent_process_peak_rss_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
    'peak_scope':'Python app process only; native renderer children are excluded.',
    'reopens_without_rebuild':3}
path.write_text(json.dumps(validation,indent=2))
print('RUNTIME83',json.dumps(validation['runtime83']),flush=True)
