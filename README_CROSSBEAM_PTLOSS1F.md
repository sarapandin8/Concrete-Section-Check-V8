# CROSSBEAM.PTLOSS1F - Regression Baseline Lock

## Scope

Locks the accepted Crossbeam PTLOSS1E baseline by repairing three stale regression assertions without changing production behavior, solver equations, prestress-force logic, Project JSON, routing, session-state behavior, reports, rebar logic, or any member workflow runtime.

## QA contract updates

- Tendon-profile import schema regression now validates the stable `dtop (mm)` column/required contract without coupling correctness to prose wording in the Description field.
- Crossbeam navigation regression now recognizes the intentionally added `Prestress Loss` page introduced by PTLOSS1.
- Railway U-Girder closeout regression now verifies that the historical closeout milestone remains documented in the global README without incorrectly requiring it to be the newest top heading.

## Production-code boundary

No production Python files are changed in this milestone. Solver equations, `Pe_eff`, PMM, SLS/ULS, prestress-loss calculations, rebar, reporting logic, Project JSON, and runtime member-workflow behavior are unchanged.

## Validation intent

This milestone does not weaken engineering checks or modify formulas to satisfy tests. It removes assertions that had become stale because later accepted milestones changed documentation order or intentionally extended navigation while preserving the underlying engineering/data contracts.

## Verification results

- `python -m compileall -q app.py concrete_pmm_pro tests`: PASS.
- Targeted PTA1/PTLOSS1/PTQA4/UI1A/Railway closeout regression set: 44 passed.
- Crossbeam regression suite (`tests/test_crossbeam_*.py`): 198 passed.
- Non-Crossbeam suite was executed in file batches to avoid runtime timeout: 1,834 passed and 4 known pre-existing failures reproduced unchanged on the PTLOSS1E baseline.

Known pre-existing failures intentionally not modified in PTLOSS1F:

1. `tests/test_railway_u_girder_rebar_enable_routing.py::test_rebar_enable1_section_builder_checkbox_synchronizes_metadata_on_change`
2. `tests/test_rebar_inclusion_visual_regression.py::test_inclusion4_bridge_precast_girder_defaults_store_rebars_but_publish_none`
3. `tests/test_regression_controls.py::test_app_does_not_reintroduce_sidebar_geometry_parameters`
4. `tests/test_results_ws2_beam_uls_dashboard.py::test_results_source_blocked_is_treated_as_danger_status`

These four failures pre-date PTLOSS1F and were reproduced against the untouched PTLOSS1E baseline. They are retained as separate QA debt rather than being silently changed outside this milestone scope.
