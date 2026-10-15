"""Real local Streamlit UI and Plotly inspection, isolated input-only bootstrap."""
import argparse
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8533)
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="csp-flexure31-") as folder:
        wrapper = Path(folder) / "browser_app.py"
        wrapper.write_text(f'''from pathlib import Path
import runpy,sys
import streamlit as st
sys.path.insert(0,{str(root)!r})
from concrete_pmm_pro.io.project_io import apply_project_to_session_state,project_from_json
if not st.session_state.get('_flexure31_browser_inputs'):
    apply_project_to_session_state(project_from_json(Path({str(args.project.resolve())!r}).read_text()),st.session_state)
    st.session_state['_nav_active_workspace']='Analysis'
    st.session_state['_nav_analysis_subpage']='ULS Strength'
    st.session_state['beam_girder_composite_flexure_stage']='Final — Composite'
    st.session_state['_flexure31_browser_inputs']=True
runpy.run_path({str(root/'app.py')!r},run_name='__main__')
''')
        with (args.output_dir / "browser-server.log").open("w") as log:
            process = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(wrapper),
                "--server.port", str(args.port), "--server.address", "127.0.0.1",
                "--server.headless", "true", "--browser.gatherUsageStats", "false"],
                cwd=root, stdout=log, stderr=log)
            try:
                url = f"http://127.0.0.1:{args.port}"
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(40):
                    try:
                        if opener.open(url, timeout=1).status == 200: break
                    except Exception: time.sleep(.25)
                else: raise RuntimeError("Local Streamlit server did not start")
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=str(args.browser.resolve()),
                        headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--no-proxy-server"])
                    page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
                    page_errors = []; page.on("pageerror", lambda e: page_errors.append(str(e)))
                    page.goto(url)
                    calculate = page.get_by_role("button", name="Calculate Flexure", exact=True)
                    calculate.wait_for(timeout=30000)
                    assert page.get_by_role("button", name=re.compile(r"^Calculate")).count() == 1
                    calculate.click()
                    chart = page.locator(".js-plotly-plot")
                    chart.first.wait_for(timeout=90000)
                    page.get_by_text("Session results only.", exact=False).wait_for(timeout=30000)
                    assert chart.count() == 1

                    def figure():
                        return chart.first.evaluate("e => ({title:e.layout.title.text,meta:e.layout.meta,range:e.layout.xaxis.range, traces:e.data.map(t=>({name:t.name,x:Array.from(t.x||[]),y:Array.from(t.y||[])}))})")

                    def select(label, value):
                        control = page.get_by_test_id("stSelectbox").filter(has=page.get_by_text(label, exact=True))
                        control.get_by_role("combobox").click()
                        page.get_by_role("option", name=value, exact=True).click()

                    def radio(value):
                        # Streamlit's visible label owns the hit target; its
                        # tiny input can sit under the label or sticky header.
                        label = page.get_by_role("radio", name=value, exact=True).locator("xpath=ancestor::label[1]")
                        label.evaluate("e => e.scrollIntoView({block:'center'})")
                        label.click()

                    default = figure()
                    assert "Left Exterior Girder" in default["title"]
                    assert default["meta"]["igird_maxmin_assessment_scope"] == "Span scope; cut ends separate"
                    assert default["meta"]["unavailable_capacity"][0]["x_m"] == 20
                    chart.first.screenshot(path=str(args.output_dir / "default_chart.png"))
                    page.get_by_text("Final Composite Flexure", exact=True).scroll_into_view_if_needed()
                    page.screenshot(path=str(args.output_dir / "workspace_1440.png"))
                    radio("CSI source M3")
                    page.wait_for_function("() => document.querySelector('.js-plotly-plot')?.layout?.meta?.flexure31_reference === 'ORIGINAL CSI'")
                    source = figure()
                    ends = [y for t in source["traces"] if t["name"].startswith("M3") for x, y in zip(t["x"], t["y"]) if x in (0, 20)]
                    assert ends and all(y == 0 for y in ends)
                    assert not any("φMn" in t["name"] for t in source["traces"])
                    chart.first.screenshot(path=str(args.output_dir / "source_m3_chart.png"))
                    radio("Demand / capacity")
                    page.wait_for_function("() => document.querySelector('.js-plotly-plot')?.layout?.meta?.igird_maxmin_assessment_scope === 'Span scope; cut ends separate'")
                    radio("Min")
                    page.wait_for_function("() => document.querySelector('.js-plotly-plot')?.layout?.meta?.igird_maxmin_step === 'Min'")
                    assert chart.count() == 1
                    radio("Max")
                    page.wait_for_function("() => document.querySelector('.js-plotly-plot')?.layout?.meta?.igird_maxmin_step === 'Max'")
                    select("View range", "Right end")
                    page.wait_for_function("() => document.querySelector('.js-plotly-plot')?.layout?.meta?.flexure31_focus === 'Right end'")
                    assert figure()["range"][1] > 20
                    assert figure()["meta"]["igird_maxmin_assessment_scope"] == "Span scope; cut ends separate"
                    chart.first.screenshot(path=str(args.output_dir / "right_end_chart.png"))
                    select("View range", "Full member")
                    page.wait_for_function("() => document.querySelector('.js-plotly-plot')?.layout?.meta?.flexure31_focus === 'Full member'")
                    page.set_viewport_size({"width": 1280, "height": 1000})
                    chart.first.scroll_into_view_if_needed()
                    chart.first.screenshot(path=str(args.output_dir / "chart_1280.png"))
                    page.get_by_text("End moments — CSI source / design reference", exact=True).click()
                    page.screenshot(path=str(args.output_dir / "end_reference_audit.png"))
                    assert not page.get_by_test_id("stException").count() and not page_errors, page_errors
                    assert page.get_by_role("button", name=re.compile(r"^Calculate")).count() == 1
                    record = {"version": "IGIRDER.FLEXURE31", "browser": browser.version,
                        "actual_Streamlit_app": True, "input_only_bootstrap": True,
                        "real_calculate_click": True, "calculate_buttons": 1, "default_charts": 1,
                        "max_min_switch": True, "source_M3_exterior_ends_zero": True,
                        "source_view_has_no_wrong_origin_capacity": True,
                        "gap_explanation_and_right_end_view": True, "viewports": [1440, 1280],
                        "separate_end_scope_retained_after_view_changes": True,
                        "page_errors": page_errors, "streamlit_exceptions": 0,
                        "visual_inspection": "Pending image inspection"}
                    (args.output_dir / "FLEXURE31_browser_review.json").write_text(json.dumps(record, indent=2) + "\n")
                    print(json.dumps(record, indent=2), flush=True)
                    browser.close()
            finally:
                process.terminate()
                process.wait(timeout=15)


if __name__ == "__main__": main()
