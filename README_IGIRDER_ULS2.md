# Concrete Section Pro — IGIRDER.ULS2

## Milestone
Bridge Precast I-Girder Construction-ULS full-span physical `φMn` capacity curve closeout.

## Problem closed
IGIRDER.ULS1 evaluated only the first 24 nonzero `Mux` rows for the Flexure preview and then plotted zero-demand end stations as artificial `φMn = 0` diagram boundaries. On a 20 m / 0.5 m station grid this produced a false red dashed capacity line that stayed flat only to roughly x = 12 m and then sloped to zero at the right support.

## Implemented
- Construction-stage Precast I-Girder Flexure now requests `full_span_capacity=True`.
- Every finite auto-generated Construction ULS station is evaluated for section capacity; the 24-row responsiveness cutoff is not used by this stage-owned route.
- Zero-demand support stations retain the actual section `φMn`; their D/C remains `N/A` because demand is zero.
- Capacity-state caching is preserved, so identical section/material/rebar/prestress states are still solved once and reused across the full station grid.
- Debonding/station-dependent strand participation continues to create distinct capacity states where the physical strand layout changes.
- The construction-flexure stored-result hash is versioned as `IGIRDER.ULS2.full-span-physical-phiMn`, invalidating the ULS1 truncated preview after deployment.
- Construction demand equations, factors, governing demand logic, and Final Composite guard are unchanged.

## Engineering semantics
`Mu(x) = 0` does not imply `φMn(x) = 0`. Demand and resistance are separate quantities. A zero-demand support point therefore keeps the section capacity applicable at that station; only utilization is not applicable.

## Scope guard
This milestone does **not** certify transfer/development length or anchorage/detailing. Those remain separate from the section-strength curve. Final Composite `φMn`, two-concrete-region strength, and girder–deck interface shear remain future work.
