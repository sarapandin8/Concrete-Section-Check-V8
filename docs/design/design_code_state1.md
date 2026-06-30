# DESIGN.CODE.STATE1 — Durable Project Design Code State

## Issue

When `Design Code` was selected on the Setup page using the Streamlit widget key
`design_code`, the Analysis page could still show `ACI 318` after navigating away
from Setup, even though Setup visibly showed `AASHTO LRFD`.

The root cause is that widget-owned keys can be removed when the owning widget is
not rendered on the active workspace.  Therefore `design_code` and
`code_edition` must not be the only project design-code source of truth.

## Fix

The Setup selector now mirrors the selected code into durable non-widget keys:

- `project_design_code`
- `project_code_edition`

Read-side helpers in `core/design_code.py` prefer these durable keys.  Legacy
keys remain synchronized while Setup is rendered or when a project file is
loaded, but Analysis, Report/QA, Prestress, save/load, and app chrome read the
durable keys first.

## Engineering rule

For Column / Pier / Wall / Pylon:

- Setup selected `AASHTO LRFD` must remain `AASHTO LRFD` in Analysis after
  workspace navigation.
- A stale legacy/widget key such as `design_code = ACI 318` must not override
  `project_design_code = AASHTO LRFD`.
- PMM may route to the AASHTO LRFD 9th implementation; shear/torsion/V+T remain
  guarded until their AASHTO solvers are implemented and validated.

## Unit discipline

This state fix does not alter equations.  AASHTO equations remain handled by the
unit-safe Section 5 basis layer added in `AASHTO.COL.PMM.BASIS1`.
