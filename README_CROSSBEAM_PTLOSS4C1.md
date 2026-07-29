# CROSSBEAM.PTLOSS4C1 — Compact Prestress Loss Summary

## Purpose

Replace the former Prestress Loss `Overview` with a decision-first `Loss Summary` tab that reports each loss source in MPa and percent of `fpj`, together with instantaneous, time-dependent, and total accounted QA subtotals.

## Summary content

- Aps-weighted reference `fpj`.
- Friction/wobble, anchorage set/draw-in, elastic shortening, creep, shrinkage, and relaxation.
- Loss in MPa and `% of fpj` for every component.
- Instantaneous subtotal and Time-Dependent subtotal.
- Total accounted loss and stress remaining after accounted losses.
- One governing accounted-loss row per tendon.

## Calculation basis

- Friction and anchorage components use station-path averages without double-counting joint-face duplicates.
- Elastic Shortening remains tendon/group specific from the current accepted station chain.
- Time-Dependent loss remains the current representative event-stress scalar.
- The summary is explicitly labeled as an accounted QA subtotal; it does not release final station-dependent `Pe(s)` or `Pe_eff(s)`.

## Safety boundary

The app shows `SOURCE BLOCKED` / `INCOMPLETE` whenever Elastic Shortening or Time-Dependent evidence is missing or stale. Partial results are not mislabeled as final total effective-prestress loss.
