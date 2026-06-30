# PRESTRESS.DEBOND.VIEW1 — Debonding Elevation Schematic and Row Summary

## Scope

This milestone replaces the old `Debonding along span` row-line chart with an elevation-style debonding schematic intended to communicate strand debonding as a drawing/detailing view.

The change is limited to the Prestress UI and tests. It does **not** change solver equations, effective prestress calculations, prestress loss calculations, PMM, SLS stress, geometry generation, section properties, load equations, report logic, or project schema.

## User-facing behavior

- Solid blue segments indicate bonded/effective strand portions.
- Red dashed end segments indicate debonded sleeve lengths from the girder ends.
- Row labels show total strand count and number of debonded strands.
- The schedule table now includes a compact `Debond pattern` and `Default row debond m` field.
- Railway U-Girder uses a one-web schematic by default because the current drawing layout is left/right symmetric.

## Railway U-Girder default debond length rule

For Railway U-Girder rows, when the engineer enters debonded strand numbers but leaves the debond length at zero, the app seeds a row default:

```text
debond_length(row i) = max(0, L/5 - 0.5 × (i - 1)) m
```

For `L = 10.0 m` this gives:

| Row | Default debond length |
|---|---:|
| Row 1 | 2.0 m |
| Row 2 | 1.5 m |
| Row 3 | 1.0 m |
| Row 4 | 0.5 m |
| Row 5 | 0.0 m |

Row 1 is the bottom strand row. The default rule is applied only after debonded strand numbers are selected; it does not automatically debond all strands.

## Guardrails

- The schematic is a detailing/preview view only.
- Transfer-length force build-up after sleeve transitions remains a future milestone.
- Debonding still requires engineering review before use in final stress calculations.
- One-web display is a UI simplification for symmetric Railway U-Girder layouts, not a hard-coded assumption for every future girder family.
