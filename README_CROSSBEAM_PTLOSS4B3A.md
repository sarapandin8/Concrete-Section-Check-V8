# CROSSBEAM.PTLOSS4B3A — In-Page Construction-Stage FEA Response Import

## Status

Corrective forward-fix milestone that supersedes the deployed `CROSSBEAM.PTLOSS4B3` workspace ownership without rewriting Git history.

## Why this milestone exists

`PTLOSS4B3` correctly introduced an imported incremental FEA `P/V2/M3` source for the permanent-load event at `tp`, but placed that source in the main **Loads** workspace. That ownership was misleading because the main Loads workspace is intended for ULS/SLS design demands, while the imported response is used only by **Prestress Loss → Time-Dependent** construction-schedule QA.

## Changes

- Relocates the `tp` construction-stage FEA response import to:
  - `Sections → Prestress Loss → Time-Dependent`
- Restores the main Crossbeam **Loads** workspace to ULS/SLS demand imports only.
- Adds dedicated Crossbeam ULS and SLS table namespaces:
  - `crossbeam_uls_loads_table`
  - `crossbeam_sls_loads_table`
- Reuses the established app import pattern:
  - Download Excel/CSV template
  - Upload
  - Preview and validate
  - Replace or append
  - Editable canonical table
- Adds a mandatory `tp` FEA source declaration:
  - FEA program
  - Exact case/construction-stage name
  - Permanent load groups included
  - Unfactored permanent-load confirmation
  - Incremental-not-total-Final-Stage confirmation
  - Exclusion of live/wind/seismic/temperature/prestress/time-dependent effects
  - Common representative activation age `tp` confirmation
- Shows explicit **INCLUDE / EXCLUDE** guidance next to the import.
- Preserves row-coupled `P/V2/M3`; independent component maxima are not assembled.
- Verifies that the declared case/stage matches the active imported `Case Name`.
- Preserves the one-solve runtime:
  - 0 solves on open/import/edit
  - 1 internal solve for falsework removal on Segmental Run
  - Imported `tp` response adds no internal solve

## Project JSON migration

New ownership is stored under:

`crossbeam_time_dependent_fea_response`

with rows and source declaration together.

Projects saved by deployed `PTLOSS4B3` are migrated forward from the legacy `workflow_load_tables[crossbeam_ptloss4b3_later_fea_response_table]` location. Existing rows are preserved, but the new mandatory source declaration is not invented and must be completed by the engineer.

## Engineering scope guard

PTLOSS4B3A supports one representative incremental permanent-load event at `tp`. Permanent load groups that activate at materially different ages must not be combined under one `tp`; a future multi-event schedule is required.

`Pe(s)` / `Pe_eff(s)` assembly remains locked. No Friction/Wobble, Anchorage Set, Elastic Shortening, creep, shrinkage, or relaxation equations were changed.

## Repo summary

Relocate Crossbeam construction-stage FEA response import into Time-Dependent prestress loss, restore the main Loads workspace to ULS/SLS demands, add mandatory source declarations and safe PTLOSS4B3 Project JSON migration.
