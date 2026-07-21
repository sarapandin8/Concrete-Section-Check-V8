# CROSSBEAM.PTLOSS2R3A — Force-Profile Visualization & Validation Evidence Hotfix

PTLOSS2R3A is a visualization/QA closeout hotfix built directly from the accepted PTLOSS2R3 baseline. It does **not** change friction/wobble or anchorage-set solver equations and does not release `Pe` / `Pe_eff`.

## Scope

- Explicitly sets the Anchorage Set force-profile Y-axis from all plotted force series (`Reference Pj`, `After Friction & Wobble`, and `After Anchorage Set`) with engineering margin so the post-seating curve cannot be clipped from the chart/print view.
- Adds a selected-tendon three-point numerical QA table at Left anchorage, the neutral/characteristic station, and Right anchorage so the graph can be checked against numerical force values.
- Adds an independent dense-grid simultaneous-both-end verification module that reconstructs the accepted left/right friction branches and re-solves bilateral seating compatibility without calling the production anchorage-set interpolation, area, or coupled-solver helpers.
- Exposes independent-verifier differences and adopted tolerances in the Formula / SI audit, with per-tendon evidence available in a collapsed expander.
- Keeps local station `P(s)` as the Crossbeam design-use source of truth; equivalent-average loss remains summary/external-lumped-loss QA only.

## Solver / workflow boundary

Unchanged from PTLOSS2R3:

- friction/wobble equations and accepted station-force route;
- single-end reverse-slip anchorage-set solver equations;
- simultaneous-both-end local/coupled anchorage-set solver equations;
- tendon `Pj` source and `tendon_analysis.py`;
- `Pe` / `Pe_eff` (still locked);
- Elastic Shortening and Time-Dependent Losses;
- PMM, SLS/ULS, rebar, reporting, shared routing, and all non-Crossbeam workflows.

## QA intent

PTLOSS2R3A closes a presentation defect discovered in printed QA output where the `After Anchorage Set` curve could fall below Plotly's displayed Y-range. The independent verifier is evidence-only and intentionally implemented outside the production anchorage-set solver path.

## Verification performed

- Python compile / compileall: PASS.
- PTLOSS1 + PTLOSS2R3A targeted regression: 35 passed.
- Complete Crossbeam regression: 223 passed.
- Cross-workflow smoke covering Project/IO, existing girder prestress, serviceability, reports, PMM benchmarks/dashboard, validation, Railway U-Girder SLS, and routing: 441 passed.
- Full non-Crossbeam repository suite was not rerun in one complete pass for this hotfix.
