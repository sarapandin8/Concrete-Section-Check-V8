# UI.PMM.NAV2 — Flexural PMM result-view tabs moved up

## Scope
Move the PMM result-view selector (`Summary`, `PMM Check`, `3D Interaction`, `SLS`, and `Diagnostics / QA`) higher in the Flexural (PMM) workspace so users can choose the result view before reading lower method QA, stored snapshots, and raw diagnostics.

## Included
- Render `PMM Result Views` immediately after run/cache controls when a stored PMM result is available.
- Preserve the existing PMM dashboard implementation and cached-result behavior.
- Keep the stored calculation snapshot and lower raw/legacy diagnostics in their existing lower expanders.
- Guard against duplicate PMM dashboard rendering in the same pass.

## Engineering guardrails
- No PMM solver change.
- No demand/capacity equation change.
- No load, prestress, rebar, geometry, report, or project-schema change.
- This is a navigation/layout polish milestone only.
