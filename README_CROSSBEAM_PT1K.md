# Concrete Section Pro - CROSSBEAM.PT1K

## Milestone

`CROSSBEAM.PT1K - Interior-support parabolic crown`

## Delivered

- Refines `Parabolic Tendon / 2 Span` around the interior column so the support
  zone is generated as an inverted parabolic crown instead of inheriting the
  sharp junction of the two adjacent span parabolas.
- Keeps the support crown centered at `L/2` and spread over
  `L/2 - support_width` through `L/2 + support_width`.
- Preserves the existing seven-point midspan sampling and editable
  `s-x-dtop` table source-of-truth.
- Leaves `Straight Tendon`, `Straight Tendon With Bends`, Project JSON shape,
  member-length ownership, review routing, and all solvers unchanged.

## Profile design notes

- Positive bend offset increases `dtop`, so low points move downward from the
  top surface.
- Around the middle support, the crown edge keeps the adjacent span depth while
  intermediate points follow a quadratic crown toward the high point at `L/2`.
- The crown removes the visual cusp in Elevation while still using ordinary
  piecewise-linear control rows.

## Scope guards

- This remains a geometry seed only. It does not calculate friction, wobble,
  anchor set, prestress loss, SLS stress, ULS strength, anchorage zones,
  deviators, D-regions, or reports.
- Existing edited tendon rows are preserved unless their Tendon IDs are selected
  when a quick-start option is applied.

## Validation

- Targeted tendon source/editor tests passed: `17 passed`.
- Crossbeam regression suite passed: `152 passed`.
- Full repository run ended with the same six known non-PT1K failures from the
  PT1J baseline area: `1984 passed, 6 failed`.

## Repo summary

Refine Crossbeam Parabolic Tendon 2 Span generation with an inverted parabolic crown over the interior support to remove the middle-column cusp while preserving solver isolation.
