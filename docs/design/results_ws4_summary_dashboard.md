### RESULTS.WS4 — Convert Results to ULS/SLS Summary Dashboard

Converted the Results workspace from a diagram-review page into an engineering decision dashboard focused on stored ULS and SLS summaries.

#### What changed
- Added Results subpages:
  - Summary Dashboard
  - ULS Results
  - SLS Results
  - Traceability
- Removed Diagram Review from the main Results workflow.
- Summary Dashboard now focuses on:
  - overall stored result state
  - ULS/SLS completeness
  - blocking issues
  - required actions
  - next engineering action
- Added a dedicated ULS Results dashboard using cached Beam/Girder ULS outputs.
- Added a dedicated SLS Results dashboard using stored serviceability summary outputs.
- Added Required Actions table that highlights missing ULS checks, missing SLS checks, failures, blocked gates, and Report / QA readiness actions.
- Traceability subpage now contains cache/source traceability and raw stored module tables.
- Results remains read-only and does not rerun PMM, ULS, SLS, shear, torsion, V+T, or serviceability solvers.

#### Not changed
- No Beam/Girder ULS calculation logic.
- No SLS calculation logic.
- No flexure/shear/torsion/V+T equations.
- No stored dataframe schema.
- No report data model.
- No project schema or save/load contract.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_results_ws4_summary_dashboard.py tests/test_results_ws3_partial_diagram_review.py tests/test_results_ws2_beam_uls_dashboard.py tests/test_uls_vt1_torsion_below_threshold_message.py tests/test_beam_uls_vt_below_threshold_al_not_required.py tests/test_navigation_workspace.py tests/test_app_commercial_tabs.py tests/test_ui_qa1_visual_consistency.py tests/test_analysis_modes.py
```

Targeted tests passed.
