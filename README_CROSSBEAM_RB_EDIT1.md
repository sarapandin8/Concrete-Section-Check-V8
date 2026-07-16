# Concrete Section Pro — CROSSBEAM.RB-EDIT1

## Milestone

`CROSSBEAM.RB-EDIT1 — Single-commit editable Rebar tables`

## Root cause and correction

Crossbeam Rebar tables previously relied on the dataframe returned after a
Streamlit rerun. The first cell change existed only as an `edited_rows` widget
patch at callback time, so canonical table state could be rewritten with the
pre-edit value and the engineer had to enter the value again.

RB-EDIT1 adds a shared patch-reconstruction helper and an `on_change` commit
callback to every editable Crossbeam Rebar data table. Each first edit is merged
into canonical longitudinal, transverse, or Segment/Zone state before the page
reruns.

## Audited editable tables

- Longitudinal templates: identity/actions, participation/material, outer-face
  layout, inner-face layout, adopted reinforcement, and notes.
- Transverse templates: identity/actions, participation/material, Hollow
  topology, Solid ties, placement offsets, and notes.
- Segment/Zone: Zone geometry and reinforcement assignment.

RB-EDIT1 originally covered 14 editable tables with the same single-commit
pattern. UI.SYNC1 later split the transverse placement editor by coordinate
direction; the current UI therefore has 15 editable tables using that pattern.
Read-only `st.dataframe` summaries are unchanged.

## State and engineering guards

- Linked material/fy pairs still refresh as one canonical pair.
- Longitudinal or transverse Template ID changes still update Zone references
  atomically.
- Zone ID changes retain reinforcement assignments and purpose text.
- Project-JSON persistence remains the RB-PERSIST1 model.
- No PMM, Beam/Girder, SLS, shear, torsion, Result Summary, Report/QA, tendon,
  segment-joint, or analysis-cache ownership is changed.

## Validation

- Exact reported case covered: the first edit of Hollow transverse center
  offset from 50 to 75 mm is retained.
- AST coverage guard confirms all 14 editable Crossbeam tables declare both
  `on_change` and callback arguments.
- Complete Crossbeam suite: 111 passed.
- Project IO/Rebar/navigation/Section Builder/Results/Report gate: 168 passed.
- Full repository suite: 1,940 passed; the same 6 unrelated baseline failures
  remain.
- Streamlit AppTest rendered all three Rebar subpages without exceptions and
  found 6 longitudinal, 6 transverse, and 2 Segment/Zone editable tables.
- Streamlit health endpoint returned HTTP 200 with `ok`.

## Repo summary

Commit the first edit across all 14 Crossbeam Rebar data tables using Streamlit
patch callbacks while preserving Template/Zone references, persistence, and
solver isolation.
