"""Live UI QA with the real uploader, compact review, charts and report.

Screenshots remain private visual QA and are never packed in a release.
The optional screenshot mat scenario is explicit and input-only.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright,expect


def run(project,exports,output,*,example_mats=False,port=8568):
    root=Path(__file__).resolve().parents[1]
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='csp-review68-') as temporary:
        wrapper=Path(temporary)/'browser_app.py'
        wrapper.write_text(f'''from pathlib import Path
import runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
sys.path.insert(0,{str(root/'qa')!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
from slab_review68_real_inputs import apply_example_mats
if not st.session_state.get('_review68_browser_inputs'):
    apply_project_to_session_state(project_from_json(Path({str(project.resolve())!r}).read_text()),st.session_state)
    if {example_mats!r}:apply_example_mats(st.session_state)
    st.session_state['_nav_active_workspace']='Loads'
    st.session_state['_nav_loads_subpage']='Slab Shell Results'
    st.session_state['_review68_browser_inputs']=True
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
                else:raise RuntimeError('Local Streamlit server unavailable')
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server'])
                    page=browser.new_page(viewport={'width':1440,'height':1100})
                    errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(url)
                    upload=page.locator('input[type=file][multiple]')
                    upload.wait_for(state='attached',timeout=60000)
                    upload.set_input_files([str(p.resolve()) for p in exports])
                    page.get_by_role('button',name='Import & validate shell data',exact=True).click()
                    page.get_by_text('IMPORTED — required tables and input links are available.',exact=False).wait_for(timeout=90000)
                    page.get_by_role('button',name='Open Slab Reinforcement →',exact=True).click()
                    calculate=page.get_by_role('button',name='Calculate Top slab',exact=True)
                    calculate.wait_for(timeout=60000)
                    assert calculate.count()==1
                    button_style=calculate.evaluate("e=>({disabled:e.disabled,background:getComputedStyle(e).backgroundImage,color:getComputedStyle(e.querySelector('p')||e).color})")
                    started=time.monotonic();calculate.click()
                    chart=page.locator('.st-key-slab_top65_plot .js-plotly-plot')
                    chart.wait_for(timeout=120000)
                    page.wait_for_function("document.querySelector('.st-key-slab_top65_plot .js-plotly-plot')?._fullLayout?.meta?.slab_version==='SLAB.REVIEW68'")
                    elapsed=time.monotonic()-started
                    expect(calculate).to_be_enabled(timeout=120000)
                    assert chart.count()==1 and page.get_by_test_id('stException').count()==0
                    review=page.get_by_text('AASHTO applicability / Local transfer review',exact=True)
                    details=review.locator('xpath=ancestor::details')
                    assert not details.get_attribute('open')
                    page.screenshot(path=str(output/'calculated_desktop.png'))
                    review.click()
                    page.get_by_text('Governing tension-side shear ties',exact=True).wait_for()
                    page.get_by_text('Selected signed section cuts · comparison only',exact=True).wait_for()
                    review.scroll_into_view_if_needed()
                    page.screenshot(path=str(output/'review_expanded.png'))
                    assert page.get_by_test_id('stException').count()==0
                    review.click()
                    chart.screenshot(path=str(output/'plan_chart.png'))
                    plan=chart.evaluate('e=>({title:e._fullLayout.title.text,meta:e._fullLayout.meta,traces:e._fullData.length})')
                    def select(label,value):
                        box=page.get_by_test_id('stSelectbox').filter(has=page.get_by_text(label,exact=True)).get_by_role('combobox')
                        box.scroll_into_view_if_needed();box.fill(value)
                        page.get_by_role('option',name=value,exact=True).click()
                    page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollTop=0')
                    page.get_by_test_id('stRadioOption').filter(has=page.get_by_text('One-way shear',exact=True)).click()
                    expect(page.get_by_role('radio',name='One-way shear',exact=True)).to_be_checked()
                    try:
                        page.wait_for_function("document.querySelector('.st-key-slab_top65_plot .gtitle')?.textContent?.startsWith('Shear · transverse')")
                    except Exception:
                        page.screenshot(path=str(output/'group_diagnostic.png'))
                        print(page.get_by_test_id('stMain').inner_text()[-18000:],flush=True)
                        raise
                    select('Result','Flexural shear tie · longitudinal')
                    select('Chart','Station D/C')
                    page.wait_for_function("document.querySelector('.st-key-slab_top65_plot .gtitle')?.textContent?.includes('longitudinal · station envelope')")
                    profile=chart.evaluate('e=>({title:e._fullLayout.title.text,meta:e._fullLayout.meta,range:e._fullLayout.xaxis.range,connectgaps:e._fullData[0].connectgaps})')
                    assert profile['connectgaps'] is False and profile['range']==[0,20]
                    chart.screenshot(path=str(output/'station_chart.png'))
                    select('Load case','U2A')
                    page.wait_for_function("document.querySelector('.st-key-slab_top65_plot .js-plotly-plot')?._fullLayout?.uirevision?.endsWith(':U2A')")
                    page.get_by_text('Code scope / Details / Report',exact=True).click()
                    page.get_by_role('button',name='Prepare compact Top slab report',exact=True).click()
                    page.get_by_role('button',name='Download Top slab report',exact=True).wait_for(timeout=60000)
                    page.set_viewport_size({'width':1280,'height':900})
                    page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollTop=0')
                    heading=page.get_by_text('Top slab · Reinforcement',exact=True)
                    box=heading.bounding_box()
                    assert box and box['y']>=0
                    overflow=page.evaluate('({width:innerWidth,document:document.documentElement.scrollWidth})')
                    assert overflow['document']<=overflow['width']+2
                    page.screenshot(path=str(output/'compact_desktop.png'))
                    assert not errors and page.get_by_test_id('stException').count()==0
                    evidence={'milestone':'SLAB.REVIEW68','actual_four_file_upload':True,'example_mats_explicitly_applied':example_mats,
                        'browser':browser.version,'page_errors':errors,'single_calculate_command':True,'single_main_chart':True,
                        'primary_button_style':button_style,
                        'review_initially_collapsed':True,'review_expanded_without_error':True,'report_prepared':True,
                        'browser_calculate_to_chart_seconds':elapsed,'plan':plan,'profile':profile,
                        'native_case_filter':'U2A','viewport_widths':[1440,1280],
                        'title_box_at_scroll_top':box,'document_overflow':overflow,'full_deck_acceptance':False}
                    (output/'Browser_Verification.json').write_text(json.dumps(evidence,indent=2))
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
    parser.add_argument('--exports',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--example-mats',action='store_true')
    args=parser.parse_args()
    run(args.project,args.exports,args.output,example_mats=args.example_mats)
