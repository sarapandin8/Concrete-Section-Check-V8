# CROSSBEAM.PTLOSS3B1A — Construction Source UX & State Reliability

This hotfix refines the accepted PTLOSS3B1 construction/stressing-stage source model without releasing or changing any Portal-Frame structural-response solver.

## Design-stage strength criteria

- Removes `Verified Crossbeam strength at stressing` and `Verified joint / closure strength at stressing` from the design page.
- The design source now stores only specified/adopted minimum stressing criteria:
  - Crossbeam `f'ci/f'c` ratio, default `0.80` and editable.
  - Required joint/closure concrete strength for Precast Segmental construction.
- Actual cylinder/cube test acceptance belongs to construction QA / stressing release, not to the design prestress-loss input page.

## Column dimension convention

Column plan dimensions are defined relative to the Crossbeam longitudinal station axis `s`:

- `Btrans` — transverse/normal to the Crossbeam axis.
- `Blong` — parallel to/along the Crossbeam axis.
- `Column Height` — vertical member height, independent of the plan dimensions.

Legacy Project JSON values `B local-2` and `H local-3` migrate to `Btrans` and `Blong`.

## Shape-dependent geometry editing

- Rectangular equal chamfer: `Btrans`, `Blong`, `Chamfer c`.
- Rectangular equal fillet: `Btrans`, `Blong`, `Fillet radius r`.
- Circular: `Diameter D` only.

Non-applicable fields are not exposed in the active shape editor and are ignored by the geometry/property route.

## State reliability

- Column summary and shape-specific geometry editors use explicit callback commits to the scoped PTLOSS3 session-state source.
- A single valid edit is committed before rerun rather than being overwritten by a dataframe rebuilt from stale source values.
- Stressing-pair sequence edits use the same explicit commit pattern and preserve the last valid complete sequence if the edited sequence is invalid.
- Add/delete rows, navigation, and Project JSON continue to use the canonical PTLOSS3 source model.

## Safety boundary

This milestone does **not** calculate or change:

- Primary Prestress structural response.
- Secondary Prestress.
- Portal-Frame gravity/self-weight response.
- Temporary-support contact reactions or lift-off.
- Source-derived `f_cgp`.
- Final Elastic Shortening adoption.
- Friction/Wobble or Anchorage Set results.
- `Pe` / `Pe_eff`.
