"""Real app Calculate / read-only review. QA displays one real cut per member.

The full imported bank remains in session and is hashed unchanged. Production
solver calls use the selected real cut rows, not a claimed 640-row span run.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--browser',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1];snapshot=args.output_dir/'session.json'
    with tempfile.TemporaryDirectory(prefix='csp-joint37-') as temp:
        wrapper=Path(temp)/'app_browser.py'
        wrapper.write_text(f'''import json,runpy,sys,hashlib
from pathlib import Path
import streamlit as st
import pandas as pd
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json,project_from_session_state,project_to_json
from concrete_pmm_pro.ui import analysis_page as ap,igird_station36 as sr,igird_joint37 as jr,igird_member_results as mr,igird_coupled_model as cm
def loads_hash():return hashlib.sha256(pd.DataFrame(st.session_state.get('igird_uls_member_bank',[])).to_json().encode()).hexdigest()
if not st.session_state.get('_station36_seeded'):
 apply_project_to_session_state(project_from_json(Path({str(args.project.resolve())!r}).read_text()),st.session_state)
 st.session_state['_nav_active_workspace']='Analysis';st.session_state['_nav_analysis_subpage']='ULS Strength'
 st.session_state['beam_girder_composite_flexure_stage']='Final — Composite'
 st.session_state['_station36_seeded']=True;st.session_state['_station36_load_hash']=loads_hash()
 st.session_state['_station36_calls']={{'section':0,'interface':0,'station':0,'joint':0}}
st.session_state['_station36_run']=st.session_state.get('_station36_run',0)+1
originals=mr.member_inputs,mr.calculate_member,ap._igird_interface_shear_dataframe,sr.calculate,jr.calculate
def selected_inputs(state):
 selected={{}}
 for name,frame in originals[0](state).items():
  chosen,_=sr.select_station(state,frame)
  selected[name]=frame.iloc[[chosen[1]]].copy()
 return selected
def counted(name,original):
 def inner(*a,**k):
  st.session_state['_station36_calls'][name]+=1
  return original(*a,**k)
 return inner
mr.member_inputs=selected_inputs;mr.calculate_member=counted('section',originals[1])
ap._igird_interface_shear_dataframe=counted('interface',originals[2]);sr.calculate=counted('station',originals[3]);jr.calculate=counted('joint',originals[4])
try:runpy.run_path({str(root/'app.py')!r},run_name='__main__')
finally:mr.member_inputs,mr.calculate_member,ap._igird_interface_shear_dataframe,sr.calculate,jr.calculate=originals
cache=st.session_state.get('igird_flexure31_runtime_results',{{}})
states={{}}
for name,value in cache.items():
 bundle=value.get('bundle',{{}});result=bundle.get('joint37_research',{{}})
 states[name]={{'status':result.get('status'),'reason':result.get('reason'),'intersections':len(result.get('geometry_audit',{{}}).get('U_intersections',[])),'accepted_phiTn_Nmm':result.get('accepted_phiTn_Nmm')}}
Path({str(snapshot.resolve())!r}).write_text(json.dumps({{'run':st.session_state['_station36_run'],'calls':st.session_state['_station36_calls'],
 'loads_unchanged':loads_hash()==st.session_state['_station36_load_hash'],'result_members':states,
 'enabled':jr.settings(st.session_state).get('enabled'),'cache_keys':list(cache),
 'json':json.loads(project_to_json(project_from_session_state(st.session_state)))['metadata'].get(jr.KEY)}},allow_nan=False))
''')
        with (args.output_dir/'server.log').open('w') as log:
            server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(wrapper),'--server.port','8547','--server.address','127.0.0.1',
                '--server.headless','true','--browser.gatherUsageStats','false','--global.developmentMode','false','--server.fileWatcherType','none'],cwd=root,stdout=log,stderr=log)
            try:
                url='http://127.0.0.1:8547';opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(80):
                    try:
                        if opener.open(url,timeout=1).status==200:break
                    except Exception:time.sleep(.2)
                else:raise RuntimeError('Streamlit did not start')
                with sync_playwright() as p:
                    browser=p.chromium.launch(executable_path=str(args.browser),headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server','--enable-unsafe-swiftshader'])
                    page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
                    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(url);button=page.get_by_role('button',name='Calculate Flexure',exact=True);button.wait_for(timeout=45000)
                    assert button.count()==1
                    button.click()
                    review=page.get_by_test_id('stExpander').filter(has=page.locator('summary').filter(has_text='Girder–U-dowel–slab — coupled transfer review'))
                    review.locator('summary').first.wait_for(timeout=120000)
                    review.locator('summary').first.click()
                    review.get_by_text('Input U path intersects 23',exact=False).wait_for(timeout=45000)
                    # First view is the design member (I section). Select the
                    # interior member through the real review control.
                    chart=review.get_by_test_id('stPlotlyChart');chart.scroll_into_view_if_needed();page.wait_for_timeout(1000)
                    page.screenshot(path=str(args.output_dir/'cage_I_1440.png'))
                    member=page.get_by_test_id('stSelectbox').filter(has_text='Girder to review')
                    combo=member.locator('[role="combobox"]');combo.click()
                    (args.output_dir/'select_state.json').write_text(json.dumps(combo.evaluate("e=>({tag:e.tagName,html:e.outerHTML,listboxes:[...document.querySelectorAll('[role=listbox]')].map(n=>n.textContent)})")))
                    combo.press('ArrowUp');combo.press('Enter')
                    review.get_by_text('BOBJ1 / Interior Girder 2 · U2A / Max / Before · x=19.000 m',exact=True).wait_for(state='attached',timeout=45000)
                    if not review.evaluate("e=>e.querySelector('details').open"):review.locator('summary').first.click()
                    review_text=review.text_content()
                    (args.output_dir/'review_text.txt').write_text(review_text)
                    assert 'x=19.000' in review_text,review_text[:1500]
                    assert review.get_by_test_id('stDataFrame').count()>=1
                    assert 'A=84–108 mm' in review_text
                    conflicts=review.get_by_test_id('stExpander').filter(has=page.locator('summary').filter(has_text='Input path conflicts / anchorage location'))
                    conflicts.locator('summary').first.click()
                    assert conflicts.get_by_test_id('stDataFrame').count()==3
                    conflicts.locator('summary').first.click()
                    review.evaluate("e=>e.scrollIntoView({block:'start',behavior:'instant'})");page.wait_for_timeout(1200)
                    page.screenshot(path=str(args.output_dir/'station_1440.png'))
                    chart=review.get_by_test_id('stPlotlyChart');chart.scroll_into_view_if_needed();page.wait_for_timeout(1500)
                    page.screenshot(path=str(args.output_dir/'cage_1440.png'))
                    data=json.loads(snapshot.read_text());calls=data['calls'].copy()
                    assert data['loads_unchanged'] and data['enabled'] and data['json']=={'enabled':True}
                    assert all(v['status']=='INPUT GEOMETRY REVIEW' and v['intersections']==23 and v['accepted_phiTn_Nmm'] is None for v in data['result_members'].values())
                    assert calls=={'section':2,'interface':2,'station':2,'joint':2},calls
                    page.set_viewport_size({'width':1280,'height':1000});page.wait_for_timeout(500)
                    review.evaluate("e=>e.scrollIntoView({block:'start',behavior:'instant'})");page.wait_for_timeout(400)
                    page.screenshot(path=str(args.output_dir/'station_1280.png'))
                    core=page.get_by_test_id('stExpander').filter(has=page.locator('summary').filter(has_text='One-station 3D review — girder cage'))
                    core.locator('summary').first.click()
                    core.get_by_text('JOINT37 found intersecting input paths.',exact=False).wait_for(timeout=15000)
                    core.locator('summary').first.click()
                    # Review toggles must not invoke any solver or mutate loads.
                    review.locator('summary').first.click();review.locator('summary').first.click();page.wait_for_timeout(500)
                    after=json.loads(snapshot.read_text());assert after['calls']==calls and after['loads_unchanged']
                    assert not errors and page.get_by_test_id('stException').count()==0
                    result={'status':'PASS','real_app':True,'actual_calculate_command':True,'one_primary_button':True,'solver_calls':calls,
                        'QA_scope':'One real selected cut per member; full 640-row bank preserved. Not a full-span browser solver run.',
                        'review_does_not_solve':True,'member_switch_does_not_solve':True,'raw_loads_unchanged':True,'json_settings_persist':True,'input_intersections_visible':23,'A_alone_infeasible_visible':True,'older_core_values_also_withheld_in_view':True,'full_composite_acceptance_withheld':True,'browser_errors':errors,'viewports':[1440,1280]}
                    (args.output_dir/'browser_review.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));browser.close()
            finally:server.terminate();server.wait(timeout=15)


if __name__=='__main__':main()
