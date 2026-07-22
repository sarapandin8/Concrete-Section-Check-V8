# CROSSBEAM.PTLOSS3A — Symmetric-Pair Elastic-Shortening Source-Gate Foundation

This milestone activates the Crossbeam Elastic Shortening workspace as a source-gated engineering preview foundation without releasing final effective prestress.

## Engineering scope

- Uses the AASHTO LRFD post-tensioned elastic-shortening average framework as the published basis.
- Implements the project construction intent that geometrically symmetric left/right tendon pairs are stressed simultaneously.
- Derives stressing pairs from the adopted tendon geometry rather than tendon names.
- Treats each verified simultaneous pair as one equivalent stressing group for the sequential-stressing preview only when all groups are valid and have equivalent total jacking force.
- Shows pair-by-pair sequence factors and ES component losses when a valid `f_cgp` source is available.
- Continues the force chain from accepted `P after Anchorage Set`; the ES preview never restarts from `fpj`.

## Safety/source gates

- `f_cgp` remains source-blocked because the current Crossbeam workflow does not yet have a validated stressing-stage frame/self-weight section-response source.
- The app does not invent a portal-frame self-weight moment or silently omit it.
- Assigned concrete material `Ec` may be shown as a preview `Eci` source with explicit stressing-age review.
- Manual `f_cgp` and `Eci` overrides exist only inside advanced QA and cannot release `Pe/Pe_eff`.
- Unequal or unresolved stressing pairs block the simple group-factor preview.

## Validation

- Reproduces the reference Segmental/AASHTO average calculation: `N=16`, `Ep=197000 MPa`, `Eci=36669 MPa`, `f_cgp=36.26 MPa` -> `91.31 MPa` average ES.
- Verifies the default 8-tendon Crossbeam resolves as four symmetric simultaneous groups: `T1+T5`, `T2+T6`, `T3+T7`, `T4+T8`.
- Verifies four-group sequence factors `0.75, 0.50, 0.25, 0.00` and average factor `0.375`.
- Verifies post-ES station force is calculated from the accepted post-anchorage-set state, not from `fpj`.

## Boundary

This is a validated source-gate and formula foundation, not a final code-certified Elastic Shortening result. Final release requires a validated source-derived stressing-stage `f_cgp` route, stressing-stage modulus confirmation, pair/group procedure confirmation, and downstream effective-prestress integration.
