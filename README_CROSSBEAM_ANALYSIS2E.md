# CROSSBEAM.ANALYSIS2E — Shear Count / Legend / Compact-Table Semantics Cleanup

**Date:** 2026-08-03  
**Baseline:** `concrete-section-pro_CROSSBEAM-ANALYSIS2D-sectional-result-joint-review-clarity.zip`  
**Scope:** ULS Shear display semantics and compact review layout only.

## Purpose

Make the Crossbeam ULS Shear page immediately readable after deployed-page visual QA. The milestone removes duplicated card labels, states exactly how total check rows are assembled, distinguishes maximum absolute demand from governing D/C, and keeps the main Column Face / ACI h/2 table decision-focused.

## Changes

### Source and result cards

- Renamed the source card from `Section checks` to `Total check rows`.
- The total now reports three non-overlapping groups:
  - regular sectional source rows,
  - generated Column Face / ACI h/2 rows,
  - retained physical-joint review rows.
- Renamed the source `Support checks` card to `Generated support checks` and reports the separate Column Face and ACI h/2 counts.
- Renamed the result `Support checks` card to `Completed support checks`.
- Added the eligible sectional-check count to the `Sectional shear` result card.

### Chart terminology

- Renamed `Governing demand` to `Max |Vu|` because maximum absolute shear demand does not necessarily govern D/C.
- Renamed `Governing shear check` to `Gov. shear D/C`.
- Preserved all accepted graph styling, support-footprint shading, Column Face / h/2 markers, physical-joint markers, and `±φVn` / `±φVc` legends.

### Compact support table

The main `Column Face / h/2 checks` table now contains only decision fields:

```text
Status | Check Point | Station s (m) | Source | Vu kN | φVn kN | Strength D/C | Detailing D/C
```

Detailed demand-recovery traceability remains in the collapsed calculation audit, including source stations, interpolation/extrapolation ratios, requested check, and resolved location.

The audit labels are clarified as:

```text
Requested Check
Resolved Location
```

## Engineering behavior unchanged

- No changes to ACI 318-19 shear equations.
- No changes to `Vc`, `Vs`, `φVn`, strength reduction factor, section limit, minimum transverse reinforcement, or spacing checks.
- No changes to support-face / h/2 station generation.
- No changes to one-sided interpolation or limited extrapolation.
- No changes to physical-joint review semantics.
- No changes to Flexure, SLS, Prestress Loss, Loads, Project JSON, or other member workflows.

## Changed files

```text
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis2_uls_shear.py
README_CROSSBEAM_ANALYSIS2E.md
```

## QA completed

```text
python -m compileall -q app.py concrete_pmm_pro tests
PASS

ANALYSIS2E focused
21 passed

Crossbeam Analysis + Navigation + shared Beam/Girder chart regression
125 passed

Complete Crossbeam suite
550 passed, 5 baseline-existing source-string failures
```

The five failures are the same legacy Prestress-Loss / FEA-handoff wording assertions present in the ANALYSIS2D baseline and are unrelated to this milestone.

## Repo summary

```text
Clarify Crossbeam ULS shear counts and chart terminology, separate generated versus completed support checks, and compact the Column Face / h/2 decision table without changing accepted ACI calculations.
```
