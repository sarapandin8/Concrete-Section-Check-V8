# CROSSBEAM.RB2C — Direct-Edit Rebar Template Tables

## Purpose

Replace the selected-template form in the Portal Frame Prestressed Crossbeam Rebar workspace with compact direct-edit tables so users can edit default/project templates with less navigation and without horizontal scrolling.

## What changed

- Removes the `Template to edit` selector and the large `Edit Selected Template` form.
- Treats the three default templates as normal editable project rows; only `Template ID` remains read-only because Segment/Zone assignments reference it.
- Adds a compact identity/action table with editable Template name, Role, and Construction plus per-row Copy/Delete checkboxes.
- Supports duplicating checked rows and guarded deletion of checked rows.
- Allows deletion of default or project templates when they are not referenced by a Rebar Zone and at least one template remains.
- Adds direct-edit compact tables for:
  - participation/material,
  - outer-face auto layout,
  - inner-face auto layout for Hollow/Any templates,
  - adopted reinforcement quantities,
  - notes.
- Uses dropdowns for role, construction, longitudinal basis, bar size, and layout method.
- Uses one compact `Target` input: spacing in mm for `By target spacing`, or total perimeter bar count for `By exact bar count`.
- Keeps every primary editable table at six columns or fewer to avoid hidden right-side columns in the normal app width.
- Keeps adopted reinforcement and notes/reset collapsed because they are secondary/future-handoff inputs.

## Engineering and state guards retained

- Ordinary rebar crossing every segment joint remains locked to `0 mm²`.
- PT continuity remains `REQUIRED — NOT VERIFIED` until Tendon System/Profile audit is connected.
- Template IDs remain stable.
- Assigned templates cannot be deleted until their Zones are reassigned.
- Auto-generated bars remain detailing preview only and are not sent to ULS/SLS solvers.
- No Project JSON schema, result persistence, solver, Result Summary, Report/QA, or non-Crossbeam workflow was changed.

## Validation

```bash
python -m py_compile concrete_pmm_pro/ui/crossbeam_rebar_page.py concrete_pmm_pro/crossbeam/rebar.py
pytest -q tests/test_crossbeam_*.py
pytest -q tests/test_presets.py tests/test_geometry.py tests/test_project_dashboard.py tests/test_design_code_source_of_truth.py tests/test_design_code_sync3_setup_widget.py tests/test_app_commercial_tabs.py tests/test_navigation_workspace.py tests/test_project_io.py tests/test_reinforcement_system_flags.py tests/test_prestress_tendon_products.py tests/test_rebar.py tests/test_rebar_layout.py tests/test_rebar_compact_workspace.py tests/test_section_builder_layout.py tests/test_section_preview_canvas_qa.py tests/test_ui_keys1_widget_keys.py tests/test_ui_dataeditor_commit1.py tests/test_ui_active_tabs1_navigation.py tests/test_ui_qa1_visual_consistency.py tests/test_ui_theme1_commercial_engineering_theme.py tests/test_workflow_status_alignment.py tests/test_preset_routing1_workflow_presets.py
```

Results:

- Crossbeam lineage: `76 passed`
- Cross-workflow geometry/navigation/rebar/UI gate: `254 passed`

A pre-existing static Results-dashboard source-string test remains unrelated and unchanged; `app.py` and `analysis_page.py` are byte-identical to the accepted RB2B baseline.
