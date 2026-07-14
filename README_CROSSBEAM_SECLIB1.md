# CROSSBEAM.SECLIB1 — Multi-Section Definition Library and Segment Assignment

Adds a workflow-scoped section-instance library for `Portal Frame Crossbeam — Prestressed Concrete` so several Solid or Hollow project sections can share the same preset family while using different actual dimensions and section properties.

## Core data-model rule

- **Preset family** defines geometry topology.
- **Section ID** defines the actual project section instance.
- Several Hollow Section IDs may use the same hollow preset while having different top/bottom flange and left/right web thicknesses.
- Segment Layout assigns Section IDs, not global hard-coded presets.

## What changed

- Adds a `Crossbeam Section Definition Library` to Section Builder.
- Seeds `CB-S01` and `CB-H01` while preserving the active Section Builder dimensions.
- Supports Add, Duplicate, rename, and guarded Delete operations.
- Automatically loads the active Section ID into Section Builder and writes valid geometry edits back to that definition only.
- Calculates gross area, centroid from top, Ix, Iy, Ztop, and Zbottom per Section ID.
- Blocks deletion of a Section ID while it is referenced by Segment Layout.
- Migrates accepted preset-based Segment Layout rows to Section ID assignments without changing station boundaries.
- Updates Segment Layout dropdowns, derived name/role/family columns, elevation labels, and hover traceability to use Section IDs.
- Adds backward-compatible Project JSON metadata for the Crossbeam section library, active Section ID, crossbeam length, and Segment Layout rows.

## Deliberately not changed

- No ULS, SLS, prestress-loss, shear, torsion, PMM, anchorage, D-region, or report solver uses the new library yet.
- Generic Section Builder, Rebar, Prestress, Railway U-Girder, Bridge/Building Beam-Girder, and Column/Pier behavior remains on existing paths.
- No result-cache persistence was added.

## Validation

```bash
python -m py_compile app.py \
  concrete_pmm_pro/crossbeam/section_library.py \
  concrete_pmm_pro/ui/crossbeam_section_library.py \
  concrete_pmm_pro/ui/crossbeam_pages.py \
  concrete_pmm_pro/ui/section_builder.py \
  concrete_pmm_pro/io/project_io.py

pytest -q tests/test_crossbeam_wf1_workflow.py \
  tests/test_crossbeam_wf1a_routing_safety.py \
  tests/test_crossbeam_ui1_workspaces.py \
  tests/test_crossbeam_ui1a_segment_assignment.py \
  tests/test_crossbeam_ui1b_hollow_elevation.py \
  tests/test_crossbeam_ui1c_elevation_polish.py \
  tests/test_crossbeam_rb1_segment_rebar.py \
  tests/test_crossbeam_seclib1_section_library.py
```

Crossbeam lineage and SECLIB1 tests: **37 passed**.

Section Builder, geometry, Project JSON, navigation, Rebar, Prestress, design-code, and cross-workflow regression gate: **339 passed**.

A broader Analysis/Result Summary/Report gate produced **289 passed** with two unchanged baseline static-source tests failing; both failures reproduce in the accepted RB1 baseline and are unrelated to SECLIB1.
