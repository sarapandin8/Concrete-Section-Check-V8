### UI.QA1 — Commercial UI Visual Consistency Sweep

Performed a non-solver visual consistency sweep after the UI.COMMERCIAL4 series.

#### What changed
- Added a commercial Results workspace foundation instead of a plain placeholder info box.
- Results now uses the same commercial page header, metric-card, and section-bar language as the other major workspaces.
- Kept Results as a read-only stored-output workspace:
  - opening Results does not rerun PMM
  - opening Results does not rerun ULS
  - opening Results does not rerun SLS
- Added a UI.QA1 regression test suite covering:
  - main workspace order
  - Report / QA promoted after Results
  - Results commercial read-only foundation
  - Analysis no longer contains Report / QA as a subpage
  - shared section preview title/legend guards
  - Rebar Auto perimeter 50 mm default

#### Not changed
- No solver equations.
- No PMM / ULS / SLS calculations.
- No load routing.
- No rebar layout generation algorithm.
- No section geometry or property calculations.
- No report data model.
- No project schema or save/load contract.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/visualization/section_plot.py concrete_pmm_pro/ui/rebar_page.py
pytest -q tests/test_ui_qa1_visual_consistency.py tests/test_navigation_workspace.py tests/test_app_commercial_tabs.py tests/test_ui_active_tabs1_navigation.py tests/test_ui_theme1_commercial_engineering_theme.py tests/test_section_preview_canvas_qa.py tests/test_rebar_auto_perimeter_apply_hotfix.py
```

Targeted tests passed.
