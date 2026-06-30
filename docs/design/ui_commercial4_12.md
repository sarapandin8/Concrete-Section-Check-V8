### UI.COMMERCIAL4.12 — Promote Report / QA to Main Workspace

Promoted **Report / QA** from an Analysis subpage into a top-level workspace after Results.

#### What changed
- Added `Report / QA` as a main workspace after `Results`.
- Removed `Report / QA` from Analysis subpage navigation.
- Added a dedicated Report / QA page header and workspace dashboard cards.
- Kept Report / QA as a stored-result / traceability / readiness workspace.
- Added main routing and sidebar support for the promoted workspace.
- Updated navigation tests to reflect the new workflow hierarchy.

#### Not changed
- No PMM, ULS, SLS, deflection/camber, verification, or report generation solver logic.
- No project schema or save/load contract changes.
- No report data model changes.
- Report / QA remains read-only with respect to solver execution and does not rerun analysis solvers.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_navigation_workspace.py tests/test_app_commercial_tabs.py tests/test_ui_active_tabs1_navigation.py tests/test_ui_theme1_commercial_engineering_theme.py tests/test_analysis_modes.py tests/test_report_export_foundation.py tests/test_reporting_foundation.py tests/test_report_railway_u_girder1.py
```

Targeted tests passed.
