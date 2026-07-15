# CROSSBEAM.RB2D — Editable Template IDs and Linked Rebar Grade Dropdowns

This workflow-scoped milestone makes Crossbeam Rebar Template IDs engineer-editable while preserving every Segment / Zone reference, and replaces free-form rebar material/strength inputs with linked dropdowns.

## What changed

- `Template ID` is editable directly in the compact Template identity table.
- IDs are normalized to uppercase reference-safe text; spaces become hyphens.
- Renaming a Template ID atomically updates every `Segment / Zone` assignment that references it.
- Duplicate or blank Template IDs are blocked before any reference is changed.
- `fy (MPa)` is a dropdown limited to `390` and `490`.
- `Material` is a dropdown limited to `SD40` and `SD50`.
- The dropdown pair is linked:
  - `SD40 ↔ fy = 390 MPa`
  - `SD50 ↔ fy = 490 MPa`
- Changing either field updates the paired field; inconsistent simultaneous edits are normalized visibly.
- Resetting Rebar Zones now selects available compatible template IDs, so renamed default IDs are not replaced by stale hard-coded references.

## Scope guards retained

- Ordinary rebar crossing every segment joint remains locked at `0 mm²`.
- PT continuity remains `REQUIRED — NOT VERIFIED` until Tendon System/Profile audit is connected.
- No ULS/SLS, flexure, shear, torsion, prestress-loss, Result Summary, Report/QA, or Project JSON solver behavior was changed.
- Other Active Member Workflows remain on their existing Rebar behavior.

## Validation

- Python compilation passed.
- Crossbeam regression suite passed.
- Targeted Template-ID reference and material/fy linkage tests passed.
