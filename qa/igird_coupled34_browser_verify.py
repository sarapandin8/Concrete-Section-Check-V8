"""Actual app.py, real solvers, explicit synthetic detail and viewport checks."""
import argparse
import json
from pathlib import Path
import re
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
    parser.add_argument("--port",type=int,default=8538)
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]
    snapshot=args.output_dir/"session_snapshot.json"
    with tempfile.TemporaryDirectory(prefix="csp-coupled34-") as temp:
        wrapper=Path(temp)/"browser_app.py"
        wrapper.write_text(f'''from pathlib import Path
import runpy,sys,json,hashlib
import streamlit as st
import pandas as pd
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
from concrete_pmm_pro.ui import analysis_page as ap,igird_coupled_model as cm,igird_member_results as mr,igird_flexure_workspace as fw
from concrete_pmm_pro.ui.igird_flexure_gap_review import missing_capacity_table
from qa.igird_coupled34_fixture import configure_hypothesis
def load_hash():
    return hashlib.sha256(pd.DataFrame(st.session_state.get('igird_uls_member_bank',[])).to_json().encode()).hexdigest()
if not st.session_state.get('_coupled34_qa_seeded'):
    apply_project_to_session_state(project_from_json(Path({str(args.project.resolve())!r}).read_text()),st.session_state)
    st.session_state['_coupled34_load_hash']=load_hash()
    configure_hypothesis(st.session_state)
    st.session_state['_nav_active_workspace']='Analysis'
    st.session_state['_nav_analysis_subpage']='ULS Strength'
    st.session_state['beam_girder_composite_flexure_stage']='Final — Composite'
    st.session_state['_coupled34_qa_seeded']=True
    st.session_state['_coupled34_calls']={{'section':0,'interface':0,'coupled':0}}
st.session_state['_coupled34_runs']=st.session_state.get('_coupled34_runs',0)+1
def count(name,original):
    def wrapped(*a,**k):
        calls=dict(st.session_state['_coupled34_calls']);calls[name]+=1;st.session_state['_coupled34_calls']=calls
        return original(*a,**k)
    return wrapped
original_section,original_interface,original_coupled=mr.calculate_member,ap._igird_interface_shear_dataframe,cm.calculate
mr.calculate_member=count('section',original_section)
ap._igird_interface_shear_dataframe=count('interface',original_interface)
cm.calculate=count('coupled',original_coupled)
try:
    runpy.run_path({str(root/'app.py')!r},run_name='__main__')
finally:
    mr.calculate_member,ap._igird_interface_shear_dataframe,cm.calculate=original_section,original_interface,original_coupled
reviews=[]
for name,entry in st.session_state.get(fw.CACHE_KEY,{{}}).items():
    bundle=entry['bundle'];research=bundle.get('coupled_research',{{}});frame=pd.DataFrame(research.get('rows',[]))
    gaps=missing_capacity_table(bundle['section'].get('flexure_preview_df'))
    reviews.append({{'member':name,'research_rows':len(frame),'numeric_model_rows':int(pd.to_numeric(frame.get('Model Tn (kN-m)',pd.Series(dtype=float)),errors='coerce').notna().sum()),
        'production':research.get('production_status'),'gap_rows':json.loads(gaps.to_json(orient='records')),
        'model_Tn_max':float(pd.to_numeric(frame.get('Model Tn (kN-m)',pd.Series(dtype=float)),errors='coerce').max()) if not frame.empty else None}})
Path({str(snapshot.resolve())!r}).write_text(json.dumps({{'run':st.session_state['_coupled34_runs'],'calls':st.session_state['_coupled34_calls'],
    'load_hash_unchanged':load_hash()==st.session_state['_coupled34_load_hash'],'settings':cm.settings(st.session_state),'reviews':reviews}},allow_nan=False))
''')
        with (args.output_dir/"browser-server.log").open("w") as log:
            server=subprocess.Popen([sys.executable,"-m","streamlit","run",str(wrapper),"--server.port",str(args.port),
                "--server.address","127.0.0.1","--server.headless","true","--browser.gatherUsageStats","false",
                "--global.developmentMode","false","--server.fileWatcherType","none"],cwd=root,stdout=log,stderr=log)
            try:
                url=f"http://127.0.0.1:{args.port}"
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(50):
                    try:
                        if opener.open(url,timeout=1).status==200:break
                    except Exception:time.sleep(.2)
                else:raise RuntimeError("Local server did not start")
                with sync_playwright() as p:
                    browser=p.chromium.launch(executable_path=str(args.browser.resolve()),headless=True,
                        args=["--no-sandbox","--disable-dev-shm-usage","--no-proxy-server"])
                    page=browser.new_page(viewport={"width":1440,"height":1100},device_scale_factor=1)
                    errors=[];page.on("pageerror",lambda e:errors.append(str(e)))
                    page.goto(url)
                    calculate=page.get_by_role("button",name="Calculate Flexure",exact=True)
                    calculate.wait_for(timeout=40000)
                    assert page.get_by_role("button",name=re.compile(r"^Calculate")).count()==1
                    calculate.click()
                    chart=page.locator(".js-plotly-plot")
                    chart.first.wait_for(timeout=120000)
                    page.get_by_text("Session results only.",exact=False).wait_for(timeout=30000)
                    assert chart.count()==1
                    data=json.loads(snapshot.read_text())
                    assert data["calls"]=={"section":2,"interface":2,"coupled":2},data["calls"]
                    assert data["load_hash_unchanged"]
                    assert len(data["reviews"])==2
                    assert all(r["production"]=="UNVALIDATED — REVIEW" and r["numeric_model_rows"]>0 for r in data["reviews"])
                    exterior=next(r for r in data["reviews"] if "Exterior" in r["member"])
                    end=next(r for r in exterior["gap_rows"] if r["Load case"]=="U1A" and r["x (m)"]==20.)
                    assert end["CSI P (kN)"]==.795 and end["All strand credit zero"] and end["All ordinary bar credit zero"]
                    meta=chart.first.evaluate("e=>e.layout.meta")
                    assert any(row["x_m"]==20 for row in meta["unavailable_capacity"])
                    detail=page.get_by_test_id("stExpander").filter(has=page.locator("summary").filter(has_text="Why φMn is missing"))
                    detail.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})")
                    page.wait_for_timeout(300);page.screenshot(path=str(args.output_dir/"gap_reason_1440.png"))
                    title=page.get_by_text("Composite V–T — coupled resistance / validation",exact=True)
                    title.evaluate("e=>e.scrollIntoView({block:'start',behavior:'instant'})")
                    page.wait_for_timeout(300);page.screenshot(path=str(args.output_dir/"coupled_model_1440.png"))
                    toggle=page.get_by_text("Edit composite / dowel inputs",exact=True)
                    toggle.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})")
                    page.wait_for_timeout(300)
                    toggle.click()
                    panel=page.get_by_test_id("stExpander").filter(has=page.locator("summary").filter(has_text="Composite V–T — research model inputs"))
                    panel.locator("summary").filter(has_text="Composite V–T — research model inputs").click()
                    table=panel.get_by_test_id("stDataFrame").first
                    edits=[]
                    for row,value in [(0,16.),(1,200.),(2,950.)]:
                        canvas=table.locator("canvas").first
                        canvas.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})");page.wait_for_timeout(350)
                        box_=canvas.bounding_box();old=json.loads(snapshot.read_text())["run"]
                        page.mouse.dblclick(box_["x"]+.86*box_["width"],box_["y"]+36+35*row+17)
                        editor=page.locator("input.gdg-input");editor.wait_for(timeout=5000)
                        editor.fill(str(value));editor.press("Enter")
                        for _ in range(80):
                            if json.loads(snapshot.read_text())["run"]>old:break
                            page.wait_for_timeout(100)
                        else:raise AssertionError("Editor did not rerun")
                        page.wait_for_timeout(300)
                        current=json.loads(snapshot.read_text());edits.append(current["settings"])
                        assert current["calls"]==data["calls"] and current["load_hash_unchanged"]
                    current=json.loads(snapshot.read_text())
                    assert [current["settings"][k] for k in ("closure_db_mm","closure_spacing_mm","lap_available_mm")]==[16.,200.,950.]
                    assert panel.locator("details").first.get_attribute("open") is not None
                    assert chart.count()==1
                    page.get_by_text("Composite research results are missing or stale.",exact=False).wait_for(timeout=10000)
                    for width in (1440,1280):
                        page.set_viewport_size({"width":width,"height":1100})
                        panel.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})")
                        page.wait_for_timeout(400);page.screenshot(path=str(args.output_dir/f"research_inputs_{width}.png"))
                        assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
                    assert not errors and page.get_by_test_id("stException").count()==0
                    assert page.get_by_role("button",name=re.compile(r"^Calculate")).count()==1
                    record={"version":"IGIRDER.COUPLED34","fixture":"SYNTHETIC U-detail/closure only; not actual project acceptance",
                        "main_calculate_clicks":1,"actual_member_calculations":data["calls"],"default_charts":1,
                        "cut_end_gap_20m_retained":True,"end_development_reason_verified":True,
                        "research_model_numeric_rows":sum(r["numeric_model_rows"] for r in data["reviews"]),
                        "production_acceptance":"WITHHELD","input_edits_retained":3,"edit_panel_stayed_open":True,
                        "review_solver_calls":0,"new_model_input_stales_only_research":True,
                        "raw_loads_unchanged":True,"viewports":[1440,1280],"browser_errors":errors}
                    (args.output_dir/"COUPLED34_browser_review.json").write_text(json.dumps(record,indent=2)+"\n")
                    print(json.dumps(record))
                    browser.close()
            finally:
                server.terminate()
                try:server.wait(timeout=10)
                except subprocess.TimeoutExpired:server.kill()


if __name__=="__main__": main()
