# QA.RAIL.UGIRDER1 — Railway U-Girder Workflow Regression Audit

## Purpose

This milestone stabilizes the accepted Railway U-Girder staged SLS workflow before adding any new capability.  It exists because the previous non-recovery `SLS.RAIL.UGIRDER8` package was created from the wrong baseline and could have silently rolled back accepted fixes.

## Baseline

Accepted input baseline:

```text
concrete-section-pro_SLS-RAIL-UGIRDER8-RECOVERY-service-multifiber-plot-rebased.zip
```

Expected SHA-256:

```text
b09c4acfdaf639204f97ab04f28998d8da7cfca6e648ef035ec082bc27eda776
```

## Scope

No solver equation, section-property, prestress-loss, Pe/debond participation, ULS, anchorage, transfer-length, development-length, or report-generation logic is changed.

The milestone adds regression coverage for the workflow handoff items most likely to regress silently:

- Railway U-Girder project save/load preservation of geometry, concrete material assignment, bridge assembly metadata, prestress system settings, strand/debonding table, and staged construction settings.
- Symmetric L/R debond mirroring plus station-based strand participation consistency at support, midspan, and right sleeve stations.
- Visible transfer/lifting/service SLS material-strength routing, especially `web f'ci = 36 MPa` at transfer/release and lifting.
- Guarded Railway U-Girder review wording and key UI/source markers for the dedicated SLS workflow.

## Current capability statement

Railway U-Girder staged SLS workflow is available for engineering-review preview. It includes geometry, material/assembly settings, strand/debonding input, station-based strand participation, transfer/lifting/construction/service staged stress previews, service multi-fiber stress plotting, and guarded decision summaries.

It is not final code-certified design.
