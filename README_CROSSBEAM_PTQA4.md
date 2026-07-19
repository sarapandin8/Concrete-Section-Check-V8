# Concrete Section Pro - CROSSBEAM.PTQA4

## Milestone

`CROSSBEAM.PTQA4 - Tendon Profile import foundation`

## Delivered

- Adds a Tendon Profile import foundation section that exposes the expected
  CSV/XLSX row contract beside the active profile table.
- Adds a CSV template download generated from the current live `s-x-dtop`
  profile rows.
- Adds preview-only CSV/XLSX upload handling that normalizes imported tendon
  profile rows and validates them against the current Tendon System, Segment
  Layout, and Section Builder context.
- Keeps imported rows read-only in this milestone: no upload can overwrite the
  active profile table, Project JSON, or solver inputs.

## Scope guards

- This is an import-preparation and validation milestone only.
- It does not add final Excel writeback/apply controls, friction, wobble,
  anchorage set, elastic shortening, creep, shrinkage, relaxation, SLS stress,
  ULS strength, reports, or station solver handoff.

## Validation

- Syntax compile passed for `concrete_pmm_pro/crossbeam/tendon.py`.
- Syntax compile passed for `concrete_pmm_pro/ui/crossbeam_pages.py`.
- Syntax compile passed for
  `tests/test_crossbeam_ptqa4_tendon_profile_import_foundation.py`.
- Runtime pytest could not be completed in this scratch environment because
  `pytest` is not installed; direct import sanity also requires the declared
  app dependency `shapely`, which is not installed in this scratch runtime.

## Repo summary

Add Crossbeam PTQA4 Tendon Profile import foundation with CSV template download and preview-only CSV/XLSX validation without mutating project state or solvers.
