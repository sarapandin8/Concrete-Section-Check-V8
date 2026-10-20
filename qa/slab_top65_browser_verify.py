"""Optional live-browser QA, with an isolated input-only Streamlit bootstrap.

Requires playwright and its chromium headless shell. Screenshots are private QA
evidence and are not bundled in a release or included in a Project JSON.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright


def run(project, exports, output, port=8565):
    root = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='csp-top65-') as temporary:
        wrapper = Path(temporary)/'browser_app.py'
        wrapper.write_text(f'''from pathlib import Path
from io import BytesIO
import runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
from concrete_pmm_pro.io.slab_shell_import import parse_files,BANK_KEY,PENDING_KEY
if not st.session_state.get('_top65_browser_inputs'):
    apply_project_to_session_state(project_from_json(Path({str(project.resolve())!r}).read_text()),st.session_state)
    files=[]
    for name in {[str(p.resolve()) for p in exports]!r}:
        path=Path(name);file=BytesIO(path.read_bytes());file.name=path.name;files.append(file)
    package=parse_files(files)
    if not package.ready:raise ValueError(str(package.errors))
    st.session_state[BANK_KEY]=package
    st.session_state[PENDING_KEY]=package.signature
    st.session_state['_nav_active_workspace']='Analysis'
    st.session_state['_nav_analysis_subpage']='Slab Reinforcement'
    st.session_state['_top65_browser_inputs']=True
runpy.run_path({str(root/'app.py')!r},run_name='__main__')
''')
        with (output/'server.log').open('w') as log:
            process = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', str(wrapper),
                '--server.port', str(port), '--server.address', '127.0.0.1',
                '--server.headless', 'true', '--browser.gatherUsageStats', 'false'], cwd=root, stdout=log, stderr=log)
            try:
                url = f'http://127.0.0.1:{port}'
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(60):
                    try:
                        if opener.open(url, timeout=1).status == 200:
                            break
                    except Exception:
                        time.sleep(.25)
                else:
                    raise RuntimeError('Local Streamlit server unavailable')
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--no-proxy-server'])
                    page = browser.new_page(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1)
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(url)
                    calculate = page.get_by_role('button', name='Calculate Top slab', exact=True)
                    calculate.wait_for(timeout=90000)
                    assert calculate.count() == 1
                    button_style = calculate.evaluate("e=>({kind:e.getAttribute('kind'),testid:e.getAttribute('data-testid'),background:getComputedStyle(e).backgroundImage,color:getComputedStyle(e.querySelector('p')||e).color})")
                    assert 'linear-gradient' in button_style['background'], button_style
                    assert button_style['color'] == 'rgb(255, 255, 255)', button_style
                    page.screenshot(path=str(output/'initial_desktop.png'))
                    print('Initial page available', flush=True)
                    calculate.click()
                    chart = page.locator('.st-key-slab_top65_plot .js-plotly-plot')
                    chart.wait_for(timeout=90000)
                    page.wait_for_function("document.querySelector('.st-key-slab_top65_plot .js-plotly-plot')?.layout?.meta?.slab_version==='SLAB.TOP65'")
                    assert chart.count() == 1
                    page.screenshot(path=str(output/'calculated_desktop.png'))
                    chart.screenshot(path=str(output/'plan_chart.png'))
                    initial = chart.evaluate('e=>({title:e.layout.title.text,meta:e.layout.meta,traces:e.data.length})')
                    def select(label, value):
                        control = page.get_by_test_id('stSelectbox').filter(has=page.get_by_text(label, exact=True))
                        combo = control.get_by_role('combobox')
                        combo.scroll_into_view_if_needed()
                        combo.fill(value)
                        page.get_by_role('option', name=value, exact=True).click()
                    select('Chart', 'Station D/C')
                    page.wait_for_function("document.querySelector('.st-key-slab_top65_plot .js-plotly-plot')?.layout?.title?.text?.includes('station envelope')")
                    profile = chart.evaluate('e=>({title:e.layout.title.text,meta:e.layout.meta,range:e.layout.xaxis.range,connectgaps:e.data[0].connectgaps})')
                    assert profile['connectgaps'] is False
                    assert abs(profile['range'][1]-20) < 1e-5
                    chart.screenshot(path=str(output/'station_chart.png'))
                    print('Plan and station charts available', flush=True)
                    select('Load case', 'U1A')
                    page.wait_for_function("document.querySelector('.st-key-slab_top65_plot .js-plotly-plot')?.layout?.uirevision?.endsWith(':U1A')")
                    assert chart.count() == 1
                    overflow = page.evaluate('({width:innerWidth,document:document.documentElement.scrollWidth})')
                    assert overflow['document'] <= overflow['width']+2
                    page.set_viewport_size({'width': 1280, 'height': 900})
                    page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollTop=0')
                    page.screenshot(path=str(output/'compact_desktop.png'))
                    # The fixed header must not cover the page's title.
                    heading = page.get_by_text('Top slab · Reinforcement', exact=True)
                    box = heading.bounding_box()
                    assert box is not None and box['y'] >= 0
                    assert not errors, errors
                    evidence = {'live_browser': True, 'browser': browser.version,
                        'viewport_widths': [1440, 1280], 'page_errors': errors,
                        'single_calculate_command': True, 'single_main_chart': True,
                        'primary_button_style': button_style,
                        'native_case_filter': 'U1A', 'plan': initial, 'profile': profile,
                        'title_box_at_scroll_top': box, 'document_overflow': overflow}
                    (output/'Browser_Verification.json').write_text(json.dumps(evidence, indent=2))
                    browser.close()
                    print(json.dumps(evidence, indent=2), flush=True)
                    return evidence
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--exports', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8565)
    args = parser.parse_args()
    run(args.project, args.exports, args.output, args.port)
