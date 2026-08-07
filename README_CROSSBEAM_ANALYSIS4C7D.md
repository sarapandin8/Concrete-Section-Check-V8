# CROSSBEAM ANALYSIS4C7D — Segmental near-joint chart points

## Summary
Implements the agreed Segmental chart rule for all ULS graphs: physical-joint one-sided rows are plotted at near-joint stations about 100 mm away from the exact joint centerline, while the exact joint remains a REVIEW discontinuity and is still reported in hover/audit context.

## Changes
- Updated the shared Segmental near-joint plotting helper to place one-sided left/right rows at approximately `joint station ± 0.10 m` (clamped safely within the member span).
- Applied the near-joint plotting rule to shared one-sided joint markers used by shear and torsion charts.
- Updated the standardized Combined V+T plotting-group builder so Precast Segmental physical-joint-side rows participate in the segment-owned traces as near-joint endpoints instead of being omitted from the plotted line data.
- Updated flexure one-sided joint markers to plot near the joint gap while keeping the exact joint station in hover text.
- Preserved the core engineering semantics:
  - no trace is drawn through a physical joint,
  - support interiors remain omitted,
  - PT end-station coverage remains retained,
  - exact joint transfer is still REVIEW rather than certified by sectional traces.

## Regression intent
This milestone changes plotting semantics only for Precast Segmental crossbeam ULS charts and should not alter Cast-in-Place continuity semantics or the underlying engineering calculations.
