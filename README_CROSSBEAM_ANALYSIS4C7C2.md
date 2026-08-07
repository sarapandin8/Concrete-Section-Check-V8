# CROSSBEAM.ANALYSIS4C7C2 — Inline Trace-Owner Runtime Hotfix

## Scope

- Fixes the deployed Flexure workspace `NameError` raised after the result chart rendered at the trace-owner caption.
- Removes every `_trace_owner_label(...)` and `trace_owner_label(...)` runtime lookup from `analysis_page.py`.
- Resolves the construction-mode label directly at each use from the canonical construction-method normalizer:
  - Cast-in-Place → `Zone-owned`
  - Precast Segmental → `Segment-owned`
- Applies the same runtime-safe expression to Flexure, Shear, Torsion, Combined V+T, and ULS source cards.
- Preserves all ANALYSIS4C7C/C7C1 engineering equations, chart traces, station-dependent prestress behavior, Project JSON contracts, and deployment dependency pins.

## Root cause

The first hotfix still required a module-global helper lookup at render time. The deployed Streamlit execution reached the caption call with `_trace_owner_label` unavailable, so Flexure failed after drawing the figure. This hotfix eliminates that helper lookup entirely rather than renaming or re-importing it.

## Repo summary

Eliminate the deployed Crossbeam Flexure trace-owner NameError by resolving Zone-owned versus Segment-owned labels inline at every ULS render site without changing engineering results.
