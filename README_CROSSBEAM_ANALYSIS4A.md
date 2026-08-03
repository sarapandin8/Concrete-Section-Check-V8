# CROSSBEAM.ANALYSIS4A — Flexure Step-Envelope Visual Closeout

## Baseline

Developed only from:

```text
concrete-section-pro_CROSSBEAM-ANALYSIS4-direct-uniaxial-development-gate.zip
SHA-256: e843816f3f460e6fd14fb1c96255512fe0b038634c818d83483398f3c8d180df
```

## Scope

This milestone changes only the Portal Frame Crossbeam ULS Flexure chart construction and chart caption. It does not change the Direct P–M3 solver, ACI 318-19 strain compatibility, development-length gate, ordinary-rebar credit result, physical-joint calculations, governing D/C, Project JSON, or any other Member Workflow.

## Visual changes

- Replaces fragmented region-by-region `φMn` traces with one clean **Adopted φMn** engineering envelope per Segment and Load Case.
- Draws binary ordinary-rebar-credit changes as vertical capacity steps; no sloped interpolation is introduced.
- Keeps physical Segment joints as separate Segment traces and overlays amber dotted joint lines.
- Retains all independently solved `s−/s+` joint capacities with smaller open left/right triangle markers.
- Adds pale amber development-zone bands to explain tendon-only/no-rebar-credit capacity regions.
- Adds compact `S1...Sn` Segment labels above the plot.
- Shortens and clarifies the chart caption and title.

## Engineering behavior preserved

- Direct uniaxial Crossbeam P–M3 solver: unchanged.
- `φPn = Pu` adaptive root and force-equilibrium tolerance: unchanged.
- Full-credit versus tendon-only capacities: unchanged.
- ACI development-length calculation and binary gate: unchanged.
- Governing flexural D/C and PASS/FAIL: unchanged.
- Precast/Cast-in-Place routing: unchanged.
- Generic PMM, Bridge/Beam/Girder, Railway U-Girder, and Column/Pier/Wall/Pylon solvers: unchanged.

## Changed files

```text
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis3b_joint_capacity_plot.py
README_CROSSBEAM_ANALYSIS4A.md
```

## QA completed

```text
python -m compileall -q app.py concrete_pmm_pro tests
PASS

Crossbeam direct-flexure / joint-capacity / CIP / JSON / navigation:
39 passed

Shared Beam/Girder ULS chart/workspace regression:
74 passed

Crossbeam Shear / compact Loads-Shear / Torsion regression:
39 passed
```

A complete `tests/test_crossbeam_*.py` run was started but exceeded the execution window before a final summary, so no full-Crossbeam-suite pass is claimed.

## Project JSON visual benchmark

Using `concrete_section_pro_project (27).json`, the calculation remains:

```text
Governing Flexural D/C = 0.548
Solid full-credit φMn = 25,241.40 kN·m
Solid tendon-only φMn = 16,422.33 kN·m
Hollow full-credit φMn = 19,811.69 kN·m
Hollow tendon-only φMn = 15,112.43 kN·m
```

The revised plot displays these results as horizontal capacity zones with vertical binary-credit steps, rather than disconnected floating line fragments.

## Repo summary

```text
Replace fragmented Crossbeam flexural-capacity traces with a Segment-owned adopted φMn step envelope, development-zone shading, and compact one-sided joint markers without changing engineering results.
```
