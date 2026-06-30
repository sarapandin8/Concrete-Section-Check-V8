# UI.COMMERCIAL.TABS4 — Active tab highlight hotfix

## Scope
Visual-only hotfix for existing app navigation controls.

## Change
- Add explicit active-state styling for Streamlit segmented controls using `stBaseButton-segmentedControlActive`.
- Strengthen selected radio fallback styling through `label:has(input:checked)`.
- Keep active tab text dark-blue and bold even when the Streamlit theme attempts to color the selected item red.
- Add a stronger active-tab fill and bottom indicator so the user can immediately see the current workspace/subpage.

## Out of scope
- No new tabs.
- No navigation relocation.
- No workflow behavior changes.
- No solver, geometry, loads, analysis, report, rebar, or prestress changes.
