# CROSSBEAM.ANALYSIS3 — ACI 318-19 Prestressed ULS Torsion

**Date:** 2026-08-03  
**Baseline:** `concrete-section-pro_CROSSBEAM-ANALYSIS2F-shear-count-consistency-closeout.zip`  
**Baseline SHA-256:** `8b6a945fd875c2b5824151131a1618b26ee854698a1e20f13a60352eee6ac27d`  
**Scope:** Standalone Crossbeam ULS Torsion station checks. Combined Shear + Torsion remains a later milestone.

## Purpose

Add the next production Crossbeam ULS check after accepted Flexure and Shear while preserving the compact Bridge/Beam interaction pattern, Crossbeam station-source ownership, Project JSON behavior, and all accepted Prestress/SLS workflows.

The ULS selector now exposes:

```text
Flexure | Shear | Torsion
```

`Shear + Torsion` is intentionally not exposed until its combined solver and adoption gates exist.

## Engineering route

### Demand and station ownership

- Uses active row-coupled `P / V2 / T / M3` from Crossbeam ULS Loads.
- Maps imported `T` to signed `Tu`; no prestress force or secondary response is added again.
- Reuses the accepted Shear station contract:
  - imported regular stations,
  - automatically generated Column Face checks,
  - automatically generated prestressed `h/2` checks,
  - exact-first, one-sided interpolation, and 25-percent-limited one-sided extrapolation,
  - no reconstruction across a Column centerline,
  - no sectional line/check through a support footprint.
- Physical Precast segment joints remain separate torsion-transfer `REVIEW` locations.

### ACI 318-19 checks

The standalone route includes:

- 22.7.1 and 22.7.4 threshold torsion `phi*Tth` for solid and hollow prestressed sections,
- 22.7.2.1 square-root concrete-strength cap for threshold/cracking torsion,
- 22.7.5 cracking torsion trace without automatic compatibility-torsion redistribution,
- 22.7.6 transverse and longitudinal space-truss torsional strength,
- 22.7.6.1.1 permitted `Ao = 0.85Aoh`,
- 22.7.6.1.2 prestress-dependent `theta = 37.5 or 45 degrees`,
- 22.7.7 solid/hollow combined shear-torsion section-size stress limit,
- 22.7.7.2 local wall-thickness substitution for thin hollow walls,
- 9.6.4 minimum transverse and longitudinal torsional reinforcement,
- 9.7.5 Outer longitudinal perimeter spacing, minimum diameter, and corner coverage,
- 9.7.6.3 closed-cage spacing and hollow inside-clearance checks,
- Table 21.2.1 torsion strength-reduction factor `phi = 0.75`.

### Conservative source and status gates

- If `Tu < phi*Tth`, the row reports `BELOW THRESHOLD` without requiring a closed torsion cage.
- If torsion design is required but no valid closed cage exists, the row reports `LAYOUT REQUIRED`; no reinforcement is invented.
- Only active `Outer:` longitudinal bars receive provisional `Al` credit.
- Hollow piecewise section/cage continuity, lap, and anchorage remain visible as `REVIEW` instead of being silently certified.
- Axial-tension rows remain `REVIEW` unless a stronger failure already governs.
- Physical segment-joint torsion transfer remains `REVIEW REQUIRED` outside the sectional route.

## Standalone versus Combined V+T boundary

A numerically passing design-required standalone Torsion result remains overall `REVIEW` until the future Combined Shear + Torsion milestone closes both:

1. additive transverse reinforcement adoption required by ACI 9.5.4.3, and
2. flexure plus additional longitudinal torsion force required by ACI 9.5.4.4.

The standalone workspace reports its component PASS/FAIL and governing D/C independently so the user can see the numerical torsion result without over-certification.

## UI and chart behavior

The workspace follows the accepted Bridge/Beam and Crossbeam ULS design system:

- on-demand `Calculate Torsion` action,
- separate deterministic Torsion result cache/fingerprint,
- decision-first source and result cards,
- compact Column Face / `h/2` table,
- detailed ACI/source terms in collapsed audit tables,
- neutral limitations expander,
- no FEA metadata, unit selector, axis declaration, or stage declaration inputs.

The graph shows:

- signed `Tu`,
- `±phiTn`,
- `±phiTth`,
- support-footprint gaps and neutral shading,
- Column Face open circles,
- ACI `h/2` open diamonds and dotted station lines,
- physical-joint amber review markers,
- one `Max |Tu|` marker,
- one governing torsion D/C marker,
- one legend entry per signed capacity/threshold pair.

## Not included

- Combined Shear + Torsion reinforcement adoption,
- final flexure plus `Al` interaction,
- compatibility-torsion redistribution,
- physical segment-joint torsion-transfer design,
- beam-column joint strut-and-tie design,
- PT anchorage/end-zone design,
- development/anchorage verification,
- warping torsion,
- fatigue or seismic detailing,
- Crossbeam Result Summary or Report/QA integration.

## Changed files

```text
concrete_pmm_pro/analysis/crossbeam_uls_torsion.py
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis3_uls_torsion.py
README_CROSSBEAM_ANALYSIS3.md
README.md
```

## QA completed

```text
python -m compileall -q app.py concrete_pmm_pro tests
PASS

ANALYSIS3 focused
12 passed

Crossbeam ULS Analysis / Loads / Navigation targeted
73 passed

Complete Crossbeam suite
562 passed, 5 baseline-existing failures

Untouched ANALYSIS2F baseline comparison
550 passed, the same 5 failures

Shared Bridge/Beam ULS chart/navigation regression
96 passed

Railway U-Girder ULS regression
16 passed
```

The five Crossbeam failures are unchanged legacy source-string assertions in older Prestress Loss / external-handoff milestone tests. They reproduce unchanged in the accepted ANALYSIS2F baseline and are unrelated to ANALYSIS3.

The Plotly figure was built and inspected programmatically, including legend de-duplication, support gaps/shading, support markers, `h/2` station lines, and final title semantics. A live deployed Streamlit browser review remains required before visual acceptance.

## Repo summary

```text
Add ACI 318-19 standalone Crossbeam ULS torsion checks with threshold routing, solid/hollow closed-cage and Outer-Al capacity gates, conservative Column Face/h/2 stations, and Combined V+T adoption guards.
```
