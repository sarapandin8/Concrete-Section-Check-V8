# UI.ACTION.BUTTONS2 — Run button state and compact runtime control

## Scope
Polish the Flexural (PMM) runtime controls without changing solver equations, analysis readiness rules, D/C extraction, or project data.

## Changes
- Run button is highlighted only when the analysis input is available.
- Disabled Run state is muted/gray rather than amber, so it does not look ready to execute.
- Runtime status is displayed in compact cards instead of large metric blocks.
- Sweep, run status, runtime, cache state, and solver guard remain visible.
- Blocking reasons are displayed clearly when analysis readiness prevents Run.

## Out of scope
- PMM solver logic.
- Analysis readiness logic.
- D/C calculation.
- Geometry, rebar, prestress, loads, reporting, and save/load behavior.
