# Concrete Section Pro — CROSSBEAM.RB2G2

## Milestone

`CROSSBEAM.RB2G2 — Hollow transverse bar-piece topology`

## Accepted Hollow topology

The Hollow cross-section preview now represents each transverse bar piece shown
in the accepted detailing sketch:

- 2 complete closed loops: one at the left web and one at the right web.
- 4 flange U-bars: Outer Top, Inner Top, Outer Bottom, and Inner Bottom.
- 4 straight chamfer bars: one parallel to each void chamfer.

There is no fictitious single closed loop around the complete Hollow section.
The web loops follow the outer bottom concrete fillets instead of raising a
rectangular loop above the fillet.

## Geometry rule

Every principal transverse centerline uses the active template's concrete-edge
offset, default 50 mm. Longitudinal preview centers retain the accepted rule:

```text
Longitudinal concrete-edge offset
= Transverse center offset + Dtransverse / 2 + Dlongitudinal / 2
```

For the default Hollow DB12 transverse and DB16 longitudinal bars this remains
`50 + 6 + 8 = 64 mm`.

## Review behavior

- Closed loops, open U-bars, and open straight bars are distinct geometry types.
- Only closed loops are converted to containment polygons.
- Every physical bar piece participates in true-radius clash and topology-
  coverage review.
- A clear Hollow result is labelled `NO GEOMETRIC CLASH — PREVIEW`; it is not a
  code-compliance or capacity certification.
- Av/s remains based only on the template's credited left/right web legs.
  Flange U-bars and chamfer bars receive no automatic solver credit.

## Scope exclusions

This milestone does not alter adopted reinforcement quantities, the Project
JSON schema, ULS/SLS inputs, shear or torsion capacity, confinement
certification, anchorage/development, tendon continuity, or segment-joint shear
transfer.

## Validation

- Changed Python files compile successfully.
- Complete Crossbeam suite: 100 passed.
- Full repository suite: 1,929 passed; the same 6 unrelated baseline failures remain.
- Static Plotly geometry QA: 2 closed loops, 4 U-bars, 4 chamfer bars, 92
  longitudinal bars, and 0 conflicts.
- Default DB12/DB16 nearest transverse-to-longitudinal center distance:
  14.000 mm (within geometry discretization tolerance).
- Every chamfer bar is parallel to and 50.000 mm from its corresponding void
  chamfer.
- Streamlit startup health smoke test returned `ok`.

## Repo summary

Replace schematic Hollow web cages with the accepted two-loop, four-U-bar, and
four-chamfer-bar detailing topology while preserving cage-relative longitudinal
clearance and solver isolation.
