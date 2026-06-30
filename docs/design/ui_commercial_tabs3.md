# UI.COMMERCIAL.TABS3 — Actual segmented-tab selector coverage

## Scope
- Fix the visual polish from `UI.COMMERCIAL.TABS2` so it applies to the Streamlit segmented navigation actually rendered by the app.
- Keep all existing tab positions, labels, and behavior unchanged.

## Root cause
`UI.COMMERCIAL.TABS2` styled `stSegmentedControl` and radio fallback selectors, but the current Streamlit runtime renders `st.segmented_control()` using a `stButtonGroup` DOM path. The visible Workspace / Setup workspace tabs therefore kept the default theme styling.

## Change
- Add `div[data-testid="stButtonGroup"]` selector coverage for segmented controls/pills.
- Force nested button text, paragraphs, and spans to dark-blue bold typography.
- Keep radio fallback styling and input-label styling intact.

## Out of scope
- No layout changes.
- No new tabs or navigation controls.
- No solver, geometry, section-property, analysis, load, report, rebar, prestress, or project-schema changes.
