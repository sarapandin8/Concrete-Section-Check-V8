# CROSSBEAM.ANALYSIS4C7D8 — Combined V+T regression / traceability closeout

## Scope
Close the Precast Segmental Crossbeam Shear + Torsion regression gate after the accepted Flexure, Shear, and standalone Torsion fixes.

## Changes
- Clarified the Combined V+T source/count banner for the 30 m Segmental benchmark:
  - 20 retained sectional rows
  - 12 generated support rows
  - 10 one-sided physical-joint audit rows
  - 42 prepared rows total
  - 2 support/joint overlap rows remain physical-joint review only
  - 30 sectional decision rows + 10 joint-side audit rows in the combined result
- Changed Combined V+T `Provided` source wording from `Adopted verified source` to `Adopted calculation source · see station audit` so the UI does not over-certify summary template quantities.
- Added regression tests protecting prepared-vs-decision row ownership and source wording.

## Engineering logic preserved
- No ACI equations changed.
- No Shear/Torsion/Flexure capacity equations changed.
- No Segmental tendon-only Flexure rule changed.
- Physical-joint V+T transfer remains a separate REVIEW gate.
- Joint-side audit rows remain excluded from sectional PASS/FAIL/governing ownership.
- Cast-in-Place joint semantics remain separate.

## Verification
- `python -m py_compile app.py concrete_pmm_pro/analysis/crossbeam_uls_combined_vt.py concrete_pmm_pro/ui/analysis_page.py` — PASS
- `pytest` Combined V+T component/semantic suite — 18 passed
- Flexure + Shear + Torsion + Combined targeted regression — 57 passed

## Visual QA
The next UI review should confirm the Combined V+T source/count cards, four component views, D/C = 1.0 limit lines, and physical-joint REVIEW map remain clear and consistent.
