# CROSSBEAM.PTLOSS.UX1 — Central Prestress-Loss Run Readiness

This milestone makes Crossbeam prestress-loss blockers visible at the calculation point without changing any engineering equation or source gate.

## Interaction changes

- Adds one `Prestress Loss Run Readiness` panel above every loss-component subtab.
- Lists Tendon System, Tendon Profile, Friction/Wobble, Anchorage Set, Elastic Shortening, Time-Dependent, and Effective Prestress in dependency order.
- Shows the exact unresolved issue, required action, and `Where to fix` location in one static decision table.
- Keeps source states honest: `CURRENT`, `STALE`, `READY TO RUN`, `BLOCKED`, and `CURRENT / CLOSED`; no misleading `PASS` is used for source readiness.
- Keeps normal Elastic Shortening and Time-Dependent Run buttons clickable. A blocked click returns the exact source issues next to the button and does not call a solver.
- Deduplicates repeated blocker text while retaining distinct engineering causes.

## Safety retained

- Friction/Wobble and Anchorage Set remain current-input automatic calculations.
- Elastic Shortening and Time-Dependent remain separate on-demand calculations.
- Advanced Construction-Stage QA remains optional, confirmation-gated, and computationally heavy.
- No prestress-loss equation, closure tolerance, fingerprint, session-state key, Project JSON schema, FEA contract, ULS/SLS route, or result-cache contract changed.
- Effective Prestress remains blocked until all upstream sources and closure gates are current.

## Repo summary

Centralize Crossbeam prestress-loss blockers in one decision-first readiness panel and keep normal ES/TD run actions clickable with exact no-solver failure guidance.
