### RESULTS.WS4.1 — Clarify Overall Result State and V+T Demand Display

Polished Results Summary Dashboard wording after RESULTS.WS4.

#### What changed
- Changed executive result state so it does not claim `Full stored results available` when SLS is missing.
- When all Beam/Girder ULS checks are calculated but SLS is not available, the dashboard now shows:
  `ULS complete / SLS pending`
- Added explicit detail:
  `All Beam/Girder ULS checks have stored results. SLS serviceability is not calculated yet.`
- Changed the fully-ready message to:
  `Stored ULS/SLS summaries available`
- Improved Results demand display:
  - Torsion demand now shows `Tu = ... kN-m`
  - Shear + Torsion demand now shows `Vu = ... kN; Tu = ... kN-m`
- Added regression tests for the new status wording and V+T demand formatting.

#### Not changed
- No calculation logic.
- No ULS / SLS / PMM solver logic.
- No flexure/shear/torsion/V+T equations.
- No stored dataframe schema.
- No report data model.
- No project schema or save/load contract.

#### Validation run
```bash
python -m py_compile app.py concrete_pmm_pro/ui/analysis_page.py
pytest -q tests/test_results_ws4_1_state_vt_demand.py tests/test_results_ws4_summary_dashboard.py tests/test_results_ws3_partial_diagram_review.py tests/test_results_ws2_beam_uls_dashboard.py tests/test_uls_vt1_torsion_below_threshold_message.py tests/test_beam_uls_vt_below_threshold_al_not_required.py tests/test_navigation_workspace.py tests/test_app_commercial_tabs.py tests/test_ui_qa1_visual_consistency.py tests/test_analysis_modes.py
```

Targeted tests passed.
