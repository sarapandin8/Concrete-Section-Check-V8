# CROSSBEAM.ANALYSIS3C — Torsion Demand Continuity and Flexure Capacity Trace Semantics

## Baseline

Developed from the accepted baseline:

```text
concrete-section-pro_CROSSBEAM-ANALYSIS3B-segment-owned-one-sided-joint-capacity.zip
```

## Purpose

Close two chart-semantics defects without changing any accepted ACI 318-19 equation or solver result:

1. `Tu` appeared to disappear at physical Segment joints because the generic trace breaker inserted artificial gaps at every joint.
2. `phiMn` was connected linearly from one Segment/Section source to the next, creating false sloping capacity transitions across Solid/Hollow physical joints.

## Torsion demand trace

`Tu` is now plotted as separate Segment-owned traces:

- every available imported/generated station is retained;
- Column Face and ACI `h/2` stations remain available;
- left/right physical-joint demands terminate/start at the exact joint station;
- no diagonal or vertical interpolation is drawn from one side of a physical joint to the other;
- if the two one-sided demands are equal, adjacent traces visually meet;
- if they differ, the values remain separate at the same station;
- only the portions inside applied Column/Support footprints are omitted.

The existing joint-side markers and joint-transfer `REVIEW` status remain unchanged.

## Flexure capacity trace review and correction

The station PMM calculations were not changed. `phiMn(Pu)` continues to be calculated independently from the actual station-specific:

- axial demand `Pu`,
- Section ID and concrete source,
- ordinary longitudinal reinforcement source,
- bonded tendon geometry and effective prestress,
- bending direction.

The observed slopes between Solid and Hollow regions were a chart interpolation artifact. The Crossbeam Flexure chart now rebuilds `phiMn` as separate Segment-owned traces:

- station-dependent variation inside one Segment is preserved;
- no line crosses a physical Segment joint;
- Solid/Hollow capacity values are never linearly interpolated across a boundary;
- the governing Flexure D/C marker and the imported `M3` demand diagram are unchanged.

This milestone does not fabricate an uncalculated exact joint capacity. If no exact Flexure station exists at a joint, adjacent Segment traces stop/start at their nearest calculated station rather than drawing a false connecting slope.

## Engineering equations

No equation or strength result changed:

- ACI PMM strain-compatibility Flexure,
- `phiMn(Pu)` and Flexural D/C,
- torsion `Tth`, `Tn`, transverse and longitudinal reinforcement checks,
- section-size/detailing limits,
- shear calculations,
- one-sided joint demand recovery.

## Files changed

```text
concrete_pmm_pro/ui/analysis_page.py
tests/test_crossbeam_analysis3b_joint_capacity_plot.py
README_CROSSBEAM_ANALYSIS3C.md
README.md
```

## QA completed

```text
Compileall:
PASS

Crossbeam Flexure / Shear / Torsion + shared Bridge/Beam ULS chart regression:
125 passed

ANALYSIS3B/3C focused trace tests:
5 passed

Crossbeam suite early gate:
316 passed
5 baseline-existing source-string assertion failures
```

The five failures are the unchanged Prestress-Loss / external-FEA handoff wording assertions already present in the ANALYSIS3B baseline. A longer Crossbeam run excluding those five was attempted and progressed beyond 88 percent before the sandbox time limit; no new failure was observed before timeout.

## Repo summary

```text
Keep Crossbeam Tu visible at every Segment station except support interiors and split phiMn capacity traces at physical joints so no Solid/Hollow capacity is linearly interpolated, without changing ACI calculations.
```
