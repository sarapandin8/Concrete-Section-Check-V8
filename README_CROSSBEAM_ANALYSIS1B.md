# CROSSBEAM.ANALYSIS1B — Zero-Moment Endpoint Capacity & D/C Separation

## Scope

- Keep Crossbeam ULS rows with `M3 = 0` as real section checks at the imported
  `Pu`; do not replace section capacity with a zero diagram-boundary value.
- Resolve the bending sign only from the nearest nonzero `M3` station in the
  same Load Case. The reference magnitude is never substituted into demand.
- Calculate and plot `phiMn(Pu)` at zero-M3 head/tail stations.
- Report `Flexural D/C = 0.000` separately from compression `Axial D/C`.
- If one Load Case contains no nonzero M3 station, do not guess the direction;
  show `REVIEW` and retain the axial ratio for audit.
- At duplicate physical-joint faces with equal Flexural D/C, plot the lower
  finite capacity as the conservative chart face.
- Bump the Crossbeam flexure fingerprint/result schema so stale ANALYSIS1A
  endpoint results are not presented as current.

## Protected behavior

- Existing ACI 318-19 PMM equations, strain compatibility, and phi-factor
  policy are unchanged.
- Imported `P/V2/T/M3` demand mapping is unchanged; `Pe` and secondary
  prestress are not added again.
- Precast physical Segment joints still receive zero ordinary longitudinal
  rebar credit, while source-ready bonded Tendons remain the continuity source.
- Crossbeam Prestress Loss, Loads, Project JSON, Result Summary, and Report / QA
  behavior are unchanged.
- Generic Bridge/Building Beam-Girder and Column/Pier workflows are unchanged.
- No result-cache persistence is added.

## QA

- Zero-M3 endpoint direction, capacity, Flexural D/C, and separate Axial D/C
  targeted tests pass.
- No-direction same-case guard and conservative duplicate-face chart selection
  targeted tests pass.
- Real PMM smoke: both zero-M3 member ends return finite `phiMn(Pu)`, with
  opposite capacity signs when their nearest same-case reference stations have
  opposite M3 signs.
- PMM/Analysis regression: 262 passed.
- Crossbeam regression: 471 passed; 8 baseline-existing failures reproduce the
  previously recorded AUTOFLOW1/ANALYSIS1A state and are outside this milestone.

## Repo summary

Calculate Crossbeam phiMn at zero-moment endpoints using the nearest same-case bending direction, separate flexural and axial D/C, and conservatively select duplicate joint-face capacity.
