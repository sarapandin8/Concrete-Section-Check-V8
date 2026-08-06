# CROSSBEAM.ANALYSIS4C7C — Torsion and Combined V+T Semantic / Chart Closeout

## Scope

- Closed the standalone Torsion and Combined Shear + Torsion decision semantics for both Cast-in-Place and Precast Segmental Crossbeams.
- Repaired the three Combined V+T review figures so every applicable D/C chart contains a real full-span `Limit = 1.0` trace rather than a legend-only placeholder.
- Added explicit below-threshold and zero-demand display modes so non-applicable torsion reinforcement checks are reported as `NOT REQUIRED`, not as blank or misleading `NOT CALCULATED / REVIEW` charts.
- Preserved the accepted station-dependent Effective Prestress, support Face / prestressed `h/2`, full-span PT end-station, and construction-mode routing introduced in the preceding milestones.

## Root-cause correction — missing D/C limit lines

- The previous global two-point `D/C = 1.0` trace was passed through the support-footprint line-break helper.
- Because every support crossing inserted a `None` gap into the two-point trace, the plot retained the legend entry but rendered no visible line.
- Component result traces are now segmented first; the global red dashed limit trace is added afterward as an independent full-span line from `s = 0` to `s = L`.
- The limit trace is not clipped by Column/support footprints, PT end stations, Zone boundaries, or physical Segment joints.

## Combined section-size interaction

- When every eligible station is below `phiTth`, the view is identified as a **Shear-only section-size check** and states that the torsion term is omitted by the threshold route.
- When torsion design is active, the accepted ACI combined V+T section-size interaction wording and result path remain active.
- The full-span red dashed `D/C = 1.0` line remains visible in both modes.

## Combined transverse reinforcement

- When the required `(Av + 2At)/s` is zero at every eligible station, the result is reported as `NOT REQUIRED` rather than a false governing `D/C = 0.000` at `s = 0`.
- The zero-demand trace remains visible slightly above the chart axis for transparent station evidence.
- The figure displays `NOT REQUIRED AT ALL ELIGIBLE STATIONS`, retains the full-span limit line, and suppresses the artificial governing marker.
- Mixed or active reinforcement-demand cases retain the accepted required/provided D/C trace and governing result.

## Longitudinal torsion reinforcement

- If all eligible stations are below the torsion threshold, the blank `NOT CALCULATED / REVIEW` view is replaced by a threshold-applicability chart.
- The chart plots `Tu / phiTth`, the full-span activation limit `1.0`, support Face / `h/2` source markers, and the maximum threshold utilization.
- The result is `NOT REQUIRED`; minimum `Aℓ` and direct flexure-plus-torsional-tension checks are explicitly not activated.
- When torsion design applies, the accepted longitudinal `Aℓ` / flexure-plus-torsional-tension D/C route, step traces, and non-applicable bands remain available.

## Standalone Torsion semantics

- `BELOW THRESHOLD` results now identify the governing check as the **Torsion threshold screen**.
- The primary ratio is labeled `Tu / phiTth` or `Threshold utilization`, not a generic strength D/C.
- Sectional torsion reinforcement, longitudinal `Aℓ`, and section-size checks are `NOT REQUIRED` below threshold.
- `phiTn` remains informational and is not presented as the governing decision route.

## Construction-mode behavior

### Cast-in-Place

- Uses `Zone` / `Zone-owned` wording.
- Physical-joint transfer is `NOT APPLICABLE — Cast-in-Place monolithic Zone`.
- No one-sided physical-joint action is requested.

### Precast Segmental

- Uses `Segment` / `Segment-owned` wording.
- Existing one-sided joint rows, trace breaks, tendon-only joint/development credit, and separate physical-joint transfer review are preserved.

## Engineering equations unchanged

- No ACI Flexure, Shear, Torsion, or Combined V+T resistance equation changed.
- No strength-reduction factor changed.
- No reinforcement area, spacing, cage-credit, or longitudinal-credit equation changed.
- No station-dependent Effective Prestress equation or interpolation rule changed.
- No Column Face, prestressed `h/2`, support-footprint, physical-joint, or full-span PT end-station rule changed.
- This milestone changes decision semantics, evidence routing, and figure construction only.

## Verification

- `python -m compileall -q app.py concrete_pmm_pro tests` — PASS.
- Crossbeam Analysis targeted/batched inventory — 116 passed.
- Complete Crossbeam test inventory — 645 collected, 639 passed, 6 verified pre-existing failures, 0 new failures.
- New ANALYSIS4C7C semantic / figure-contract tests — 9 passed.
- Deployment dependency contract — 1 passed (`streamlit==1.61.0`, `starlette==1.3.1`).

### Verified pre-existing failures

- Five historical source-string assertions still expect superseded PTLOSS / Effective Prestress handoff wording.
- One Rebar editor-count assertion still expects seven editors while the accepted baseline contains eight.
- The same six failures exist before ANALYSIS4C7C and were not changed to force a green result.

## Repo summary

Close Crossbeam Torsion and Combined V+T semantics with real full-span D/C limit lines, explicit below-threshold and zero-demand NOT REQUIRED modes, complete longitudinal applicability evidence, and construction-mode-aware joint messaging without changing engineering equations.
