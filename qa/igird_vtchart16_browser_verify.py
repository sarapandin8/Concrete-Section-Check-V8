"""Visual QA on the actual app; screenshots remain outside the deliverable."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import requests
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--chrome',required=True)
parser.add_argument('--seed',required=True)
parser.add_argument('--screenshots',required=True)
args = parser.parse_args()
out = Path(args.screenshots).resolve()
assert not out.is_relative_to(ROOT)
out.mkdir(parents=True,exist_ok=True)
env = {**os.environ,'CSP_VTCHART16_QA_SEED':str(Path(args.seed).resolve())}
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
url = f'http://127.0.0.1:{port}'
records,errors = [],[]
with (out/'streamlit.log').open('w') as log:
    server = subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'qa/igird_vtchart16_ui_preview.py'),
        '--global.developmentMode','false','--server.port',str(port),'--server.headless','true',
        '--server.fileWatcherType','none','--browser.gatherUsageStats','false'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        for _ in range(150):
            try:
                if requests.get(url+'/_stcore/health',timeout=1).ok: break
            except requests.RequestException: pass
            time.sleep(.2)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chrome,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            page = browser.new_page(viewport={'width':1440,'height':1280})
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(url,wait_until='domcontentloaded')
            page.get_by_text('Girder: Left Exterior Girder',exact=True).wait_for(timeout=60000)
            for member in ('Left Exterior Girder','Interior Girder 2'):
                panel = page.get_by_test_id('stExpander').filter(has=page.get_by_text('Girder: '+member,exact=True)).first
                panel.locator('summary').first.click()
                panel.get_by_text('Combined components / individual cases',exact=True).click()
            page.wait_for_function("""() => [...document.querySelectorAll('.js-plotly-plot')].filter(p=>p.data?.some(t=>t.name==='Spacing D/C')).length===2""",timeout=60000)
            charts = page.get_by_test_id('stPlotlyChart').filter(has=page.locator('.js-plotly-plot'))
            for width in (1440,1100):
                page.set_viewport_size({'width':width,'height':1280})
                for i in range(charts.count()):
                    chart = charts.nth(i)
                    if not chart.locator('.js-plotly-plot').evaluate("p => p.data?.some(t=>t.name==='Spacing D/C')"): continue
                    chart.scroll_into_view_if_needed()
                    page.wait_for_timeout(350)
                    record = chart.locator('.js-plotly-plot').evaluate("""p => ({title:p.layout.title.text,
                        legend:[...p.querySelectorAll('.legendtext')].map(t=>t.textContent),
                        spacing:p.data.filter(t=>t.name==='Spacing D/C').length,
                        shear:p.data.filter(t=>t.name==='Shear limit D/C').length,
                        xDomain:p.layout.xaxis.range,legendBottom:p.querySelector('.legend').getBoundingClientRect().bottom,
                        chartBottom:p.getBoundingClientRect().bottom})""")
                    assert record['spacing'] and record['shear']
                    assert 'Veff D/C' not in record['legend']
                    assert record['legendBottom'] < record['chartBottom'],record
                    assert record['xDomain']==[0,20]
                    record['width'] = width
                    records.append(record)
                    chart.screenshot(path=str(out/f'components_{i}_{width}.png'))
            assert not errors,errors
            assert not page.get_by_test_id('stException').count()
            browser.close()
    finally:
        server.terminate(); server.wait(timeout=20)
(ROOT/'qa/evidence/igird_vtchart16/browser_checks.json').write_text(json.dumps({
    'browser':'Chrome Headless Shell 134','javascript_errors':errors,'records':records},indent=2)+'\n')
print('Browser: four components visible for both girders at 1440 and 1100 px.',flush=True)
