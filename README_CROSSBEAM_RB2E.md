# CROSSBEAM.RB2E — Linked Rebar Grade Dropdown Hotfix

## Scope

- Keeps both `fy (MPa)` and `Material` as editable dropdowns in the compact Crossbeam Rebar Template table.
- Selecting `390` immediately resolves the row to `SD40`.
- Selecting `490` immediately resolves the row to `SD50`.
- Selecting `SD40` immediately resolves the row to `390 MPa`.
- Selecting `SD50` immediately resolves the row to `490 MPa`.
- Refreshes only the Crossbeam template-editor widget key after a linked change, preventing a visually stale companion cell.
- Does not change Segment/Zone assignments, rebar geometry generation, adopted reinforcement, solver handoff, joint rules, Project JSON, or any other Active Member Workflow.

## Engineering guard

Ordinary rebar crossing each segment joint remains locked to `0 mm²`; PT continuity remains `REQUIRED — NOT VERIFIED`.
