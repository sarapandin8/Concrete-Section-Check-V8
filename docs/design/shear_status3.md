# SHEAR.STATUS3 — Shear Compact Status Stale-Row Hardening

## Purpose

Fix the remaining Beam/Girder ULS shear compact-table status mismatch where the visible shear workspace showed PASS and finite numeric gates were below 1.0, but the compact summary still showed FAIL because a cached/source row carried stale text-only FAIL markers.

## Rule

For Beam/Girder provided-stirrup shear summary:

1. Finite numeric strength D/C controls strength pass/fail.
2. Finite numeric detailing D/C controls detailing pass/fail.
3. If numeric D/C values are missing, formatted utilization text such as `0.541 / det 0.757` is parsed as a display-layer recovery path.
4. Bare text `FAIL` without finite numeric gate evidence is treated as stale review metadata and must not override current numeric PASS evidence.
5. `LAYOUT REQUIRED`, explicit data-not-ready states, and finite D/C values greater than 1.0 remain controlling.

## Scope

This is a UI/status propagation hotfix only. It does not change shear equations, capacity, demand, section geometry, or reinforcement calculations.
