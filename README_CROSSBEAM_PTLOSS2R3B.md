# CROSSBEAM.PTLOSS2R3B — Prestress Loss Rerun Performance Hotfix

PTLOSS2R3B is a performance-only hotfix built directly from the accepted PTLOSS2R3A baseline. It removes the heavy independent dense-grid both-end QA solve from the normal Streamlit rerun path without changing accepted friction/wobble or anchorage-set solver equations and without releasing `Pe` / `Pe_eff`.

## Root cause

PTLOSS2R3A executed `independent_both_end_dense_grid_validation()` synchronously on every Prestress Loss rerun, before the component subtabs were rendered. The default eight-tendon simultaneous-both-end model therefore repeated a full 8,000-step-per-tendon independent validation even when the user only changed the displayed tendon, switched component tabs, or triggered another ordinary Streamlit rerun.

A default-case timing benchmark in the development environment measured approximately:

- production prestress-loss path (friction → anchorage set → station rows → equivalent average): **0.016 s**;
- full independent dense-grid QA: **15.99 s**.

The heavy QA path was therefore roughly **980×** slower than the normal component calculation and was the dominant avoidable rerun cost.

## Scope

- Removes the independent dense-grid validator from the eager `render_crossbeam_prestress_loss_page()` calculation path.
- Adds an explicit `Run / Refresh Independent Both-End Validation` action inside the Formula / SI QA area.
- Keeps the full 8,000-step independent validation fidelity unchanged when the user explicitly runs it.
- Stores QA evidence only in workflow-scoped Streamlit session state; it is not added to Project JSON or final design results.
- Adds a SHA-256 input fingerprint covering the current friction trace, anchorage-set end results, member length, adopted `Δa`, and `Ep`.
- Reuses independent QA evidence only when the fingerprint exactly matches the current inputs.
- If relevant inputs change, the previous QA result is treated as **STALE**, is not shown as current PASS evidence, and the UI requires an explicit refresh.
- Normal tendon-selection and subtab reruns therefore retain the fast production calculation path without silently weakening the independent QA method.

## Solver / workflow boundary

Unchanged from PTLOSS2R3A:

- friction/wobble equations and station-force route;
- single-end anchorage-set reverse-slip equations;
- simultaneous-both-end anchorage-set local/coupled equations;
- equivalent-average anchorage-set calculation;
- independent validator numerical fidelity when explicitly run;
- tendon `Pj` source and `tendon_analysis.py`;
- `Pe` / `Pe_eff` (still locked);
- Elastic Shortening and Time-Dependent Losses;
- PMM, SLS/ULS, rebar, reporting, shared routing, and non-Crossbeam workflows.

## Verification performed

- Python compile / compileall: PASS.
- PTLOSS1 + PTLOSS2R3B targeted regression: **36 passed**.
- Complete Crossbeam regression: **224 passed**.
- Cross-workflow split smoke: **578 passed** across Project/IO, routing/source-of-truth, existing girder prestress, serviceability, reporting/Word export, PMM benchmarks/dashboard, and validation guards.
- Performance architecture regression confirms the heavy independent validator is not called directly from `render_crossbeam_prestress_loss_page()` and is gated behind the explicit button action.
- Full repository suite was not rerun in one complete pass for this hotfix.
