# CROSSBEAM.ANALYSIS4C7D13 — Crossbeam ULS Result Summary integration

## Scope
Integrate the accepted Crossbeam ULS Analysis results into the existing read-only `Result Summary` workspace without rerunning Flexure, Shear, Torsion, or Combined V+T solvers.

## Changes
- Adds a Crossbeam-specific stored-result adapter for Flexure, Shear, Torsion, and Shear + Torsion.
- Result Summary now selects the Crossbeam ULS route when the active workflow is Portal Frame Crossbeam instead of falling back to dormant Beam/Girder result caches.
- Adds Crossbeam ULS decision cards and a compact stored-result table with Status, governing check, case/station, demand, capacity/limit, D/C, code basis, scope, and required action.
- Preserves construction-specific semantics:
  - Precast Segmental Flexure reports tendon-only sectional Mn.
  - Segmental physical-joint shear/torsion/V+T transfer remains separate from sectional decisions.
  - Cast-in-Place uses monolithic Zone semantics and reports physical Segment-joint transfer as not applicable.
- Detects construction-type ownership mismatch in stored component packages and reports the dormant result as `STALE` instead of showing CIP results as Segmental or vice versa.
- Crossbeam ULS completeness and executive/Report-handoff logic now use the four Crossbeam stored checks rather than Beam/Girder cache counts.
- Traceability shows active Crossbeam construction type plus the stored package/hash for each ULS component.
- Raw Crossbeam stored result tables are available in the Result Summary Traceability workspace for audit review.

## Read-only contract
`Result Summary` only reads the existing session-state result packages and stored hashes. It does not call Crossbeam preparation builders or solver runners.

## Verification
- Python compile: PASS for `app.py`, `analysis_page.py`, and all four Crossbeam ULS analysis modules.
- New D13 Crossbeam Result Summary integration tests: 6 passed, covering CIP, Segmental, construction-type stale isolation, active-workflow routing, and read-only behavior.
- Result Summary / Report-alignment / D9-D12 targeted regression set: 46 passed in a completed run before the final D13 Segmental case was added; D13 itself was rerun after that addition and passed 6/6.
- A wider legacy Crossbeam/UI sweep exposed only pre-existing baseline failures unrelated to D13 (legacy flexure joint-trace expectation tests and an old UI-theme README assertion); those failures reproduce on the untouched D12 baseline.

## Engineering impact
Result-summary integration and traceability only. No ACI equation, capacity value, demand routing, tendon/rebar credit rule, physical-joint ownership rule, or Analysis solver behavior was changed.
