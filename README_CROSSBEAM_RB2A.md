# CROSSBEAM.RB2A — Rebar Review Hardening and PT-Continuity Guard

This milestone hardens the Crossbeam RB2 input/review workspace without connecting it to any existing ULS/SLS, shear, torsion, Result Summary, Report/QA, or Project JSON solver path.

## What changed

- Replaces wide multi-template editors with a compact six-column Template Summary plus one selected-template editor.
- Keeps every modified table compact (maximum six visible columns in the main editors/audits) so users do not need horizontal scrolling to discover hidden fields.
- Separates `Auto-generated layout` from `Adopted provided reinforcement`; generated bar counts/As remain preview-only.
- Adds Section ID/name/role context directly to the compact Segment/Zone editor and keeps Purpose as a selected-zone field below the table.
- Preserves role compatibility validation: Hollow sections require Hollow/Any templates and Solid sections require Solid/Any templates.
- Adds `Enhanced markers` (default) and `True bar diameter` display modes while retaining true bar diameter for all As calculations.
- Reduces the section-rebar figure height and labels it explicitly as a longitudinal bar-location preview; transverse reinforcement is not drawn.
- Rewords every joint status to distinguish the locked ordinary-rebar rule from tendon verification:
  - ordinary rebar crossing joint = `0 mm² (LOCKED)`
  - PT continuity = `REQUIRED — NOT VERIFIED`
- Compacts Joint and Station audit tables so all decision columns are visible together.
- Combines repeated undefined-reinforcement warnings into one concise action message.

## Engineering guard

RB2A does not claim that tendons cross every joint merely because prestressing is enabled. A future Tendon System/Profile audit must verify active tendon geometry and active Aps at each joint before station-based ULS handoff may claim global continuity.

## Not changed

- No ULS/SLS, PMM, flexure, shear, torsion, prestress-loss, Result Summary, or Report/QA solver changes.
- No Project JSON schema change and no result-cache persistence.
- No changes to Railway U-Girder, Bridge/Building Beam-Girder, or Column/Pier workflows.

## Validation

- Crossbeam lineage and RB2A tests: `68 passed`.
- Geometry/Rebar/Navigation/Project JSON regression gate: `244 passed`; one unchanged baseline test failed and was reproduced in the accepted RB2 ZIP.
- Analysis/Result Summary/Report QA regression gate: `258 passed`.
