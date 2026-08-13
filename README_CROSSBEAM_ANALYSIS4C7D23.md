# CROSSBEAM.ANALYSIS4C7D23 — Deflection / Camber Source Ownership Cleanup

## Purpose

Move the Portal Frame Crossbeam external-FEA vertical-displacement source out of the `Loads` workspace and into its true user-facing owner:

`Analysis → SLS Deflection / Camber → Deflection / Camber source`

This is an architecture/ownership cleanup only. It does not change the D22 displacement evaluation equations or the accepted Crossbeam ULS/SLS stress logic.

## Adopted behavior

- `Loads` remains the owner of row-coupled force demands (`P / V2 / T / M3`) and their SLS/ULS stages.
- External-FEA vertical displacement is response/source data used only by the Deflection / Camber check, so its import/template/editor now lives on the Analysis Deflection / Camber page.
- A single source table may contain both `Transfer stage` and `Final service stage` rows.
- Canonical displacement sign remains:
  - positive = upward / camber;
  - negative = downward / deflection.
- Absolute Portal-Frame displacement is still read from verified external FEA; the app does not fabricate total frame displacement by integrating Crossbeam `M3/EI`.
- Final-service span response remains measured relative to the straight chord joining adjacent column-centre displacements.

## Project JSON ownership

The durable Project JSON owner is now:

`metadata.analysis_sources.crossbeam_sls_deflection_displacement`

rather than `metadata.workflow_load_tables.crossbeam_sls_displacement_table`.

D22 projects are forward-migrated on load: legacy displacement rows found under `workflow_load_tables` are restored, then written under `analysis_sources` the next time the project is saved.

## Dependency / stale-result behavior

The displacement source is deliberately excluded from the global Loads dirty-state hash. Changing it:

- changes the dedicated Deflection / Camber preparation fingerprint;
- makes an existing Deflection / Camber result stale;
- does **not** invalidate Crossbeam ULS Flexure/Shear/Torsion/V+T results;
- does **not** invalidate SLS Stress & Cracking results merely because displacement rows changed.

This keeps source ownership and dependency scope aligned.

## UI changes

Removed from `Loads → SLS Loads`:

- displacement source heading;
- Excel/CSV displacement import;
- displacement data editor.

Added to `Analysis → SLS Deflection / Camber`:

- source explanation;
- Excel/CSV templates;
- import/replace action;
- editable Transfer/Final-Service displacement source table;
- run-blocking guidance that points to the local Analysis source panel.

## Regression

- `py_compile` on the changed Python modules: PASS.
- D22 + D23 focused tests: 9 passed.
- D17–D23 SLS/result-semantics regression: 31 passed.
- Loads / Project JSON / navigation / D20–D23 focused regression: 81 passed.

A broad wildcard `tests/test_crossbeam_analysis4c7d*.py` attempt exceeded the execution time limit and is not claimed as a completed full-suite run.

## Engineering scope

No changes to:

- ACI stress criteria;
- Segmental Transfer joint no-tension rule;
- Segmental Final Service joint `0.70 MPa` compression rule;
- ULS equations or reinforcement/prestress credit;
- prestress loss equations;
- external-FEA force-demand routing;
- D22 support-chord relative-deflection calculation;
- user-adopted `L/n` acceptance calculation.
