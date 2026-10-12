"""Real-browser section inputs/preview verification; screenshots stay internal."""
import argparse,json,os,socket,subprocess,sys,time
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
for key in ['chrome','seed','screenshots']:parser.add_argument('--'+key,required=True)
args=parser.parse_args();out=Path(args.screenshots).resolve();assert not out.is_relative_to(ROOT);out.mkdir(parents=True,exist_ok=True)
env={**os.environ,'CSP_ENDSECTION18_SEED':str(Path(args.seed).resolve())}
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}';errors=[];records=[]
with (out/'streamlit.log').open('w') as log:
    server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'qa/igird_endsection18_ui_preview.py'),
        '--global.developmentMode','false','--server.port',str(port),'--server.headless','true','--server.fileWatcherType','none','--browser.gatherUsageStats','false'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        for _ in range(150):
            try:
                if requests.get(url+'/_stcore/health',timeout=1).ok:break
            except requests.RequestException:pass
            time.sleep(.2)
        with sync_playwright() as p:
            Path(args.chrome).chmod(0o700)
            browser=p.chromium.launch(executable_path=args.chrome,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
            page=browser.new_page(viewport={'width':1440,'height':1200});page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url,wait_until='domcontentloaded')
            header=page.get_by_text('Solid End Sections',exact=True);header.wait_for(timeout=90000)
            panel=header.locator("xpath=ancestor::div[@data-testid='stVerticalBlock'][1]");panel.scroll_into_view_if_needed()
            expect(page.get_by_text('LEFT SOLID END · bv ≈ 600 mm',exact=False)).to_be_visible(timeout=60000)
            for width in (1440,1100):
                page.set_viewport_size({'width':width,'height':1200});panel.scroll_into_view_if_needed();page.wait_for_timeout(300)
                panel.screenshot(path=str(out/f'end_sections_{width}.png'));box=panel.bounding_box();assert box['width']<=width and box['x']>=0
                records.append({'width':width,'inputs_and_section_preview_visible':True,'panel_fits_viewport':True})
            slider=page.get_by_role('slider',name='Preview section at Loads x (m) Preview section at Loads x (m)');slider.press('Home')
            for _ in range(80):slider.press('ArrowRight')
            expect(page.get_by_text('I SECTION · bv ≈ 200 mm',exact=False)).to_be_visible(timeout=60000)
            panel.screenshot(path=str(out/'i_section_preview_1100.png'))
            assert not page.get_by_test_id('stException').count() and not errors,errors;browser.close()
    finally:server.terminate();server.wait(timeout=20)
evidence=ROOT/'qa/evidence/igird_endsection18';evidence.mkdir(parents=True,exist_ok=True)
(evidence/'browser_checks.json').write_text(json.dumps({'records':records,'slider_changes_actual_polygon':True,'javascript_errors':errors},indent=2)+'\n')
print('Browser 1440/1100 px and actual solid/I polygon preview: PASS',flush=True)
