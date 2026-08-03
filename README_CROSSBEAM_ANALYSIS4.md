# CROSSBEAM.ANALYSIS4 — Direct ACI P–M3 Flexure + Precast Development Gate

## Baseline

- Starting ZIP: `concrete-section-pro_CROSSBEAM-ANALYSIS3D-flexure-segment-trace-continuity.zip`
- Starting SHA-256: `4cb62fba50fc4453ec5a8bf992104c2462c2fbcbd5de340bcdad63984bb948d9`
- Scope is limited to **Portal Frame Crossbeam — ULS Flexure** plus its chart/audit presentation.

## Production engineering route

Crossbeam Flexure no longer obtains directional `φMn(Pu)` from the generic discretized biaxial PMM surface. The production route is now:

```text
Pu + signed M3
→ exact section Mx bending axis
→ ACI 318-19 strain compatibility
→ Whitney compression block + ordinary rebar + bonded tendons
→ adaptive bracketed solution of φPn(c) = Pu
→ direct φMn and D/C
```

The solver:

- is implemented in `concrete_pmm_pro/analysis/crossbeam_flexure_uniaxial.py`;
- uses a workflow-scoped exact-axis neutral-axis depth solution;
- applies the existing ACI concrete, rebar, bonded-prestress stress/strain, and strain-based `φ` models;
- retains a separate ACI compression axial D/C;
- reports `c`, `a`, `φ`, net tensile strain, strain condition, force residual, bracket count, and iterations;
- uses a production equilibrium tolerance not exceeding 1 N or `1e-8` of the axial-force scale, whichever is larger;
- is independent of Fast / Standard / High Accuracy PMM angle/depth presets.

The generic `pmm_solver.py` and `capacity_check.py` are unchanged and remain the production routes for workflows that require a biaxial PMM surface.

## Crossbeam accuracy preset

The Crossbeam-scoped legacy/reference preset defaults to:

```text
High Accuracy
```

It is no longer shown as a primary production control because the direct P–M3 result is preset-independent. Other member-workflow defaults are not changed.

## Precast Segmental ordinary-rebar strength credit

For `Construction Method = Precast Segmental`:

```text
Fully developed Segment interior:
Concrete + bonded tendons + ordinary longitudinal rebar

Physical Segment joint:
Concrete + bonded tendons only

Unverified development zone adjacent to a joint:
Concrete + bonded tendons only
```

The binary gate is based on:

- ACI 318-19 25.4.1.1 development on each side of a checked section;
- Table 25.4.2.3 `Other cases`;
- conservative `ψt = 1.3` for all active strength-credit bars;
- uncoated normalweight reinforcement;
- no confinement reduction credit;
- the applicable high-strength reinforcement factor `ψg`;
- the ACI concrete-strength limit used for development length;
- minimum `ld = 300 mm`;
- governing `ld` from the active outer/inner longitudinal bar systems.

This is a **strength-credit gate**, not a replacement for final anchorage detailing. Hooked, headed, mechanical, or project-specific anchorage credit is not assumed.

For `Construction Method = Cast-in-Place`, the Precast joint/development exclusion does not apply; ordinary reinforcement retains the existing monolithic-zone route.

## Generated safety checks

The Crossbeam station adapter now adds:

- two independently owned section-capacity rows at every physical joint (`J1-L/J1-R` …);
- row-coupled physical-joint demand recovered from an exact FEA row or shared bracketing member-force interpolation;
- development-boundary checks at each applicable `Segment start + ld` and `Segment end − ld`;
- no average of left/right Section, rebar, or tendon capacity sources.

For the accepted six-Segment benchmark this creates:

```text
16 imported ULS rows
10 one-sided physical-joint capacity rows
12 development-boundary rows
38 total Crossbeam Flexure checks
```

## Chart behavior

- `φMn` traces are owned by each Segment and each binary rebar-credit interval.
- Tendon-only development zones and full-credit interiors are separate traces.
- No sloped interpolation is drawn across a development gate or physical joint.
- Actual one-sided joint capacities are shown with `Joint φMn (s−/s+)` markers.
- Stable capacities extend only to the true limits of their own credit interval.
- The audit table retains every generated and imported check row.

## Independent benchmark from the accepted 30 m project JSON

For `Pu = 5,000 kN`, positive M3, ACI 318-19:

| Capacity basis | Direct φMn (kN·m) |
|---|---:|
| CB-S01 Solid — fully developed ordinary rebar | 25,241.40 |
| CB-H01 Hollow — fully developed ordinary rebar | 19,811.69 |
| CB-S01 Solid — tendon-only joint/development zone | 16,422.33 |
| CB-H01 Hollow — tendon-only joint/development zone | 15,112.43 |

Maximum force-equilibrium residual in the benchmark is below `1 N` (residual ratio below `2e-7`). The benchmark is stored as a regression fixture under `tests/data/`.

The sample project governing Flexural D/C changes from the former PMM-interpolated interior result to approximately:

```text
D/C = 0.548
```

because the governing `Mu = 9,000 kN·m` occurs in a tendon-only development/joint region. This is an intentional conservative change, not a chart-only change.

## Files changed

```text
concrete_pmm_pro/analysis/crossbeam_flexure_uniaxial.py  (new)
concrete_pmm_pro/analysis/crossbeam_uls.py
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis1a_uls_adapter.py
tests/test_crossbeam_analysis3b_joint_capacity_plot.py
tests/test_crossbeam_analysis4_direct_uniaxial.py        (new)
tests/data/crossbeam_analysis4_direct_solver_benchmark.json (new)
README_CROSSBEAM_ANALYSIS4.md                            (new)
```

## Explicitly unchanged

- Generic ACI/AASHTO biaxial PMM solver and directional capacity checker
- Column/Pier/Wall/Pylon solver routing
- Bridge/Beam, Building Beam, and Railway U-Girder calculation equations/defaults
- Crossbeam Shear equations and chart routing
- Crossbeam Torsion equations and chart routing
- Loads, Prestress Loss, SLS, Result Summary, Report/QA, and Project JSON schemas
- Cast-in-Place reinforcement continuity semantics

## QA status

Focused Crossbeam Flexure/direct/chart tests, Crossbeam Shear/Torsion tests, CIP/Project JSON/navigation regressions, and generic PMM/capacity benchmarks were run. The complete wildcard Crossbeam suite was attempted but did not complete within the execution window, so this release does not claim a full Crossbeam-suite pass.

One shared Result Summary source-string assertion fails identically in the ANALYSIS3D baseline and is unrelated to this milestone.

## Repo summary

```text
Replace Portal Frame Crossbeam PMM interpolation with a direct ACI P–M3 strain-compatibility solver and apply binary ordinary-rebar strength credit only in fully developed Precast Segment interiors, with tendon-only joint/development capacities and non-interpolated audit traces.
```
