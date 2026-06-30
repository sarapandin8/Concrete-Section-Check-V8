# SECTION.PROPERTY.BENCHMARK1 — Filleted/chamfered hollow section property benchmarks

## Scope
Add executable section-property benchmark tests for the recently added Column/Pier/Wall/Pylon hollow section presets:

- `Rectangular Hollow Filleted`
- `Rectangular Hollow Filleted-Chamfered`

## Validation intent
These tests protect the geometry-summary path used by Section Builder before the shapes are relied on by PMM or serviceability workflows. They do not change the section-property engine or solver equations.

## Benchmarks added
- Zero-radius / zero-chamfer cases are checked against independent closed-form rectangular hollow section formulas for area, centroid, `Ix`, `Iy`, and `Ixy`.
- Symmetric rounded and chamfered hollow cases are checked against independent analytical area formulas.
- Symmetric cases must keep centroid at the section origin and `Ixy` near zero.
- Asymmetric wall-thickness cases must move the centroid toward the thicker concrete regions.
- Zero-feature filleted/chamfered hollow presets must match the existing `Rectangular Hollow` generator.

## Out of scope
- No solver changes.
- No geometry generator changes.
- No PMM/shear/torsion/SLS/report changes.
- This benchmark validates the polygon-discretized fillet implementation; exact closed-form arc inertias are reserved for a later validation milestone if needed.
