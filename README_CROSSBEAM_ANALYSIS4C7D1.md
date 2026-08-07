# CROSSBEAM ANALYSIS4C7D1 — Near-joint sectional runtime hotfix

## Purpose
Fix the deployed Shear + Torsion `ValueError` introduced by ANALYSIS4C7D and complete the intended Precast Segmental near-joint chart contract with real sectional checks about 100 mm before/after each physical joint.

## Root cause fixed
The 4C7D plotting helper attempted to assign an array sized for the whole result DataFrame into only the masked physical-joint rows. Pandas correctly raised `ValueError: Must have equal len keys and value when setting with an iterable` while rendering the Combined V+T component chart.

## Engineering / chart correction
- Added real row-coupled near-joint sectional demand checks at approximately `sJ - 0.10 m` and `sJ + 0.10 m`, recovered strictly from the adjacent Segment without crossing the physical joint.
- Shared Shear preparation now supplies these near-joint rows to standalone Shear, standalone Torsion, and Combined V+T.
- Standalone Flexure independently generates the same near-joint sectional stations and applies the existing Segmental development-credit rules there.
- Combined V+T charts again keep exact `PHYSICAL JOINT SIDE` rows audit-only; finite near-joint sectional rows close the plotted Segment trace instead.
- Flexure capacity traces are clipped to the ±100 mm joint gap and no longer extend a stable-credit line to the exact joint station.
- Shear and Torsion line traces use the same near-joint gap while support interiors remain omitted.
- Exact one-sided physical-joint audit rows and physical-joint transfer `REVIEW` semantics remain unchanged; no line connects across a physical joint.
- Cast-in-Place routing is unchanged.

## Regression coverage
Targeted Crossbeam ULS tests cover:
- Combined V+T component rendering with near-joint rows and no pandas length mismatch.
- Shear and Torsion station-count changes from added near-joint sectional checks.
- Segment-owned trace endpoints at 4.4/4.6 m, 10.4/10.6 m, 19.4/19.6 m, and 25.4/25.6 m in the 30 m six-Segment benchmark; the joint inside the C2 support footprint remains omitted from ordinary traces.
- Flexure near-joint section rows and truthful Segmental capacity-envelope gaps.
