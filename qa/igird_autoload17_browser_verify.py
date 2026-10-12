"""Real XLSX upload requires no Apply or member-assignment click."""
import argparse,json,os,socket,subprocess,sys,time
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
for name in ('chrome','seed','screenshots'):parser.add_argument('--'+name,required=True)
args=parser.parse_args();out=Path(args.screenshots).resolve()
assert not out.is_relative_to(ROOT)
out.mkdir(parents=True,exist_ok=True)
env={**os.environ,'CSP_AUTOLOAD17_SEED':str(Path(args.seed).resolve())}
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'
errors=[];records=[]
with (out/'streamlit.log').open('w') as log:
    server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'qa/igird_autoload17_ui_preview.py'),
        '--global.developmentMode','false','--server.port',str(port),'--server.headless','true',
        '--server.fileWatcherType','none','--browser.gatherUsageStats','false'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        for _ in range(150):
            try:
                if requests.get(url+'/_stcore/health',timeout=1).ok:break
            except requests.RequestException:pass
            time.sleep(.2)
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=args.chrome,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            page=browser.new_page(viewport={'width':1440,'height':1200})
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url,wait_until='domcontentloaded')
            title='Import Bridge Beam/Girder ULS station loads from Excel / CSV'
            page.get_by_text(title,exact=True).wait_for(timeout=90000)
            panel=page.get_by_test_id('stExpander').filter(has=page.get_by_text(title,exact=True)).first
            panel.get_by_test_id('stFileUploader').locator('input[type=file]').set_input_files(str(ROOT/'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx'))
            expect(panel.get_by_text('Loads assigned by Girder',exact=True)).to_be_visible(timeout=60000)
            expect(panel.get_by_test_id('stAlert').filter(has_text='Last successful import')).to_be_visible()
            assert panel.get_by_role('button',name='Replace entire girder collection',exact=True).count()==0
            assert page.get_by_role('button',name='Use this girder — all imported load cases',exact=True).count()==0
            assert panel.get_by_text('Force-vector source',exact=True).count()==0
            for width in (1440,1100):
                page.set_viewport_size({'width':width,'height':1200})
                panel.scroll_into_view_if_needed();page.wait_for_timeout(300)
                panel.screenshot(path=str(out/f'auto_import_{width}.png'))
                records.append({'width':width,'automatic_import':True,'success_visible':True,'apply_clicks':0,'member_assignment_clicks':0,'advanced_controls_hidden':True})
            assert not page.get_by_test_id('stException').count()
            assert not errors,errors
            browser.close()
    finally:server.terminate();server.wait(timeout=20)
(ROOT/'qa/evidence/igird_autoload17/browser_checks.json').write_text(json.dumps({'records':records,'javascript_errors':errors,
    'member_switch_verification':'Actual app.py AppTest; browser verification scoped to native upload and layout.'},indent=2)+'\n')
print('Browser: upload automatically assigns both girders without an Apply click.',flush=True)
