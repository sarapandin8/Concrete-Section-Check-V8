"""Local browser QA; screenshots stay outside the distributable project."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import requests
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--chrome', required=True)
parser.add_argument('--screenshots', required=True)
args = parser.parse_args()
out = Path(args.screenshots).resolve()
if out.is_relative_to(ROOT):
    raise ValueError('Internal browser screenshots must be outside the distributable project.')
out.mkdir(parents=True, exist_ok=True)
source = ROOT / 'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx'
record = {}
with (out / 'streamlit.log').open('w') as log:
    server = subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT / 'qa/igird_csiimport14_ui_preview.py'),
        '--global.developmentMode','false','--server.port','8515','--server.headless','true',
        '--server.fileWatcherType','none','--browser.gatherUsageStats','false'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env=os.environ.copy())
    try:
        for attempt in range(100):
            try:
                if requests.get('http://127.0.0.1:8515/_stcore/health',timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(.2)
        else:
            raise RuntimeError('Local QA server did not start.')
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chrome,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            page = browser.new_page(viewport={'width':1440,'height':1180},device_scale_factor=1)
            failures = []
            page.on('pageerror',lambda error:failures.append(str(error)))
            page.goto('http://127.0.0.1:8515',wait_until='domcontentloaded')
            entry = page.get_by_text('Import Bridge Beam/Girder ULS station loads from Excel / CSV',exact=True)
            expect(entry).to_be_visible(timeout=45000)
            entry.click()
            expect(page.get_by_text('ULS Excel / CSV import — automatic format detection',exact=True)).to_be_visible(timeout=45000)
            label = 'Upload Bridge Beam/Girder ULS station-load import'
            upload = page.get_by_test_id('stFileUploader').filter(has_text=label)
            upload.locator('input[type=file]').set_input_files(str(source))
            expect(page.get_by_text('Bridge Object Girder Forces: 2 physical girders detected.',exact=False)).to_be_visible(timeout=30000)
            for text in ('I confirm member names identify physical girders consistently across files, with the same station origin for each member',
                         'All tables use raw CSI P signs: tension positive, compression negative'):
                page.get_by_test_id('stCheckbox').filter(has_text=text).locator('label').click()
                expect(page.get_by_label(text,exact=True)).to_be_checked(timeout=10000)
            replace = page.get_by_role('button',name='Replace entire girder collection',exact=True)
            expect(replace).to_be_enabled(timeout=30000)
            page.get_by_text('1 file · 640 retained rows · 32 separate vector series',exact=True).scroll_into_view_if_needed()
            page.screenshot(path=str(out / 'native_preview_1440.png'))
            page.get_by_text('Source rows / units — Before/After and original CSI fields',exact=True).click()
            page.get_by_text('Original CSI columns and raw signs are retained',exact=False).scroll_into_view_if_needed()
            page.screenshot(path=str(out / 'source_audit_1440.png'))
            replace.click()
            expect(page.get_by_text('Imported girder collection — select member for Analysis',exact=False)).to_be_visible(timeout=30000)
            combo = page.get_by_test_id('stSelectbox').filter(has_text='Girder to design').get_by_role('combobox')
            combo.click()
            page.get_by_role('option',name='BOBJ1 / Interior Girder 2',exact=True).click()
            page.get_by_role('button',name='Use this girder — all imported load cases',exact=True).click()
            expect(page.get_by_text('Analysis member: BOBJ1 / Interior Girder 2.',exact=False)).to_be_visible(timeout=30000)
            page.get_by_text('Imported girder collection — select member for Analysis',exact=False).scroll_into_view_if_needed()
            page.screenshot(path=str(out / 'active_interior_1440.png'))
            assert not failures, failures
            record = {'browser':'Chrome Headless Shell 134','viewport':[1440,1180],'native_upload':True,
                      'preview_rows':640,'source_members':2,'vector_series':32,'source_audit_visible':True,
                      'member_switch':'BOBJ1 / Interior Girder 2','javascript_errors':failures}
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)
(ROOT / 'qa/evidence/igird_csiimport14/browser_checks.json').write_text(json.dumps(record,indent=2)+'\n')
print('Actual browser upload, audit preview and member switch passed; internal screenshots ready.',flush=True)
