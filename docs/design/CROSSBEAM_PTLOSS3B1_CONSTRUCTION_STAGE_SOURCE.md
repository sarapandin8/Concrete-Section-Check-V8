# CROSSBEAM PTLOSS3B1 — Construction/Stressing-Stage Source Specification

## Purpose

Define the auditable physical source model required before implementing a limited 2D Portal-Frame stressing-stage solver for Elastic Shortening.

## 1. Construction methods

### Precast Segmental

- All segments are erected/assembled before stressing.
- Joint/closure concrete must satisfy the adopted project stressing-strength requirement before stressing.
- Tendons are stressed as verified symmetric pairs/groups.
- Temporary erection support/gantry remains available during stressing.
- The future solver must allow prestress camber to cause partial/full loss of contact.

### Cast-in-Place

- Crossbeam concrete must satisfy the adopted stressing-strength criterion before stressing.
- Continuous falsework/support condition is represented by the same compression-only contact model unless a future approved project-specific source replaces it.

## 2. Column source

Inputs per column:

- Column ID.
- Station `s` along the Crossbeam.
- Height.
- Shape.
- Shape dimensions aligned with local 2/3 axes.
- Concrete `f'c`.

Current base assumption: `FIXED`.

Accepted shapes:

- Rectangular — Equal Chamfer 4 Corners.
- Rectangular — Equal Fillet 4 Corners.
- Circular.

Derived gross properties:

- `A`.
- `I22`.
- `I33`.
- `Ec` using the existing ACI normal-weight concrete material route.
- `EA`.
- `EI22`, `EI33`.

No structural response is calculated in PTLOSS3B1.

## 3. Temporary support source

Default idealization:

`continuous full-length + initially in contact + compression-only + automatic lift-off`.

Future contact rule:

- Active contact reaction must satisfy `R >= 0`.
- If a linear trial solution requires `R < 0`, that location cannot carry tension and must be released, followed by re-analysis until the active contact set is compatible.

`All active` and `all released` may later be used only as QA bounding cases, not as the physical design-use source when automatic contact is available.

## 4. Stressing pair sequence

- Pair membership is derived from adopted tendon geometry.
- Stressing order is an independent construction source.
- Every verified pair must appear exactly once.
- Tendons within the same pair are stressed simultaneously.
- The stored order will drive the future incremental stage solver.

## 5. Strength readiness

- Default Crossbeam stressing criterion: `f'ci/f'c = 0.80` as a configurable project assumption.
- Verified Crossbeam strength at stressing is a separate input/readiness source.
- Precast joint/closure required strength and verified strength are separate explicit sources.
- No universal closure-strength value is invented by the solver.

## 6. Locked downstream calculations

PTLOSS3B1 must not release:

- Primary/Secondary Prestress structural response.
- Contact reactions/lift-off results.
- Source-derived `f_cgp`.
- Final Elastic Shortening.
- Time-dependent losses.
- `Pe` / `Pe_eff`.
