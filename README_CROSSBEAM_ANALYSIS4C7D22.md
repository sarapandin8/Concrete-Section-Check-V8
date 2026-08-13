# CROSSBEAM.ANALYSIS4C7D22 — SLS Deflection / Camber displacement-source foundation

## Scope

This milestone opens the Portal Frame Crossbeam `Analysis → SLS Deflection / Camber` route without reusing the generic simple-span Beam/Girder deflection preview.

### Adopted source contract

Crossbeam absolute vertical movement is read from a dedicated verified external-FEA displacement source under `Loads → SLS Loads → SLS Deflection / Camber displacement source`.

Canonical app sign:

- positive = upward movement / camber;
- negative = downward movement / deflection.

The app deliberately does **not** integrate the imported beam M3 diagram to fabricate absolute Portal-Frame displacement. Beam curvature alone cannot recover total Crossbeam movement because connected-column translation/rotation is part of the frame response.

### Final-service span check

For each adjacent column pair, the app evaluates displacement relative to the straight chord joining the two column-centre displacement values. This removes support translation from the span-deflection measure without assuming zero column-top movement.

The final-service acceptance criterion is project-selected (`Review only`, `L/240`, `L/360`, `L/480`, `L/1000`, or custom `L/n`). `Review only` is the safe default; no code deflection limit is silently assumed.

### Transfer response

Transfer-stage displacement is reported as camber/deflection response only. No service acceptance limit is fabricated for Transfer.

### Explicit limitations

- Overhang displacement is visible but is not assigned an `L/n` acceptance limit in D22.
- Connected plot lines interpolate source stations for visualization; no unverified local extremum is inferred between imported rows.
- Creep, shrinkage, cracked-section stiffness, staged stiffness change, construction tolerance, and differential settlement are included only if already represented by the external-FEA displacement result.
- D22 stores an Analysis result package, but Result Summary / Report-QA promotion remains the next integration milestone after visual acceptance.

## Files changed

- `concrete_pmm_pro/analysis/crossbeam_sls_deflection.py` — new source validation and span-relative deflection/camber evaluator.
- `concrete_pmm_pro/ui/loads_page.py` — dedicated Crossbeam SLS vertical-displacement import/editor source.
- `concrete_pmm_pro/ui/analysis_page.py` — Crossbeam Deflection/Camber workspace, plots, audit, cache/stale behavior.
- `concrete_pmm_pro/io/project_io.py` — Project JSON persistence for the displacement-source table.
- `tests/test_crossbeam_analysis4c7d22_sls_deflection_displacement_foundation.py` — D22 regression coverage.

## Engineering equations changed

None of the accepted ULS, Transfer-stress, Final-Service-stress, prestress-loss, rebar-credit, or physical-joint stress equations were changed.
