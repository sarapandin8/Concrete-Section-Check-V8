# CLOSEOUT.RAIL.UGIRDER1 — Railway U-Girder SLS Engineering Review Closeout

## Purpose

This milestone closes the current Railway U-Girder development slice as a report-ready SLS engineering-review package.

The closeout status is deliberately limited:

```text
Railway U-Girder SLS Engineering Review Package - Closeout Ready
```

This means the current Railway U-Girder workflow has guarded report evidence, Word export support, QA wording checks, and regression coverage for the accepted SLS preview scope.

It does **not** mean final code-certified design.

## Closeout deliverable status

The closed scope includes:

- Railway U-Girder geometry and material/stage settings.
- Default 72-strand Railway U-Girder prestress layout.
- Debonding input, symmetric L/R mirror, and station-based participation handoff.
- Transfer, lifting, wet slab/construction, and final service staged SLS previews.
- Service multi-fiber report summary for top/bottom web and top/bottom CIP slab fibers.
- Guarded SLS decision summary using `Preview PASS` / `REVIEW` wording.
- Draft Word report section titled `Railway U-Girder SLS Engineering Review`.
- Railway U-Girder closeout status table in the report package.
- Regression tests that protect closeout wording and prevent final-certification overclaiming.

## Explicit non-closeout items

The following are still outside the current closed scope:

- transfer length force ramp
- development length
- anchorage / end-zone bursting
- lifting insert/local hardware check
- creep/shrinkage redistribution
- full time-dependent transformed composite analysis
- ULS Railway U-Girder PMM/shear coupling
- final code-certified design checks

## Decision wording policy

Allowed wording:

```text
Preview PASS
REVIEW
SLS engineering-review report-ready
not final code-certified
Closeout Ready for SLS engineering review
```

Forbidden wording for the current Railway U-Girder scope:

```text
Final Design PASS
Code-Certified PASS
Final code-certified design complete
Guaranteed safe
Approved for construction without independent review
```

## Files changed

```text
README.md
docs/design/closeout_rail_ugirder1.md
concrete_pmm_pro/reporting/__init__.py
concrete_pmm_pro/reporting/railway_u_girder_report.py
concrete_pmm_pro/reporting/report_tables.py
concrete_pmm_pro/reporting/word_export.py
tests/test_closeout_railway_u_girder1.py
```

## Non-changes

No solver equations, SLS stress equations, prestress force logic, debond participation logic, geometry generation, section properties, PMM, ULS shear/torsion, load combinations, or project schema were changed.
