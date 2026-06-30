### RESULTS.WS2 — Beam/Girder ULS Stored Results Dashboard

Connected cached Beam/Girder ULS analysis outputs into the Results workspace more completely.

#### What changed
- Added a dedicated `Beam/Girder ULS Stored Results` section in Results.
- Added four read-only dashboard cards for:
  - Flexure
  - Shear
  - Torsion
  - Shear + Torsion
- Each Beam/Girder ULS card now summarizes:
  - status
  - governing case
  - governing station/point
  - D/C or utilization
  - required action
- Added a compact Beam/Girder ULS summary table with demand, capacity/limit, D/C/utilization, and required action.
- Connected the main Governing Results Dashboard to the richer Beam/Girder ULS stored-result rows.
- Improved Results status styling so:
  - `SOURCE BLOCKED` is treated as a danger state
  - `NOT CALCULATED` is treated as a warning state, not a calculated/ready state
- Kept Results read-only: it reads cached Analysis outputs only and does not rerun PMM, ULS, SLS, shear, torsion, or V+T checks.

#### Not changed
- No Beam/Girder ULS calculation logic.
- No flexure/shear/torsion/V+T equations.
- No stored dataframe schema.
- No solver, load routing, report data model, project schema, or save/load contract.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_results_ws2_beam_uls_dashboard.py tests/test_beam_uls_vt_plot_action_polish.py tests/test_beam_uls_static_plot_size_hotfix.py tests/test_results_ws1_hotfix.py tests/test_navigation_workspace.py tests/test_app_commercial_tabs.py tests/test_ui_qa1_visual_consistency.py tests/test_analysis_modes.py
```

Targeted tests passed.
