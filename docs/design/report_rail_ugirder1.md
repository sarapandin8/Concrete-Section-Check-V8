# REPORT.RAIL.UGIRDER1 — Railway U-Girder SLS Engineering Review Report Section

## Scope

This milestone adds a report-ready Railway U-Girder staged SLS engineering-review section to the existing Report / QA workflow.

The section is intentionally guarded. It may be used for engineering review evidence, but it is not a final code-certified design report.

## Added report content

The report package exposes these tables when the active workflow is Railway U-Girder:

- Railway U-Girder Closeout Status
- Railway U-Girder SLS Report Scope
- Railway U-Girder Geometry Summary
- Railway U-Girder Material and Stage Settings
- Railway U-Girder Stage Quantities
- Railway U-Girder Prestress / Debonding Summary
- Railway U-Girder SLS Stage Governing Rows
- Railway U-Girder SLS Limit Governing Rows
- Railway U-Girder Final Service Governing Rows
- Railway U-Girder SLS Decision Summary
- Railway U-Girder Service Multi-Fiber Summary

The Draft Word Report export now includes a dedicated heading:

```text
Railway U-Girder SLS Engineering Review
```

## Guardrails

The report wording is limited to:

```text
Preview PASS
REVIEW
SLS engineering-review report-ready
not final code-certified
```

It must not claim final design certification.

## Explicit exclusions

The following remain future work and are not certified by this report section:

- transfer length force ramp
- development length
- anchorage / end-zone bursting
- lifting insert/local hardware check
- creep/shrinkage redistribution
- full time-dependent transformed composite analysis
- ULS Railway U-Girder PMM/shear coupling
- final code-certified design checks

## Files changed

```text
concrete_pmm_pro/reporting/railway_u_girder_report.py
concrete_pmm_pro/reporting/__init__.py
concrete_pmm_pro/reporting/report_tables.py
concrete_pmm_pro/reporting/report_sections.py
concrete_pmm_pro/reporting/limitations.py
concrete_pmm_pro/reporting/word_export.py
concrete_pmm_pro/ui/analysis_page.py
tests/test_report_railway_u_girder1.py
README.md
docs/design/report_rail_ugirder1.md
```

## Non-changes

No SLS solver equations, prestress force logic, debond participation logic, geometry generation, section properties, PMM, ULS shear/torsion, or project schema were changed.
