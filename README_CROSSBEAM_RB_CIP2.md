# CROSSBEAM.RB-CIP2 — Continuous Longitudinal Bar-Run Editor + Engineering Topology Preview

## Scope

This milestone releases the first user-editable **Cast-in-Place Portal Frame Crossbeam longitudinal reinforcement topology workflow** on top of the solver-neutral RB-CIP1 foundation.

### Added

- A CIP-only station-based longitudinal bar-run editor with immediate callback-driven commit.
- User-editable fields for:
  - `Run ID`, `s_start`, `s_end`, bar group, layer/face,
  - bar size and material,
  - exact-count or target-spacing definition basis,
  - explicit start/end termination intent,
  - notes and active/inactive state.
- Derived/read-only diameter and `fy` fields so these values are not duplicated as independent canonical state.
- App-standard bar/grade review rule:
  - DB10–DB28 → SD40 / `fy = 390 MPa`,
  - DB32 → SD50 / `fy = 490 MPa`.
  Existing mismatches are preserved and reported as `REVIEW REQUIRED`; they are not silently rewritten.
- Preservation of unsupported/custom loaded labels and their stored diameter/fy values for explicit review instead of replacement.
- Longitudinal continuity elevation showing bar-run station extents across Section/Zone bands.
- Zone-crossing continuity audit showing exactly which zones each run occupies and how many zone boundaries it crosses.
- Station review workspace showing which bar runs participate at any selected Crossbeam station.
- Construction-type-aware visible navigation label:
  - Precast Segmental → `Segment Layout`,
  - Cast-in-Place → `Section / Zone Layout`.
  Both labels route to the same existing layout workspace and canonical layout state.

## Locked engineering semantics

- Cast-in-Place Crossbeam = one monolithic continuously cast **Solid-only** member.
- CIP Section/Zone boundaries are geometry/property/analysis/rebar zones, **not physical joints**.
- Longitudinal bar runs may cross any number of zone boundaries without automatic termination or splice.
- New CIP runs are never invented automatically. A user-requested draft is seeded over `0–L` only as an editing convenience and remains `REVIEW REQUIRED` until required engineering fields are defined.
- Precast Segmental reinforcement state remains separate and preserves the physical-joint rule: ordinary longitudinal rebar crossing a segment joint = `As = 0 mm²`.

## Explicitly not included

- No exact longitudinal bar coordinates within the section.
- No development length, splice, curtailment, termination, anchorage, congestion, or code-minimum certification (`RB-CIP3` remains pending).
- No CIP bar-run solver participation in PMM, ULS, SLS, shear, torsion, prestress loss, Result Summary, or Report/QA.
- No changes to Friction/Wobble, Anchorage Set, Elastic Shortening, `fcgp`, Primary/Secondary Prestress, or construction-stage solver equations.

## Validation

- RB-CIP2 targeted + RB-CIP1 regression: passed.
- Complete Crossbeam regression: passed.
- Cross-workflow smoke: two failures reproduced unchanged on the untouched RB-CIP1 baseline and treated as pre-existing.
- Full repository suite was attempted but timed out before completion; no full-suite-green claim is made.

## Repo summary

`Release the Cast-in-Place Crossbeam continuous longitudinal bar-run editor with zone-aware continuity and station previews, dynamic Section/Zone Layout labeling, preserved custom inputs for REVIEW, and no solver handoff or Precast Segmental behavior changes.`
