# SECTION.HOLLOW.FILLET.CHAMFER1 — Outer filleted / inner chamfered hollow rectangle preset

## Scope
Add a new `Rectangular Hollow Filleted-Chamfered` preset under `Basic Solid` for Column/Pier/Wall/Pylon workflows.

## Geometry behavior
- Outer boundary: rounded rectangle with uniform outer fillet radius `Ro`.
- Inner void boundary: rectangular void with four straight chamfered corners, controlled by `Ci`.
- Wall thicknesses remain independent: `t_top`, `t_bottom`, `t_left`, `t_right`.

## Included
- New geometry generator `rectangular_hollow_outer_filleted_inner_chamfered`.
- New dimension helper `rectangular_hollow_outer_filleted_inner_chamfered_dimensions`.
- New preset wiring in `data/section_presets.json`.
- Regression tests for valid geometry, inner chamfer limit, and dimension symbols.

## Out of scope
- No solver changes.
- No section-property formula changes.
- No PMM/shear/torsion/SLS/report changes.
- No independent per-corner radius or per-corner chamfer in this milestone.
