# CROSSBEAM.ANALYSIS2B — Conservative Column Face + h/2 ULS Shear Checks

## Milestone

`CROSSBEAM.ANALYSIS2B`

## Baseline

Started only from:

```text
concrete-section-pro_CROSSBEAM-ANALYSIS2A-compact-loads-shear-visual-cleanup.zip
```

## Purpose

Close the support-region presentation and engineering gap in the Crossbeam ACI 318-19 ULS Shear workspace without adding new user controls or clutter.

The accepted project-specific conservative route now checks both:

1. the beam-side Column Face, and
2. the ACI h/2 critical section measured outward from that face for prestressed beams.

The larger demand/capacity or detailing utilization governs. The support-footprint D-region itself remains outside the sectional beam-shear module, but its presence no longer downgrades a completed sectional PASS to REVIEW.

## Engineering source rule

### Column Face

- Requires an exact one-sided canonical station-force row at the face.
- The app does not interpolate through a support reaction.
- `P`, `V2`, `T`, and `M3` remain coupled to the same imported row.

### ACI h/2 critical section

- Generated automatically from the applied Column / Support Layout and the beam-side section depth `h`.
- Uses an exact row when available.
- Otherwise uses linear interpolation only between two active rows in the same Load Case and on the same beam side.
- Interpolation through any support-footprint interior is prohibited.
- All four resultants are interpolated with one common ratio; independent maxima are never combined.

### Member-end behavior

When an h/2 station falls outside the modeled member, the applicable Column Face check remains active and the out-of-domain h/2 point is not fabricated.

## Result semantics

- `COLUMN FACE` and `ACI h/2 CRITICAL SECTION` are production sectional checks and can return PASS or FAIL.
- Imported rows inside a support footprint are omitted from the sectional route and replaced by the generated support checks.
- Beam-column joint/support-footprint D-region design remains a separate scope note and does not create an automatic module REVIEW.
- Exact Precast physical segment joints remain REVIEW because interface/joint shear transfer is outside this one-way sectional route.

## Graph changes

The Crossbeam Shear figure keeps the accepted Bridge/Beam chart language while adding Crossbeam-specific support semantics:

- shaded neutral support-footprint bands,
- signed `Vu` lines broken across each support footprint,
- `±φVn` lines broken across each support footprint,
- `±φVc` shown symmetrically,
- Column Face markers shown as open circles,
- ACI h/2 markers shown as open diamonds,
- short support-face labels,
- physical segment joints retained as amber REVIEW markers,
- one visible legend entry for `±φVn`,
- one visible legend entry for `±φVc`.

The former duplicated positive/negative `φVn` legend entries are removed.

## UI changes

- Shear status now reflects completed sectional checks rather than support-footprint presence.
- Governing gate can report `COLUMN FACE`, `ACI h/2`, `STRENGTH`, `DETAILING`, or physical-joint `SCOPE GUARD`.
- The result strip reports Support checks separately from total sectional checks.
- No new user-facing FEA metadata, unit, axis, stage, or support-rule controls were added.

## Files changed

```text
concrete_pmm_pro/analysis/crossbeam_uls_shear.py
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis2_uls_shear.py
tests/test_crossbeam_analysis2a_compact_loads_shear_cleanup.py
README_CROSSBEAM_ANALYSIS2B.md
```

## Engineering equations

The accepted ACI 318-19 sectional strength equations from ANALYSIS2 were not changed:

- prestressed approximate `Vc`,
- provided `Vs`,
- `φVn`,
- section/diagonal-compression limit,
- minimum transverse reinforcement,
- longitudinal and transverse spacing limits,
- shear `φ = 0.75`.

This milestone changes support-station generation, source gating, result semantics, and graph presentation only.

## QA completed

```text
Compileall:
PASS

ANALYSIS2B focused tests:
16 passed

Crossbeam Analysis / navigation targeted regression:
55 passed

Complete Crossbeam suite:
545 passed
5 baseline-existing failures

ANALYSIS2A baseline Crossbeam suite comparison:
543 passed
5 identical pre-existing failures

Bridge/Beam shared Analysis and chart regression:
104 passed
```

The five Crossbeam failures are unchanged source-string assertions in older Prestress Loss / FEA-handoff milestone tests and reproduce in the ANALYSIS2A baseline.

Live Streamlit browser rendering was not executed in this sandbox because the Streamlit runtime package is not installed. Figure construction, trace grouping, support gaps, legend deduplication, support shading, and marker semantics are covered by automated Plotly figure tests.

## Not included

- Torsion
- Combined shear + torsion
- Beam-column joint strut-and-tie design
- Local bearing or hanger reinforcement
- PT anchorage/end-zone design
- Physical segment-joint interface shear transfer
- Fatigue
- Seismic detailing
- Crossbeam Result Summary / Report QA integration

## Repo summary

```text
Add conservative Crossbeam ULS shear checks at Column Faces and ACI h/2 sections, break demand and capacity curves across shaded support footprints, and consolidate ±φVn/±φVc legends without changing accepted ACI strength equations.
```
