# REBAR.RAIL.UGIRDER2 — Auto Perimeter Apply Commit Hotfix

## Purpose

This milestone fixes the second ordinary-rebar workflow issue observed in Railway U-Girder: the auto perimeter generator previewed bars correctly, but pressing **Apply generated perimeter layout to Rebar table** could appear to do nothing because the generated rows were not reliably committed through the Streamlit data-editor widget state on rerun.

## Scope

Implemented a dedicated apply-state helper that:

1. Normalizes the generated perimeter table to the standard Longitudinal Rebar editor contract.
2. Writes it to `st.session_state["rebar_table"]`.
3. Increments `rebar_editor_revision` so the editor remounts with the new table.
4. Clears stale `rebar_data_editor_*` widget states that may otherwise replay an older empty editor payload.
5. Returns the input mode to `Manual table` so the applied bars are immediately visible/editable.
6. Shows a one-rerun success message confirming how many generated rows were applied.

## Engineering boundary

This is a UI/state routing hotfix only. It does not change ordinary rebar capacity calculations, SLS/ULS solver equations, prestress/debonding logic, Railway U-Girder geometry, or report certification wording.

## Regression protection

Added tests for:

- generated rows are committed to `rebar_table`,
- editor revision is bumped,
- stale `rebar_data_editor_*` states are removed,
- the committed table matches the Rebar editor column contract.
