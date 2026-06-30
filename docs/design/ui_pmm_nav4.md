# UI.PMM.NAV4 — PMM Result View Tabs First + Remove SLS View Tab

## Scope
- Move the PMM result-view tabs so they appear immediately under the Flexural (PMM) result-view heading and before the summary/decision cards.
- Remove the local `SLS` view tab from Flexural (PMM). Serviceability belongs in the main Analysis SLS subpage workflow, not inside the ULS PMM result views.

## Included
- `Summary`, `PMM Check`, `3D Interaction`, and `Diagnostics / QA` are now the PMM result-view tabs.
- The former Summary decision cards are rendered inside the `Summary` tab instead of above the tab bar.
- PMM solver, D/C calculation, result cache, load cases, and report calculations are unchanged.

## Out of scope
- Creating a full SLS Analysis subpage is future work.
- No solver or engineering formula changes.
