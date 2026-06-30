# SLS.MATERIAL.ROUTING2 — Robust Stage Material Routing for SLS Diagram Guide

## Scope

This milestone closes a regression found after SLS.MATERIAL.ROUTING1: the Beam/Girder full-length SLS diagram tensile-limit guide could still display the final concrete strength as `f'ci` when the Analysis page reached the generic diagram route with a stale or missing `section_preset_key`.

## Change

The SLS material-strength router now detects Railway U-Girder from the active generated geometry metadata before falling back to session-state preset selectors. It also checks user-facing section labels and geometry name as defensive fallbacks. This keeps Transfer/Lifting checks tied to Railway U-Girder `web_fci_MPa`, even after project load/rerun sequences where selector state is stale.

## Engineering rule protected

- Railway U-Girder Transfer/Lifting: use precast web `f'ci`.
- Railway U-Girder Construction/Wet casting: use precast web `f'c`.
- Railway U-Girder Service top/bottom extreme-fiber preview: use web `f'c`, with CIP slab `f'c` retained as audit note pending slab-fiber checks.

## Non-scope

No stress equations, ULS/PMM, geometry, prestress losses, rebar logic, load import, report, or project schema calculation logic changed.
