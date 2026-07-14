# CROSSBEAM.SECLIB1A — Streamlit State Hotfix and Low-Effort Section Workflow

Hotfixes the Crossbeam Section Definition Library widget-state error and simplifies the primary workflow so users can create several Solid/Hollow section instances with minimal effort.

## Root cause fixed

`CROSSBEAM.SECLIB1` changed the `crossbeam_seclib1_active_section_id` selectbox-owned session-state key after the selectbox had already been instantiated. Streamlit rejects that mutation and raised `StreamlitAPIException` when Add, Duplicate, Rename, or Delete attempted to activate another Section ID.

`SECLIB1A` now stages the next active Section ID in a non-widget pending key, reruns, and applies the selection before any Section Builder widgets are rendered.

## Simplified primary workflow

The visible Section Library workflow is reduced to:

1. Select **Section to edit**.
2. Click **Duplicate current** for another section with similar geometry.
3. Edit the dimensions in the standard Geometry Parameters panel below.
4. Assign the new Section ID in **Segment Layout**.

One-click **New Hollow** and **New Solid** buttons remain available for fresh default geometry.

The previous `New section family` selector plus generic `Add` button were removed.

## Reduced visual and interaction load

- Keeps only the active section selector and three common actions in the main view.
- Moves rename, guarded delete, metrics, and the complete property table into one collapsed advanced expander.
- Shows the current Section ID, role, and assigned segments immediately below the selector.
- Displays a concise fast-workflow instruction.
- Makes the generic Crossbeam preset-family control read-only because topology belongs to the selected project Section ID; users create a New Solid/New Hollow definition rather than changing topology in place.

## Regression scope

- Crossbeam-only session-state keys and rendering paths.
- No ULS/SLS, prestress loss, shear/torsion, PMM, Rebar solver, Report/QA, or result persistence changes.
- Existing Railway U-Girder, Bridge/Building Beam-Girder, and Column/Pier workflows retain their original Section Type / Preset selector behavior.
- Project JSON schema remains the backward-compatible `SECLIB1` schema.

## Validation

```bash
python -m py_compile app.py \
  concrete_pmm_pro/crossbeam/section_library.py \
  concrete_pmm_pro/ui/crossbeam_section_library.py \
  concrete_pmm_pro/ui/crossbeam_pages.py \
  concrete_pmm_pro/ui/section_builder.py \
  concrete_pmm_pro/io/project_io.py
```

Crossbeam lineage/state tests: **40 passed**.

Section Builder, geometry, Project JSON, navigation, Rebar, Prestress, design-code, and cross-workflow regression gate: **227 passed**.

Analysis, Result Summary, Report/QA, Railway U-Girder SLS, and staged-stress regression gate: **331 passed**.

A live Streamlit server smoke run was not available in the packaging container because the Streamlit runtime executable/module is not installed there; the state-transition regression test directly verifies that action handling no longer mutates the rendered selectbox key.
