# Concrete Section Pro - CROSSBEAM.PT1J

## Milestone

`CROSSBEAM.PT1J - Support-width tendon profile sampling`

## Delivered

- Adds a `Support width (m)` quick-start control on the Crossbeam Tendon Profile
  page. It is display/seed geometry input only and does not become a new solver
  or member-length editor.
- Updates `Straight Tendon With Bends / 2 Span` so the interior support high
  zone uses three control points across the selected support width instead of a
  single sharp point.
- Updates `Parabolic Tendon / Single Span` to use seven sampled control points
  with a true midpoint low point.
- Updates `Parabolic Tendon / 2 Span` to use seven sampled points per span plus
  dense interior-support sampling across `2 x support width`.
- Keeps all generated rows as ordinary editable `s-x-dtop` profile points, so
  Plan, Elevation, Cross Section, 3D Orthographic, station audit, and Project
  JSON continue to use the existing source-of-truth.

## Profile design notes

- Positive bend offset increases `dtop`, so low points move downward from the
  top surface.
- The 2 Span bent support zone places high points at
  `L/2 - support_width/2`, `L/2`, and `L/2 + support_width/2`.
- The 2 Span parabolic support zone samples around the middle support from
  `L/2 - support_width` through `L/2 + support_width`.
- The support-width slider is capped to a practical portion of member length so
  generated support zones do not overrun adjacent midspan low zones.

## Scope guards

- The quick-start profile remains a geometry seed only. It does not calculate
  friction, wobble, anchor set, prestress loss, SLS stress, ULS strength,
  anchorage zones, deviators, D-regions, or reports.
- The persistent schema remains the existing editable tendon profile row table.
- Existing edited tendon rows are preserved unless their Tendon IDs are selected
  when a quick-start option is applied.

## Validation

- Targeted tendon source/editor tests passed: `16 passed`.
- Crossbeam regression suite passed: `151 passed`.
- Full repository run ended with the same six known non-PT1J failures from the
  PT1I baseline area: `1983 passed, 6 failed`.

## Repo summary

Add support-width-aware Crossbeam tendon quick-start sampling so bent 2-span profiles use a column-width high zone and parabolic presets use denser control points while preserving solver isolation.
