# CROSSBEAM.ANALYSIS4C2 — Solver Adoption Correction

**Project:** Concrete Section Pro  
**Workflow:** Portal Frame Crossbeam — Prestressed Concrete  
**Member design basis:** ACI 318-19  
**Accepted input baseline:** `CROSSBEAM.ANALYSIS4C1B`  
**Milestone role:** engineering solver/source adoption; visual and print closeout remains a later milestone

## 1. Purpose

This milestone makes the Crossbeam Shear, standalone Torsion, and combined Shear + Torsion routes consume the reinforcement source contract accepted in ANALYSIS4C1B.

The governing rule is that every physical bar is counted once:

- `Av` uses all effective shear legs.
- `At` uses one leg of the verified outer closed torsion cage.
- A verified **additional** outer cage contributes its two side legs once to the physical transverse-steel pool.
- A cage **shared** with the existing outer shear loop is already included in `Av` and is not added again.
- `Al` is the outer-cage-associated subset of physical longitudinal `As`; it is not duplicate steel.

## 2. Engineering changes

### 2.1 Unique physical transverse-steel accounting

A new Crossbeam-scoped source record assembles:

```text
Base Av/s
+ verified additional outer-cage side legs/s, when applicable
= unique physical transverse steel/s
```

For a shared cage, the added term is zero.

### 2.2 Shear adoption

The standalone ACI prestressed shear route now credits the unique physical vertical-leg pool. Therefore a verified additional outer cage can contribute to `Vs`, while a shared cage is never counted twice.

### 2.3 Standalone torsion adoption

The Torsion route now uses:

- `At`, spacing, offset, `Aoh`, `Ao`, and `ph` from the verified user-defined outer cage;
- the unique physical transverse pool for the ACI minimum total transverse-reinforcement gate;
- outer longitudinal bars associated with the actual cage perimeter for `Al` area, spacing, diameter, corner coverage, and cage-containment review.

`Tn` itself continues to use `At` and the actual outer-cage geometry, not all shear legs.

### 2.4 Combined Shear + Torsion

The Crossbeam-scoped combined route checks:

- ACI 9.5.4.3 required `Av/s + 2At/s` against the unique physical transverse-steel pool;
- ACI 9.5.4.4 prestressed flexure under concurrent `Mu`, `Pu`, and the additional concentric torsional tensile force `Al,strength fy` using the accepted direct P–M3 solver;
- minimum/perimeter `Al` as a separate ordinary-reinforcement gate;
- ACI 22.7.7 combined shear-torsion section-size stress;
- one-sided physical-joint values as `REVIEW`, without granting joint-transfer PASS.

### 2.5 Torsion continuation and support anchorage screens

For Precast Segmental construction, the route reports the required continuation distance `bt + d` and compares it with the available distance to the nearest physical Segment end. Reinforcement continuity across a physical joint is never assumed.

- insufficient automatically verifiable continuation → `REVIEW`;
- a Column Face requiring torsion → support anchorage `REVIEW` because hook/embedment details are not modeled;
- numerical failures remain `FAIL` and are not hidden by a review gate.

This is a conservative template-coverage screen. Physical-joint transfer, bar hooks/laps, D-regions, and final drawing details remain project checks.

## 3. Verification with the current 30 m project JSON

The uploaded project was reloaded and the Hollow template was set to:

```text
Outer cage: DB12 @ 200 mm
Centerline offset: 50 mm
Relationship: Additional outer cage
Closure: Verified closed loop
```

### Adopted reinforcement

```text
Base Hollow Av/s                         = 2.261947 mm²/mm
Additional outer-cage side legs/s       = 1.130973 mm²/mm
Unique physical transverse steel/s      = 3.392920 mm²/mm
Outer-cage At/s                         = 0.565487 mm²/mm
Outer-associated Al provided            = 10,053.096 mm²
```

### Results

```text
Shear sectional status                  = PASS
Shear overall status                    = REVIEW (physical joints)
Governing Shear strength D/C            = 0.529986

Standalone Torsion sectional/overall    = FAIL
Governing Torsion component D/C         = 2.262128 (minimum Al)

Combined V+T sectional/overall          = FAIL
Governing station                       = S2 at s = 6.000 m
Stress D/C                              = 0.427222
Transverse D/C                          = 0.271509
Longitudinal / Overall D/C              = 2.262128
Required Av/s + 2At/s                   = 0.921208 mm²/mm
Unique transverse steel provided        = 3.392920 mm²/mm
Al,min required                         = 22,741.393 mm²
Al provided                             = 10,053.096 mm²
Direct flexure + torsion D/C             = 0.093792
Direct force-equilibrium residual       = -0.601 N
Required bt + d continuation            = 3.600 m
Available to nearest Segment end        = 1.500 m
Torsion continuation status             = REVIEW
```

The previous Combined transverse failure was therefore a false failure caused by discarding effective inner shear legs. After unique-steel adoption, transverse reinforcement passes; minimum longitudinal torsion reinforcement remains the controlling failure.

## 4. Files changed

```text
concrete_pmm_pro/crossbeam/transverse.py
concrete_pmm_pro/analysis/crossbeam_uls_shear.py
concrete_pmm_pro/analysis/crossbeam_uls_torsion.py
concrete_pmm_pro/analysis/crossbeam_uls_combined_vt.py        [new]
concrete_pmm_pro/ui/crossbeam_transverse_page.py
concrete_pmm_pro/ui/crossbeam_rebar_page.py
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis3_uls_torsion.py
tests/test_crossbeam_analysis4c2_solver_adoption.py           [new]
README_CROSSBEAM_ANALYSIS4C2.md                               [new]
```

## 5. Regression protection

Hash comparison against ANALYSIS4C1B confirmed no changes to:

```text
app.py
concrete_pmm_pro/analysis/pmm_solver.py
concrete_pmm_pro/analysis/crossbeam_flexure_uniaxial.py
concrete_pmm_pro/analysis/crossbeam_uls.py
concrete_pmm_pro/io/project_io.py
concrete_pmm_pro/crossbeam/rebar_persistence.py
```

Therefore this milestone does not change the generic PMM solver, accepted direct Flexure solver, or Project JSON schema.

## 6. QA completed

```text
Compileall                                            PASS
Crossbeam Analysis / Shear / Torsion / Flexure        72 passed
Crossbeam Rebar / Transverse / JSON / CIP / Nav       87 passed
Generic RC / Prestressed / AASHTO PMM                 155 passed
Shared Beam/Girder ULS                                81 passed
```

One shared Result Summary source-string assertion remains failed. The identical assertion also fails in the accepted ANALYSIS4C1B baseline, and `app.py` is byte-identical in this milestone. It is not attributed to ANALYSIS4C2.

The complete repository suite was not claimed as green.

## 7. Deferred to ANALYSIS4C3

- final row taxonomy and count wording;
- PASS / FAIL / REVIEW presentation closeout;
- physical-joint graph gaps and marker semantics;
- generated support-check evidence on the main page;
- required/provided/action cards;
- print-safe PDF tables and pagination;
- final visual QA of Shear, Torsion, and Combined V+T.

## Repo summary

```text
Correct Crossbeam shear–torsion solver adoption by counting every physical transverse leg once, using verified cage geometry and cage-associated Al, and adding direct prestressed V+T plus bt+d continuation review.
```
