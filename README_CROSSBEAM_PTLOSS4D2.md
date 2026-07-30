# CROSSBEAM.PTLOSS4D2 — Effective Prestress External-FEA Handoff

## Purpose

Convert the closed PTLOSS4D1A `fpe(s)` / `Pe(s)` preview into an auditable download package for external portal-frame FEA without duplicating a secondary-prestress solver inside Concrete Section Pro.

## Handoff content

The Effective Prestress tab now provides a source-gated FEA handoff with:

- one compact row per Tendon containing Left, Mid, Right, and projected-station-average `fpe` / `Pe`;
- the complete Tendon/station stress-force profile;
- average loss, loss percentage, and remaining-prestress percentage;
- total-system station force rows;
- a deterministic SHA-256 source fingerprint;
- a formatted Excel workbook plus Tendon and Station CSV downloads;
- explicit units, sign convention, application-mode, and SLS-return instructions.

## FEA application boundary

Two application routes are documented, and the engineer must use exactly one:

1. input exported effective `fpe` / `Pe` directly and disable duplicate FEA loss calculation; or
2. input `fpj` / `Pj` and reproduce the same loss model in FEA without also applying `fpe` / `Pe`.

Secondary prestress is not treated as a tendon loss and is not subtracted from `Pe`. External FEA remains responsible for primary and secondary response from portal-frame compatibility and restraint.

## SLS return route

This milestone does not write results into SLS automatically. After external FEA calculates prestress response and service actions, verified SLS `P/V2/M3` resultants must return through the main Loads workspace.

## Current limitation

Creep, shrinkage, and relaxation remain the accepted representative Time-Dependent scalar used by PTLOSS4D1A. The export states this limitation explicitly and does not claim tendon/station-dependent TD refinement.

## Safety and regression boundary

- Friction/Wobble, Anchorage Set, Elastic Shortening, Creep, Shrinkage, and Relaxation equations are unchanged.
- Effective Prestress stress/force closure and projected-station averaging remain unchanged.
- Export generation performs zero structural solves and does not mutate Project JSON or analysis state.
- Main Loads remains dedicated to ULS/SLS demand import.
- No non-Crossbeam workflow is changed.
