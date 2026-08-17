# CROSSBEAM.ANALYSIS4C7D29 — Final Service Default / Review Wording Polish

## Scope

D29 is a Final-Service SLS Deflection / Camber UI-semantic closeout. It does not change displacement evaluation, support-chord or overhang response equations, L/n or Lo/n limits, stage ownership, result fingerprints, Project JSON persistence, or governing calculations from D28.

## Changes

- Distinguishes the **current project selection** from the **new-project general-practice default** below both Final-Service criterion selectors.
- When a project preserves `Review only`, the UI now states that explicitly rather than presenting `L/360` / `Lo/180` as though they were active.
- Keeps `L/360` for support spans and `Lo/180` for overhangs as new-project defaults without overwriting a stored/current engineer selection.
- Updates the Acceptance Basis card detail so a preserved non-default criterion is not described as the active default.
- When Final Service status is `REVIEW`, the status card now states the reason directly: missing support-span L/n, missing overhang Lo/n, or both.
- PASS/FAIL Final-Service result semantics remain unchanged.

## Engineering intent

`Review only` is an intentional project selection, not a failed default assignment. D29 makes that distinction visible at the decision point and on the result card while preserving engineer-selected criteria and all existing serviceability calculations.

## Validation

- `compileall`: PASS for `concrete_pmm_pro`.
- Focused D17–D29 regression: 52 tests PASS.
- Dedicated D29 semantic tests: 4 PASS.
- Full repository suite: not run.

**Repo summary:** Clarify Final-Service Deflection/Camber UI by separating current project criteria from L/360/Lo/180 new-project defaults and showing the explicit reason whenever the stage remains REVIEW.
