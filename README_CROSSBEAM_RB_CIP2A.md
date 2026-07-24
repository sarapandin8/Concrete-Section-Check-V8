# CROSSBEAM.RB-CIP2A — Align CIP Rebar UX with Precast Template Pattern

## Baseline
- Starting baseline: `concrete-section-pro_CROSSBEAM-RB-CIP2-continuous-bar-run-editor-topology-preview.zip`
- Baseline SHA-256: `8580dbeb6843c1fb2c69411cee6751eca099288b741c65b6f3f14bd93d718264`

## Purpose
Replace the user-facing Cast-in-Place `Add draft bar run` workflow with the accepted Crossbeam Rebar template interaction pattern already used by Precast Segmental, while preserving the fundamentally different construction semantics.

## Cast-in-Place behavior
- Solid-only longitudinal and transverse Rebar Template libraries.
- Same primary subview pattern as Precast:
  - Longitudinal
  - Transverse / Shear
  - Section / Zone
  - Preview
  - Continuity & Station Audit
- Section/Zone assignment maps Solid longitudinal/transverse templates to `Z1`, `Z2`, ... from the CIP layout.
- Zone boundaries are geometry/property boundaries, **not physical joints**.
- Longitudinal reinforcement may remain continuous across adjacent Zones.
- Adjacent Zone template arrangements are compared by a conservative derived continuity audit:
  - `MATCHED LAYOUT` means adjacent arrangements match and may remain continuous;
  - it does **not** certify development, splice, termination, anchorage, or exact bar identity.
- The exact Precast physical-joint rule remains unchanged: ordinary longitudinal rebar crossing a Precast segment joint = `0 mm²`.

## Project JSON / migration
- `crossbeam_cip_rebar_input_model` advances to schema version 2.
- CIP longitudinal templates, transverse templates, Zone assignments, and preview state are stored separately from Precast Segmental Rebar state.
- Legacy RB-CIP1/RB-CIP2 station-based bar-run rows are preserved non-destructively in Project JSON for backward compatibility.
- Legacy bar runs are not silently converted into the new template/Zone model and receive no solver credit.
- Dormant CIP Zone assignments are preserved when a Zone is temporarily removed from the active layout.

## Solver scope
No engineering solver equations changed.
No CIP Rebar solver handoff was added.
No changes were made to PMM, ULS, SLS, shear, torsion, prestress loss, `fcgp`, Primary/Secondary Prestress, or construction-stage analysis.

## Changed production files
- `concrete_pmm_pro/crossbeam/cip_rebar_templates.py` — new CIP Solid-template/Zone model, validation, reconciliation, and continuity audit.
- `concrete_pmm_pro/crossbeam/cip_rebar_persistence.py` — schema-v2 separate CIP template/Zone persistence with non-destructive legacy run preservation.
- `concrete_pmm_pro/ui/crossbeam_rebar_page.py` — aligned CIP Rebar UI, removal of user-facing draft-run workflow, Solid-only template editors, Section/Zone assignment, preview reuse, and continuity/station QA.

## Tests
- Added `tests/test_crossbeam_rb_cip2a_template_alignment.py`.
- Updated the first-edit callback coverage test to include the added aligned CIP data editors.
- Complete Crossbeam regression: 293 passed.
- Cross-workflow smoke selection: 163 passed.
- Known pre-existing Railway U-Girder source-assertion failure independently reproduced on both untouched RB-CIP2 baseline and RB-CIP2A worktree:
  - `test_rebar_enable1_section_builder_checkbox_synchronizes_metadata_on_change`
- Full repository suite attempted; timed out at approximately 43% with no failure reported before timeout. Full repository green is therefore **not claimed**.

## Repo summary
Align Cast-in-Place Crossbeam Rebar with the accepted Precast template-based workflow using Solid-only Section/Zone assignments, derived continuity QA, separate CIP persistence, and no solver or Precast joint-rule changes.
