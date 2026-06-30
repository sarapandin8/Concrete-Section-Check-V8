# DESIGN.CODE.STATE3 — Setup Widget Change Sync

## Problem

After `AASHTO.COL.PMM1.CODE_SYNC2`, the durable project design-code keys were correctly used by Analysis, but the Setup page still copied the durable value back into the Streamlit widget-owned keys at the top of every rerun. When the user selected **AASHTO LRFD** from the Setup dropdown, Streamlit delivered the changed value through `st.session_state["design_code"]` before the page body rendered again. The default initializer then overwrote that fresh widget value with the old durable value, so the dropdown snapped back to **ACI 318**.

## Fix

`_ensure_project_default_state(...)` now initializes missing design-code widget keys only. It no longer overwrites existing widget-owned keys at page start.

A Setup-only sync marker pair was added:

- `_project_design_code_widget_sync`
- `_project_code_edition_widget_sync`

Before the Setup selectboxes are created, `_sync_setup_design_code_widget_state_before_render(...)` checks whether the widget key changed from the last durable value that was copied into it. If yes, the change is treated as a real user selection and promoted to durable project keys before the selectbox is instantiated.

## Source of truth

- Setup edit event: widget key may temporarily lead during the next rerun.
- Durable application state: `project_design_code` and `project_code_edition` remain the source of truth after the Setup selector syncs.
- Analysis, Report, Prestress, save/load, and app chrome must continue to read durable/workflow-compatible helpers, not raw widget keys.

## Regression coverage

`tests/test_design_code_sync3_setup_widget.py` covers:

1. ACI → AASHTO dropdown change is promoted before selectbox render.
2. Durable AASHTO still overrides stale legacy ACI after navigation.
3. AASHTO → ACI dropdown change remains possible for Column/Pier/Wall/Pylon workflow.
