"""Actual UI export, renderer reuse, progress, and Linux process-tree observations.

Run with PYTHONPATH pointing to the candidate (or baseline) source. The same
AppTest export captures native Word download bytes; no renderer is replaced.
RSS sums include shared pages more than once and are observations, not a
Streamlit Cloud quota guarantee.
"""
from collections import Counter
from pathlib import Path
import json
import math
import os
import runpy
import threading
import time
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.reporting import figure_export
from concrete_pmm_pro.ui import bg40_report as ui

ROOT=Path(__file__).resolve().parents[1]
counts=Counter(); events=[]; samples=[]; runs=[]; apps=[]; stop=threading.Event()
host_pid=int(next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('Pid:')))

def process_tree():
    rows={}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            tail=path.read_text().rsplit(')',1)[1].split()
            rows[int(path.parent.name)]=(int(tail[1]),int(tail[2]),int(tail[21])*os.sysconf('SC_PAGE_SIZE'),tail[0])
        except (OSError,ValueError,IndexError):
            pass
    selected={host_pid}; changed=True
    while changed:
        previous=len(selected)
        selected.update(pid for pid,row in rows.items() if row[0] in selected)
        changed=len(selected)!=previous
    live={pid:rows[pid] for pid in selected if pid in rows and rows[pid][3]!='Z'}
    return live

def monitor():
    while not stop.is_set():
        rows=process_tree()
        samples.append({'rss':sum(r[2] for r in rows.values()),
            'parent_rss':rows.get(host_pid,(0,0,0,''))[2],
            'children':len(rows)-int(host_pid in rows)})
        stop.wait(.05)

native_run=AppTest.run

def observed_run(app,*args,**kwargs):
    start=time.perf_counter()
    result=native_run(app,*args,**kwargs)
    runs.append({'seconds':round(time.perf_counter()-start,3),
                 'exceptions':[e.message for e in app.exception]})
    apps[:]=[app]
    return result

native_build=ui.build_complete_artifact

def observed_build(*args,**kwargs):
    counts['complete_exports']+=1
    progress=kwargs.get('progress')
    if progress is not None:
        def observed_progress(message,fraction):
            events.append({'message':message,'fraction':fraction})
            return progress(message,fraction)
        kwargs['progress']=observed_progress
    return native_build(*args,**kwargs)

worker_type=getattr(figure_export,'_StaticImageRenderer',None)
native_start=worker_type._start if worker_type else None

def observed_start(renderer):
    counts['renderer_worker_starts']+=1
    return native_start(renderer)

thread=threading.Thread(target=monitor,daemon=True);thread.start()
try:
    with patch.object(AppTest,'run',observed_run), patch.object(ui,'build_complete_artifact',observed_build):
        context=patch.object(worker_type,'_start',observed_start) if worker_type else __import__('contextlib').nullcontext()
        with context:
            runpy.run_path(str(ROOT/'qa/report_runtime83_ui_export.py'),run_name='__main__')
finally:
    stop.set();thread.join(timeout=3)

import sys
out=Path(sys.argv[sys.argv.index('--out')+1]);path=out/'UI_Export_Validation.json'
validation=json.loads(path.read_text())
validation['cloud85']={'runs':runs,'counts':dict(counts),'progress_events':len(events),
    'progress_reaches_complete':bool(events and events[-1]['fraction']==1.),
    'maximum_process_tree_rss_mib':round(max(s['rss'] for s in samples)/1024**2,2),
    'maximum_parent_rss_mib':round(max(s['parent_rss'] for s in samples)/1024**2,2),
    'maximum_concurrent_child_processes':max(s['children'] for s in samples),
    'live_descendants_after_export':max(0,len(process_tree())-1),
    'resource_scope':'Linux app process and all native descendants, sampled every 50 ms. Summed RSS double-counts shared pages; local observation, not a Cloud quota guarantee.'}
if worker_type:
    expected=math.ceil(validation['figures']/figure_export.MAX_FIGURES_PER_WORKER)
    assert counts['renderer_worker_starts']==expected
    assert events and events[-1]['fraction']==1.
    assert validation['cloud85']['live_descendants_after_export']==0
validation['cloud85']['diagnostics']=dict(apps[-1].session_state[ui.DIAGNOSTICS_KEY])
(out/'Cloud85_Export_Validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
print('CLOUD85',json.dumps(validation['cloud85']),flush=True)
