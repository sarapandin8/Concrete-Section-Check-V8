# CROSSBEAM.PTLOSS2R1 — Single-End Anchor-Set Revalidation + Both-End Safety Lock

## Purpose

Revalidate Crossbeam anchorage-set/draw-in methodology before any result can feed effective prestress. PTLOSS2R1 replaces the active single-end zero-movement-capacity formulation with a full-path friction-coupled reverse-slip compatibility solve, and removes the historical PTLOSS2C final-state coupled both-end result from the design-use route.

## Engineering basis

### Single-end stressing — active preview route

The accepted PTLOSS1 post-friction diagram is the source of truth. From the active jacking anchorage:

`ΔfpA(s) = max[ΔfpA,0 − 2ΔfpF(s), 0]`

`Δa = 1000/Ep ∫ ΔfpA(s) ds`

The solver finds `ΔfpA,0` so the integrated tendon strain reduction equals the adopted anchorage draw-in `Δa`.

This permits two valid physical cases:

1. `Partial affected length`: `ΔfpA(s)` reaches zero before the dead end; the zero-loss station defines `s_a`.
2. `Full tendon affected`: `ΔfpA(s)` remains positive at the dead end; `s_a = L` and a nonzero dead-end stress loss is retained.

For a linear friction-loss diagram this generalized implementation reduces to the Caltrans similar-triangle equations:

`x_pA = sqrt(Ep Δa L / (1000 d))` in SI (`Ep,d` MPa; `Δa` mm; `L,x_pA` m)

`ΔfpA,0 = 2 d x_pA / L`

### Both-end stressing — locked

`Jack = Both` does not uniquely define final anchorage-set force history. PTLOSS2R1 therefore returns `REVIEW REQUIRED` for both-end anchor seating until a later sequence-aware milestone explicitly models and validates at least:

- simultaneous / equal both-end stressing;
- sequential Left → Right;
- sequential Right → Left.

The historical PTLOSS2C `FULL-LENGTH COUPLED` final-state compatibility algorithm remains private/historical only and is not routed into current design-use output.

## Validation benchmarks

PTLOSS2R1 regression tests reproduce published Caltrans Prestress Manual Appendix E examples after SI conversion:

- Example 2: `x_pA ≈ 109.5 ft`, `ΔfpA ≈ 15.97 ksi`.
- Example 3 one-end stressing: `x_pA ≈ 112 ft`, `ΔfpA ≈ 15.63 ksi`.

The same benchmark is also checked by round-tripping the SI solver output back to native US customary units.

## Safety boundaries

- `Pe` / `Pe_eff` remain locked.
- Both-end anchorage-set force is not calculated for design use.
- Elastic shortening and time-dependent losses remain untouched.
- Friction/wobble equations are unchanged.
- No PMM, SLS/ULS, rebar, report, or other member workflow solver is changed.

## Next milestone

`CROSSBEAM.PTLOSS2R2 — Sequence-Aware Both-End Anchorage Seating`

Define the stressing procedure as explicit project input, derive the force-history/state transition for each supported procedure, and validate against official two-end stressing / anchor-set benchmarks before any both-end result can be released.
