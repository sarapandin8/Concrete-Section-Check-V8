# SECTION.RAIL.UGIRDER1 — Railway Through U-Girder Non-composite Preset

## Scope

Add a Bridge Beam/Girder preset for a railway through U-girder section where trains run inside the U-shaped trough.  The preset is classified as `General / Non-composite Girder` and does not enable composite-deck metadata.

## Drawing interpretation

Default dimensions follow the user-provided symmetric railway U-girder drawing:

- Overall width B = 5500 mm.
- Overall depth H = 1600 mm.
- Half width = 2750 mm.
- Top side-wall width = 600 mm.
- Lower side block width = 650 mm.
- Clear inner half width = 2100 mm, derived as B/2 - lower side block width.
- Top-to-haunch vertical depth = 600 mm.
- Inner haunch = 300 mm horizontal x 300 mm vertical.
- Floor top at side/haunch toe = 900 mm from top.
- Floor thickness at side = 395 mm.
- Floor thickness at centerline = 450 mm.
- Floor underside = 1295 mm from top.
- Center floor top = 845 mm from top.
- Exterior step/notch level = 930 mm from top = 670 mm from bottom.
- Exterior notch projection = 50 mm, derived from lower side block width - top side-wall width.
- Six chamfers are modeled as fixed 25 mm drawing details:
  - top outer left/right,
  - top inner left/right,
  - bottom outer left/right.

## Implementation notes

The geometry is generated as a single concave outer polygon with no closed hole.  This matches a through U-girder/trough section rather than a box section.  The polygon is built in drawing coordinates and then converted to the app coordinate system where y=0 is the section mid-depth and positive y is upward.

The notch and chamfer details are intentionally not exposed as user inputs.  They are drawing details derived from the main editable dimensions so the Section Builder remains compact.

## Changed files

- `data/section_presets.json`
- `concrete_pmm_pro/geometry/generators.py`
- `tests/test_railway_u_girder_preset.py`
- `docs/design/section_rail_ugirder1.md`
- `README.md`

## QA

Targeted regression checks cover:

- preset availability for Bridge Beam/Girder,
- category and generator mapping,
- exact default polygon vertices including notches, chamfers, haunches, and floor crown,
- positive valid geometry,
- symmetry about bridge centerline,
- section bounds B=5500 mm and H=1600 mm,
- derived drawing details: notch 50 mm, chamfer 25 mm, step 930 mm from top / 670 mm from bottom, floor side/center/underside levels,
- dimension guide values.

No solver, rebar, prestress, SLS, shear/torsion, report, or project schema behavior is changed.
