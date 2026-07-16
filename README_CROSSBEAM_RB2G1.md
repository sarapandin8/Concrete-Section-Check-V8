# Concrete Section Pro — CROSSBEAM.RB2G1

## Milestone

`CROSSBEAM.RB2G1 — Cage-relative longitudinal offset correction`

## Corrected rule

The active-Zone longitudinal preview center is derived from its transverse cage:

```text
Longitudinal concrete-edge offset
= Transverse center offset + Dtransverse / 2 + Dlongitudinal / 2
```

The second radius is the longitudinal bar radius, not a repeated transverse radius unless both diameters are equal.

Examples:

- Hollow default: DB12 transverse + DB16 longitudinal → `50 + 6 + 8 = 64 mm`.
- Solid default: DB16 transverse + DB20 longitudinal → `50 + 8 + 10 = 68 mm`.

## Implemented

- Kept the transverse center offset at the active template value, default 50 mm.
- Derived Outer and Inner longitudinal preview offsets dynamically from the active Zone's transverse and longitudinal bar sizes.
- Fitted Solid perimeter bars and Hollow web/corner bars to the actual cage path so bottom fillets and locally raised rectangular cages retain exact bar-to-cage contact.
- Preserved top/bottom Hollow flange-face bars between the independent web cages and checked them for cage clash without pulling them sideways into a web cage.
- Changed the old longitudinal offset editor label to `Fallback offset (mm)` for backward compatibility; it does not override an active cage-relative Zone preview.
- Updated the Geometric fit review so default Solid and Hollow previews report zero conflicts and `READY FOR DETAILING REVIEW` when geometry is valid.

## Scope exclusions

This change adjusts preview coordinates only. It does not alter adopted reinforcement quantities, Project JSON schema, ULS/SLS solver inputs, ACI compliance, shear/torsion capacity, confinement certification, tendon continuity, or segment-joint shear transfer.

## Validation

- Changed Python files compiled successfully.
- Complete Crossbeam suite: 99 passed.
- Full repository suite: 1,928 passed; the same 6 unrelated baseline failures remain.
- Exact geometry checks confirmed 14.0 mm center-to-center clearance for DB12/DB16 Hollow web bars and 18.0 mm for DB16/DB20 Solid bars.
- Static Plotly review confirmed corrected Solid and Hollow combined figures with zero conflicts.
- Streamlit server startup smoke test completed successfully.

## Repo summary

Derive Crossbeam longitudinal preview offsets from the active transverse cage and both bar radii, eliminating Solid and Hollow reinforcement overlap while preserving solver isolation.
