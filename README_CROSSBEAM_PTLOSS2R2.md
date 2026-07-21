# CROSSBEAM.PTLOSS2R2 — Simultaneous Both-End Anchorage Set Revalidation

PTLOSS2R2 defines `Jack = Both` as simultaneous equal left/right stressing and activates a guarded simultaneous lock-off/seating anchorage-set preview while keeping `Pe / Pe_eff` locked.

## Engineering changes

- Retains the PTLOSS2R1 single-end full-path friction-coupled reverse-slip solver and Caltrans benchmark coverage.
- Changes simultaneous-both-end pre-seat friction selection from a geometric nearest-end switch to the controlling left/right jacking branch envelope; the point of no movement is the branch-force equilibrium intersection and is not hard-coded to midspan.
- For simultaneous both-end anchorage seating:
  - solves independent local reverse-slip zones when they remain separated;
  - escalates to a guarded full-tendon coupled compatibility solve when the zones reach/overlap the equilibrium region;
  - uses the same adopted `Δa` at both ends and assumes simultaneous lock-off/seating for the component preview;
  - requires compatibility closure, force continuity, nonnegative final stress, and no stress gain above the accepted pre-seat friction envelope.
- The coupled formulation is explicitly described as an engineering extension of the published force-diagram / equal-and-opposite-friction concept, not a verbatim AASHTO numbered equation.
- Replaces Python-style `None` values in the decision view with engineering-facing em-dash placeholders and separates affected-length, neutral-station, dead-end-loss, and neutral-region-loss semantics.

## Validation

- Caltrans Appendix E single-end benchmarks remain required.
- Adds symmetric small-draw-in separated-zone benchmark.
- Adds symmetric interacting-zone closed-form benchmark.
- Adds exact zero-friction simultaneous-both-end uniform-shortening limit.
- Adds asymmetric left/right mirror-invariance benchmark to prove the equilibrium/neutral station is not hard-coded to `L/2`.

## Scope guard

`Pe / Pe_eff`, Elastic Shortening, Time-Dependent Losses, PMM, SLS/ULS, rebar, reports, and other member workflows remain outside this milestone.
