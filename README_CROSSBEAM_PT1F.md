# Concrete Section Pro — CROSSBEAM.PT1F

## Milestone

`CROSSBEAM.PT1F — Web-centered tendon default placement`

## Delivered

- Changes the Portal Frame Crossbeam default tendon inventory from four to
  eight stored tendons so the Cross Section view starts with four tendon
  centers in each web.
- Places T1-T4 on the left web centerline and T5-T8 on the right web
  centerline. For the default B = 2500 mm and 300 mm webs, x = -1100 mm and
  x = +1100 mm.
- Keeps each default tendon profile straight in the vertical direction by
  giving P1, P2, and P3 the same x and dtop values.
- Sets the four default vertical levels from top to bottom as 500 mm from the
  top, two equally spaced intermediate levels, and 300 mm above the bottom.
  For H = 1500 mm this gives dtop = 500.000, 733.333, 966.667, and 1200.000 mm.
- Uses actual left/right web thickness inputs from the Crossbeam Section
  Builder where available; older projects without a tendon block receive the
  same web-centered defaults during Project-JSON migration.

## Scope guards

- Existing engineer-edited tendon rows are not automatically redistributed.
  The new placement rule applies to default seeding, explicit tendon-geometry
  reset, older-project seeding, and newly added tendon default points.
- The three-point `s-x-dtop` source-of-truth, Project-JSON schema version,
  minimum three-tendon validation guard, Add/Remove inventory workflow, 3D
  visual palette, and solver isolation remain intact.
- No friction, wobble, anchor-set, prestress-loss, SLS, ULS, anchorage-zone,
  deviator, D-region, report, or other member workflow calculation is changed.

## Validation

- Targeted PT/profile/project tests passed: `32 passed`.
- Crossbeam regression suite passed: `143 passed`.
- The new regression verifies eight default tendon IDs, four web-centered
  tendon centers per side, fixed x at each profile point, and constant dtop
  through the default P1-P2-P3 source.
- Deterministic Cross Section QA exported the same Plotly figure builder used
  by the app and confirmed all eight tendon centers are `IN CONCRETE` for the
  default hollow section.

## Repo summary

Seed Crossbeam tendon defaults as eight web-centered tendons, four per side,
with constant x and dtop profiles from 500 mm below the top to 300 mm above the
bottom, while preserving the existing tendon source-of-truth and solver
isolation.
