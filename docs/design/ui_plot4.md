# UI.PLOT4 — ULS Shear Diagram and Failure Diagnosis Polish

## Purpose

Improve the Beam/Girder ULS shear review experience by making the controlling shear status self-explanatory in the main workspace. Before this milestone, the compact table and shear cards could show a clear FAIL while the user had to open the detailed audit table to discover whether the failure came from strength, minimum Av/s, spacing, Vn limit, or zone coverage.

## Scope

This milestone is UI/diagnostic only. It adds:

- A governing shear diagnosis helper for the selected decision row.
- A three-card diagnosis strip in the Shear workspace:
  - Shear diagnosis
  - Evidence
  - Recommended action
- Clear messages for:
  - Strength shear failure
  - Minimum Av/s failure
  - Maximum stirrup spacing failure
  - Nominal Vn limit failure
  - Layout/zone coverage requirement
  - Passing shear check
- A report-style ULS shear plot layout with increased height, bottom legend spacing, explicit axis labels, and a governing decision marker.

## Engineering behavior

No calculation behavior changed. The diagnosis reads the existing shear result row and explains the already-calculated gates:

```text
Strength D/C
Av/s min D/C
Spacing D/C
Vn limit D/C
Status / Strength status / Detailing status
```

## Non-scope

This milestone does not change:

- Shear equations
- φVc / φVs / φVn calculation
- Av/s minimum equation
- Maximum spacing equation
- Flexure or torsion equations
- SLS stress calculation
- Data editor commit logic
- Widget keys
- Project schema
- Load-combination logic
- Geometry generation
- Prestress/debonding logic
- Report certification wording

## QA

Regression coverage was added for:

- Minimum Av/s failure diagnosis text.
- ULS shear plot layout height, legend spacing, and decision marker text.
- Existing ULS girder compact workspace behavior.
