# AASHTO.COL.PMM1.CODE_SYNC1 — Analysis Design-Code Synchronization

## Problem

Column/Pier/Wall/Pylon can select either ACI 318 or AASHTO LRFD in Setup. After AASHTO LRFD was selected, Analysis could still display or reuse ACI-oriented PMM state because `AnalysisSettings.code` was a separate solver-control field that could remain stale at `ACI 318`.

This created a route risk:

- Setup / chrome says AASHTO LRFD, but
- AnalysisSettings / cached PMM result still comes from an older ACI run.

## Fix

- Setup/workflow Project Design Code is treated as the source of truth.
- AnalysisSettings keeps solver controls such as sweep resolution, rebar/prestress inclusion, prestress stress model, etc., but its `code` is synchronized from the workflow-compatible Project Design Code.
- Analysis synchronizes the code before rendering cached PMM result views.
- When the synchronized code changes, stale PMM result/cache artifacts are cleared so an old ACI result cannot remain visible after changing to AASHTO.
- Preflight input building also forces the AnalysisInput settings code from the workflow-compatible Project Design Code, so solver routing cannot use stale ACI settings.

## Scope

This milestone does not change the AASHTO PMM formulas from AASHTO.COL.PMM1. It only fixes route/display/source-of-truth synchronization.

## Expected behavior

For Column/Pier/Wall/Pylon:

- Setup Design Code = ACI 318 → AnalysisSettings.code = ACI 318 → PMM route = ACI.
- Setup Design Code = AASHTO LRFD → AnalysisSettings.code = AASHTO LRFD → PMM route = AASHTO.
- If the code is changed after an earlier PMM run, cached PMM results are cleared and the user must recalculate.

## Unit note

AASHTO PMM remains SI-internal. AASHTO ksi/kips expressions must continue to pass through the AASHTO unit conversion helpers added in AASHTO.COL.PMM.BASIS1.
