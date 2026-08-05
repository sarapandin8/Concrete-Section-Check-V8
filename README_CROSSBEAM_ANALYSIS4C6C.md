# CROSSBEAM.ANALYSIS4C6C — Station-dependent Effective Prestress for ULS

## Scope

- Replaced the single system-average ULS prestress scalar with tendon-specific local `fpe_i(s)` / `fse_i(s)` for Crossbeam Flexure, Shear, Torsion, and Combined V+T.
- Added a versioned Effective Prestress profile contract that stores canonical tendon/station rows, source coverage, source fingerprint, Project JSON persistence, and an explicit override state.
- Exact source stations are used directly; intermediate ULS stations use bracketed linear interpolation between the same Tendon's adjacent projected stations.
- Extrapolation beyond the available tendon profile is not permitted.
- Duplicate face rows at the same Tendon/station are collapsed deterministically; any stress spread remains visible in QA warnings and audit data.

## Engineering routing

- Flexure uses local `fpe_i(s)` as each bonded Tendon's initial steel stress/strain in the existing direct `P–M3` strain-compatibility solver.
- Shear uses local `fse_i(s)` for the ACI prestressed applicability and source terms while preserving the accepted `Vc`, `Vs`, and `phiVn` equations.
- Torsion uses the same local `fse_i(s)` source for `fpc(s)`, prestress-dominance routing, `Tth(s)`, and the accepted torsional capacity checks.
- Combined V+T carries the same local shear/torsion and flexure prestress evidence into its station audit and source status.
- Imported FEA `P/V2/T/M3` demands remain row-coupled and prestress force is not added to demand a second time.

## Source gates and migration

- A current Tendon/Station Effective Prestress profile covering `s=0` through `s=L` is required for every active Tendon.
- Legacy average-only links are preserved on load but block production ULS until the Effective Prestress workspace is refreshed.
- A uniform-average fallback is available only through an explicit engineering override flag; every affected Flexure, Shear, Torsion, and Combined V+T result is downgraded to `REVIEW` rather than `PASS`.
- Project JSON round-trips the profile rows and fingerprint without changing dormant construction-mode data.

## UI and traceability

- Flexure identifies `LOCAL fpe(s)` as the capacity-strain source and keeps the no-double-counting demand statement visible.
- Flexure, Shear, Torsion, and Combined audit tables expose the local prestress mode, local minimum/maximum stress, and Tendon source values.
- Source profile changes participate in ULS fingerprints and stale-result propagation.

## Engineering equations unchanged

- No ACI Flexure, Shear, Torsion, or Combined V+T resistance equation changed.
- No strength-reduction factor changed.
- No Column Face, `h/2`, support-footprint, physical-joint, ordinary-rebar-credit, or full-span end-station rule changed.
- No prestress-loss equation changed; this milestone changes only how accepted Effective Prestress is consumed by ULS.

## Verification

- `python -m compileall -q app.py concrete_pmm_pro tests` — PASS.
- Crossbeam Analysis inventory — 107/107 passed when executed in bounded batches.
- Complete Crossbeam inventory — 636 collected, 630 passed, 6 verified pre-existing source-string/editor-count failures, 0 new failures.
- Project JSON / source-contract targeted suite — 55 passed.
- Deployment dependency contract — 1 passed (`streamlit==1.61.0`, `starlette==1.3.1`).

## Repo summary

Use tendon-specific station-dependent Effective Prestress across Crossbeam Flexure, Shear, Torsion, and Combined V+T with interpolation audit, Project JSON persistence, stale-source fingerprints, and conservative blocking or REVIEW fallback for legacy average-only sources.
