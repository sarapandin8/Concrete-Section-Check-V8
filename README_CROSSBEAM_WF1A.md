# CROSSBEAM.WF1A — Workflow routing and regression-safety correction

This milestone corrects the Portal Frame Prestressed Crossbeam foundation before the new Segment Layout and Tendon Profile workspaces are added.

## Scope

- Keeps the existing global Sections navigation unchanged: `Section Builder | Rebar | Prestress`.
- Adds a workflow-scoped `Portal Frame Crossbeam` section-family label so Crossbeam status cards no longer fall through to `Column/Pier/Wall/Pylon section`.
- Uses the Crossbeam coordinate vocabulary `s/u/v` in Crossbeam status and audit wording while retaining `x/y/z` for existing workflows.
- Displays Crossbeam section-analysis scope accurately:
  - `ULS PMM — Not active`
  - `Crossbeam station model — Layout foundation`
- Prevents steel-system overrides from another preset from leaking into a newly selected Crossbeam preset.
  - Crossbeam defaults remain Rebar ON / Prestress ON.
  - An explicit override made on the same Crossbeam preset is preserved.
  - Legacy projects use the saved reinforcement preset key as the backward-compatible override scope.
- Relabels existing Crossbeam table station columns as `s_start`, `s_end`, `s/L`, and `s (m)` without changing the stored WF1 legacy field names.
- Relabels tendon geometry output as `dtop`, centroid depth from top, and `e(s)`.

## Deliberately not changed

- No new tabs or workspace navigation yet.
- No Segment Elevation, Tendon Plan/Profile/3D figures yet; these remain `CROSSBEAM.UI1`.
- No prestress-loss, SLS, ULS, shear/torsion, anchorage, or D-region solver changes.
- No changes to existing Railway U-Girder, Bridge Beam/Girder, Building Beam/Girder, or Column/Pier solver routing.
- No Project JSON schema changes and no result-cache persistence.

## Validation

```bash
python -m py_compile app.py concrete_pmm_pro/ui/section_builder.py concrete_pmm_pro/core/reinforcement_system.py
pytest -q tests/test_crossbeam_wf1a_routing_safety.py tests/test_crossbeam_wf1_workflow.py tests/test_reinforcement_system_flags.py tests/test_workflow_status_alignment.py tests/test_preset_routing1_workflow_presets.py tests/test_workflow_type3_shared_section_presets.py
pytest -q tests/test_navigation_workspace.py tests/test_ui_active_tabs1_navigation.py tests/test_app_commercial_tabs.py tests/test_project_io.py tests/test_project_dashboard.py tests/test_section_builder_layout.py tests/test_rebar_railway_u_girder3_section_builder_sync.py tests/test_prestress_tendon_products.py tests/test_qa_railway_u_girder_workflow_regression_audit.py tests/test_building_beam_girder_sls_load_workflow.py tests/test_girder_service_workflow.py tests/test_design_code_source_of_truth.py tests/test_design_code_sync3_setup_widget.py tests/test_crossbeam_wf1a_routing_safety.py tests/test_crossbeam_wf1_workflow.py tests/test_reinforcement_system_flags.py tests/test_workflow_status_alignment.py tests/test_preset_routing1_workflow_presets.py tests/test_workflow_type3_shared_section_presets.py
```

Targeted plus cross-workflow regression gate: **195 passed**.

The repository-wide suite contains pre-existing baseline documentation/legacy metadata-driven tests that already conflict with the accepted WF1 lineage; they are not caused by WF1A. No new failures were found in the scoped regression gate above.
