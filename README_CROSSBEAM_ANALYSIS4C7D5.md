# CROSSBEAM.ANALYSIS4C7D5 — Flexure near-joint demand continuity

## Scope
Fix the Precast Segmental Crossbeam ULS Flexure false narrow φMn sign-reversal spikes near physical segment joints.

## Engineering contract preserved
- Segmental Flexure Mn credit remains concrete compression + bonded Tendons only.
- Ordinary longitudinal rebar remains excluded from Segmental Mn.
- Cast-in-Place Flexure behavior is not changed.
- Exact physical-joint left/right capacities remain one-sided and are not averaged.
- Local station-dependent effective prestress fpe(s) remains active.
- Imported FEA demand is not modified by re-adding prestress forces.

## Code change
`concrete_pmm_pro/analysis/crossbeam_uls.py`

Generated near-joint Flexure demand recovery now uses the continuous full-member force source range (0 to member length) while retaining one-sided local Segment ownership for the capacity solve.

This prevents sparse Segment-local source rows from extrapolating through zero and falsely changing the M3 bending direction immediately adjacent to a physical segment joint.

## Regression test
`tests/test_crossbeam_analysis4_direct_uniaxial.py`

Added explicit near-joint regression checks at:
- J1-R near 100 mm, s = 4.6 m
- J5-L near 100 mm, s = 25.4 m

For the 30 m benchmark, both rows now recover M3 = +950 kN·m from the continuous member diagram, retain positive capacity plot sign, and solve on the Sagging (+M3) branch.

## Verification completed
- `python -m py_compile app.py concrete_pmm_pro/analysis/crossbeam_uls.py concrete_pmm_pro/ui/analysis_page.py` — PASS
- `python -m pytest -q tests/test_crossbeam_analysis4_direct_uniaxial.py` — 5 passed

A broader regression run identified an existing failure in `tests/test_crossbeam_analysis4c7c3_flexure_runtime_and_envelope.py`. The same test also fails on the untouched ANALYSIS4C7D4 packaged baseline, so it is not introduced by D5.

## Visual acceptance
Streamlit visual QA of the corrected Flexure chart remains required before declaring ULS Flexure fully closed.
