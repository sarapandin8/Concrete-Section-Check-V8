"""Reproduce old cell resets and verify continuous editing in actual app.py."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--browser',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--app-root',type=Path)
    parser.add_argument('--expect-reset',action='store_true')
    parser.add_argument('--port',type=int,default=8535)
    parser.add_argument('--width',type=int,default=1440)
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    root=(args.app_root or Path(__file__).resolve().parents[1]).resolve()
    snapshot=args.output_dir.resolve()/'session_inputs.json'
    with tempfile.TemporaryDirectory(prefix='csp-edit33-') as temp:
        wrapper=Path(temp)/'browser_app.py'
        wrapper.write_text(f'''from pathlib import Path
import hashlib,json,runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
from concrete_pmm_pro.ui import analysis_page as ap,igird_member_results as members
def load_hash():
    def fallback(v):return v.to_dict(orient='records') if hasattr(v,'to_dict') else str(v)
    return hashlib.sha256(json.dumps({{k:st.session_state.get(k) for k in ('igird_uls_member_bank','beam_uls_loads_table')}},sort_keys=True,default=fallback).encode()).hexdigest()
if not st.session_state.get('_edit33_browser_inputs'):
    apply_project_to_session_state(project_from_json(Path({str(args.project.resolve())!r}).read_text()),st.session_state)
    st.session_state['_nav_active_workspace']='Analysis'
    st.session_state['_nav_analysis_subpage']='ULS Strength'
    st.session_state['beam_girder_composite_flexure_stage']='Final — Composite'
    st.session_state['igird_flexure31_edit_inputs']=True
    st.session_state['_edit33_load_hash']=load_hash()
    st.session_state['_edit33_browser_inputs']=True
def forbidden(*a,**k):raise AssertionError('Editing inputs triggered a solver')
ap._igird_interface_shear_dataframe=forbidden
ap._igird_dowel_joint_review=forbidden
members.calculate_member=forbidden
runpy.run_path({str(root/'app.py')!r},run_name='__main__')
st.session_state['_edit33_qa_runs']=st.session_state.get('_edit33_qa_runs',0)+1
Path({str(snapshot)!r}).write_text(json.dumps({{'run':st.session_state['_edit33_qa_runs'],
    'settings':ap._igird_interface_shear_settings_from_state(st.session_state),
    'workspace':st.session_state.get('_nav_active_workspace'),
    'subpage':st.session_state.get('_nav_analysis_subpage'),
    'stage':st.session_state.get('beam_girder_composite_flexure_stage'),
    'edit_inputs':st.session_state.get('igird_flexure31_edit_inputs'),
    'loads_unchanged':load_hash()==st.session_state['_edit33_load_hash'],
    'solver_calls':0}},allow_nan=False))
''')
        with (args.output_dir/'browser-server.log').open('w') as log:
            server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(wrapper),
                '--server.port',str(args.port),'--server.address','127.0.0.1',
                '--server.headless','true','--browser.gatherUsageStats','false',
                '--global.developmentMode','false','--server.fileWatcherType','none'],
                cwd=root,stdout=log,stderr=log)
            try:
                url=f'http://127.0.0.1:{args.port}'
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(50):
                    try:
                        if opener.open(url,timeout=1).status==200:break
                    except Exception:time.sleep(.2)
                else:raise RuntimeError('Server did not start')
                with sync_playwright() as p:
                    browser=p.chromium.launch(executable_path=str(args.browser.resolve()),headless=True,
                        args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server'])
                    page=browser.new_page(viewport={'width':args.width,'height':1100},device_scale_factor=1)
                    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(url)
                    page.get_by_role('button',name='Calculate Flexure',exact=True).wait_for(timeout=30000)
                    detail=page.get_by_test_id('stExpander').filter(has=page.locator('summary').filter(has_text=re.compile('Dowel detail')))
                    summary=detail.locator('summary').filter(has_text=re.compile('Dowel detail'))
                    summary.click()
                    detail.get_by_text('Match A–F in the drawing',exact=False).scroll_into_view_if_needed()
                    guide=page.locator('svg[data-dowel-guide="IGIRDER.DOWEL32"]')
                    guide.wait_for(state='visible',timeout=15000)
                    page.wait_for_timeout(400)
                    table=detail.get_by_test_id('stDataFrame').first
                    rows=['row_spacing_mm','slab_ldh_available_mm','hook_tail_mm',
                        'hook_inside_bend_mm','cover_required_mm','girder_ld_available_mm']
                    edits=[(0,120.),(1,180.)] if args.expect_reset else [
                        (0,120.),(1,180.),(2,200.),(3,72.),(4,55.),(5,900.),(2,None),(2,200.),(0,125.)]
                    records=[]
                    for row,value in edits:
                        canvas=table.locator('canvas').first
                        canvas.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})")
                        page.wait_for_timeout(300)
                        bounds=canvas.bounding_box();assert bounds
                        old=json.loads(snapshot.read_text())['run']
                        old_scroll=page.get_by_test_id('stMain').evaluate('e=>e.scrollTop')
                        widget=table.locator('xpath=ancestor::div[@data-testid="stElementContainer"][1]').get_attribute('class')
                        # Glide's scroll overlay owns pointer events above its
                        # canvas. Send a real pointer action to the observed
                        # cell location, rather than targeting the covered node.
                        page.mouse.dblclick(bounds['x']+bounds['width']*.88,bounds['y']+36+35*row+17)
                        field=page.locator('input.gdg-input')
                        try:field.wait_for(state='visible',timeout=3000)
                        except Exception:
                            page.screenshot(path=str(args.output_dir/'cell_debug.png'))
                            (args.output_dir/'cell_debug.json').write_text(json.dumps({
                                'bounds':bounds,'active':page.evaluate('document.activeElement.outerHTML'),
                                'inputs':page.locator('input,textarea,[contenteditable]').evaluate_all('es=>es.map(e=>e.outerHTML)'),
                                'table':table.evaluate('e=>e.outerHTML')},indent=2))
                            raise
                        commit_key='Tab' if row==3 else 'Enter'
                        field.fill('' if value is None else str(value));field.press(commit_key)
                        for _ in range(160):
                            try:
                                current=json.loads(snapshot.read_text())
                                if current['run']>old:break
                            except (FileNotFoundError,json.JSONDecodeError):pass
                            time.sleep(.05)
                        else:raise AssertionError('Cell commit did not finish')
                        page.wait_for_timeout(200)
                        saved=current['settings']['dowel_connection'][rows[row]]
                        opened=detail.locator('details').first.evaluate('e=>e.open')
                        new_scroll=page.get_by_test_id('stMain').evaluate('e=>e.scrollTop')
                        record={'dimension':rows[row],'entered':value,'saved':saved,
                            'detail_open':opened,'scroll_change_px':round(new_scroll-old_scroll,2),
                            'widget_class':widget,'run':current['run'],'commit_key':commit_key}
                        records.append(record)
                        if not args.expect_reset:
                            assert saved==value,record
                            assert opened and current['workspace']=='Analysis' and current['subpage']=='ULS Strength',record
                            assert current['stage']=='Final — Composite' and current['edit_inputs'],record
                            assert abs(new_scroll-old_scroll)<200,record
                            assert current['loads_unchanged'] and current['solver_calls']==0
                    if args.expect_reset:
                        assert records[0]['saved']==120 and (records[1]['saved']!=180 or not records[1]['detail_open']),records
                    else:
                        assert len({r['widget_class'] for r in records})==1,records
                        accepted=current['settings']['dowel_connection']
                        for show in (False,True):
                            old=current['run']
                            page.get_by_text('Edit composite / dowel inputs',exact=True).click()
                            for _ in range(160):
                                current=json.loads(snapshot.read_text())
                                if current['run']>old:break
                                time.sleep(.05)
                            else:raise AssertionError('Input view toggle did not finish')
                            assert current['edit_inputs']==show
                            assert current['settings']['dowel_connection']==accepted
                        if not detail.locator('details').first.evaluate('e=>e.open'):summary.click()
                        guide.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})")
                        guide.wait_for(state='visible')
                        assert '125 mm' in guide.locator('[data-dimension="row_spacing_mm"]').text_content()
                        guide.evaluate("e=>e.scrollIntoView({block:'center'})")
                        guide.screenshot(path=str(args.output_dir/'guide_after_edits.png'))
                        table.evaluate("e=>e.scrollIntoView({block:'center'})")
                    page.screenshot(path=str(args.output_dir/'input_editor.png'))
                    assert not page.get_by_test_id('stException').count() and not errors,errors
                    assert page.get_by_role('button',name=re.compile('^Calculate')).count()==1
                    result={'mode':'baseline_reproduction' if args.expect_reset else 'EDIT33',
                        'actual_app':True,'browser':browser.version,'viewport_width':args.width,'commits':records,
                        'hide_reopen_preserves_inputs':not args.expect_reset,
                        'loads_unchanged':current['loads_unchanged'],'solver_calls':0,
                        'page_errors':errors,'streamlit_exceptions':0,'visual_inspection':'Pending'}
                    (args.output_dir/'EDIT33_browser_review.json').write_text(json.dumps(result,indent=2)+'\n')
                    print(json.dumps(result,indent=2),flush=True)
                    browser.close()
            finally:
                server.terminate();server.wait(timeout=15)


if __name__=='__main__':main()
