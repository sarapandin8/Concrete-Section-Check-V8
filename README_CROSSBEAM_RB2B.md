# CROSSBEAM.RB2B — Rebar Template Management and Count/Spacing Layout

This milestone extends the Crossbeam-only RB2A input/review workspace so engineers can create, duplicate, edit, and safely delete project Rebar Templates without widening the compact summary tables or connecting any template data to existing solvers.

## What changed

- Adds low-effort Template actions:
  - `Duplicate selected`
  - `New Hollow`
  - `New Solid`
  - guarded `Delete template`
- Generates stable project Template IDs automatically (`RB-H##` and `RB-S##`) so Segment/Zone references are not renamed accidentally.
- Blocks deletion while a Template is assigned to any Rebar Zone and lists the blocking Zone IDs.
- Preserves the compact six-column read-only Template Summary so all summary fields remain visible without horizontal scrolling.
- Keeps detailed editing in one selected-template panel below the summary table.
- Adds two graphical longitudinal-bar layout methods for Outer and Inner faces:
  - `By target spacing`
  - `By exact bar count`
- Exact-count generation retains section corner/control bars, applies existing spacing/geometry guards, and reports a review error if the requested exact count cannot be maintained.
- Keeps Outer and Inner layout controls separate and automatically disables Inner-face controls for Solid-only Templates.
- Preserves the existing `Adopted provided reinforcement` fields as a separate engineering input; auto-generated layout and As remain preview-only.
- Retains a guarded reset-to-default action inside a collapsed confirmation panel.

## Engineering guards

- Ordinary rebar crossing every segment joint remains locked to `0 mm²`.
- PT continuity remains `REQUIRED — NOT VERIFIED` until Tendon System/Profile audit is connected.
- A Template may be credited only inside its assigned Segment/Zone.
- Generated bars are not code-minimum design output and do not populate ULS/SLS solver reinforcement.

## Not changed

- No ULS/SLS, PMM, flexure, shear, torsion, prestress-loss, Result Summary, or Report/QA solver changes.
- No Project JSON schema change and no result-cache persistence.
- No changes to Railway U-Girder, Bridge/Building Beam-Girder, or Column/Pier workflows.

## Validation

- Crossbeam lineage including RB2B: `72 passed`.
- Navigation, Section Builder, geometry, Project JSON, Rebar/Prestress, and workflow regression gate: `183 passed`.
- Analysis, Result Summary, and Report/QA gate: `183 passed, 1 unchanged baseline static-source failure` (the same test is unrelated to the three RB2B source files).
