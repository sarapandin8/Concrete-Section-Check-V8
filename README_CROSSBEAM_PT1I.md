# Concrete Section Pro - CROSSBEAM.PT1I

## Milestone

`CROSSBEAM.PT1I - Curated 2-span tendon profile gallery`

## Delivered

- Reduces the Crossbeam Tendon Profile quick-start catalog to three clear,
  unnumbered engineering patterns: `Straight Tendon`,
  `Straight Tendon With Bends`, and `Parabolic Tendon`.
- Replaces the ambiguous Multiple Span label with `2 Span` for the current
  workflow scope.
- Corrects 2 Span geometry so it repeats the matching simple-span pattern over
  two spans, with high points at supports and low points between supports.
- Keeps legacy numbered preset names and old Multiple Span state compatible by
  normalizing them into the curated options.
- Updates the gallery schematics and selection callback so the UI, generated
  table rows, and success messages all use the new names.

## Profile design notes

- Positive bend offset increases `dtop`, so low points move downward from the
  top surface.
- `Straight Tendon` remains constant depth in both Single Span and 2 Span.
- `Straight Tendon With Bends` uses high points at end/middle supports and low
  plateau points between supports.
- `Parabolic Tendon` samples a sagging simple-span profile; 2 Span repeats that
  sampled shape on each side of the middle support.

## Scope guards

- The quick-start gallery remains a geometry seed only. It does not calculate
  friction, wobble, anchor set, prestress loss, SLS stress, ULS strength,
  anchorage zones, deviators, D-regions, or reports.
- The persistent schema remains the existing editable tendon profile row table.
- Existing edited tendon rows are preserved unless their Tendon IDs are selected
  when a quick-start option is applied.
- Future 3-span support should extend the same repeat-between-supports rule
  without changing the current Project JSON schema.

## Validation

- Targeted tendon source/editor tests passed: `15 passed`.
- Crossbeam regression suite passed: `150 passed`.
- Full repository run ended with the same six known non-PT1I failures from the
  PT1H baseline area: `1982 passed, 6 failed`.

## Repo summary

Curate Crossbeam tendon quick-start profiles to three unnumbered options with explicit 2 Span patterns that repeat the simple-span shape between supports while preserving solver isolation.
