"""Exercise the real file uploader, import action and static-result chart.

Browser screenshots are private QA and are not included in release archives.
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


def run(project, exports, output, port=8567):
    root = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='csp-import67-') as temporary:
        wrapper = Path(temporary)/'browser_app.py'
        wrapper.write_text(f'''from pathlib import Path
import runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
if not st.session_state.get('_import67_browser_inputs'):
    apply_project_to_session_state(project_from_json(Path({str(project.resolve())!r}).read_text()),st.session_state)
    st.session_state['_nav_active_workspace']='Loads'
    st.session_state['_nav_loads_subpage']='Slab Shell Results'
    st.session_state['_import67_browser_inputs']=True
runpy.run_path({str(root/'app.py')!r},run_name='__main__')
''')
        with (output/'server.log').open('w') as log:
            process = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', str(wrapper),
                '--server.port', str(port), '--server.address', '127.0.0.1',
                '--server.headless', 'true', '--browser.gatherUsageStats', 'false'],
                cwd=root, stdout=log, stderr=log)
            try:
                url = f'http://127.0.0.1:{port}'
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(80):
                    try:
                        if opener.open(url, timeout=1).status == 200:
                            break
                    except Exception:
                        time.sleep(.25)
                else:
                    raise RuntimeError('Local Streamlit server unavailable')
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--no-proxy-server'])
                    page = browser.new_page(viewport={'width': 1440, 'height': 1100})
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(url)
                    upload = page.locator('input[type=file][multiple]')
                    upload.wait_for(state='attached', timeout=60000)
                    upload.set_input_files([str(p.resolve()) for p in exports])
                    command = page.get_by_role('button', name='Import & validate shell data', exact=True)
                    command.click()
                    page.get_by_text('IMPORTED — required tables and input links are available.', exact=False).wait_for(timeout=90000)
                    assert page.get_by_test_id('stException').count() == 0
                    assert page.get_by_test_id('stAlertContainer').filter(has_text='INCOMPLETE').count() == 0
                    page.get_by_text('Imported tables / validation details', exact=True).click()
                    page.get_by_text('StepType not exported; retained as blank.', exact=False).wait_for()
                    page.screenshot(path=str(output/'imported_static.png'))
                    print('Actual four-file upload imported successfully', flush=True)
                    page.get_by_role('button', name='Open Slab Reinforcement →', exact=True).click()
                    calculate = page.get_by_role('button', name='Calculate Top slab', exact=True)
                    calculate.wait_for(timeout=60000)
                    assert calculate.count() == 1
                    calculate.click()
                    chart = page.locator('.st-key-slab_top65_plot .js-plotly-plot')
                    chart.wait_for(timeout=120000)
                    assert chart.count() == 1
                    page.screenshot(path=str(output/'calculated_static.png'))
                    assert page.get_by_test_id('stException').count() == 0
                    assert not errors, errors
                    verification = {'milestone': 'SLAB.IMPORT67', 'actual_file_upload': True,
                        'import_button_used': True, 'static_import_ready': True,
                        'optional_step_note_visible': True, 'analysis_navigation': True,
                        'calculation_button_count': calculate.count(), 'chart_count': chart.count(),
                        'chart_meta': chart.evaluate('e=>e.layout.meta'), 'page_errors': errors,
                        'browser': browser.version, 'full_deck_acceptance': False}
                    (output/'Browser_Verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2))
                    browser.close()
                    print(json.dumps(verification, ensure_ascii=False, indent=2), flush=True)
                    return verification
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
    args = parser.parse_args()
    run(args.project, args.exports, args.output)
