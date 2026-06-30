# UI.ANALYSIS.NAV2 — Promote ULS Strength Summary to First-Class Check Tab

## Scope
- Promote `Summary` to the first tab under `ULS Strength Check`.
- Move project code basis, Column/Pier decision view, and Column/Pier ULS decision summary into this Summary tab.
- Keep `Flexural (PMM)`, `Shear`, `Torsion`, and `Shear + Torsion` as individual check tabs.

## Rationale
The moved information is ULS-strength workflow context rather than a Flexural PMM result view. Keeping it above every check made the page long and visually repetitive. The Summary tab now acts as the commercial first-screen overview for code basis, scoped capability, and overall ULS decision status.

## Out of scope
- No PMM solver changes.
- No D/C equation changes.
- No shear/torsion/V+T logic changes.
- No project schema, report, geometry, rebar, prestress, or load changes.
