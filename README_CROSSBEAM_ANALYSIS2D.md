# CROSSBEAM.ANALYSIS2D — Sectional Shear Result / Physical-Joint Review Clarity

**Date:** 2026-08-02  
**Baseline:** `concrete-section-pro_CROSSBEAM-ANALYSIS2C-one-sided-support-demand-recovery.zip`  
**Scope:** Result semantics, chart annotation cleanup, and compact ULS Shear review tables only.

## Purpose

Keep the conservative physical-joint scope guard without hiding the completed ACI 318-19 sectional shear result. The page now reports the numerical sectional PASS/FAIL and governing D/C independently from the separate Precast physical-joint shear-transfer review.

## Changes

### Result semantics

- Added a dedicated `sectional_status` derived only from rows eligible for the ACI sectional one-way shear check.
- Added `sectional_governing_row`, so a physical-joint scope row can no longer replace the numerical governing sectional D/C.
- Preserved the conservative overall module status: exact physical-joint rows keep the overall module at `REVIEW` until joint shear transfer is verified separately.
- Added explicit counts for:
  - sectional check rows,
  - generated Column Face / ACI h/2 checks,
  - evaluated support checks,
  - generated support checks coinciding with physical joints,
  - physical-joint review rows.

### ULS Shear workspace

- Replaced the ambiguous cards:
  - `Shear Status`,
  - `Governing D/C`,
  - `Governing Gate`.
- New decision cards are:
  - `Sectional Shear`,
  - `Governing Sectional D/C`,
  - `Physical Joint Check`,
  - `Support Checks`.
- Removed the redundant `Axis Mapping` card from the main page.
- Clarified source counts as retained source/joint rows plus generated Column Face / h/2 rows.
- Updated the scope text to match the current support-face/h/2 route; support-footprint interiors are omitted rather than treated as beam-shear scope guards.

### Chart and tables

- Replaced long vertical physical-joint labels with compact amber X markers and one legend item: `Physical joint — REVIEW`.
- Retained the accepted support-footprint shading, Column Face markers, ACI h/2 markers, and deduplicated `±φVn` / `±φVc` legends.
- Added a compact main-page `Column Face / h/2 checks` table, including exact/interpolated/extrapolated demand source traceability.
- Moved regular/imported station checks into a collapsed expander.
- Kept the full ACI calculation audit collapsed.

## Engineering behavior unchanged

- No changes to ACI 318-19 shear equations.
- No changes to `Vc`, `Vs`, `φVn`, strength reduction factor, section limit, minimum transverse reinforcement, or spacing checks.
- No changes to one-sided interpolation or limited extrapolation.
- No changes to Flexure, SLS, Prestress Loss, Loads, Project JSON, or other member workflows.
- Physical-joint shear transfer remains outside the current sectional-shear module and is not certified by this milestone.

## Changed files

```text
concrete_pmm_pro/analysis/crossbeam_uls_shear.py
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis2_uls_shear.py
README_CROSSBEAM_ANALYSIS2D.md
```

## QA completed

```text
python -m compileall -q app.py concrete_pmm_pro tests
PASS

ANALYSIS2 / ANALYSIS2A / ANALYSIS2D focused
26 passed

Crossbeam + Beam/Girder chart/navigation regression
60 passed

Bridge/Girder ULS regression
102 passed

Complete Crossbeam-selected suite
551 passed, 5 baseline-existing source-string failures
```

The five Crossbeam-selected failures are the same legacy Prestress-Loss / FEA-handoff wording assertions already present in the ANALYSIS2C baseline and are unrelated to this milestone.

A larger combined shared-analysis command was attempted but did not complete within the 15-minute execution limit. The relevant suites were then split and completed successfully as reported above. A live Streamlit browser runtime was not available in the sandbox; deployed-page visual QA remains required before final acceptance.

## Repo summary

```text
Clarify Crossbeam ULS shear by reporting the governing ACI sectional PASS/FAIL and D/C separately from physical-joint REVIEW, while simplifying joint markers and adding compact support-check traceability.
```
