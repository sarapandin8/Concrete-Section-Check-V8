# CROSSBEAM.UI.ROWDELETE2 — In-table checkbox row deletion

## Scope

Replaces the unsuccessful multiselect row-deletion workflow with a direct checkbox pattern in the two Crossbeam layout tables:

- **Section Builder → Column / support-line layout**
- **Segment Layout / Section-Zone Layout**

## Implemented behavior

### Column / support-line layout

- Adds a `Delete` checkbox as the first column of the existing batched table.
- Places one `Delete checked row(s)` button immediately below that table.
- The user ticks one or more rows and presses the button; no separate row selector is required.
- Retained row edits are applied in the same form submission.
- Delete-all remains blocked because the current Portal Frame Crossbeam source requires at least one Column/support row.
- A successful deletion preserves the accepted downstream stale-state propagation for Elastic Shortening, Time-Dependent Loss, Effective Prestress handoff, and the Loads FEA contract.

### Segment / Section-Zone layout

- Adds a `Delete` checkbox as the first column of the Segment/Zone table.
- Places one `Delete checked row(s)` button directly below the table.
- Checkbox selections are preserved through the Streamlit rerun until the delete button is pressed.
- Precast Segment and Cast-in-Place Zone selections are stored separately.
- Delete-all remains blocked rather than silently recreating a default row.
- Existing layout validation continues to report gaps or overlaps after an interior row is removed.

## Regression boundary

- No engineering equations changed.
- No ULS/SLS solver logic changed.
- No prestress-loss calculation changed.
- No sign, axis, station, Section ID, or construction-type semantics changed.
- No Project JSON schema or result-cache persistence was added.

## Tests

- Compile: `python -m compileall -q app.py concrete_pmm_pro tests`
- Checkbox row-deletion and related helper tests: 24 passed.
- Related Segment Layout, Section Builder, CIP routing, Project JSON, Elastic Shortening, and Time-Dependent regression set: 72 passed.
- Full `tests/test_crossbeam_*.py` was attempted but did not complete within the 120-second execution limit; no full-suite pass is claimed.

## Repo summary

Replace Crossbeam layout row-deletion multiselects with direct in-table Delete checkboxes and one button below each table while preserving validation, construction-mode isolation, and downstream stale-state safeguards.
