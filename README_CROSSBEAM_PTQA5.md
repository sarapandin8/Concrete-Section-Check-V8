# Concrete Section Pro - CROSSBEAM.PTQA5

## Milestone

`CROSSBEAM.PTQA5 - Tendon Profile import apply guard`

## Delivered

- Compacts the Tendon Profile import panel by moving column requirements behind
  a secondary expander and keeping template/download plus upload controls on
  one action row.
- Adds row-change summary metrics for valid import previews, including added,
  changed, removed, unchanged, and affected-tendon counts.
- Adds a guarded `Apply imported profile` action that requires a valid preview
  plus explicit confirmation before replacing the active Tendon Profile
  `s-x-dtop` table.
- Adds one-step `Undo last import` to restore the profile rows that were active
  immediately before the latest import apply.

## Scope guards

- The apply action rewrites only Tendon Profile geometry rows and increments the
  profile editor revision.
- It does not change Tendon System, Segment Layout, Section Builder, Project JSON
  export shape, rebar workflows, reports, or solver calculations.
- It does not calculate friction, wobble, anchorage set, elastic shortening,
  creep, shrinkage, relaxation, SLS stress, ULS strength, reports, or station
  solver handoff.

## Validation

- Syntax compile passed for `concrete_pmm_pro/crossbeam/tendon.py`.
- Syntax compile passed for `concrete_pmm_pro/ui/crossbeam_pages.py`.
- Syntax compile passed for
  `tests/test_crossbeam_ptqa4_tendon_profile_import_foundation.py`.
- Runtime pytest could not be completed in this scratch environment because
  `pytest` is not installed; direct import sanity also requires the declared app
  dependency `shapely`, which is not installed in this scratch runtime.

## Repo summary

Add Crossbeam PTQA5 guarded Tendon Profile import apply with compact preview, row-change summary, explicit confirmation, and one-step undo while leaving solvers unchanged.
