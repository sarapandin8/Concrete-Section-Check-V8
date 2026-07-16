# Concrete Section Pro — CROSSBEAM.PT1

## Milestone

`CROSSBEAM.PT1 — Tendon System and Tendon Profile source of truth`

## Canonical tendon input model

- Crossbeam projects start with four complete tendons and require at least
  three active tendons. Each stable Tendon ID owns Active, Internal/External,
  strand count, seven-wire low-relaxation strand, Aps/strand, fpu, fpj/fpu,
  calculated fpj, Left/Right/Both jacking, and both end anchorages.
- Defaults are fpu = 1,860 MPa, Aps = 140 mm²/strand, and fpj = 0.75 fpu =
  1,395 MPa. Both-end jacking remains one tendon force source; it does not
  double Pj.
- Tendon geometry has one editable `s–x–dtop` point table. Plan, Profile, 3D,
  validation, audit, and Project JSON all consume this same source. `dtop` is
  measured downward from the top surface; `s/L` is derived rather than entered
  twice.

## UI and engineering audit

- Tendon System is split into compact linked identity/stressing and
  prestressing-steel tables plus a read-only anchorage table. Tendon ID renames
  update profile references and visible-tendon selections atomically.
- Every editable Tendon System/Profile table commits Streamlit's first
  `edited_rows` patch before rerender, so one edit stores the value once.
- Plan section widths, Profile bottom/centroid traces, and 3D concrete extents
  are derived from the Section ID assigned to each Segment.
- The calculated audit uses the station's assigned Section ID centroid. A point
  on an internal Segment joint expands to both adjacent faces so neither
  centroid is silently discarded.
- Internal tendons are checked against the applicable Section ID envelope;
  External tendons may leave that simplified envelope for future deviator and
  external-duct detailing.

## Project JSON

- A versioned `crossbeam_tendon_input_model` stores only tendon-system rows,
  profile points, and stable review selections.
- Older Crossbeam projects without the block receive a four-tendon system and
  three-point top-referenced profiles. Recognized legacy flat/nested data is
  migrated, while unresolved Tendon IDs remain visible as `REVIEW REQUIRED`.
- Editor revisions, generated figures, solver results, and analysis caches are
  excluded from the persisted input block.

## Scope guards

- PT continuity across every Segment joint is `REQUIRED — NOT VERIFIED` until
  PTQA1. Ordinary rebar crossing each joint remains locked at 0 mm².
- No friction, wobble, anchor-set, elastic-shortening, creep, shrinkage,
  relaxation, SLS, ULS, anchorage-zone, deviator-force, D-region, FEA, Result
  Summary, Report/QA, or solver coupling is added.
- Existing Crossbeam reinforcement and all other member workflows are
  unchanged.

## Validation

- Changed Python files compile successfully.
- Complete Crossbeam suite: 120 passed.
- Full repository suite: 1,952 passed; the same 6 unrelated baseline failures
  remain.
- Streamlit AppTest rendered Tendon System with three tables and Tendon Profile
  with four tables plus Plan/Profile/3D figures without exceptions.
- Streamlit health endpoint returned `ok`.

## Repo summary

Promote the Crossbeam tendon system and top-referenced Plan/Profile/3D geometry
to a versioned Project-JSON source of truth with compact first-edit tables and
station-specific Section ID centroid audit, without solver coupling.
