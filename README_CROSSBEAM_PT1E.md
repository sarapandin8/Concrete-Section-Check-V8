# Concrete Section Pro — CROSSBEAM.PT1E

## Milestone

`CROSSBEAM.PT1E — 3D visual hierarchy and neutral concrete palette`

## Delivered

- Replaces Plotly's automatic per-trace Mesh3d colors with two explicit,
  role-based neutral colors: darker blue-gray for Solid segments and lighter
  blue-gray for Hollow segments.
- Reduces concrete opacity and specular lighting so overlapping segment faces
  no longer form a saturated rainbow or compete visually with the tendons.
- Assigns each Tendon ID a stable, high-contrast color from the complete
  profile source. Hiding a tendon or switching transparency never recolors the
  remaining tendon paths.
- Strengthens tendon line/point marks and adds explicit dark section-boundary
  loops plus dashed Hollow-void loops at unique segment stations.
- Clarifies the 3D title, legend, neutral scene background, grid, toggle help,
  and figure caption while preserving the existing orthographic projection.
- Keeps two display-only modes: muted concrete for reviewing the overall
  member mass and transparent concrete for tracing internal tendon paths.

## Display contract

- Muted mode opacity: Solid `0.34`, Hollow `0.22`.
- Transparent mode opacity: Solid `0.14`, Hollow `0.09`.
- Default tendon palette begins T1 blue, T2 orange, T3 green, and T4 purple;
  later tendons use the remaining stable palette entries.
- Section and void boundary traces are display overlays only and never enter
  engineering calculations or persisted model data.

## Scope guards

- No Section Builder geometry, Segment Layout station, Tendon System row,
  Tendon Profile coordinate, or Project-JSON schema is changed.
- No prestress-loss, SLS, ULS, shear/torsion, anchorage-zone, D-region, FEA,
  report, or other member-workflow solver is added or changed.
- The transparency control remains display-only and does not mutate source
  data, analysis state, or the adopted orthographic camera contract.

## Validation

- PT1E and adjacent PT1A/PT1B/PT1D tests: **17 passed**.
- All Crossbeam regression tests: **142 passed**.
- Full repository regression: **1,974 passed**; the same **6 unrelated
  baseline failures** remain in Railway U-Girder and legacy source-audit tests.
- Live-browser QA verified both opacity contracts, the two concrete colors,
  four distinct stable tendon colors, section/void boundaries, visible title
  and legend labels, orthographic projection, and **0 browser errors**.

## Repo summary

Replace Plotly's per-trace rainbow Mesh3d colors with a role-based neutral
concrete palette, stable high-contrast tendon colors, and clear section/void
boundaries in both display modes, without changing geometry, tendon inputs,
persistence, or solvers.
