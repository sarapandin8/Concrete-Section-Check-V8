"""Actual app.py: read-only U-dowel guide, form references and viewport QA."""
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
    parser.add_argument('--port',type=int,default=8534)
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='csp-dowel32-') as temp:
        wrapper=Path(temp)/'browser_app.py'
        wrapper.write_text(f'''from pathlib import Path
import runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
if not st.session_state.get('_dowel32_browser_inputs'):
    apply_project_to_session_state(project_from_json(Path({str(args.project.resolve())!r}).read_text()),st.session_state)
    st.session_state['_nav_active_workspace']='Analysis'
    st.session_state['_nav_analysis_subpage']='ULS Strength'
    st.session_state['beam_girder_composite_flexure_stage']='Final — Composite'
    st.session_state['igird_flexure31_edit_inputs']=True
    st.session_state['_dowel32_browser_inputs']=True
runpy.run_path({str(root/'app.py')!r},run_name='__main__')
''')
        with (args.output_dir/'browser-server.log').open('w') as log:
            server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(wrapper),
                '--server.port',str(args.port),'--server.address','127.0.0.1',
                '--server.headless','true','--browser.gatherUsageStats','false'],
                cwd=root,stdout=log,stderr=log)
            try:
                url=f'http://127.0.0.1:{args.port}'
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(40):
                    try:
                        if opener.open(url,timeout=1).status==200:break
                    except Exception:time.sleep(.25)
                else:raise RuntimeError('Local server did not start')
                with sync_playwright() as p:
                    browser=p.chromium.launch(executable_path=str(args.browser.resolve()),headless=True,
                        args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server'])
                    page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
                    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    console=[];page.on('console',lambda m:console.append(m.text) if m.type=='error' else None)
                    page.goto(url)
                    page.get_by_role('button',name='Calculate Flexure',exact=True).wait_for(timeout=30000)
                    detail=page.get_by_test_id('stExpander').filter(has=page.locator('summary').filter(has_text=re.compile('Dowel detail —')))
                    detail.locator('summary').filter(has_text=re.compile('Dowel detail —')).click()
                    # HTML/Canvas components load on viewport entry. Move the
                    # guide placeholder into view before waiting for its SVG.
                    detail.get_by_text('Match A–F in the drawing',exact=False).scroll_into_view_if_needed()
                    guide=page.locator('svg[data-dowel-guide="IGIRDER.DOWEL32"]')
                    try:
                        guide.wait_for(state='visible',timeout=20000)
                    except Exception:
                        (args.output_dir/'debug-timeout.json').write_text(json.dumps({'page_errors':errors,
                            'console':console,'html':page.get_by_test_id('stHtml').evaluate_all('es=>es.map(e=>e.outerHTML)'),
                            'body':detail.evaluate('e=>e.outerHTML')},indent=2))
                        page.screenshot(path=str(args.output_dir/'debug-timeout.png'))
                        raise
                    assert guide.count()==1
                    entries=guide.locator('g[data-dimension]').all_text_contents()
                    assert len(entries)==6
                    assert sum('Not entered' in text for text in entries)==5
                    assert '50 mm' in entries[4]
                    records=[]
                    for width in (1440,1280):
                        page.set_viewport_size({'width':width,'height':1100})
                        guide.evaluate("e=>e.scrollIntoView({block:'center'})")
                        page.wait_for_timeout(250)
                        bounds=guide.bounding_box()
                        assert bounds and bounds['x']>=0 and bounds['x']+bounds['width']<=width+1
                        assert bounds['height']>350
                        overlaps=guide.evaluate('''svg=>Array.from(svg.querySelectorAll('g[data-dimension]')).filter(row=>{
                            const label=row.querySelector('text.field').getBBox(),value=row.querySelector('text.value').getBBox();
                            return label.x+label.width+12>value.x;
                        }).map(row=>row.dataset.dimension)''')
                        assert not overlaps,overlaps
                        guide.screenshot(path=str(args.output_dir/f'guide_{width}.png'))
                        records.append({'width':width,'figure_width':bounds['width'],'legend_overlaps':overlaps})
                    detail.get_by_text('How to measure A–F',exact=True).click()
                    assert detail.locator('summary').filter(has_text='How to measure A–F').evaluate('s=>s.parentElement.open')
                    page.wait_for_timeout(350)
                    page.screenshot(path=str(args.output_dir/'form_1280.png'),full_page=True)
                    assert page.get_by_role('button',name=re.compile('^Calculate')).count()==1
                    assert not page.get_by_test_id('stException').count() and not errors,errors
                    # The guide must not trigger any calculation while opened.
                    page.get_by_text('No current results for this girder.',exact=False).wait_for(timeout=10000)
                    record={'version':'IGIRDER.DOWEL32','browser':browser.version,
                        'actual_app':True,'input_only_bootstrap':True,'guide_count':1,
                        'six_matching_dimension_references':True,'unknown_lengths_preserved':True,
                        'reused_cover_mm':50,'calculate_buttons':1,'viewports':records,
                        'page_errors':errors,'streamlit_exceptions':0,
                        'visual_inspection':'Pending image inspection'}
                    (args.output_dir/'DOWEL32_browser_review.json').write_text(json.dumps(record,indent=2)+'\n')
                    print(json.dumps(record,indent=2),flush=True)
                    browser.close()
            finally:
                server.terminate();server.wait(timeout=15)


if __name__=='__main__':main()
