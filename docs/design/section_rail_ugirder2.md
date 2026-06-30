# SECTION.RAIL.UGIRDER2 — Railway U-Girder h1-h4 and Haunch XY Controls

## Scope

Refine the Bridge Beam/Girder `Railway U-Girder` preset so the drawing-critical U-girder dimensions are editable without exposing secondary drafting details.

This milestone updates only the geometry preset inputs, dimension guides, documentation, and regression tests. It does not change solver, rebar, prestress, SLS, shear/torsion, report, or project-schema behavior.

## User-facing parameter changes

The previous single `Inner haunch size` input is split into two independent parameters:

- `Haunch X (mm)` — horizontal haunch projection.
- `Haunch Y (mm)` — vertical haunch projection.

The previous derived `y_step` dimension guide is replaced by editable h-dimensions matching the user's annotated drawing:

- `h1 Step height (mm)` — height from section bottom to the exterior notch/step.
- `h2 Bottom opening (mm)` — depth from section bottom to the underside of the floor slab/opening.
- `h3 Side floor thk (mm)` — floor slab thickness at the haunch toe/side.
- `h4 Center floor thk (mm)` — floor slab thickness at bridge centerline.

Default values remain the accepted drawing defaults:

- `h1 = 670 mm`
- `h2 = 305 mm`
- `h3 = 395 mm`
- `h4 = 450 mm`
- `Haunch X = 300 mm`
- `Haunch Y = 300 mm`

## Geometry relationships

Coordinates are interpreted from the top of side wall downward:

- Exterior notch level from top = `H - h1`.
- Floor underside from top = `H - h2`.
- Floor top at side/haunch toe = `H - h2 - h3`.
- Floor top at centerline = `H - h2 - h4`.
- Vertical side wall to haunch start = `H - h2 - h3 - Haunch Y`.
- Haunch toe x-coordinate = `inner_half_width - Haunch X`.

The exterior notch remains derived from:

```text
Bottom side width - Top wall width
```

The six 25 mm chamfers remain fixed drawing details and are intentionally not exposed as inputs.

## Backward compatibility

The generator still accepts the older `SECTION.RAIL.UGIRDER1` parameter aliases (`inner_vertical_depth_mm`, `haunch_size_mm`, `floor_side_thickness_mm`, and `floor_center_thickness_mm`) so saved projects from the immediately previous baseline can still generate the accepted default geometry.

## QA

Regression checks cover:

- new parameter names and compact labels,
- default geometry unchanged from the accepted drawing,
- h1-h4 and Haunch X/Y driving the polygon vertices,
- dimension guide symbols `h1`, `h2`, `h3`, `h4`, `hx`, and `hy`,
- invalid notch relationship guard.
