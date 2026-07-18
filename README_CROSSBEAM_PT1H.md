# Concrete Section Pro - CROSSBEAM.PT1H

## Milestone

`CROSSBEAM.PT1H - Quick-start tendon profile gallery`

## Delivered

- Reworks the Crossbeam Tendon Profile quick-start UI into a reference-style
  gallery with named options, compact Single Span and Multiple Span schematics,
  and a highlighted active selection.
- Expands the preset catalog to match the requested family names:
  `Straight Tendon 1`, `Straight Tendon 2`,
  `Straight Tendon With Bends 1-4`, and `Parabolic Tendon 1-3`.
- Adds a Span type selector so the same quick-start option can generate
  different control-point patterns for Single Span versus Multiple Span
  layouts.
- Applies profile selection changes directly to the selected tendons' editable
  `s-x-dtop` rows; the Re-apply action remains available after changing target
  tendons or bend offset.
- Keeps all generated profiles as ordinary Tendon Profile table rows, so Plan,
  Elevation, Cross Section, 3D Orthographic, station audit, and Project JSON
  continue to use the existing source-of-truth.

## Profile design notes

- Positive bend offset increases `dtop`, so low points move downward from the
  top surface.
- Straight Tendon presets use constant or linearly varied depth rows.
- Straight Tendon With Bends presets use kinked low/high point control rows.
- Parabolic Tendon presets use sampled control rows that preview as smooth
  draped or hogging tendon shapes while remaining piecewise-linear input data.

## Scope guards

- The quick-start gallery is a geometry seed only. It does not calculate
  friction, wobble, anchor set, prestress loss, SLS stress, ULS strength,
  anchorage zones, deviators, D-regions, or reports.
- The persistent schema remains the existing tendon profile row table; no new
  Project JSON shape type is required.
- Existing edited tendon rows are preserved unless their Tendon IDs are selected
  when the quick-start option is applied.

## Validation

- Targeted tendon source/editor tests passed: `13 passed`.
- Crossbeam regression suite passed: `148 passed`.
- Full repository run ended with the same six known non-Crossbeam failures from
  the PT1G baseline area: `1980 passed, 6 failed`.

## Repo summary

Add a reference-style Crossbeam tendon quick-start gallery with Single/Multiple
Span profile schematics that rewrite selected editable s-x-dtop rows while
preserving solver isolation.
