"""Real app input flow; QA mesh edits never update the user's project JSON."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--project",type=Path,required=True)
    parser.add_argument("--browser",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--inspect-only",action="store_true")
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1];snapshot=args.output_dir/"session.json"
    with tempfile.TemporaryDirectory(prefix="csp-detail35-") as temp:
        wrapper=Path(temp)/"browser_app.py"
        wrapper.write_text(f'''import json,runpy,sys,hashlib
from pathlib import Path
import streamlit as st
import pandas as pd
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json,project_from_session_state,project_to_json
from concrete_pmm_pro.ui import analysis_page as ap,igird_coupled_model as cm,igird_member_results as mr
def loads_hash():return hashlib.sha256(pd.DataFrame(st.session_state.get('igird_uls_member_bank',[])).to_json().encode()).hexdigest()
if not st.session_state.get('_detail35_seeded'):
 apply_project_to_session_state(project_from_json(Path({str(args.project.resolve())!r}).read_text()),st.session_state)
 st.session_state['_nav_active_workspace']='Analysis';st.session_state['_nav_analysis_subpage']='ULS Strength'
 st.session_state['beam_girder_composite_flexure_stage']='Final — Composite'
 st.session_state['_detail35_seeded']=True;st.session_state['_detail35_load_hash']=loads_hash()
 st.session_state['_detail35_calls']={{'section':0,'interface':0,'coupled':0}}
st.session_state['_detail35_run']=st.session_state.get('_detail35_run',0)+1
def counted(name,original):
 def inner(*a,**k):
  st.session_state['_detail35_calls'][name]+=1
  return original(*a,**k)
 return inner
originals=mr.calculate_member,ap._igird_interface_shear_dataframe,cm.calculate
mr.calculate_member=counted('section',originals[0]);ap._igird_interface_shear_dataframe=counted('interface',originals[1]);cm.calculate=counted('coupled',originals[2])
try:runpy.run_path({str(root/'app.py')!r},run_name='__main__')
finally:mr.calculate_member,ap._igird_interface_shear_dataframe,cm.calculate=originals
conf=ap._igird_interface_shear_settings_from_state(st.session_state)
saved=json.loads(project_to_json(project_from_session_state(st.session_state)))
Path({str(snapshot.resolve())!r}).write_text(json.dumps({{'run':st.session_state['_detail35_run'],'calls':st.session_state['_detail35_calls'],'settings':conf,
 'json_settings':saved['metadata'].get(ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY),
 'edit_open':st.session_state.get('igird_flexure31_edit_inputs'), 'loads_unchanged':loads_hash()==st.session_state['_detail35_load_hash']}},allow_nan=False))
''')
        with (args.output_dir/"server.log").open("w") as log:
            server=subprocess.Popen([sys.executable,"-m","streamlit","run",str(wrapper),"--server.port","8545",
                "--server.address","127.0.0.1","--server.headless","true","--browser.gatherUsageStats","false",
                "--global.developmentMode","false","--server.fileWatcherType","none"],cwd=root,stdout=log,stderr=log)
            try:
                url="http://127.0.0.1:8545";opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(50):
                    try:
                        if opener.open(url,timeout=1).status==200:break
                    except Exception:time.sleep(.2)
                else:raise RuntimeError("Server did not start")
                with sync_playwright() as p:
                    browser=p.chromium.launch(executable_path=str(args.browser.resolve()),headless=True,args=["--no-sandbox","--disable-dev-shm-usage","--no-proxy-server"])
                    page=browser.new_page(viewport={"width":1440,"height":1100},device_scale_factor=1)
                    errors=[];page.on("pageerror",lambda error:errors.append(str(error)))
                    page.goto(url);page.get_by_role("button",name="Calculate Flexure",exact=True).wait_for(timeout=45000)
                    page.get_by_text("Edit composite / dowel inputs",exact=True).click()
                    def panel(text):return page.get_by_test_id("stExpander").filter(has=page.locator("summary").filter(has_text=text))
                    dowel=panel("Dowel detail — saved dimensions");dowel.locator("summary").first.click()
                    svg=dowel.locator("svg[data-dowel-guide]")
                    svg.wait_for();assert "170 mm" in svg.text_content() and "72 mm" in svg.text_content() and "180 mm" in svg.text_content()
                    svg.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})");page.wait_for_timeout(350)
                    page.screenshot(path=str(args.output_dir/"hook_1440.png"))
                    mesh=panel("Slab mesh — top / bottom, both directions");mesh.locator("summary").first.click()
                    table=mesh.get_by_test_id("stDataFrame").nth(1)
                    table.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})");page.wait_for_timeout(350)
                    page.screenshot(path=str(args.output_dir/"mesh_1440.png"))
                    if args.inspect_only:
                        print(json.dumps({"table":table.bounding_box(),"canvas":table.locator('canvas').first.bounding_box(),"snapshot":json.loads(snapshot.read_text())},ensure_ascii=False));return
                    def edit(row,col,text):
                        table.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})");page.wait_for_timeout(350)
                        canvas=table.locator("canvas").first;box=canvas.bounding_box()
                        x=box["x"]+box["width"]*(.23,.43,.65,.87)[col]
                        page.mouse.dblclick(x,box["y"]+36+35*row+17,delay=80)
                        entry=page.locator("input.gdg-input");entry.wait_for(timeout=5000)
                        old=json.loads(snapshot.read_text())["run"]
                        entry.fill(str(text));entry.press("Enter")
                        for _ in range(80):
                            page.wait_for_timeout(100)
                            if json.loads(snapshot.read_text())["run"]>old:break
                        else:raise AssertionError("Edit did not rerun")
                        assert json.loads(snapshot.read_text())["edit_open"]
                    # Coordinates are verified against the inspected table screenshot.
                    for args_edit in ((0,0,12),(0,1,150),(1,0,16),(1,1,200)):edit(*args_edit)
                    data=json.loads(snapshot.read_text());cfg=data["settings"]["dowel_connection"]
                    assert cfg["slab_transverse_mesh"]["top"]["Diameter_mm"]==12 and cfg["slab_transverse_mesh"]["top"]["Spacing_mm"]==150
                    assert cfg["slab_transverse_mesh"]["bottom"]["Diameter_mm"]==16 and cfg["slab_transverse_mesh"]["bottom"]["Spacing_mm"]==200
                    assert cfg["hook_top_depth_mm"]==170 and cfg["hook_inside_bend_mm"]==72 and cfg["slab_ldh_available_mm"]==180
                    assert data["settings"]==data["json_settings"] and data["loads_unchanged"]
                    assert data["calls"]=={"section":0,"interface":0,"coupled":0} and not errors
                    assert page.get_by_role("button",name="Calculate Flexure",exact=True).count()==1
                    assert page.get_by_test_id("stException").count()==0
                    page.screenshot(path=str(args.output_dir/"mesh_edited_1440.png"))
                    page.set_viewport_size({"width":1280,"height":1000});page.wait_for_timeout(400)
                    table.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})");page.wait_for_timeout(350)
                    page.screenshot(path=str(args.output_dir/"mesh_edited_1280.png"))
                    result={"status":"PASS","real_app":True,"input_only":True,"QA_mesh_values_not_user_data":True,"consecutive_edits":4,"input_panel_stays_open":True,"loads_unchanged":True,"json_matches_inputs":True,"solver_calls":data["calls"],"browser_errors":errors,"viewports":[1440,1280]}
                    (args.output_dir/"browser_review.json").write_text(json.dumps(result,indent=2));print(json.dumps(result))
                    browser.close()
            finally:server.terminate();server.wait(timeout=15)


if __name__=="__main__":main()
