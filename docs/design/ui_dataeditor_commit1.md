# UI.DATAEDITOR.COMMIT1 — One-Pass Commit for Rebar and Load Input Tables

## Purpose

Several editable tables used `st.data_editor` as the visible input surface while storing the authoritative engineering data in `st.session_state` and project metadata.  In some edit paths, especially first edits after changing tabs or using dynamic rows, the widget's internal patch payload was not committed into the source-of-truth table until a second edit/rerun.  This made users enter transverse reinforcement or ULS/SLS station loads twice before the values were retained.

## Scope

This milestone applies a one-pass commit pattern to:

- Sections → Rebar → Beam/Girder Shear Reinforcement Layout
- Sections → Rebar → Column/Pier control-section transverse reinforcement
- Loads → Column/Pier ULS table
- Loads → Column/Pier SLS table
- Loads → Bridge Beam/Girder ULS table
- Loads → Building Beam/Girder ULS table
- Loads → Beam/Girder SLS stage tabs: Transfer, Construction, Service

## Implementation

The UI now reconstructs a full dataframe from either:

- the normal dataframe returned by `st.data_editor`, or
- the keyed widget patch payload containing `edited_rows`, `added_rows`, and `deleted_rows`.

The patch is applied to the existing source-of-truth table during the widget `on_change` callback before the next rerun.  For transverse rebar, the editor revision is bumped and the stale widget payload is cleared so dependent cells such as diameter/fy from bar-size selection are shown from the normalized table immediately.

## Engineering boundary

This is a UI persistence hotfix only.  It does not change:

- SLS solver equations
- ULS flexure/shear/torsion equations
- shear Av/s minimum or spacing equations
- load-combination logic
- section geometry or section properties
- prestress/debonding logic
- project schema

## Regression coverage

Added `tests/test_ui_dataeditor_commit1.py` covering:

- reconstruction of first-edit load-table payloads,
- merging first-edit SLS stage payloads back into the backend SLS table,
- reconstruction of first-edit transverse-rebar payloads,
- source-level guard that requested tables use one-pass `on_change` commit callbacks.
