# CROSSBEAM.PTLOSS4D1A — Projected-Station Integrated Effective Prestress Average and Closure Guard

## Purpose

Correct the PTLOSS4D1 system-average Effective Prestress calculation so displayed station rows are integrated by their actual projected-member spacing instead of being collapsed to an arithmetic row mean.

## Root cause

- Upstream loss/component rows use the station field `s (m)`.
- PTLOSS4D1 assembled Effective Prestress rows use `Station s (m)`.
- The averaging helper read only `s (m)`, so every assembled row fell back to station zero.
- Duplicate station-zero rows were then averaged arithmetically, which caused the reported average `fpe` and `Pe` to disagree with the independently integrated average loss components.

## Correction

- Accepts both canonical station labels and ignores rows with no valid station source.
- Collapses duplicate left/right rows at one station before integration.
- Uses piecewise trapezoidal integration with the actual, possibly nonuniform, station spacing.
- Requires complete projected coverage from `s = 0` to `s = L` before the Effective Prestress preview can be marked ready.
- Adds per-tendon projected-station averaging audit rows.
- Adds system-average stress and force closure checks:

  `f̄pj − Δf̄total − f̄pe = 0`

  `ΣPj − ΣPe,avg − Aps,Σ Δf̄total / 1000 = 0`

## Averaging scope

The current source is projected member station `s`, not tendon arc length. The UI therefore identifies the result as an Aps-weighted projected-station trapezoidal average and does not call it a true tendon-path-length average.

## Safety boundary

- Friction/Wobble, Anchorage Set, Elastic Shortening, Creep, Shrinkage, and Relaxation equations are unchanged.
- Time-Dependent loss remains a representative scalar.
- Secondary prestress and final station-dependent TD loss remain excluded.
- Final SLS handoff remains blocked.
- No Project JSON schema, solver runtime, or non-Crossbeam workflow changed.
