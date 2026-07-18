# Concrete Section Pro — CROSSBEAM.PT1D

## Milestone

`CROSSBEAM.PT1D — Tendon inventory source of truth`

## Delivered

- Removes the editable `Number of tendons` state that could display `3` while
  the Tendon identity table still contained T1–T4.
- Treats the canonical Tendon System rows as the sole source for Stored and
  Active tendon counts. The legacy count key remains only as a derived
  compatibility mirror.
- Adds read-only inventory cards for Stored tendons, Active tendons, the
  minimum requirement, and the 64-row inventory limit.
- Adds a controlled **Add tendon** action. It creates one complete active
  tendon with the first unused stable T-number and three linked top-referenced
  Tendon Profile points.
- Adds a two-step **Review removal → Confirm remove** action. It deletes one
  uniquely identified Tendon System row and every profile point linked to that
  Tendon ID.
- Locks removal at the minimum of three stored tendons and when IDs are blank
  or duplicated. Reset explicitly restores the current default tendon system.
- Keeps Tendon System revisions, Tendon Profile revisions, visible Tendon IDs,
  and Project-JSON restore state synchronized after inventory changes.

## Source and persistence rules

- One Tendon System row represents one complete tendon; `Strands` remains the
  number of strands inside that tendon.
- Project JSON persists the Tendon System rows and their profile points, not a
  second editable count. On restore, the compatibility count is derived from
  `len(tendon_system)` even when an incomplete older file requires review.
- Adding a tendon does not move or redistribute existing tendon coordinates.
  The new three-point profile is intentionally marked for engineer review in
  Tendon Profile.

## Scope guards

- No prestress-loss, SLS, ULS, shear/torsion, anchorage-zone, D-region, or FEA
  solver is added or changed.
- Segment Layout, Section Builder, Rebar, reinforcement quantities, material
  values, and other member workflows are unchanged.
- The minimum of three stored and active tendons remains a validation rule; it
  is not silently repaired when an incomplete Project JSON file is loaded.

## Validation

- PT1D plus adjacent PT1/Project-JSON tests: **18 passed**.
- All Crossbeam regression tests: **138 passed**.
- Full repository regression: **1,970 passed**; the same **6 unrelated
  baseline failures** remain in Railway U-Girder and legacy source-audit tests.
- Historical live-browser QA verified 4 → Add T5 → 5 → confirmed Remove T5 → 4,
  confirmed 12 linked profile points after removal, found no independent
  count input, and reported **0 browser errors**.

## Repo summary

Make Tendon System rows the sole Crossbeam tendon-count source; replace the
independent count input with read-only Stored/Active counts and controlled
Add/confirmed-Remove actions that synchronize linked profile points and
Project JSON without changing any solver.
