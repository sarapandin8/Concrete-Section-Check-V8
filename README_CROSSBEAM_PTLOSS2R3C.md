# CROSSBEAM.PTLOSS2R3C — Anchorage Set Semantic Closeout

This milestone closes the Crossbeam Anchorage Set preview UI semantics without changing any prestress-loss solver equation.

## Scope

- Adds an explicit **Overall anchorage-set summary — all active tendons** heading above the global component cards.
- Clarifies that governing/local maximum, area-weighted equivalent average, calculated seating ends, and neutral/characteristic geometry in the upper cards summarize the full active tendon set.
- Keeps the **Selected tendon** cards under the force-profile graph as the tendon-specific decision layer.
- Prevents users from mistaking an overall governing Both-end value for the currently selected Single-end tendon.

## Solver protection

No changes to Friction/Wobble, Single-end Anchorage Set, simultaneous Both-end Anchorage Set, equivalent-average calculations, Pj, Pe/Pe_eff, PMM, SLS/ULS, rebar, reports, or other member workflows.
