"""Actual browser visual QA of app.py through the external checkpoint seed."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "qa/evidence/igird_rebaradvisor13/app"
OUT.mkdir(parents=True, exist_ok=True)
# Playwright is a QA dependency only; app requirements remain unchanged.
from playwright.sync_api import sync_playwright

log_path = Path(os.environ.get("CSP_UI_SERVER_LOG", "/tmp/csp_rebaradvisor13_visual.log"))
with log_path.open("w") as log:
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "qa/igird_rebaradvisor13_ui_preview.py"),
        "--server.port", "8502", "--server.address", "127.0.0.1", "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        cwd=ROOT, stdout=log, stderr=log)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen("http://127.0.0.1:8502/_stcore/health", timeout=.2)
                break
            except Exception:
                if server.poll() is not None:
                    raise RuntimeError("Streamlit visual QA server exited; inspect " + str(log_path))
                time.sleep(.2)
        with sync_playwright() as playwright:
            arguments = {"headless": True, "args": ["--no-sandbox"]}
            if os.environ.get("CSP_QA_CHROME"):
                arguments["executable_path"] = os.environ["CSP_QA_CHROME"]
            browser = playwright.chromium.launch(**arguments)
            page = browser.new_page(viewport={"width": 1680, "height": 1050}, device_scale_factor=1)
            page.goto("http://127.0.0.1:8502", wait_until="domcontentloaded")
            heading = page.get_by_text("Reinforcement advisor — ตำแหน่งและวิธีแก้ไข", exact=True)
            heading.wait_for(timeout=90000)
            assert not page.get_by_text("NameError", exact=False).count()
            page.get_by_role("button", name="Calculate trial — ตรวจชุดปลอกที่แนะนำทุกคาน", exact=True).click()
            page.get_by_text("Trial verification — ผลหลังปรับปลอก", exact=True).wait_for(timeout=90000)
            # Collapse the long action table for a focused decision screenshot.
            action = page.get_by_text("Required actions beyond stirrups — สาเหตุที่ต้องแก้ร่วมกัน", exact=True)
            action.click()
            page.wait_for_function("document.querySelectorAll('[data-testid=\"stExpander\"] details').length > 0")
            page.wait_for_timeout(500)
            heading.evaluate("el => {el.style.scrollMarginTop='80px'; el.scrollIntoView({block:'start'});}")
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / "advisor_trial_1680.png"))
            trial = page.get_by_text("Trial verification — ผลหลังปรับปลอก", exact=True)
            trial.evaluate("el => {el.style.scrollMarginTop='80px'; el.scrollIntoView({block:'start'});}")
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / "trial_results_1680.png"))
            page.set_viewport_size({"width": 1280, "height": 1000})
            heading.evaluate("el => {el.style.scrollMarginTop='80px'; el.scrollIntoView({block:'start'});}")
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / "advisor_1280.png"))
            assert page.get_by_role("button", name="Calculate trial — ตรวจชุดปลอกที่แนะนำทุกคาน", exact=True).count() == 1
            record = {"browser": browser.version, "actual_app": True, "viewport_widths": [1680, 1280],
                "screenshots": ["advisor_trial_1680.png", "trial_results_1680.png", "advisor_1280.png"],
                "single_trial_button": True, "explicit_real_trial_button_clicked": True}
            (OUT / "visual_verification.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            print(json.dumps(record), flush=True)
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
