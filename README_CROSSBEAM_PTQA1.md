# Concrete Section Pro - CROSSBEAM.PTQA1

## Milestone

`CROSSBEAM.PTQA1 - Tendon geometry continuity audit`

## Delivered

- Adds a solver-neutral segment-joint PT continuity audit for Crossbeam Tendon
  Profile.
- Checks every active tendon at every internal segment joint station.
- Verifies each active tendon has an interpolated profile position, positive
  `Aps total`, positive `fpj`, and acceptable section fit on each adjacent
  joint face.
- Uses the same Section-ID polygon fit behavior as the Cross Section view, so
  internal tendons in voids or outside concrete are flagged for review.
- Replaces the Tendon Profile `PT continuity = NOT VERIFIED` card with
  `GEOMETRY VERIFIED`, `REVIEW REQUIRED`, or `NO JOINTS` based on the live audit.
- Adds a `Segment joint PT continuity` table to the `Calculated Audit` tab.
- Changes the Tendon System page card to `CHECK IN PROFILE` because the
  continuity result depends on profile rows and segment/section assignment.

## Scope guards

- This is an input geometry and source-readiness audit only.
- It does not calculate friction, wobble, anchorage set, elastic shortening,
  creep, shrinkage, relaxation, SLS stress, ULS strength, anchorage zones,
  deviator forces, solid/hollow transition D-regions, or reports.
- Project JSON shape, member-length ownership, tendon inventory, preset
  generation, rebar workflows, segment layout, and solvers remain unchanged.

## Validation

- Focused tendon/profile/view tests passed: `24 passed`.
- Crossbeam regression suite passed: `157 passed`.
- Full repository run ended with the same six known non-PTQA1 failures from the
  PT1L baseline area: `1989 passed, 6 failed`.

## Repo summary

Add Crossbeam PTQA1 segment-joint tendon geometry continuity audit with live PT continuity status and Calculated Audit rows while preserving solver isolation.
