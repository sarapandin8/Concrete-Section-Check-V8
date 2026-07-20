### CROSSBEAM.PTLOSS1D - External Note Table Compactness Polish

PTLOSS1D polishes the Crossbeam `Prestress Loss` external tendon review text
after checking the PDF/export layout of PTLOSS1C.

#### What changed

- Shortens the nonblocking external HDPE-lined review note shown in station
  trace and per-tendon summary tables to keep exported tables readable.
- Shortens the blocking no-deviator message while preserving the engineering
  meaning that the AASHTO `+0.04 rad/deviator` term has not been applied.
- Adds regression assertions for the compact review-note and no-deviator
  wording so future wording changes stay intentional.

#### Scope guard

- No AASHTO friction/wobble equation, `Pj`, status rule, summary metric,
  Project JSON, navigation, solver, SLS, ULS, anchorage set, elastic shortening,
  creep, shrinkage, relaxation, report, anchorage-zone, deviator-force, or
  D-region logic is changed.

#### Repo summary

Polish Crossbeam Prestress Loss external tendon table notes with compact review and no-deviator wording while preserving PTLOSS1C calculation behavior.
