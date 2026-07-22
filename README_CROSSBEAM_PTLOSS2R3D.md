# CROSSBEAM.PTLOSS2R3D — Anchorage Set QA-State & Wording Closeout

This milestone closes the Crossbeam Anchorage Set optional-QA presentation without changing any prestress-loss solver equation or numerical result.

## Scope

- Renames the main Anchorage Set heading to **engineering preview + optional independent QA** so optional verification is not confused with the loss calculation itself.
- Moves the heavy independent dense-grid checker into its own collapsed **Optional Independent Numerical QA — does not affect calculated prestress-loss results** expander.
- Defines mutually exclusive QA states: **NOT RUN — READY TO VALIDATE**, **PASS / REVIEW**, **STALE — REFRESH REQUIRED**, and **NOT APPLICABLE**.
- Removes the contradictory state where a valid simultaneous-both-end coupled preview could be shown while the UI also claimed independent QA was not applicable.
- Renames the action to **Run / Refresh Optional Independent QA** and states explicitly that running or skipping it does not change Friction & Wobble, Anchorage Set loss, station force P(s), or Equivalent Average Loss.
- Adds a clear boundary note that independent-QA PASS confirms agreement between two numerical implementations within tolerance and does not by itself constitute code certification.
- Replaces internal milestone-heavy wording in the main Prestress Loss workspace banner with commercial user-facing wording; method revision identifiers remain available in audit-level content.

## Solver protection

No changes to Friction/Wobble, Single-end Anchorage Set, simultaneous Both-end Anchorage Set, equivalent-average calculations, independent dense-grid equations, Pj, Pe/Pe_eff, Elastic Shortening, PMM, SLS/ULS, rebar, reports, project schema, or other member workflows.
