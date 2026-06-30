# UI.ACTIVE.TABS3 — Navigation Density Polish

## Scope
- Polish only the visual density of existing app navigation.
- Keep all existing tab choices and locations unchanged.
- Do not change solver, geometry, load, rebar, prestress, project schema, report, or analysis logic.

## Changes
- Tighten deterministic active-tab columns so app navigation reads as a compact tab strip rather than full-width action buttons.
- Reduce global working-screen top padding and vertical gaps.
- Reduce active-tab height, padding, radius, and shadow weight.
- Slightly reduce global action-button height to align with the compact commercial style.
- Keep active tabs highlighted with a dark-blue border/accent and pale-blue fill.

## QA
- Source tests assert the deterministic navigation renderer remains active.
- Source tests assert the compact tab density constants and CSS selectors are present.
