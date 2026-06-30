# AASHTO.COL.PMM.TRACE1 — PMM Code-Basis Traceability

## Purpose

This milestone makes the Column/Pier/Wall/Pylon PMM Visual Review show the active code basis explicitly.  The prior AASHTO PMM route was implemented, but a result with no active prestress still displayed the generic label `RC PMM`, which could be mistaken for the legacy ACI-oriented route.

## UI changes

The PMM dashboard now renders a code-basis trace card strip in the Summary and PMM Check tabs:

- Code Basis
- PMM Route
- Prestress Branch
- φ / Units Trace

The Selected Case Details panel now includes:

- Code basis
- Code edition
- PMM route
- Flexural basis
- Phi basis
- Units trace
- Prestress branch

The 2D Mux-Muy slice and 3D PMM interaction Plotly figures receive a compact code-basis subtitle and `layout.meta["pmm_code_trace"]` metadata so exported/reused figures carry the same route trace.

## AASHTO wording

For AASHTO LRFD projects the visible route is:

```text
AASHTO LRFD Column/Pier PMM
AASHTO Section 5 B-region axial-flexure
AASHTO strain-controlled φ transition
SI solver units; AASHTO ksi/kips constants converted before use
```

The `RC PMM` analysis-mode label is preserved only to mean that the selected PMM branch has ordinary rebar and no active bonded prestress; it is no longer the only visible basis label.

## Guarded scope

This milestone does not expand the solver.  AASHTO shear, torsion, V+T, slenderness, seismic, detailing, and hollow-wall local-buckling checks remain guarded future/engineering-review work.

## Regression coverage

Added `tests/test_aashto_col_pmm_trace1.py` to verify:

- AASHTO route/edition/context wording.
- Prestress branch wording does not imply ACI.
- Summary cards expose code route, φ basis, and unit trace.
- Selected case summaries are enriched with code-basis fields.
- Plotly titles and metadata carry the PMM code trace.
