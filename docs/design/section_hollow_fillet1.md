# SECTION.HOLLOW.FILLET1 — Hollow preview solid inner outlines + rectangular hollow filleted preset

## Scope
1. Render hollow-section inner boundaries as solid lines in Live Section Preview.
2. Add a new `Rectangular Hollow Filleted` preset for Column/Pier/Wall/Pylon workflows.

## Included
- Hollow preview hole/void outline styling changed from dashed to solid.
- New geometry generator `rectangular_hollow_filleted` with separate outer and inner fillet radii.
- New dimension helper `rectangular_hollow_filleted_dimensions`.
- Preset wiring in `data/section_presets.json`.
- Regression tests for geometry, dimensions, and preview line style.

## Behavior
- Outer rectangle with uniform outer radius `Ro`.
- Inner void with uniform inner radius `Ri`.
- Independent wall thicknesses `t_top`, `t_bottom`, `t_left`, `t_right`.
- Dimension guides: `B`, `H`, wall thicknesses, `Ro`, `Ri`.

## Out of scope
- No solver changes.
- No PMM/shear/torsion/SLS/report changes.
- No independent per-corner radii in this milestone.
