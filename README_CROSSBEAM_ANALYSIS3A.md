# CROSSBEAM.ANALYSIS3A — Torsion Chart Completeness and Capacity Semantics

**Date:** 2026-08-03  
**Baseline:** `concrete-section-pro_CROSSBEAM-ANALYSIS3-aci-prestressed-uls-torsion.zip`  
**Baseline SHA-256:** `2155e2b3ebb270569bc931084323a7bed696cac991d27e3139a9d0deb8f2146e`  
**Scope:** Correct the standalone Crossbeam ULS Torsion figure only; no ACI equation, capacity, station-force, Project JSON, or solver-result change.

## Defect confirmed from deployed visual QA

The accepted ANALYSIS3 figure could omit the Solid-section `±φTth` traces because the chart-row adapter retained only rows with finite `φTn`. Below-threshold sections intentionally have no detailed `φTn`, but they still have a valid ACI threshold `φTth` that must remain visible.

The force/capacity figure also used the overall standalone governing D/C marker. In the reviewed model that value was governed by longitudinal torsion reinforcement `Al`, not by `Tu/φTn`, so the marker could be misread as a torsional-strength failure.

## Changes

### Complete threshold plotting

- `φTth` is retained and plotted for every eligible section, including below-threshold Solid sections where `φTn` is intentionally blank.
- `φTn` remains plotted only where detailed torsion design is required and a finite torsional strength exists.
- Lines remain broken across support footprints and are now also broken across physical segment-joint stations.

### Explicit symmetric chart scale

The y-axis is calculated from all finite values of:

```text
|Tu|
|φTth|
|φTn|
```

The plot uses a symmetric `±1.12 × maximum` range so a high Solid-section threshold/capacity cannot be clipped by the demand or an adjacent Hollow section.

### Correct force-graph governing marker

- The black marker now reports `Gov. Tu/φTn` using `Strength D/C value` only.
- Overall standalone failure caused by longitudinal `Al` or the section-size gate remains visible in the result cards and tables, not mislabelled on the torque-capacity graph.

### ACI support-location wording

- Prestressed `h/2` points are identified as the ACI critical-section route.
- Column Faces are identified as conservative support-face screens.
- No existing generated station or demand-recovery logic was changed.

## No engineering equation change

Unchanged:

- `Tth`, `Tcr`, `Tn`, and `φ = 0.75`
- solid/hollow threshold routes
- closed-cage and Outer longitudinal `Al` checks
- section-size stress limit
- Column Face / `h/2` demand recovery
- one-sided interpolation and limited extrapolation
- physical-joint REVIEW routing
- Flexure, Shear, SLS, Prestress Loss, Loads, and Project JSON

## Changed files

```text
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis3_uls_torsion.py
README_CROSSBEAM_ANALYSIS3A.md
README.md
```

## QA completed

```text
python -m compileall -q app.py concrete_pmm_pro tests
PASS

ANALYSIS3 / ANALYSIS3A focused
13 passed

Crossbeam ULS / Loads / Navigation + shared ULS chart regression
120 passed

Complete Crossbeam suite
563 passed, 5 baseline-existing failures

Untouched ANALYSIS3 baseline comparison
562 passed, the same 5 failures
```

The five failures are unchanged legacy source-string assertions in older Prestress Loss / external-handoff milestone tests and reproduce in the untouched ANALYSIS3 baseline.

Programmatic figure QA confirms:

- one `±φTn` legend entry,
- one `±φTth` legend entry,
- all finite threshold values appear in the positive threshold trace,
- the symmetric y-axis covers at least 110 percent of every finite `Tu`, `φTth`, and `φTn`,
- the force graph uses `Gov. Tu/φTn`, not the overall longitudinal-`Al` governing D/C.

A deployed Streamlit screenshot remains required for final visual acceptance.

## Repo summary

```text
Complete Crossbeam ULS torsion threshold traces across Solid and Hollow sections, fit the symmetric chart scale to all finite Tu/φTth/φTn values, and separate Tu/φTn graph semantics from longitudinal-Al failure without changing ACI calculations.
```
