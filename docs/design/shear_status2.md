# SHEAR.STATUS2 — Shear Numeric Gate Status Hotfix

## Purpose

Fix the Beam/Girder ULS shear compact status when stale textual status fields
remain in cached/source rows after the visible strength and detailing D/C gates
have recalculated to passing values.

## Problem

The shear workspace could show:

- Strength D/C < 1.0,
- Detailing D/C < 1.0,
- Shear card = PASS,
- demand below φVn in the diagram,

while the compact ULS table still showed `Shear = FAIL` because it trusted a
stale text field such as `Status = FAIL` or `Strength status = FAIL` before the
finite utilization values.

## Fix

When finite numeric gates are available, they are the source of truth:

1. `Strength D/C value > 1.0` fails.
2. `Detailing D/C value > 1.0` fails.
3. If both finite numeric gates are `<= 1.0`, stale textual `FAIL` values do not
   override the calculated evidence.
4. Textual fail/review states still control when numeric evidence is absent or
   data are incomplete.

## Scope

Beam/Girder ULS provided-stirrup shear compact summary and source gate logic.
No shear equations, geometry, prestress, or load-combination equations were
changed.
