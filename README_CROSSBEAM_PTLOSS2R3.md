# CROSSBEAM.PTLOSS2R3 — Anchorage Set Equivalent-Average QA & Closeout Polish

PTLOSS2R3 preserves the accepted PTLOSS2R2 single-end and simultaneous-both-end anchorage-set solver equations and adds an explicit equivalent-average QA layer so local tendon-force losses are no longer confused with member/global representative losses.

## Engineering / product changes

- Keeps station-specific post-seating tendon force `P(s)` as the Crossbeam design-use source of truth.
- Adds a distribution-equivalent average anchorage-set stress loss for each tendon:

  `ΔfpA,avg = (1/L) ∫ ΔfpA(s) ds`

- Adds an area-weighted global equivalent average over adopted tendons:

  `ΔfpA,avg,global = Σ(Aps,i · ΔfpA,avg,i) / ΣAps,i`

- Separates the two quantities in the decision UI:
  - **Local max anchor-set loss** — station/local diagnostic used for tendon-force distribution.
  - **Equivalent average anchor-set loss** — summary / external lumped-loss comparison only.
- Adds a selected-tendon summary beneath the force-profile graph with jacking/mode, local maximum, equivalent average, and mode-specific seating geometry.
- Renames the card to **Calculated seating ends** and fixes the single-end decision-table `Affected sₐ` mapping that was hidden because `SINGLE-END FRICTION-COUPLED` contains the word `COUPLED`.
- Replaces remaining Python-style null display values in the detailed compatibility audit with engineering-facing em dashes where practical.

## Independent QA

- Numerically integrates the calculated station-loss distribution and compares it with the independent compatibility-average identity:
  - single-end: `Ep·Δa/(1000L)`
  - simultaneous equal both-end: `Ep·(ΔaL+ΔaR)/(1000L)`
- Adds a dense-grid independent simultaneous-both-end verifier that does not call the production interpolation/area/coupled-solver helpers and checks neutral station, meeting stress, and left/right anchorage losses for an asymmetric case.
- Retains all PTLOSS2R1 Caltrans single-end benchmarks and PTLOSS2R2 symmetric, zero-friction, and asymmetric tests.

## Scope guard

No accepted friction or anchorage-set solver equation is changed in PTLOSS2R3. `Pe / Pe_eff`, Elastic Shortening, Time-Dependent Losses, PMM, SLS/ULS, rebar, reports, and other member workflows remain outside this milestone.

## QA status

- `compileall`: PASS
- PTLOSS1/PTLOSS2R3 targeted: 34 passed
- Complete Crossbeam regression: 222 passed
- Completed non-Crossbeam split batches: 1,688 passed / 4 known pre-existing failures
- Remaining final large ULS/validation batch: not completed due environment timeout; no claim of full-project green status
