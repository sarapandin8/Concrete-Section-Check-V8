# CROSSBEAM.UI.ROWDELETE1 — Explicit row deletion for member layout tables

## Scope

Adds a visible, deliberate row-deletion workflow to the two Crossbeam layout inputs requested by the user:

- **Section Builder → Column / support-line layout**
- **Segment Layout / Section-Zone Layout**

## Implemented behavior

### Column / support-line layout

- Adds a `Column row(s) to delete` multiselect inside the existing batched form.
- Adds a `Delete selected Column row(s)` form action beside `Apply Column / Support Layout`.
- Applies edits to retained rows and deletion in the same batched action.
- Blocks deletion of every Column row because the current Portal Frame Crossbeam source requires at least one Column/support row.
- Preserves the accepted stale-propagation contract: changing the applied Column layout marks Elastic Shortening, Time-Dependent Loss, Effective Prestress handoff, and the Loads FEA contract stale.

### Segment / Section-Zone layout

- Adds a `Segment row(s) to delete` control in Precast Segmental mode.
- Adds a `Zone row(s) to delete` control in Cast-in-Place mode.
- Supports deleting one or multiple stored rows explicitly.
- Blocks deletion of every layout row instead of silently reseeding a default row.
- Keeps separate Precast and Cast-in-Place longitudinal layouts isolated and preserved.
- After deleting an interior row, the existing layout validator reports any resulting gap or overlap until adjacent station limits are corrected.

## Regression boundary

- No engineering equations changed.
- No ULS/SLS solver logic changed.
- No prestress-loss calculation changed.
- No sign, axis, station, or Section ID semantics changed.
- No Project JSON schema or result-cache persistence was added.

## Tests

- Compile: `python -m compileall -q app.py concrete_pmm_pro tests`
- Targeted row-delete tests: 22 passed.
- Related Section Builder, CIP routing, Project JSON, Elastic Shortening, and Segment Layout regression set: 66 passed.
- Full `tests/test_crossbeam_*.py` run was attempted but did not complete within the 120-second execution limit; no full-suite pass is claimed.

## Repo summary

Add explicit batched row deletion to Crossbeam Column/support and Segment/Zone layout tables while preserving validation, active construction-mode isolation, and downstream stale-state safeguards.
