# CROSSBEAM.RB-CIP2B — Canonical Section/Zone Reinforcement Assignment

## Baseline
- Starting baseline: `concrete-section-pro_CROSSBEAM-RB-CIP2A-template-zone-aligned-rebar-workflow.zip`
- Baseline SHA-256: `7d2debbd4213f5b7722d5ca4d07b1365a2b6bbf786629a3bc113a5773fca8ab8`

## Purpose
Remove the redundant Cast-in-Place `Credit in zone` control and lock the `Section / Zone Reinforcement Assignment` table as the single canonical adopted-reinforcement source for each active CIP Zone.

## Locked CIP semantics
- Selecting a `Longitudinal template` in `Section / Zone` means that template is the adopted longitudinal reinforcement source for that Zone.
- Selecting a `Transverse template` in `Section / Zone` means that template is the adopted transverse/shear reinforcement source for that Zone.
- No second per-template design-credit checkbox is required in Cast-in-Place.
- The legacy serialized `Credit inside segment` field is preserved non-destructively for backward compatibility only and is ignored by CIP adoption/continuity semantics.
- Only templates assigned to active Zones contribute to CIP input-completeness warnings; dormant/unassigned library templates do not create false review noise.
- Zone boundaries remain geometry/property boundaries, not physical joints.
- Solver handoff remains LOCKED; this milestone defines the future solver source mapping but does not activate PMM/ULS/SLS/shear/torsion credit.

## Regression protection
- Precast Segmental `Credit in zone` behavior and physical-joint rules are unchanged.
- No Precast canonical state or Project JSON schema was changed.
- No engineering solver equation changed.

## Changed production files
- `concrete_pmm_pro/crossbeam/cip_rebar_templates.py`
- `concrete_pmm_pro/ui/crossbeam_rebar_page.py`

## Tests
- Added `tests/test_crossbeam_rb_cip2b_assignment_source.py`.
- Tests verify that CIP Section/Zone assignment remains adopted even when legacy credit metadata is false, continuity ignores legacy credit metadata, completeness follows assigned templates only, and the CIP editor no longer exposes a `Credit in zone` checkbox.
- Targeted RB-CIP2A/RB-CIP2B tests: **10 passed**.
- Complete Crossbeam regression: **297 passed**.
- Cross-workflow smoke/regression selection: **199 passed, 1 pre-existing failure**.
  - `test_results_source_blocked_is_treated_as_danger_status` was independently reproduced on the untouched RB-CIP2A baseline.
- Known pre-existing Railway U-Girder source-assertion failure was also independently reproduced on both the untouched RB-CIP2A baseline and RB-CIP2B worktree:
  - `test_rebar_enable1_section_builder_checkbox_synchronizes_metadata_on_change`.
- Full repository suite attempted; timed out at approximately **47%** with no failure reported before timeout. Full repository green is therefore **not claimed**.
- `py_compile` and `compileall` passed for modified production/test paths and the application package.

## Repo summary
Make Cast-in-Place Section/Zone template assignment the single adopted reinforcement source, remove the redundant CIP credit checkbox, and preserve Precast Segmental behavior and solver locks.
