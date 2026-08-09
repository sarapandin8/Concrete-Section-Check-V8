# CROSSBEAM.ANALYSIS4C7D11 — CIP ULS cross-workflow regression closeout

## Scope
Close Milestone C from the 2026-08-07 Crossbeam ULS handoff by proving that the Segmental-specific ULS changes completed through ANALYSIS4C7D10 do not contaminate the Cast-in-Place Crossbeam workflow.

## Application code changes
None. This milestone is a regression-lock / acceptance milestone. The accepted D10 engineering implementation is preserved unchanged.

## New regression coverage
Added `tests/test_crossbeam_analysis4c7d11_cip_uls_regression.py`.

The new tests prove:

1. **CIP Flexure remains monolithic and rebar-active**
   - flexure credit basis = `SECTION REBAR + TENDONS`;
   - ordinary longitudinal reinforcement receives `FULL CREDIT`;
   - credited ordinary bars and As are nonzero;
   - no physical Segment joint or ±100 mm near-joint rows are generated;
   - only `ZONE INTERIOR` and `COLUMN FACE` locations appear in the CIP Flexure result.

2. **CIP Shear / Torsion / Combined V+T remain joint-free**
   - Zone interior, Column Face, and ACI h/2 sectional routes remain active where applicable;
   - no physical-joint rows are generated;
   - Combined V+T reports `joint_side_checks = 0`, `joint_review_count = 0`, and `joint_transfer_status = NOT APPLICABLE`;
   - all Combined V+T rows remain sectional decision rows for the CIP benchmark.

3. **Construction-type isolation survives Segmental → CIP → Segmental switching**
   - Segmental Flexure returns to `TENDON-ONLY` with physical-joint and near-joint semantics;
   - CIP Flexure switches to `SECTION REBAR + TENDONS` with no joint semantics;
   - switching back restores the original Segmental behavior;
   - dormant Precast and CIP reinforcement datasets are preserved unchanged during the switch.

## Engineering behavior preserved
- Segmental Flexure remains tendon-only.
- CIP Flexure continues to credit authorized ordinary longitudinal reinforcement.
- Segmental physical-joint and near-joint rows remain Segmental-only.
- CIP Zone boundaries remain monolithic property boundaries, not physical construction joints.
- Local station-dependent effective prestress remains active.
- Shear Column Face / ACI h/2 routing remains active.
- Physical-joint V+T transfer remains outside the current Segmental sectional ULS milestone and is not applicable to CIP.
- No ACI strength equation or solver capacity equation is changed by D11.

## Verification
- `python -m py_compile app.py concrete_pmm_pro/analysis/crossbeam_uls.py concrete_pmm_pro/analysis/crossbeam_uls_shear.py concrete_pmm_pro/analysis/crossbeam_uls_torsion.py concrete_pmm_pro/analysis/crossbeam_uls_combined_vt.py concrete_pmm_pro/ui/analysis_page.py` — PASS
- D11 + D10/D9/Combined semantics/Torsion wording targeted group — 22 passed
- Existing CIP workflow/rebar regression group — 58 passed
- Flexure / Shear / station-geometry / local-fpe / Segmental tendon-only targeted group — 46 passed
- Standalone Torsion solver regression — 13 passed

Total completed regression executions for this milestone: **139 passed**.
