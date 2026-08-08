# CROSSBEAM.ANALYSIS4C7D6 — Torsion decision/audit ownership cleanup

## Scope
Correct the Precast Segmental Crossbeam standalone ULS Torsion count and governing ownership semantics discovered during Segmental ULS regression QA.

## Engineering behavior
- One-sided physical-joint torsion rows remain fully calculated capacity audit evidence.
- One-sided joint audit rows are excluded from standalone sectional PASS/FAIL counts and sectional governing ranking.
- Physical-joint torsion transfer remains `REVIEW REQUIRED` and is not certified by the sectional route.
- Support checks that coincide with a physical joint remain REVIEW rows and are excluded from sectional decision counts.
- No ACI torsion equations, section capacities, prestress routing, or reinforcement equations were changed.
- ANALYSIS4C7D5 Flexure near-joint full-member demand continuity is preserved.

## 30 m benchmark count contract
- 20 retained sectional rows
- 12 generated support rows total
  - 10 eligible sectional support checks
  - 2 support / physical-joint overlap REVIEW rows
- 10 one-sided physical-joint audit rows
- 42 total calculation rows
- 30 standalone sectional decision checks
- 10 torsion-design-required sectional checks
- 20 below-threshold sectional checks

## Files changed
- `concrete_pmm_pro/analysis/crossbeam_uls_torsion.py`
- `concrete_pmm_pro/ui/analysis_page.py`
- `tests/test_crossbeam_analysis3b_joint_capacity_plot.py`

## Verification
- `python -m py_compile app.py concrete_pmm_pro/analysis/crossbeam_uls_torsion.py concrete_pmm_pro/ui/analysis_page.py concrete_pmm_pro/analysis/crossbeam_uls.py` — PASS
- `python -m pytest -q tests/test_crossbeam_analysis3_uls_torsion.py` — 13 passed
- `python -m pytest -q tests/test_crossbeam_analysis3b_joint_capacity_plot.py -k 'not test_flexure_capacity_is_one_full_member_tendon_only_envelope'` — 6 passed, 1 deselected
- `python -m pytest -q tests/test_crossbeam_analysis4c7c_torsion_combined_semantics.py` — 9 passed
- `python -m pytest -q tests/test_crossbeam_analysis4_direct_uniaxial.py` — 5 passed

## Known pre-existing regression
`tests/test_crossbeam_analysis3b_joint_capacity_plot.py::test_flexure_capacity_is_one_full_member_tendon_only_envelope` still fails on the untouched ANALYSIS4C7D5 package as well. This is the previously identified obsolete exact-joint plotting expectation and is not introduced by D6.

## Visual QA required
Re-run the standalone Torsion page and verify the top cards report the 42/30/10/20 ownership counts above before accepting D6 visually.
