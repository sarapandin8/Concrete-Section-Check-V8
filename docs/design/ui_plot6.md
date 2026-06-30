# UI.PLOT6 — ULS Torsion Full-Length Capacity Plot Hotfix

## Purpose

Ensure Beam/Girder ULS torsion capacity/threshold traces plot over the full active member station domain, matching the demand line from the first active station to the last active station.

## Issue

Railway U-Girder torsion demand plotted from x=0 to x=L, but capacity and threshold traces could start/end at the first/last torsion design-zone rows instead of the member ends. This was visually misleading because the plot appeared truncated even though the demand line covered the full member length.

## Change

`_make_beam_uls_torsion_capacity_figure()` now applies a display-only extension of finite φTn / φTcr plot rows to the active station-domain ends when explicit boundary rows are missing or stale. The extension clones the nearest finite torsion capacity row for plotting only and marks it as a diagram boundary; it is not used for governing torsion checks, combined V+T source gates, or capacity calculations.

## Scope

Applies to Beam/Girder ULS torsion figures for all presets/member types using the shared Beam/Girder torsion plotting route, including Railway U-Girder, I-Girder, Box Girder, and rectangular/custom Beam/Girder presets.

## Not changed

- Torsion strength equation
- φTn / φTcr calculations
- Torsion status logic
- Governing station selection
- Combined V+T logic
- SLS/ULS solver equations
- Load routing
- Project schema

