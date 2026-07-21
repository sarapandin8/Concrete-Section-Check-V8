# CROSSBEAM.PTLOSS2D — Anchorage Seating Visualization & Semantics Lock

## Scope

PTLOSS2D is a visualization and wording milestone built directly on the accepted PTLOSS2C full-length both-end seating solver. It does **not** change anchorage-set equations, friction/wobble equations, tendon force arithmetic, `Pe / Pe_eff`, PMM, SLS/ULS, rebar, reports, or other member workflows.

## Changes

- Adds a selectable tendon-force profile graph showing:
  - `Reference Pj`;
  - `After Friction & Wobble`;
  - `After Anchorage Set`.
- Marks `Neutral station sₙ` for `FULL-LENGTH COUPLED` seating solutions; local solutions retain zero-movement boundary markers.
- Changes the top coupled-solution status to `PREVIEW READY — PROCEDURE REVIEW` when final-state compatibility is solved but explicit first-end/second-end stressing and seating sequence remains outside the current solver.
- Uses dynamic seating-geometry terminology:
  - `Neutral station` for fully coupled solutions;
  - `Max influence length La` for isolated local solutions;
  - mixed-mode wording when both solution families coexist.
- Renames the decision card from `Worst local loss` to `Worst seating loss` so coupled results are not mislabeled as local.
- Clarifies code/method semantics:
  - ACI 318-19 remains the active structural design code;
  - anchorage seating/set is classified as an instantaneous prestress-loss component;
  - the numerical basis is the FHWA graphical force-diagram / area-compatibility concept;
  - PTLOSS2C coupled full-length final-state compatibility remains an engineering implementation extension, not a verbatim numbered AASHTO equation.

## QA Boundary

- `Pe / Pe_eff` remains locked.
- Explicit stressing/seating sequence remains a procedure-review item.
- No solver equations are changed in this milestone.
- Live Streamlit rendering is not available in the development runtime; source-level UI contracts, compile checks, targeted tests, Crossbeam regression, and cross-workflow smoke tests are used instead.

## Repo Summary

Add Crossbeam PTLOSS2D anchorage-seating force-profile visualization and locked engineering semantics for coupled/local seating previews without changing solver equations or other member workflows.
