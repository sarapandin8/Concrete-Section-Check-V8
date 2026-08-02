# CROSSBEAM.ANALYSIS2C — One-Sided Column-Face Demand Recovery

## Milestone

`CROSSBEAM.ANALYSIS2C`

## Baseline

Started only from:

```text
concrete-section-pro_CROSSBEAM-ANALYSIS2B-support-face-h2-shear.zip
```

Verified baseline SHA-256:

```text
fc86f2540472d3205b8dae857f025602971341fe344f3ad75222fdbdba8460e0
```

## Purpose

Remove unnecessary ULS Shear source blocking when an imported station-force table does not contain an exact row at every Column Face, while preserving the accepted conservative checks at both the Column Face and the ACI h/2 section.

No new user input or declaration is added.

## Accepted source-recovery hierarchy

For each Load Case and each beam side of a Column / Support:

1. exact row at the check station,
2. row-coupled one-sided interpolation,
3. limited row-coupled one-sided extrapolation.

`P`, `V2`, `T`, and `M3` always use the same two source rows and the same ratio. Independent maxima are never combined.

## Reaction-discontinuity protection

The source recovery never crosses a support centerline:

- a candidate row on the opposite side of the active Column centerline is rejected,
- a candidate row is rejected when any support centerline lies between that row and the target check station,
- a row located exactly on a support centerline is not used as a one-sided source,
- imported rows inside a support footprint may be used when they remain on the correct beam side of the Column centerline.

This allows a normal station grid to recover a face value without interpolating through the support reaction jump.

## Limited extrapolation gate

One-sided extrapolation is accepted only when:

```text
extrapolation distance / source-row spacing <= 0.25
```

If the required extrapolation exceeds 25 percent of the source-row spacing, the affected support check remains source blocked and asks for a closer station-force row.

## Traceability

Each generated support row stores:

- demand source: `EXACT`, `INTERPOLATED`, or `EXTRAPOLATED`,
- source station 1,
- source station 2,
- common interpolation/extrapolation ratio,
- extrapolation-to-spacing ratio,
- a concise source note.

These fields are shown only in the collapsed Shear calculation audit. The main workspace remains compact.

## Verified project-grid behavior

The current 2 m station-grid pattern was checked explicitly for the previously blocked Column Faces:

```text
C1-L Face  s = 1.750 m  -> interpolation from 0.000 and 2.000 m
C1-R Face  s = 3.750 m  -> 12.5% extrapolation from 4.000 and 6.000 m
C3-L Face  s = 26.250 m -> 12.5% extrapolation from 24.000 and 26.000 m
C3-R Face  s = 28.250 m -> interpolation from 28.000 and 30.000 m
```

No reconstruction crosses the Column centerline.

## Files changed

```text
concrete_pmm_pro/analysis/crossbeam_uls_shear.py
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis2_uls_shear.py
README_CROSSBEAM_ANALYSIS2C.md
README.md
```

## Engineering equations

No accepted ACI 318-19 strength or detailing equation changed:

- prestressed approximate `Vc`,
- provided `Vs`,
- `phiVn`,
- section/diagonal-compression limit,
- minimum transverse reinforcement,
- longitudinal and transverse spacing limits,
- shear `phi = 0.75`.

This milestone changes station-force source recovery, traceability, and source gating only.

## QA completed

```text
Compileall:
PASS

ANALYSIS2C focused tests:
18 passed

Crossbeam Analysis / Loads / Navigation targeted regression:
58 passed

Complete Crossbeam suite:
547 passed
5 baseline-existing failures

Shared Analysis / Bridge-Girder / Navigation regression:
145 passed
```

The five Crossbeam failures are unchanged source-string assertions in older Prestress Loss / FEA-handoff milestone tests and reproduce in the ANALYSIS2B baseline.

Live Streamlit browser rendering was not executed in this sandbox. The recovery hierarchy, 25 percent extrapolation gate, no-cross-centerline rule, source trace fields, chart regression, and existing support-figure behavior are covered by automated tests.

## Not included

- Torsion
- Combined shear + torsion
- Beam-column joint strut-and-tie design
- Physical segment-joint interface shear transfer
- Local bearing or hanger reinforcement
- PT anchorage/end-zone design
- Fatigue
- Seismic detailing
- Crossbeam Result Summary / Report QA integration

## Repo summary

```text
Recover missing Crossbeam Column-Face and ACI h/2 ULS shear demands with exact-first, one-sided interpolation, and 25%-limited one-sided extrapolation without crossing support centerlines or changing accepted ACI strength equations.
```
