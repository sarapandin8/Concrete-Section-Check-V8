# FINAL.RAIL.UGIRDER1 — Railway U-Girder Final Design-Check Evidence Closeout

## Purpose

`FINAL.RAIL.UGIRDER1` consolidates the Railway U-Girder SLS, ULS, prestress development, anchorage/end-zone, release, report, and QA evidence into a final **software design-check evidence** package.

This milestone is intended to close the current development phase without adding new Streamlit UI, without changing solver equations, and without pretending the software can replace Engineer-of-Record responsibility.

## Final status wording

Allowed wording:

```text
Railway U-Girder Final Design-Check Evidence Package - Complete
```

Blocked wording for software-only output:

```text
Final Code-Certified Design Complete
certified approval PASS wording
Software-certified final structural design
```

The blocked wording can only be used outside the app when an Engineer-of-Record has attached signed project calculations, benchmark validation, project-specific assumptions, authority/client requirements, and formal approval records.

## What is consolidated

The final evidence package consolidates:

- Staged SLS engineering-review report evidence.
- ULS flexure evidence.
- ULS PSC shear route evidence.
- ULS torsion / V+T guard evidence.
- Prestress transfer / development length evidence.
- Anchorage / end-zone bursting evidence.
- Release manifest and claim guardrails.
- Word report section and report table registry entries.
- QA guardrails that prevent misleading certification wording.

## No solver or UI change

This milestone intentionally makes no solver or UI change:

- No SLS solver equations changed.
- No ULS flexure/shear/torsion equations changed.
- No prestress/debond station-participation logic changed.
- No geometry generator or section-property equations changed.
- No load-combination equations changed.
- No project schema changed.
- No new Streamlit panels, tabs, or controls added.

## Engineer-of-Record boundary

This package is complete for software evidence closeout, but it is not legal certification. A responsible engineer must still review and approve:

- project-specific loads and load combinations,
- drawings and member boundary conditions,
- reinforcement detailing and constructability,
- anchorage/end-zone reinforcement details,
- independent benchmark validation record,
- client/authority requirements,
- signed calculation package.

## Files added/changed

```text
concrete_pmm_pro/reporting/railway_u_girder_final.py
concrete_pmm_pro/reporting/report_tables.py
concrete_pmm_pro/reporting/word_export.py
concrete_pmm_pro/reporting/__init__.py
docs/design/final_rail_ugirder1.md
tests/test_final_railway_u_girder1.py
README.md
```

## Regression intent

Tests lock the following behavior:

- Final package is available when Railway U-Girder evidence exists.
- Final manifest, prerequisite matrix, certification boundary, and handoff tables are available.
- Word report includes the final design-check evidence section.
- Misleading `certified approval PASS wording` wording is not generated.
- The exact software-only final code-certified claim is blocked without Engineer-of-Record approval.
