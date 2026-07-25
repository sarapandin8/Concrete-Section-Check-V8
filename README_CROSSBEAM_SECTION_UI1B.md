# CROSSBEAM.SECTION-UI1B — Rename Action State and Active-Context Synchronization

## Starting baseline

- `concrete-section-pro_CROSSBEAM-SECTION-UI1A-rename-row-polish.zip`
- SHA-256: `5646317cdeaed74c385e2fc9dad9135edafa0c2f0b091d61f7bd48d895fca12c`

## Scope

This milestone is a targeted Crossbeam Section Builder UI/state correction. It does not change section geometry, Project JSON schema, Rebar, Prestress, PMM, ULS/SLS, or any engineering solver.

## Changes

1. **State-aware Rename section action**
   - Replaced the form submit control with an explicit Streamlit action button so the global commercial action styling applies consistently.
   - The button is disabled and neutral when the name is blank, unchanged, or duplicated elsewhere in the project.
   - The button becomes the normal blue primary action only when a valid unique replacement name is ready.
   - Blank and duplicate-name issues are reported next to the rename row.
   - Stable Section ID and Segment/Section-Zone references remain unchanged.

2. **Crossbeam active-context synchronization**
   - The sidebar and top `SECTION TYPE / PRESET` chrome now resolve from the active Crossbeam Project Section definition.
   - Stale generic labels such as `Rectangle` are no longer accepted while the Portal Frame Crossbeam workflow is active.
   - Safe fallbacks are limited to valid Crossbeam Solid/Hollow presets or an explicit `Crossbeam section not selected` state.

## Regression safety

- Precast Segmental Solid/Hollow section behavior is preserved.
- Cast-in-Place remains Solid-only.
- Rename remains project-facing only; stable Section ID and assignments are preserved.
- No solver handoff or engineering equation changed.

## Validation performed

- Targeted Section Library/CIP/UI tests: `51 passed`
- Complete Crossbeam regression: `322 passed`
- Selected navigation/project/chrome regression: `134 passed`
- Full repository suite attempted for 120 seconds and reached approximately 46% with no failure reported before timeout; full-suite green is not claimed.
- `py_compile`: passed
- `compileall`: passed
