# QA.BASELINE1 - Baseline Test Gate and Documentation Alignment

Milestone: `QA.BASELINE1`

This milestone stabilizes the uploaded `Concrete-Section-Check-V6` baseline so it
can be used as a reliable starting point for later engineering features. It is a
QA/documentation/test-gate milestone only.

## Scope

- Confirm the uploaded baseline opens, compiles, and has a coherent test gate.
- Keep the Streamlit production dependency in `requirements.txt` unchanged.
- Add a pytest-only Streamlit fallback stub so source-audit and import tests can
  run in sandbox/CI environments where the Streamlit UI runtime is not installed.
- Refresh stale source-audit tests whose expected UI strings or setup routing no
  longer matched the current Project and Analysis architecture.
- Add exact wording in PMM final-readiness audit documents so line wrapping does
  not defeat source-audit guard tests.

## Deliberate Non-Scope

- No PMM solver equation changes.
- No prestress stress-state or `Pe_eff` logic changes.
- No shear, torsion, flexure, service-stress, deflection, or composite-section
  calculation changes.
- No UI feature addition.
- No report output logic change.

## Current Baseline Capability Notes

The source now contains guarded commercial-preview workflows for:

- Column/Pier/Wall/Pylon flexural PMM with ACI-oriented RC production-preview
  readiness evidence and AASHTO LRFD PMM still guarded as future work.
- Beam/Girder ULS workspace with compact flexure/shear/torsion decision routing,
  including code-basis modules for flexure and shear/torsion preview layers.
- Beam/Girder staged SLS stress workflow with Transfer, Construction, Service,
  prestress force-state handling, code-limit preview, full-length stress diagram,
  and Beam/CIP final-service split checks.
- SLS deflection/camber preview workspace.
- Validation, reporting, Word export, and QA modules.

All PASS/FAIL wording in these preview areas remains guarded. Preview checks are
not final code-certified design checks unless a later named milestone explicitly
implements and validates that scope.

## QA Gate Result

`QA.BASELINE1` is considered successful only if source compilation passes and the
full test suite can be executed in practical chunks without failures. A single
all-at-once pytest run may exceed the hosted sandbox execution window because the
validation and Word-report tests are comparatively slow; that is a runner limit,
not a solver result.
