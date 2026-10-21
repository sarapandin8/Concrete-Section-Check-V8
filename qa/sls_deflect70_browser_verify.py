"""Real file upload, two native girder plots, stage navigation and audit QA.

Browser screenshots are private visual QA. No artificial live load is added.
"""
from pathlib import Path
import argparse
import csv
from io import BytesIO, StringIO
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from zipfile import ZipFile

from playwright.sync_api import sync_playwright, expect


def run(project, workbook, output, port=8570):
    root = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='csp-deflect70-browser-') as temporary:
        wrapper = Path(temporary) / 'browser_app.py'
        wrapper.write_text(f'''from pathlib import Path
import runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
if not st.session_state.get('_deflect70_browser_inputs'):
    apply_project_to_session_state(project_from_json(Path({str(project.resolve())!r}).read_text()),st.session_state)
    st.session_state['_nav_active_workspace']='Analysis'
    st.session_state['_nav_analysis_subpage']='SLS Deflection / Camber'
    st.session_state['_deflect70_browser_inputs']=True
runpy.run_path({str(root/'app.py')!r},run_name='__main__')
''')
        with (output / 'server.log').open('w') as log:
            process = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', str(wrapper),
                '--server.port', str(port), '--server.address', '127.0.0.1', '--server.headless', 'true',
                '--browser.gatherUsageStats', 'false'], cwd=root, stdout=log, stderr=log)
            try:
                url = f'http://127.0.0.1:{port}'
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(100):
                    try:
                        if opener.open(url, timeout=1).status == 200: break
                    except Exception: time.sleep(.25)
                else: raise RuntimeError('Local server unavailable')
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--no-proxy-server'])
                    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
                    errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(url)
                    calculate = page.get_by_role('button', name='Calculate deflection / camber', exact=True)
                    calculate.wait_for(timeout=90000)
                    assert calculate.count() == 1
                    chart = page.locator('.st-key-girder_deflect70_plot .js-plotly-plot')
                    def stage(value):
                        option = page.get_by_test_id('stRadioOption').filter(has=page.get_by_text(value, exact=True))
                        option.evaluate("e=>e.scrollIntoView({block:'center'})")
                        option.click()
                        page.wait_for_function("document.querySelector('.st-key-girder_deflect70_plot .js-plotly-plot')?._fullLayout?.meta?.stage === " + json.dumps(value))
                    def capture(name):
                        assert chart.count() == 1
                        chart.screenshot(path=str(output / name))
                        return chart.evaluate('e=>({title:e._fullLayout.title.text,meta:e._fullLayout.meta,range:e._fullLayout.xaxis.range,traces:e._fullData.map(t=>({name:t.name,x:Array.from(t.x||[]),y:Array.from(t.y||[]),connectgaps:t.connectgaps}))})')
                    calculate.click(); chart.wait_for(timeout=90000)
                    expect(calculate).to_be_enabled(timeout=60000)
                    stage('Service stage')
                    missing = capture('service_before_upload.png')
                    assert not missing['meta']['service_available']
                    assert not any('Calculated response' == t['name'] for t in missing['traces'])
                    page.locator('.st-key-girder_deflect70_ui_upload input[type="file"]').set_input_files(str(workbook.resolve()))
                    page.get_by_text('2 girders', exact=False).wait_for(timeout=60000)
                    calculate.click(); chart.wait_for(timeout=90000)
                    expect(calculate).to_be_enabled(timeout=60000)
                    plots = {}
                    stage('Transfer stage'); plots['Transfer'] = capture('transfer.png')
                    stage('Construction stage'); plots['Construction'] = capture('construction.png')
                    stage('Service stage')
                    page.wait_for_function("document.querySelector('.st-key-girder_deflect70_plot .js-plotly-plot')?._fullLayout?.meta?.girder === 'Left Exterior Girder'")
                    plots['Left Exterior Girder'] = capture('service_left_exterior.png')
                    selector = page.locator('.st-key-girder_deflect70_ui_girder').get_by_role('combobox')
                    selector.click()
                    page.get_by_role('option', name='Interior Girder 2', exact=True).click()
                    page.wait_for_function("document.querySelector('.st-key-girder_deflect70_plot .js-plotly-plot')?._fullLayout?.meta?.girder === 'Interior Girder 2'")
                    plots['Interior Girder 2'] = capture('service_interior_2.png')
                    for girder, expected in [('Left Exterior Girder', -9.227), ('Interior Girder 2', -9.160)]:
                        item = plots[girder]
                        assert girder in item['title'] and 'WebTop Vert' in item['title']
                        assert item['meta']['source'] == 'Imported SLS envelope'
                        traces = [t for t in item['traces'] if t['name'] in ['Envelope Max', 'Envelope Min']]
                        assert len(traces) == 2 and all(len(t['x']) == 24 for t in traces)
                        assert all(t['connectgaps'] is False and t['x'][0] == 0 and t['x'][-1] == 20 for t in traces)
                        assert abs(min(v for t in traces for v in t['y']) - expected) < 1e-9
                        assert item['range'] == [0, 20]
                    for label in ['Transfer', 'Construction']:
                        assert 'single I-girder' in plots[label]['title'] and 'calculated' in plots[label]['title']
                    page.get_by_text('Calculation trace / Equations / Source audit', exact=True).click()
                    with page.expect_download() as downloaded:
                        page.get_by_role('button', name='Download deflection audit', exact=True).click()
                    path = output / 'downloaded_audit.zip'
                    downloaded.value.save_as(str(path))
                    with ZipFile(BytesIO(path.read_bytes())) as archive:
                        assert archive.testzip() is None
                        records = list(csv.DictReader(StringIO(archive.read('CSI_Service_Source.csv').decode('utf-8-sig'))))
                        assert len(records) == 96
                    page.set_viewport_size({'width': 1280, 'height': 900})
                    chart.screenshot(path=str(output / 'service_compact_1280.png'))
                    overflow = page.evaluate('({width:innerWidth,document:document.documentElement.scrollWidth})')
                    assert overflow['document'] <= overflow['width'] + 2
                    assert not errors and page.get_by_test_id('stException').count() == 0
                    evidence = {'milestone': 'SLS.DEFLECT70', 'browser': browser.version, 'page_errors': errors,
                        'actual_workbook_uploaded_through_browser': True, 'no_service_fallback_before_upload': True,
                        'single_calculate_command': True, 'single_visible_chart': True, 'two_girders_selectable': True,
                        'viewports_px': [1440,1280], 'document_overflow': overflow,
                        'report_downloaded_with_96_native_vertical_rows': True, 'plots': plots,
                        'full_deflection_acceptance': False}
                    (output / 'Browser_Verification.json').write_text(json.dumps(evidence, indent=2))
                    print(json.dumps({k:v for k,v in evidence.items() if k != 'plots'}, indent=2), flush=True)
                    browser.close()
                    return evidence
            finally:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--workbook', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.project, args.workbook, args.output)
