# UI.ACTIVE.TABS1 — Deterministic active tab highlight

## Scope
Replace fragile Streamlit selected-state CSS dependency for app-owned navigation with a deterministic navigation renderer.

## Why
Streamlit's `segmented_control` and button group DOM changed across versions. Earlier CSS selectors styled the inactive typography but did not reliably detect the selected tab in the user's deployed app.

## Change
- Add `concrete_pmm_pro.ui.navigation.render_active_choice()`.
- Active option is rendered directly from `st.session_state` as a highlighted pill.
- Inactive options remain buttons that update the same session-state key.
- Existing navigation labels and options are preserved.
- Analysis subpage and Column/Pier ULS check navigation use the same helper.

## Out of scope
- No new tabs.
- No workflow relocation.
- No solver, geometry, load, report, rebar, prestress, or project schema changes.
