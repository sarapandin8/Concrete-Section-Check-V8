# CROSSBEAM.RB-MIG1 — Geometry-Compatible Legacy Rebar Migration

This milestone hardens only the Portal Frame Crossbeam legacy Rebar migration/reconciliation path.

## Scope

- Preserve the current Segment Layout + Section Library as the Solid/Hollow geometry source of truth.
- Repair migrated Zone assignments only when a longitudinal or transverse Template reference is missing or incompatible with the resolved Segment role.
- Preserve already-compatible custom project Template assignments.
- Never silently substitute an incompatible template when no role-compatible project template exists; validation remains `REVIEW REQUIRED`.
- Add a one-time page-entry reconciliation for legacy/session-order cases where Rebar migration ran before final Section-ID-derived Segment roles were available.
- Refresh Project-load validation after any automatic compatibility repair.

## Protected boundaries

No changes were made to Rebar design/solver equations, Crossbeam section geometry, Segment Layout geometry, Friction/Wobble, Anchorage Set, Elastic Shortening equations, `f_cgp`, Primary/Secondary Prestress, `Pe/Pe_eff`, PMM, SLS/ULS, or other member workflows.
