# CROSSBEAM.PTLOSS3B1B — Compact Column Plan-Section Preview

This UI hotfix refines the accepted PTLOSS3B1A construction/stressing-stage source model without changing any prestress-loss or structural-stage solver logic.

## Column preview

- Replaces the ASCII/text `PLAN VIEW` sketch with a compact Plotly engineering preview.
- The preview follows the same axis convention as the source model:
  - `s` = Crossbeam longitudinal axis.
  - `Btrans` = transverse / normal to `s`.
  - `Blong` = along / parallel to `s`.
- The user selects a column from the preview selector; the graph then follows that column's current shape and dimensions.
- Rectangular equal-chamfer previews show `Btrans`, `Blong`, and `Chamfer c`.
- Rectangular equal-fillet previews show `Btrans`, `Blong`, and `Fillet r`.
- Circular previews show `Diameter D` only.
- Incomplete geometry shows a non-misleading input-required message instead of inventing nominal dimensions.
- Plot height is intentionally compact so the preview does not dominate the source-input workspace.

## Safety boundary

This milestone does **not** change:

- Column property equations or persisted source values.
- Friction/Wobble or Anchorage Set solvers.
- PTLOSS3 elastic-shortening equations.
- Primary/Secondary Prestress structural response.
- Temporary-support contact/lift-off analysis.
- Source-derived `f_cgp`.
- `Pe` / `Pe_eff` or any other member workflow.
