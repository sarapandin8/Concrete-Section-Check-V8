# CROSSBEAM ANALYSIS4C7D2 — Continuous full-span Flexure demand trace

## Summary
Keeps the Segmental Crossbeam Flexure `Demand Mux` diagram continuous across the full member length while preserving local sectional-capacity discontinuities at supports, physical joints, and reinforcement-credit boundaries.

## Changes
- The blue `Demand Mux` trace is no longer clipped by Column/support footprints or the ±100 mm physical-joint plotting gaps.
- The imported global-analysis moment diagram remains one continuous trace from `s = 0` to `s = L` for each load case.
- The red `Adopted φMn` capacity envelope retains all existing engineering semantics:
  - support interiors remain omitted from ordinary sectional capacity,
  - Precast physical joints remain true capacity discontinuities,
  - one-sided near-joint capacity markers remain separate,
  - development/no-rebar-credit capacity steps remain unchanged.
- The Flexure caption now explicitly distinguishes the continuous global demand diagram from the local sectional-capacity envelope.

## Engineering scope
No Flexure equations, strain-compatibility logic, prestress source, capacity values, D/C calculations, Project JSON, or other ULS solvers are changed by this milestone.
