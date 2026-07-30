# CROSSBEAM.SUPPORTQA1A — One-Sided Column-Joint ES Audit and Equilibrium Closure

## Baseline

Starts from candidate `CROSSBEAM.SUPPORTQA1 — Multi-Column Loss Verification, Support-Footprint Gate, and Batched Column Input` after visual review of the four-column Section Builder, Segment Layout, and Elastic Shortening pages.

## Purpose

Clarify why two different Crossbeam force/stress rows can legitimately occur at one Column centerline in a line-frame model, and prevent those one-sided values from being accepted without an explicit Column-joint equilibrium check.

A Column centerline is a frame joint. The Crossbeam section immediately to the left is the `LEFT LIMIT (s−)` and the Crossbeam section immediately to the right is the `RIGHT LIMIT (s+)`. They share the same displayed station but are different one-sided section limits. Their internal actions may differ because the Column-top action, a prestress equivalent nodal action, and an active temporary-support contact reaction can enter the joint.

## Changes

### Explicit one-sided section labels

- Beam response rows now identify:
  - `I-end / RIGHT LIMIT (s+)`;
  - `J-end / LEFT LIMIT (s−)`; and
  - `Interior sample`.
- The bonded `f_cgp` evaluation table labels every Column centerline row as either:
  - `Column Cn centerline — LEFT LIMIT (s−)`; or
  - `Column Cn centerline — RIGHT LIMIT (s+)`.
- The table exposes `Limit side` and `Element` columns so two values at the same station are no longer presented as duplicate answers to one section.

### Column-joint equilibrium audit

For every Column centerline, the stored cumulative solution is post-processed in the global reference-node signs:

```text
Σ(element resisting actions)
− explicit prestress nodal action
− active contact / restraint reaction
= residual
```

The element sum includes:

- the left Crossbeam one-sided action, when present;
- the right Crossbeam one-sided action, when present; and
- the Column-top action.

The audit includes exact centroid rigid-offset transformations used by the frame solve. Distributed self-weight fixed-end effects are already included in the element end actions. No additional structural solve is performed.

Each Column reports:

- left and right beam joint actions;
- Column-top action;
- explicit prestress nodal action;
- temporary-support contact/restraint reaction;
- residual `Fx`, `Fy`, and moment;
- normalized residual ratio; and
- `PASS` / `REVIEW`.

The Elastic Shortening result is not ready if any Column-joint audit fails the adopted `1.0e-8` residual-ratio tolerance or lacks the required beam/Column connectivity.

### Multi-column coverage summary

The ES page now shows:

- compatible support footprints;
- evaluated physical locations;
- number of Columns, bays, and overhangs;
- total `f_cgp` audit rows; and
- Column-joint equilibrium pass count and maximum residual ratio.

For bonded tendons, a physical location is counted as covered only when:

- each Column has its one-sided centerline evaluation rows; and
- each bay/overhang has both a midpoint row and an actual governing-`f_cgp` row.

The permanently unbonded route continues to show member-length integration rather than bonded location coverage.

### Stale-result safety

- The lightweight ES fingerprint schema is advanced to `lightweight-es-supportqa1a-joint-audit-v2`.
- Any stored SUPPORTQA1 ES result without the new one-sided and equilibrium evidence becomes stale and must be rerun.
- The downstream Time-Dependent fingerprint inherits the revised ES fingerprint, so Pe/Pe_eff, Time-Dependent Loss, Effective Prestress adoption, and external-FEA handoff cannot silently reuse an older ES source.

### Semantic cleanup

The obsolete statement that Pe/Pe_eff and Time-Dependent Loss were not yet released is replaced with the current rule: after a support-layout change, Pe/Pe_eff assembly, Time-Dependent Loss, and Effective Prestress must be recalculated before renewed downstream adoption and FEA handoff.

## Engineering scope

- No Friction/Wobble equation changed.
- No Anchorage Set equation changed.
- No Elastic Shortening equation or stressing-group factor changed.
- No contact/frame stiffness formulation changed.
- No additional structural solve was added.
- No Project JSON schema changed.
- No ULS/SLS Loads or Analysis workflow changed.

This milestone adds interpretation, post-solve equilibrium evidence, and a readiness gate around the accepted cumulative ES solution.

## Verification

- SUPPORTQA1 / SUPPORTQA1A targeted tests: 19 passed.
- Crossbeam regression partitions: 464 passed; 2 known pre-existing obsolete PTLOSS4B2B1 source-string failures reproduced on the starting SUPPORTQA1 baseline.
- Loads / Project JSON / dirty-state / navigation / Result Summary integration: 184 passed.
- Repository inventory: 2,304 collected tests.
- Exact two-column lightweight ES numerical regression remains unchanged.
- Four-column joint-equilibrium benchmark: 4/4 Column centerlines pass the `1.0e-8` residual-ratio gate.
- Modified modules pass `py_compile`; repository `compileall` is required before packaging.
