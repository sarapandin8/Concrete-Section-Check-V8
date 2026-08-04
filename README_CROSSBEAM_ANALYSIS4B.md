# CROSSBEAM.ANALYSIS4B — Combined V+T / Shear–Torsion Closeout

## Baseline

Developed only from the latest accepted Crossbeam baseline:

```text
concrete-section-pro_CROSSBEAM-ANALYSIS4A-flexure-step-envelope-visual-closeout.zip
SHA-256: b8deacffb95964ce5a941490755191ddc8e45145949c20e669ef2d1a2d7d514e
```

## Scope

This milestone adds the dedicated Portal Frame Crossbeam:

```text
ULS Strength → Shear + Torsion
```

It closes the sectional adoption path that the standalone Torsion workspace intentionally left at REVIEW:

- ACI 318-19 9.5.4.3 additive transverse reinforcement,
- ACI 318-19 9.5.4.4 prestressed flexure plus torsional longitudinal tension,
- ACI 318-19 22.7.7 combined shear–torsion section-size stress,
- concurrent row-coupled `P / V2 / T / M3`,
- Column Face and prestressed `h/2` checks,
- Precast development-credit and physical-joint scope guards.

Physical Segment-joint V+T transfer remains a separate project `REVIEW REQUIRED` item. The new workspace does not certify interface friction, shear keys, joint compression transfer, anchorage zones, D-regions, fatigue, seismic detailing, or warping torsion.

## Engineering correction identified during closeout

The prior standalone Torsion audit formed its reported transverse area as:

```text
Av(side)/s + 2At/s = 4At/s
```

for one physical closed cage. That credited the same two outer side legs twice. ACI R9.5.4.3 requires the **required** shear and torsion areas to be added before selecting the stirrup; only the legs adjacent to the sides may be included when a group has more than two shear legs.

The corrected single-cage basis is:

```text
Required total = Av,required/s + 2At,required/s
Provided total = actual outer closed-stirrup side legs = 2At,provided/s
```

Inner multi-leg shear bars are not credited in the torsion summation. The standalone minimum-transverse audit now uses the same physical `2At/s` provided basis.

This is an engineering correction, not chart polish. It is conservative and can increase transverse V+T utilization.

## Combined transverse route — ACI 9.5.4.3

At every eligible station:

```text
Av,strength/s = Vs,required / (fyt d)
Av,adopted/s  = max(Av,strength/s, applicable Av,min/s)
Total required = max(Av,adopted/s + 2At,required/s,
                     (Av + 2At)min/s)
Total provided = outer closed-stirrup side legs/s
Transverse D/C = Total required / Total provided
```

The Shear result now exposes strength-required, minimum-required, and adopted-required `Av/s` separately for audit. Shear equations and existing standalone Shear D/C are unchanged.

## Longitudinal route — ACI 9.5.4.4

The torsional strength-equivalent area provides the concentric tensile force:

```text
Ntor = Al,strength fy
Pu,combined = Pu − Ntor       # compression positive
```

The accepted direct exact-axis Crossbeam P–M3 solver then solves:

```text
phi Pn(c) = Pu,combined
```

and checks concurrent imported `M3` without creating an independent-maximum row.

Final longitudinal adoption governs from:

- direct flexure plus torsional-tension D/C,
- ACI minimum longitudinal torsion reinforcement `Al,min`,
- perimeter spacing, minimum diameter, and corner coverage,
- Precast ordinary-bar development credit.

Bonded tendon overstrength may satisfy the strength interaction, but it does not erase minimum ordinary torsion reinforcement or its development/detailing requirements.

## Status semantics

- `PASS`: all eligible sectional stress, transverse, longitudinal, Shear source, Torsion detailing, and direct-solver gates pass.
- `FAIL`: a completed sectional strength/detailing/utilization gate exceeds its limit.
- `REVIEW`: source/layout/development/hollow-cage continuity or other scoped engineering verification remains unresolved.
- Physical-joint one-sided rows remain `REVIEW` and do not replace the governing sectional D/C.

The standalone Shear and Torsion workspaces remain available as component audits. Torsion now directs final adoption to the dedicated `Shear + Torsion` workspace.

## Project JSON benchmark

Using:

```text
concrete_section_pro_project (27).json
16 imported ULS rows
22 eligible sectional/imported/support checks
10 one-sided physical-joint audit rows
32 combined result rows
```

The current reinforcement design does **not** pass Combined V+T:

```text
Combined sectional status: FAIL
Overall module status: FAIL

Governing overall station:
ULS-01 · S2 · s = 6.000 m
Stress D/C       = 0.427
Transverse D/C   = 1.380
Longitudinal D/C = 2.262
Overall D/C      = 2.262
```

The largest transverse utilization occurs in the Hollow regions at approximately:

```text
S2 / S5 · s = 8.000 / 22.000 m
Transverse D/C = 1.463
```

For the governing Hollow source:

```text
Al,min required = 22,741.39 mm²
Outer Al provided = 10,053.10 mm²
Al,min D/C = 2.262

Direct 9.5.4.4 flexure-plus-torsional-tension D/C ≈ 0.094
Direct solver force residual < 1 N
```

Therefore the current project failure is controlled by reinforcement adoption, not by the direct P–M3 numerical solver. The user must revise the Hollow Segment transverse closed cage and longitudinal perimeter reinforcement before a design PASS is possible.

## UI / chart

The new chart follows the existing Concrete Section Pro utilization language:

- `Stress D/C`
- `Transverse D/C`
- `Longitudinal D/C`
- `Limit = 1.0`
- `Gov. V+T`
- physical-joint `REVIEW` markers
- support-footprint shading

The main page remains decision-first; detailed ACI terms, direct-solver residuals, reinforcement areas, and development sources remain in collapsed audit tables.

## Changed files

```text
concrete_pmm_pro/analysis/crossbeam_uls_combined_vt.py   [new]
concrete_pmm_pro/analysis/crossbeam_uls_shear.py
concrete_pmm_pro/analysis/crossbeam_uls_torsion.py
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis4b_combined_vt.py           [new]
tests/test_crossbeam_analysis3_uls_torsion.py
README_CROSSBEAM_ANALYSIS4B.md                            [new]
```

## Protected behavior

No changes were made to:

- Direct Crossbeam P–M3 solver equations,
- Crossbeam Flexure result or chart,
- generic PMM solver or capacity interpolation,
- Bridge/Beam/Girder solvers,
- Railway U-Girder solvers,
- Column/Pier/Wall/Pylon solvers,
- SLS, Prestress Loss, Loads, Project JSON, Result Summary, or Report/QA behavior.

## QA completed

```text
python -m compileall -q app.py concrete_pmm_pro tests
PASS

Crossbeam Shear:
21 passed

Crossbeam standalone Torsion:
13 passed

Combined V+T focused:
9 passed

Crossbeam Flexure / joint plotting / compact Loads-Shear:
22 passed

Shared Beam/Girder ULS V+T chart/workspace:
76 passed

Generic PMM benchmarks:
21 passed

Crossbeam CIP / Project JSON / navigation / Loads:
36 passed
```

The groups above were executed as separate targeted/regression runs. No full-repository green claim is made.

## Repo summary

```text
Add a Crossbeam ACI 318-19 combined shear–torsion workspace, correct outer-stirrup area accounting to prevent double counting, and close concurrent transverse and prestressed longitudinal V+T adoption with physical-joint review guards.
```
