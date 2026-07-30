# CROSSBEAM.SUPPORTQA1 — Multi-Column Loss Verification, Support-Footprint Gate, and Batched Column Input

## Baseline

Starts from accepted `CROSSBEAM.LOADS1B — Separate SLS At Transfer and At Service Imports`.

## Purpose

Harden the existing dynamic Column / support-line source for two or more columns before the Crossbeam Analysis workflow is released. This milestone removes per-cell Column-editor reruns, verifies that every column and bay participates in prestress-loss stress routing, and blocks Elastic Shortening / Time-Dependent loss when a support footprint intersects a Hollow segment.

## Changes

### Batched Column / support-line editor

- The Section Builder Column summary and section-geometry tables now share one Streamlit form.
- Cell edits are buffered until `Apply Column / Support Layout` is pressed.
- Typing no longer rebuilds the section preview, column stiffness tables, Segment Layout source, and Prestress-Loss source after every cell edit.
- Dynamic row add/delete remains supported.
- Applied rows are canonicalized and stored in increasing station order.
- Column IDs and centerline stations must be unique before the frame model is ready.

### Support-footprint hard gate

- The production stressing-stage frame model now enforces the existing Column/support footprint QA.
- Any footprint that overlaps a recognized Hollow segment, lies outside the Crossbeam extent, has zero width, or does not overlap a recognized Segment/Zone blocks the model source.
- Segment Layout shows the same footprint evidence, but the result is no longer presentation-only: Elastic Shortening and Time-Dependent loss cannot proceed until all support footprints are compatible with Solid regions.
- The pure model-builder API retains an explicit audit-only default for legacy tests and diagnostic callers; the deployed Crossbeam loss route enables the gate.

### Multi-column Elastic Shortening representative route

For bonded post-tensioning, representative `f_cgp` evaluation now includes:

- every column centerline;
- every bay midpoint;
- every nonzero end-overhang midpoint; and
- the actual maximum `f_cgp` row within each bay/overhang.

The governing value is selected from calculated `f_cgp`, not inferred from maximum absolute moment alone.

### Multi-column Later Permanent / Time-Dependent route

Imported Later Permanent FEA response routing now includes:

- every column centerline;
- every bay/overhang midpoint; and
- the actual maximum `Δf_cd` row within each physical region.

This preserves row-coupled imported FEA response semantics while generalizing the representative stress route beyond two outer columns.

### Stale-state propagation

Changing and applying the Column/support layout now:

- changes the Prestress dirty-state hash;
- retains prior ES/TD result evidence so it can be reported as stale rather than silently deleted;
- invalidates Effective Prestress engineer adoption and FEA handoff readiness; and
- invalidates the Loads external-FEA contract until the revised loss chain and FEA model revision are confirmed again.

## Important design behavior

- Friction/Wobble and Anchorage Set equations are unchanged; column count affects those losses only if the adopted Tendon profile changes.
- The frame assembly already supports multiple fixed-base columns. This milestone hardens the stress-selection and source-gate logic around that capability.
- A Segmental layout with support footprints crossing Hollow zones is intentionally blocked. Solid support/diaphragm zones must cover the complete longitudinal footprint of every column/support.
- No Analysis workspace solver or strength/stress check was added.
- The LOADS1B separation of ULS Final Stage, SLS At Transfer, and SLS At Service is unchanged.
- No Project JSON schema change was required because the dynamic Column rows were already persisted by the accepted input model.

## Verification

- SUPPORTQA1 targeted tests: 11 passed.
- Crossbeam regression partitions: 463 passed; 2 known pre-existing obsolete source-string tests deselected.
- Loads / Project JSON / dirty-state / navigation integration: 111 passed.
- Repository inventory: 2,303 collected tests.
- Modified modules pass `py_compile` and repository `compileall`.

## Current sample-layout implication

For the reviewed four-column sample at stations 1.5, 10.0, 12.5, and 18.5 m, only the first support footprint is compatible with the current Segment Layout. The other three footprints intersect Hollow S4 or S6. Under SUPPORTQA1, Elastic Shortening and Time-Dependent loss remain source-blocked until those support regions are reassigned to suitable Solid Segment/Zone extents.
