"""Real-upload navigation review for the four bridge Analysis subpages.

Use --expect-retained after the fix. Before/after evidence is written outside
the repository. The wrapper only counts solver calls and exposes state facts.
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


def run(project, workbook, output, *, expect_retained=False, port=8571):
    root=Path(__file__).resolve().parents[1]
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='csp-analysis71-') as temporary:
        wrapper=Path(temporary)/'browser_app.py'
        wrapper.write_text(f'''from pathlib import Path
from html import escape
from unittest.mock import patch
import runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
from concrete_pmm_pro.io.girder_deflect70 import BANK_KEY
from concrete_pmm_pro.serviceability import girder_deflect70 as deflection
from concrete_pmm_pro.ui import analysis_page as ap,igird_sls53_results as stress
from concrete_pmm_pro.analysis import slab_review68 as slab
if not st.session_state.get('_analysis71_loaded'):
    apply_project_to_session_state(project_from_json(Path({str(project.resolve())!r}).read_text()),st.session_state)
    st.session_state['_nav_active_workspace']='Analysis'
    st.session_state['_nav_analysis_subpage']='SLS Deflection / Camber'
    st.session_state['_analysis71_loaded']=True
def tracked(name,original):
    def call(*args,**kwargs):
        key='_qa71_calls_'+name
        st.session_state[key]=st.session_state.get(key,0)+1
        return original(*args,**kwargs)
    return call
with patch.object(deflection,'calculate',tracked('deflection',deflection.calculate)),patch.object(stress,'calculate',tracked('stress',stress.calculate)),patch.object(slab,'calculate',tracked('slab',slab.calculate)),patch.object(ap,'_beam_uls_calculate_selected_check',tracked('uls',ap._beam_uls_calculate_selected_check)):
    runpy.run_path({str(root/'app.py')!r},run_name='__main__')
st.session_state['_qa71_sequence']=st.session_state.get('_qa71_sequence',0)+1
facts={{'bank':BANK_KEY in st.session_state,'result_current':deflection.current(st.session_state) is not None,
    'stage':st.session_state.get('girder_deflect70_ui_stage'),
    'girder':st.session_state.get('girder_deflect70_ui_girder'),
    'workspace':st.session_state.get('_nav_active_workspace'),'subpage':st.session_state.get('_nav_analysis_subpage'),
    'dirty_analysis_status':st.session_state.get('_perf_analysis_status'),
    'calls':{{k:st.session_state.get('_qa71_calls_'+k,0) for k in ['deflection','stress','slab','uls']}}}}
st.html('<div id="qa71-state" data-sequence="'+str(st.session_state['_qa71_sequence'])+'" data-facts="'+escape(__import__('json').dumps(facts),quote=True)+'"></div>')
''')
        with (output/'server.log').open('w') as log:
            process=subprocess.Popen([sys.executable,'-m','streamlit','run',str(wrapper),'--server.port',str(port),
                '--server.address','127.0.0.1','--server.headless','true','--browser.gatherUsageStats','false'],
                cwd=root,stdout=log,stderr=log)
            try:
                url=f'http://127.0.0.1:{port}'
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(100):
                    try:
                        if opener.open(url,timeout=1).status==200:break
                    except Exception:time.sleep(.25)
                else:raise RuntimeError('Local app unavailable')
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server'])
                    page=browser.new_page(viewport={'width':1440,'height':1100})
                    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(url)
                    facts=page.locator('#qa71-state')
                    facts.wait_for(state='attached',timeout=90000)
                    def state():
                        value=json.loads(facts.get_attribute('data-facts'))
                        value['sidebar_analysis']=page.locator('.cpmm-sidebar-status-row').nth(1).locator('.cpmm-sidebar-status-value').inner_text()
                        return value
                    def action(callback):
                        previous=int(facts.get_attribute('data-sequence'))
                        callback()
                        page.wait_for_function("Number(document.querySelector('#qa71-state')?.dataset.sequence)>"+str(previous),timeout=90000)
                        assert page.get_by_test_id('stException').count()==0
                        return state()
                    evidence={'initial':state()}
                    (output/'Navigation_Initial.json').write_text(json.dumps(evidence,indent=2))
                    # Older JSON may restore stale ULS entries. Neither a page
                    # visit nor its saved global flag can make them Current.
                    if expect_retained:assert evidence['initial']['sidebar_analysis'] in {'Not calculated 0/4','Stale 0/4'}, evidence['initial']
                    action(lambda:page.locator('.st-key-girder_deflect70_ui_upload input[type="file"]').set_input_files(str(workbook.resolve())))
                    action(lambda:page.get_by_role('button',name='Calculate deflection / camber',exact=True).click())
                    if expect_retained:
                        assert state()['sidebar_analysis']=='Partial 1/4'
                        current_card=page.locator('.cpmm-commercial-metric-card').filter(has=page.get_by_text('Stored result status',exact=True))
                        expect(current_card.locator('.cpmm-commercial-metric-value')).to_have_text('CURRENT')
                    option=page.get_by_test_id('stRadioOption').filter(has=page.get_by_text('Service stage',exact=True))
                    action(lambda:option.click())
                    selector=page.locator('.st-key-girder_deflect70_ui_girder').get_by_role('combobox')
                    selector.click()
                    evidence['before_navigation']=action(lambda:page.get_by_role('option',name='Interior Girder 2',exact=True).click())
                    assert evidence['before_navigation']['bank'] and evidence['before_navigation']['result_current']
                    evidence['summary']=action(lambda:page.get_by_role('button',name='Result Summary',exact=True).click())
                    evidence['report']=action(lambda:page.get_by_role('button',name='Report / QA',exact=True).click())
                    evidence['returned']=action(lambda:page.get_by_role('button',name='Analysis',exact=True).click())
                    page.screenshot(path=str(output/'return_to_analysis.png'))
                    if expect_retained:
                        page.locator('.st-key-girder_deflect70_plot').screenshot(path=str(output/'service_plot.png'))
                    if expect_retained:
                        assert evidence['returned']['bank'] and evidence['returned']['result_current']
                        assert evidence['returned']['stage']=='Service stage'
                        assert evidence['returned']['girder']=='Interior Girder 2'
                        route_states={}
                        for subpage in ['ULS Strength','SLS / Stress & Cracking','Slab Reinforcement','SLS Deflection / Camber']:
                            route_states[subpage]=action(lambda name=subpage:page.get_by_role('button',name=name,exact=True).click())
                            assert route_states[subpage]['bank'] and route_states[subpage]['result_current']
                            assert route_states[subpage]['calls']=={'deflection':1,'stress':0,'slab':0,'uls':0}
                        assert route_states['SLS Deflection / Camber']['girder']=='Interior Girder 2'
                        evidence['four_subpage_navigation']=route_states
                        evidence['explicit_clear']=action(lambda:page.get_by_role('button',name='Clear Service import',exact=True).click())
                        assert not evidence['explicit_clear']['bank'] and not evidence['explicit_clear']['result_current']
                        action(lambda:page.locator('.st-key-girder_deflect70_ui_upload input[type="file"]').set_input_files(str(workbook.resolve())))
                        remove=page.locator('.st-key-girder_deflect70_ui_upload').get_by_role('button',name='Remove '+workbook.name,exact=True)
                        evidence['explicit_X']=action(lambda:remove.click())
                        assert not evidence['explicit_X']['bank'] and not evidence['explicit_X']['result_current']
                        assert evidence['explicit_X']['calls']=={'deflection':1,'stress':0,'slab':0,'uls':0}
                    assert evidence['returned']['calls']=={'deflection':1,'stress':0,'slab':0,'uls':0}
                    assert not errors
                    evidence.update(browser=browser.version,page_errors=errors,expect_retained=expect_retained)
                    (output/'Navigation_Verification.json').write_text(json.dumps(evidence,indent=2))
                    print(json.dumps(evidence,indent=2),flush=True)
                    browser.close()
                    return evidence
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--workbook',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expect-retained',action='store_true')
    args=parser.parse_args()
    run(args.project,args.workbook,args.output,expect_retained=args.expect_retained)
