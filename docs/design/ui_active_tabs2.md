# UI.ACTIVE.TABS2 — Compact Commercial Active Tab Bar

## Scope
Refine the app-owned deterministic navigation introduced in `UI.ACTIVE.TABS1` so existing navigation reads as a compact commercial tab bar instead of full-width action buttons.

## Included
- Keep all existing navigation choices and locations unchanged.
- Add compact left-aligned tab clustering using a trailing spacer column.
- Reduce tab height/padding and soften active-state shadow.
- Keep active tabs visible with light-blue fill, dark-blue border, and bottom accent line.
- Style Streamlit `st.tabs` detail tabs, such as Rebar longitudinal/transverse tabs, in the same dark-blue active-tab language.

## Out of scope
- No new tabs.
- No navigation relocation.
- No solver, geometry, loads, analysis, report, rebar, or prestress logic changes.
