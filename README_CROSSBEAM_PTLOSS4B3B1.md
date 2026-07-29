# CROSSBEAM.PTLOSS4B3B1 — Multi-Event Schedule Editor KeyError Hotfix

## Scope

- Fix the deployed Time-Dependent permanent-load event schedule crash caused by reusing a load-table normalizer that assumed every data editor contained an `Active` column.
- Preserve the schedule's intended `Adopt` checkbox semantics and default inactive rows.
- Preserve all existing ULS/SLS load-editor `Active` behavior.

## Engineering impact

- No prestress-loss equations changed.
- No event ages, FEA response mapping, `P/V2/M3` sign conventions, solver routing, or Project JSON schema changed.
- Runtime remains 0 solves on open/import and 1 internal solve for falsework removal on a Segmental Run.

## Regression protection

- Added tests for initial schedule rendering, first-edit patch reconstruction, and unchanged legacy `Active` load-editor defaults.
