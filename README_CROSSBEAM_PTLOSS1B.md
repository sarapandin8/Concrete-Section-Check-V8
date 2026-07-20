### CROSSBEAM.PTLOSS1B - Loss Table Readability Polish

PTLOSS1B polishes the Crossbeam `Prestress Loss` page after reviewing the
printed PDF layout of PTLOSS1A.  It keeps the PTLOSS1A AASHTO friction/wobble
calculation unchanged.

#### What changed

- Shortens the station trace `K use` values to compact reviewer text:
  `Internal: AASHTO K` and `External: N/A, no Kx`.
- Shortens the station trace `mu basis` values to `Internal duct mu` and
  `HDPE-lined: adopted 0.25`.
- Splits the assumptions caption into two shorter lines so the PDF/browser
  print layout is easier to read.
- Keeps external HDPE-lined `mu = 0.25` as the conservative adopted value and
  keeps AASHTO polyethylene `mu = 0.23` visible as a reference.
- Adds regression coverage so the compact row wording remains stable.

#### Scope guard

- No formula, force, Project JSON, navigation, solver, SLS, ULS, anchorage set,
  elastic shortening, creep, shrinkage, relaxation, report, or D-region logic
  is changed.
- External tendon loss remains a deviator-preview calculation until a detailed
  deviator table is implemented.

#### Repo summary

Polish Crossbeam Prestress Loss table readability with compact K/mu basis wording and shorter assumptions captions while preserving the PTLOSS1A AASHTO friction/wobble calculations.
