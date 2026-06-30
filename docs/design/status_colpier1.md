# STATUS.COLPIER1 — Column/Pier Scoped PASS Status Alignment

This milestone aligns the Column/Pier ACI RC nonprestressed Shear, Torsion, and Shear + Torsion detail tabs with the existing Column/Pier ULS Decision Summary.

## Scope

- Promote implemented Column/Pier ACI RC nonprestressed shear detail rows from `Preview PASS/FAIL` wording to scoped `PASS/FAIL` wording when all implemented gates are complete.
- Promote implemented Column/Pier ACI RC nonprestressed torsion detail rows from `Preview PASS/FAIL` wording to scoped `PASS/FAIL` wording when threshold/strength, longitudinal `Al`, transverse reinforcement, and spacing gates are complete.
- Keep combined V+T source-gate logic compatible with both older `Preview PASS/FAIL` rows and new scoped `PASS/FAIL` rows.
- Keep `REVIEW` for AASHTO LRFD routes, active prestress in V/T, incomplete geometry/material/reinforcement inputs, open ties for torsion, and unsupported scope.
- Keep torsion `BELOW THRESHOLD` when all active Tu rows are below the implemented ACI torsion threshold screen.

## Not changed

- No PMM, shear, torsion, V+T, prestress, SLS, deflection, load, or report calculation formulas are changed.
- No solver equations are changed.
- No AASHTO LRFD, prestressed V/T, seismic confinement, anchorage, lap-splice, or shop-drawing certification is added.

## Engineering boundary

`PASS` in these Column/Pier tabs means the current visible rows pass the implemented ACI RC nonprestressed section gates for the current stored input data. It does not certify excluded detailing or project-authority items.

Excluded items that remain engineering review include seismic special confinement, hook/anchorage detailing, lap splices, constructability, local end-zone detailing, AASHTO LRFD, prestressed shear/torsion interaction, and independent project benchmark acceptance.
