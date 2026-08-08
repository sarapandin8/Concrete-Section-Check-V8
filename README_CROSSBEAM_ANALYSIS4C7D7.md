# CROSSBEAM.ANALYSIS4C7D7 — Torsion traceability wording closeout

## Scope
Close two user-facing traceability inconsistencies found during visual QA of the standalone Crossbeam ULS Torsion workspace after ANALYSIS4C7D6.

## Changes
- Reword legacy blank Rebar Template summary-quantity warnings when a detailed adopted longitudinal bar layout is actually present and used by the torsion solver for provided Aℓ.
- Change the Torsion "Provided" card helper text from an over-certifying verified-source label to "Adopted calculation source · see station audit".
- Clarify the calculation-limitations scope so a standalone sectional FAIL remains FAIL and is never described as being downgraded to overall REVIEW; Combined V+T and physical-joint transfer remain separate completion gates.

## Engineering behavior preserved
- No ACI torsion equations changed.
- No threshold, φTn, φTth, At, Aℓ, or section-size calculation changed.
- No station ownership, support routing, or physical-joint audit logic changed.
- No Flexure, Shear, Combined V+T, Project JSON, or result-cache behavior changed.

## Verification
- `python -m py_compile app.py concrete_pmm_pro/analysis/crossbeam_uls_torsion.py concrete_pmm_pro/ui/analysis_page.py` — PASS
- `python -m pytest -q tests/test_crossbeam_analysis4c1_torsion_source_contract.py tests/test_crossbeam_analysis4_direct_uniaxial.py tests/test_crossbeam_analysis4c7d7_torsion_traceability_wording.py` — 12 passed
