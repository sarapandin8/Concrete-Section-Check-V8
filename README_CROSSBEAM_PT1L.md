# Concrete Section Pro - CROSSBEAM.PT1L

## Milestone

`CROSSBEAM.PT1L - Parabolic preset parameter reactivity`

## Delivered

- Hooks the Crossbeam Tendon Profile `Preset bend offset (mm)` slider into the
  same immediate preset-apply callback used by quick-start option changes.
- Hooks the `Support width (m)` slider into the same immediate preset-apply
  callback so 2 Span parabolic support-crown stations widen as soon as the
  support width changes.
- Keeps `Re-apply` available for target-tendon changes and manual reapplication
  of the current preset.
- Adds regression coverage for both UI callback wiring and generated
  `Parabolic Tendon / 2 Span` geometry sensitivity.

## Engineering notes

- The geometry generator already responded to `bend_offset_mm` and
  `support_width_m`; the app UI did not automatically regenerate selected
  tendon rows when those slider values changed.
- With `bend_offset_mm = 400` and `support_width_m = 2.0`, the generated low
  points move from `dtop = 700 mm` to `dtop = 900 mm`, and the interior-support
  crown widens from stations `9.0-11.0 m` to `8.0-12.0 m` for `L = 20 m`.
- Existing editable tendon rows are preserved unless their Tendon IDs are
  selected when the active quick-start preset is applied.

## Scope guards

- This is UI/state and preset-generation behavior only.
- Project JSON shape, member-length ownership, tendon inventory, review figures,
  segment layout, rebar workflows, solvers, reports, and non-Crossbeam workflows
  remain unchanged.

## Validation

- Targeted tendon source/editor tests passed: `20 passed`.
- Crossbeam regression suite passed: `155 passed`.
- Full repository run ended with the same six known non-PT1L failures from the
  PT1K baseline area: `1987 passed, 6 failed`.

## Repo summary

Make Crossbeam parabolic tendon preset offset and support-width sliders immediately regenerate selected tendon profile rows while preserving solver isolation.
