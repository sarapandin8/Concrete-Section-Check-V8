# SECTION.RAIL.UGIRDER3 — Railway U-Girder Dimension Label and Naming Polish

## Scope

Polish the `Railway U-Girder` preset annotations and input wording after visual review in the Section Builder.

This milestone changes only preset labels, dimension-guide text placement, documentation, and regression tests. It does not change the concrete polygon, section properties, solver, rebar, prestress, SLS, shear/torsion, report, or project-schema behavior.

## User-facing changes

- Rename `h1 Step height (mm)` to `h1 Step from bottom (mm)` so the reference direction is explicit.
- Rename `h2 Bottom opening (mm)` to `h2 Bottom recess (mm)` to avoid implying a horizontal opening width or closed void.
- Move the `hx` dimension annotation to the left-side haunch and keep `hy` on the right-side haunch. The section is symmetric, so the geometry meaning is unchanged while the labels no longer overlap.

## Engineering guardrails

- No Railway U-Girder vertex coordinates changed.
- The derived 50 mm exterior notch and six fixed 25 mm chamfers remain unchanged.
- h1, h2, h3, h4, Haunch X, and Haunch Y still drive the same accepted polygon relationships from `SECTION.RAIL.UGIRDER2`.

## QA

Regression checks confirm:

- Railway U-Girder preset parameter names are unchanged.
- Updated h1/h2 input labels are present.
- Default polygon vertices, area, centroid, and derived drawing levels are unchanged.
- `hx` and `hy` dimension labels render on opposite sides of the trough with full `300 mm` labels.
