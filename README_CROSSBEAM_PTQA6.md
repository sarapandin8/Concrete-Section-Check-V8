### CROSSBEAM.PTQA6 - Tendon Profile Import UX Audit Trace

PTQA6 builds on `CROSSBEAM.PTQA5A` and keeps the Tendon Profile import flow
solver-neutral while making import review easier to audit before and after
apply.

#### What changed

- Adds an explicit `Download active profile CSV` action so users can export the
  currently active `s-x-dtop` rows in the exact import column order.
- Adds Excel sheet inspection for `.xlsx/.xls` uploads and a worksheet picker
  when an uploaded workbook has multiple sheets.
- Adds a row-level diff preview for Tendon Profile imports, showing Added,
  Changed, and Removed rows before the guarded apply button is enabled.
- Records a compact `Last applied import audit` after apply with file name,
  sheet name, rows applied, row-change counts, affected tendon count, timestamp,
  and status.
- Keeps Undo available after apply and marks the audit as `Undone` when the
  previous profile rows are restored.
- Adds friendlier import validation hints for missing columns, station limits,
  lateral coordinates, dtop values, Tendon ID matching, and Curve role values.

#### Scope guard

- Applies only to Crossbeam Tendon Profile import preview/apply UX.
- Does not change Tendon System schema, Segment Layout, Section Builder,
  Project JSON export shape, reports, rebar workflows, or any solver.

#### Validation

- `python -m compileall concrete_pmm_pro/crossbeam/tendon.py concrete_pmm_pro/ui/crossbeam_pages.py tests/test_crossbeam_ptqa4_tendon_profile_import_foundation.py`
- `python -m py_compile concrete_pmm_pro/crossbeam/tendon.py concrete_pmm_pro/ui/crossbeam_pages.py tests/test_crossbeam_ptqa4_tendon_profile_import_foundation.py`
- `pytest` may require the project test dependency to be installed in the
  runtime environment.
