# IGIRDER.FLEXREVIEW25

2026-10-13. Baseline: the complete IGIRDER.FLEXCHART24 source archive.

The developed I-girder solver checks primary-axis Mux/M3 with Nu. Imported
secondary-axis Muy/M2 previously appeared in the source audit without an
acceptance gate. This release records a secondary-axis scope gate: nonzero or
unavailable Muy changes a passing/section-preview overall row to REVIEW,
without changing numerical status, resistance, demand, equilibrium or D/C.
Existing FAIL/NO EQUILIBRIUM and missing resistance remain unchanged.

The stored failure summary now identifies case, Max/Min, section face and
station, preserves both raw P and solver Nu, reports unavailable resistance
explicitly, and distinguishes source-row count from station-coordinate count.
Analysis and Report/QA use the same read-only summary. When V/T declarations
and Flexure declarations differ, input copy explains their separate scope.
No new checkbox or automatic assumption synchronization is introduced.

Flexure result versions change to invalidate results calculated before the
scope gate. Project JSON serialization/restoration behavior, imported source
declarations, loads, stage Pe/losses, geometry, materials, anchorage inputs,
development equations, composite strength and other workflows are preserved.
No result-persistence feature, git push or online deployment is included.

## Validation

- 27 selected regression modules: 429 passed with the real Streamlit runtime;
  this is scoped regression, not the entire repository suite.
- Actual app.py with the supplied project: both girders and 640 imported source
  rows, original numerical values and full development traces exactly equal
  to the FLEXCHART24 calculation. Every original force/sign/station remains.
- Four member charts plus two detailed charts have distinct element IDs.
  Report/QA renders two bounds. Review invokes no solver and changes no saved
  input/load-bank/result snapshots.
- Browser review at 1440 and 1100 px confirms warnings, failure tables and all
  six charts, without JavaScript/Streamlit exceptions. Screenshots/checkpoints
  are internal and excluded from this archive.
- New tests cover positive/negative/missing Muy, zero primary moment with
  secondary bending, unchanged primary resistance, preserved failure/gaps,
  and case-aware stored summaries. Existing version test follows the current
  result-version constant while still proving stale-result rejection.

Use the complete release tree, load the current Project JSON and calculate
Flexure again. Numerical M3 agreement is software verification; combined
Nu/M3/M2, source correspondence and real end detailing still require review.

Repo summary:

```text
Qualify primary-axis girder flexure when M2 is present and explain source-row endpoint failures without altering numerical capacity or imported forces.
```
