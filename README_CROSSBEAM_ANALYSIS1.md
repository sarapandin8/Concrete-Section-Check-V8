# CROSSBEAM.ANALYSIS1 — Three-Stage Station-Check Foundation

## Scope

Adds the first production-routed Analysis workspace for **Portal Frame Crossbeam — Prestressed Concrete** without running a structural design solver.

The workspace consumes the existing validated Crossbeam Loads handoff and keeps three independent datasets:

- ULS Final Stage
- SLS At Transfer
- SLS At Service

Each active imported force row is mapped to:

- source row and source fingerprint,
- station and optional Check Point,
- one-sided `s-` / `s+` face at internal boundaries when applicable,
- active Segment / Zone,
- active project Section ID and gross-property readiness,
- active Longitudinal Rebar Template,
- active Transverse / Shear Template,
- unchanged row-coupled `P, V2, T, M3` resultants.

## Construction semantics

- **Precast Segmental:** internal boundaries are physical segment joints. Both faces remain explicit when the Check Point does not select Left/Right. Ordinary rebar across the joint remains `0 mm² (LOCKED)`. SLS joint contexts identify the future project gate requiring top and bottom compression of at least `0.70 MPa` for every Transfer and Service case.
- **Cast-in-Place:** internal boundaries are Section / analysis-zone boundaries in one monolithic member. Solid Section IDs only; the physical-joint `0.70 MPa` gate does not apply.

## Design basis shown

- Member design code: **ACI 318-19**
- Prestress-loss basis: **AASHTO LRFD 2020 Section 5.9.3**

## Deliberate exclusions

No engineering equation or solver was added in this milestone. The workspace does not calculate:

- SLS concrete stress,
- segment-joint compression,
- ULS axial-flexure,
- shear,
- torsion or combined V+T,
- anchorage-zone or D-region strength.

Result Summary and Report / QA remain read-only and are not connected to this source foundation yet. Project JSON analysis-result persistence was not added.

## Files

- `concrete_pmm_pro/crossbeam/analysis_foundation.py`
- `concrete_pmm_pro/ui/crossbeam_analysis_page.py`
- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_crossbeam_analysis1_three_stage_foundation.py`

## Regression protection

The shared Analysis page routes Crossbeam to its own workflow-scoped page. Existing Column/Pier, Bridge Beam/Girder, and Building Beam/Girder subpages remain unchanged. Opening the Crossbeam input foundation does **not** mark ULS/SLS analysis as `CURRENT` because no solver has run.

## Repo summary

Add a Crossbeam-specific three-stage Analysis input foundation with station-to-section/rebar mapping, one-sided segment-joint traceability, and no-solver readiness gates.
