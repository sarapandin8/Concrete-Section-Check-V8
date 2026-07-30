# CROSSBEAM.PTLOSS4D2B — Compact Prestress-Loss Closeout

## Purpose

Close the Portal Frame Crossbeam Prestress Loss development phase with a compact, decision-first Effective Prestress page so the next major effort can move to the Analysis workflow without removing any accepted engineering traceability.

## Compact Effective Prestress page

The default page now shows only four decision cards:

1. Average total loss — QA
2. Average effective prestress
3. Maximum local loss
4. External FEA / SLS handoff status

One concise scope message states that the current external-FEA handoff uses the representative Time-Dependent approximation, that exactly one FEA application route must be used, and that external FEA remains responsible for secondary prestress and verified SLS response.

## Collapsed QA detail

The following information remains available but is collapsed by default:

- QA formulas, stress/force closure, and projected-station averaging audit;
- system-station and tendon/station Effective Prestress preview tables;
- detailed sequential source rows;
- FEA instructions, limitations, and traceability.

This preserves auditability without making the normal workflow a multi-page calculation report.

## Compact FEA handoff contract

The FEA route selector and Engineer-adoption checkbox are displayed in one compact control row. The page then shows a single contract-status message, Source ID / Contract ID, the Tendon handoff summary, and three download buttons.

Download gating, Source/Contract fingerprints, Engineer adoption, workbook QA formulas, no-double-counting rules, and the external-FEA secondary/SLS boundary are unchanged.

## Regression boundary

- No Friction/Wobble, Anchorage Set, Elastic Shortening, Creep, Shrinkage, Relaxation, Effective Prestress, averaging, or closure equation is changed.
- No Project JSON schema or engineering-result state is changed.
- No solver route or runtime count is changed.
- Main Loads remains dedicated to verified ULS/SLS response import.
- PTLOSS4D2A workbook and CSV contracts remain compatible.

## Closeout decision

After visual confirmation on the deployed app, PTLOSS4D2B is intended to freeze the Prestress Loss workflow and establish the baseline for the next Analysis-focused milestone.
