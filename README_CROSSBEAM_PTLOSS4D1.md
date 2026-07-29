# CROSSBEAM.PTLOSS4D1 — Reordered Loss Workflow and Source-Gated Effective Prestress Preview

## Purpose

Reorder the Prestress Loss subtabs to follow the actual calculation chain and add a reviewable Effective Prestress preview without releasing the final SLS handoff.

## Workflow order

`Friction & Wobble → Anchorage Set / Draw-in → Elastic Shortening → Time-Dependent → Loss Summary → Effective Prestress → Audit`

## Loss Summary semantics

- Separates the Aps-weighted tendon-path-average loss from the maximum local tendon/station loss.
- Keeps the system-average value for global prestress review.
- Keeps the maximum local value for tendon/station audit.
- Reports each loss source in MPa and percent of the Aps-weighted `fpj`.
- Does not substitute the local maximum for the system-average total.

## Effective Prestress preview

- Builds the row-consistent sequential chain `fpj → after friction → after anchorage → after ES → fpe preview`.
- Calculates tendon force `Pe = Aps × fpe / 1000` in kN.
- Calculates Aps-weighted average effective stress and average effective force.
- Displays system tendon-force distribution by station.
- Displays stress closure and force closure.
- Shows the formulas and unit conversion used by the preview.

## Safety boundary

- Time-Dependent loss remains the current representative event-stress scalar.
- Station-dependent Time-Dependent loss is not yet released.
- Secondary prestress response of the indeterminate portal frame is not assembled.
- Result Summary, Report / QA, ULS, and SLS receive no Effective Prestress handoff.
- The tab therefore remains `PREVIEW READY — FINAL SLS HANDOFF BLOCKED` even when its source and closure checks pass.

## Engineering impact

No Friction/Wobble, Anchorage Set, Elastic Shortening, Creep, Shrinkage, or Relaxation equation changed. No Project JSON schema or solver runtime changed.
