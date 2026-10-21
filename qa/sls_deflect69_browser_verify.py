"""Live local-app QA of all stage plots, LL source and compact export.

Screenshots are private visual QA, not release artifacts or project inputs.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright, expect


def run(project,output,port=8569):
    root=Path(__file__).resolve().parents[1]
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='csp-deflect69-') as temporary:
        wrapper=Path(temporary)/'browser_app.py'
        wrapper.write_text(f'''from pathlib import Path
import runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
if not st.session_state.get('_deflect69_qa_inputs'):
    apply_project_to_session_state(project_from_json(Path({str(project.resolve())!r}).read_text()),st.session_state)
    st.session_state['_nav_active_workspace']='Analysis'
    st.session_state['_nav_analysis_subpage']='SLS Deflection / Camber'
    st.session_state['_deflect69_qa_inputs']=True
runpy.run_path({str(root/'app.py')!r},run_name='__main__')
''')
        with (output/'server.log').open('w') as log:
            process=subprocess.Popen([sys.executable,'-m','streamlit','run',str(wrapper),
                '--server.port',str(port),'--server.address','127.0.0.1','--server.headless','true',
                '--browser.gatherUsageStats','false'],cwd=root,stdout=log,stderr=log)
            try:
                url=f'http://127.0.0.1:{port}'
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(80):
                    try:
                        if opener.open(url,timeout=1).status==200:break
                    except Exception:time.sleep(.25)
                else:raise RuntimeError('Local server unavailable')
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server'])
                    page=browser.new_page(viewport={'width':1440,'height':1100})
                    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(url)
                    calculate=page.get_by_role('button',name='Calculate deflection / camber',exact=True)
                    calculate.wait_for(timeout=90000)
                    assert calculate.count()==1
                    calculate.click()
                    chart=page.locator('.st-key-girder_deflect69_plot .js-plotly-plot')
                    chart.wait_for(timeout=90000)
                    expect(calculate).to_be_enabled(timeout=60000)
                    assert chart.count()==1
                    page.get_by_text('The generated bridge stage-load model has no live-load component.',exact=False).wait_for()
                    stage_evidence={}
                    def capture(stage,name,evidence_key=None):
                        page.wait_for_function("document.querySelector('.st-key-girder_deflect69_plot .js-plotly-plot')?._fullLayout?.meta?.stage === "+json.dumps(stage))
                        chart.screenshot(path=str(output/name))
                        evidence=chart.evaluate('e=>({title:e._fullLayout.title.text,meta:e._fullLayout.meta,range:e._fullLayout.xaxis.range,traces:e._fullData.map(t=>({name:t.name,x:Array.from(t.x||[]),y:Array.from(t.y||[]),connectgaps:t.connectgaps}))})')
                        assert evidence['range']==[0,20]
                        assert all(t['connectgaps'] is False for t in evidence['traces'] if len(t['x'])>2)
                        stage_evidence[evidence_key or stage]=evidence
                    capture('Transfer stage','transfer.png')
                    for stage,name in [('Construction stage','construction.png'),('Service stage','service_missing_ll.png')]:
                        option=page.get_by_test_id('stRadioOption').filter(has=page.get_by_text(stage,exact=True))
                        option.evaluate("e=>e.scrollIntoView({block:'center'})")
                        option.click()
                        capture(stage,name)
                    service=stage_evidence['Service stage']
                    limit=next(t for t in service['traces'] if t['name'].startswith('LL limit'))
                    assert abs(limit['y'][0]+20000/1500)<1e-8
                    assert sum(t['name']=='Sustained · elastic' for t in service['traces'])==1
                    assert not any(t['name']=='LL+IM increment' for t in service['traces'])
                    page.get_by_text('Deflection criteria / Live-load source',exact=True).click()
                    live=page.get_by_role('spinbutton',name='Service LL+IM per girder (kN/m)',exact=True)
                    live.fill('20');live.press('Tab')
                    calculate.click()
                    page.wait_for_function("document.querySelector('.st-key-girder_deflect69_plot .js-plotly-plot')?._fullLayout?.meta?.live_source_available === true")
                    expect(calculate).to_be_enabled(timeout=60000)
                    capture('Service stage','service_explicit_qa_ll20.png','Service stage · QA LL20')
                    assert any(t['name']=='LL+IM increment' for t in stage_evidence['Service stage · QA LL20']['traces'])
                    page.get_by_text('Calculation trace / Equations / Source audit',exact=True).click()
                    download=page.get_by_role('button',name='Download deflection audit',exact=True)
                    download.wait_for()
                    with page.expect_download() as downloaded:
                        download.click()
                    downloaded.value.save_as(str(output/'downloaded_audit.zip'))
                    page.set_viewport_size({'width':1280,'height':900})
                    page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollTop=0')
                    page.screenshot(path=str(output/'compact_1280.png'))
                    overflow=page.evaluate('({width:innerWidth,document:document.documentElement.scrollWidth})')
                    assert overflow['document']<=overflow['width']+2
                    assert not errors and page.get_by_test_id('stException').count()==0
                    evidence={'milestone':'SLS.DEFLECT69','browser':browser.version,'page_errors':errors,
                        'single_calculate_command':True,'single_visible_chart':True,'viewports':[1440,1280],
                        'document_overflow':overflow,'original_project_LL_source_missing':True,
                        'explicit_QA_only_live_udl_kN_m':20.,'explicit_LL_plot_available':True,
                        'report_downloaded':True,'stages':stage_evidence,'full_deflection_acceptance':False}
                    (output/'Browser_Verification.json').write_text(json.dumps(evidence,indent=2))
                    print(json.dumps({k:v for k,v in evidence.items() if k!='stages'},indent=2),flush=True)
                    browser.close()
                    return evidence
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.project,args.output)
