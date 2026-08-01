# CROSSBEAM.ANALYSIS1A — ULS Station-Force Adapter and Run Readiness

## Baseline

- Starting ZIP: `concrete-section-pro_CROSSBEAM-AUTOFLOW1-auto-loss-handoff-simplified-imports.zip`
- Starting SHA-256: `605bb47d87ba8090444d6ebd6a5ea50d5ac7ec5eb02b32e0e354362324260957`

## Problem corrected

Crossbeam ULS resultants were stored in `crossbeam_uls_loads_table`, but the
Analysis page fell through to the generic Column/Pier PMM workflow and required
generic `load_cases`. The Crossbeam station-force handoff therefore had no
consumer and the Calculate action remained blocked even when its own sources
were ready.

## Implemented route

- Route Portal Frame Crossbeam ULS Strength to a dedicated station adapter
  before the generic Analysis preflight.
- Read active canonical Crossbeam `P/V2/T/M3` rows directly.
- Map compression-positive `P` to PMM `Pu` and sagging-positive `M3` to PMM
  `Mux`; retain `V2` and `T` with the same row for audit only.
- Rebuild Section ID, concrete, generated ordinary reinforcement, tendon
  profile position, bond state, and effective prestress at every check station.
- At a Precast physical Segment joint, omit ordinary longitudinal rebar and
  credit only bonded Tendons that have valid profile coverage and a
  CURRENT/CLOSED average `fpe` source.
- Treat Cast-in-Place Zone boundaries as property boundaries rather than
  physical joints.
- Use imported external-FEA resultants once. `Pe` and secondary prestress are
  not added to demand inside Analysis.
- Cache results with deterministic engineering fingerprints that exclude
  runtime-generated model UUIDs.
- Guard Crossbeam SLS and Deflection tabs instead of accidentally running a
  generic girder route.

## Protected behavior

- Existing PMM equations, ACI strain compatibility, and phi-factor policy are
  unchanged.
- Crossbeam PT Loss and Loads equations/contracts are unchanged.
- Generic Column/Pier, Bridge Girder, and Building Girder routes are unchanged.
- This milestone does not calculate Shear, Torsion, combined V+T, SLS stress,
  deflection/camber, physical-joint shear transfer, anchorage/development,
  transition D-regions, or seismic detailing.
- Permanently unbonded/external Tendons are not silently credited by the bonded
  section-strain route; any otherwise passing result is downgraded to REVIEW.

## QA

- New adapter tests cover generic-load-case independence, row-coupled mapping,
  interior versus physical-joint reinforcement credit, effective-prestress
  blocking, deterministic cache fingerprints, existing-PMM invocation, and UI
  routing.
- A real existing-PMM smoke run completed two station checks (interior and
  physical joint) without solver errors.
- Selected Analysis regression: 128 passed.
- Complete Crossbeam regression: 468 passed and 8 baseline-existing failures;
  all eight failures reproduce on the untouched AUTOFLOW1 ZIP.

## Repo summary

Connect Crossbeam ULS station forces to the existing ACI PMM engine with
station-specific Section/Rebar/Bonded-Tendon mapping, physical-joint continuity
rules, deterministic caching, and no duplicate prestress demand.
