# Crossbeam Anchorage-Set / Draw-In Methodology Specification

Milestone family: `CROSSBEAM.PTLOSS2R`

## 1. Calculation chain

`Pj source → station friction/wobble profile → anchorage seating → later immediate losses → Pe/Pe_eff`

Anchorage seating may never bypass the accepted station-by-station friction traces. `Pe / Pe_eff` remains locked until the complete immediate-loss chain is validated.

## 2. App stressing definitions

- `Jack = Left`: single-end stressing from the left anchorage.
- `Jack = Right`: single-end stressing from the right anchorage.
- `Jack = Both`: simultaneous equal stressing from the left and right anchorages.

For the PTLOSS2R2 component preview, `Jack = Both` also assumes simultaneous lock-off / anchorage seating at both ends with the same adopted `Δa`. This is an explicit app calculation assumption and must be verified against the approved PT stressing procedure before final design use.

## 3. Single-end stressing

### Inputs

- active jacking end: Left or Right;
- adopted station-by-station post-friction stress/force trace;
- anchorage draw-in `Δa` from project / approved PT supplier;
- prestressing steel modulus `Ep`;
- tendon steel area `Aps`.

### Governing distribution

For path distance `s` measured from the active anchorage:

`ΔfpA(s) = max[ΔfpA,0 − 2 ΔfpF(s), 0]`

where `ΔfpF(s)` is cumulative friction loss from the active anchorage based only on the accepted friction trace.

Solve `ΔfpA,0` from:

`Δa = 1000/Ep ∫_0^L ΔfpA(s) ds`

Then:

`fp,F+A(s) = fp,F(s) − ΔfpA(s)`

### Boundary cases

- If `ΔfpA(s)` becomes zero at `s_a < L`, anchorage-set influence ends at `s_a`.
- If `ΔfpA(L) > 0`, the full tendon is affected and a nonzero dead-end loss is retained.
- If the solved active-end loss would require negative lock-off stress, return `REVIEW REQUIRED`.
- The accepted one-end cumulative friction-loss trace must be nondecreasing with distance from the active jack.

## 4. Simultaneous both-end stressing

### 4.1 Pre-seat friction equilibrium

Left and right jacking branches are traced independently from the same `Pj`. The physical pre-seat force field is the controlling envelope of the two branch stresses.

The pre-seat point of no movement `s0` is the unique left/right branch equilibrium point:

`fL(s0) = fR(s0)`

The point is not hard-coded to `L/2`; it may move away from mid-length for asymmetric curvature/wobble routes.

### 4.2 Separated local seating zones

Each anchorage is first solved using the single-end reverse-slip distribution over its branch from the anchorage to `s0`.

If both anchorage-set loss distributions decay to zero before reaching `s0`, the local solutions are retained and the central region remains unchanged.

### 4.3 Interacting / overlapping seating zones

If either local seating zone reaches the pre-seat equilibrium region with nonzero loss, a full-tendon simultaneous compatibility solution is required.

Let `sn` be the zero-displacement neutral station after simultaneous seating and `fn` the common meeting stress. Using the left/right jacking branch traces:

`fA,L(s) = fn + fL(sn) − fL(s)` for `0 ≤ s ≤ sn`

`fA,R(s) = fn + fR(sn) − fR(s)` for `sn ≤ s ≤ L`

Solve `sn` and `fn` so that:

`ΔaL = 1000/Ep ∫_0^sn [fi(s) − fA,L(s)] ds`

`ΔaR = 1000/Ep ∫_sn^L [fi(s) − fA,R(s)] ds`

and:

`fA,L(sn) = fA,R(sn) = fn`

For the app-defined `Jack = Both` preview:

`ΔaL = ΔaR = adopted Δa`

This coupled formulation is a guarded engineering extension of the published equal-and-opposite friction / force-diagram area-compatibility concept. It is not presented as a verbatim AASHTO numbered equation.

### 4.4 Both-end acceptance checks

A both-end result is `PREVIEW READY + NOTE` only when all of the following pass:

1. a unique pre-seat left/right branch equilibrium point exists;
2. bilateral draw-in compatibility closes within tolerance;
3. final left/right stress is continuous at the solved neutral station;
4. final tendon stress is nonnegative;
5. seating does not increase stress above the accepted pre-seat friction envelope;
6. the approved PT procedure is confirmed to match the simultaneous stressing / simultaneous seating assumption.

## 5. Unit convention

App working/display system remains SI:

- stress/modulus: MPa;
- force: kN;
- steel area: mm²;
- path coordinate: m;
- anchorage draw-in: mm.

Compatibility conversion:

`1000 × (MPa / MPa) × m = mm`

Force conversion:

`Aps(mm²) × fp(MPa=N/mm²) / 1000 = P(kN)`

## 6. Published single-end benchmark acceptance

### Caltrans Prestress Manual Appendix E — Example 2

Native reference:

- `Ep = 28,000 ksi`
- `Δa = 0.375 in`
- `L = 144 ft`
- friction loss `d = 10.5 ksi`

Acceptance:

- `x_pA ≈ 109.5 ft`
- `ΔfpA,0 ≈ 15.97 ksi`

### Caltrans Prestress Manual Appendix E — Example 3

Native reference:

- one-end stressing;
- `Ep = 28,000 ksi`
- `Δa = 0.375 in`
- `L = 140 ft`
- total friction loss `d = 9.77 ksi`

Acceptance:

- `x_pA ≈ 112 ft`
- `ΔfpA,0 ≈ 15.63 ksi`

## 7. Simultaneous both-end benchmark acceptance

Because the reviewed Caltrans two-end examples represent first-end / second-end stressing rather than the app-defined simultaneous procedure, PTLOSS2R2 does not mislabel those examples as direct simultaneous benchmarks.

The simultaneous solver must instead pass independent physics/closed-form gates:

1. **Symmetric linear friction, separated zones** — reproduce the closed-form single-end affected length independently from both anchors.
2. **Symmetric linear friction, interacting zones** — reproduce the closed-form neutral station, meeting stress, anchorage loss, and bilateral draw-in compatibility.
3. **Zero-friction limit** — reduce to uniform elastic stress loss `Ep(ΔaL+ΔaR)/(1000L)`; for equal seating this is `2EpΔa/(1000L)`.
4. **Asymmetric branch mirror test** — swapping left/right friction routes mirrors `s0` and `sn` about `L/2` without hard-coding midspan.
5. **Continuity / nonnegative / no-stress-gain checks** — all must pass.

## 8. Release gate before Pe/Pe_eff

Anchorage set cannot feed effective prestress until:

1. single-end Left/Right published benchmarks pass;
2. simultaneous both-end closed-form and metamorphic benchmarks pass;
3. SI/native-unit equivalence passes;
4. station-by-station force continuity and nonnegative-stress checks pass;
5. the app definition and approved PT procedure are visibly stated and verified;
6. Project JSON persistence remains compatible;
7. Crossbeam and cross-workflow regression gates remain green.


## PTLOSS2R3 — Equivalent-average QA layer

PTLOSS2R3 does **not** replace station-specific `P(s)` with an average. It adds a summary/QA collapse of the calculated anchorage-set stress-loss distribution:

`ΔfpA,avg,i = (1/L) ∫0^L ΔfpA,i(s) ds`

and the area-weighted tendon-system value:

`ΔfpA,avg,global = Σ(Aps,i ΔfpA,avg,i) / ΣAps,i`.

For the current Crossbeam compatibility coordinate, the independently expected average is `Ep·Δa/(1000L)` for one active seating end and `Ep·(ΔaL+ΔaR)/(1000L)` for simultaneous equal both-end seating. The integrated station distribution must reproduce this identity within tolerance. This equivalent average is for summary / external lumped-loss comparison only; local section/tendon calculations continue to use station-specific post-seating force.

## PTLOSS2R3A — Visualization and independent-validation evidence closeout

PTLOSS2R3A does not alter the accepted PTLOSS2R2/R3 loss equations. It adds two QA protections:

1. The force-profile chart range is explicitly derived from all plotted force series so the post-anchorage-set curve cannot be clipped from visual/printed review.
2. A separate dense-grid verifier independently reconstructs accepted left/right friction branches and solves simultaneous both-end seating compatibility without calling the production coupled-solver helper chain. The UI reports numerical differences in neutral station, meeting stress, and left/right anchorage loss against explicit tolerances.

The three-point Left / neutral-or-characteristic / Right table is a presentation cross-check of the same station-force outputs plotted in the chart. `Pe` and `Pe_eff` remain locked.
