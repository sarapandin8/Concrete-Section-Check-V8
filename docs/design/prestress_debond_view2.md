# PRESTRESS.DEBOND.VIEW2 — Debonding Schematic Label Cleanup

## Scope

This milestone refines the Prestress → Debonding along span view after the
first elevation schematic milestone.

## Changes

- Removes `Debond pattern (mm)` from the primary editable strand-layout table.
- Keeps legacy `Debond pattern mm` metadata in the backend/project schema for
  old project compatibility only.
- Uses these fields as the debonding source of truth for the primary workflow:
  - `Left debond (m)`
  - `Right debond (m)`
  - `Debonded strand nos`
- Replaces ambiguous schedule wording with a derived `Debond summary` such as:
  - `2 strand(s) @ 1.000 m each end`
  - `2 strand(s): left 1.000 m / right 2.000 m`
- Removes repeated per-row debond-length text from the elevation schematic.
- Places unique debond length labels on dimension lines below the girder with
  explicit side wording, e.g. `1000 mm from left end` and
  `1000 mm from right end`.
- Increases bottom plot margin/spacing for dimension labels to avoid left-end
  text overlap.

## Non-goals

- No change to solver equations.
- No change to effective prestress/station-based Pe logic.
- No change to prestress losses, PMM, SLS stress, geometry, section properties,
  report generation, or project schema calculation logic.

## Engineering note

`Debond pattern (mm)` was removed from the primary table because it duplicated
and could contradict the source-of-truth fields.  Drawing-symbol metadata is
still load/save compatible for older projects, but the current user-facing
workflow derives row debond summaries from left/right sleeve lengths and the
selected debonded strand numbers.
