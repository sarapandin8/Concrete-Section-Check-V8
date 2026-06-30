# UI.PRESTRESS.PREVIEW2 — Hide Dimension Guides on Prestress Preview

## Scope

This milestone removes Section Builder dimension guides from Prestress-page preview canvases.

The Prestress page is a steel-layout review workspace. Its default preview should show the active concrete polygon and prestressing steel only, not the full section dimension annotation set.

## Changes

- Prestress default preview now passes an empty dimension-guide list to `create_section_preview`.
- Prestress geometry-only preview also hides dimension guides while no active tendon rows are available.
- Prestress combined reinforcement coordination preview also hides dimension guides so rebar/prestress graphics remain legible.
- Captions explicitly state that ordinary rebar and dimension guides are intentionally hidden from the default Prestress preview.

## Non-goals

- No prestress parser changes.
- No tendon force or `Pe_eff` logic changes.
- No section geometry or section-property changes.
- No PMM, shear, torsion, SLS, report, or project-schema changes.
- Section Builder remains the owner of dimension guides.

## QA

Regression tests assert that the Prestress preview uses `preview_dimensions = []` and does not read `st.session_state["section_dimensions"]` for the prestress preview calls.
