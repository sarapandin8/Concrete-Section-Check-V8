# UI.PRESTRESS.PREVIEW1 — Prestress preview visible by default

## Scope
- Adjust the Prestress page visual policy so the section preview is displayed directly when Prestress is enabled from Section Builder.
- Keep the Prestress page default preview separated from ordinary rebar.
- Keep the combined rebar + prestress coordination preview available in a collapsed expander.

## Change
- Passive/reference prestress rows are now drawn immediately in `Section Preview with Prestress` instead of being hidden behind a collapsed expander.
- When no active prestress rows exist, a geometry-only section preview is shown so the Prestress page still has a visible canvas after enabling Prestress.
- The Prestress preview is shown before status/notes in the right column so users can check the layout sooner.
- Preview chart height is slightly reduced for a more compact working layout.

## Out of scope
- No prestress calculation changes.
- No PMM/SLS/shear/torsion/report changes.
- No table schema or project save/load changes.
