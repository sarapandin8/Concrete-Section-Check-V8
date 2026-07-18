# Concrete Section Pro - CROSSBEAM.PT1G

## Milestone

`CROSSBEAM.PT1G - Editable tendon profile points and presets`

## Delivered

- Adds a Quick profile preset dropdown to the Crossbeam Tendon Profile page.
  Presets create editable `s-x-dtop` rows for straight constant-depth,
  straight bent, parabolic low/high point, and multi-span draped geometry.
- Adds a preset bend-offset control and target-tendon selector so engineers can
  apply a preset to selected tendons without replacing unrelated tendon rows.
- Keeps preset application schema-neutral: generated rows remain ordinary
  Tendon Profile source-of-truth rows, so Project JSON, plan/elevation,
  cross-section, 3D orthographic review, and station audit reuse the existing
  interpolation path.
- Makes profile-row editing explicit by adding a `Delete row` checkbox column
  while retaining Streamlit dynamic rows for adding extra control points.
- Preserves PT1F web-centered default coordinates when applying a preset to a
  subset of tendons by using the full tendon inventory as the coordinate
  reference.
- Updates the Tendon System reset label from the stale 4-tendon wording to the
  current 8-tendon default.

## Scope guards

- Presets are geometry quick-starts only and do not calculate friction, wobble,
  anchor set, prestress loss, SLS stress, ULS strength, anchorage zones,
  deviators, D-regions, or reports.
- The persistent profile schema remains the existing `Tendon ID`, `Point`,
  `s/L`, `s (m)`, `x lateral (mm)`, `dtop (mm)`, and `Curve role` rows.
- Segment Layout and Tendon Profile remain read-only consumers of Crossbeam
  member length `L`; no length editor was reintroduced outside Section Builder.
- Existing engineer-edited profile rows are preserved unless the engineer
  explicitly applies a preset to those tendon IDs or deletes selected rows.

## Validation

- Targeted PT/profile editor tests passed: `11 passed`.
- Crossbeam regression suite passed: `146 passed`.
- Full repository run ended with the same six known non-Crossbeam failures from
  the PT1F baseline area: `1978 passed, 6 failed`.

## Repo summary

Add Crossbeam tendon-profile presets and explicit dynamic profile-row add/delete
handling while preserving the existing s-x-dtop source-of-truth and solver
isolation.
