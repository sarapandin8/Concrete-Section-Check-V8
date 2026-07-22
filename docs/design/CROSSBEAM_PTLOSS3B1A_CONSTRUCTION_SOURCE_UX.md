# CROSSBEAM PTLOSS3B1A — Construction Source UX and State Contract

## 1. Design versus construction verification

The design application defines specified minimum concrete strengths used to establish the stressing-stage design basis. It does not request future field-test results before construction exists.

- Crossbeam source: specified `f'ci/f'c` criterion.
- Precast joint/closure source: specified minimum strength at stressing.
- Actual test verification is a future construction QA / stressing-release record and must not gate design-source readiness.

## 2. Column-axis convention

Let `s` be the Crossbeam longitudinal axis.

- `Btrans`: plan dimension transverse/normal to `s`.
- `Blong`: plan dimension parallel to/along `s`.
- Column Height: vertical member length from base to Crossbeam connection.

For in-plane Portal-Frame bending along `s`, the gross inertia about the transverse axis is derived using the `Blong` dimension cubed. The source model continues to retain both gross principal inertias for later solver QA.

## 3. Accepted shape inputs

### Rectangular — equal chamfer at four corners

Required active dimensions: `Btrans`, `Blong`, chamfer leg `c`.

### Rectangular — equal fillet at four corners

Required active dimensions: `Btrans`, `Blong`, fillet radius `r`.

### Circular

Required active dimension: diameter `D`.

Inputs belonging to another shape are dormant and must not feed section-property calculations.

## 4. Editor state contract

- The canonical source remains `crossbeam_ptloss3b1_column_rows`.
- Editors commit through scoped callbacks before the rerun reads the source again.
- Editor widget keys are revisioned after a successful commit to avoid replaying stale editor deltas.
- A single edit must persist without requiring repeated entry.
- Pair sequence is committed only if each verified pair occurs exactly once and sequence values are `1..G`; otherwise the last valid sequence remains adopted.

## 5. Locked calculations

PTLOSS3B1A is input/source hardening only. No structural stage, contact, prestress-response, `f_cgp`, Elastic Shortening adoption, or effective-prestress solver is released.
