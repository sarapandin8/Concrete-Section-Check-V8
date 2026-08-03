# CROSSBEAM.ANALYSIS2F — Shear Count Consistency Closeout

**Date:** 2026-08-03  
**Baseline:** `concrete-section-pro_CROSSBEAM-ANALYSIS2E-shear-count-legend-compact-table-cleanup.zip`  
**Scope:** Crossbeam ULS Shear count semantics and result wording only.

## Purpose

Close the final deployed-page count inconsistency in the Crossbeam ULS Shear workspace. Generated support rows that coincide with physical segment joints are now reported as a subset of the existing check rows, not as an additional row group.

## Changes

### Source banner

The source banner now reports two non-overlapping row groups:

```text
retained source rows + generated support rows = total check rows
```

It then reports the result classification within those same rows:

```text
eligible sectional checks + physical-joint review locations
```

This prevents the prior contradictory wording that displayed `0 physical-joint review rows` while two generated support locations were visibly marked `REVIEW`.

### Source cards

The source summary now shows:

```text
ULS Source
Total Check Rows
Eligible Sectional Checks
Generated Support Checks
```

For the deployed review example, the intended reading is:

```text
24 total rows
22 eligible sectional checks
12 generated support checks
2 physical-joint review locations within the generated support set
```

Physical-joint review locations are therefore not added again to the total.

### Result card wording

`Physical Joint Check` is renamed to `Physical Joint Review`.

When all physical-joint reviews are generated support locations coinciding with segment joints, the detail states that relationship directly rather than describing them as separate rows.

## Engineering behavior unchanged

- No changes to ACI 318-19 shear equations.
- No changes to `Vc`, `Vs`, `phi Vn`, strength reduction factor, section limit, minimum transverse reinforcement, or spacing checks.
- No changes to Column Face or ACI h/2 station generation.
- No changes to exact, one-sided interpolation, or limited one-sided extrapolation.
- No changes to physical-joint review routing or overall module status.
- No changes to charts, tables, Loads, Flexure, SLS, Prestress Loss, Project JSON, or other workflows.

## Changed files

```text
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis2_uls_shear.py
README_CROSSBEAM_ANALYSIS2F.md
```

## QA completed

```text
python -m compileall -q app.py concrete_pmm_pro tests
PASS

ANALYSIS2F focused
21 passed

Crossbeam Analysis / Loads / Navigation targeted
61 passed

Complete Crossbeam suite
550 passed, 5 baseline-existing source-string failures

Shared Crossbeam + Beam/Girder chart/navigation selection
53 passed, 1 baseline-existing Result Summary source-string failure
```

The same five Crossbeam failures and the same shared Result Summary failure reproduce in the ANALYSIS2E baseline and are unrelated to this milestone.

## Repo summary

```text
Correct Crossbeam ULS shear count semantics so physical-joint reviews are reported as locations within retained/generated rows, not double-counted as additional check rows.
```
