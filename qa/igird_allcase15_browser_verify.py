"""Browser chart QA; all screenshots and result checkpoints remain internal."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import socket
import sys
import time
import requests
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--chrome',required=True)
parser.add_argument('--screenshots',required=True)
parser.add_argument('--seed',required=True)
args = parser.parse_args()
out = Path(args.screenshots).resolve()
assert not out.is_relative_to(ROOT)
out.mkdir(parents=True,exist_ok=True)
env = os.environ.copy()
env['CSP_ALLCASE15_QA_SEED'] = str(Path(args.seed).resolve())
records = []
with socket.socket() as address:
    address.bind(('127.0.0.1',0))
    port = address.getsockname()[1]
url = f'http://127.0.0.1:{port}'
with (out/'streamlit.log').open('w') as log:
    server = subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'qa/igird_allcase15_ui_preview.py'),
        '--global.developmentMode','false','--server.port',str(port),'--server.headless','true',
        '--server.fileWatcherType','none','--browser.gatherUsageStats','false'],
        cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        for _ in range(150):
            try:
                if requests.get(url+'/_stcore/health',timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(.2)
        else:
            raise RuntimeError('QA server did not start')
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chrome,headless=True,
                args=['--no-sandbox','--disable-dev-shm-usage'])
            errors = []
            for check in ('Torsion','Shear'):
                page = browser.new_page(viewport={'width':1440,'height':1280})
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(url+'?qa_check='+check,wait_until='domcontentloaded')
                page.wait_for_function("""() => document.querySelector('[data-testid="stException"]') ||
                    document.body.textContent.includes('Girder: BOBJ1 / Left Exterior Girder')""",timeout=60000)
                assert page.get_by_test_id('stException').count() == 0, page.get_by_test_id('stException').all_text_contents()
                for member in ('BOBJ1 / Left Exterior Girder','BOBJ1 / Interior Girder 2'):
                    label = page.get_by_text('Girder: '+member,exact=True)
                    expect(label).to_be_visible(timeout=60000)
                    label.click()
                page.wait_for_function("""check => {
                    const plots = [...document.querySelectorAll('.js-plotly-plot')];
                    const all = plots.filter(p => p.layout?.meta?.igird_allcase_check === check);
                    return all.length === 2 && all.every(p => Object.keys(p.layout.meta.member_case_legend).length === 16);
                }""",arg=check,timeout=60000)
                charts = page.evaluate("""check => [...document.querySelectorAll('.js-plotly-plot')]
                    .filter(p => p.layout?.meta?.igird_allcase_check === check)
                    .map(p => ({title:p.layout.title.text,cases:p.layout.meta.igird_allcase_cases.length,
                        demandTraces:p.data.filter(t => /^(Vu|Tu) C[0-9]+$/.test(t.name)).length,
                        hiddenDemands:p.data.filter(t => /^(Vu|Tu) C[0-9]+$/.test(t.name) && t.visible === 'legendonly').length,
                        domain:p.layout.xaxis.range}))""",check)
                assert len(charts) == 2 and all(c['demandTraces'] == 16 and not c['hiddenDemands'] for c in charts)
                assert page.get_by_text('Case for diagram',exact=True).count() == 0
                chart = page.get_by_test_id('stPlotlyChart').filter(has=page.locator('.js-plotly-plot')).first
                chart.scroll_into_view_if_needed()
                layout_ok = """() => {
                    const p = document.querySelector('.js-plotly-plot');
                    const legend = p?.querySelector('.legend');
                    const note = [...(p?.querySelectorAll('.annotation') || [])].find(g => g.textContent.includes('Blue: every'));
                    return legend && note && note.getBoundingClientRect().top > legend.getBoundingClientRect().bottom + 4
                        && note.getBoundingClientRect().bottom < p.getBoundingClientRect().bottom - 4;
                }"""
                page.wait_for_function(layout_ok,timeout=15000)
                chart.screenshot(path=str(out/(check.lower()+'_all_cases_1440.png')))
                records.append({'check':check,'charts':charts,'redundant_case_selector':False,
                                'legend_note_clearance_verified':True})
                if check == 'Shear':
                    page.set_viewport_size({'width':1100,'height':1150})
                    chart.scroll_into_view_if_needed()
                    page.wait_for_function(layout_ok,timeout=15000)
                    chart.screenshot(path=str(out/'shear_all_cases_1100.png'))
                page.close()
            assert not errors,errors
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)
(ROOT/'qa/evidence/igird_allcase15/browser_checks.json').write_text(json.dumps({
    'browser':'Chrome Headless Shell 134','javascript_errors':errors,'records':records,
    'viewports':[[1440,1280],[1100,1150]]},indent=2)+'\n')
print('Browser: both girders plot all 16 source traces for Shear and Torsion without a second case selector.',flush=True)
