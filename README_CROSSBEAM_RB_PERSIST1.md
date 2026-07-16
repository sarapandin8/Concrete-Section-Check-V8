# Concrete Section Pro — CROSSBEAM.RB-PERSIST1

## Milestone

`CROSSBEAM.RB-PERSIST1 — Crossbeam reinforcement Project-JSON persistence`

## Persisted input model

Project JSON now stores one versioned, Crossbeam-scoped reinforcement block:

- Complete longitudinal template library, including editable Template IDs,
  material/fy, adopted quantities, face participation, bar sizes, offsets,
  spacing/exact-count controls, Active/Credit flags, and notes.
- Complete transverse template library, including editable Template IDs,
  material/fy, bar size, spacing, web/effective legs, cage status, center/end
  offsets, Active/Credit flags, and notes.
- Segment/Zone assignments with both longitudinal and transverse Template ID
  references, station limits, and purpose text.
- Stable review selections: subview, Segment, Zone, active longitudinal
  template, preview mode, and marker mode.

Editor revision counters, action/confirmation widgets, generated preview
geometry, and analysis-result caches are not part of this input block.

## Migration and validation

- Crossbeam projects saved before RB-PERSIST1 receive the same default template
  libraries and Segment-derived Zone assignments that the existing UI formerly
  created on first visit.
- Legacy flat/nested session-key metadata and pre-TR1 Zones are migrated into
  the versioned schema; missing transverse references are assigned by Segment
  role without changing longitudinal references.
- Current-schema files retain unresolved IDs unchanged and receive a visible
  `REVIEW REQUIRED` load status instead of silent reference replacement.
- Every loaded Zone is checked against Segment IDs plus active longitudinal and
  transverse Template IDs. Editor revisions and the Segment signature are then
  refreshed for Streamlit-safe rendering.
- Re-saving a migrated project writes only the current versioned block and
  removes recognized legacy Crossbeam reinforcement metadata keys.

## Scope exclusions

This milestone does not connect Crossbeam reinforcement to PMM, Beam/Girder,
SLS, shear, torsion, Result Summary, Report/QA, tendon continuity, segment-joint
shear transfer, or any analysis-result cache.

## Validation

- Changed Python files compile successfully.
- Complete Crossbeam suite: 104 passed.
- Project JSON/navigation/Section Builder/Result Summary/Report QA gate:
  126 passed.
- Full repository suite: 1,933 passed; the same 6 unrelated baseline failures
  remain.
- Streamlit startup health smoke test returned `ok`.
- Round-trip tests cover renamed Template IDs and references, material/fy,
  bar sizes, offsets, spacing/count, Active/Credit flags, Zone assignments,
  preview settings, older-project migration, and unresolved-reference review.

## Repo summary

Persist the complete Crossbeam longitudinal/transverse template and Segment/Zone
input model in versioned Project JSON with legacy migration, reference
validation, and no solver/cache coupling.
