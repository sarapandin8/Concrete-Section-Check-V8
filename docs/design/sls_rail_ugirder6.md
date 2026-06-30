# SLS.RAIL.UGIRDER6 — Decision Summary + Status Polish

## Scope

This milestone adds a compact guarded decision summary for the Railway U-Girder staged SLS review workflow.

The summary condenses:

- Transfer
- Lifting
- Wet slab casting
- Final service

into a single table with decision wording, governing source, utilization, governing stress, section basis, and review action.

## Engineering guardrails

The decision wording is intentionally guarded:

- `Preview PASS` means the stage is available for engineering review under the current preview assumptions.
- `REVIEW` means the stage needs attention because a limit failed, a required load case is missing, or a check row is not available.

This milestone does not create a final code-certified staged composite solver.

## Not changed

No changes were made to:

- PMM / ULS solvers
- shear / torsion checks
- prestress loss equations
- transfer-length force ramping
- development length
- anchorage / end-zone bursting
- geometry generator
- report generation
