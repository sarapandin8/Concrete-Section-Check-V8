# AASHTO.COL.PMM.QA1 — PMM route QA and UI scope wording

## Purpose

This milestone closes the first QA pass after `AASHTO.COL.PMM1` and `CODE_SYNC3`.
The goal is to verify that Column / Pier / Wall / Pylon PMM does not merely display
an AASHTO label, but routes to the AASHTO LRFD 9th axial-flexure implementation and
keeps unsupported AASHTO shear/torsion checks clearly guarded.

## Scope

Covered in this milestone:

- AASHTO PMM result surface numeric stability in SI internal units.
- AASHTO route separation from the legacy ACI-oriented PMM route.
- Resistance factor application consistency to `Pn`, `Mnx`, and `Mny`.
- AASHTO axial compression cap consistency against the AASHTO helper layer.
- Bonded active and passive prestress metadata in the AASHTO PMM sweep.
- Decision-view UI wording when Project Design Code is AASHTO LRFD.

Not expanded in this milestone:

- AASHTO Column/Pier shear solver.
- AASHTO Column/Pier torsion solver.
- AASHTO combined shear + torsion solver.
- Slenderness / second-order moment magnification.
- Seismic special detailing.
- Hollow rectangular wall local-buckling reduction / adjusted extreme strain.
- Development length, splice, anchorage, confinement, and shop drawing detailing.

## QA findings

The PMM route and solver tests passed, but the Column/Pier decision summary still
contained ACI-specific wording for shear, torsion, and V+T rows even when AASHTO LRFD
was the active Project Design Code.  That wording was safe in the sense that it said
unsupported routes remained guarded, but it was not clean enough for a commercial
engineering UI because AASHTO users could misread the summary as an ACI check route.

## Fixes made

- Added `_column_pier_decision_caption_for_code(...)` so the Column/Pier decision
  caption is code-specific.
- Updated AASHTO decision rows so guarded checks explicitly read as AASHTO
  not-implemented / REVIEW rows, instead of ACI scoped routes.
- Updated decision summary cards so the Code Route and V+T cards are code-specific.
- Added regression tests in `tests/test_aashto_col_pmm_qa1.py`.

## Unit discipline

The AASHTO helper layer remains responsible for applying ksi-based thresholds and
stress-block coefficients safely while the solver uses SI internally:

- geometry: mm / mm²
- stresses: MPa = N/mm²
- forces: N
- moments: N-mm
- display: kN and kN-m

No new imperial formulas were inserted directly in the solver in this milestone.

## Acceptance criteria

This milestone is accepted when:

1. Selecting AASHTO LRFD keeps AASHTO in Setup and Analysis.
2. PMM calls route to AASHTO LRFD when the project code is AASHTO.
3. ACI and AASHTO PMM results are not identical for a high-strength concrete case.
4. AASHTO PMM points contain finite SI values and display-unit conversions.
5. Factored axial and biaxial moment components use the same point-level phi.
6. Axial cap displayed by the solver is consistent with the AASHTO helper.
7. Shear, torsion, and V+T decision rows do not claim ACI scoped checks when AASHTO is active.
