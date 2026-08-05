# CROSSBEAM.ANALYSIS4C6B — Shared ULS station eligibility and geometry routing

## Scope

- Added one shared Crossbeam ULS station/geometry contract used by Flexure, Shear, Torsion, and Combined V+T.
- Added beam-side Column Face recovery for Flexure.
- Preserved Column Face plus prestressed `h/2` recovery for Shear, Torsion, and Combined V+T through the same row-coupled source rules.
- Exact station-force rows govern first; otherwise the route uses one-sided interpolation or limited one-sided extrapolation without crossing a support centerline.
- Ordinary B-region demand/capacity traces are omitted inside Column/support footprints.
- Added explicit PT anchorage/end-zone exclusion from ordinary ULS sectional governing.
- Added a conservative starter PT end-zone basis equal to the local end-section overall depth `h`, with optional engineer-adopted manual left/right lengths.
- Added backward-compatible Project JSON persistence for the PT end-zone basis and manual lengths.
- Added construction-mode-aware terminology and trace ownership:
  - Cast-in-Place: `ZONE INTERIOR` and `Zone-owned` traces; no physical-joint rows.
  - Precast Segmental: `SEGMENT INTERIOR` and `Segment-owned` traces; physical-joint one-sided rows remain separate and traces break at every physical joint.

## Engineering behavior

### Flexure

- Generates Column Face checks only; `h/2` is not a Flexure station rule.
- Excludes imported/generated ordinary B-region rows inside supports and PT end zones.
- Keeps Precast physical-joint and development-zone tendon-only credit unchanged.
- Breaks the capacity trace when the checked bending direction reverses; positive and negative one-direction capacities are not connected by a fictitious sloping line.

### Shear / Torsion / Combined V+T

- Use the same Column/support footprint source and the same one-sided demand-recovery rules.
- Generate Column Face and prestressed `h/2` checks.
- Cast-in-Place no longer creates physical-joint side rows from Zone boundaries.
- Precast physical-joint one-sided sectional checks and separate transfer review remain intact.
- Combined V+T reuses the already routed Shear/Torsion station set when assembling direct Flexure inputs, preventing duplicate support generation or inconsistent station ownership.

## UI / chart behavior

- Added `ULS station eligibility / PT end zones` controls in the Analysis workspace.
- Shows the active construction-mode trace ownership and the adopted left/right PT end-zone boundaries.
- Shades support footprints and PT end zones while clipping ordinary B-region line traces from those excluded regions.
- Shows Column Face and `h/2` evidence only where applicable.
- Provides an audit table for rows excluded as `PT END ZONE / D-REGION — REVIEW`.

## Engineering impact

- No ACI Flexure, Shear, Torsion, or Combined V+T resistance equation changed.
- No strength-reduction factor changed.
- No prestress-loss equation changed.
- No ordinary-rebar joint/development credit rule changed.
- Project JSON was extended only with backward-compatible PT end-zone settings; no schema-version migration was required.
- Station eligibility, source recovery, result fingerprints, and chart semantics changed intentionally.

## Tests

- `python -m compileall -q app.py concrete_pmm_pro tests` — PASS.
- Crossbeam Analysis suites — 101 passed.
- Complete Crossbeam test inventory executed in chunks — 624 passed, 6 failed.
- All 6 failures were reproduced unchanged in the accepted `ANALYSIS4C6A` baseline and are pre-existing source-string/test-count assertions outside this milestone:
  - 1 Rebar editor-count assertion expects 7 editors while the accepted page contains 8.
  - 2 PTLOSS4B2B1 source-string assertions expect obsolete milestone wording.
  - 3 Effective Prestress handoff source-string assertions expect wording no longer present in the accepted baseline.

## Repo summary

Add a shared construction-mode-aware Crossbeam ULS station and geometry contract with Column Face/h/2 routing, PT end-zone exclusion, support-footprint trace gaps, and consistent CIP Zone versus Precast Segment ownership without changing resistance equations.
