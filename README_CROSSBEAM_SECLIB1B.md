# CROSSBEAM.SECLIB1B — Visible Section Summary and Low-Effort Management

Makes the Crossbeam project-section library easier to understand and maintain by surfacing a complete section inventory plus direct rename and guarded delete controls in the primary Section Builder workflow.

## What changed

- Adds a visible `Project Section Summary` table for every Solid/Hollow project section.
- Reports Section ID, user-facing name, family, B × H, wall/fillet/chamfer summary, gross area, centroid from top, Ix, Iy, assigned segments, and geometry status.
- Adds direct `Section name` editing with a prominent `Save name` action while keeping the stable Section ID unchanged.
- Adds visible guarded deletion:
  - sections assigned in Segment Layout cannot be deleted;
  - at least one project section must remain;
  - eligible deletion requires explicit confirmation.
- Keeps deliberate Section-ID changes in a collapsed advanced control and updates all Segment Layout references when used.
- Preserves the SECLIB1A pending-selection mechanism so rename/delete actions do not mutate a rendered Streamlit selectbox key.

## Low-effort workflow

1. Select a project section.
2. Review all created sections in the visible summary table.
3. Rename the selected section directly.
4. Duplicate or create a new Solid/Hollow section when needed.
5. Edit geometry in the standard Section Builder controls.
6. Assign the Section ID in Segment Layout.
7. Delete only unused definitions after confirmation.

## Deliberately not changed

- No ULS, SLS, prestress-loss, shear, torsion, PMM, anchorage, D-region, Rebar solver, Result Summary, or Report/QA calculation changes.
- No change to Railway U-Girder, Bridge/Building Beam-Girder, Column/Pier, or generic Section Builder behavior.
- Project JSON remains on the backward-compatible SECLIB1 schema.
- No result-cache persistence was added.

## Validation

```bash
python -m py_compile \
  concrete_pmm_pro/ui/crossbeam_section_library.py \
  tests/test_crossbeam_seclib1b_section_management.py

pytest -q tests/test_crossbeam*.py
# 44 passed

pytest -q \
  tests/test_section_builder_layout.py \
  tests/test_project_io.py \
  tests/test_navigation_workspace.py \
  tests/test_ui_active_tabs1_navigation.py \
  tests/test_app_commercial_tabs.py \
  tests/test_preset_routing1_workflow_presets.py \
  tests/test_presets.py \
  tests/test_geometry.py \
  tests/test_reinforcement_system_flags.py \
  tests/test_rebar_railway_u_girder3_section_builder_sync.py \
  tests/test_prestress_tendon_products.py \
  tests/test_design_code_source_of_truth.py \
  tests/test_design_code_sync3_setup_widget.py \
  tests/test_workflow_status_alignment.py \
  tests/test_workflow_type3_shared_section_presets.py \
  tests/test_project_dashboard.py
# 192 passed

pytest -q \
  tests/test_analysis_modes.py \
  tests/test_analysis_preflight.py \
  tests/test_analysis_runtime.py \
  tests/test_result_summary2_sls_code_integration.py \
  tests/test_report_qa2_unified_readiness.py \
  tests/test_girder_service_workflow.py \
  tests/test_building_beam_girder_sls_load_workflow.py \
  tests/test_railway_u_girder_sls_stage_preview.py \
  tests/test_railway_u_girder_sls_stage_limits.py \
  tests/test_girder_sls_full_length_diagram.py \
  tests/test_qa_railway_u_girder_workflow_regression_audit.py
# 182 passed
```
