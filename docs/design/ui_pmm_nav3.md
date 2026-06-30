# UI.PMM.NAV3 — PMM Result Views immediately under Flexural

## Scope
Move the PMM result-view dashboard so the `Summary / PMM Check / 3D Interaction / SLS / Diagnostics / QA` tabs appear immediately under the `Flexural (PMM)` heading when a stored PMM result exists.

## Included
- Adds a first-screen PMM result-view render helper.
- Keeps run/cache controls, analysis setup, snapshots, and raw diagnostics below the result-view area.
- Guards against rendering the same PMM dashboard twice in the lower diagnostic flow.

## Out of scope
- No PMM solver changes.
- No D/C equation changes.
- No load-case, prestress, rebar, geometry, report, or project schema changes.
