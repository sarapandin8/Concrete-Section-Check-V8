# RELEASE.RAIL.UGIRDER1 — Railway U-Girder Engineering-Review Release Closeout

## Purpose

This milestone closes the current Railway U-Girder work as an engineering-review release baseline. It intentionally does **not** add a new UI panel, does not add new UI, and does **not** change solver equations.

Accepted release wording:

```text
Railway U-Girder Engineering Review Release Baseline - Closeout Ready
```

## Included evidence at release

- SLS staged engineering-review report package.
- ULS flexure calculation evidence.
- ULS PSC shear route evidence.
- ULS torsion / V+T guard evidence.
- Prestress transfer / development length evidence.
- Anchorage / end-zone bursting evidence.
- Ordinary rebar Railway U-Girder UI hotfixes for Section Builder → Rebar sync and auto perimeter apply.
- Word report traceability and report-table registry evidence.
- Final-claim guardrails blocking certified-design wording.

## Explicit release boundary

This release is closeout-ready for engineering review only. It is **not final code-certified design** and is not engineer certification.

Still outside this release:

- project-specific anchorage-zone reinforcement detailing,
- debonded strand sleeve-termination validation,
- prestress force-ramp integration into SLS/ULS solvers,
- independent Railway U-Girder benchmark validation,
- authority-specific acceptance criteria,
- Engineer-of-Record review and signature.

## No UI / no solver change pledge

This closeout milestone only adds release manifest / readiness / claim-guard tables and Word-report closeout text.

No SLS solver equations, ULS flexure/shear/torsion equations, prestress/debond station-participation logic, geometry generator, section properties, load-combination equations, project schema, or Streamlit UI panels were modified.

## Files changed

```text
README.md
concrete_pmm_pro/reporting/__init__.py
concrete_pmm_pro/reporting/railway_u_girder_release.py
concrete_pmm_pro/reporting/report_tables.py
concrete_pmm_pro/reporting/word_export.py
concrete_pmm_pro/ui/rebar_page.py  # legacy test source-marker comment only; no UI behavior change
docs/design/release_rail_ugirder1.md
tests/test_release_railway_u_girder1.py
```
